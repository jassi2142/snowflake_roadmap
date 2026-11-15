# Remove duplicate rows with QUALIFY

topics: snowflake-sql-extensions, loading-best-practices
tags: data-quality, deduplication, sql
level: beginner

`QUALIFY` filters on window function results without a subquery. Use `ROW_NUMBER()` to keep exactly one row per business key, for example the most recently loaded version of each customer.

```sql
-- Preview: keep the latest row per customer_id
SELECT *
FROM my_db.bronze.customers_raw
QUALIFY ROW_NUMBER() OVER (
          PARTITION BY customer_id
          ORDER BY loaded_at DESC, file_row_number DESC   -- tie-breaker makes the result deterministic
        ) = 1;

-- See which keys are duplicated and how often
SELECT customer_id, COUNT(*) AS copies
FROM my_db.bronze.customers_raw
GROUP BY customer_id
HAVING COUNT(*) > 1
ORDER BY copies DESC;

-- Write a deduplicated table
CREATE OR REPLACE TABLE my_db.silver.customers AS
SELECT *
FROM my_db.bronze.customers_raw
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY loaded_at DESC, file_row_number DESC) = 1;

-- Deduplicate in place (rows that are exact duplicates across all columns)
INSERT OVERWRITE INTO my_db.bronze.customers_raw
SELECT DISTINCT * FROM my_db.bronze.customers_raw;
```

## Notes
- Without a unique `ORDER BY`, `ROW_NUMBER` may pick a different row each run when rows tie.
- `RANK()` keeps all tied rows; use `ROW_NUMBER()` when you need exactly one.
- `INSERT OVERWRITE` replaces the table contents in one transaction; Time Travel still lets you recover the previous version.

## References
- [QUALIFY](https://docs.snowflake.com/en/sql-reference/constructs/qualify)
- [ROW_NUMBER](https://docs.snowflake.com/en/sql-reference/functions/row_number)
- [INSERT](https://docs.snowflake.com/en/sql-reference/sql/insert)
