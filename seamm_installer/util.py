# -*- coding: utf-8 -*-

"""Utility methods for the SEAMM installer."""

from datetime import datetime
import json
from pathlib import Path
import pkg_resources
import pprint
import shutil
import subprocess

from platformdirs import user_data_dir
import requests

from .conda import Conda
from .metadata import core_packages, molssi_plug_ins, excluded_plug_ins
from . import my
from .pip import Pip


class JSONEncoder(json.JSONEncoder):
    """Class for handling the package versions in JSON."""

    def default(self, obj):
        if isinstance(obj, pkg_resources.extern.packaging.version.Version):
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
                return pkg_resources.parse_version(d["data"])
            else:
                # Oops... better put this back together.
                d["__type__"] = type
        return d


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
    if True:
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

        return package_db["packages"]

    user_data_path = Path(user_data_dir("seamm-installer", appauthor=False))
    package_db_path = user_data_path / "downloads.json"
    if package_db_path.exists():
        try:
            with package_db_path.open("r") as fd:
                package_db = json.load(fd, cls=JSONDecoder)
        except Exception as e:
            my.logger.warning(f"Exception reading the package cache: {e}")
            age = cache_valid
        else:
            db_date = datetime.fromisoformat(package_db["date"])
            age = datetime.now() - db_date
            packages = package_db["packages"]
    else:
        user_data_path.mkdir(parents=True, exist_ok=True)
        age = None

    if not (update_cache or age is None) and age.days < cache_valid:
        print(f"Using the package database which is {age.days} days old.")
        print(
            "    run 'seamm-installer refresh-cache' if you think packages have been "
            "added or updated recently."
        )

        # If the installer has been updated, the list of excluded packages may have
        # changed. So check.
        for package in excluded_plug_ins:
            if package in packages:
                del packages[package]

        # Convert conda-forge url in channel to 'conda-forge'
        for data in packages.values():
            if "/conda-forge" in data["channel"]:
                data["channel"] = "conda-forge"

        return packages

    # Update the package list and database!
    print("Finding all the packages that make up SEAMM. This may take several minutes.")
    # Use pip to find possible packages.
    packages = my.pip.search(
        query="SEAMM", progress=progress, newline=False, update=update
    )
    for package in excluded_plug_ins:
        if package in packages:
            del packages[package]

    # Need to add molsystem and reference-handler by hand
    for package in core_packages:
        if package not in packages:
            tmp = my.pip.search(
                query=package, exact=True, progress=True, newline=False, update=update
            )
            my.logger.debug(f"Query for package {package}\n{pprint.pformat(tmp)}\n")
            if package in tmp:
                packages[package] = tmp[package]

    # Set the type
    for package in packages:
        if package in core_packages:
            packages[package]["type"] = "Core package"
        elif package in molssi_plug_ins:
            packages[package]["type"] = "MolSSI plug-in"
        else:
            packages[package]["type"] = "3rd-party plug-in"

    # Check the versions on conda, and prefer those...
    my.logger.info("Find packages: checking for conda versions")
    for package, data in packages.items():
        my.logger.info(f"    {package}")
        conda_packages = my.conda.search(
            package, progress=True, newline=False, update=update
        )

        if conda_packages is None:
            continue

        tmp = conda_packages[package]
        if tmp["version"] >= data["version"]:
            data["version"] = tmp["version"]
            data["channel"] = tmp["channel"]
            if "/conda-forge" in data["channel"]:
                data["channel"] = "conda-forge"
    if progress:
        if update is None:
            print("", flush=True)
        else:
            update()

    # Save the package database for future use
    package_db = {
        "date": datetime.now().isoformat(),
        "packages": packages,
    }
    # pprint.pprint(package_db)
    with package_db_path.open("w") as fd:
        json.dump(package_db, fd, cls=JSONEncoder, indent=4, sort_keys=True)
    print(f"Wrote the package database to {str(package_db_path)}.")

    # Convert conda-forge url in channel to 'conda-forge'
    for data in packages.values():
        if "/conda-forge" in data["channel"]:
            data["channel"] = "conda-forge"

    return packages


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
