#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import logging
import os
import sys

if __package__ is None and __name__ == "__main__":
    usage = [
        "Error: This script must be used in the context of a Python module.",
        "Hint: Run `./scripts/repl` instead.",
    ]
    print("\n\n".join(usage), file=sys.stderr)
    sys.exit(1)

# imports from within our package and  from vendor dirs must be after the `if`
# block above due to package semantics with `__init__.py`.
#
# pylint: disable=wrong-import-position
import IPython
from dotenv import dotenv_values, load_dotenv
from google.appengine.api import apiproxy_stub_map
from google.appengine.api.datastore_file_stub import DatastoreFileStub
from google.appengine.api.memcache.memcache_stub import MemcacheServiceStub
from google.appengine.api.taskqueue.taskqueue_stub import TaskQueueServiceStub
from google.appengine.api.urlfetch_stub import URLFetchServiceStub

try:
    from add_lib_paths import gae_sdk_path

    # before we import the `DatastoreGrpcStub`, we need to inject the bundled grpc
    # lib into `sys.path` so it's available. still not entirely sure the grpc path
    # is not included in the paths added by `dev_appserver.fix_sys_path()`. see
    # <gae_sdk_path>/wrapper_util.py for the logic.
    #
    sys.path.append("{}/lib/grpcio-1.20.0".format(gae_sdk_path))
    #
    # now we can safely import the stub.
    from google.appengine.tools.devappserver2.datastore_grpc_stub import (  # noqa:E402
        DatastoreGrpcStub,
    )
except ImportError:
    # CLEANUP: figure out how to get Datastore functional under Py3
    logging.warning(
        "Proceeding without Datastore GPRC stub; Unable to connect to instance."
    )


# pylint: enable=wrong-import-position


def print_env(env):
    if not env:
        return

    print(">> Using env vars from .env:")
    print("")
    for k in sorted(env.keys()):
        print('   {}="{}"'.format(k, env[k]))
    print("")


def repl():
    # use .env file to override Settings, thereby avoiding datastore calls
    load_dotenv()

    # output parsed env vars so it's clear we're using them
    print_env(dotenv_values())

    # configure the key service stubs
    apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
    apiproxy_stub_map.apiproxy.RegisterStub("urlfetch", URLFetchServiceStub())
    apiproxy_stub_map.apiproxy.RegisterStub("memcache", MemcacheServiceStub())
    apiproxy_stub_map.apiproxy.RegisterStub("taskqueue", TaskQueueServiceStub())

    # taskqueue = apiproxy_stub_map.apiproxy.GetStub("taskqueue")

    # if DATASTORE_EMULATOR_HOST is not set, we just use the in-memory stub,
    # which lets us explore models.
    dse_host = os.getenv("DATASTORE_EMULATOR_HOST")
    datastore_stub = (
        DatastoreGrpcStub(dse_host)
        if dse_host
        else DatastoreFileStub(os.getenv("APPLICATION_ID"), None)
    )
    apiproxy_stub_map.apiproxy.RegisterStub("datastore", datastore_stub)

    print(
        ">> Patched urlfetch, memcache, datastore, and taskqueue "
        "for use outside App Engine"
    )
    print("")

    # pre-import a few more modules for convenience
    #
    # pylint: disable=unused-import,unused-variable, import-outside-toplevel
    import logging  # noqa:F401
    import unittest  # noqa:F401
    from pprint import pprint  # noqa:F401

    from google.appengine.ext import ndb  # noqa:F401

    print(">> Already-imported modules: os, sys, logging, unittest, ndb, pprint")
    print("")

    log_level = os.getenv("LOG_LEVEL", "debug").upper()
    logging.getLogger().setLevel(log_level)

    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
    logging.getLogger("google_auth_httplib2").setLevel(logging.INFO)
    logging.getLogger("google.appengine.tools.appengine_rpc").setLevel(logging.INFO)
    logging.getLogger("oauth2client.client").setLevel(logging.WARNING)
    logging.getLogger("oauth2client.transport").setLevel(logging.WARNING)

    IPython.embed()


if __name__ == "__main__":
    try:
        repl()
    except Exception as e:
        print("Error: {} ({})".format(e, e.__class__.__name__), file=sys.stderr)
        sys.exit(1)

    sys.exit(0)
