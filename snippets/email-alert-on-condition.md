# Email when tasks fail in the last hour

topics: alerts, tasks
tags: alerting, email, monitoring
level: intermediate

A Snowflake alert runs a condition query on a schedule and performs an action only when the query returns rows. This one emails the team whenever any task failed in the past hour.

```sql
USE ROLE accountadmin;
USE SCHEMA my_db.monitoring;

-- 1. Email integration; recipients must be verified users in this account
CREATE OR REPLACE NOTIFICATION INTEGRATION ops_email_int
  TYPE = EMAIL
  ENABLED = TRUE
  ALLOWED_RECIPIENTS = ('data-ops@example.com');

-- 2. Alert: condition returns rows -> action runs
CREATE OR REPLACE ALERT failed_tasks_alert
  WAREHOUSE = my_wh
  SCHEDULE = '60 MINUTE'
  IF (EXISTS (
        SELECT 1
        FROM TABLE(my_db.INFORMATION_SCHEMA.TASK_HISTORY(
               SCHEDULED_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP()),
               ERROR_ONLY => TRUE))
  ))
  THEN
    BEGIN
      LET failed STRING := (
        SELECT LISTAGG(name || ': ' || error_message, '\n')
        FROM TABLE(my_db.INFORMATION_SCHEMA.TASK_HISTORY(
               SCHEDULED_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP()),
               ERROR_ONLY => TRUE)));
      CALL SYSTEM$SEND_EMAIL(
        'ops_email_int',
        'data-ops@example.com',
        'Snowflake: task failures in the last hour',
        :failed);
    END;

-- 3. Alerts are created suspended
ALTER ALERT failed_tasks_alert RESUME;

-- Check alert runs
SELECT name, state, scheduled_time, sql_error_message
FROM TABLE(INFORMATION_SCHEMA.ALERT_HISTORY(
       SCHEDULED_TIME_RANGE_START => DATEADD('day', -1, CURRENT_TIMESTAMP())))
ORDER BY scheduled_time DESC;
```

## Notes
- The alert owner needs EXECUTE ALERT on the account, USAGE on the warehouse and integration, and privileges to see the task history (task OWNERSHIP, MONITOR, or MONITOR EXECUTION).
- `INFORMATION_SCHEMA.TASK_HISTORY` is scoped to the database you name; use `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY` for the whole account (it has up to 45 minutes of latency).
- Omit `WAREHOUSE` to make it a serverless alert. Every evaluation costs compute, so pick a sensible schedule.
- Clean up with `DROP ALERT failed_tasks_alert;`.

## References
- [Setting up alerts based on data in Snowflake](https://docs.snowflake.com/en/user-guide/alerts)
- [CREATE ALERT](https://docs.snowflake.com/en/sql-reference/sql/create-alert)
- [SYSTEM$SEND_EMAIL](https://docs.snowflake.com/en/sql-reference/stored-procedures/system_send_email)
- [TASK_HISTORY](https://docs.snowflake.com/en/sql-reference/functions/task_history)
