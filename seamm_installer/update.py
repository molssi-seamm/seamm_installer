# -*- coding: utf-8 -*-

"""Update requested components of SEAMM."""
from datetime import datetime
import platform

from packaging.version import Version

from .datastore import update as update_datastore
from .metadata import development_packages, development_packages_pip
from . import my
from .util import (
    create_env,
    find_packages,
    get_metadata,
    package_info,
    run_plugin_installer,
)


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

        update_packages("all", gui_only=my.options.gui_only)
    else:
        update_packages(my.options.modules, gui_only=my.options.gui_only)

    if my.development:
        update_development_environment()

    final_version = {p: package_info(p)[0] for p in service_packages}
    # And restart any services that need
    if (
        initial_version["seamm-datastore"] is not None
        and final_version["seamm-datastore"] is not None
        and Version(final_version["seamm-datastore"])
        > Version(initial_version["seamm-datastore"])
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
            and Version(final_version["seamm-dashboard"])
            > Version(initial_version["seamm-dashboard"])
        ):
            service_name = "dev_dashboard" if my.development else "dashboard"
            if mgr.is_installed(service_name):
                mgr.restart(service_name)
                print(f"Restarted the {service_name} because it was updated.")
        if (
            initial_version["seamm-jobserver"] is not None
            and final_version["seamm-jobserver"] is not None
            and Version(final_version["seamm-jobserver"])
            > Version(initial_version["seamm-jobserver"])
        ):
            service_name = "dev_jobserver" if my.development else "jobserver"
            if mgr.is_installed(service_name):
                mgr.restart(service_name)
                print(f"Restarted the {service_name} because it was updated.")


def update_packages(to_update, gui_only=False):
    """Update SEAMM components and plug-ins."""
    metadata = get_metadata()

    # Find all the packages
    packages = find_packages(progress=True)

    if to_update == "all":
        to_update = [*packages.keys()]

    # Get the info about the installed packages
    info = my.conda.list(environment=my.environment)

    conda_packages = []
    pypi_packages = []
    for package in to_update:
        available = Version(packages[package]["version"])
        channel = packages[package]["channel"]

        # Skip packages that aren't installed.
        if package not in info:
            continue

        installed_version = Version(info[package]["version"])
        installed_channel = info[package]["channel"]

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
                    pypi_packages.append(spec)
                else:
                    conda_packages.append(spec)
            else:
                raise NotImplementedError(
                    f"package {package} changed from {installed_channel} to {channel}!"
                )
    # Added any pinned dependencies based on everything installed
    env = create_env(
        conda_packages, pypi_packages, installed_packages=[*packages.keys()]
    )

    directory = my.root / "environments"
    directory.mkdir(exist_ok=True)
    tstamp = datetime.now().isoformat(timespec="seconds")
    path = directory / f"{tstamp}_update.yml"
    path.write_text(env)

    # And do the update
    print(f"Updating the Conda environment with {path.name}")
    my.conda.update_environment(path, name=my.environment)
    print("done")

    # Write the export file
    path = directory / f"{tstamp}_environment.yml"
    my.conda.export_environment(my.environment, path=path)

    # And the explicit file for "conda create --file"
    path = directory / f"{tstamp}_environment.txt"
    path.write_text(my.conda.list(my.environment, explicit=True))

    # See if any packages have an installer
    if not metadata["gui-only"] and not gui_only:
        for package in to_update:
            # Skip packages that aren't installed.
            if package in info:
                run_plugin_installer(package, "update")


def update_development_environment():
    """Update packages needed for development."""
    packages = [*development_packages]
    print(f"Updating Conda development packages {' '.join(packages)}")
    my.conda.update(packages)

    packages = [*development_packages_pip]
    print(f"Updating PyPI development packages {' '.join(packages)}")
    my.pip.update(packages)
