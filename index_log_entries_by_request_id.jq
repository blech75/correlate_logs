# ----

map(select(has("protoPayload"))) | group_by(.protoPayload.requestId) |
reduce .[] as $entries ({}; . + {
  # sorting by endTime guarantees us that the last entry has the trace ID
  ($entries[0].protoPayload.requestId): $entries | sort_by(.protoPayload.endTime)
})
