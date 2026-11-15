# Snowpark

Snowpark is Snowflake's developer framework for writing data pipelines and applications in Python, Java, or Scala that run inside Snowflake. Instead of pulling data out to a client, you build DataFrame operations that Snowpark translates to SQL and executes on a Snowflake warehouse, so processing stays close to the data and inherits Snowflake's security and scaling.

## How it works

**Session.** Everything starts with a `Session`, which holds connection details (account, user, authentication, role, warehouse, database, schema). Locally you build one with `Session.builder.configs(...).create()`; inside a stored procedure or notebook, Snowflake supplies the session for you.

**Lazy DataFrames.** A Snowpark DataFrame is a description of a query, not data in memory. Transformations such as `filter`, `select`, `join`, and `group_by` build up a plan. Nothing runs until you call an **action**, for example `collect()`, `show()`, `count()`, `to_pandas()`, or `write.save_as_table()`. At that point Snowpark generates SQL and runs it on the warehouse. This means:

- Large data never travels to the client unless you explicitly collect it.
- You can inspect the generated SQL with `df.queries` or `df.explain()`.

**Server-side code.** Snowpark lets you register Python, Java, or Scala functions as UDFs, UDTFs, UDAFs (Python), and stored procedures, so custom logic runs in Snowflake's sandbox next to the data. Python code can use third-party packages from the Snowflake Anaconda channel.

**Semantics are Snowflake's, not pandas'.** Because DataFrame operations compile to SQL, behaviors such as NULL handling, type casting, and division follow Snowflake SQL rules. For a pandas-style API that executes in Snowflake, Snowflake also provides the pandas on Snowflake API (`modin` based), which is separate from the core Snowpark DataFrame API.

**Where it runs.** You can use Snowpark from a local IDE, from Snowflake Notebooks, inside stored procedures (often scheduled by tasks), and in Streamlit in Snowflake apps.

## Example

A local Python script that reads a table, aggregates, and writes the result back, all executed in Snowflake.

```python
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col, sum as sum_

session = Session.builder.config("connection_name", "my_conn").create()

orders = session.table("RAW.ORDERS")

daily = (
    orders
    .filter(col("STATUS") != "returned")
    .group_by(col("ORDER_DATE"))
    .agg(sum_(col("AMOUNT")).alias("REVENUE"))
)

daily.write.mode("overwrite").save_as_table("ANALYTICS.DAILY_REVENUE")
print(daily.limit(5).collect())
```

Only the final `save_as_table` and `collect` trigger execution; the filter and aggregation run as SQL on the warehouse.

Registering a Python function as a permanent UDF from Snowpark:

```python
from snowflake.snowpark.types import StringType

def mask_email(email: str) -> str:
    if email is None:
        return None
    name, _, domain = email.partition("@")
    return name[:1] + "***@" + domain

session.udf.register(
    mask_email,
    name="ANALYTICS.MASK_EMAIL",
    return_type=StringType(),
    input_types=[StringType()],
    is_permanent=True,
    stage_location="@ANALYTICS.UDF_STAGE",
    replace=True,
)
```

## Best practices

- Push work into DataFrame operations; avoid `collect()` or `to_pandas()` on large results.
- Prefer built-in functions over Python UDFs where possible; they compile to native SQL.
- Use vectorized UDFs for batch-friendly Python logic.
- Keep credentials out of code: use connection files, key-pair auth, or the session provided inside Snowflake.
- Package pipeline logic as stored procedures so tasks can schedule it.

## Common pitfalls

- Assuming pandas semantics for NULLs, integer division, or type coercion.
- Calling actions inside loops, which sends many small queries.
- Pulling a large table to the client with `to_pandas()` and running out of memory.
- Forgetting that registered temporary UDFs disappear when the session ends; use `is_permanent=True` with a stage for reuse.

## Learn more

- [Snowpark developer guide](https://docs.snowflake.com/en/developer-guide/snowpark/index)

## Knowledge check

### When does a Snowpark DataFrame chain of `filter` and `group_by` actually execute?
- [ ] Immediately after each method call
- [x] When an action such as collect(), show(), or save_as_table() is called
- [ ] When the session is closed
- [ ] Only inside a stored procedure
> Snowpark DataFrames are lazy; actions trigger SQL generation and execution on the warehouse.

### A developer calls `to_pandas()` on a 500 GB table locally and the script crashes. What is the better approach?
- [ ] Use a larger warehouse
- [x] Express the transformation with DataFrame operations so it runs in Snowflake, then collect only the small result
- [ ] Convert the table to a view
- [ ] Use a secure UDF
> Keeping work in DataFrame operations executes it in Snowflake; only small results should be brought to the client.

### Why can Snowpark code behave differently from equivalent pandas code?
- [ ] Snowpark uses a different Python interpreter
- [x] Snowpark DataFrame operations compile to SQL and follow Snowflake SQL semantics
- [ ] Snowpark samples data randomly
- [ ] Snowpark does not support NULL values
> Because operations are translated to SQL, NULL handling, casting, and similar behaviors follow Snowflake rules.
