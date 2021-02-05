#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `seamm_installer` package."""

import pytest  # noqa: F401
import seamm_installer  # noqa: F401


def test_construction():
    """Just create an object and test its type."""
    result = seamm_installer.SeammInstaller()
    assert str(type(result)) == (
        "<class 'seamm_installer.seamm_inst.SeammInstaller'>"  # noqa: E501
    )
