# -*- coding: utf-8 -*-
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys

logger = logging.getLogger(__name__)


class Conda(object):
    """
    Class for handling conda

    Attributes
    ----------

    """

    def __init__(self, logger=logger):
        logger.debug("Creating Conda {str(type(self))}")

        self._is_installed = False
        self._data = None
        self.logger = logger
        self.channels = ["local", "seamm"]

        self._initialize()

    def __str__(self):
        """Print the conda information in a nice format."""
        if self.is_installed:
            return json.dumps(self._data, indent=4, sort_keys=True)
        else:
            return "Conda does not appear to be installed!"

    @property
    def environments(self):
        """The available conda environments."""
        if self.is_installed:
            result = []
            for env in self._data["envs"]:
                if env == self.root_prefix:
                    result.append("base")
                else:
                    path = Path(env)
                    if path.name == "miniconda":
                        # Windows is different.
                        result.append("base")
                    else:
                        result.append(path.name)
            return result
        else:
            return None

    @property
    def is_installed(self):
        """Whether we have access to conda."""
        return self._is_installed

    @property
    def prefix(self):
        """The path for the conda root."""
        if self.is_installed:
            return self._data["conda_prefix"]
        else:
            return None

    @property
    def root_prefix(self):
        """The root prefix of the conda installation."""
        if self.is_installed:
            return self._data["root_prefix"]
        else:
            return None

    def activate(self, environment):
        """Activate the requested environment."""
        if not self.is_installed:
            raise RuntimeError("Conda is not installed.")
        if not self.exists(environment):
            raise ValueError(f"Conda environment '{environment}' does not exist.")

        # Set the various environment variables that 'conda activate' does
        if "CONDA_SHLVL" in os.environ:
            level = int(os.environ["CONDA_SHLVL"])
            os.environ[f"CONDA_PREFIX_{level}"] = os.environ["CONDA_PREFIX"]
            level += 1
            os.environ["CONDA_SHLVL"] = str(level)
        os.environ["CONDA_PROMPT_MODIFIER"] = f"({environment})"

        path = os.environ["PATH"].split(os.pathsep)
        if level == 1:
            path.insert(0, str(self.path(environment) / "bin"))
        elif level >= 2:
            path[0] = str(self.path(environment) / "bin")
        os.environ["PATH"] = os.pathsep.join(path)

        os.environ["CONDA_PREFIX"] = str(self.path(environment))
        os.environ["CONDA_DEFAULT_ENV"] = environment

    def _initialize(self):
        """Get the information about the current Conda installation."""
        command = "conda info --json"
        try:
            result = subprocess.check_output(
                command, shell=True, text=True, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"Calling conda, returncode = {e.returncode}")
            self.logger.debug(f"Output:\n\n{e.output}\n\n")

            self._is_installed = False
            self._data = None
            return

        self._is_installed = True
        self._data = json.loads(result)
        tmp = "\n\t".join(self.environments)
        self.logger.info(f"environments:\n\t{tmp}")

    def create_environment(self, environment_file, name=None, force=False):
        """Create a Conda environment.

        Parameters
        ----------
        environment_file : str or pathlib.Path
            The name or path to the environment file.
        name : str = None
            The name of the environment. Defaults to that given in the
            environment file.
        force : bool = False
            Whether to overwrite an existing environment.
        """
        if isinstance(environment_file, Path):
            path = str(environment_file)
        else:
            path = environment_file

        command = f"conda env create --file '{path}'"
        if force:
            command += " --force"
        if name is not None:
            command += f" --name '{name}'"
        self.logger.debug(f"command = {command}")
        try:
            self._execute(command)
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Calling conda, returncode = {e.returncode}")
            self.logger.warning(f"Output:\n\n{e.output}\n\n")
            self._initialize()
            raise
        self._initialize()

    def exists(self, environment):
        """Whether an environment exists.

        Parameters
        ----------
        environment : str
           The name of the environment.

        Returns
        -------
        bool
            True if the environment exists, False otherwise.
        """
        return environment in self.environments

    def install(self, package, environment=None):
        """Install a package in an environment..

        Parameters
        ----------
        package: strip
            The package to install.
        environment : str
            The name of the environment to list, defaults to the current.
        """
        command = "conda install "
        if environment is not None:
            command += f" --name '{environment}'"
        command += f" {package}"

        self.execute(command)

    def list(self, environment=None, query=None):
        """The contents of an environment.

        Parameters
        ----------
        environment : str
            The name of the environment to list, defaults to the current.
        query: str
            Regexp for package names, default to all packages

        Returns
        -------
        dict
            A dictionary keyed by the package names.
        """
        command = "conda list --json"
        if environment is not None:
            command += f" --name '{environment}'"
        if query is not None:
            command += f" '{query}'"

        self.logger.debug(f"command = {command}")

        try:
            result, stdout, stderr = self._execute(command)
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Calling conda, returncode = {e.returncode}")
            self.logger.warning(f"Output:\n\n{e.output}\n\n")
            raise

        return {x["name"]: x for x in json.loads(stdout)}

    def path(self, environment):
        """The path for an environment.

        Parameters
        ----------
        environment : str
            The name of the environment to remove.

        Returns
        -------
        pathlib.Path
            The path to the environment.
        """
        if environment == "base":
            return Path(self.root_prefix)
        else:
            for env in self._data["envs"]:
                if env != self.root_prefix:
                    path = Path(env)
                    if environment == path.name:
                        return path
        raise ValueError(f"Environment '{environment}' not found.")

    def remove_environment(self, environment):
        """Remove an existing environment.

        Parameters
        ----------
        environment : str
            The name of the environment to remove.
        """
        command = f"conda env remove --name '{environment}' --yes --json"
        try:
            self._execute(command)
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Calling conda, returncode = {e.returncode}")
            self.logger.warning(f"Output:\n\n{e.output}\n\n")

            self._initialize()
            raise
        self._initialize()

    def search(self, query=None, channels=None, override_channels=True):
        """Run conda search, returning a dictionary of packages.

        Parameters
        ----------
        query: str = None
            The pattern to search, Defaults to None, meaning all packages.
        channels: [str] = None
            A list of channels to search. defaults to the list in self.channels.
        override_channels: bool = True
            Ignore channels configured in .condarc and the default channel.

        Returns
        -------
        dict
            A dictionary of packages, with versions for each.
        """
        command = "conda search --json"
        if override_channels:
            command += " --override-channels"
        if channels is None:
            for channel in self.channels:
                command += f" -c {channel}"
        else:
            for channel in channels:
                command += f" -c {channel}"
        if query is not None:
            command += f" {query}"

        result = self._execute(command)

        return json.loads(result[1])

    def uninstall(self, package, environment=None):
        """Uninstall a package from an environment..

        Parameters
        ----------
        package: str
            The package to uninstall install.
        environment : str
            The name of the environment to list, defaults to the current.
        """
        command = "conda uninstall "
        if environment is not None:
            command += f" --name '{environment}'"
        command += f" {package}"

        self.execute(command)

    def update_environment(self, environment_file, name=None):
        """Update a Conda environment.

        Parameters
        ----------
        environment_file : str or pathlib.Path
            The name or path to the environment file.
        name : str = None
            The name of the environment. Defaults to the current environment.
        """
        if isinstance(environment_file, Path):
            path = str(environment_file)
        else:
            path = environment_file

        command = f"conda env update --file '{path}'"
        if name is not None:
            command += f" --name '{name}'"
        self.logger.debug(f"command = {command}")
        try:
            self._execute(command)
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Calling conda, returncode = {e.returncode}")
            self.logger.warning(f"Output:\n\n{e.output}\n\n")
            raise

    def _execute(self, command, poll_interval=2):
        """Execute the command as a subprocess.

        Parameters
        ----------
        command : str
            The command, with any arguments, to execute.
        poll_interval : int
            Time interval in seconds for checking for output.
        """
        self.logger.info(f"running '{command}'")
        args = shlex.split(command)
        process = subprocess.Popen(
            args,
            bufsize=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        n = 0
        stdout = ""
        stderr = ""
        while True:
            self.logger.debug("    checking if finished")
            result = process.poll()
            if result is not None:
                self.logger.info(f"    finished! result = {result}")
                break
            try:
                self.logger.debug("    calling communicate")
                output, errors = process.communicate(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                self.logger.debug("    timed out")
                print(".", end="")
                n += 1
                if n >= 50:
                    print("")
                    n = 0
                sys.stdout.flush()
            else:
                if output != "":
                    stdout += output
                    self.logger.debug(output)
                if errors != "":
                    stderr += errors
                    self.logger.debug(f"stderr: '{errors}'")
        print("")
        return result, stdout, stderr
