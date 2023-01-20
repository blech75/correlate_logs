module {
  desc: "summarizes all traces' log entries via key domain object info and counts of other log data.",
  input: "object(keys: str(<trace id>); values: array(object(<log entry>)))",
  returns: "object(keys: str(<trace id>); values: array(object()))"
};

include "utils";

# ----

def summarizeTraceEntries($entries):
  getStructuredLogEntries($entries) as $structuredLogEntries |
  getProtoPayloadEntries($entries) as $protoPayloadEntries |
  getLogMessagesFromProtoPayload($protoPayloadEntries) as $logMessages |
  getPubSubMessagesFromJsonPayload($structuredLogEntries) | [.[].pubSubMessage.message_id] | filterSortUnique(.) as $pubSubMessageIds |
  [$protoPayloadEntries[].protoPayload.requestId] | filterSortUnique(.) as $requestIds |
  [$protoPayloadEntries[].protoPayload.taskName] | filterSortUnique(.) as $taskIds |
  ($entries | min_by(.timestamp) | .timestamp) as $timeRangeStart |
  ($entries | max_by(._timestampEnd) | ._timestampEnd) as $timeRangeEnd |

  {
    $timeRangeStart,
    $timeRangeEnd,
    timeRangeDuration: duration($timeRangeStart; $timeRangeEnd),
    #
    services: $entries | map(.resource.labels.module_id) | filterSortUnique(.),
    logEntryCount: $entries | length,
    requestIdCount: $requestIds | length,
    $requestIds,
    $taskIds,
    $pubSubMessageIds,
    #
    found: {
      deferredTasks: $logMessages | map(capture("task:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
      parentTraces: $logMessages | map(capture("trace:(?<id>[^;]+)"; "g") | .id) | filterSortUnique(.) |  map(formatTraceId(.)),
      posts: $logMessages | map(capture("post:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
      recipes: $logMessages | map(capture("recipe:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
      recipeCollections: $logMessages | map(capture("recipeCollection:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
    }
  };

# ----

with_entries(.value |= summarizeTraceEntries(.))
