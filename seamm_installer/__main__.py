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
    # Parse the commandline
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--log-level',
        default='WARNING',
        type=str.upper,
        choices=['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help=(
            "The level of informational output, defaults to "
            "'%(default)s'"
        )
    )
    parser.add_argument(
        '--seamm',
        default='seamm',
        type=str.lower,
        help="The conda environment for seamm, defaults to '%(default)s'"
    )

    tmp = parser.parse_args()
    options = vars(tmp)

    # Set up the logging
    level = options.pop('log_level')
    logging.basicConfig(level=level)
    logger.info(f"Logging level is {level}")

    # Get to work!
    installer = seamm_installer.SEAMMInstaller(**options)
    installer.run()
