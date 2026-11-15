# Pass values between tasks in a graph

topics: tasks, pipeline-design
tags: orchestration, task-graph
level: advanced

A task can publish a small string result with `SYSTEM$SET_RETURN_VALUE`, and any direct successor can read it with `SYSTEM$GET_PREDECESSOR_RETURN_VALUE`. Here the load task reports how many rows it inserted and the next task logs it.

```sql
USE SCHEMA my_db.pipelines;

CREATE OR REPLACE TABLE my_db.pipelines.run_log (
  logged_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
  step      STRING,
  rows_in   NUMBER
);

CREATE OR REPLACE TASK root_rv
  WAREHOUSE = my_wh
  SCHEDULE = '60 MINUTE'
AS
  SELECT 1;

-- Producer: load data and publish the row count
CREATE OR REPLACE TASK load_step
  WAREHOUSE = my_wh
  AFTER root_rv
AS
BEGIN
  INSERT INTO my_db.silver.events
  SELECT * FROM my_db.bronze.events_stream;   -- a stream: consumed rows are removed from it
  LET n NUMBER := SQLROWCOUNT;
  CALL SYSTEM$SET_RETURN_VALUE(:n::STRING);
END;

-- Consumer: read the value published by the predecessor named LOAD_STEP
CREATE OR REPLACE TASK log_step
  WAREHOUSE = my_wh
  AFTER load_step
AS
  INSERT INTO my_db.pipelines.run_log (step, rows_in)
  SELECT 'load_step', SYSTEM$GET_PREDECESSOR_RETURN_VALUE('LOAD_STEP')::NUMBER;

SELECT SYSTEM$TASK_DEPENDENTS_ENABLE('my_db.pipelines.root_rv');

-- Return values are also visible in task history
SELECT name, state, return_value
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY())
WHERE name IN ('LOAD_STEP', 'LOG_STEP')
ORDER BY scheduled_time DESC;
```

## Notes
- Return values are strings and are size-limited; pass identifiers or counts, not data sets. Store larger results in a table.
- The predecessor name argument is the task name (not fully qualified); with a single predecessor you can omit it.
- Only direct predecessors' values are readable.

## References
- [Create a sequence of tasks with a task graph](https://docs.snowflake.com/en/user-guide/tasks-graphs)
- [SYSTEM$SET_RETURN_VALUE](https://docs.snowflake.com/en/sql-reference/functions/system_set_return_value)
- [SYSTEM$GET_PREDECESSOR_RETURN_VALUE](https://docs.snowflake.com/en/sql-reference/functions/system_get_predecessor_return_value)
