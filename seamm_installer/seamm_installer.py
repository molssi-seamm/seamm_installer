# -*- coding: utf-8 -*-

"""Non-graphical part of the SEAMM Installer
"""

import json
import logging
from pathlib import Path
import pkg_resources
import shlex
import shutil
import subprocess
import sys
import textwrap
from typing import Iterable, Mapping

from tabulate import tabulate

from .conda import Conda
from .pip import Pip
import seamm_installer

logger = logging.getLogger(__name__)

core_packages = (
    "seamm",
    "seamm-jobserver",
    "seamm-util",
    "seamm-widgets",
    "seamm-ff-util",
    "molsystem",
    "reference-handler",
)
exclude_plug_ins = ("seamm-cookiecutter", "cassandra-step", "solvate-step")
no_installer = ("seamm", "seamm-installer")


class SEAMMInstaller(object):
    """
    The non-graphical part of a SEAMM Installer.

    Attributes
    ----------

    """

    def __init__(self, logger=logger, seamm="seamm"):
        """The installer/updater for SEAMM.

        Parameters
        ----------
        logger : logging.Logger
            The logger for debug and other output.
        """
        logger.debug("Creating SEAMM Installer {}".format(self))

        self.logger = logger
        self.options = None
        self._seamm_environment = seamm
        self._conda = None
        self._pip = None

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
        self._seamm_environment = value

    def check(self, *modules, yes=False):
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
        self.conda.activate(self.seamm_environment)

        packages = self.find_packages(progress=False)
        print("")

        cmd = ["check"]
        if yes:
            cmd.append("--yes")

        if "all" in modules or "core" in modules:
            print("")
            print("Checking the core packages of SEAMM:")
            for package in core_packages:
                # If the package has an installer, run it.
                print(f"   Checking the installation for {package}")
                self.run_plugin_installer(package, *cmd)

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
                self.run_plugin_installer(package, *cmd)

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in ("core", "plug-ins", "plugins", "all"):
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
                    self.run_plugin_installer(package, *cmd)

    def check_installer(self, yes: bool = False) -> None:
        """Check and optionally install or update the installer.

        Parameters
        ----------
        yes:
            Whether to install or update without asking.
        """

        # Show the installer itself...need to be careful which installer!
        package = "seamm-installer"

        # See if conda knows it is installed
        try:
            installed = pkg_resources.parse_version(
                self.conda.list(query=package)["version"]
            )
        except Exception:
            installed = None
            installed_source = None
        else:
            installed_source = "conda"

        # Get a list of conda versions available
        conda_packages = self.conda.search(query=package)

        # See if pip knows it is installed
        try:
            version = pkg_resources.parse_version(self.pip.show(package)["version"])
        except Exception:
            pass
        else:
            if installed is None or installed < version:
                installed = version
                installed_source = "pip"

        # Get a list of pip version available
        pip_packages = self.pip.search(query=package, exact=True, progress=False)

        available = None
        source = None
        if package in conda_packages:
            available = pkg_resources.parse_version(
                conda_packages[package][-1]["version"]
            )
            source = "conda"
        if package in pip_packages:
            version = pkg_resources.parse_version(pip_packages[package]["version"])
            if available is None or version > available:
                available = version
                source = "pip"

        if installed is None:
            if available is None:
                print(
                    f"The SEAMM installer '{package}' is neither installed nor "
                    "available! This seems imnpossible!"
                )
            else:
                if yes:
                    if source == "pip":
                        self.pip.install(package)
                    else:
                        self.conda.install(package)
                    print(
                        f"The SEAMM installer '{package}' was not installed so "
                        f"installed version {available} using {source}."
                    )
                else:
                    print(
                        f"The SEAMM installer '{package}' is not installed "
                        f"but version {available} is available using {source}."
                    )
        elif available > installed:
            if yes:
                if installed_source == "pip":
                    self.pip.uninstall(package)
                else:
                    self.conda.uninstall(package)
                if source == "pip":
                    self.pip.install(package)
                else:
                    self.conda.install(package)
                print(
                    f"The SEAMM installer '{package}' version {version} was "
                    f"updated to version {available} using {source}."
                )
            else:
                print(
                    f"The SEAMM installer '{package}' version {version} is "
                    f"installed but a newer version {available} is available "
                    f"using {source}."
                )
        else:
            print(
                f"The SEAMM installer '{package}', version {version} " "is up-to-date."
            )

    def find_packages(self, progress: bool = False) -> Mapping[str, str]:
        """Find the Python packages in SEAMM.

        Parameters
        ----------
        Returns
        -------
        dict(str, str)
            A dictionary with information about the packages.
        """
        # Use pip to find possible packages.
        packages = self.pip.search(query="SEAMM", progress=False)

        # Remove this installer package
        if "seamm-installer" in packages:
            del packages["seamm-installer"]

        # Need to add molsystem and reference-handler by hand
        for package in ("molsystem", "reference-handler"):
            tmp = self.pip.search(query=package, exact=True, progress=False)
            logger.debug(
                f"Query for package {package}\n"
                f"{json.dumps(tmp, indent=4, sort_keys=True)}\n"
            )
            if package in tmp:
                packages[package] = tmp[package]
        return packages

    def install(self, *modules, **kwargs):
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
            logger.debug(f"data directory: {path}")
            self.conda.create_environment(
                path / "seamm.yml", name=self.seamm_environment
            )
            print("")
            print(f"Installed the {self.seamm_environment} Conda environment " "with:")
            self.conda.activate(self.seamm_environment)
            packages = self.pip.list()
            for package in core_packages:
                if package in packages:
                    print(f"   {package} {packages[package]}")
                else:
                    print(f"   Warning: {package} was not installed!")
            print("")
            packages = self.find_packages(progress=False)
            print("")
        else:
            self.conda.activate(self.seamm_environment)
            packages = self.find_packages(progress=False)
            print("")
            if "all" in modules or "core" in modules:
                print("")
                print("Installing the core packages of SEAMM:")
                to_install = []
                for package in core_packages:
                    try:
                        version = self.pip.show(package)["version"]
                    except Exception:
                        if package in packages:
                            to_install.append(package)
                    else:
                        if package in packages:
                            available = packages[package]["version"]
                            v_installed = pkg_resources.parse_version(version)
                            v_available = pkg_resources.parse_version(available)
                            if v_installed < v_available:
                                to_install.append(package)

                for package in sorted(to_install):
                    print(f"   Installing {package} " f"{packages[package]['version']}")
                    self.pip.install(package)

                    # See if the package has an installer
                    self.run_plugin_installer(package, "install")

        if "all" in modules or "plug-ins" in modules or "plugins" in modules:
            print("")
            print("Installing all of the plug-ins for SEAMM:")
            for package in sorted(packages.keys()):
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                install = "no"
                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    install = "full"
                else:
                    available = packages[package]["version"]
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        to_install.append(package)
                    else:
                        # See if the package has an installer
                        result = self.run_plugin_installer(package, "check", "--yes")
                        if result is not None:
                            if result.returncode == 0:
                                if "need to install" in result.stdout:
                                    install = "package installer"

                if install == "full":
                    print(f"   Installing {package} " f"{packages[package]['version']}")
                    self.pip.install(package)
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
            if module not in ("core", "plug-ins", "plugins", "all"):
                explicit.append(module)

        if len(explicit) > 0:
            print("")
            print("Installing the specified modules in SEAMM:")

            for package in explicit:
                if package not in packages:
                    print(f"Package '{package}' is not available for " "installation.")
                    continue

                install = "no"
                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    install = "full"
                else:
                    # If the package has an installer, run it.
                    print(f"   Checking the installation for {package}.")
                    result = self.run_plugin_installer(package, "show")
                    if result is not None:
                        if result.returncode == 0:
                            if (
                                "need to install" in result.stdout
                                or "not configured" in result.stdout
                            ):
                                install = "package installer"
                        else:
                            print(
                                "Encountered an error checking the "
                                f"installation for {package}: "
                                f"{result.returncode}"
                            )
                            print(f"\nstdout:\n{result.stdout}")
                            print(f"\nstderr:\n{result.stderr}")
                    available = packages[package]["version"]
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        print(f"{package} is installed but should be updated.")
                    elif install == "no":
                        print(f"{package} is already installed.")

                if install == "full":
                    print(f"Installing {package}")
                    self.pip.install(package)
                    self.run_plugin_installer(package, "install")
                elif install == "package installer":
                    print(f"Installing local part of {package}")
                    self.run_plugin_installer(package, "install")

    def run(self):
        """Run the installer/updater"""
        logger.debug("Entering run method of the SEAMM installer")

        # Process the conda environment
        self._handle_conda()
        self.conda.activate(self.seamm_environment)

        # Use pip to find possible packages.
        packages = self.pip.search(query="SEAMM")

        # Need to add molsystem and reference-handler by hand
        for package in ("molsystem", "reference-handler"):
            tmp = self.pip.search(query=package, exact=True)
            logger.debug(
                f"Query for package {package}\n"
                f"{json.dumps(tmp, indent=4, sort_keys=True)}\n"
            )
            if package in tmp:
                packages[package] = tmp[package]

        # And see what the user wants to do with them
        self._handle_core(packages)
        self._handle_plugins(packages)

        print("All done.")

    def run_plugin_installer(
        self, package: str, *args: Iterable[str]
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
        installer = shutil.which(f"{package}-installer")
        if installer is None:
            self.logger.info("    no local installer, returning None")
            return None
        else:
            result = subprocess.run([installer, *args], capture_output=True, text=True)
            self.logger.info(f"    ran the local installer: {result}")
            return result

    def show(self, *modules, **kwargs):
        """Show the current status of the installation.

        Parameters
        ----------
        modules : [str]
            The modules to show, or 'all', 'core' or 'plug-ins'.
        """
        logger.debug("Entering run method of the SEAMM installer")
        logger.debug(f"    modules = {modules}")

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
        self.conda.activate(self.seamm_environment)

        packages = self.find_packages(progress=False)
        print("")

        # Show the core SEAMM modules if requested
        if "all" in modules or "core" in modules:
            print("")
            print("Showing the core packages of SEAMM:")
            data = []
            line_no = 1
            am_current = True
            count = 0
            for package in core_packages:
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
                        v_installed = pkg_resources.parse_version(version)
                        v_available = pkg_resources.parse_version(available)
                        if v_installed < v_available:
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
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        am_current = False
                        state[package] = "not up-to-date"
                    else:
                        state[package] = "up-to-date"

                    result = self.run_plugin_installer(package, "show")
                    if result is not None:
                        if result.returncode == 0:
                            print(result.stdout)
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
            if module not in ("core", "plug-ins", "plugins", "all"):
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
                        v_installed = pkg_resources.parse_version(version)
                        v_available = pkg_resources.parse_version(available)
                        if v_installed < v_available:
                            am_current = False
                            state[package] = "not up-to-date"
                        else:
                            state[package] = "up-to-date"

                        # See if the package has an installer
                        result = self.run_plugin_installer(package, "show")
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

    def uninstall(self, *modules, **kwargs):
        if "all" in modules or "core" in modules:
            print("")
            print("Core packages of SEAMM:")
        if "all" in modules or "plug-ins" in modules or "plugins" in modules:
            print("")
            print("Plug-ins for SEAMM:")

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in ("core", "plug-ins", "plugins", "all"):
                explicit.append(module)

        if len(explicit) > 0:
            print("")
            print("Uninstalling the specified modules in SEAMM:")

    def update(self, *modules, **kwargs):
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
        self.conda.activate(self.seamm_environment)

        packages = self.find_packages(progress=False)
        print("")

        if "all" in modules or "core" in modules:
            print("")
            print("Updating the core packages of SEAMM:")
            for package in core_packages:
                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    pass
            else:
                if package in packages:
                    available = packages[package]["version"]
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        print(f"   Updating {package}")
                        self.pip.update(package)

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

                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    pass
                else:
                    available = packages[package]["version"]
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        print(
                            f"   Updating {package} from {v_installed} to "
                            f"{v_available}."
                        )
                        self.pip.update(package)

                        # See if the package has an installer
                        self.run_plugin_installer(package, "update")
                        print("    Done.")

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in ("core", "plug-ins", "plugins", "all"):
                explicit.append(module)

        if len(explicit) > 0:
            print("")
            print("Updating the specified modules in SEAMM:")

            for package in explicit:
                if package not in packages:
                    print(f"Package '{package}' is not available for " "upgrading.")
                    continue

                try:
                    version = self.pip.show(package)["version"]
                except Exception:
                    pass
                else:
                    available = packages[package]["version"]
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        print(
                            f"   Updating {package} from {v_installed} to "
                            f"{v_available}."
                        )
                        self.pip.update(package)

                        # See if the package has an installer
                        self.run_plugin_installer(package, "update")
                        print("    Done.")

    def _execute(self, command, poll_interval=2):
        """Execute the command as a subprocess.

        Parameters
        ----------
        command : str
            The command, with any arguments, to execute.
        poll_interval : int
            Time interval in seconds for checking for output.
        """
        logger.info(f"running '{command}'")
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
            logger.debug("    checking if finished")
            result = process.poll()
            if result is not None:
                logger.info(f"    finished! result = {result}")
                break
            try:
                logger.debug("    calling communicate")
                output, errors = process.communicate(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                logger.debug("    timed out")
                print(".", end="")
                n += 1
                if n >= 50:
                    print("")
                    n = 0
                sys.stdout.flush()
            else:
                if output != "":
                    stdout += output
                    logger.debug(output)
                if errors != "":
                    stderr += errors
                    logger.debug(f"stderr: '{errors}'")

        return result, stdout, stderr
