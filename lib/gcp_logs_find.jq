# python2 log entries
def getProtoPayloadEntries($entries): $entries | map(select(has("protoPayload")));
def getLogMessagesFromProtoPayload($entries): $entries | [.[].protoPayload] | map(select(has("line"))) | [.[].line[].logMessage];
#
# structured log entries
def getStructuredLogEntries($entries): $entries | map(select(has("jsonPayload")));
def getPubSubMessagesFromJsonPayload($entries): $entries | [.[].jsonPayload] | map(select(has("pubSubMessage")));
#
# helper func
def filterSortUnique($entries): $entries | map(select(. != null)) | sort | unique;

# ----

{
  # standard attribute; we need to know which project we're querying, so just
  # use the project of the first entry for now. should we ever have multiple
  # projects in a query, we will need to revisit this and a slew of other things.
  project: .[0].resource.labels.project_id,
  #
  # these values get "expanded" via expand_datetime_window()
  timeRangeStart: .[0].timestamp,
  timeRangeEnd: .[-1].timestamp,
  #
  # find the following standard attrs in the current set of query results. these
  # will be added to the current search state to accumulate values as we go.
  #
  # insertIds are 1:1 with a log enttry. once found, they are excluded from
  # future queries.
  insertIds: [.[].insertId] | filterSortUnique(.),
  #
  # operations and traces are 1:many with a long entry. including these in a
  # query may yield more log entries. once we use them in one query, we don't
  # need them in future queries
  operations: [.[].operation] | map(select(has("first") | not)) | [.[].id] | filterSortUnique(.),
  traces: [.[].trace] | filterSortUnique(.) | map(split("/")[-1]),
  #
  # separate out the different types of log entries once, to avoid doing it
  # multiple times in the next step.
  legacyAppEngineLogEntries: getProtoPayloadEntries(.),
  structuredLogEntries: getStructuredLogEntries(.)
} |

(. + {
  # add log messages
  logMessages: getLogMessagesFromProtoPayload(.legacyAppEngineLogEntries)
}) |

{
  # carry-through values from above
  project: .project,
  insertIds: .insertIds,
  timeRangeStart: .timeRangeStart,
  timeRangeEnd: .timeRangeEnd,
  operations: .operations,
  tasks: .tasks,
  traces: .traces,
  #
  #
  # we don't need legacyAppEngineLogEntries or structuredLogMessages (raw data)
  # in the final state.
  #
  #
  # ### extract standard values
  #
  requestIds: [.legacyAppEngineLogEntries[].protoPayload.requestId] | filterSortUnique(.),
  #
  #
  # ### extract "custom" values from structured logs
  #
  # we can efficiently query for pubsub log messages by their message_id
  pubSubMessageIds: getPubSubMessagesFromJsonPayload(.structuredLogEntries) | [.[].pubSubMessage.message_id] | filterSortUnique(.),
  #
  #
  # ### parse log messages to find more log messages
  #
  # now we need to parse log messages to find known strings that can help us to
  # correlate the current set of log entries to other yet-to-be-found log
  # entries. these entries/values are output courtesy of helper methods in
  # lib_gen.
  #
  # CLEANUP: maybe nest under "found" key?
  #
  # these found values may not be present in the current (or accumulated) set of
  # log entries. we specifically want to expand the next logs query to include
  # search for these newly-found values via standard log message attributes.
  tasksFound: .logMessages | map(capture("task:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
  tracesFound: .logMessages | map(capture("trace:(?<id>[^;]+)"; "g") | .id) | filterSortUnique(.) |  map(split("/")[-1]),
  # foundTraces: (.traces + (
  #   .logMessages | map(capture("trace:(?<id>[^;]+)"; "g") | .id) | map(split("/")[-1])
  # )) | filterSortUnique(.),
  pubSubMessageIdsFound: .logMessages | map(capture("msgid:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
  #
  #
  # ### parse log messages to find domain objects
  #
  # same as above, but these attrs are so we know which domain objects are
  # implicated in the log entries.
  posts: [],
  recipes: [],
  recipeCollections: [],
  postsFound: .logMessages | map(capture("post:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
  recipesFound: .logMessages | map(capture("recipe:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
  recipeCollectionsFound: .logMessages | map(capture("recipeCollection:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.)
}
