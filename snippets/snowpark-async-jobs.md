# Run Snowpark queries in parallel with async jobs

topics: snowpark
tags: python, async, performance
level: intermediate

By default a Snowpark action such as `collect()` blocks until the query finishes. `collect_nowait()` (or `block=False`) submits the query and returns an `AsyncJob` right away, so several independent queries can run at once and you gather the results afterwards.

```python
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col, sum as sum_

# Connection from ~/.snowflake/connections.toml (or use get_active_session() inside Snowflake)
session = Session.builder.config("connection_name", "my_conn").create()
session.use_warehouse("my_wh")

regions = ["EMEA", "AMER", "APAC"]
orders = session.table("my_db.my_schema.orders")

# 1. Submit one aggregate per region without waiting
jobs = {}
for region in regions:
    df = (orders.filter(col("region") == region)
                .group_by("order_month")
                .agg(sum_("amount").alias("revenue")))
    jobs[region] = df.collect_nowait()          # returns AsyncJob immediately
    print(region, "submitted as", jobs[region].query_id)

# 2. Gather results; result() blocks until that job finishes
for region, job in jobs.items():
    rows = job.result()                          # list[Row]
    print(region, len(rows), "months")

# 3. Other actions also accept block=False
count_job = orders.count(block=False)
write_job = orders.filter(col("amount") > 1000) \
                  .write.save_as_table("my_db.my_schema.big_orders",
                                       mode="overwrite", block=False)

print("is done?", count_job.is_done())
print("row count:", count_job.result())
write_job.result()                               # wait for the write to finish

# 4. Re-attach to a running query by id (e.g. from another process)
job = session.create_async_job(jobs["EMEA"].query_id)
print(job.status(), job.result(result_type="pandas_batches") is not None)

# 5. Cancel a job you no longer need
slow = session.sql("SELECT SYSTEM$WAIT(60)").collect_nowait()
slow.cancel()

session.close()
```

## Notes
- All async jobs share the session's warehouse. Concurrent queries can queue if the warehouse is small, so use a multi-cluster warehouse when you need real parallelism.
- `AsyncJob.result()` accepts `result_type` values such as `"row"`, `"pandas"`, `"pandas_batches"`, `"row_iterator"` and `"no_result"`.
- Call `result()` on every job and handle its exceptions: a failed query raises when you collect it, not when you submit it.

## References
- [Snowpark Python: AsyncJob](https://docs.snowflake.com/en/developer-guide/snowpark/reference/python/latest/snowpark/api/snowflake.snowpark.AsyncJob)
- [Working with DataFrames in Snowpark Python](https://docs.snowflake.com/en/developer-guide/snowpark/python/working-with-dataframes)
