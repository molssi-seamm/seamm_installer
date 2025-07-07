# -*- coding: utf-8 -*-

"""Install requested components of SEAMM."""
from datetime import datetime
import platform

from packaging.version import Version

from . import datastore
from .metadata import development_packages, development_packages_pip
from . import my
from .util import (
    create_env,
    find_packages,
    get_metadata,
    run_plugin_installer,
    set_metadata,
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
            "all",
            third_party=my.options.third_party,
            update=my.options.update,
            gui_only=my.options.gui_only,
        )
    else:
        install_packages(
            my.options.modules, update=my.options.update, gui_only=my.options.gui_only
        )

    if my.development:
        install_development_environment()


def install_packages(to_install, update=False, third_party=False, gui_only=False):
    """Install SEAMM components and plug-ins."""
    metadata = get_metadata()

    # Find all the packages
    packages = find_packages(progress=True)

    if to_install == "all":
        if third_party:
            to_install = [*packages.keys()]
        else:
            to_install = [
                p for p, d in packages.items() if "3rd-party" not in d["type"]
            ]

    # Get the info about the installed packages
    info = my.conda.list(environment=my.environment)

    conda_packages = []
    pypi_packages = []
    for package in to_install:
        if package == "development":
            continue
        available = Version(packages[package]["version"])
        channel = packages[package]["channel"]
        installed_version = (
            Version(info[package]["version"]) if package in info else None
        )
        ptype = packages[package]["type"]

        pinned = "pinned" in packages[package] and packages[package]["pinned"]
        if pinned:
            spec = f"{package}=={available}"
            print(f"pinning {package} to version {available}")
        else:
            spec = package

        if package not in info:
            print(f"Installing {ptype.lower()} {package} version {available}.")
            if channel == "pypi":
                pypi_packages.append(spec)
            else:
                conda_packages.append(spec)
        elif update and installed_version < available:
            installed_channel = info[package]["channel"]
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
                    f"Install: channel {channel} != {installed_channel} for "
                    f"package {package}"
                )

    # Create a list of all packages that exist already or will be installer
    all_packages = [*packages.keys()]
    for package in to_install:
        if package not in all_packages:
            all_packages.append(package)

    # Get the environment file data, accounting for pinned dependencies
    env = create_env(conda_packages, pypi_packages, installed_packages=all_packages)

    directory = my.root / "environments"
    directory.mkdir(parents=True, exist_ok=True)
    tstamp = datetime.now().isoformat(timespec="seconds")
    path = directory / f"{tstamp}_install.yml"
    path.write_text(env)

    # And do the update
    if update:
        print(f"Installing to and updating the Conda environment with {path.name}")
    else:
        print(f"Installing into the Conda environment with {path.name}")
    my.conda.update_environment(path, name=my.environment)
    print("done")

    # Write the export file
    path = directory / f"{tstamp}_environment.yml"
    my.conda.export_environment(my.environment, path=path)

    # And the explicit file for "conda create --file"
    path = directory / f"{tstamp}_environment.txt"
    path.write_text(my.conda.list(my.environment, explicit=True))

    # Restart services and run custom installer
    for package in to_install:
        if not update and package in info:
            continue

        if package == "development":
            continue

        if package == "seamm-datastore":
            datastore.update()
        elif package == "seamm-dashboard":
            # If installing, the service should not exist, but restart if it does.
            service = f"dev_{package}" if my.development else package
            mgr.restart(service, ignore_errors=True)
        elif package == "seamm-jobserver":
            service = f"dev_{package}" if my.development else package
            mgr.restart(service, ignore_errors=True)

        # See if the package has an installer
        if not metadata["gui-only"] and not gui_only:
            run_plugin_installer(package, "install")


def install_development_environment():
    """Install packages needed for development."""
    packages = [*development_packages]
    print(f"Installing Conda development packages {' '.join(packages)}")
    my.conda.install(packages)

    packages = [*development_packages_pip]
    print(f"Installing PyPI development packages {' '.join(packages)}")
    my.pip.install(packages)
