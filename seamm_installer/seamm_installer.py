# -*- coding: utf-8 -*-

"""Non-graphical part of the SEAMM Installer
"""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import pkg_resources
import pprint
import shlex
import shutil
import subprocess
import sys
import textwrap
from typing import Iterable, Tuple

from platformdirs import user_data_dir
from tabulate import tabulate

from .conda import Conda
from .pip import Pip
import seamm_installer

logger = logging.getLogger(__name__)

core_packages = (
    "seamm",
    "seamm-util",
    "seamm-widgets",
    "seamm-ff-util",
    "molsystem",
    "reference-handler",
    "seamm-datastore",
    "seamm-jobserver",
    "seamm-installer",
)
exclude_plug_ins = (
    "chemical-formula",
    "seamm-dashboard",
    "seamm-cookiecutter",
    "cassandra-step",
    "solvate-step",
)
development_packages = (
    "black",
    "codecov",
    "flake8",
    "pytest",
    "pytest-cov",
    "pygments",
    "sphinx",
    "twine",
    "watchdog",
)
development_packages_pip = (
    "build",
    "rinohtype",
    "sphinx-rtd-theme",
    "pystemmer",
)
no_installer = ("seamm", "seamm-installer")
package_groups = (
    "core",
    "plug-ins",
    "plugins",
    "all",
    "seamm-installer",
    "development",
)


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


class SEAMMInstaller(object):
    """
    The non-graphical part of a SEAMM Installer.

    Attributes
    ----------

    """

    def __init__(self, logger=logger, environment="", ini_file="~/SEAMM/seamm.ini"):
        """The installer/updater for SEAMM.

        Parameters
        ----------
        logger : logging.Logger
            The logger for debug and other output.
        """
        logger.debug("Creating SEAMM Installer {}".format(self))

        self.logger = logger
        self.options = None
        self._configuration = seamm_installer.Configuration()
        self._conda = None
        self._pip = None

        # Set the environment at the end so can use conda
        self.seamm_environment = environment

        print(f"The conda environment is {self.seamm_environment}")

        self.check_configuration_file(ini_file)

    @property
    def version(self):
        """The semantic version of this module."""
        return seamm_installer.__version__

    @property
    def git_revision(self):
        """The git version of this module."""
        return seamm_installer.__git_revision__

    @property
    def conda(self):
        """The Conda object."""
        if self._conda is None:
            self._conda = Conda()
        return self._conda

    @property
    def configuration(self):
        """The Configuration object for working with the ini file."""
        return self._configuration

    @property
    def pip(self):
        """The Pip object."""
        if self._pip is None:
            self._pip = Pip()
        return self._pip

    @property
    def seamm_environment(self):
        """The Conda environment for SEAMM."""
        return self._seamm_environment

    @seamm_environment.setter
    def seamm_environment(self, value):
        if value is None or value == "":
            self._seamm_environment = self.conda.active_environment
        else:
            self._seamm_environment = value

        # Make the desired environment the active one if it exists
        if self.conda.active_environment != self.seamm_environment:
            if self.conda.exists(self._seamm_environment):
                self.conda.activate(self._seamm_environment)
            else:
                print(
                    f"The conda environment '{self._seamm_environment}' does not "
                    "currently exist."
                )

    def check(self, *modules, yes=False, update_cache=False):
        """Check the requested modules.

        Parameters
        ----------
        *modules: [str]
            A list of modules to install. May be 'all', 'core', or 'plug-ins'
            to request either all modules, or just the core or plug-ins be
            installed.
        yes: bool
            Answer 'yes' to all prompts.
        **kwargs: dict(str, str)
            Other optional keyword arguments.
        """
        # See if Conda is installed
        if not self.conda.is_installed:
            print("Conda is not installed, so none of SEAMM is.")
            return

        # Activate the seamm environment, if it exists.
        if not self.conda.exists(self.seamm_environment):
            print(f"The '{self.seamm_environment}' Conda environment is not installed.")
            text = "\n    ".join(self.conda.environments)
            self.logger.info(f"Conda environments:\n    {text}")
            return
        if self.conda.active_environment != self.seamm_environment:
            self.conda.activate(self.seamm_environment)

        packages = self.find_packages(progress=True, update_cache=update_cache)
        # print("")

        cmd = ["check"]
        if yes:
            cmd.append("--yes")

        if "all" in modules or "core" in modules:
            print("")
            print("Checking the core packages of SEAMM:")
            for package in core_packages:
                if package == "seamm-installer":
                    continue
                # If the package has an installer, run it.
                print(f"   Checking the installation for {package}")
                self.run_plugin_installer(package, *cmd, verbose=False)

        if "all" in modules or "plug-ins" in modules or "plugins" in modules:
            print("")
            print("Checking the plug-ins for SEAMM:")
            for package in packages:
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                # If the package has an installer, run it.
                print(f"   Checking the installation for {package}.")
                self.run_plugin_installer(package, *cmd, verbose=False)

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in package_groups:
                explicit.append(module)

        if len(explicit) > 0:
            print("")
            print("Checking the specified modules in SEAMM:")

            for package in explicit:
                if package not in packages:
                    print(f"    {package} is not installed.")
                else:
                    # If the package has an installer, run it.
                    print(f"   Checking the installation for {package}.")
                    self.run_plugin_installer(package, *cmd, verbose=False)

    def check_configuration_file(self, ini_file):
        """Ensure that the configuration file exists.

        If it does not, it will be created and a template written to it. The
        template contains a prolog with a description of the file followed by
        [DEFAULT] and [SEAMM] sections, which ensures that they are
        present and at the top of the file.
        """
        path = Path(ini_file).expanduser().resolve()
        if not path.exists():
            data_dir = Path(pkg_resources.resource_filename(__name__, "data/"))
            self.logger.debug(f"data directory: {data_dir}")
            template = data_dir / "seamm.ini"
            text = template.read_text()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

        # And read it in
        self.configuration.path = path

        # Check the secret key for the dashboard
        data = self.configuration.get_values("SEAMM")
        if "secret-key" not in data or data["secret-key"] == "":
            secret = os.urandom(32)
            self.configuration.set_value("SEAMM", "secret-key", secret)
            self.configuration.save()

    def check_installer(self, yes: bool = False) -> None:
        """Check and optionally install or update the installer.

        Parameters
        ----------
        yes:
            Whether to install or update without asking.
        """

        self.logger.info("Checking if the installer is up-to-date.")

        # Show the installer itself...need to be careful which installer!
        package = "seamm-installer"

        installed_version, channel = self.package_info(package)

        # Get a list of conda versions available
        conda_packages = self.conda.search(query=package)

        # Get a list of pip version available
        pip_packages = self.pip.search(query=package, exact=True, progress=False)

        available = None
        source = None
        if package in conda_packages:
            available = conda_packages[package]["version"]
            source = "conda"
        if package in pip_packages:
            version = pip_packages[package]["version"]
            if available is None or version > available:
                available = version
                source = "pip"

        if installed_version is None:
            if available is None:
                print(
                    f"The SEAMM installer '{package}' is neither installed nor "
                    "available! This seems impossible!"
                )
            else:
                if yes:
                    print(
                        f"The SEAMM installer '{package}' is not installed so "
                        f"will install version {available} using {source}."
                    )
                    if channel == "pypi":
                        self.pip.install(package)
                    else:
                        self.conda.install(package)
                else:
                    print(
                        f"The SEAMM installer '{package}' is not installed "
                        f"but version {available} is available using {source}."
                    )
        elif available > installed_version:
            if yes and self.conda.active_environment != self.seamm_environment:
                print(
                    f"The SEAMM installer '{package}' version {installed_version} will "
                    f"be updated to version {available} using {source}."
                )
                if channel == "pypi":
                    self.pip.uninstall(package)
                else:
                    self.conda.uninstall(package)
                if source == "pip":
                    self.pip.install(package)
                else:
                    self.conda.install(package)
            else:
                print(
                    f"The SEAMM installer '{package}' version {installed_version} is "
                    f"installed but a newer version {available} is available "
                    f"using {source}.\n"
                    "Update it with this command:\n"
                )
                if source == "pip":
                    print("    pip update seamm-installer")
                else:
                    print("    conda update -c conda-forge seamm-installer")
        else:
            print(
                f"The SEAMM installer '{package}', version {installed_version} is "
                "up-to-date."
            )

    def find_packages(self, progress: bool = True, update_cache=False, cache_valid=7):
        """Find the Python packages in SEAMM.

        Parameters
        ----------
        progress : bool = True
            Whether to print out dots to show progress.
        update_cache : bool = False
            Update the cache (package db) no matter what.
        cache_valid : int = 7
            How many days before updating the cache. Defaults to a week.

        Returns
        -------
        dict(str, str)
            A dictionary with information about the packages.
        """
        user_data_path = Path(user_data_dir("seamm-installer", appauthor=False))
        package_db_path = user_data_path / "downloads.json"
        if package_db_path.exists():
            try:
                with package_db_path.open("r") as fd:
                    package_db = json.load(fd, cls=JSONDecoder)
            except Exception as e:
                self.logger.warning(f"Exception reading the package cache: {e}")
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
            print("    Add the '--update-cache' flag if you want to update the cache.")

            return packages

        # Update the package list and database!
        print(
            "Finding all the packages that make up SEAMM. This may take a minute or "
            "two."
        )
        # Use pip to find possible packages.
        packages = self.pip.search(query="SEAMM", progress=progress, newline=False)

        # Need to add molsystem and reference-handler by hand
        for package in ("molsystem", "reference-handler", "seaam-datastore"):
            if package not in packages:
                tmp = self.pip.search(
                    query=package, exact=True, progress=True, newline=False
                )
                self.logger.debug(
                    f"Query for package {package}\n{pprint.pformat(tmp)}\n"
                )
                if package in tmp:
                    packages[package] = tmp[package]

        # Check the versions on conda, and prefer those...
        self.logger.info("Find packages: checking for conda versions")
        for package, data in packages.items():
            self.logger.info(f"    {package}")
            conda_packages = self.conda.search(package, progress=True, newline=False)

            if conda_packages is None:
                continue

            tmp = conda_packages[package]
            if tmp["version"] >= data["version"]:
                data["version"] = tmp["version"]
                data["channel"] = tmp["channel"]

        if progress:
            print("", flush=True)

        # Save the package database for future use
        package_db = {
            "date": datetime.now().isoformat(),
            "packages": packages,
        }
        # pprint.pprint(package_db)
        with package_db_path.open("w") as fd:
            json.dump(package_db, fd, cls=JSONEncoder)
        print(f"Wrote the package database to {str(package_db_path)}.")

        return packages

    def install(self, *modules, update_cache=False, **kwargs):
        """Install the requested modules.

        Parameters
        ----------
        *modules: [str]
            A list of modules to install. May be 'all', 'core', or 'plug-ins'
            to request either all modules, or just the core or plug-ins be
            installed.
        **kwargs: dict(str, str)
            Other optional keyword arguments.
        """
        # See if Conda is installed
        if not self.conda.is_installed:
            print("Conda is not installed, so none of SEAMM is.")
            return

        # Activate the seamm environment, if it exists.
        if not self.conda.exists(self.seamm_environment):
            print(
                f"Installing the '{self.seamm_environment}' Conda environment."
                " This will take a minute or two."
            )
            # Get the path to seamm.yml
            path = Path(pkg_resources.resource_filename(__name__, "data/"))
            self.logger.debug(f"data directory: {path}")
            self.conda.create_environment(
                path / "seamm.yml", name=self.seamm_environment
            )
            print("")
            print(f"Installed the {self.seamm_environment} Conda environment " "with:")
            self.conda.activate(self.seamm_environment)
            packages = self.pip.list()
            for package in core_packages:
                if package == "seamm-installer":
                    continue
                if package in packages:
                    print(f"   {package} {packages[package]}")
                else:
                    print(f"   Warning: {package} was not installed!")
            print("")
            packages = self.find_packages(progress=True, update_cache=update_cache)
            # print("")
        else:
            packages = self.find_packages(progress=True, update_cache=update_cache)
            if "all" in modules or "core" in modules:
                print("")
                print("Installing the core packages of SEAMM:")
                to_install = []
                for package in core_packages:
                    if package == "seamm-installer":
                        continue
                    installed_version, channel = self.package_info(package)

                    if installed_version is None:
                        if package in packages:
                            version = packages[package]["version"]
                            channel = packages[package]["channel"]
                            to_install.append((package, version, channel))

                for package, version, channel in to_install:
                    if channel == "pypi":
                        print(
                            f"   Installing {package} {packages[package]['version']} "
                            "using pip."
                        )
                        self.pip.install(package)
                    else:
                        print(
                            f"   Installing {package} {packages[package]['version']} "
                            f"from conda channel {channel}."
                        )
                        self.conda.install(package, environment=self.seamm_environment)

                    # See if the package has an installer
                    self.run_plugin_installer(package, "install")

        if "development" in modules:
            print("")
            print("Installing the standard development tools:")
            for package in development_packages:
                installed_version, channel = self.package_info(package)
                if installed_version is None:
                    self.conda.install(package)
                    installed_version, channel = self.package_info(package)
                    print(f"   Installed {package} {installed_version} using conda.")
            for package in development_packages_pip:
                installed_version, channel = self.package_info(package)
                if installed_version is None:
                    self.pip.install(package)
                    installed_version, channel = self.package_info(package)
                    print(f"   Installed {package} {installed_version} using pip.")

        if "all" in modules or "plug-ins" in modules or "plugins" in modules:
            print("")
            print("Installing all of the plug-ins for SEAMM:")
            for package in sorted(packages.keys()):
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                install = "no"
                installed_version, channel = self.package_info(package)
                if installed_version is None:
                    install = "full"
                else:
                    available = packages[package]["version"]
                    if installed_version < available:
                        to_install.append(package)
                    else:
                        # See if the package has an installer
                        result = self.run_plugin_installer(
                            package, "check", "--yes", verbose=False
                        )
                        if result is not None:
                            if result.returncode == 0:
                                if "need to install" in result.stdout:
                                    install = "package installer"

                if install == "full":
                    channel = packages[package]["channel"]
                    if channel == "pypi":
                        print(
                            f"   Installing {package} {packages[package]['version']} "
                            "using pip"
                        )
                        self.pip.install(package)
                    else:
                        print(
                            f"   Installing {package} {packages[package]['version']} "
                            f"from conda channel {channel}"
                        )
                        self.conda.install(package)
                    # See if the package has an installer
                    self.run_plugin_installer(package, "install")
                elif install == "package installer":
                    print(
                        f"   {package} is installed, but its installer needs "
                        "to be run"
                    )
                    # See if the package has an installer
                    self.run_plugin_installer(package, "install")

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in package_groups:
                explicit.append(module)

        if len(explicit) > 0:
            print("")
            print("Installing the specified modules in SEAMM:")

            for package in explicit:
                if package not in packages:
                    print(f"Package '{package}' is not available for " "installation.")
                    continue

                install = "no"
                installed_version, channel = self.package_info(package)
                if installed_version is None:
                    install = "full"
                else:
                    # If the package has an installer, run it.
                    print(f"   Checking the installation for {package}.")
                    result = self.run_plugin_installer(package, "show", verbose=False)
                    if result is not None:
                        if result.returncode == 0:
                            if (
                                "need to install" in result.stdout
                                or "not configured" in result.stdout
                            ):
                                install = "package installer"
                        else:
                            self.logger.warning(
                                "Encountered an error checking the "
                                f"installation for {package}: "
                                f"{result.returncode}"
                            )
                            self.logger.warning(f"\nstdout:\n{result.stdout}")
                            self.logger.warning(f"\nstderr:\n{result.stderr}")
                    available = packages[package]["version"]
                    if installed_version < available:
                        print(f"{package} is installed but should be updated.")
                    elif install == "no":
                        print(f"{package} is already installed.")

                if install == "full":
                    channel = packages[package]["channel"]
                    if channel == "pypi":
                        print(
                            f"   Installing {package} {packages[package]['version']} "
                            "using pip"
                        )
                        self.pip.install(package)
                    else:
                        print(
                            f"   Installing {package} {packages[package]['version']} "
                            f"from conda channel {channel}"
                        )
                        self.conda.install(package)
                    self.logger.info(
                        "    Running the plug-in specific installer if it exists."
                    )
                    self.run_plugin_installer(package, "install")
                elif install == "package installer":
                    print(f"Installing local part of {package}")
                    self.run_plugin_installer(package, "install")

    def package_info(self, package: str, conda_only: bool = False) -> Tuple[str, str]:
        """Return info on a package

        Parameters
        ----------
        package:
            The name of the package.
        """

        self.logger.info(f"Info on package '{package}'")

        # See if conda knows it is installed
        self.logger.debug("    Checking if installed by conda")
        data = self.conda.list(query=package, fullname=True)
        if package not in data:
            version = None
            channel = None
            self.logger.debug("        No.")
        else:
            self.logger.debug(f"Conda:\n---------\n{pprint.pformat(data)}\n---------\n")
            version = data[package]["version"]
            channel = data[package]["channel"]
            self.logger.info(
                f"   version {version} installed by conda, channel {channel}"
            )

        if conda_only:
            return version, channel

        # See if pip knows it is installed
        if channel is None:
            self.logger.debug("    Checking if installed by pip")
            try:
                data = self.pip.show(package)
            except Exception as e:
                self.logger.debug("        No.", exc_info=e)
                pass
            else:
                self.logger.debug(
                    f"Pip:\n---------\n{pprint.pformat(data)}\n---------\n"
                )
                if "version" in data:
                    version = data["version"]
                    channel = "pypi"
                    self.logger.info(f"   version {version} installed by pip from pypi")

        return version, channel

    def run(self):
        """Run the installer/updater"""
        self.logger.debug("Entering run method of the SEAMM installer")

        # Process the conda environment
        self._handle_conda()
        if self.conda.active_environment != self.seamm_environment:
            self.conda.activate(self.seamm_environment)

        # Use pip to find possible packages.
        packages = self.pip.search(query="SEAMM")

        # Need to add molsystem and reference-handler by hand
        for package in ("molsystem", "reference-handler"):
            tmp = self.pip.search(query=package, exact=True)
            self.logger.debug(f"Query for package {package}\n{pprint.pformat(tmp)}\n")
            if package in tmp:
                packages[package] = tmp[package]

        # And see what the user wants to do with them
        self._handle_core(packages)
        self._handle_plugins(packages)

        print("All done.")

    def run_plugin_installer(
        self, package: str, *args: Iterable[str], verbose: bool = True
    ) -> subprocess.CompletedProcess:
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
        self.logger.info(f"run_plugin_installer {package} {args}")
        if package == "seamm":
            return None

        installer = shutil.which(f"{package}-installer")
        if installer is None:
            self.logger.info("    no local installer, returning None")
            return None
        else:
            if verbose:
                print(f"   Running the plug-in specific installer for {package}.")
            result = subprocess.run([installer, *args], capture_output=True, text=True)
            self.logger.info(f"    ran the local installer: {result}")
            return result

    def show(self, *modules, update_cache=False, **kwargs):
        """Show the current status of the installation.

        Parameters
        ----------
        modules : [str]
            The modules to show, or 'all', 'core' or 'plug-ins'.
        """
        self.logger.debug("Entering run method of the SEAMM installer")
        self.logger.debug(f"    modules = {modules}")

        # See if Conda is installed
        if not self.conda.is_installed:
            print("Conda is not installed, so none of SEAMM is.")
            return

        # Activate the seamm environment, if it exists.
        if not self.conda.exists(self.seamm_environment):
            print(f"The '{self.seamm_environment}' Conda environment is not installed.")
            text = "\n    ".join(self.conda.environments)
            self.logger.info(f"Conda environments:\n    {text}")
            return
        self.logger.info(f"Activating {self.seamm_environment} environment")
        if self.conda.active_environment != self.seamm_environment:
            self.conda.activate(self.seamm_environment)

        packages = self.find_packages(progress=True, update_cache=update_cache)
        # print("")

        # Show the core SEAMM modules if requested
        if "all" in modules or "core" in modules:
            print("")
            print("Showing the core packages of SEAMM:")
            data = []
            line_no = 1
            am_current = True
            count = 0
            for package in core_packages:
                if package == "seamm-installer":
                    continue
                count += 1
                if count > 50:
                    count = 0
                    print("\n.", end="", flush=True)
                else:
                    print(".", end="", flush=True)

                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    if package in packages:
                        available = packages[package]["version"]
                        description = packages[package]["description"]
                        data.append([line_no, package, "--", available, description])
                        am_current = False
                    else:
                        data.append([line_no, package, "--", "--", "not available"])
                else:
                    if package in packages:
                        available = packages[package]["version"]
                        description = packages[package]["description"]
                        data.append([line_no, package, version, available, description])
                        if version < available:
                            am_current = False
                    else:
                        data.append([line_no, package, version, "--", "not available"])
                line_no += 1

            headers = ["Number", "Package", "Installed", "Available", "Description"]
            print("")
            print(tabulate(data, headers, tablefmt="fancy_grid"))
            if am_current:
                print("The core packages are up-to-date.")
            print("")
        if "all" in modules or "plug-ins" in modules or "plugins" in modules:
            print("")
            print("Showing the plug-ins for SEAMM:")
            data = []
            am_current = True
            all_installed = True
            state = {}
            count = 0
            for package in packages:
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                if "description" in packages[package]:
                    description = packages[package]["description"].strip()
                    description = textwrap.fill(description, width=50)
                else:
                    description = "description unavailable"

                count += 1
                if count > 50:
                    count = 0
                    print("\n.", end="", flush=True)
                else:
                    print(".", end="", flush=True)

                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    available = packages[package]["version"]
                    data.append([package, "--", available, description])
                    all_installed = False
                    state[package] = "not installed"
                else:
                    available = packages[package]["version"]
                    if version < available:
                        am_current = False
                        state[package] = "not up-to-date"
                    else:
                        state[package] = "up-to-date"

                    result = self.run_plugin_installer(package, "show", verbose=False)
                    if result is not None:
                        if result.returncode == 0:
                            for line in result.stdout.splitlines():
                                description += f"\n{line}"
                        else:
                            description += (
                                f"\nThe installer for {package} "
                                f"returned code {result.returncode}"
                            )
                            for line in result.stderr.splitlines():
                                description += f"\n    {line}"
                    data.append([package, version, available, description])

            # Sort by the plug-in names
            data.sort(key=lambda x: x[0])

            # And number
            for i, line in enumerate(data, start=1):
                line.insert(0, i)

            headers = ["Number", "Plug-in", "Installed", "Available", "Description"]
            print("")
            print(tabulate(data, headers, tablefmt="fancy_grid"))
            if am_current:
                if all_installed:
                    print("The plug-ins are up-to-date.")
                else:
                    print(
                        "The installed plug-ins are up-to-date; however, not "
                        "all the plug-ins are installed"
                    )
                print("")
            else:
                if all_installed:
                    print("The plug-ins are not up-to-date.")
                else:
                    print(
                        "The plug-ins are not up-to-date and some are not " "installed."
                    )

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in package_groups:
                explicit.append(module)

        if len(explicit) > 0:
            print("")
            print("Showing the specified modules in SEAMM:")
            data = []
            am_current = True
            state = {}
            count = 0
            for package in explicit:
                count += 1
                if count > 50:
                    count = 0
                    print("\n.", end="", flush=True)
                else:
                    print(".", end="", flush=True)

                if package in packages and "description" in packages[package]:
                    description = packages[package]["description"].strip()
                    description = textwrap.fill(description, width=50)
                else:
                    description = "description unavailable"

                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    if package in packages:
                        available = packages[package]["version"]
                        data.append([package, "--", available, description])
                        am_current = False
                        state[package] = "not installed"
                    else:
                        data.append([package, "--", "--", "not available"])
                        state[package] = "not installed, not available"
                else:
                    if package in packages:
                        available = packages[package]["version"]
                        if version < available:
                            am_current = False
                            state[package] = "not up-to-date"
                        else:
                            state[package] = "up-to-date"

                        # See if the package has an installer
                        result = self.run_plugin_installer(
                            package, "show", verbose=False
                        )
                        if result is not None:
                            if result.returncode == 0:
                                for line in result.stdout.splitlines():
                                    description += f"\n{line}"
                            else:
                                description += (
                                    f"\nThe installer for {package} "
                                    f"returned code {result.returncode}"
                                )
                                for line in result.stderr.splitlines():
                                    description += f"\n    {line}"
                        data.append([package, version, available, description])
                    else:
                        data.append([package, version, "--", "not available"])
                        state[package] = "installed, not available"

            # Sort by the plug-in names
            data.sort(key=lambda x: x[0])

            # And number
            for i, line in enumerate(data, start=1):
                line.insert(0, i)

            headers = ["Number", "Plug-in", "Installed", "Available", "Description"]
            print("")
            print(tabulate(data, headers, tablefmt="fancy_grid"))
            if am_current:
                print("The plug-ins are up-to-date.")
            print("")

        # Development modules
        if "development" in modules:
            print("")
            print("Showing the standard development tools:")
            data = []
            line_no = 1
            am_current = True
            count = 0
            for package in (*development_packages, *development_packages_pip):
                count += 1
                if count > 50:
                    count = 0
                    print("\n.", end="", flush=True)
                else:
                    print(".", end="", flush=True)

                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    data.append([line_no, package, "--"])
                else:
                    data.append([line_no, package, version])
                line_no += 1

            headers = ["Number", "Package", "Installed"]
            print("")
            print(tabulate(data, headers, tablefmt="fancy_grid"))
            print("")

    def uninstall(self, *modules, update_cache=False, **kwargs):
        """Remove the requested modules.

        Parameters
        ----------
        *modules: [str]
            A list of modules to install. May be 'all', 'core', or 'plug-ins'
            to request either all modules, or just the core or plug-ins be
            installed.
        **kwargs: dict(str, str)
            Other optional keyword arguments.
        """

        if self.conda.active_environment != self.seamm_environment:
            self.conda.activate(self.seamm_environment)

        packages = None
        if "all" in modules or "core" in modules:
            print("")
            print("Core packages of SEAMM:")
            for package in core_packages:
                if package == "seamm-installer":
                    continue
                installed_version, channel = self.package_info(package)

                if installed_version is None:
                    continue

                print(f"   Uninstalling {package} {installed_version}")

                # See if the package has an installer
                self.run_plugin_installer(package, "uninstall")

                if channel == "pypi":
                    self.pip.uninstall(package)
                else:
                    self.conda.uninstall(package)

        if "all" in modules or "plug-ins" in modules or "plugins" in modules:
            print("")
            print("Plug-ins for SEAMM:")
            if packages is None:
                packages = self.find_packages(progress=True, update_cache=update_cache)
            for package in sorted(packages.keys()):
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                installed_version, channel = self.package_info(package)
                if installed_version is None:
                    continue

                print(f"   Uninstalling {package} {installed_version}")

                # See if the package has an installer
                self.run_plugin_installer(package, "uninstall")

                if channel == "pypi":
                    self.pip.uninstall(package)
                else:
                    self.conda.uninstall(package)

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in package_groups:
                explicit.append(module)

        if len(explicit) > 0:
            print("")
            print("Uninstalling the specified modules in SEAMM:")
            for package in explicit:
                installed_version, channel = self.package_info(package)
                if installed_version is None:
                    print(f"   {package} is not installed")
                    continue

                print(f"   Uninstalling {package} {installed_version}")

                # See if the package has an installer
                self.run_plugin_installer(package, "uninstall")

                if channel == "pypi":
                    self.pip.uninstall(package)
                else:
                    self.conda.uninstall(package)

        if "development" in modules:
            print("")
            print("Uninstalling the standard development tools:")
            for package in development_packages:
                installed_version, channel = self.package_info(package)
                if installed_version is not None:
                    print(f"   Uninstalling {package} {installed_version} using conda.")
                    self.conda.uninstall(package)
            for package in development_packages_pip:
                installed_version, channel = self.package_info(package)
                if installed_version is not None:
                    print(f"   Uninstalling {package} {installed_version} using pip.")
                    self.pip.uninstall(package)

    def update(self, *modules, update_cache=False, **kwargs):
        """Update the requested modules.

        Parameters
        ----------
        *modules: [str]
            A list of modules to install. May be 'all', 'core', or 'plug-ins'
            to request either all modules, or just the core or plug-ins be
            installed.
        **kwargs: dict(str, str)
            Other optional keyword arguments.
        """
        # See if Conda is installed
        if not self.conda.is_installed:
            print("Conda is not installed, so none of SEAMM is.")
            return

        # Activate the seamm environment, if it exists.
        if not self.conda.exists(self.seamm_environment):
            print(f"The '{self.seamm_environment}' Conda environment is not installed.")
            text = "\n    ".join(self.conda.environments)
            self.logger.info(f"Conda environments:\n    {text}")
            return
        if self.conda.active_environment != self.seamm_environment:
            self.conda.activate(self.seamm_environment)

        packages = self.find_packages(progress=True, update_cache=update_cache)
        print("")

        if "all" in modules or "core" in modules:
            print("")
            print("Updating the core packages of SEAMM:")
            for package in core_packages:
                if package == "seamm-installer":
                    continue
                installed_version, installed_channel = self.package_info(package)
                if installed_version is None:
                    continue

                if package in packages:
                    available = packages[package]["version"]
                    channel = packages[package]["channel"]
                    if installed_version < available:
                        print(f"   Updating {package}")
                        if channel == installed_channel:
                            if channel == "pypi":
                                self.pip.update(package)
                            else:
                                self.conda.update(package)
                        else:
                            if installed_channel == "pypi":
                                self.pip.uninstall(package)
                            else:
                                self.conda.uninstall(package)
                            if channel == "pypi":
                                self.pip.install(package)
                            else:
                                self.conda.install(package)

                        # See if the package has an installer
                        self.run_plugin_installer(package, "update")

        if "all" in modules or "plug-ins" in modules or "plugins" in modules:
            print("")
            print("Plug-ins for SEAMM:")
            for package in packages:
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                installed_version, installed_channel = self.package_info(package)
                if installed_version is None:
                    continue

                available = packages[package]["version"]
                channel = packages[package]["channel"]
                if installed_version < available:
                    print(
                        f"   Updating {package} from {installed_version} to "
                        f"{available}."
                    )
                    if channel == installed_channel:
                        if channel == "pypi":
                            self.pip.update(package)
                        else:
                            self.conda.update(package)
                    else:
                        if installed_channel == "pypi":
                            self.pip.uninstall(package)
                        else:
                            self.conda.uninstall(package)
                        if channel == "pypi":
                            self.pip.install(package)
                        else:
                            self.conda.install(package)

                    # See if the package has an installer
                    self.run_plugin_installer(package, "update")
                    print("    Done.")

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in package_groups:
                explicit.append(module)

        if len(explicit) > 0:
            print("")
            print("Updating the specified modules in SEAMM:")

            for package in explicit:
                if package not in packages:
                    print(f"Package '{package}' is not available for " "upgrading.")
                    continue

                installed_version, installed_channel = self.package_info(package)
                if installed_version is None:
                    continue

                available = packages[package]["version"]
                channel = packages[package]["channel"]
                if installed_version < available:
                    print(
                        f"   Updating {package} from {installed_version} to "
                        f"{available}."
                    )
                    if channel == installed_channel:
                        if channel == "pypi":
                            self.pip.update(package)
                        else:
                            self.conda.update(package)
                    else:
                        if installed_channel == "pypi":
                            self.pip.uninstall(package)
                        else:
                            self.conda.uninstall(package)
                        if channel == "pypi":
                            self.pip.install(package)
                        else:
                            self.conda.install(package)

                    # See if the package has an installer
                    self.run_plugin_installer(package, "update")
                    print("    Done.")

        if "development" in modules:
            print("")
            print("Updating the standard development tools:")
            for package in (*development_packages, *development_packages_pip):
                installed_version, channel = self.package_info(package)
                if installed_version is not None:
                    if channel == "pypi":
                        print(f"   Updating {package} {installed_version} using pip.")
                        self.pip.update(package)
                    else:
                        print(f"   Updating {package} {installed_version} using conda.")
                        self.conda.update(package)
                    new_version, channel = self.package_info(package)
                    if new_version != installed_version:
                        print(f"      --> {new_version}")

    def _execute(self, command, poll_interval=2):
        """Execute the command as a subprocess.

        Parameters
        ----------
        command : str
            The command, with any arguments, to execute.
        poll_interval : int
            Time interval in seconds for checking for output.
        """
        self.logger.info(f"running '{command}'")
        args = shlex.split(command)
        process = subprocess.Popen(
            args,
            bufsize=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        n = 0
        stdout = ""
        stderr = ""
        while True:
            self.logger.debug("    checking if finished")
            result = process.poll()
            if result is not None:
                self.logger.info(f"    finished! result = {result}")
                break
            try:
                self.logger.debug("    calling communicate")
                output, errors = process.communicate(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                self.logger.debug("    timed out")
                print(".", end="")
                n += 1
                if n >= 50:
                    print("")
                    n = 0
                sys.stdout.flush()
            else:
                if output != "":
                    stdout += output
                    self.logger.debug(output)
                if errors != "":
                    stderr += errors
                    self.logger.debug(f"stderr: '{errors}'")
        if n > 0:
            print("")

        return result, stdout, stderr
