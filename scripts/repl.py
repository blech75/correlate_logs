#!/usr/bin/env python3

from __future__ import print_function

import sys

import IPython
from dotenv import dotenv_values, load_dotenv

if __package__ is None:
    print(
        "The REPL must be run from the project root via `./scripts/repl`",
        file=sys.stderr,
    )
    sys.exit(1)


def print_env(env):
    if not env:
        return

    print(">> Using env vars from .env:")
    print("")
    for k, v in env.items():
        print('   {}="{}"'.format(k, v))
    print("")


def repl():
    # use .env file to override Settings, thereby avoiding datastore calls
    load_dotenv()

    # output parsed env vars so it's clear we're using them
    print_env(dotenv_values())

    # pre-import a few more modules for convenience
    #
    # pylint: disable=unused-import,unused-variable, import-outside-toplevel
    import logging  # noqa:F401
    import unittest  # noqa:F401
    from pprint import pprint  # noqa:F401

    print(">> Already-imported modules: os, sys, logging, unittest, pprint")
    print("")

    IPython.embed()


if __name__ == "__main__":
    repl()
    # try:
    #     repl()
    # except Exception as e:
    #     print("Error: {} ({})".format(e, e.__class__.__name__), file=sys.stderr)
    #     sys.exit(1)

    sys.exit(0)
