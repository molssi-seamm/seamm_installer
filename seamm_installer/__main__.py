# -*- coding: utf-8 -*-

"""The main module for running the SEAMM installer.
"""
import argparse
import logging
import platform
import sys

import seamm_installer

logger = logging.getLogger(__name__)


def run():
    """Run the installer.

    How the installer runs is controlled by command-line arguments.

    We need the installer object to setup the parser; however, it needs
    some of the information from the commandline so we parse those arguments
    first, then setup the rest.
    """
    system = platform.system()

    # Parse the commandline
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--log-level",
        default="WARNING",
        type=str.upper,
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=("The level of informational output, defaults to " "'%(default)s'"),
    )
    parser.add_argument(
        "--update-cache", action="store_true", help="Update the package database."
    )

    # And continue
    parser.add_argument(
        "--environment",
        default="",
        type=str.lower,
        help="The conda environment to install to, defaults to the current environment",
    )

    # Parse the first options
    if "-h" not in sys.argv and "--help" not in sys.argv:
        options, _ = parser.parse_known_args()
        kwargs = vars(options)

        # Set up the logging
        level = kwargs.pop("log_level")
        logging.basicConfig(level=level)

        environment = kwargs.pop("environment")

        # Create the installer
        installer = seamm_installer.SEAMMInstaller(environment=environment)
    else:
        # Create the installer
        installer = seamm_installer.SEAMMInstaller()

    subparsers = parser.add_subparsers()

    module_description = (
        "'core', 'plug-ins', 'all', 'development', 'apps', 'services', "
        "or a list of modules separated by spaces. "
        "Default is %(default)s."
    )

    # check
    check = subparsers.add_parser("check")
    check.set_defaults(method=installer.check)
    check.add_argument(
        "-y", "--yes", action="store_true", help="Answer 'yes' to all prompts"
    )
    check.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help="The modules to check: " + module_description,
    )

    # install
    install = subparsers.add_parser("install")
    install.set_defaults(method=installer.install)
    if system in ("Darwin",):
        install.add_argument(
            "--all-users",
            action="store_true",
            help="Install any apps or services for all users.",
        )
        install.add_argument(
            "--daemon",
            action="store_true",
            help="Install services as system-wide services.",
        )

    install.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help="The modules to install: " + module_description,
    )

    # show
    show = subparsers.add_parser("show")
    show.set_defaults(method=installer.show)
    show.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help="The modules to show: " + module_description,
    )

    # update
    update = subparsers.add_parser("update")
    update.set_defaults(method=installer.update)
    update.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help="The modules to update: " + module_description,
    )

    # uninstall
    uninstall = subparsers.add_parser("uninstall")
    uninstall.set_defaults(method=installer.uninstall)
    uninstall.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help="The modules to uninstall: " + module_description,
    )

    # Parse the options
    options = parser.parse_args()
    kwargs = vars(options)

    # Remove the logging and environment options since they have been handled
    level = kwargs.pop("log_level")
    environment = kwargs.pop("environment")

    # get the modules
    modules = kwargs.pop("modules", ["all"])

    # And remove the method
    method = kwargs.pop("method", installer.show)

    # Check the installer itself.
    if method == installer.install or method == installer.update:
        answer = True
    elif method == installer.check:
        answer = kwargs["yes"]
    else:
        answer = False

    installer.check_installer(yes=answer)

    # Run the requested subcommand
    method(*modules, **kwargs)
