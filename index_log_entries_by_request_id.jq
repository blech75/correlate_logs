# ----

map(select(has("protoPayload"))) | group_by(.protoPayload.requestId) |
reduce .[] as $entries ({}; . + { ($entries[0].protoPayload.requestId): $entries | sort_by(.protoPayload.endTime) })
