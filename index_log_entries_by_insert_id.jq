module {
  desc: "creates an index of insert IDs with their associated log entry",
  input: "array(object(<log entry>))",
  returns: "object(keys: str(<insert ID>); values: object(<log entry)"
};

# ----

# CLEANUP: a better way to do this?
group_by(.insertId)

| reduce .[] as $entries ({}; . + {
  ($entries[0].insertId): $entries[0]
})
