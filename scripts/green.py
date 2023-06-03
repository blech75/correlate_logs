#!/usr/bin/env python

"""Thin wrapper for green, so we can modify the sys.path via scripts.__init__

CLEANUP: investigate if required or advantageous for py3
"""

from __future__ import absolute_import, division, print_function

import sys

from green.cmdline import main  # noqa:F401

sys.exit(main())
