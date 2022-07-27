# -*- coding: utf-8 -*-

"""The main module for running the SEAMM installer.
"""
import argparse
import logging
import sys

from . import cli
from . import my
from . import util

my.logger = logging.getLogger(__name__)


def run():
    """Run the installer.

    The installer uses nested parsers to handle commands and options on the
    command line. Each subparser has a default command which is how the code
    calls the requested method.
    """
    # Get the Conda environment
    util.initialize()
    my.environment = my.conda.active_environment

    # Create the argument parser and set the debug level ASAP
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--log-level",
        default="WARNING",
        type=str.upper,
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=("The level of informational output, defaults to " "'%(default)s'"),
    )
    if my.environment is not None and "dev" in my.environment:
        my.development = True
        parser.add_argument(
            "--no-development",
            dest="development",
            action="store_false",
            help="Work with the production environment, not the development one.",
        )
    else:
        my.development = False
        parser.add_argument(
            "--development",
            action="store_true",
            help="Work with the development environment, not the production one.",
        )

    # Whether to not use the GUI
    parser.add_argument(
        "-n",
        "--nw",
        dest="no_gui",
        action="store_true",
        help="No GUI, just commandline.",
    )

    # Parse the first options
    if "-h" not in sys.argv and "--help" not in sys.argv:
        options, _ = parser.parse_known_args()
        kwargs = vars(options)

        # Set up the logging
        level = kwargs.pop("log_level", "WARNING")
        logging.basicConfig(level=level)

        my.development = kwargs.pop("development", False)
    else:
        kwargs = {"no_gui": True}

    # Now setup the rest of the command-line interface.
    parser.add_argument(
        "--root",
        type=str,
        default="~/SEAMM_DEV" if my.development else "~/SEAMM",
    )

    if kwargs.pop("no_gui", False):
        cli.setup(parser)

        # Parse the command-line arguments and call the requested function
        my.options = parser.parse_args()
        try:
            sys.exit(my.options.func())
        except AttributeError:
            print(f"Missing arguments to seamm-installer {' '.join(sys.argv[1:])}")
            # Append help so help will be printed
            sys.argv.append("--help")
            # re-run
            run()
    else:
        from .gui import GUI

        gui = GUI(logger=my.logger)

        # enter the event loop
        gui.event_loop()


if __name__ == "__main__":
    run()
