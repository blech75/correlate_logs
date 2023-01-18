#!/usr/bin/env python

"""a thin wrapper around `python -m unittest discover test` with the added
benefit of measuring each test's speed and summarizing the slow tests after the
run.

shamelessly ripped from https://hakibenita.com/timing-tests-in-python-for-fun-and-profit
and adapted for our use.

used by our main test runner, `./scripts/test`, but also callable directly via
`python -m scripts.test`.
"""

from __future__ import absolute_import, print_function

import argparse
import os
import sys
import time
import unittest
from collections import namedtuple

if __package__ is None and __name__ == "__main__":
    usage = [
        (
            "Error: This script must be used in the context of a Python module. "
            "See `python -m scripts.test -h` for full usage."
        ),
        "Hint: Run `./scripts/test` instead.",
    ]
    print("\n\n".join(usage), file=sys.stderr)
    sys.exit(1)


PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# add the project path so we can access the `add_lib_paths` module. always
# check if it's there before we add because we don't want to mess up the
# delicate path order.
if PROJECT_PATH not in sys.path:
    sys.path.append(PROJECT_PATH)

# CLEANUP: WIP abstraction to deal with packages, which are slightly different
# from services.
PACKAGE_PATH = PROJECT_PATH

# defined in 'test' (wrapper script)
TARGET_DIR = os.getenv("TARGET_DIR", "test")

# dir where our tests live. passed to `unittest.TestLoader().discover()`.
TEST_PATH = os.path.join(PACKAGE_PATH, TARGET_DIR)

# defined in 'test' (wrapper script)
TEST_FILE_PATTERN = os.getenv("TEST_FILE_PATTERN", "test_*.py")

# CLEANUP: consider dynamically adjusting SLOW_TEST_THRESHOLD if we're running
# via `coverage` because everything runs slower.
SLOW_TEST_THRESHOLD = 0.5  # seconds, as float
SLOWEST_COUNT = 3  # num of tests to list if all are fast

# nice for readability; not entirely necessary
TestTiming = namedtuple("TestTiming", ["name", "elapsed"])


class TimeLoggingTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        self.timings = []

        super(TimeLoggingTestResult, self).__init__(*args, **kwargs)

    def startTest(self, test):
        self._test_started_at = time.time()

        super(TimeLoggingTestResult, self).startTest(test)

    def addSuccess(self, test):
        elapsed = time.time() - self._test_started_at
        name = self.getDescription(test)
        self.timings.append(TestTiming(name=name, elapsed=elapsed))

        super(TimeLoggingTestResult, self).addSuccess(test)


def format_slow_tests(hdr, tests):
    lines = [hdr, "-" * len(hdr)]

    for t in tests:
        lines.append("{:.2f}s {}".format(t.elapsed, t.name))

    return "\n".join(lines)


def summarize_slow_tests(test_result):
    test_timings = sorted(test_result.timings, key=lambda t: t.elapsed, reverse=True)

    slow_tests = [t for t in test_timings if t.elapsed > SLOW_TEST_THRESHOLD]

    if slow_tests:
        return format_slow_tests(
            "Slow Tests (> {}s)".format(SLOW_TEST_THRESHOLD),
            slow_tests,
        )

    msg = (
        'Congratulations! All tests are "fast enough" (< {}s). '
        "For further speed improvement, you might consider optimizing the "
        "following tests."
    ).format(SLOW_TEST_THRESHOLD)

    return "\n".join(
        [
            msg,
            "",
            format_slow_tests(
                "Top {} Slowest Tests".format(SLOWEST_COUNT),
                test_timings[0:SLOWEST_COUNT],
            ),
        ]
    )


def run_tests(names=None, verbosity=1):
    # magic, part 1: custom result class
    runner = unittest.TextTestRunner(
        resultclass=TimeLoggingTestResult, verbosity=verbosity
    )

    test_loader = unittest.TestLoader()
    tests = (
        test_loader.loadTestsFromNames(names)
        if names
        else test_loader.discover(
            TEST_PATH,
            top_level_dir=PACKAGE_PATH,
            pattern=TEST_FILE_PATTERN,
        )
    )

    result = runner.run(tests)

    # magic, part 2: summarizing and writing results to stream
    runner.stream.writeln("")
    runner.stream.writeln(summarize_slow_tests(result))

    return result.wasSuccessful()


def cli():
    parser = argparse.ArgumentParser(
        description="Simple test runner with slow test summary."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose test output (shows test names)",
    )
    parser.add_argument(
        "names",
        metavar="NAME",
        type=str,
        nargs="*",
        help=(
            "One ore more Python dotted-name notations for test target. "
            "(e.g. test.test_main, genservice.foo_test)"
        ),
    )

    args = parser.parse_args()

    verbosity = 2 if args.verbose else 1

    # allows ctrl-c to cause graceful exit
    unittest.installHandler()

    return run_tests(names=args.names, verbosity=verbosity)


if __name__ == "__main__":
    try:
        tests_passed = cli()
        status = int(not tests_passed)
    except Exception as e:
        print("Error: {} ({})".format(e, e.__class__.__name__), file=sys.stderr)
        status = 1

    sys.exit(status)
