# -*- coding: utf-8 -*-

"""Update requested components of SEAMM."""
from . import my
from .util import find_packages, get_metadata, package_info, run_plugin_installer


def setup(parser):
    """Define the command-line interface for updating SEAMM components.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The main parser for the application.
    """
    subparser = parser.add_parser("update")
    subparser.set_defaults(func=update)

    subparser.add_argument(
        "--all",
        action="store_true",
        help="Fully update the SEAMM installation",
    )
    subparser.add_argument(
        "--install-molssi",
        action="store_true",
        help="Install any missing packages from the MolSSI",
    )
    subparser.add_argument(
        "--install-3rd-party",
        action="store_true",
        help="Install any missing packages from 3rd parties",
    )
    subparser.add_argument(
        "modules",
        nargs="*",
        default=None,
        help="Specific modules and plug-ins to update.",
    )


def update():
    """Update the requested SEAMM components and plug-ins.

    Parameters
    ----------
    """

    if my.options.all:
        # First update the conda environment
        environment = my.conda.active_environment
        print(f"Updating the conda environment {environment}")
        my.conda.update(all=True)

        update_packages("all")
    else:
        update_packages(my.options.modules)


def update_packages(to_update):
    """Update SEAMM components and plug-ins."""
    metadata = get_metadata()

    # Find all the packages
    packages = find_packages(progress=True)

    if to_update == "all":
        to_update = [*packages.keys()]

    for package in to_update:
        available = packages[package]["version"]
        channel = packages[package]["channel"]
        installed_version, installed_channel = package_info(package)
        ptype = packages[package]["type"]
        if installed_version < available:
            print(
                f"Updating {ptype.lower()} {package} from version {installed_version} "
                f"to {available}"
            )
            if channel == installed_channel:
                if channel == "pypi":
                    my.pip.update(package)
                else:
                    my.conda.update(package)
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
            run_plugin_installer(package, "update")
