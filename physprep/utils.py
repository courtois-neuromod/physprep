"""Utilities for Physprep"""

import json
import os
import pickle


def _check_filename(outdir, filename, extension=None, overwrite=False):
    # Check extension if specified
    if extension is not None:
        root, ext = os.path.splitext(filename)
        if not ext or ext != extension:
            filename = root + extension

    # Check if file already exist
    if os.path.exists(os.path.join(outdir, filename).strip()):
        if not overwrite:
            raise FileExistsError(
                "Killing the script because the file already exist. "
                "If you want to overwrite the file, set the `overwrite` "
                "flag to `True`"
            )
        else:
            print(
                "WARNING: This file already exist, but will be overwritten. "
                "If you do not want to overwrite the file, kill the script and "
                "set the `overwrite` flag to `False`"
            )

    return filename


def _check_input_validity(option, valid_options, empty=True):
    if type(valid_options) is list:
        if empty:
            if option in ["", " "]:
                return option
        if int in valid_options or float in valid_options:
            if "." in option or "," in option:
                return float(option)
            elif option.isdigit() is False:
                print("**Please enter a positive number.")
                return False
            else:
                return int(option)
        else:
            if option not in valid_options:
                print(f"**Please enter a valid option: {', '.join(valid_options)}.")
                return False
            else:
                if option in [
                    "resampling",
                    "resample",
                    "upsampling",
                    "upsample",
                    "downsampling",
                    "downsample",
                ]:
                    option = "signal_resample"
                return option
    if valid_options in [int, "odd"]:
        if option.isdigit() is False:
            print("**Please enter a positive integer.")
            return False
        if valid_options == "odd":
            if int(option) % 2 == 0:
                print("**Please enter an odd number.")
                return False
            else:
                return int(option)
        else:
            return int(option)
    if valid_options == float:
        if "." in option or "," in option:
            return float(option)
        else:
            print("**Please enter a positive float.")
            return False


def _create_ref():
    # Instantiate variable
    ref = {}
    publication_type = book = False
    # Collect input
    ref["authors"] = input("Enter the author(s) name: \n")
    ref["year"] = input("Enter the publication year: \n")
    ref["title"] = input("Enter the publication title: \n")
    while publication_type is False:
        publication_type = input("Is the source of information a journal ? [y/n] \n")
        publication_type = _check_input_validity(publication_type, ["y", "n"])
    if publication_type == "y":
        ref["journal"] = input("Enter the title of the journal: \n")
        ref["volume"] = input("Enter the volume number: \n")
        ref["issue"] = input("Enter the issue number: \n")
        ref["page"] = input("Enter the page numbers: \n")
        ref["doi"] = input("Enter the DOI: \n")
    else:
        while book is False:
            book = input("Is the source of information a book ? [y/n] \n")
            book = _check_input_validity(book, ["y", "n"])
        if book == "y":
            ref["publisher"] = input("Enter the name of the publisher: \n")
            ref["location"] = input(
                "Enter the location of the publisher (city and state/country): \n"
            )

    ref["url"] = input("Enter the URL of the source: \n")

    return ref


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
    try:
        with open(filename, "r") as tmp:
            data = json.loads(tmp.read())
        tmp.close()
    except Exception:
        try:
            with open(filename, "rb") as tmp:
                data = pickle.load(tmp)
            tmp.close()
        except Exception:
            pass

    return data


def create_config_preprocessing(outdir, filename, overwrite=False):
    """
    Generate a configuration file for the preprocessing strategy based on the user inputs.

    Parameters
    ----------
    outdir: str, Path
        Saving directory.
    filename: str
        Saving filename.
    overwrite: bool
        If `True`, overwrite the existing file with the specified `filename` in the
        `outdir` directory. If `False`, the function will not be executed if there is
        already a file with the specified `filename` in `outdir`.
    """
    # Instantiate variables
    steps = []
    valid_filters = ["butterworth", "fir", "bessel", "savgol", "notch"]
    valid_steps = [
        "filtering",
        "resampling",
        "resample",
        "upsampling",
        "upsample",
        "downsampling",
        "downsample",
    ]

    filename = _check_filename(outdir, filename, extension=".json", overwrite=overwrite)

    while True:
        tmp = {}
        tmp_params = {}
        step = input(
            "\n Enter a processing step among the following: resampling, "
            "filtering.\nIf you do not want to add a step, just press enter.\n"
        )
        step = _check_input_validity(step.lower(), valid_steps, empty=True)
        if step not in ["", " "]:
            method = (
                lowcut
            ) = highcut = order = desired_sampling_rate = cutoff = ref = False
            tmp["step"] = step
            if step in ["filtering", "filter"]:
                while method is False:
                    method = input(
                        "\n Enter the filter type among the following: "
                        f"{', '.join(valid_filters)}.\n"
                    )
                    tmp_params["method"] = _check_input_validity(
                        method.lower(), valid_filters
                    )
                if method == "notch":
                    Q = input("\n Enter the quality factor for the notch filter. \n")
                    tmp_params["Q"] = _check_input_validity(Q, [int, float])
                if method in ["butterworth", "fir", "bessel"]:
                    while cutoff is False:
                        while lowcut is False:
                            lowcut = input(
                                "\n Enter the lower cutoff frequency (Hz). "
                                "If you do not want to apply a high pass or band "
                                "pass filter, just press enter. \n"
                            )
                            lowcut = _check_input_validity(
                                lowcut, [int, float], empty=True
                            )
                            if lowcut not in ["", " "]:
                                tmp_params["lowcut"] = lowcut
                        while highcut is False:
                            highcut = input(
                                "\n Enter the higher cutoff frequency (Hz). "
                                "If you do not want to apply a low pass filter "
                                "or band pass filter, just press enter. \n"
                            )
                            highcut = _check_input_validity(
                                highcut, [int, float], empty=True
                            )
                            if highcut not in ["", " "]:
                                tmp_params["highcut"] = highcut
                        if lowcut in ["", " "] and highcut in ["", " "]:
                            print(
                                "**Please enter either the filter lower cutoff frequency "
                                "and/or the filter higher cutoff frequency"
                            )
                            lowcut = highcut = False
                        else:
                            cutoff = True
                if method in ["savgol", "butterworth", "bessel"]:
                    while order is False:
                        order = input(
                            "\n Enter the filter order. Must be a positive " "integer.\n"
                        )
                        tmp_params["order"] = _check_input_validity(order, int)
                if method == "savgol":
                    window_size = input(
                        "\n Enter the length of the filter window. Must be an odd "
                        "integer.\n"
                    )
                    tmp_params["window_size"] = _check_input_validity(window_size, "odd")

            if step == "signal_resample":
                while desired_sampling_rate is False:
                    desired_sampling_rate = input(
                        "\n Enter the desired sampling frequency "
                        "to resample the signal (in Hz). \n"
                    )
                    desired_sampling_rate = _check_input_validity(
                        desired_sampling_rate, [int, float]
                    )
                    tmp_params["desired_sampling_rate"] = desired_sampling_rate

            tmp["parameters"] = tmp_params

            while ref is False:
                ref = input("\n Is there a reference related to that step ? [y/n] \n")
                ref = _check_input_validity(ref, ["y", "n"], empty=False)
            if ref == "y":
                tmp["reference"] = _create_ref()
            steps.append(tmp)
        else:
            print("\n---Saving configuration file---")
            with open(os.path.join(outdir, filename), "w") as f:
                json.dump(steps, f, indent=4)
            break


def create_config_workflow(outdir, filename, dir_preprocessing=None, overwrite=False):
    """
    Generate a configuration file for the workflow strategy based on the user inputs.

    Parameters
    ----------
    outdir: str, Path
        Saving directory.
    dir_preprocessing: str, Path
        Directory of the preprocessing configuration files. If `None`, assumes that
        the configuration files are located in the `outdir`. Default: `None`.
    filename: str
        Saving filename.
    overwrite: bool
        If `True`, overwrite the existing file with the specified `filename` in the
        `outdir` directory. If `False`, the function will not be executed if there is
        already a file with the specified `filename` in `outdir`.
    """
    # Instantiate variables
    signals = {}
    valid_signals = [
        "cardiac_ppg",
        "cardiac_ecg",
        "electrodermal",
        "respiratory",
        "trigger",
    ]
    preprocessing_strategy = [
        os.path.splitext(f)[0]
        for f in os.listdir("./physprep/data/preprocessing_strategy/")
    ]
    preprocessing_strategy.append("new")

    if dir_preprocessing is None:
        dir_preprocessing = outdir

    filename = _check_filename(outdir, filename, extension=".json", overwrite=overwrite)

    while True:
        signal = preprocessing = False
        while signal is False:
            signal = input(
                "\n Enter the type of signal to process. Currently only the (pre-)"
                f"processing of {', '.join(valid_signals)}. \nIf you do not want to add "
                "another type of signal, just press enter.\n"
            )
            signal = _check_input_validity(signal.lower(), valid_signals, empty=True)

        if signal not in ["", " "]:
            signals[signal] = {}
            # Associate abrreviation to the signal type
            if signal == "cardiac_ppg":
                signals[signal] = {
                    "id": "PPG",
                    "Description": "continuous pulse measurement",
                    "Units": "V",
                }
            elif signal == "cardiac_ecg":
                signals[signal] = {
                    "id": "ECG",
                    "Description": "continuous electrocardiogram measurement",
                    "Units": "mV",
                }
            elif signal == "electrodermal":
                signals[signal] = {
                    "id": "EDA",
                    "Description": "continuous electrodermal activity measurement",
                    "Units": "microsiemens",
                }
            elif signal == "respiratory":
                signals[signal] = {
                    "id": "RESP",
                    "Description": "continuous breathing measurement",
                    "Units": "cm H2O",
                }
            elif signal == "trigger":
                signals[signal] = {
                    "id": "TTL",
                    "Description": "continuous measurement of the scanner trigger signal",
                    "Units": "V",
                }

            # Ask for the channel name associated with the signal
            channel = input(
                "\n Enter the name of the channel in your acq file associated with the "
                f"{signal} signal: \n"
            )
            signals[signal].update({"channel": channel})

            if signal != "trigger":
                # Add preprocessing strategy to the workflow
                while preprocessing is False:
                    preprocessing = input(
                        "\n Enter the name of the preprocessing "
                        f"strategy to clean the {signal} signal. Choose among the "
                        "current configuration files by providing the name of the "
                        "strategy, \n or create a new configuration file. To create a "
                        "new configuration file type `new`.\n Otherwise, choose among "
                        f"those strategy: {', '.join(preprocessing_strategy[:-1])}.\n"
                    )
                    preprocessing = _check_input_validity(
                        preprocessing, preprocessing_strategy, empty=True
                    )

                if preprocessing == "new":
                    filename_preprocessing = input(
                        "\n Enter the name of the preprocessing "
                        "strategy. The given name will be used as the name of the json "
                        "file.\n"
                    )
                    filename_preprocessing = _check_filename(
                        outdir,
                        filename_preprocessing,
                        extension=".json",
                        overwrite=overwrite,
                    )
                    # Create the preprocessing configuration file
                    create_config_preprocessing(
                        outdir, filename_preprocessing, overwrite=overwrite
                    )
                    # Add preprocessing config file directory to the workflow config file
                    signals[signal].update(
                        {
                            "preprocessing_strategy": os.path.join(
                                dir_preprocessing, filename_preprocessing
                            )
                        }
                    )
                else:
                    filename_preprocessing = _check_filename(
                        outdir, preprocessing, extension=".json", overwrite=overwrite
                    )
                    signals[signal].update(
                        {
                            "preprocessing_strategy": os.path.join(
                                dir_preprocessing, filename_preprocessing
                            )
                        }
                    )

        else:
            # Save the configuration file only if there is at least one signal
            if bool(signals):
                print("\n---Saving configuration file---")
                with open(os.path.join(outdir, filename), "w") as f:
                    json.dump(signals, f, indent=4)
            break
