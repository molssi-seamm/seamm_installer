# !/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
from pathlib import Path

import seamm_installer

logger = logging.getLogger(__name__)

prolog = """\
# Configuration options for SEAMM.
#
# The options in this file override any defaults in SEAMM
# and its plug-ins; however, command-line arguments will
# in turn override the values here.
#
# The keys should have dashes '-' separating words. In either case,
# the command line options is '--<key with dashes>' and the variable
# name inside SEAMM is '<key with underscores>', e.g. 'log-level' in
# this file corresponds to the command line option '--log-level'
# and the variable in SEAMM 'log_level'.
#
# The file is broken into sections, with a name in square brackets,
# like [lammps-step]. Within each section there can be a series of
# option = value statements. '#' introduces comment lines. The
# section names and variables should be in lower case except for
# the [DEFAULT] and [SEAMM] sections which are special.
#
# [DEFAULT] provides default values for any other section. If an
# option is requested for a section, but does not exist in that
# section, the option is looked for in the [DEFAULT] section. If it
# exists there, the corresponding value is used.
#
# The [SEAMM] section contains options for the SEAMM environment
# itself. On the command line these come before any options for
# plug-ins, which follow the name of the plug-in. The plug-in name is
# also the section in this file for that plug-in.
#
# All other sections are for the plug-ins, and generally have the form
# [xxxxx-step], in lowercase.
#
# Finally, options can refer to options in the same or other sections
# with a syntax like ${section:option}. If the section is omitted,
# the current section and [DEFAULT] are searched, in that
# order. Otherwise the given section and [DEFAULT] are searched.

[DEFAULT]
# Default values for options in any section.

[SEAMM]
# Options for the SEAMM infrastructure.

"""


class InstallerBase(object):
    """A base class for plug-in installers.

    This base class provides much of the functionality needed by installers for
    plug-ins, but not the functionality specific to a given plug-in.

    Attributes
    ----------
    section : str
        The section of the configuration file to use. Defaults to None.
    """

    def __init__(self, ini_file="~/.seamm/seamm.ini", logger=logger):
        # Create the ini file if it does not exist.
        self._check_ini_file(ini_file)

        self.logger = logger

        # and make the configuration, conda and pip objects
        self._configuration = seamm_installer.Configuration(ini_file)
        self._conda = seamm_installer.Conda()
        self._pip = seamm_installer.Pip()

        # Setup the parseer for the command-line
        self.options = None
        self.subparser = {}
        self.parser = self.setup_parser()

    @property
    def conda(self):
        """The Conda object to use for accessing Conda."""
        return self._conda

    @property
    def configuration(self):
        """The Configuration object for working with the ini file."""
        return self._configuration

    @property
    def pip(self):
        """The Pip object used for working with pip."""
        return self._pip

    def ask_yes_no(self, text, default=None):
        """Ask a simple yes/no question, returning True/False.

        Parameters
        ----------
        text : str
             The text of the question.

        Returns
        -------
        bool
            True for yes; False, no
        """
        if default is None:
            answer = input(f"{text} y/n: ")
        elif default == "yes":
            answer = input(f"{text} [y]/n: ")
        elif default == "no":
            answer = input(f"{text} y/[n]: ")
        else:
            answer = input(f"{text} y/n: ")

        while True:
            if len(answer) == 0:
                if default == "yes":
                    return True
                elif default == "no":
                    return False
            else:
                answer = answer[0].lower()
                if answer == "y":
                    return True
                elif answer == "n":
                    return False
            input("Please answer 'y' or 'n': ")

    def _check_ini_file(self, ini_file):
        """Ensure that the ini file exists.

        If it does not, it will be created and a template written to it. The
        template contains a prolog with a description of the file followed by
        empty [DEFAULT] and [SEAMM] sections, which ensures that they are
        present and at the top of the file.
        """
        path = Path(ini_file).expanduser().resolve()
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(prolog)

    def check(self):
        """Check that the installation is OK.

        Most plug-ins don't have anyhting to check.
        """
        pass

    def install(self):
        """Override this to install whatever is needed."""
        raise NotImplementedError("need to override 'install' method.")

    def setup_parser(self):
        """Parse the command line into the options."""

        parser = argparse.ArgumentParser()

        parser.add_argument(
            "--log-level",
            default="WARNING",
            type=str.upper,
            choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help=("The level of informational output, defaults to " "'%(default)s'"),
        )
        parser.add_argument(
            "--seamm",
            default="seamm",
            type=str.lower,
            help="The conda environment for seamm, defaults to '%(default)s'",
        )

        subparsers = parser.add_subparsers()
        self.subparser["subparsers"] = subparsers

        # check
        self.subparser["check"] = check = subparsers.add_parser("check")
        check.add_argument(
            "-y", "--yes", action="store_true", help="Answer 'yes' to all prompts"
        )
        check.set_defaults(method=self.check)

        # install
        self.subparser["install"] = install = subparsers.add_parser("install")
        install.set_defaults(method=self.install)

        # update
        self.subparser["update"] = update = subparsers.add_parser("update")
        update.set_defaults(method=self.update)

        # uninstall
        uninstall = subparsers.add_parser("uninstall")
        self.subparser["uninstall"] = uninstall
        uninstall.set_defaults(method=self.uninstall)

        # show
        self.subparser["show"] = show = subparsers.add_parser("show")
        show.set_defaults(method=self.show)

        # Parse what we know so that we can set up logging.
        tmp = parser.parse_known_args()
        self.options = tmp[0]

        # Set up the logging
        level = self.options.log_level
        logging.basicConfig(level=level)
        # Don't know why basicConfig doesn't seem to work!
        self.logger.setLevel(level)
        self.logger.info(f"Logging level is {level}")

        return parser

    def run(self):
        """Do what the user asks via the commandline."""
        self.options = self.parser.parse_args()

        # Run the requested subcommand
        self.options.method()

    def show(self):
        """Override this to show whatever is needed."""
        raise NotImplementedError("need to override 'show' method.")

    def uninstall(self):
        """Override this to uninstall whatever is needed."""
        raise NotImplementedError("need to override 'uninstall' method.")

    def update(self):
        """Override this to update whatever is needed."""
        raise NotImplementedError("need to override 'update' method.")
