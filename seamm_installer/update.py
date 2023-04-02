# -*- coding: utf-8 -*-

"""Update requested components of SEAMM."""
import platform

from .datastore import update as update_datastore
from .metadata import development_packages, development_packages_pip
from . import my
from .util import find_packages, get_metadata, package_info, run_plugin_installer


system = platform.system()
if system in ("Darwin",):
    from .mac import ServiceManager

    mgr = ServiceManager(prefix="org.molssi.seamm")
elif system in ("Linux",):
    from .linux import ServiceManager

    mgr = ServiceManager(prefix="org.molssi.seamm")
else:
    raise NotImplementedError(f"SEAMM does not support services on {system} yet.")


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
        "--gui-only",
        action="store_true",
        help="Update only packages necessary for the GUI",
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

    # Need to track packages that require services to be restarted.
    service_packages = ("seamm-datastore", "seamm-dashboard", "seamm-jobserver")
    initial_version = {p: package_info(p)[0] for p in service_packages}

    if my.options.all:
        # First update the conda environment
        # environment = my.conda.active_environment
        # print(f"Updating the conda environment {environment}")
        # my.conda.update(all=True)

        update_packages("all")
    else:
        update_packages(my.options.modules)

    if my.development:
        update_development_environment()

    final_version = {p: package_info(p)[0] for p in service_packages}
    # And restart any services that need
    if (
        initial_version["seamm-datastore"] is not None
        and final_version["seamm-datastore"] is not None
        and final_version["seamm-datastore"] > initial_version["seamm-datastore"]
    ):
        service_name = "dev_dashboard" if my.development else "dashboard"
        if mgr.is_installed(service_name):
            mgr.stop(service_name)
            update_datastore()
            mgr.start(service_name)
            print(f"Restarted the {service_name} because the datastore was updated.")
        service_name = "dev_jobserver" if my.development else "jobserver"
        if mgr.is_installed(service_name):
            mgr.restart(service_name)
            print(f"Restarted the {service_name} because the datastore was updated.")
    else:
        if (
            initial_version["seamm-dashboard"] is not None
            and final_version["seamm-dashboard"] is not None
            and final_version["seamm-dashboard"] > initial_version["seamm-dashboard"]
        ):
            service_name = "dev_dashboard" if my.development else "dashboard"
            if mgr.is_installed(service_name):
                mgr.restart(service_name)
                print(f"Restarted the {service_name} because it was updated.")
        if (
            initial_version["seamm-jobserver"] is not None
            and final_version["seamm-jobserver"] is not None
            and final_version["seamm-jobserver"] > initial_version["seamm-jobserver"]
        ):
            service_name = "dev_jobserver" if my.development else "jobserver"
            if mgr.is_installed(service_name):
                mgr.restart(service_name)
                print(f"Restarted the {service_name} because it was updated.")


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
        # Skip packages that aren't installed.
        if installed_version is None:
            continue

        pinned = "pinned" in packages[package] and packages[package]["pinned"]
        if pinned:
            spec = f"{package}=={available}"
            print(f"pinning {package} to version {available}")
        else:
            spec = package

        ptype = packages[package]["type"]
        if installed_version < available:
            # Convert conda-forge url in channel to 'conda-forge'
            if "/conda-forge" in channel:
                channel = "conda-forge"

            print(
                f"Updating {ptype.lower()} {package} from version {installed_version} "
                f"to {available}"
            )
            if channel == installed_channel:
                if channel == "pypi":
                    if pinned:
                        my.pip.install(spec)
                    else:
                        my.pip.update(spec)
                else:
                    if pinned:
                        my.conda.install(spec)
                    else:
                        my.conda.update(spec)
            else:
                if installed_channel == "pypi":
                    my.pip.uninstall(package)
                else:
                    my.conda.uninstall(package)
                if channel == "pypi":
                    my.pip.install(spec)
                else:
                    my.conda.install(spec)
        # See if the package has an installer
        if not metadata["gui-only"] and not my.options.gui_only:
            run_plugin_installer(package, "update")


def update_development_environment():
    """Update packages needed for development."""
    packages = [*development_packages]
    print(f"Updating Conda development packages {' '.join(packages)}")
    my.conda.update(packages)

    packages = [*development_packages_pip]
    print(f"Updating PyPI development packages {' '.join(packages)}")
    my.pip.update(packages)
