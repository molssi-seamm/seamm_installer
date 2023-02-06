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
    "lammps-step",
    "loop-step",
    "mopac-step",
    "packmol-step",
    "psi4-step",
    "quickmin-step",
    "rdkit-step",
    "read-structure-step",
    "set-cell-step",
    "strain-step",
    "supercell-step",
    "table-step",
)
external_plug_ins = []

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
    "rinohtype",
    "seamm-cookiecutter",
    "sphinx-copybutton",
    "sphinx-rtd-theme",
    "pystemmer",
)
