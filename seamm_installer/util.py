# -*- coding: utf-8 -*-

"""Utility methods for the SEAMM installer."""

# from datetime import datetime
import json
from packaging.version import Version
from pathlib import Path
import pprint
import shutil
import subprocess

from platformdirs import user_data_dir
import requests

from .conda import Conda
from . import my
from .pip import Pip

# from .metadata import core_packages, molssi_plug_ins, excluded_plug_ins


class JSONEncoder(json.JSONEncoder):
    """Class for handling the package versions in JSON."""

    def default(self, obj):
        if isinstance(obj, Version):
            return {"__type__": "Version", "data": str(obj)}
        else:
            return json.JSONEncoder.default(self, obj)


class JSONDecoder(json.JSONDecoder):
    """Class for handling the package versions in JSON."""

    def __init__(self):
        super().__init__(object_hook=self.dict_to_object)

    def dict_to_object(self, d):
        if "__type__" in d:
            type_ = d.pop("__type__")
            if type_ == "Version":
                return Version(d["data"])
            else:
                # Oops... better put this back together.
                d["__type__"] = type
        return d


def create_env(conda_packages, pypi_packages, installed_packages=[]):
    """Create the environment files for the packages.

    Parameters
    ----------
    conda_packages : [str]
        The packages from conda
    pypi_packages : [str]
        The packages from PyPi
    installed_packages : [str]
        The installed packages for dependecy pinning
    """
    print("Creating the environment file for the packages.")
    prelines = [
        """name: seamm
channels:
  - conda-forge
  - defaults
dependencies:
  - pip
  - python
"""
    ]

    lines = []
    # First the conda installable packages, including any dependencies
    for repo in ("conda-forge", "pypi"):
        if repo == "conda-forge":
            lines.extend(prelines)
            spc = 2 * " "
            packages = conda_packages
        else:
            lines.append("  # PyPi packages")
            lines.append("  - pip:")
            spc = 6 * " "
            packages = pypi_packages

        for _type in ("Core package", "MolSSI plug-in", "3rd-party plug-in"):
            if _type not in my.package_metadata:
                continue
            lines.append(f"{spc}# {_type}s")
            for package in sorted(my.package_metadata[_type].keys()):
                base = package.split("==")[0]
                if base in packages:
                    lines.append(f"{spc}- {package}")
            lines.append("")

        # Are there any dependencies that require conda installs?
        dependencies = []
        for _type in ("Core package", "MolSSI plug-in", "3rd-party plug-in"):
            if _type not in my.package_metadata:
                continue
            for package, meta in my.package_metadata[_type].items():
                if package in installed_packages and "dependencies" in meta:
                    for dependency, depdata in meta["dependencies"].items():
                        if depdata["repository"] == repo:
                            dependencies.append(
                                f"{spc}# {package}: {depdata['comment']}"
                            )
                            if "pinning" in depdata and depdata["pinning"] != "":
                                dependencies.append(
                                    f"{spc}- {dependency}{depdata['pinning']}"
                                )
                            else:
                                dependencies.append(f"{spc}- {dependency}")

        if len(dependencies) > 0:
            lines.append(f"{spc}# Dependencies that require special handling\n")
            lines.extend(dependencies)
            lines.append("")

    return "\n".join(lines)


def find_packages(progress=True, update=None, update_cache=False, cache_valid=1):
    """Find the Python packages in SEAMM.

    Parameters
    ----------
    progress : bool = True
        Whether to print out dots to show progress.
    update_cache : bool = False
        Update the cache (package db) no matter what.
    cache_valid : int = 1
        How many days before updating the cache. Defaults to a week.

    Returns
    -------
    dict(str, str)
        A dictionary with information about the packages.
    """
    url = "https://zenodo.org/api/records/7789854/versions/latest"
    try:
        response = requests.get(url)
        record = response.json(cls=JSONDecoder)
    except Exception as e:
        raise RuntimeError(f"Error finding the package list from Zenodo: {str(e)}")

    # Find SEAMM_packages.json
    url = None
    for data in record["files"]:
        if data["key"] == "SEAMM_packages.json":
            url = data["links"]["self"]
            break
    if url is None:
        raise RuntimeError(
            "Unable to get the package list from Zenodo. "
            "There is no file 'SEAMM_packages.json'"
        )

    try:
        response = requests.get(url)
        package_db = response.json(cls=JSONDecoder)
    except Exception as e:
        raise RuntimeError(f"Error getting the package list from Zenodo: {str(e)}")

    my.package_metadata = package_db["metadata"] if "metadata" in package_db else []

    return package_db["packages"]


def get_metadata():
    """Get the metadata for this installation.

    Returns
    -------
    {str: any}
        A dictionary of the metadata.
    """
    # Get the metadata for the installation
    environment = my.conda.active_environment
    user_data_path = Path(user_data_dir("seamm-installer", appauthor=False))
    path = user_data_path / (environment + ".json")

    if path.exists():
        try:
            with path.open("r") as fd:
                metadata = json.load(fd, cls=JSONDecoder)
        except Exception as e:
            my.logger.error(f"Exception reading the metadata for {environment}: {e}")
            my.logger.error(f"   File path is {path}")
            raise RuntimeError(f"Error reading metadata from {path}")
    else:
        metadata = {
            "environment": environment,
            "development": "dev" in environment,
            "gui-only": False,
        }
        user_data_path.mkdir(parents=True, exist_ok=True)
        with path.open("w") as fd:
            json.dump(metadata, fd, cls=JSONEncoder)

    return metadata


def initialize():
    if my.conda is None:
        my.conda = Conda()
        my.logger.debug("Setup conda in __init__")
    if my.pip is None:
        my.pip = Pip()


def package_info(package, conda_only=False):
    """Return info on a package

    Parameters
    ----------
    package:
        The name of the package.

    Returns
    -------
    (str, str)
        The version and channel (pip or conda) for the current installation.
    """
    my.logger.info(f"Info on package '{package}'")

    # See if conda knows it is installed
    my.logger.debug("    Checking if installed by conda")
    data = my.conda.show(package)
    if data is None:
        version = None
        channel = None
        my.logger.debug("        No.")
    else:
        my.logger.debug(f"Conda:\n---------\n{pprint.pformat(data)}\n---------\n")
        version = data["version"]
        channel = data["channel"]
        my.logger.info(f"   version {version} installed by conda, channel {channel}")
        if "/conda-forge" in channel:
            channel = "conda-forge"

    if conda_only:
        return version, channel

    # See if pip knows it is installed
    if channel is None:
        my.logger.debug("    Checking if installed by pip")
        try:
            data = my.pip.show(package)
        except Exception as e:
            my.logger.debug("        No.", exc_info=e)
            pass
        else:
            my.logger.debug(f"Pip:\n---------\n{pprint.pformat(data)}\n---------\n")
            if "version" in data:
                version = data["version"]
                channel = "pypi"
                my.logger.info(f"   version {version} installed by pip from pypi")

    return version, channel


def run_plugin_installer(package, *args, verbose=True):
    """Run the plug-in installer with given arguments.

    Parameters
    ----------
    package
        The package name for the plug-in. Usually xxxx-step.
    args
        Command-line arguments for the plugin installer.

    Returns
    -------
    xxxx
        The result structure from subprocess.run, or None if there is no
        installer.
    """
    my.logger.info(f"run_plugin_installer {package} {args}")
    if package == "seamm":
        return None

    installer = shutil.which(f"{package}-installer")
    if installer is None:
        my.logger.info("    no local installer, returning None")
        return None
    else:
        if verbose:
            print(f"   Running the plug-in specific installer for {package}.")
        result = subprocess.run([installer, *args], capture_output=True, text=True)
        my.logger.info(f"    ran the local installer: {result}")
        return result


def set_metadata(metadata):
    """Set the metadata for this installation.

    Parameters
    ----------
    {str: any}
        A dictionary of the metadata.
    """
    # Find the metadata for the installation
    environment = my.conda.active_environment
    user_data_path = Path(user_data_dir("seamm-installer", appauthor=False))
    path = user_data_path / (environment + ".json")

    user_data_path.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fd:
        json.dump(metadata, fd, cls=JSONEncoder)
