# -*- coding: utf-8 -*-

"""The main module for running the SEAMM installer.
"""
import argparse
import logging

import seamm_installer

logger = logging.getLogger(__name__)


def run():
    """Run the installer.

    How the installer runs is controlled by command-line arguments.
    """
    # Create the installer
    installer = seamm_installer.SEAMMInstaller()

    # Parse the commandline
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--log-level",
        default="WARNING",
        type=str.upper,
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=("The level of informational output, defaults to " "'%(default)s'"),
    )

    # And continue
    parser.add_argument(
        "--seamm",
        default="seamm",
        type=str.lower,
        help="The conda environment for seamm, defaults to '%(default)s'",
    )

    subparsers = parser.add_subparsers()

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
        help=(
            "The modules to install. 'core', 'plug-ins', 'all', or a list of "
            "modules separated by spaces. Default is '%(default)s'."
        ),
    )

    # install
    install = subparsers.add_parser("install")
    install.set_defaults(method=installer.install)
    install.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help=(
            "The modules to install. 'core', 'plug-ins', 'all', or a list of "
            "modules separated by spaces. Default is '%(default)s'."
        ),
    )

    # show
    show = subparsers.add_parser("show")
    show.set_defaults(method=installer.show)
    show.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help=(
            "The modules to install. 'core', 'plug-ins', 'all', or a list of "
            "modules separated by spaces. Default is '%(default)s'."
        ),
    )

    # update
    update = subparsers.add_parser("update")
    update.set_defaults(method=installer.update)
    update.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help=(
            "The modules to install. 'core', 'plug-ins', 'all', or a list of "
            "modules separated by spaces. Default is '%(default)s'."
        ),
    )

    # uninstall
    uninstall = subparsers.add_parser("uninstall")
    uninstall.set_defaults(method=installer.uninstall)
    uninstall.add_argument(
        "modules",
        nargs="*",
        default=["all"],
        help=(
            "The modules to install. 'core', 'plug-ins', 'all', or a list of "
            "modules separated by spaces. Default is '%(default)s'."
        ),
    )

    # Parse the options
    options = parser.parse_args()
    kwargs = vars(options)

    # Set up the logging
    level = kwargs.pop("log_level")
    logging.basicConfig(level=level)

    environment = kwargs.pop("seamm")
    installer.seamm_environment = environment

    # get the modules
    modules = kwargs.pop("modules")

    # And remove the method
    method = kwargs.pop("method")

    # Check the installer itself.
    installer.check_installer(yes=True)

    # Run the requested subcommand
    method(*modules, **kwargs)
