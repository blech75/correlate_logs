#!/usr/bin/env python

"""Thin wrapper for coverage, so we can control which python version runs coverage.

CLEANUP: investigate if required or advantageous for py3
"""

from __future__ import absolute_import, division, print_function

from coverage import __main__  # noqa:F401
