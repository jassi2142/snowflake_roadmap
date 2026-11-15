# Size and cap a serverless task

topics: tasks, serverless-compute
tags: cost, orchestration
level: intermediate

Serverless tasks let Snowflake pick the compute size for each run. These parameters set the starting size, the minimum and maximum size, and a completion target so you get predictable runtime without runaway cost.

```sql
USE SCHEMA my_db.pipelines;

-- No WAREHOUSE parameter => serverless
CREATE OR REPLACE TASK hourly_rollup
  SCHEDULE = 'USING CRON 7 * * * * UTC'
  USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'SMALL'   -- size for the first runs, before history exists
  SERVERLESS_TASK_MIN_STATEMENT_SIZE = 'XSMALL'        -- default XSMALL
  SERVERLESS_TASK_MAX_STATEMENT_SIZE = 'LARGE'         -- default XXLARGE (the maximum)
  TARGET_COMPLETION_INTERVAL = '30 MINUTES'            -- Snowflake scales to finish within this
  USER_TASK_TIMEOUT_MS = 3600000                       -- hard stop after 1 hour
  SUSPEND_TASK_AFTER_NUM_FAILURES = 3
AS
  INSERT INTO my_db.gold.hourly_sales
  SELECT DATE_TRUNC('hour', order_ts), SUM(amount)
  FROM my_db.silver.orders
  WHERE order_ts >= DATEADD('hour', -1, DATE_TRUNC('hour', CURRENT_TIMESTAMP()))
    AND order_ts <  DATE_TRUNC('hour', CURRENT_TIMESTAMP())
  GROUP BY 1;

ALTER TASK hourly_rollup RESUME;

-- Credits used by this task over the last 7 days
SELECT start_time, end_time, credits_used
FROM TABLE(my_db.INFORMATION_SCHEMA.SERVERLESS_TASK_HISTORY(
       DATE_RANGE_START => DATEADD('day', -7, CURRENT_TIMESTAMP()),
       TASK_NAME => 'HOURLY_ROLLUP'))
ORDER BY start_time DESC;
```

## Notes
- The owning role needs EXECUTE MANAGED TASK on the account (plus EXECUTE TASK).
- The largest serverless size is XXLARGE; workloads needing more must use a user-managed warehouse.
- Once at the max size, Snowflake ignores the completion target, so `USER_TASK_TIMEOUT_MS` is your real cap on a single run.
- Serverless tasks are billed per actual compute used, without the warehouse 60-second minimum, which suits short or infrequent jobs.

## References
- [Introduction to tasks](https://docs.snowflake.com/en/user-guide/tasks-intro)
- [CREATE TASK](https://docs.snowflake.com/en/sql-reference/sql/create-task)
- [SERVERLESS_TASK_HISTORY](https://docs.snowflake.com/en/sql-reference/functions/serverless_task_history)
