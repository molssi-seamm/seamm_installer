# -*- coding: utf-8 -*-

"""Metadata about packages, etc."""

core_packages = (
    "molsystem",
    "reference-handler",
    "seamm",
    "seamm-dashboard",
    "seamm-datastore",
    "seamm-ff-util",
    "seamm-installer",
    "seamm-jobserver",
    "seamm-thermochemistry",
    "seamm-util",
    "seamm-widgets",
)
molssi_plug_ins = (
    "control-parameters-step",
    "crystal-builder-step",
    "custom-step",
    "dftbplus-step",
    "forcefield-step",
    "geometry-analysis-step",
    "from-smiles-step",
    "gaussian-step",
    "lammps-step",
    "loop-step",
    "mopac-step",
    "nwchem-step",
    "packmol-step",
    "psi4-step",
    "qcarchive-step",
    "quickmin-step",
    "rdkit-step",
    "read-structure-step",
    "set-cell-step",
    "strain-step",
    "supercell-step",
    "torchani-step",
    "table-step",
    "thermal-conductivity-step",
)
external_plug_ins = []
# Packages that install()/services.py handle directly (their own dedicated
# Conda environment, not the shared main one; no Zenodo package-registry
# entry) rather than through the generic install_packages()/per-package
# Installer machinery. See install.py's install_seamm_webui().
standalone_packages = ("seamm-webui",)

excluded_plug_ins = (
    "chemical-formula",
    "cms-plots",
    "seamm-dashboard-client",
    "seamm-cookiecutter",
    "cassandra-step",
    "solvate-step",
)
development_packages = (
    "black",
    "codecov",
    "flake8",
    "nodejs",
    "pydata-sphinx-theme",
    "pytest",
    "pytest-cov",
    "pygments",
    "sphinx",
    "sphinx-design",
    "twine",
    "watchdog",
)
development_packages_pip = (
    "build",
    "seamm-cookiecutter",
    "sphinx-copybutton",
)
