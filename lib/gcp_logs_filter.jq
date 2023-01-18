def toConditonal($entries): $entries | sort | unique | map(tojson) | join(" OR ");
def toRegexConditonal($entries): $entries | sort | unique | join("|");
def joinConditionsWithOr($entries):  $entries | join(" OR\n  ");

def operations($entries): if ($entries | length) > 0 then "operation.id=(\(toConditonal($entries)))" else null end;
def messageIds($entries): if ($entries | length) > 0 then "protoPayload.line.logMessage:(\(toConditonal($entries)))" else null end;
def messageIdsRegex($entries): if ($entries | length) > 0 then "protoPayload.line.logMessage=~\"msg:(\(toRegexConditonal($entries)))\"" else null end;
def jsonMessageIds($entries): if ($entries | length) > 0 then "jsonPayload.pubSubMessage.message_id=(\(toConditonal($entries)))" else null end;
def tasks($entries): if ($entries | length) > 0 then "protoPayload.taskName=(\(toConditonal($entries)))" else null end;
def traces($entries): if ($entries | length) > 0 then "trace=(\(toConditonal($entries)))" else null end;
def tracesRegex($entries): if ($entries | length) > 0 then "trace=~\"projects/\(.project)/traces/(\(toRegexConditonal($entries)))\"" else null end;
def insertIdsRegex($entries): if ($entries | length) > 0 then "-insertId=~\"(\(toRegexConditonal($entries)))\"" else null end;

{
  project: .project,
  #
  # insertIds are excluded, so we need to include ALL currently-known insertIds
  insertIds: .insertIds,
  #
  # newly-found traces will yield new log entries across all log types
  #
  # NOTE: sometimes the first found trace may be from a long-ago request, so it
  # won't appear in the time-restricted query. allow a little slack to bootstrap
  # our results
  # traces: (if (.traces | length) < 3 then .traces else .tracesNew end),
  traces: .traces,
  #
  # newly-found operations and tasks will yield new log entries
  requestLogConditions: [
    operations(.operationsNew),
    tasks(.tasksNew)
    #
    # CLEANUP: figure out if this is worth it or not. it feels like this should
    # not yield new log entries.
    #
    # messageIdsRegex(.pubSubMessageIdsNew),
  ] | map(select(. != null)),
  #
  appLogConditions: [
    # right now, pubsub message logs do not contain any parseable log messages,
    # so we're not including an expression for returning pubsub messages.
    #
    # jsonMessageIds(.pubSubMessageIdsNew)
  ] | map(select(. != null))
} |

"(
  " + tracesRegex(.traces) +

(if (.requestLogConditions | length) > 0 then "
  OR (
    \(joinConditionsWithOr(.requestLogConditions))
    log_name=\"projects/\(.project)/logs/appengine.googleapis.com%2Frequest_log\"
  )" else "" end) +

(if (.appLogConditions | length) > 0 then "
  OR (
    \(joinConditionsWithOr(.appLogConditions))
    log_name=\"projects/\(.project)/logs/app\"
  )" else "" end) +

"
)
" + (if (.insertIds | length) > 1 then insertIdsRegex(.insertIds) else "" end)
