# Get notified when a task graph fails

topics: tasks, alerts
tags: alerting, orchestration, webhook
level: intermediate

Two ways to hear about task failures: `ERROR_INTEGRATION` pushes a message to a cloud queue (SNS, Pub/Sub, Event Grid) for every failed run, and a finalizer task can post to Slack, Teams, or email when any task in the run failed.

```sql
USE SCHEMA my_db.pipelines;

-- Option A: push each failure to a cloud queue (set on the ROOT task only;
-- failed child tasks report through the root's integration)
ALTER TASK root_load SUSPEND;
ALTER TASK root_load SET ERROR_INTEGRATION = my_sns_error_int;   -- queue-type notification integration
ALTER TASK root_load RESUME;

-- Option B: finalizer that sends a webhook message if anything in this run failed
CREATE OR REPLACE TASK notify_on_failure
  WAREHOUSE = my_wh
  FINALIZE = root_load
AS
DECLARE
  failures STRING;
BEGIN
  SELECT LISTAGG(name || ': ' || COALESCE(error_message, state), '; ')
    INTO :failures
  FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
         SCHEDULED_TIME_RANGE_START => DATEADD('day', -1, CURRENT_TIMESTAMP())))
  WHERE graph_run_group_id = SYSTEM$TASK_RUNTIME_INFO('CURRENT_TASK_GRAPH_RUN_GROUP_ID')
    AND state IN ('FAILED', 'CANCELLED');

  IF (failures IS NOT NULL) THEN
    CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
      SNOWFLAKE.NOTIFICATION.TEXT_PLAIN(
        SNOWFLAKE.NOTIFICATION.SANITIZE_WEBHOOK_CONTENT('Pipeline root_load failed: ' || :failures)),
      SNOWFLAKE.NOTIFICATION.INTEGRATION('slack_alerts_int'));
  END IF;
END;

-- Resuming the root task does not resume children/finalizer; enable them together
SELECT SYSTEM$TASK_DEPENDENTS_ENABLE('my_db.pipelines.root_load');
```

## Notes
- Setting `ERROR_INTEGRATION` needs USAGE on the notification integration. With `TASK_AUTO_RETRY_ATTEMPTS > 0`, a notification is sent for every failed attempt.
- For an aggregate signal (error rate over a threshold) rather than per-failure messages, use the built-in TASKS_ERROR_RATE alert template, which needs `LOG_EVENT_LEVEL = INFO` on monitored tasks.
- The finalizer always runs after the graph finishes, whether it succeeded or failed. See the Slack webhook snippet for creating `slack_alerts_int`.
- The finalizer owner needs READ on the webhook secret and must be able to read the task history.

## References
- [Configure error alerts and notifications for tasks](https://docs.snowflake.com/en/user-guide/tasks-errors-integrate)
- [Create a sequence of tasks with a task graph](https://docs.snowflake.com/en/user-guide/tasks-graphs)
- [SYSTEM$TASK_RUNTIME_INFO](https://docs.snowflake.com/en/sql-reference/functions/system_task_runtime_info)
