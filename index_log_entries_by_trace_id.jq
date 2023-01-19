def formatTraceId($entry): ($entry.trace // "_") | split("/")[-1];

# the -1 index assumes the last entry contains a trace ID
def traceIdFromEntry($entry): $logEntriesByRequestId[$entry.operation.id][-1].trace | split("/")[-1];

def addSortTime($entry): $entry + {
  _timestampEnd: (if ($entry | has("protoPayload"))
    then $entry.protoPayload.endTime
    else $entry.timestamp
  end)
};

# ----


group_by(.trace)

# create object with trace ID as key and entries as value. note this
# (temporarily) adds a "_" key for holding entries without a trace ID.
| reduce .[] as $entries ({}; . + {
  (formatTraceId($entries[0])): $entries
})

# iterate over entries in "_" and look up their trace ID by correlating their
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
