# -*- coding: utf-8 -*-

"""
seamm_installer
The installer/updater for SEAMM.
"""

# Bring up the classes so that they appear to be directly in
# the seamm_installer package.

from seamm_installer.seamm_inst import SeammInstaller  # noqa: F401, E501
from seamm_installer.seamm_inst_parameters import SeammInstallerParameters  # noqa: F401, E501
from seamm_installer.seamm_inst_step import SeammInstallerStep  # noqa: F401, E501
from seamm_installer.tk_seamm_inst import TkSeammInstaller  # noqa: F401, E501

# Handle versioneer
from ._version import get_versions
__author__ = """Paul Saxe"""
__email__ = 'psaxe@molssi.org'
versions = get_versions()
__version__ = versions['version']
__git_revision__ = versions['full-revisionid']
del get_versions, versions
