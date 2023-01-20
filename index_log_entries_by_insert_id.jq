# ----

# CLEANUP: a better way to do this?
group_by(.insertId) |
reduce .[] as $entries ({}; . + {
  ($entries[0].insertId): $entries[0]
})
