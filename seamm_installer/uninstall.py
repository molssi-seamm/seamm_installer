# -*- coding: utf-8 -*-

"""Uninstall requested components of SEAMM."""
from . import my
from .util import find_packages, get_metadata, package_info, run_plugin_installer


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

        uninstall_packages("all")
    else:
        uninstall_packages(my.options.modules)


def uninstall_packages(to_uninstall):
    """Uninstall SEAMM components and plug-ins."""
    metadata = get_metadata()

    # Find all the packages
    packages = find_packages(progress=True)

    if to_uninstall == "all":
        for package in package_info:
            version, channel = package_info(package)
            ptype = packages[package]["type"]
            print(f"Uninstalling {ptype.lower()} {package}")
            if channel == "pypi":
                my.pip.uninstall(package)
            else:
                my.conda.uninstall(package)
            # See if the package has an installer
            if not metadata["gui-only"] and not my.options.gui_only:
                run_plugin_installer(package, "uninstall")
    else:
        for package in to_uninstall:
            version, channel = package_info(package)
            ptype = packages[package]["type"]
            print(f"Uninstalling {ptype.lower()} {package}")
            if channel == "pypi":
                my.pip.uninstall(package)
            else:
                my.conda.uninstall(package)
            # See if the package has an installer
            if not metadata["gui-only"] and not my.options.gui_only:
                run_plugin_installer(package, "uninstall")
