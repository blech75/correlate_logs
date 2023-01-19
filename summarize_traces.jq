def getProtoPayloadEntries($entries): $entries | map(select(has("protoPayload")));
def getLogMessagesFromProtoPayload($entries): $entries | [.[].protoPayload] | map(select(has("line"))) | [.[].line[].logMessage];
def getStructuredLogEntries($entries): $entries | map(select(has("jsonPayload")));
def getPubSubMessagesFromJsonPayload($entries): $entries | [.[].jsonPayload] | map(select(has("pubSubMessage")));
def filterSortUnique($entries): $entries | map(select(. != null)) | sort | unique;
#
def parseTimestampToNs($ts): (($ts[0:19] + "Z" | fromdateiso8601) * 1000) + ($ts[20:26] | tonumber) / 1000 | round;
def duration($s;$e): (parseTimestampToNs($e) - parseTimestampToNs($s)) / 1000;
def formatTraceId($entry): ($entry.trace // "null") | split("/")[-1];
#
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
      parentTraces: $logMessages | map(capture("trace:(?<id>[^;]+)"; "g") | .id) | filterSortUnique(.) |  map(split("/")[-1]),
      posts: $logMessages | map(capture("post:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
      recipes: $logMessages | map(capture("recipe:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
      recipeCollections: $logMessages | map(capture("recipeCollection:(?<id>\\d+)"; "g") | .id) | filterSortUnique(.),
    }
  };

# ----

with_entries(.value |= summarizeTraceEntries(.))
