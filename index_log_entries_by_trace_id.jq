module {
  desc: "creates an index of traces with their associated log entries",
  input: "array(object(<log entry>))",
  returns: "object(keys: str(<trace ID>); values: array(object(<log entry))"
};

include "utils";

# $logEntriesByRequestId is provided via `--argfile`. the -1 index to assumes
# the last entry contains a trace ID
def traceIdFromEntry($entry):
  $logEntriesByRequestId[$entry.operation.id][-1].trace | formatTraceId(.);

def addSortTime($entry):
  $entry + {
    # using underscore to indicate a 'private' field
    _timestampEnd: (if ($entry | has("protoPayload"))
      then $entry.protoPayload.endTime
      else $entry.timestamp
    end)
  };

# ----

group_by(.trace)

# create object with trace ID as key and entries as value. note this
# (temporarily) adds a "_" key for holding 'orphan entries' (those without a
# trace ID - something that happens when a single request is split across
# multiple log entries). we associate these orphan entries with their trace in
# the next step.
| reduce .[] as $entries ({}; . + {
  (formatTraceId($entries[0].trace // "_")): $entries
})

# iterate over orphan entries and look up their trace ID by correlating their
# operation ID (same as request ID) to an index of log entries by request ID.
| reduce ._[] as $nullEntry (.; . + {
  (traceIdFromEntry($nullEntry)): (
    # the array is likely a mix of .protoPayload and .jsonPayload entries, so
    # we can't sort them right now.
    .[traceIdFromEntry($nullEntry)] + [$nullEntry]
  )
})

# remove the temporary "_" key
| del(._)

# sort the entries by adding a consistent sort key (._timestampEnd)
| reduce keys[] as $traceId (.; . + {
  ($traceId): .[$traceId] | map(addSortTime(.)) | sort_by(._timestampEnd)
})
