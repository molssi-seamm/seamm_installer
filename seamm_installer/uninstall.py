# -*- coding: utf-8 -*-

"""Uninstall requested components of SEAMM."""
from datetime import datetime

from . import my
from .util import find_packages, get_metadata, run_plugin_installer


def setup(parser):
    """Define the command-line interface for removing SEAMM components.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The main parser for the application.
    """
    subparser = parser.add_parser("uninstall")
    subparser.set_defaults(func=uninstall)

    subparser.add_argument(
        "--all",
        action="store_true",
        help="Fully uninstall the SEAMM installation",
    )
    subparser.add_argument(
        "--third-party",
        action="store_true",
        help="Uninstall all packages from 3rd parties",
    )
    subparser.add_argument(
        "--gui-only",
        action="store_true",
        help="Uninstall only the GUI part of packages, leaving the background part.",
    )
    subparser.add_argument(
        "modules",
        nargs="*",
        default=None,
        help="Specific modules and plug-ins to uninstall.",
    )


def uninstall():
    """Uninstall the requested SEAMM components and plug-ins.

    Parameters
    ----------
    """

    if my.options.all:
        # First uninstall the conda environment
        environment = my.conda.active_environment
        print(f"Removing the conda environment {environment}")
        # my.conda.uninstall(all=True)

        uninstall_packages("all", gui_only=my.options.gui_only)
    else:
        uninstall_packages(my.options.modules, gui_only=my.options.gui_only)


def uninstall_packages(to_uninstall, gui_only=False):
    """Uninstall SEAMM components and plug-ins."""
    metadata = get_metadata()

    # Find all the packages
    packages = find_packages(progress=True)

    # Get the info about the installed packages
    info = my.conda.list(environment=my.environment)

    if to_uninstall == "all":
        to_uninstall = [*packages.keys()]

    # First uninstall any plug-in installation
    if not metadata["gui-only"] and not gui_only:
        print(
            "Checking for plug-ins that have their own installations, and "
            "uninstalling them."
        )
    conda_packages = []
    pypi_packages = []
    for package in to_uninstall:
        if package in info:
            if info[package]["channel"] == "pypi":
                pypi_packages.append(package)
            else:
                conda_packages.append(package)
            # See if the package has an installer
            if not metadata["gui-only"] and not gui_only:
                run_plugin_installer(package, "uninstall")

    # Now the pip packages, if any
    if len(pypi_packages) > 0:
        tmp = ", ".join(pypi_packages)
        print(f"Uninstalling PyPi packages {tmp}")
        my.pip.uninstall(pypi_packages)

    if len(conda_packages) > 0:
        tmp = ", ".join(conda_packages)
        print(f"Uninstalling Conda packages {tmp}")
        my.conda.uninstall(conda_packages)

    directory = my.root / "environments"
    directory.mkdir(exist_ok=True)
    tstamp = datetime.now().isoformat(timespec="seconds")

    # Write the export file
    path = directory / f"{tstamp}_environment.yml"
    my.conda.export_environment(my.environment, path=path)

    # And the explicit file for "conda create --file"
    path = directory / f"{tstamp}_environment.txt"
    path.write_text(my.conda.list(my.environment, explicit=True))
