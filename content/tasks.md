# Tasks & Task Graphs

A task is a Snowflake object that runs a SQL statement, a Snowflake Scripting block, or a stored procedure call on a schedule or when an event occurs. Task graphs (DAGs) chain tasks together with dependencies, giving you built-in orchestration for data pipelines without an external scheduler.

## How it works

**Compute models.** A task runs either on a user-managed warehouse (specify `WAREHOUSE`) or as a **serverless task** (omit `WAREHOUSE`). Serverless tasks are sized by Snowflake based on recent runs, up to the equivalent of an XXLARGE warehouse; you can bound sizing with `SERVERLESS_TASK_MIN_STATEMENT_SIZE` (default XSMALL) and `SERVERLESS_TASK_MAX_STATEMENT_SIZE` (default XXLARGE). Serverless tasks require the account-level `EXECUTE MANAGED TASK` privilege; running any task requires the owner role to have `EXECUTE TASK`.

**Scheduling.** `SCHEDULE` accepts an interval (`'60 MINUTES'`) or a cron expression (`'USING CRON 0 6 * * * UTC'`). A `WHEN` clause, typically `SYSTEM$STREAM_HAS_DATA('my_stream')`, makes the task skip when there is no new data. Omitting `SCHEDULE` and using only `WHEN` creates a **triggered task** that runs as stream data arrives.

**Lifecycle.** New tasks are created **suspended**. Use `ALTER TASK ... RESUME` to start them and `EXECUTE TASK` to run one ad hoc. Only one instance of a scheduled task runs at a time; if a run overlaps the next schedule, that scheduled time is skipped.

**Task graphs.** A root task holds the schedule; child tasks declare `AFTER parent_task`. Siblings run in parallel; a task with multiple parents waits for all of them. Limits: a graph can contain up to 1000 tasks, and a task can have up to 100 parents and 100 children. All tasks in a graph must share the same owner, database, and schema. An optional **finalizer** task (`FINALIZE = root_task`) runs after all other tasks finish or fail, which is useful for cleanup and notifications.

**Failure handling.** By default a graph is suspended after 10 consecutive failed runs; change this with `SUSPEND_TASK_AFTER_NUM_FAILURES`. Automatic retries are off by default; set `TASK_AUTO_RETRY_ATTEMPTS` on the root task. `EXECUTE TASK ... RETRY LAST` reruns from the last failed task. `OVERLAP_POLICY` (default `NO_OVERLAP`) controls whether graph runs can overlap.

**Versioning.** To modify tasks in a graph, suspend the root task first. A new graph version is set when the root is resumed or executed. Tasks can pass data with `SYSTEM$SET_RETURN_VALUE` / `SYSTEM$GET_PREDECESSOR_RETURN_VALUE` and read graph configuration with `SYSTEM$GET_TASK_GRAPH_CONFIG`.

## Example

A serverless root task loads data hourly when the stream has changes; two children run after it, and a finalizer cleans up.

```sql
CREATE OR REPLACE TASK load_orders
  SCHEDULE = '60 MINUTES'
  SUSPEND_TASK_AFTER_NUM_FAILURES = 3
  TASK_AUTO_RETRY_ATTEMPTS = 2
  WHEN SYSTEM$STREAM_HAS_DATA('raw_orders_stream')
AS
  INSERT INTO orders_staging SELECT * FROM raw_orders_stream;

CREATE OR REPLACE TASK build_daily_sales
  WAREHOUSE = transform_wh
  AFTER load_orders
AS
  CALL refresh_daily_sales();

CREATE OR REPLACE TASK build_customer_metrics
  WAREHOUSE = transform_wh
  AFTER load_orders
AS
  CALL refresh_customer_metrics();

CREATE OR REPLACE TASK cleanup_finalizer
  WAREHOUSE = transform_wh
  FINALIZE = load_orders
AS
  TRUNCATE TABLE IF EXISTS orders_scratch;

-- Resume all dependents and the root in one call
SELECT SYSTEM$TASK_DEPENDENTS_ENABLE('load_orders');
```

Monitor runs with the `TASK_HISTORY` table function:

```sql
SELECT name, state, scheduled_time, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY())
ORDER BY scheduled_time DESC
LIMIT 20;
```

## Best practices

- Prefer **serverless** tasks for short or under-utilized workloads, and warehouses for heavily utilized shared compute.
- Use `WHEN SYSTEM$STREAM_HAS_DATA` to avoid paying for empty runs.
- Set `SUSPEND_TASK_AFTER_NUM_FAILURES` and error notifications so failing pipelines stop consuming credits and alert someone.
- Keep task bodies thin: call stored procedures so logic is versioned and testable.
- Run production tasks under a dedicated service role, not a personal role.

## Common pitfalls

- Forgetting to resume child tasks: resuming only the root leaves suspended children skipped.
- Editing a child task without suspending the root first.
- Schedules shorter than graph duration, which causes skipped runs under `NO_OVERLAP`.
- Granting ownership of a single task, which severs its links to parent and child tasks.

## Learn more

- [Introduction to tasks](https://docs.snowflake.com/en/user-guide/tasks-intro)
- [Create a sequence of tasks with a task graph](https://docs.snowflake.com/en/user-guide/tasks-graphs)

## Knowledge check

### You created a root task and three child tasks, then resumed only the root. What happens at the next scheduled run?
- [ ] All four tasks run because children inherit the root's state
- [x] The root runs, but suspended children are skipped
- [ ] The root fails because children are suspended
- [ ] Nothing runs until EXECUTE TASK is called
> Tasks are created suspended; each child must be resumed (or use SYSTEM$TASK_DEPENDENTS_ENABLE), otherwise suspended children are skipped.

### A small task runs every 5 minutes on a large shared warehouse that otherwise sits idle. What change most directly reduces cost?
- [ ] Increase the warehouse size so it finishes faster
- [x] Convert it to a serverless task and add a WHEN condition on its stream
- [ ] Set OVERLAP_POLICY = ALLOW_ALL_OVERLAP
- [ ] Add a finalizer task
> Serverless tasks bill for actual compute used rather than keeping a warehouse running, and a WHEN condition skips runs with no new data.

### Which statement about finalizer tasks is correct?
- [ ] A root task can have several finalizers
- [ ] A finalizer can have its own child tasks
- [x] A finalizer runs after all other tasks in the graph complete or fail
- [ ] A finalizer runs even when the root task is skipped
> A finalizer is tied to one root task, has no children, runs after the rest of the graph finishes, and does not start if the root is skipped.
