# Run a task only when a stream has new data

topics: tasks, streams
tags: cdc, event-driven, orchestration
level: intermediate

A triggered task has no SCHEDULE: it runs whenever its stream has new change records, and costs nothing while the stream is empty.

```sql
USE SCHEMA my_db.pipelines;

CREATE OR REPLACE STREAM raw_orders_stream ON TABLE my_db.bronze.raw_orders;

-- Serverless triggered task: no SCHEDULE, no WAREHOUSE, TARGET_COMPLETION_INTERVAL is required
CREATE OR REPLACE TASK process_new_orders
  TARGET_COMPLETION_INTERVAL = '5 MINUTES'
  WHEN SYSTEM$STREAM_HAS_DATA('raw_orders_stream')
AS
  INSERT INTO my_db.silver.orders (order_id, customer_id, amount, order_ts)
  SELECT order_id, customer_id, amount, order_ts
  FROM raw_orders_stream
  WHERE METADATA$ACTION = 'INSERT';

-- Tasks are created suspended
ALTER TASK process_new_orders RESUME;

-- Optional: allow triggers as often as every 10 seconds (default minimum is 30)
ALTER TASK process_new_orders SET USER_TASK_MINIMUM_TRIGGER_INTERVAL_IN_SECONDS = 10;

-- Triggered runs show SCHEDULED_FROM = 'TRIGGER'
SELECT name, state, scheduled_from, scheduled_time
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'PROCESS_NEW_ORDERS'))
ORDER BY scheduled_time DESC;
```

## Notes
- For a warehouse-based triggered task, replace `TARGET_COMPLETION_INTERVAL` with `WAREHOUSE = my_wh`.
- Serverless tasks need the EXECUTE MANAGED TASK account privilege; all tasks need EXECUTE TASK.
- Reading the stream in a DML statement advances its offset; a plain SELECT does not.
- Not supported on hybrid tables or streams on external tables. If the task hasn't run in 12 hours, Snowflake runs a health check to keep the stream from going stale.

## References
- [Triggered tasks](https://docs.snowflake.com/en/user-guide/tasks-triggered)
- [CREATE TASK](https://docs.snowflake.com/en/sql-reference/sql/create-task)
- [Introduction to streams](https://docs.snowflake.com/en/user-guide/streams-intro)
