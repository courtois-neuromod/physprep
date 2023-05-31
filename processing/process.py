# -*- coding: utf-8 -*-
# !/usr/bin/env python
"""
Neuromod processing utilities
"""
# dependencies
import os
import json
import click
import numpy as np
import pandas as pd

# high-level processing utils
from heartpy import process
from systole.correction import correct_rr, correct_peaks
from neurokit2 import ecg_peaks, ppg_findpeaks

# signal utils
import neurokit2 as nk
from neurokit2.misc import as_vector
from systole.utils import input_conversion
from neurokit2 import signal_rate
from neurokit2.signal.signal_formatpeaks import _signal_from_indices

# home brewed cleaning utils
from clean import neuromod_ecg_clean, neuromod_eda_clean, neuromod_ppg_clean, neuromod_rsp_clean


# ==================================================================================
# Processing pipeline
# ==================================================================================


@click.command()
@click.argument("source", type=str)
@click.argument("sub", type=str)
@click.argument("ses", type=str)
@click.argument("outdir", type=str)
@click.argument("multi_echo", type=bool)
def neuromod_bio_process(source, sub, ses, outdir, multi_echo):
    """
    Run processing pipeline on specified biosignals.

    Parameters
    ----------
    source : str
        The main directory contaning the segmented runs.
    sub : str
        The id of the subject.
    ses : str
        The id of the session.
    outdir : str
        The directory to save the outputs.
    multi_echo : bool
        Indicate if the multi-echo sequence was used or not.

    Examples
    --------
    In terminal
    >>> python process.py /home/user/dataset/converted/ sub-01 ses-001 /home/user/dataset/derivatives/ True False
    """
    # Load tsv files contained in source/sub/ses
    data_tsv, data_json, filenames_tsv = load_segmented_runs(source, sub, ses)
    sampling_rate = data_json["SamplingFrequency"]

    # initialize returned objects
    for idx, df in enumerate(data_tsv):
        print(
            f"---Processing biosignals for {sub} {ses}: run {filenames_tsv[idx][-2:]}---"
        )

        bio_info = {}
        bio_df = pd.DataFrame()

        # initialize each signals
        ppg_raw = df["PPG"]
        rsp_raw = df["RSP"]
        eda_raw = df["EDA"]
        ecg_raw = df["ECG"]

        # ppg
        print("******PPG workflow: begin***")
        ppg, ppg_info = ppg_process(ppg_raw, sampling_rate=sampling_rate)
        bio_info["PPG"] = ppg_info
        bio_df = pd.concat([bio_df, ppg], axis=1)
        print("***PPG workflow: done***")

        # ecg
        print("***ECG workflow: begin***")
        ecg, ecg_info = ecg_process(ecg_raw, sampling_rate=sampling_rate, me=multi_echo)
        bio_info["ECG"] = ecg_info
        bio_df = pd.concat([bio_df, ecg], axis=1)
        print("***ECG workflow: done***")

        #  rsp
        print("***Respiration workflow: begin***")
        rsp, rsp_info = rsp_process(
            rsp_raw, sampling_rate=sampling_rate, method="khodadad2018"
        )
        bio_info["RSP"] = rsp_info
        bio_df = pd.concat([bio_df, rsp], axis=1)
        print("***Respiration workflow: done***")

        #  eda
        print("***Electrodermal activity workflow: begin***")
        eda, eda_info = eda_process(eda_raw, sampling_rate, me=multi_echo)
        bio_info["EDA"] = eda_info
        bio_df = pd.concat([bio_df, eda], axis=1)
        print("***Electrodermal activity workflow: done***")

        # return a dataframe
        bio_df["time"] = df["time"]

        print("***Saving processed biosignals***")
        bio_df.to_csv(
            os.path.join(
                outdir, sub, ses, f"{filenames_tsv[idx]}" + "_physio" + ".tsv.gz"
            ),
            sep="\t",
        )
        with open(
            os.path.join(
                outdir, sub, ses, f"{filenames_tsv[idx]}" + "_physio" + ".json"
            ),
            "w",
        ) as fp:
            json.dump(bio_info, fp)
            fp.close()


# ==================================================================================
# Loading functions
# ==================================================================================


def load_json(filename):
    """
    Parameters
    ----------
    filename : str
        File path of the .json to load.

    Returns
    -------
    data : dict
        Dictionary with the content of the .json passed in argument.
    """
    tmp = open(filename)
    data = json.load(tmp)
    tmp.close()

    return data


def load_segmented_runs(source, sub, ses):
    """
    Parameters
    ----------
    source : str
        The main directory contaning the segmented runs.
    sub : str
        The id of the subject.
    ses : str
        The id of the session.

    Returns
    -------
    data_tsv : list
        List containing dataframes with the raw signal for each run.
    data_json : dict
        Dictionary containing metadata.
    filenames : list
        List contaning the filename for each segmented run without the extension.
    """
    data_tsv, filenames = [], []
    files_tsv = [f for f in os.listdir(os.path.join(source, sub, ses)) if "tsv.gz" in f]
    # Remove files ending with _01
    files_tsv = [f for f in files_tsv if "_01." not in f]
    files_tsv.sort()

    for tsv in files_tsv:
        filename = tsv.split(".")[0]
        filenames.append(filename)
        print(f"---Reading data for {sub} {ses}: run {filename[-2:]}---")
        json = filename + ".json"
        print("Reading json file")
        data_json = load_json(os.path.join(source, sub, ses, json))
        print("Reading tsv file")
        data_tsv.append(
            pd.read_csv(
                os.path.join(source, sub, ses, tsv),
                sep="\t",
                compression="gzip",
                names=data_json["Columns"],
            )
        )

    return data_tsv, data_json, filenames


# ==================================================================================
# Processing functions
# ==================================================================================


def process_cardiac(signal_raw, signal_cleaned, sampling_rate=10000, data_type="PPG"):
    """
    Process cardiac signal.

    Extract features of interest for neuromod project.

    Parameters
    ----------
    signal_raw : array
        Raw PPG/ECG signal.
    signal_cleaned : array
        Cleaned PPG/ECG signal.
    sampling_rate : int
        The sampling frequency of `signal_raw` (in Hz, i.e., samples/second).
        Defaults to 10000.
    data_type : str
        Precise the type of signal to be processed. The function currently
        support PPG and ECG signal processing.
        Default to 'PPG'.

    Returns
    -------
    signals : DataFrame
        A DataFrame containing the cleaned PPG/ECG signals.
        - the raw signal.
        - the cleaned signal.
        - the heart rate as measured based on PPG/ECG peaks.
        - the PPG/ECG peaks marked as "1" in a list of zeros.
    info : dict
        Dictionary containing list of intervals between peaks.
    """
    # heartpy
    print("HeartPy processing started")
    wd, m = process(
        signal_cleaned,
        sampling_rate,
        reject_segmentwise=True,
        interp_clipping=True,
        report_time=True,
    )
    cumsum = 0
    rejected_segments = []
    for i in wd["rejected_segments"]:
        cumsum += int(np.diff(i) / sampling_rate)
        rejected_segments.append((int(i[0]), int(i[1])))
    print("Heartpy found peaks")

    # Find peaks
    print("Neurokit processing started")
    if data_type in ["ecg", "ECG"]:
        _, info = ecg_peaks(
            ecg_cleaned=signal_cleaned,
            sampling_rate=sampling_rate,
            method="nabian2018",
            correct_artifacts=True,
        )
        info[f"{data_type.upper()}_Peaks"] = info[f"{data_type.upper()}_R_Peaks"]
    elif data_type in ["ppg", "PPG"]:
        info = ppg_findpeaks(signal_cleaned, sampling_rate=sampling_rate)
    else:
        print("Please use a valid data type: 'ECG' or 'PPG'")

    info[f"{data_type.upper()}_Peaks"] = info[f"{data_type.upper()}_Peaks"].tolist()
    peak_list_nk = _signal_from_indices(
        info[f"{data_type.upper()}_Peaks"], desired_length=len(signal_cleaned)
    )
    print("Neurokit found peaks")

    # peak to intervals
    rr = input_conversion(
        info[f"{data_type.upper()}_Peaks"],
        input_type="peaks_idx",
        output_type="rr_ms",
        sfreq=sampling_rate,
    )

    # correct beat detection
    corrected, (nMissed, nExtra, nEctopic, nShort, nLong) = correct_rr(rr)
    corrected_peaks = correct_peaks(peak_list_nk, n_iterations=4)
    print("systole corrected RR series")
    # Compute rate based on peaks
    rate = signal_rate(
        info[f"{data_type.upper()}_Peaks"],
        sampling_rate=sampling_rate,
        desired_length=len(signal_raw),
    )

    # sanitize info dict
    info.update(
        {
            f"{data_type.upper()}_ectopic": nEctopic,
            f"{data_type.upper()}_short": nShort,
            f"{data_type.upper()}_long": nLong,
            f"{data_type.upper()}_extra": nExtra,
            f"{data_type.upper()}_missed": nMissed,
            f"{data_type.upper()}_clean_rr_systole": corrected.tolist(),
            f"{data_type.upper()}_clean_rr_hp": [float(v) for v in wd["RR_list_cor"]],
            f"{data_type.upper()}_rejected_segments": rejected_segments,
            f"{data_type.upper()}_cumulseconds_rejected": int(cumsum),
            f"{data_type.upper()}_%_rejected_segments": float(
                cumsum / (len(signal_raw) / sampling_rate)
            ),
        }
    )
    if data_type in ["ecg", "ECG"]:
        info[f"{data_type.upper()}_R_Peaks"] = info[
            f"{data_type.upper()}_R_Peaks"
        ].tolist()
        del info[f"{data_type.upper()}_Peaks"]

    # Prepare output
    signals = pd.DataFrame(
        {
            f"{data_type.upper()}_Raw": signal_raw,
            f"{data_type.upper()}_Clean": signal_cleaned,
            f"{data_type.upper()}_Peaks_NK": peak_list_nk,
            f"{data_type.upper()}_Peaks_Systole": corrected_peaks["clean_peaks"],
            f"{data_type.upper()}_Rate": rate,
        }
    )

    return signals, info


def ppg_process(ppg_raw, sampling_rate=10000):
    """
    Process PPG signal.

    Custom processing function for neuromod PPG acquisition.

    Parameters
    ----------
    ppg_raw : vector
        The raw PPG channel.
    sampling_rate : int
        The sampling frequency of `ppg_raw` (in Hz, i.e., samples/second).
        Default to 10000.

    Returns
    -------
    signals : DataFrame
        A DataFrame containing the cleaned ppg signals.
        - *"PPG_Raw"*: the raw signal.
        - *"PPG_Clean"*: the cleaned signal.
        - *"PPG_Rate"*: the heart rate as measured based on PPG peaks.
        - *"PPG_Peaks"*: the PPG peaks marked as "1" in a list of zeros.
    info : dict
        Dictionary containing list of intervals between peaks.
    """
    ppg_signal = as_vector(ppg_raw)

    # Prepare signal for processing
    print("Cleaning PPG")
    ppg_signal, ppg_cleaned = neuromod_ppg_clean(
        ppg_signal, sampling_rate=10000.0, downsampling=2500
    )
    print("PPG Cleaned")
    # Process clean signal
    signals, info = process_cardiac(
        ppg_signal, ppg_cleaned, sampling_rate=10000, data_type="PPG"
    )

    return signals, info


def ecg_process(ecg_raw, sampling_rate=10000, method="bottenhorn", me=True):
    """
    Process ECG signal.

    Custom processing for neuromod ECG acquisition.

    Parameters
    -----------
    ecg_raw : vector
        The raw ECG channel.
    sampling_rate : int
        The sampling frequency of `ecg_raw` (in Hz, i.e., samples/second).
        Default to 10000.
    method : str
        The processing pipeline to apply.
        Default to 'bottenhorn'.
    mr : bool
        True if MB-ME sequence was used. Otherwise, considered that the MB-SE
        sequence was used.
        Default to True.

    Returns
    -------
    signals : DataFrame
        A DataFrame containing the cleaned ecg signals.
        - *"ECG_Raw"*: the raw signal.
        - *"ECG_Clean"*: the cleaned signal.
        - *"ECG_Rate"*: the heart rate as measured based on ECG peaks.
    info : dict
        Dictionary containing list of peaks.
    """
    ecg_signal = as_vector(ecg_raw)

    # Prepare signal for processing
    print("Cleaning ECG")
    ecg_signal, ecg_cleaned = neuromod_ecg_clean(
        ecg_signal, sampling_rate=sampling_rate, method=method, me=me, downsampling=2500
    )
    print("ECG Cleaned")
    # Process clean signal
    signals, info = process_cardiac(
        ecg_signal, ecg_cleaned, sampling_rate=sampling_rate, data_type="ECG"
    )

    return signals, info


def eda_process(eda_raw, sampling_rate=10000, me=True):
    """
    Process EDA signal.

    Custom processing for neuromod EDA acquisition.

    Parameters
    -----------
    eda_raw : vector
        The raw EDA channel.
    sampling_rate : int
        The sampling frequency of `eda_raw` (in Hz, i.e., samples/second).
        Default to 10000.
    mr : bool
        True if MB-ME sequence was used. Otherwise, considered that the MB-SE
        sequence was used.
        Default to True.

    Returns
    -------
    signals : DataFrame
        A DataFrame containing the cleaned eda signals.
        - *"EDA_Raw"*: the raw signal.
        - *"EDA_Clean"*: the clean signal.
        - *"EDA_Tonic"*: the tonic component of the EDA signal.
        - *"EDA_Phasic"*: the phasic component of the EDA signal.
    info : dict
        Dictionary containing a list of SCR peaks.
    """
    eda_signal = as_vector(eda_raw)

    # Prepare signal for processing
    print("Cleaning EDA")
    eda_signal, eda_cleaned = neuromod_eda_clean(
        eda_signal, sampling_rate=sampling_rate, me=me, downsampling=2500
    )
    print("EDA Cleaned")
    # Process clean signal
    signals, info = nk.eda_process(
        eda_cleaned, sampling_rate=sampling_rate, method="neurokit"
    )

    for k in info.keys():
        if isinstance(info[k], np.ndarray):
            info[k] = info[k].tolist()

    return signals, info


def rsp_process(rsp_raw, sampling_rate=10000, method="khodadad2018"):
    """
    Parameters
    ----------
    rsp_raw : vector
        The raw RSP channel
    sampling_rate : int
        The sampling frequency of `eda_raw` (in Hz, i.e., samples/second).
        Default to 10000.

    Returns
    -------
    signals : DataFrame
        A DataFrame containing the cleaned RSP signals.
    info : dict
        Dictionary containing a list of peaks and troughts.

    References
    ----------
    Khodadad, D., Nordebo, S., Müller, B., Waldmann, A., Yerworth, R., Becher, T., ...
        & Bayford, R. (2018). Optimized breath detection algorithm in electrical impedance
        tomography. Physiological measurement, 39(9), 094001.

    See also
    --------
    https://neuropsychology.github.io/NeuroKit/functions/rsp.html#preprocessing
    """
    rsp_signal = as_vector(rsp_raw)

    # Clean and filter respiratory signal
    print("Cleaning RSP")
    rsp_signal, rsp_cleaned = neuromod_rsp_clean(
        rsp_signal, sampling_rate=sampling_rate, downsampling=2500
    )
    # Process clean signal
    print("Processing RSP")
    signals, info = nk.rsp_process(
        rsp_cleaned, sampling_rate=sampling_rate
    )
    print("RSP Cleaned and processed")

    for k in info.keys():
        if isinstance(info[k], np.ndarray):
            info[k] = info[k].tolist()

    return signals, info


if __name__ == "__main__":
    # Physio processing pipeline
    neuromod_bio_process()
