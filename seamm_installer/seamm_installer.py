# -*- coding: utf-8 -*-

"""Non-graphical part of the SEAMM Installer
"""

import json
import logging
from pathlib import Path
import pkg_resources
import shlex
import shutil
import subprocess
import sys
import textwrap

from tabulate import tabulate

from .conda import Conda
from .pip import Pip
import seamm_installer

logger = logging.getLogger(__name__)

core_packages = (
    'seamm', 'seamm-jobserver', 'seamm-util', 'seamm-widgets', 'seamm-ff-util',
    'molsystem', 'reference-handler'
)
exclude_plug_ins = ('seamm-cookiecutter', 'cassandra-step', 'solvate-step')


class SEAMMInstaller(object):
    """
    The non-graphical part of a SEAMM Installer.

    Attributes
    ----------

    """

    def __init__(self, seamm='seamm'):
        """The installer/updater for SEAMM.

        Parameters
        ----------
        logger : logging.Logger
            The logger for debug and other output.
        """
        logger.debug('Creating SEAMM Installer {}'.format(self))

        self.options = None
        self._seamm_environment = seamm
        self._conda = Conda()
        self._pip = Pip()

    @property
    def version(self):
        """The semantic version of this module."""
        return seamm_installer.__version__

    @property
    def git_revision(self):
        """The git version of this module."""
        return seamm_installer.__git_revision__

    @property
    def conda(self):
        """The Conda object."""
        return self._conda

    @property
    def pip(self):
        """The Pip object."""
        return self._pip

    @property
    def seamm_environment(self):
        """The Conda environment for SEAMM."""
        return self._seamm_environment

    @seamm_environment.setter
    def seamm_environment(self, value):
        self._seamm_environment = value

    def check(self, *modules, yes=False):
        """Check the requested modules.

        Parameters
        ----------
        *modules: [str]
            A list of modules to install. May be 'all', 'core', or 'plug-ins'
            to request either all modules, or just the core or plug-ins be
            installed.
        yes: bool
            Answer 'yes' to all prompts.
        **kwargs: dict(str, str)
            Other optional keyword arguments.
        """
        # See if Conda is installed
        if not self.conda.is_installed:
            print("Conda is not installed, so none of SEAMM is.")
            return

        # Activate the seamm environment, if it exists.
        if not self.conda.exists(self.seamm_environment):
            print(
                f"The '{self.seamm_environment}' Conda environment is not "
                "installed."
            )
            return
        self.conda.activate(self.seamm_environment)

        packages = self.find_packages()

        if 'all' in modules or 'core' in modules:
            print('')
            print('Checking the core packages of SEAMM:')
            for package in core_packages:
                if package == 'seamm':
                    # seamm has no installer, but is an executable
                    continue
                # See if the package has an installer
                installer = shutil.which(package)
                if installer is not None:
                    print(f"   Checking the installation for {package}")
                    if yes:
                        subprocess.run([installer, 'check', '--yes'])
                    else:
                        subprocess.run([installer, 'check'])
                    print("   Done.")

        if 'all' in modules or 'plug-ins' in modules or 'plugins' in modules:
            print('')
            print('Checking the plug-ins for SEAMM:')
            for package in packages:
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                installer = shutil.which(package)
                if installer is not None:
                    print(f"   Checking the installation for {package}.")
                    if yes:
                        subprocess.run([installer, 'check', '--yes'])
                    else:
                        subprocess.run([installer, 'check'])
                    print("   Done.")

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in ('core', 'plug-ins', 'plugins', 'all', 'seamm'):
                explicit.append(module)

        if len(explicit) > 0:
            print('')
            print('Checking the specified modules in SEAMM:')

            for package in explicit:
                if package not in packages:
                    print(f"    {package} is not installed.")
                else:
                    # See if the package has an installer
                    installer = shutil.which(package)
                    if installer is not None:
                        print(f"   Checking the installation for {package}.")
                        if yes:
                            subprocess.run([installer, 'check', '--yes'])
                        else:
                            subprocess.run([installer, 'check'])
                        print("   Done.")

    def find_packages(self):
        """Find the Python packages in SEAMM.

        Returns
        -------
        dict(str, str)
            A dictionary with information abut the packages.
        """
        # Use pip to find possible packages.
        packages = self.pip.search(query='SEAMM')

        # Need to add molsystem and reference-handler by hand
        for package in ('molsystem', 'reference-handler'):
            tmp = self.pip.search(query=package, exact=True)
            logger.debug(
                f"Query for package {package}\n"
                f"{json.dumps(tmp, indent=4, sort_keys=True)}\n"
            )
            if package in tmp:
                packages[package] = tmp[package]
        return packages

    def install(self, *modules, **kwargs):
        """Install the requested modules.

        Parameters
        ----------
        *modules: [str]
            A list of modules to install. May be 'all', 'core', or 'plug-ins'
            to request either all modules, or just the core or plug-ins be
            installed.
        **kwargs: dict(str, str)
            Other optional keyword arguments.
        """
        # See if Conda is installed
        if not self.conda.is_installed:
            print("Conda is not installed, so none of SEAMM is.")
            return

        # Activate the seamm environment, if it exists.
        if not self.conda.exists(self.seamm_environment):
            print(
                f"Installing the '{self.seamm_environment}' Conda environment."
                " This will take a minute or two."
            )
            # Get the path to seamm.yml
            path = Path(pkg_resources.resource_filename(__name__, 'data/'))
            logger.debug(f"data directory: {path}")
            self.conda.create_environment(
                path / 'seamm.yml', name=self.seamm_environment
            )
            print('')
            self.conda.activate(self.seamm_environment)
            packages = self.find_packages()
            for package in packages:
                print(f"   Installed {package}")
            print('')
        else:
            self.conda.activate(self.seamm_environment)
            packages = self.find_packages()
            if 'all' in modules or 'core' in modules:
                print('')
                print('Installing the core packages of SEAMM:')
                to_install = []
                for package in core_packages:
                    try:
                        version = self.pip.show(package)['version']
                    except Exception as e:
                        print(e)
                        if package in packages:
                            to_install.append(package)
                else:
                    if package in packages:
                        available = packages[package]['version']
                        v_installed = pkg_resources.parse_version(version)
                        v_available = pkg_resources.parse_version(available)
                        if v_installed < v_available:
                            to_install.append(package)

                for package in to_install:
                    print(f"   Installing {package}")
                    self.pip.install(package)

                    # See if the package has an installer
                    if package == 'seamm':
                        # seamm has no installer, but is an executable
                        continue
                    else:
                        installer = shutil.which(package)
                        if installer is not None:
                            subprocess.run([installer, 'install'])

        if 'all' in modules or 'plug-ins' in modules or 'plugins' in modules:
            print('')
            print('Installing all of the plug-ins for SEAMM:')
            for package in packages:
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                install = 'no'
                try:
                    version = self.pip.show(package)['version']
                except Exception:
                    install = 'full'
                else:
                    available = packages[package]['version']
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        to_install.append(package)
                    else:
                        # See if the package has an installer
                        if package == 'seamm':
                            # seamm has no installer, but is an executable
                            installer = None
                        else:
                            installer = shutil.which(package)
                        if installer is not None:
                            result = subprocess.run(
                                [installer, 'check', '--yes'],
                                text=True,
                                capture_output=True
                            )
                            if result.returncode == 0:
                                if 'need to install' in result.stdout:
                                    install = 'package installer'

                if install == 'full':
                    print(f"   Installing {package}")
                    self.pip.install(package)

                    # See if the package has an installer
                    if package == 'seamm':
                        # seamm has no installer, but is an executable
                        installer = None
                    else:
                        installer = shutil.which(package)
                    if installer is not None:
                        subprocess.run([installer, 'install'])
                elif install == 'package installer':
                    print(
                        f"   {package} is installed, but its installer needs "
                        "to be run"
                    )
                    if package == 'seamm':
                        # seamm has no installer, but is an executable
                        installer = None
                    else:
                        installer = shutil.which(package)
                    if installer is not None:
                        subprocess.run([installer, 'install'])

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in ('core', 'plug-ins', 'plugins', 'all'):
                explicit.append(module)

        if len(explicit) > 0:
            print('')
            print('Installing the specified modules in SEAMM:')

            for package in explicit:
                if package not in packages:
                    print(
                        f"Package '{package}' is not available for "
                        "installation."
                    )
                    continue

                install = 'no'
                try:
                    version = self.pip.show(package)['version']
                except Exception:
                    install = 'full'
                else:
                    # See if the package has an installer
                    if package == 'seamm':
                        # seamm has no installer, but is an executable
                        installer = None
                    else:
                        installer = shutil.which(package)
                    if installer is not None:
                        result = subprocess.run(
                            [installer, 'show'],
                            text=True,
                            capture_output=True
                        )
                        if result.returncode == 0:
                            if (
                                'need to install' in result.stdout or
                                'not configured' in result.stdout
                            ):
                                install = 'package installer'
                        else:
                            print(
                                "Encountered an error checking the "
                                f"installation for {package}: "
                                f"{result.returncode}"
                            )
                            print(f"\nstdout:\n{result.stdout}")
                            print(f"\nstderr:\n{result.stderr}")
                    available = packages[package]['version']
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        print(f"{package} is installed but should be updated.")
                    elif install == 'no':
                        print(f"{package} is already installed.")

                if install == 'full':
                    print(f"Installing {package}")
                    self.pip.install(package)

                    # See if the package has an installer
                    if package == 'seamm':
                        # seamm has no installer, but is an executable
                        installer = None
                    else:
                        installer = shutil.which(package)
                    if installer is not None:
                        subprocess.run([installer, 'install'])
                elif install == 'package installer':
                    if package == 'seamm':
                        # seamm has no installer, but is an executable
                        installer = None
                    else:
                        installer = shutil.which(package)
                    subprocess.run([installer, 'install'])

    def run(self):
        """Run the installer/updater
        """
        logger.debug('Entering run method of the SEAMM installer')

        # Process the conda environment
        self._handle_conda()
        self.conda.activate(self.seamm_environment)

        # Use pip to find possible packages.
        packages = self.pip.search(query='SEAMM')

        # Need to add molsystem and reference-handler by hand
        for package in ('molsystem', 'reference-handler'):
            tmp = self.pip.search(query=package, exact=True)
            logger.debug(
                f"Query for package {package}\n"
                f"{json.dumps(tmp, indent=4, sort_keys=True)}\n"
            )
            if package in tmp:
                packages[package] = tmp[package]

        # And see what the user wants to do with them
        self._handle_core(packages)
        self._handle_plugins(packages)

        print('All done.')

    def show(self, *modules, **kwargs):
        """Show the current status of the installation.

        Parameters
        ----------
        modules : [str]
            The modules to show, or 'all', 'core' or 'plug-ins'.
        """
        logger.debug('Entering run method of the SEAMM installer')
        logger.debug(f"    modules = {modules}")

        # See if Conda is installed
        if not self.conda.is_installed:
            print("Conda is not installed, so none of SEAMM is.")
            return

        # Activate the seamm environment, if it exists.
        if not self.conda.exists(self.seamm_environment):
            print(
                f"The '{self.seamm_environment}' Conda environment is not "
                "installed."
            )
            return
        self.conda.activate(self.seamm_environment)

        packages = self.find_packages()

        if 'all' in modules or 'core' in modules:
            print('')
            print('Showing the core packages of SEAMM:')
            data = []
            line_no = 1
            am_current = True
            for package in core_packages:
                try:
                    version = self.pip.show(package)['version']
                except Exception as e:
                    print(e)
                    if package in packages:
                        available = packages[package]['version']
                        description = packages[package]['description']
                        data.append(
                            [line_no, package, '--', available, description]
                        )
                        am_current = False
                    else:
                        data.append(
                            [line_no, package, '--', '--', 'not available']
                        )
                else:
                    if package in packages:
                        available = packages[package]['version']
                        description = packages[package]['description']
                        data.append(
                            [
                                line_no, package, version, available,
                                description
                            ]
                        )
                        v_installed = pkg_resources.parse_version(version)
                        v_available = pkg_resources.parse_version(available)
                        if v_installed < v_available:
                            am_current = False
                    else:
                        data.append(
                            [line_no, package, version, '--', 'not available']
                        )
                line_no += 1

            headers = [
                'Number', 'Package', 'Installed', 'Available', 'Description'
            ]
            print(tabulate(data, headers, tablefmt='fancy_grid'))
            if am_current:
                print("The core packages are up-to-date.")
            print('')
        if 'all' in modules or 'plug-ins' in modules or 'plugins' in modules:
            print('')
            print('Showing the plug-ins for SEAMM:')
            data = []
            am_current = True
            all_installed = True
            state = {}
            for package in packages:
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                if 'description' in packages[package]:
                    description = packages[package]['description'].strip()
                    description = textwrap.fill(description, width=50)
                else:
                    description = 'description unavailable'

                try:
                    version = self.pip.show(package)['version']
                except Exception:
                    if package in packages:
                        available = packages[package]['version']
                        data.append([package, '--', available, description])
                        all_installed = False
                        state[package] = 'not installed'
                    else:
                        data.append([package, '--', '--', 'not available'])
                        state[package] = 'not installed, not available'
                else:
                    if package in packages:
                        available = packages[package]['version']
                        v_installed = pkg_resources.parse_version(version)
                        v_available = pkg_resources.parse_version(available)
                        if v_installed < v_available:
                            am_current = False
                            state[package] = 'not up-to-date'
                        else:
                            state[package] = 'up-to-date'

                        # See if the package has an installer
                        installer = shutil.which(package)
                        if installer is not None:
                            result = subprocess.run(
                                [installer, 'show'],
                                text=True,
                                capture_output=True
                            )
                            if result.returncode == 0:
                                print(type(result.stdout))
                                print(result.stdout)
                                for line in result.stdout.splitlines():
                                    description += f"\n{line}"
                            else:
                                description += (
                                    f"\nThe installer for {package} "
                                    f"returned code {result.returncode}"
                                )
                                for line in result.stderr.splitlines():
                                    description += f"\n    {line}"
                        data.append([package, version, available, description])
                    else:
                        data.append([package, version, '--', 'not available'])
                        state[package] = 'installed, not available'

            # Sort by the plug-in names
            data.sort(key=lambda x: x[0])

            # And number
            for i, line in enumerate(data, start=1):
                line.insert(0, i)

            headers = [
                'Number', 'Plug-in', 'Installed', 'Available', 'Description'
            ]
            print('')
            print(tabulate(data, headers, tablefmt='fancy_grid'))
            if am_current:
                if all_installed:
                    print("The plug-ins are up-to-date.")
                else:
                    print(
                        "The installed plug-ins are up-to-date; however, not "
                        "all the plug-ins are installed"
                    )
                print('')
            else:
                if all_installed:
                    print("The plug-ins are not up-to-date.")
                else:
                    print(
                        "The plug-ins are not up-to-date and some are not "
                        "installed."
                    )

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in ('core', 'plug-ins', 'plugins', 'all'):
                explicit.append(module)

        if len(explicit) > 0:
            print('')
            print('Showing the specified modules in SEAMM:')
            data = []
            am_current = True
            state = {}
            for package in explicit:
                if package in packages and 'description' in packages[package]:
                    description = packages[package]['description'].strip()
                    description = textwrap.fill(description, width=50)
                else:
                    description = 'description unavailable'

                try:
                    version = self.pip.show(package)['version']
                except Exception:
                    if package in packages:
                        available = packages[package]['version']
                        data.append([package, '--', available, description])
                        am_current = False
                        state[package] = 'not installed'
                    else:
                        data.append([package, '--', '--', 'not available'])
                        state[package] = 'not installed, not available'
                else:
                    if package in packages:
                        available = packages[package]['version']
                        v_installed = pkg_resources.parse_version(version)
                        v_available = pkg_resources.parse_version(available)
                        if v_installed < v_available:
                            am_current = False
                            state[package] = 'not up-to-date'
                        else:
                            state[package] = 'up-to-date'

                        # See if the package has an installer
                        installer = shutil.which(package)
                        if installer is not None:
                            result = subprocess.run(
                                [installer, 'show'],
                                text=True,
                                capture_output=True
                            )
                            if result.returncode == 0:
                                for line in result.stdout.splitlines():
                                    description += f"\n{line}"
                            else:
                                description += (
                                    f"\nThe installer for {package} "
                                    f"returned code {result.returncode}"
                                )
                                for line in result.stderr.splitlines():
                                    description += f"\n    {line}"
                        data.append([package, version, available, description])
                    else:
                        data.append([package, version, '--', 'not available'])
                        state[package] = 'installed, not available'

            # Sort by the plug-in names
            data.sort(key=lambda x: x[0])

            # And number
            for i, line in enumerate(data, start=1):
                line.insert(0, i)

            headers = [
                'Number', 'Plug-in', 'Installed', 'Available', 'Description'
            ]
            print('')
            print(tabulate(data, headers, tablefmt='fancy_grid'))
            if am_current:
                print("The plug-ins are up-to-date.")
            print('')

    def uninstall(self, *modules, **kwargs):
        if 'all' in modules or 'core' in modules:
            print('')
            print('Core packages of SEAMM:')
        if 'all' in modules or 'plug-ins' in modules or 'plugins' in modules:
            print('')
            print('Plug-ins for SEAMM:')

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in ('core', 'plug-ins', 'plugins', 'all'):
                explicit.append(module)

        if len(explicit) > 0:
            print('')
            print('Uninstalling the specified modules in SEAMM:')

    def update(self, *modules, **kwargs):
        """Update the requested modules.

        Parameters
        ----------
        *modules: [str]
            A list of modules to install. May be 'all', 'core', or 'plug-ins'
            to request either all modules, or just the core or plug-ins be
            installed.
        **kwargs: dict(str, str)
            Other optional keyword arguments.
        """
        # See if Conda is installed
        if not self.conda.is_installed:
            print("Conda is not installed, so none of SEAMM is.")
            return

        # Activate the seamm environment, if it exists.
        if not self.conda.exists(self.seamm_environment):
            print(
                f"The '{self.seamm_environment}' Conda environment is not "
                "installed."
            )
            return
        self.conda.activate(self.seamm_environment)

        packages = self.find_packages()

        if 'all' in modules or 'core' in modules:
            print('')
            print('Updating the core packages of SEAMM:')
            for package in core_packages:
                try:
                    version = self.pip.show(package)['version']
                except Exception:
                    pass
            else:
                if package in packages:
                    available = packages[package]['version']
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        print(f"   Updating {package}")
                        self.pip.update(package)

                        # See if the package has an installer
                        installer = shutil.which(package)
                        if installer is not None:
                            subprocess.run([installer, 'update'])

        if 'all' in modules or 'plug-ins' in modules or 'plugins' in modules:
            print('')
            print('Plug-ins for SEAMM:')
            for package in packages:
                if package in core_packages:
                    continue

                if package in exclude_plug_ins:
                    continue

                try:
                    version = self.pip.show(package)['version']
                except Exception:
                    pass
                else:
                    available = packages[package]['version']
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        print(
                            f"   Updating {package} from {v_installed} to "
                            f"{v_available}."
                        )
                        self.pip.update(package)

                        # See if the package has an installer
                        installer = shutil.which(package)
                        if installer is not None:
                            print(
                                f"   Updating the installation for {package}."
                            )
                            subprocess.run([installer, 'update'])
                        print("    Done.")

        # Any modules given explicitly
        explicit = []
        for module in modules:
            if module not in ('core', 'plug-ins', 'plugins', 'all'):
                explicit.append(module)

        if len(explicit) > 0:
            print('')
            print('Updating the specified modules in SEAMM:')

            for package in explicit:
                if package not in packages:
                    print(
                        f"Package '{package}' is not available for "
                        "upgrading."
                    )
                    continue

                try:
                    version = self.pip.show(package)['version']
                except Exception:
                    pass
                else:
                    available = packages[package]['version']
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        print(
                            f"   Updating {package} from {v_installed} to "
                            f"{v_available}."
                        )
                        self.pip.update(package)

                        # See if the package has an installer
                        installer = shutil.which(package)
                        if installer is not None:
                            print(
                                f"   Updating the installation for {package}."
                            )
                            subprocess.run([installer, 'update'])
                        print("    Done.")

    def _execute(self, command, poll_interval=2):
        """Execute the command as a subprocess.

        Parameters
        ----------
        command : str
            The command, with any arguments, to execute.
        poll_interval : int
            Time interval in seconds for checking for output.
        """
        logger.info(f"running '{command}'")
        args = shlex.split(command)
        process = subprocess.Popen(
            args,
            bufsize=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        n = 0
        stdout = ''
        stderr = ''
        while True:
            logger.debug('    checking if finished')
            result = process.poll()
            if result is not None:
                logger.info(f"    finished! result = {result}")
                break
            try:
                logger.debug('    calling communicate')
                output, errors = process.communicate(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                logger.debug('    timed out')
                print('.', end='')
                n += 1
                if n >= 50:
                    print('')
                    n = 0
                sys.stdout.flush()
            else:
                if output != '':
                    stdout += output
                    logger.debug(output)
                if errors != '':
                    stderr += errors
                    logger.debug(f"stderr: '{errors}'")

        return result, stdout, stderr

    def _handle_conda(self):
        """Check the status of conda and do what is requested.
        """
        logger.debug('Handling the Conda installation.')
        conda = self.conda
        if not conda.is_installed:
            answer = input('Conda is not installed. Install it? [y]/n: ')
            if len(answer) > 0 and answer.lower()[0] == 'n':
                print('Will not install Conda, so am exiting.')
                return
            raise NotImplementedError()

        if conda.exists(self.seamm_environment):
            answer = input(
                f"The '{self.seamm_environment}' environment is installed. "
                "Do you want to remove it? y/[n]: "
            )
            if len(answer) > 0 and answer.lower()[0] == 'y':
                print(f"Removing the '{self.seamm_environment}' environment.")
                conda.remove_environment(self.seamm_environment)
                print('')

        if not conda.exists(self.seamm_environment):
            answer = input(
                f"Install the '{self.seamm_environment}' Conda environment? "
                "[y]/n: "
            )
            if len(answer) > 0 and answer.lower()[0] == 'n':
                print(
                    f"Will not install the '{self.seamm_environment}' Conda "
                    "environment, so will exit."
                )
                return

            print(
                f"Installing the '{self.seamm_environment}' Conda environment."
                " This will take a minute or two."
            )
            # Get the path to seamm.yml
            path = Path(pkg_resources.resource_filename(__name__, 'data/'))
            logger.debug(f"data directory: {path}")
            conda.create_environment(path / 'seamm.yml')
            print('')
        else:
            answer = input(
                f"Update the '{self.seamm_environment}' Conda environment? "
                "[y]/n: "
            )
            if len(answer) == 0 or answer.lower()[0] == 'y':
                print(
                    f"Updating the '{self.seamm_environment}' Conda "
                    "environment. This will take a minute or two."
                )
                # Get the path to seamm.yml
                path = Path(pkg_resources.resource_filename(__name__, 'data/'))
                logger.debug(f"data directory: {path}")
                conda.update_environment(
                    path / 'seamm.yml', name=self.seamm_environment
                )
                print('')

    def _handle_core(self, packages):
        """Prompt the user to install or update core modules, as needed."""
        print('')
        print('Core packages of SEAMM:')
        data = []
        line_no = 1
        am_current = True
        for package in core_packages:
            try:
                version = self.pip.show(package)['version']
            except Exception as e:
                print(e)
                if package in packages:
                    available = packages[package]['version']
                    description = packages[package]['description']
                    data.append(
                        [line_no, package, '--', available, description]
                    )
                    am_current = False
                else:
                    data.append(
                        [line_no, package, '--', '--', 'not available']
                    )
            else:
                if package in packages:
                    available = packages[package]['version']
                    description = packages[package]['description']
                    data.append(
                        [line_no, package, version, available, description]
                    )
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        am_current = False
                else:
                    data.append(
                        [line_no, package, version, '--', 'not available']
                    )
            line_no += 1

        headers = [
            'Number', 'Package', 'Installed', 'Available', 'Description'
        ]
        print(tabulate(data, headers, tablefmt='fancy_grid'))
        print('')

        if am_current:
            answer = input(
                'The core packages are up-to-date. Do you want to uninstall '
                'any? y/[n]: '
            )
            if len(answer) > 0 and answer.lower()[0] == 'y':
                action = 'uninstall'
            else:
                action = 'continue'
        else:
            answer = input(
                'Do you wish to r\u0332emove, i\u0332nstall, or u\u0332pdate '
                'selected packages or c\u0332ontinue on? r/i/u/c: '
            )

            action = 'continue'
            if len(answer) > 0:
                key = answer.lower()[0]
                if key == 'r':
                    action = 'uninstall'
                elif key == 'i':
                    action = 'install'
                elif key == 'u':
                    action = 'update'

        if action == 'uninstall':
            while True:
                answer = input(
                    "List the package numbers to uninstall, separated by "
                    "blanks, or 'all': "
                )

                to_uninstall = []
                for value in answer.split():
                    if value.isdecimal():
                        to_uninstall.append(int(value))
                    elif value.lower()[0] == 'a':
                        to_uninstall = list(range(1, len(core_packages) + 1))
                        break
                    else:
                        print(
                            "Please use numbers, separated by blanks, or 'all'"
                        )
                        print('')
                        continue

            for i in to_uninstall:
                package = core_packages[i]
                self.pip.uninstall(package)

    def _handle_plugins(self, packages):
        """Prompt the user to install or update plug-in modules, as needed."""
        print('')
        print('Plug-ins for SEAMM:')
        data = []
        am_current = True
        state = {}
        for package in packages:
            if package in core_packages:
                continue

            if package in exclude_plug_ins:
                continue

            if 'description' in packages[package]:
                description = textwrap.fill(
                    packages[package]['description'].strip(), width=50
                )
            else:
                description = 'description unavailable'

            try:
                version = self.pip.show(package)['version']
            except Exception:
                if package in packages:
                    available = packages[package]['version']
                    data.append([package, '--', available, description])
                    am_current = False
                    state[package] = 'not installed'
                else:
                    data.append([package, '--', '--', 'not available'])
                    state[package] = 'not installed, not available'
            else:
                if package in packages:
                    available = packages[package]['version']
                    data.append([package, version, available, description])
                    v_installed = pkg_resources.parse_version(version)
                    v_available = pkg_resources.parse_version(available)
                    if v_installed < v_available:
                        am_current = False
                        state[package] = 'not up-to-date'
                    else:
                        state[package] = 'up-to-date'
                else:
                    data.append([package, version, '--', 'not available'])
                    state[package] = 'installed, not available'

        # Sort by the plug-in names
        data.sort(key=lambda x: x[0])

        # And number
        for i, line in enumerate(data, start=1):
            line.insert(0, i)

        headers = [
            'Number', 'Plug-in', 'Installed', 'Available', 'Description'
        ]
        print('')
        print(tabulate(data, headers, tablefmt='fancy_grid'))
        print('')

        if am_current:
            answer = input(
                'The plug-ins are up-to-date. Do you want to uninstall '
                'any? y/[n]: '
            )
            if len(answer) > 0 and answer.lower()[0] == 'y':
                action = 'uninstall'
            else:
                action = 'continue'
        else:
            answer = input(
                'Do you wish to r\u0332emove, i\u0332nstall, or u\u0332pdate '
                'selected packages or c\u0332ontinue on? r/i/u/c: '
            )

            action = 'continue'
            if len(answer) > 0:
                key = answer.lower()[0]
                if key == 'r':
                    action = 'uninstall'
                elif key == 'i':
                    action = 'install'
                elif key == 'u':
                    action = 'update'

        if action == 'uninstall':
            ask_again = True
            while ask_again:
                answer = input(
                    "List the plug-in numbers to uninstall, separated by "
                    "blanks, or 'all': "
                )

                to_uninstall = []
                ask_again = False
                for value in answer.split():
                    if value.isdecimal():
                        to_uninstall.append(data[int(value) - 1][1])
                    elif value.lower()[0] == 'a':
                        to_uninstall = [
                            x[1]
                            for x in data
                            if 'not installed' not in state[x[1]]
                        ]
                        break
                    else:
                        print(
                            "Please use numbers, separated by blanks, or 'all'"
                        )
                        print('')
                        ask_again = True
                        continue

            for package in to_uninstall:
                print(f"   Uninstalling {package}")
                self.pip.uninstall(package)
        elif action == 'install':
            ask_again = True
            while ask_again:
                answer = input(
                    "List the plug-in numbers to install, separated by "
                    "blanks, or 'all': "
                )

                to_install = []
                ask_again = False
                for value in answer.split():
                    if value.isdecimal():
                        value = int(value)
                        package = data[value - 1][1]
                        if state[package] == 'not installed':
                            to_install.append(package)
                    elif value.lower()[0] == 'a':
                        to_install = [
                            x[1]
                            for x in data
                            if state[x[1]] == 'not installed'
                        ]
                        break
                    else:
                        print(
                            "Please use numbers, separated by blanks, or 'all'"
                        )
                        print('')
                        ask_again = True
                        continue

            for package in to_install:
                print(f"   Installing {package}")
                self.pip.install(package)

                # See if the package has an installer
                installer = shutil.which(package)
                if installer is not None:
                    print(f"{package} has an installer")
                    subprocess.run(installer)
        elif action == 'update':
            ask_again = True
            while ask_again:
                answer = input(
                    "List the plug-in numbers to update, separated by "
                    "blanks, or 'all': "
                )

                to_update = []
                ask_again = False
                for value in answer.split():
                    if value.isdecimal():
                        value = int(value)
                        package = data[value - 1][1]
                        to_update.append(package)
                    elif value.lower()[0] == 'a':
                        to_update = [x[1] for x in data]
                        break
                    else:
                        print(
                            "Please use numbers, separated by blanks, or 'all'"
                        )
                        print('')
                        ask_again = True
                        continue

            for package in to_update:
                print(f"   Updating {package}:")
                if state[package] == 'not up-to-date':
                    self.pip.update(package)

                # See if the package has an installer
                installer = shutil.which(f"{package}-installer")
                if installer is not None:
                    # print(f"{package} has an installer")
                    subprocess.run(installer, '--update')
                print('    up-to-date.')
