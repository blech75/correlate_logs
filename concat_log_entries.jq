module {
  desc: "concatenates log entries from multiple response files sorted by timestamp (requires -s arg)",
  input: "array(object(<response>))",
  returns: "array(object(<log entry))"

};

# ----

[.[].logEntries[]]

| sort_by(.timestamp)
