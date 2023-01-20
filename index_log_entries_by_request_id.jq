module {
  desc: "creates an index of requests with their associated [protoPayload] log entries.",
  input: "array(object(<log entry>))",
  returns: "object(keys: str(<request ID>); values: array(object(<log entry))"
};

# ----

# only protoPayload entries contain request IDs.
map(select(has("protoPayload")))

| group_by(.protoPayload.requestId)

| reduce .[] as $entries ({}; . + {
  # sorting by endTime guarantees us that the last entry has the trace ID
  ($entries[0].protoPayload.requestId): $entries | sort_by(.protoPayload.endTime)
})
