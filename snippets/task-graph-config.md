# Parameterize a task graph with CONFIG

topics: tasks, pipeline-design
tags: orchestration, parameters
level: advanced

Put run settings (target environment, lookback window) in the root task's CONFIG, read them from any task in the graph, and override them for a one-off backfill without editing the tasks.

```sql
USE SCHEMA my_db.pipelines;

-- Root task carries default configuration as JSON
CREATE OR REPLACE TASK root_daily
  WAREHOUSE = my_wh
  SCHEDULE = 'USING CRON 15 2 * * * UTC'
  CONFIG = $${"env": "prod", "lookback_days": 1}$$
AS
  SELECT 1;   -- root can be a no-op that just starts the graph

-- Child task reads the config values at run time
CREATE OR REPLACE TASK load_orders
  WAREHOUSE = my_wh
  AFTER root_daily
AS
  INSERT INTO my_db.silver.orders_daily
  SELECT order_id, customer_id, amount, order_ts
  FROM my_db.bronze.orders
  WHERE order_ts >= DATEADD(
          'day',
          -1 * SYSTEM$GET_TASK_GRAPH_CONFIG('lookback_days')::INT,
          CURRENT_DATE());

-- Enable root and all dependents
SELECT SYSTEM$TASK_DEPENDENTS_ENABLE('my_db.pipelines.root_daily');

-- Normal manual run with the defaults
EXECUTE TASK root_daily;

-- One-off backfill: override the config for this run only and wait for completion
EXECUTE TASK root_daily
  USING CONFIG = $${"env": "prod", "lookback_days": 30}$$
  AWAIT;
```

## Notes
- `SYSTEM$GET_TASK_GRAPH_CONFIG` returns NULL for a missing key, so cast and default carefully (for example with `COALESCE`).
- `USING CONFIG` replaces the configuration for that single graph run; scheduled runs continue to use the CONFIG stored on the root.
- `EXECUTE TASK` requires OWNERSHIP or OPERATE on the task plus EXECUTE TASK on the account.

## References
- [Create a sequence of tasks with a task graph](https://docs.snowflake.com/en/user-guide/tasks-graphs)
- [EXECUTE TASK](https://docs.snowflake.com/en/sql-reference/sql/execute-task)
- [SYSTEM$GET_TASK_GRAPH_CONFIG](https://docs.snowflake.com/en/sql-reference/functions/system_get_task_graph_config)
