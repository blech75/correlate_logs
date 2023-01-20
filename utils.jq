module {
  desc: "utility functions"
};

# ----

def getProtoPayloadEntries($entries):
  $entries
  | map(select(has("protoPayload")));

def getLogMessagesFromProtoPayload($entries):
  $entries
  | [.[].protoPayload]
  | map(select(has("line")))
  | [.[].line[].logMessage];

def getStructuredLogEntries($entries):
  $entries
  | map(select(has("jsonPayload")));

def getPubSubMessagesFromJsonPayload($entries):
  $entries
  | [.[].jsonPayload]
  | map(select(has("pubSubMessage")));

def filterSortUnique($entries):
  $entries
  | map(select(. != null))
  | sort
  | unique;

def parseTimestampToNs($ts):
  (
    (($ts[0:19] + "Z" | fromdateiso8601) * 1000) +
    ($ts[20:26] | tonumber)
  ) / 1000
  | round;

# using cryptic vars here because '$end' causes compilation issues
def duration($s;$e):
  (parseTimestampToNs($e) - parseTimestampToNs($s)) / 1000;

# only use the trailing ID from the trace string
def formatTraceId($entry): $entry | split("/")[-1];
