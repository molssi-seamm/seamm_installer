# !/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
from pathlib import Path
import shutil

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
        """Check the installation and fix errors if requested.

        If the option `yes` is present and True, this method will attempt to
        correct any errors in the configuration file. Use `--yes` on the
        command line to enable this.

        The information in the configuration file is:

            installation
                How the executables are installed. One of `user`, `modules` or `conda`
            conda-environment
                The Conda environment if and only if `installation` = `conda`
            modules
                The environment modules if `installation` = `modules`
            {self.path_name}
                The path where the executables are. Automatically
                defined if `installation` is `conda` or `modules`, but given
                by the user is it is `user`.

        Returns
        -------
        bool
            True if everything is OK, False otherwise. If `yes` is given as an
            option, the return value is after fixing the configuration.
        """
        self.logger.debug("Entering check method.")
        if not self.configuration.section_exists(self.section):
            if self.options.yes or self.ask_yes_no(
                f"There is no section for {self.section} in the configuration "
                f" file ({self.configuration.path}).\nAdd one?",
                default="yes",
            ):
                self.check_configuration_file()
                print(
                    f"Added the {self.section} section to the configuration file "
                    f"{self.configuration.path}"
                )

        # Get the values from the configuration
        data = self.configuration.get_values(self.section)

        # Save the initial values, if any, of the key configuration variables
        if self.path_name in data and data[self.path_name] != "":
            path = Path(data[self.path_name]).expanduser().resolve()
            initial_exe_path = path
        else:
            initial_exe_path = None
        if "installation" in data and data["installation"] != "":
            initial_installation = data["installation"]
        else:
            initial_installation = None
        if "conda-environment" in data and data["conda-environment"] != "":
            initial_conda_environment = data["conda-environment"]
        else:
            initial_conda_environment = None
        if "modules" in data and data["modules"] != "":
            initial_modules = data["modules"]
        else:
            initial_modules = None

        # Is there a valid -path?
        self.logger.debug(
            "Checking for the executable in the initial path " f"{initial_exe_path}."
        )
        if initial_exe_path is None or not self.have_executables(initial_exe_path):
            exe_path = None
        else:
            exe_path = initial_exe_path
        self.logger.debug(f"initial-exe-path = {initial_exe_path}.")

        # Is there an installation indicated?
        if initial_installation in ("user", "conda", "modules"):
            installation = initial_installation
        else:
            installation = None
        self.logger.debug(f"initial-installation = {initial_installation}.")

        if installation == "conda":
            # Is there a conda environment?
            conda_environment = None
            if initial_conda_environment is None or not self.conda.exists(
                initial_conda_environment
            ):
                if exe_path is not None:
                    # see if this path corresponds to a Conda environment
                    for tmp in self.conda.environments:
                        tmp_path = self.conda.path(tmp) / "bin"
                        if tmp_path == exe_path:
                            conda_environment = tmp
                            break
                    if conda_environment is not None:
                        if self.options.yes or self.ask_yes_no(
                            "The Conda environment in the config file "
                            "is not correct.\n"
                            f"It should be {conda_environment}. Fix?",
                            default="yes",
                        ):
                            self.configuration.set_value(
                                self.section, "installation", "conda"
                            )
                            self.configuration.set_value(
                                self.section, "conda-environment", conda_environment
                            )
                            self.configuration.set_value(self.section, "modules", "")
                            self.configuration.save()
                            print(
                                "Corrected the conda environment to "
                                f"{conda_environment}"
                            )
            else:
                # Have a Conda environment!
                conda_path = self.conda.path(initial_conda_environment) / "bin"
                self.logger.debug(
                    f"Checking for executable in conda-path: {conda_path}."
                )
                if self.have_executables(conda_path):
                    # All is good!
                    conda_environment = initial_conda_environment
                    if exe_path is None:
                        if self.options.yes or self.ask_yes_no(
                            f"The {self.path_name} in the config file is not set,"
                            f"but the Conda environment {conda_environment} "
                            f"is.\nFix {self.path_name}?",
                            default="yes",
                        ):
                            exe_path = conda_path
                            self.configuration.set_value(
                                self.section, self.path_name, exe_path
                            )
                            self.configuration.set_value(self.section, "modules", "")
                            self.configuration.save()
                            print(f"Set the {self.path_name} to {conda_path}")
                    elif exe_path != conda_path:
                        if self.options.yes or self.ask_yes_no(
                            f"The {self.path_name} in the config file {exe_path}"
                            "is different from that for  the Conda "
                            f"environment {conda_environment} is.\n"
                            "Use the path from the Conda environment?",
                            default="yes",
                        ):
                            exe_path = conda_path
                            self.configuration.set_value(
                                self.section, self.path_name, exe_path
                            )
                            self.configuration.set_value(self.section, "modules", "")
                            self.configuration.save()
                            print(f"Changed the {self.path_name} to {conda_path}")
                    else:
                        # Everything is fine!
                        pass
        if installation == "modules":
            print(f"Can't check the actual modules {initial_modules} yet")
            if initial_conda_environment is not None:
                if self.options.yes or self.ask_yes_no(
                    "A Conda environment is given: "
                    f"{initial_conda_environment}.\n"
                    "A Conda environment should not be used when using "
                    "modules. Remove it from the configuration?",
                    default="yes",
                ):
                    self.configuration.set_value(self.section, "conda-environment", "")
                    self.configuration.save()
                    print(
                        "Using modules, so removed the conda-environment from "
                        "the configuration"
                    )
        else:
            if exe_path is None:
                # No path or executable in the path!
                environments = self.conda.environments
                if self.environment in environments:
                    # Make sure it is first!
                    environments.remove(self.environment)
                    environments.insert(0, self.environment)
                for tmp in environments:
                    tmp_path = self.conda.path(tmp) / "bin"
                    if self.have_executables(tmp_path):
                        if self.options.yes or self.ask_yes_no(
                            f"There are no valid executables in the {self.path_name}"
                            " in the config file, but there are in the Conda "
                            f"environment {tmp} ({tmp_path}).\n"
                            "Use them?",
                            default="yes",
                        ):
                            conda_environment = tmp
                            exe_path = tmp_path
                            self.configuration.set_value(
                                self.section, self.path_name, exe_path
                            )
                            self.configuration.set_value(
                                self.section, "installation", "conda"
                            )
                            self.configuration.set_value(
                                self.section, "conda-environment", conda_environment
                            )
                            self.configuration.set_value(self.section, "modules", "")
                            self.configuration.save()
                            print(
                                "Will use the conda environment "
                                f"'{conda_environment}'"
                            )
                            break
            if exe_path is None:
                # Haven't found it. Check in the path.
                exe_path = self.executables_in_path()
                if exe_path is not None:
                    if self.options.yes or self.ask_yes_no(
                        "Found valid executable(s) in the PATH at "
                        f"{exe_path}\n"
                        "Use them?",
                        default="yes",
                    ):
                        self.configuration.set_value(
                            self.section, "installation", "user"
                        )
                        self.configuration.set_value(
                            self.section, "conda-environment", ""
                        )
                        self.configuration.set_value(self.section, "modules", "")
                        self.configuration.save()
                        print("Using the executable(s) at {exe_path}")

            if exe_path is None:
                # Can't find the executable(s)
                print(
                    f"Cannot find the executable(s): {', '.join(self.executables)}. "
                    "You will need to install them."
                )
                if (
                    initial_installation is not None
                    and initial_installation != "not installed"
                ):
                    if self.options.yes or self.ask_yes_no(
                        "The configuration file indicates that the executable(s) "
                        "are installed, but they can't be found.\n"
                        "Fix the configuration file?",
                        default="yes",
                    ):
                        self.configuration.set_value(
                            self.section, "installation", "not installed"
                        )
                        self.configuration.set_value(self.section, self.path_name, "")
                        self.configuration.set_value(
                            self.section, "conda-environment", ""
                        )
                        self.configuration.set_value(self.section, "modules", "")
                        self.configuration.save()
                        print(
                            "Since no executable(s) were found, cleared "
                            "the configuration."
                        )
            else:
                print("The check completed successfully.")

    def check_configuration_file(self):
        """Checks that the necessary section for the plug-in is in the
        configuration file.
        """
        if not self.configuration.section_exists(self.section):
            # Get the text of the data
            path = self.resource_path / "configuration.txt"
            text = path.read_text()

            # Add it to the configuration file and write to disk.
            self.configuration.add_section(self.section, text)
            self.configuration.save()

    def have_executables(self, path):
        """Check whether the executables are found at the given path.

        Parameters
        ----------
        path : pathlib.Path
            The directory to check.

        Returns
        -------
        bool
            True if all of the executables are found.
        """
        for executable in self.executables:
            tmp_path = path / executable
            if not tmp_path.exists():
                self.logger.debug(f"Did not find {executable} in {path}")
                return False
        self.logger.debug(f"Found all executables in {path}")
        return True

    def executables_in_path(self):
        """Check whether the executables are found in the PATH.

        Returns
        -------
        pathlib.Path
            The path where the executables are, or None.
        """
        path = None
        for executable in self.executables:
            path = shutil.which(executable)
            if path is not None:
                path = Path(path).expanduser().resolve()
                break
        # And check that have all the executables
        if path is not None and self.have_executables(path):
            return path
        else:
            return None

    def install(self):
        """Install using a Conda environment."""
        print(
            f"Installing Conda environment '{self.environment}'. This "
            "may take a minute or two."
        )
        self.conda.create_environment(self.environment_file, name=self.environment)
        # Update the configuration file.
        self.check_configuration_file()
        path = self.conda.path(self.environment) / "bin"
        self.configuration.set_value(self.section, self.path_name, str(path))
        self.configuration.set_value(self.section, "installation", "conda")
        self.configuration.set_value(
            self.section, "conda-environment", self.environment
        )
        self.configuration.set_value(self.section, "modules", "")
        self.configuration.save()
        print("Done!\n")

    def run(self):
        """Do what the user asks via the commandline."""
        self.options = self.parser.parse_args()

        # Run the requested subcommand
        self.options.method()

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

    def show(self):
        """Show the current installation status."""
        self.logger.debug("Entering show")

        # See if the executables are already registered in the configuration file
        if not self.configuration.section_exists(self.section):
            print(f"There is no section in the configuration file for {self.section}.")
        data = self.configuration.get_values(self.section)

        # Keep track of where executables are
        exe_path = None

        # Is the path in the configuration file?
        if self.path_name in data:
            conf_path = Path(data[self.path_name]).expanduser().resolve()
            if self.have_executables(conf_path):
                exe_path = conf_path
                exe_version = self.exe_version(exe_path / self.executables[0])

            extra = f"from path {conf_path}."
            if "installation" in data:
                installation = data["installation"]
                if installation == "conda":
                    if "conda-environment" in data and data["conda-environment"] != "":
                        extra = (
                            "from Conda environment " f"{data['conda-environment']}."
                        )
                    else:
                        extra = "from an unknown Conda environment."
                elif installation == "modules":
                    if "modules" in data and data["modules"] != "":
                        extra = f"from module(s) {data['modules']}."
                    else:
                        extra = "from unknown modules."
                elif installation == "user":
                    extra = f"from user-defined path {conf_path}."

            if exe_path is not None:
                print(f"{self.executables[0]} executable, version {exe_version}")
                print(extra)
            else:
                print(f"{self.executables[0]} is not configured to run.")
        else:
            print(f"{self.executables[0]} is not configured to run.")

        # Look in the PATH, but only record if not same as in the conf file
        tmp = shutil.which(self.executables[0])
        if tmp is not None:
            tmp = Path(tmp).expanduser().resolve().parent
            if exe_path is not None and exe_path != tmp:
                version = self.executable_version(tmp)
                print(
                    f"Another executable (version {version}) "
                    "is in the PATH:\n"
                    f"    {tmp}"
                )

    def uninstall(self):
        """Uninstall the Conda environment."""
        # See if the exectuables are already registered in the configuration file
        data = self.configuration.get_values(self.section)
        if "installation" in data and data["installation"] == "conda":
            environment = self.environment
            if "conda-environment" in data and data["conda-environment"] != "":
                environment = data["conda-environment"]
            print(
                f"Uninstalling Conda environment '{environment}'. This "
                "may take a minute or two."
            )
            self.conda.remove_environment(environment)
            # Update the configuration file.
            self.configuration.set_value(self.section, self.path_name, "")
            self.configuration.set_value(self.section, "modules", "")
            self.configuration.set_value(self.section, "installation", "not installed")
            self.configuration.set_value(self.section, "conda-environment", "")
            self.configuration.save()
            print("Done!\n")

    def update(self):
        """Update the installation, if possible."""
        # See if the executables are already registered in the configuration file
        data = self.configuration.get_values(self.section)
        if "installation" in data and data["installation"] == "conda":
            environment = self.environment
            if "conda-environment" in data and data["conda-environment"] != "":
                environment = data["conda-environment"]
            print(
                f"Updating Conda environment '{environment}'. This may "
                "take a minute or two."
            )
            self.conda.update_environment(self.environment_file, name=environment)
            # Update the configuration file, just in case.
            path = self.conda.path(environment) / "bin"
            self.configuration.set_value(self.section, self.path_name, str(path))
            self.configuration.set_value(self.section, "installation", "conda")
            self.configuration.set_value(self.section, "conda-environment", environment)
            self.configuration.set_value(self.section, "modules", "")
            self.configuration.save()
            print("Done!\n")
        else:
            print(
                "Unable to update the executables because they were not installed "
                "using Conda"
            )
