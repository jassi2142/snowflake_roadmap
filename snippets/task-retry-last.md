# Automatic and manual retries for failed task graphs

topics: tasks
tags: orchestration, reliability
level: intermediate

Let Snowflake retry a failed graph automatically, cap how many consecutive failures are tolerated, and rerun only the failed part of the last run after you fix the cause.

```sql
USE SCHEMA my_db.pipelines;

-- Retry a failed graph run up to 2 times; suspend after 3 consecutive failed runs
ALTER TASK root_daily SUSPEND;
ALTER TASK root_daily SET
  TASK_AUTO_RETRY_ATTEMPTS = 2,
  SUSPEND_TASK_AFTER_NUM_FAILURES = 3;
ALTER TASK root_daily RESUME;

-- Inspect the latest failures
SELECT name, state, attempt_number, error_message, scheduled_time
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
       SCHEDULED_TIME_RANGE_START => DATEADD('day', -1, CURRENT_TIMESTAMP()),
       ERROR_ONLY => TRUE))
ORDER BY scheduled_time DESC;

-- After fixing the cause: rerun the last graph run starting from the failed tasks.
-- Tasks that already succeeded in that run are not rerun.
EXECUTE TASK root_daily RETRY LAST;

-- If the root was auto-suspended, resume it (and its dependents) again
SELECT SYSTEM$TASK_DEPENDENTS_ENABLE('my_db.pipelines.root_daily');
```

## Notes
- `TASK_AUTO_RETRY_ATTEMPTS` is set on the root task (or at account/database/schema level) and is disabled (0) by default.
- `SUSPEND_TASK_AFTER_NUM_FAILURES` defaults to 10; 0 disables auto-suspension.
- `RETRY LAST` requires the latest graph run to be FAILED or CANCELED, the graph to be unmodified since that run, and the run's first attempt to be within the last 14 days.
- Retries re-execute SQL, so make task statements idempotent (MERGE, or delete-then-insert for a window).

## References
- [Introduction to tasks](https://docs.snowflake.com/en/user-guide/tasks-intro)
- [EXECUTE TASK](https://docs.snowflake.com/en/sql-reference/sql/execute-task)
- [Parameters](https://docs.snowflake.com/en/sql-reference/parameters)
