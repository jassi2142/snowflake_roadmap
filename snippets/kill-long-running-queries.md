# Cancel long-running queries (and prevent them with timeouts)

topics: timeouts-queuing, stored-procedures, information-schema
tags: cost, monitoring, warehouses, scripting
level: intermediate

Stop runaway queries from burning warehouse credits. The main fix is preventive: set `STATEMENT_TIMEOUT_IN_SECONDS` so Snowflake cancels queries automatically. For one-off cleanups, the procedure below finds queries that have been running longer than N minutes and cancels them, with a dry-run mode so you can see the list first.

```sql
-- 1. Preferred: timeouts. Account < user < session resolves to one value; if the warehouse
--    also sets one, the lower non-zero value of the two is enforced.
ALTER WAREHOUSE adhoc_wh SET STATEMENT_TIMEOUT_IN_SECONDS = 1800;        -- 30 min for ad-hoc work
ALTER WAREHOUSE adhoc_wh SET STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 600;  -- give up after 10 min in the queue
ALTER USER bi_service    SET STATEMENT_TIMEOUT_IN_SECONDS = 900;

-- 2. See what is running long right now
SELECT query_id, user_name, warehouse_name, start_time,
       DATEDIFF(minute, start_time, CURRENT_TIMESTAMP()) AS minutes_running,
       LEFT(query_text, 200) AS query_text
FROM TABLE(my_db.INFORMATION_SCHEMA.QUERY_HISTORY(
       END_TIME_RANGE_START => DATEADD(hour, -24, CURRENT_TIMESTAMP()),
       RESULT_LIMIT => 10000))
WHERE execution_status = 'RUNNING'
  AND start_time < DATEADD(minute, -30, CURRENT_TIMESTAMP())
ORDER BY start_time;

-- 3. Procedure: cancel queries running longer than max_minutes (dry_run = TRUE only lists them)
CREATE OR REPLACE PROCEDURE my_db.admin.cancel_long_queries(max_minutes NUMBER, dry_run BOOLEAN)
RETURNS ARRAY
LANGUAGE SQL
EXECUTE AS CALLER          -- uses the calling role's query visibility and cancel rights
AS
$$
DECLARE
  cutoff    TIMESTAMP_LTZ;
  cancelled ARRAY DEFAULT ARRAY_CONSTRUCT();
  qid       STRING;
  res       STRING;
  rs        RESULTSET;
BEGIN
  cutoff := DATEADD(minute, -1 * max_minutes, CURRENT_TIMESTAMP());
  rs := (SELECT query_id
         FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
                END_TIME_RANGE_START => DATEADD(hour, -24, CURRENT_TIMESTAMP()),
                RESULT_LIMIT => 10000))
         WHERE execution_status = 'RUNNING'
           AND start_time < :cutoff);
  LET c1 CURSOR FOR rs;
  FOR rec IN c1 DO
    qid := rec.query_id;
    IF (NOT dry_run) THEN
      SELECT SYSTEM$CANCEL_QUERY(:qid) INTO :res;
    END IF;
    cancelled := ARRAY_APPEND(cancelled, qid);
  END FOR;
  RETURN cancelled;
END;
$$;

-- 4. Dry run first, then cancel for real
CALL my_db.admin.cancel_long_queries(60, TRUE);
-- CALL my_db.admin.cancel_long_queries(60, FALSE);
```

## Notes
- Works in all editions. The STATEMENT_TIMEOUT_IN_SECONDS default is 172800 seconds (2 days), so set it lower on every warehouse.
- `INFORMATION_SCHEMA.QUERY_HISTORY` has no latency (unlike ACCOUNT_USAGE). It returns your own queries, plus other users' queries on warehouses where the role has MONITOR or OPERATE. Cancelling another user's query requires OPERATE or OWNERSHIP on the warehouse, OWNERSHIP of that user, or ACCOUNTADMIN.
- `RESULT_LIMIT` (maximum 10,000) is applied before the WHERE clause. On very busy accounts, narrow the time window or use the `QUERY_HISTORY_BY_WAREHOUSE` table function.
- To run this on a schedule, call the procedure from a task. A timeout is still simpler and acts instantly, so treat the procedure as a backstop.
- To stop everything on a warehouse at once, `ALTER WAREHOUSE adhoc_wh ABORT ALL QUERIES` is an alternative to cancelling queries one by one.

## References
- [STATEMENT_TIMEOUT_IN_SECONDS](https://docs.snowflake.com/en/sql-reference/parameters#statement-timeout-in-seconds)
- [SYSTEM$CANCEL_QUERY](https://docs.snowflake.com/en/sql-reference/functions/system_cancel_query)
- [QUERY_HISTORY table functions](https://docs.snowflake.com/en/sql-reference/functions/query_history)
- [Working with cursors in Snowflake Scripting](https://docs.snowflake.com/en/developer-guide/snowflake-scripting/cursors)
