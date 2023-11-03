=======
History
=======
2023.11.3 BugFix: Internal update due to changes for versioneer

2023.11.2 Bugfix: Fixed a crash casued by a minor change in the Zenodo API

2023.6.7 Bugfix: Ensuring the LaunchAgents directory exists on Mac

2023.4.2 Bugfix: Updating full conda environment breaks pinning.
   So removed that capability.
   
2023.4.1.1 Bugfix: Problem with JobServer service

2023.4.1 Bugfix: get latest version from Zenodo

2023.3.31.1 Switching to Zenodo
   * Getting the package list from Zenodo
   * Added ability to pin packages.

2023.3.31
   * Added new plug-in: QCArchive

2023.3.23
   * Added new plug-ins: Gaussian, TorchANI and NWChem
   * Updated creating the JobServer service to handle changes in the JobServer

2022.10.25
  Added QuickMin and ensured the Dashboard is included.
  Also hardened the code, handling more errors gracefully.
