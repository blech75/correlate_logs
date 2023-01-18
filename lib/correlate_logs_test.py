import unittest
from datetime import datetime

from freezegun import freeze_time

from .correlate_logs import (
    GCP_LOGS_URL_BASE,
    gcp_logs_url,
    parse_datetime_range,
    parse_gcp_datetime,
    parse_gcp_logs_url,
    sum_search_states,
)


def mock_dt():
    return datetime.now()


def mock_query():
    return "foo"


class ParseTimeRangeTest(unittest.TestCase):
    def test_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_datetime_range("foo")

    def test_parses_days(self):
        mock_end_date = datetime(2020, 6, 8, 12, 00, 00)
        mock_start_date = datetime(2020, 6, 1, 12, 00, 00)

        with freeze_time(mock_end_date.isoformat()):
            start_dt, end_dt = parse_datetime_range("PT7D")

            self.assertEqual(end_dt, mock_end_date)
            self.assertEqual(start_dt, mock_start_date)

    def test_parses_hours(self):
        mock_end_date = datetime(2020, 6, 1, 12, 00, 00)
        mock_start_date = datetime(2020, 6, 1, 4, 00, 00)

        with freeze_time(mock_end_date.isoformat()):
            start_dt, end_dt = parse_datetime_range("PT8H")

            self.assertEqual(end_dt, mock_end_date)
            self.assertEqual(start_dt, mock_start_date)

    def test_parses_minutes(self):
        mock_end_date = datetime(2020, 6, 1, 12, 00, 00)
        mock_start_date = datetime(2020, 6, 1, 11, 45, 00)

        with freeze_time(mock_end_date.isoformat()):
            start_dt, end_dt = parse_datetime_range("PT15M")

            self.assertEqual(end_dt, mock_end_date)
            self.assertEqual(start_dt, mock_start_date)

    def test_parses_seconds(self):
        mock_end_date = datetime(2020, 6, 1, 12, 00, 00)
        mock_start_date = datetime(2020, 6, 1, 11, 59, 30)

        with freeze_time(mock_end_date.isoformat()):
            start_dt, end_dt = parse_datetime_range("PT30S")

            self.assertEqual(end_dt, mock_end_date)
            self.assertEqual(start_dt, mock_start_date)

    def test_parses_start_end_dates(self):
        mock_end_date = datetime(2020, 6, 1, 12, 00, 00)
        mock_start_date = datetime(2020, 6, 1, 11, 59, 30)

        start_dt, end_dt = parse_datetime_range(
            "2020-06-01T11:59:30.000Z/2020-06-01T12:00:00.000Z"
        )

        self.assertEqual(end_dt, mock_end_date)
        self.assertEqual(start_dt, mock_start_date)

    def test_parses_start_date(self):
        mock_start_date = datetime(2020, 6, 1, 11, 59, 30)

        start_dt, end_dt = parse_datetime_range("2020-06-01T11:59:30.000Z/")

        self.assertEqual(start_dt, mock_start_date)
        self.assertIsNone(end_dt)

    def test_parses_end_date(self):
        mock_end_date = datetime(2020, 6, 1, 12, 00, 00)

        start_dt, end_dt = parse_datetime_range("/2020-06-01T12:00:00.000Z")

        self.assertEqual(end_dt, mock_end_date)
        self.assertIsNone(start_dt)


class ParseGcpLogsUrlTest(unittest.TestCase):
    def test_returns_empty_params_for_simple_url(self):
        url = "http://foo/bar"
        (params, _) = parse_gcp_logs_url(url)
        self.assertDictEqual(params, {})

    def test_returns_empty_params_for_simple_url_with_semicolon(self):
        url = "http://foo/bar;"
        (params, _) = parse_gcp_logs_url(url)
        self.assertDictEqual(params, {})

    def test_parses_query_with_missing_value(self):
        url = "http://foo/bar;query="
        (params, _) = parse_gcp_logs_url(url)
        self.assertEqual(len(params), 1)
        self.assertEqual(params["query"], "")

    def test_parses_simple_query(self):
        url = "http://foo/bar;query=foo%3D%22bar%22"
        (params, _) = parse_gcp_logs_url(url)
        self.assertEqual(params["query"], 'foo="bar"')

    def test_parses_query_with_parens(self):
        url = "http://foo/bar;query=%2528foo%3D%22bar%22%2529"
        (params, _) = parse_gcp_logs_url(url)
        self.assertEqual(
            params["query"],
            '(foo="bar")',
        )

    def test_parses_query_with_linebreaks(self):
        url = "http://foo/bar;query=%0Afoo%3D%22bar%22%0A"
        (params, _) = parse_gcp_logs_url(url)
        self.assertEqual(params["query"], '\nfoo="bar"\n')

    def test_parses_query_with_logfile_retains_escaped_chars(self):
        url = "http://foo/bar;query=log_name%3D%22projects%2Fgen-prod%2Flogs%2Fappengine.googleapis.com%252Frequest_log%22"  # noqa:E501
        (params, _) = parse_gcp_logs_url(url)
        self.assertEqual(
            params["query"],
            'log_name="projects/gen-prod/logs/appengine.googleapis.com%2Frequest_log"',
        )

    def test_parses_summary_fields(self):
        url = "http://foo/bar;summaryFields=resource%252Flabels%252Fmodule_id,trace:true:28:end"  # noqa:E501
        (params, _) = parse_gcp_logs_url(url)
        self.assertEqual(
            params["summaryFields"],
            ["resource/labels/module_id", "trace"],
        )

    def test_parses_lfe_custom_fields(self):
        url = "http://foo/bar;lfeCustomFields=protoPayload%252FtaskQueueName"
        (params, _) = parse_gcp_logs_url(url)
        self.assertEqual(
            params["lfeCustomFields"],
            ["protoPayload/taskQueueName"],
        )

    def test_parses_time_range(self):
        url = "http://foo/bar;timeRange=2022-11-29T16:00:00.000Z%2F2022-11-29T16:05:00.000Z"  # noqa:E501
        (params, _) = parse_gcp_logs_url(url)
        self.assertEqual(
            params["timeRange"],
            (
                parse_gcp_datetime("2022-11-29T16:00:00.000Z"),
                parse_gcp_datetime("2022-11-29T16:05:00.000Z"),
            ),
        )

    def test_parses_project_from_query_string(self):
        url = "http://foo/bar;foo=bar?project=baz-quux"
        (_, query) = parse_gcp_logs_url(url)
        self.assertEqual(query["project"], ["baz-quux"])


class CreateLogsUrlFromFilterTest(unittest.TestCase):
    def test_foo(self):
        url = gcp_logs_url(
            mock_query(),
            (mock_dt(), mock_dt()),
            {},
            {"foo": ["bar"]},
        )
        self.assertTrue(url.startswith, GCP_LOGS_URL_BASE)


class SumSearchStatesTest(unittest.TestCase):
    def test_foo_found_not_added(self):
        state1 = {"foo": ["1", "2", "3"]}
        state2 = {
            "foo": ["1", "2"],
            "fooFound": ["3"],
        }

        actual = sum_search_states(state1, state2)
        expected = {
            "foo": ["1", "2", "3"],
            "fooNew": [],
        }
        self.assertEqual(actual, expected)

    def test_tasks_found_added(self):
        state1 = {"tasks": ["1", "2"]}
        state2 = {
            "tasks": ["1", "2"],
            "tasksFound": ["3"],
        }

        actual = sum_search_states(state1, state2)
        expected = {
            "tasks": ["1", "2", "3"],
            "tasksNew": ["3"],
        }
        self.assertEqual(actual, expected)

    def test_tasks_found_not_added(self):
        state1 = {"tasks": ["1", "2", "3"]}
        state2 = {
            "tasks": ["1", "2"],
            "tasksFound": ["3"],
        }

        actual = sum_search_states(state1, state2)
        expected = {
            "tasks": ["1", "2", "3"],
            "tasksNew": [],
        }
        self.assertEqual(actual, expected)
