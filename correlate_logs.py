#!/usr/bin/env python3

import argparse
import json
import logging
import sys
from copy import deepcopy

import coloredlogs
from dotenv import load_dotenv

from lib.correlate_logs import FilterTooBigError as FilterError
from lib.correlate_logs import (
    extract_search_state_from_log_entries,
    find_entries,
    pretty_json,
)

# init coloredlogs based on .env file
load_dotenv()
coloredlogs.auto_install()

logger = logging.getLogger(__name__)


class CliError(Exception):
    exit_status = 255
    msg = "Unknown Error"

    def __init__(self, *args):
        logger.error(self.msg)
        super().__init__(self.msg, *args)


class FilterTooBigError(CliError):
    exit_status = 8
    msg = "Input filter is too big."


class IdenticalSearchStateError(CliError):
    exit_status = 9
    msg = "Output state is same as input state."


class NoMoreEntriesError(CliError):
    exit_status = 10
    msg = "No log entries found with supplied query."


def read_json_file(f):
    return json.loads(open(f, "r").read())


def cli():
    parser = argparse.ArgumentParser(
        description="Find associated log entries from GCP logs JSON"
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-f", "--file", action="store", help="Filename for input JSON"
    )
    input_group.add_argument(
        "-i", "--stdin", action="store_true", help="Use stdin for input JSON"
    )

    format_group = parser.add_mutually_exclusive_group(required=True)
    format_group.add_argument(
        "-l", "--logs", action="store_true", help="treat input JSON as GCP logs"
    )
    format_group.add_argument(
        "-s", "--state", action="store_true", help="treat input JSON as search state"
    )

    args = parser.parse_args()

    input_filename = args.file or "stdin.json"
    input_file = open(args.file, "r") if args.file else sys.stdin
    input_json = json.loads(input_file.read())

    prev_search_state = (
        extract_search_state_from_log_entries(input_json)
        if args.logs
        else deepcopy(input_json)
    )

    if args.logs:
        in_state_file = input_filename.replace(".json", ".input-state.json")
        with open(in_state_file, "w") as f:
            print(pretty_json(prev_search_state), file=f)

    logger.debug(f"Using search state: {pretty_json(prev_search_state)}")
    try:
        (resp_msg, resp_data) = find_entries(prev_search_state)
    except FilterError as err:
        raise FilterTooBigError from err

    out_state_file = input_filename.replace(".json", ".resp.json")
    with open(out_state_file, "w") as f:
        print(pretty_json(resp_data), file=f)

    logger.info(resp_msg)

    # output search state to stdout so it can be redirected/saved however the
    # harness sees fit
    print(pretty_json(resp_data["searchState"]), file=sys.stdout)

    if resp_data["searchState"] == prev_search_state:
        raise IdenticalSearchStateError

    if not resp_data["logEntries"]:
        raise NoMoreEntriesError


if __name__ == "__main__":
    try:
        cli()
    except CliError as err:
        sys.exit(err.exit_status)
    except KeyboardInterrupt:
        sys.exit(1)

    sys.exit(0)
