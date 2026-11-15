# Alerts & Notifications

A Snowflake alert is a schema-level object that checks a SQL condition and runs an action when the condition is met, such as sending an email or writing to a table. Combined with notification integrations, alerts let you react automatically to cost spikes, failed pipelines or data quality problems instead of discovering them later.

## How it works

An alert has three parts:

- **Condition** – a SQL statement in `IF (EXISTS (...))`. The condition is met when the statement returns one or more rows.
- **Action** – a SQL statement that runs when the condition is met, often a call to a notification procedure.
- **Schedule or trigger** – when the condition is evaluated.

There are two types of alerts:

- **Alerts on a schedule** run every *n* minutes or on a CRON expression and evaluate the condition against all data.
- **Alerts on new data** have no SCHEDULE and run when new rows arrive in a table or view, evaluating only the new rows. The source must have change tracking enabled, the FROM clause can reference only one table, view or event table, and CTEs, joins, DML and stored procedure calls are not allowed in the condition.

**Compute.** An alert either uses a warehouse you specify or runs **serverless** if you omit `WAREHOUSE`. Serverless alerts require the EXECUTE MANAGED ALERT privilege, scale automatically (up to the equivalent of an XXLARGE warehouse), and are billed as a serverless feature. A warehouse-based alert incurs at least one minute of warehouse cost each time it runs, so serverless is often better for infrequent checks.

**Privileges.** Creating and running alerts requires the EXECUTE ALERT privilege on the account plus privileges on the schema, warehouse and queried objects.

**Lifecycle.** A new alert is **suspended by default**; you must run `ALTER ALERT ... RESUME`. You can set `SUSPEND_ALERT_AFTER_NUM_FAILURES` so an alert suspends itself after repeated failures.

**Notifications.** Actions usually send messages through a **notification integration** (email, cloud queues such as Amazon SNS, Azure Event Grid or Google Pub/Sub, or webhooks for tools like Slack or Teams). `SYSTEM$SEND_SNOWFLAKE_NOTIFICATION` sends a message through one or more integrations.

**Useful functions inside alerts:** `SNOWFLAKE.ALERT.SCHEDULED_TIME()` and `SNOWFLAKE.ALERT.LAST_SUCCESSFUL_SCHEDULED_TIME()` let a scheduled alert examine only the window since its last successful run, avoiding duplicate notifications. `SNOWFLAKE.ALERT.GET_CONDITION_QUERY_UUID()` gives the condition's query ID so the action can include its results via `RESULT_SCAN`.

## Example

Create an email notification integration (recipients must be verified users in the account):

```sql
CREATE NOTIFICATION INTEGRATION ops_email_int
  TYPE = EMAIL
  ENABLED = TRUE
  DEFAULT_RECIPIENTS = ('data-ops@example.com');
```

A serverless alert that checks hourly for failed tasks since the last successful run:

```sql
CREATE OR REPLACE ALERT ops.monitoring.failed_tasks_alert
  SCHEDULE = '60 MINUTE'
  IF (EXISTS (
    SELECT 1
    FROM TABLE(ops.information_schema.task_history(
      SCHEDULED_TIME_RANGE_START => SNOWFLAKE.ALERT.LAST_SUCCESSFUL_SCHEDULED_TIME(),
      SCHEDULED_TIME_RANGE_END   => SNOWFLAKE.ALERT.SCHEDULED_TIME()))
    WHERE state = 'FAILED'
  ))
  THEN
    CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
      SNOWFLAKE.NOTIFICATION.TEXT_PLAIN('One or more tasks failed in the last hour.'),
      '{"ops_email_int": {}}');

ALTER ALERT ops.monitoring.failed_tasks_alert RESUME;
```

Review recent alert runs and their outcomes:

```sql
SELECT name, state, scheduled_time, completed_time, sql_error_message
FROM TABLE(ops.information_schema.alert_history(
  SCHEDULED_TIME_RANGE_START => DATEADD('day', -1, CURRENT_TIMESTAMP())))
ORDER BY scheduled_time DESC;
```

States include TRIGGERED (action ran), CONDITION_FALSE, CONDITION_FAILED and ACTION_FAILED.

## Best practices

- Use the scheduled-time functions so each run checks only new activity and does not repeat notifications.
- Prefer serverless alerts for lightweight, infrequent checks.
- Use alerts on new data for event-driven monitoring of append-only tables and event tables.
- Set `SUSPEND_ALERT_AFTER_NUM_FAILURES` so a broken alert does not keep consuming credits.
- Remember that ACCOUNT_USAGE sources have latency; size your schedule and look-back windows accordingly.

## Common pitfalls

- Creating an alert and forgetting to resume it.
- Writing a condition that returns rows every time, causing a flood of notifications.
- Running a frequent alert on a warehouse and paying a minute of compute per run.
- Querying ACCOUNT_USAGE with a look-back window shorter than the view's latency and missing events.
- Forgetting that alerts on new data cannot be run manually with EXECUTE ALERT.

## Learn more

- [Setting up alerts based on data in Snowflake](https://docs.snowflake.com/en/user-guide/alerts)
- [ALERT_HISTORY](https://docs.snowflake.com/en/sql-reference/functions/alert_history)

## Knowledge check

### You create an alert with a valid condition and schedule, but it never runs. What is the most likely cause?
- [ ] The alert needs a clustering key
- [x] Alerts are created in a suspended state and must be resumed with ALTER ALERT ... RESUME
- [ ] Alerts only run in Business Critical Edition
- [ ] The schedule must be a CRON expression
> New alerts are suspended by default; they do not execute until they are resumed.

### A check runs every 5 minutes, finishes in a few seconds, and rarely fires. Which compute option is usually most cost-effective?
- [ ] A dedicated Medium warehouse
- [x] A serverless alert (omit the WAREHOUSE parameter)
- [ ] A multi-cluster warehouse
- [ ] A Snowpark-optimized warehouse
> A warehouse-based alert pays at least one minute of compute per run, whereas a serverless alert is billed only for the resources it actually uses.

### An hourly alert sends the same failure notification repeatedly for one old failure. How should you fix it?
- [ ] Increase the schedule to every 10 minutes
- [x] Restrict the condition to the window between LAST_SUCCESSFUL_SCHEDULED_TIME() and SCHEDULED_TIME()
- [ ] Use SELECT * in the condition
- [ ] Move the alert to a different schema
> Limiting the condition to activity since the last successful run means each event is evaluated only once.
