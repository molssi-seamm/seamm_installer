# -*- coding: utf-8 -*-

"""Install requested components of SEAMM."""
import platform

from . import datastore
from . import my
from .util import (
    find_packages,
    get_metadata,
    package_info,
    run_plugin_installer,
    set_metadata,
)


system = platform.system()
if system in ("Darwin",):
    from .mac import ServiceManager

    mgr = ServiceManager(prefix="org.molssi.seamm")
elif system in ("Linux",):
    raise NotImplementedError("Linux not implemented yet.")
else:
    raise NotImplementedError(f"SEAMM does not support services on {system} yet.")


def setup(parser):
    """Define the command-line interface for installing SEAMM components.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The main parser for the application.
    """
    # Install
    subparser = parser.add_parser("install")
    subparser.set_defaults(func=install)
    subparser.add_argument(
        "--all",
        action="store_true",
        help="Install any missing packages from the MolSSI",
    )
    subparser.add_argument(
        "--third-party",
        action="store_true",
        help="Install any missing packages from 3rd parties",
    )
    subparser.add_argument(
        "--update",
        action="store_true",
        help="Update any out-of-date packages",
    )
    subparser.add_argument(
        "--gui-only",
        action="store_true",
        help="Install only packages necessary for the GUI",
    )
    subparser.add_argument(
        "modules",
        nargs="*",
        default=None,
        help="Specific modules and plug-ins to install.",
    )


def install():
    """Install the requested SEAMM components and plug-ins.

    Parameters
    ----------
    options : argparse.Namespace
        The options from the command-line parser.
    """
    if my.options.gui_only:
        metadata = get_metadata()
        if not metadata["gui-only"]:
            metadata["gui-only"] = True
            set_metadata(metadata)

    if my.options.all:
        install_packages(
            "all", third_party=my.options.third_party, update=my.options.update
        )
    else:
        install_packages(my.my.options.modules, update=my.options.update)


def install_packages(to_install, update=False, third_party=False):
    """Install SEAMM components and plug-ins."""
    metadata = get_metadata()

    # Find all the packages
    packages = find_packages(progress=True)

    if to_install == "all":
        if third_party:
            to_install = [*packages.keys()]
        else:
            to_install = [p for p, d in packages.items() if "third" not in d["type"]]

    for package in to_install:
        available = packages[package]["version"]
        channel = packages[package]["channel"]
        installed_version, installed_channel = package_info(package)
        ptype = packages[package]["type"]

        if installed_channel is None:
            print(f"Installing {ptype.lower()} {package} version {available}.")
            if channel == "pypi":
                my.pip.install(package)
            else:
                my.conda.install(package)

            if package == "seamm-datastore":
                datastore.update(my.options)
            elif package == "seamm-dashboard":
                service = f"dev_{package}" if my.development else package
                mgr.restart(service)
            elif package == "seamm-jobserver":
                service = f"dev_{package}" if my.development else package
                mgr.restart("service")
        elif update and installed_version < available:
            print(
                f"Updating {ptype.lower()} {package} from version {installed_version} "
                f"to {available}"
            )
            if channel == installed_channel:
                if channel == "pypi":
                    my.pip.install(package)
                else:
                    my.conda.install(package)
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
            run_plugin_installer(package, "install")
