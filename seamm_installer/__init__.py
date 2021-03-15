# -*- coding: utf-8 -*-

"""
seamm_installer
The installer/updater for SEAMM.
"""

# Bring up the classes so that they appear to be directly in
# the seamm_installer package.

from seamm_installer.conda import Conda  # noqa: F401
from seamm_installer.configuration import Configuration  # noqa: F401
from seamm_installer.installer_base import InstallerBase  # noqa: F401
from seamm_installer.pip import Pip  # noqa: F401
from seamm_installer.seamm_installer import SEAMMInstaller  # noqa: F401

# Handle versioneer
from ._version import get_versions

__author__ = """Paul Saxe"""
__email__ = "psaxe@molssi.org"
versions = get_versions()
__version__ = versions["version"]
__git_revision__ = versions["full-revisionid"]
del get_versions, versions
