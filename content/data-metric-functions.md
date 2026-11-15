# Data Metric Functions

Data metric functions (DMFs) are Snowflake's native building blocks for data quality monitoring. A DMF computes a metric over a table or view, such as null count, duplicate count, row count, or freshness, and Snowflake runs it on a schedule using serverless compute, recording results centrally. Combined with expectations, DMFs turn data quality from ad hoc SQL checks into continuously enforced, auditable contracts.

## How it works

Data Quality Monitoring requires **Enterprise Edition** and is not available in trial or reader accounts.

### Building blocks

- **System DMFs** live in `SNOWFLAKE.CORE`, for example `NULL_COUNT`, `DUPLICATE_COUNT`, `ROW_COUNT`, `BLANK_COUNT`, and `ACCEPTED_VALUES` (which takes a lambda, such as `age -> age >= 0`).
- **Custom DMFs** are created with `CREATE DATA METRIC FUNCTION`. They take one or more `TABLE(...)` arguments and return a number, which allows arbitrary checks including cross-table referential integrity.
- **Associations** attach a DMF to an object and specify which columns are passed: `ALTER TABLE ... ADD DATA METRIC FUNCTION ... ON (col)`. You can also attach DMFs at creation time with `WITH DATA METRIC FUNCTION (...)`. Each association counts toward a limit of **50,000 associations per account**.
- **Expectations** add pass/fail semantics: a boolean condition on the keyword `VALUE` (for example `VALUE = 0`). Results that fail are reported as violations.
- **Anomaly detection** can learn from history and flag unusual volume and freshness without hand-set thresholds.

### Scheduling and execution

The `DATA_METRIC_SCHEDULE` object parameter controls how often all DMFs on a table or view run; every DMF on that object shares one schedule. Options:

- An interval: `'5 MINUTE'`, `'60 MINUTE'`.
- A cron expression: `'USING CRON 0 8 * * * UTC'`.
- `'TRIGGER_ON_CHANGES'`: run when DML modifies the table (reclustering does not trigger it; only certain table kinds support it).
- `''` to suspend all DMFs on the object; individual associations can also be suspended and resumed.

Changes to a schedule take about 10 minutes to affect existing associations. Results land in `SNOWFLAKE.LOCAL.DATA_QUALITY_MONITORING_RESULTS`; evaluate them by `measurement_time`, which reflects when the DMF actually ran rather than when it was scheduled.

### Cost model and trade-offs

Scheduled DMFs run on serverless compute billed under Data Quality Monitoring; result logging appears separately as Logging. You are not billed for creating a DMF or for calling one manually in a `SELECT`. The main design trade-off is **frequency versus cost**: high-frequency or trigger-based schedules on large, frequently updated tables can be expensive, so tier tables by criticality. Because all DMFs on an object share one schedule, put expensive checks on objects whose cadence matches their importance, or check them through a separate view.

Constraints to plan around: DMFs cannot be set on hybrid tables, streams, shared objects, or tags.

## Example

Set a schedule and attach system DMFs with expectations:

```sql
ALTER TABLE sales.public.orders SET DATA_METRIC_SCHEDULE = 'USING CRON 0 6,12,18 * * * UTC';

ALTER TABLE sales.public.orders
  ADD DATA METRIC FUNCTION SNOWFLAKE.CORE.NULL_COUNT ON (customer_id)
  EXPECTATION no_null_customers (VALUE = 0);

ALTER TABLE sales.public.orders
  ADD DATA METRIC FUNCTION SNOWFLAKE.CORE.DUPLICATE_COUNT ON (order_id)
  EXPECTATION no_duplicate_orders (VALUE = 0);
```

Create a custom DMF and test it manually before scheduling it:

```sql
CREATE OR REPLACE DATA METRIC FUNCTION governance.dmfs.negative_amounts(
  arg_t TABLE(arg_amount NUMBER))
RETURNS NUMBER
AS 'SELECT COUNT(*) FROM arg_t WHERE arg_amount < 0';

SELECT governance.dmfs.negative_amounts(SELECT amount FROM sales.public.orders);

ALTER TABLE sales.public.orders
  ADD DATA METRIC FUNCTION governance.dmfs.negative_amounts ON (amount);
```

Attach checks at creation time so monitoring starts immediately:

```sql
CREATE OR REPLACE TABLE sales.public.customers (
  customer_id NUMBER,
  email       VARCHAR
)
WITH DATA METRIC FUNCTION (
  SNOWFLAKE.CORE.NULL_COUNT ON (email) EXPECTATION no_null_email (VALUE = 0)
);
```

Review recent results:

```sql
SELECT measurement_time, table_name, metric_name, value
FROM SNOWFLAKE.LOCAL.DATA_QUALITY_MONITORING_RESULTS
ORDER BY measurement_time DESC
LIMIT 100;
```

## Best practices

- Tier tables: frequent schedules for SLA-critical tables, daily for the long tail.
- Use expectations so failures are explicit, and route violations to alerts or notifications.
- Prefer `TRIGGER_ON_CHANGES` for batch-loaded tables where checks only matter after a load.
- Test custom DMFs with a manual `SELECT` before associating them.
- Track spend with `DATA_QUALITY_MONITORING_USAGE_HISTORY`.

## Common pitfalls

- Forgetting that one schedule applies to all DMFs on an object, then being surprised by cost.
- Comparing results against scheduled time instead of `measurement_time`, misattributing late-arriving loads.
- Expecting schedule changes to apply instantly to existing associations.
- Writing expectations with arithmetic on `VALUE` or subqueries, which are not allowed.

## Learn more

- [Introduction to data quality checks](https://docs.snowflake.com/en/user-guide/data-quality-intro)
- [Use SQL to set up data metric functions](https://docs.snowflake.com/en/user-guide/data-quality-working)

## Knowledge check

### A table has five DMFs. You want NULL_COUNT to run every 5 minutes but an expensive custom DMF only daily. What constraint must your design account for?
- [ ] Each DMF association has its own independent schedule
- [x] All DMFs on a table share the table's DATA_METRIC_SCHEDULE, so you need a different object (for example a view) for a different cadence
- [ ] Custom DMFs can only run daily
- [ ] System DMFs ignore the schedule
> DATA_METRIC_SCHEDULE is an object parameter and every DMF on that object follows it.

### Finance asks why their DMF bill is high on a table loaded once per night. Which change most directly reduces cost without losing coverage?
- [ ] Drop the expectations
- [x] Change the schedule from a 5-minute interval to TRIGGER_ON_CHANGES or a daily cron after the load
- [ ] Call the DMFs manually with SELECT from a warehouse every 5 minutes
- [ ] Move the table to a reader account
> Scheduled executions drive serverless cost; aligning the schedule to the load pattern avoids computing metrics on unchanged data.

### A DMF result shows a NULL spike, but the load finished before the scheduled time. Which column should you use to reason about when the metric was computed?
- [ ] scheduled_time
- [x] measurement_time
- [ ] query_start_time from QUERY_HISTORY
- [ ] The table's last_altered timestamp
> Snowflake recommends measurement_time because DML can occur between the scheduled time and the actual evaluation.
