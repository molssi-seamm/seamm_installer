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
        if not metadata["gui-only"]:
            for package in packages:
                run_plugin_installer(package, "uninstall")

    else:
        for package in to_uninstall:
            available = packages[package]["version"]
            channel = packages[package]["channel"]
            installed_version, installed_channel = package_info(package)
            ptype = packages[package]["type"]
            if installed_version < available:
                print(
                    f"Updating {ptype.lower()} {package} from version "
                    f"{installed_version} to {available}"
                )
                if channel == installed_channel:
                    if channel == "pypi":
                        my.pip.uninstall(package)
                    else:
                        my.conda.uninstall(package)
                else:
                    if installed_channel == "pypi":
                        my.pip.uninstall(package)
                    else:
                        my.conda.uninstall(package)
                    if channel == "pypi":
                        my.pip.install(package)
                    else:
                        my.conda.install(package)
            # See if the package has an installer
            if not metadata["gui-only"]:
                run_plugin_installer(package, "uninstall")
