import json
import logging
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta
from textwrap import dedent
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import google.cloud.logging
import jq

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# if/when we set log level to debug, urllib3.connectionpool gets rather noisy,
# so raise its log level a bit.
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

LOGS_CLIENT = google.cloud.logging.Client()

CURRENT_PATH = os.path.abspath(os.path.dirname(__file__))
JQ_FILTER_FILE = "gcp_logs_filter.jq"
JQ_FILTER_PATH = os.path.join(CURRENT_PATH, JQ_FILTER_FILE)
JQ_FIND_FILE = "gcp_logs_find.jq"
JQ_FIND_PATH = os.path.join(CURRENT_PATH, JQ_FIND_FILE)

jq_filter = jq.compile(open(JQ_FILTER_PATH, "r").read())
jq_find = jq.compile(open(JQ_FIND_PATH, "r").read())

LOG_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_DATETIME_WINDOW = timedelta(minutes=10)  # minutes, +/-

# assuming P means "past"
# T only seems present for "time" (HMS)
PAST_DATETIME_REGEX = r"^PT?(\d+)([WDHMS])$"  # weeks,days,hours,minutes,seconds

GCP_LOGS_URL_BASE = "https://console.cloud.google.com/logs/query"
DEFAULT_GCP_PROJECT = "gen-prod"

TRUNCATION_CONFIG = "true:28:end"
DEFAULT_SUMMARY_FIELDS = [
    "resource/labels/module_id",
    "resource/labels/version_id",
    "trace",
    "protoPayload/taskQueueName",
    "protoPayload/taskName",
]
DEFAULT_LFE_CUSTOM_FIELDS = [
    "resource/labels/module_id",
    "resource/labels/version_id",
    "protoPayload/status",
    "protoPayload/taskQueueName",
    "protoPayload/taskName",
]


# key = url param; value = timedelta arg
TIME_RANGE_MAP = {
    "W": "weeks",
    "D": "days",
    "H": "hours",
    "M": "minutes",
    "S": "seconds",
}

MAX_ITERATIONS = 16
MAX_LOG_ENTRIES = 700
MAX_FILTER_SIZE = 20000  # characters


class FilterTooBigError(Exception):
    def __init__(self, *args):
        msg = f"Query is longer than {MAX_FILTER_SIZE} characters!"
        logger.warning(msg)
        super().__init__(msg, *args)


class NoEntriesError(Exception):
    pass


def pretty_json(data):
    return json.dumps(data, indent=2)


def format_gcp_time(dt):
    return dt.isoformat(timespec="milliseconds") + "Z"


def parse_gcp_datetime(dt_str):
    # remove milli-/micro-/pico-seconds because the resolution appears to vary
    # depending on the context. the datetime is also easier to read without such
    # fine resolution.
    #
    # NOTE: our default "window" should take care of ensuring we don't lose any
    # log entries as the result of (effectively) rounding-down the end time.
    #
    # CLEANUP: do this parsing a bit more safely. also, round-up the time.
    dt_str_simple = f"{dt_str.split('.')[0]}Z"

    return datetime.strptime(dt_str_simple, LOG_DATETIME_FORMAT) if dt_str else None


def get_entry_datetime(entry):
    return parse_gcp_datetime(entry.get("timestamp"))


def round_datetime(dt, down=False):
    if down:
        return dt.replace(microsecond=0)

    return (dt + timedelta(seconds=1)).replace(microsecond=0)


def expand_datetime_window(start_iso_dt, end_iso_dt, window=DEFAULT_DATETIME_WINDOW):
    start_dt = parse_gcp_datetime(start_iso_dt) - window
    end_dt = parse_gcp_datetime(end_iso_dt) + window

    return (round_datetime(start_dt, down=True), round_datetime(end_dt))


def update_state_datetimes(state, start_dt, end_dt):
    new_state = deepcopy(state)
    new_state.update(
        timeRangeStart=format_gcp_time(start_dt),
        timeRangeEnd=format_gcp_time(end_dt),
    )
    return new_state


def state_time_range(state):
    return (state["timeRangeStart"], state["timeRangeEnd"])


def create_datetime_window_filter(start_dt, end_dt):
    return (
        dedent(
            """
        timestamp>="%s"
        timestamp<="%s"
        """
        )
        % (
            format_gcp_time(start_dt),
            format_gcp_time(end_dt),
        )
    )


def datetime_window_filter(start_iso_dt, end_iso_dt):
    return (
        dedent(
            """
        timestamp>="%s"
        timestamp<="%s"
        """
        )
        % (start_iso_dt, end_iso_dt)
    )


def add_datetime_window_to_query(query, time_range):
    if time_range:
        query += create_datetime_window_filter(*time_range)

    return query


def sum_sets(set1, set2):
    return sorted(list(set(set1 + set2)))


def encode_time_range(start_dt, end_dt):
    return quote_slash(f"{start_dt}/{end_dt}")


def decode_query(value):
    return value.replace("%28", "(").replace("%29", ")")


def encode_query(value):
    return quote_slash(value).replace("(", "%28").replace(")", "%29")


def decode_summary_fields(value):
    parts = value.split(":")

    # ignoring truncation because we don't really need it.
    return [unquote(f) for f in parts[0].split(",")]


def encode_fields(fields):
    return ",".join(quote_slash(f) for f in fields)


def quote_slash(value):
    return quote(value, safe="")


def preview_entries(entries):
    return [entries[0], entries[-1]] if entries else None


# ---


def parse_gcp_logs_url(url):
    params = {}

    parsed_url = urlparse(url)

    for p in parsed_url.params.split(";"):
        if not p:
            continue

        k, v = p.split("=")
        v = unquote(v)

        # some fields need special processing. we ignore special handling of
        # cursorTimestamp for now because we don't need it.
        if k == "query":
            v = decode_query(v)

        elif k == "timeRange":
            v = parse_datetime_range(v)

        elif k in ["lfeCustomFields", "summaryFields"]:
            v = decode_summary_fields(v)

        params[k] = v

    query = parse_qs(parsed_url.query)

    return params, query


def parse_datetime_range(value):
    end_dt = datetime.utcnow()

    if value is None:
        start_dt = end_dt - timedelta(hours=1)
        logger.info("Missing timeRange value; using past hour")
        return (start_dt, end_dt)

    # first try "past" datetime
    matches = re.match(PAST_DATETIME_REGEX, value)
    if matches:
        time_range = matches.group(1)
        time_scale = matches.group(2)

        props = {TIME_RANGE_MAP[time_scale]: int(time_range)}

        start_dt = end_dt - timedelta(**props)

        return (start_dt, end_dt)

    # then try explicit start/end time (both optional)
    try:
        # 2022-11-10T20:51:36.027Z/2022-11-17T20:51:36.027Z
        # 2022-11-10T20:51:36.027Z/
        # /2022-11-17T20:51:36.027Z
        (start_ts, end_ts) = value.split("/")

    # CLEANUP: this feels a bit lazy. what other values could we really be
    # dealing with at this point?
    except Exception as err:
        raise ValueError("Invalid timeRange param") from err

    return (parse_gcp_datetime(start_ts), parse_gcp_datetime(end_ts))


def get_state_from_url(url_params, url_qs):
    logs_query = add_datetime_window_to_query(
        url_params["query"],
        # timeRange may not be present
        url_params.get("timeRange"),
    )

    logger.info("Extracted logs query from provided URL...\n%s", logs_query)

    log_entries = query_logs(logs_query)
    if not log_entries:
        raise NoEntriesError

    return extract_search_state_from_log_entries(log_entries)


def gcp_logs_url(logs_filter, time_range, url_params=None, url_query=None):
    params = {
        "query": encode_query(logs_filter),
        "timeRange": encode_time_range(*time_range),
        "summaryFields": f"{encode_fields(DEFAULT_SUMMARY_FIELDS)}:{TRUNCATION_CONFIG}",
        "lfeCustomFields": encode_fields(DEFAULT_LFE_CUSTOM_FIELDS),
    }

    params_str = ";".join([f"{k}={v}" for k, v in params.items()])

    # CLEANUP: there's gotta be a better way to do this.
    try:
        project = url_query.get("project")[0]
    except (AttributeError, IndexError, TypeError):
        project = DEFAULT_GCP_PROJECT

    query = {
        "project": project,
    }

    return f"{GCP_LOGS_URL_BASE};{params_str}?{urlencode(query)}"


# ---

# these state keys values do not make sense to sum, so they are just copied
STATE_KEYS_COPY = ["project", "timeRangeStart", "timeRangeEnd"]

# these keys do make sense to sum; we also want to include found values in the
# summed state
STATE_KEYS_TRACK_FOUND = [
    "tasks",
    "traces",
    "pubSubMessageIds",
    "posts",
    "recipes",
    "recipeCollections",
]


def sum_search_states(state1, state2):
    new_state = {}

    # logger.debug("state1", extra={ "json_fields": state1})
    # logger.debug("state2", extra={ "json_fields": state2})

    # get all keys from both states
    all_keys = list(set(list(state1.keys()) + list(state2.keys())))

    for k in all_keys:
        if k in STATE_KEYS_COPY:
            new_state[k] = state2[k]
            continue

        # ignore keys added as part of the logic below
        if k.endswith("Found") or k.endswith("New"):
            continue

        curr = state1.get(k, [])
        found = (
            sum_sets(state2.get(k) or [], state2.get(f"{k}Found") or [])
            if k in STATE_KEYS_TRACK_FOUND
            else state2.get(k, [])
        )

        new_state[k] = sum_sets(curr, found)
        new_state[f"{k}New"] = [f for f in found if f not in curr]

    return new_state


def extract_search_state_from_log_entries(log_entries):
    return jq_find.input(log_entries).first()


def create_logs_filter_from_search_state(state, exclude_insert_ids=True):
    new_state = deepcopy(state)

    if exclude_insert_ids:
        # exclude known insertIds to reduce response overhead. this introduces
        # complexity with merging state, but it's needed.
        new_state.update(insertIds=[])

    return json.loads(jq_filter.input(new_state).text())


# ---


def query_for_log_entries(query):
    return [e.to_api_repr() for e in LOGS_CLIENT.list_entries(filter_=query)]


def query_logs(query):
    if len(query) > MAX_FILTER_SIZE:
        raise FilterTooBigError

    entries = query_for_log_entries(query)
    logger.debug(
        f"Query returned {len(entries)} entries...\n",
        extra={"json_fields": preview_entries(entries)},
    )

    if len(entries) >= MAX_LOG_ENTRIES:
        logger.warning(
            f"Number of log entries received ({len(entries)}) exceeds "
            f"limit ({MAX_LOG_ENTRIES})!"
        )

    return entries


# ---


class LogsQueryInput:
    def __init__(self, state):
        self.state = state

        logger.debug("Preparing logs query from state", extra={"json_fields": state})
        self.filter = create_logs_filter_from_search_state(
            state, exclude_insert_ids=False
        )

        # a query is a filter with a datetime window
        self.query = self.filter + datetime_window_filter(*state_time_range(state))
        logger.info("Logs query (%s chars):\n%s", len(self.query), self.query)


class LogsQueryResult:
    def __init__(self, entries):
        if not entries:
            raise NoEntriesError

        self.entries = entries
        self.entries_count = len(entries)

        self.state = extract_search_state_from_log_entries(entries)

        # use first/last entries as next time range, expanding with default
        # window to find even more entries
        self.state = update_state_datetimes(
            self.state,
            *expand_datetime_window(
                self.entries[0]["timestamp"],
                self.entries[-1]["timestamp"],
                # provide a tighter window so the view is zoomed in
                window=timedelta(minutes=1),
            ),
        )


# ---


def find_entries(state, url_params=None, url_qs=None):
    # expand given datetime window and round microseconds
    input_state = deepcopy(state)
    input_state = update_state_datetimes(
        input_state, *expand_datetime_window(*state_time_range(input_state))
    )

    try:
        query_result = LogsQueryResult(query_logs(LogsQueryInput(input_state).query))
    except NoEntriesError:
        query_result = None

    resp_entries = query_result.entries if query_result else []
    resp_state = (
        sum_search_states(input_state, query_result.state)
        if query_result
        else deepcopy(state)
    )

    resp_filter = create_logs_filter_from_search_state(resp_state)
    resp_url = gcp_logs_url(
        resp_filter, state_time_range(resp_state), url_params, url_qs
    )

    resp_msg = f"Found {len(resp_entries)} log entries"
    resp_data = {
        "searchState": resp_state,
        "filter": resp_filter,
        "logEntries": resp_entries,
        "logEntryCount": len(resp_entries),
        "url": resp_url,
    }

    return (resp_msg, resp_data)
