#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `seamm_installer` package."""

import pytest  # noqa: F401
import seamm_installer  # noqa: F401


def test_construction():
    """Just create an object and test its type."""
    result = seamm_installer.SEAMMInstaller()
    assert str(type(result)) == (
        "<class 'seamm_installer.seamm_installer.SEAMMInstaller'>"  # noqa: E501
    )


def test_is_installed():
    """Test whether Conda is installed."""
    installer = seamm_installer.SEAMMInstaller()
    assert installer.conda.is_installed


def test_environments():
    """Test that we can get the environments."""
    installer = seamm_installer.SEAMMInstaller()
    assert installer.conda.environments[0] == "base"
