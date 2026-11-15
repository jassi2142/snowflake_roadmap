# Record a run summary with a finalizer task

topics: tasks, pipeline-design
tags: orchestration, observability, task-graph
level: advanced

A finalizer task runs once after every task in a graph run has finished, whether the run succeeded or failed. Use it to write one audit row per run with counts of succeeded, failed, and skipped tasks.

```sql
USE SCHEMA my_db.pipelines;

CREATE TABLE IF NOT EXISTS my_db.pipelines.graph_run_summary (
  run_group_id   STRING,
  root_task      STRING,
  finished_at    TIMESTAMP_LTZ,
  tasks_total    NUMBER,
  tasks_ok       NUMBER,
  tasks_failed   NUMBER,
  tasks_skipped  NUMBER,
  first_error    STRING
);

CREATE OR REPLACE TASK summarize_run
  WAREHOUSE = my_wh
  FINALIZE = root_daily          -- attach to the root task of the graph
AS
  INSERT INTO my_db.pipelines.graph_run_summary
  SELECT
    SYSTEM$TASK_RUNTIME_INFO('CURRENT_TASK_GRAPH_RUN_GROUP_ID'),
    SYSTEM$TASK_RUNTIME_INFO('CURRENT_ROOT_TASK_NAME'),
    CURRENT_TIMESTAMP(),
    COUNT(*),
    COUNT_IF(state = 'SUCCEEDED'),
    COUNT_IF(state IN ('FAILED', 'CANCELLED')),
    COUNT_IF(state = 'SKIPPED'),
    MIN_BY(error_message, IFF(error_message IS NULL, NULL, scheduled_time)) -- earliest error
  FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
         GRAPH_RUN_GROUP_ID => SYSTEM$TASK_RUNTIME_INFO('CURRENT_TASK_GRAPH_RUN_GROUP_ID')))
  WHERE name <> 'SUMMARIZE_RUN';  -- exclude the finalizer itself

SELECT SYSTEM$TASK_DEPENDENTS_ENABLE('my_db.pipelines.root_daily');

-- Review recent runs
SELECT * FROM my_db.pipelines.graph_run_summary ORDER BY finished_at DESC LIMIT 20;
```

## Notes
- A root task can have only one finalizer, and a finalizer cannot have children.
- Retried runs (automatic or `RETRY LAST`) stay in the same graph run group, so the history includes earlier failed attempts too. Filter on the highest `attempt_number` if you want only the latest attempt.
- `MIN_BY` skips rows whose ordering key is NULL, so only rows with an error are considered and `first_error` is NULL for fully successful runs.

## References
- [Create a sequence of tasks with a task graph](https://docs.snowflake.com/en/user-guide/tasks-graphs)
- [TASK_HISTORY](https://docs.snowflake.com/en/sql-reference/functions/task_history)
- [SYSTEM$TASK_RUNTIME_INFO](https://docs.snowflake.com/en/sql-reference/functions/system_task_runtime_info)
