import json
import logging
from copy import deepcopy

import functions_framework
import google.cloud.logging
from werkzeug.exceptions import BadRequest

from lib.correlate_logs import (
    FilterTooBigError,
    NoEntriesError,
    find_entries,
    get_state_from_url,
    parse_gcp_logs_url,
)

logs_client = google.cloud.logging.Client()
logs_client.setup_logging(log_level=logging.DEBUG)

logger = logging.getLogger(__name__)


NO_ENTRIES_RESPONSE_JSON = {
    "status": "ok",
    "msg": "Could not find any log entries",
    "data": None,
}


@functions_framework.errorhandler(BadRequest)
def handle_bad_request(e):
    response = e.get_response()

    resp_msg = e.description
    resp_data = {
        "status": "error",
        "msg": resp_msg,
        "data": {"code": e.code, "name": e.name},
    }
    logger.info(f"RESP: {resp_msg}", extra={"json_fields": resp_data})

    response.data = json.dumps(resp_data)
    response.content_type = "application/json"
    return response, 400


@functions_framework.http
def correlate_logs(request):
    req_data = request.get_json()
    logger.info("REQ: post body", extra={"json_fields": req_data})

    url = req_data.get("url")
    # or
    prev_state = req_data.get("prevSearchState")
    prev_url = req_data.get("prevUrl")

    if not (url or (prev_state and prev_url)):
        raise BadRequest("Missing required param(s)")

    (url_params, url_qs) = parse_gcp_logs_url(url or prev_url)

    if url:
        try:
            prev_state = get_state_from_url(url_params, url_qs)

        except ValueError as err:
            raise BadRequest("Incorrect DateTime format") from err
        except KeyError as err:
            raise BadRequest("Missing query param") from err
        except FilterTooBigError as err:
            raise BadRequest(err.message) from err

        except NoEntriesError:
            logger.info(
                f"RESP: {NO_ENTRIES_RESPONSE_JSON['msg']}",
                extra={"json_fields": NO_ENTRIES_RESPONSE_JSON["data"]},
            )
            return NO_ENTRIES_RESPONSE_JSON

    try:
        (resp_msg, resp_data) = find_entries(prev_state, url_params, url_qs)
    except FilterTooBigError:
        return {
            "status": "error",
            "msg": "Computed filter is too big for GCP Logging API.",
            "data": None,
        }

    resp_data_logged = deepcopy(resp_data)
    resp_data_logged.update(logEntries=[])
    logger.info(f"RESP: {resp_msg}", extra={"json_fields": resp_data_logged})

    return {
        "status": "ok",
        "msg": resp_msg,
        "data": resp_data,
    }
