# Write a custom data metric function

topics: data-metric-functions, udfs
tags: data-quality, dmf, monitoring
level: advanced

When the system DMFs don't cover a business rule, write your own DMF in SQL. This snippet creates two: one counts orders with an invalid amount, the other counts orders whose customer is missing from the customers table (a referential check across two tables). Both run on the table's DMF schedule, and expectations flag failures.

```sql
USE ROLE dq_engineer;
USE SCHEMA my_db.dq;

-- 1. Single-table DMF: rows with a negative or missing amount
CREATE OR REPLACE DATA METRIC FUNCTION invalid_amount_count(
  arg_t TABLE (arg_amount NUMBER(12,2)))
RETURNS NUMBER
COMMENT = 'Rows where amount is NULL or negative'
AS
$$
  SELECT COUNT(*) FROM arg_t WHERE arg_amount IS NULL OR arg_amount < 0
$$;

-- 2. Two-table DMF: orders whose customer_id has no match in the customers table
CREATE OR REPLACE DATA METRIC FUNCTION orphan_key_count(
  arg_child  TABLE (arg_fk NUMBER),
  arg_parent TABLE (arg_pk NUMBER))
RETURNS NUMBER
AS
$$
  SELECT COUNT(*) FROM arg_child c
  WHERE c.arg_fk IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM arg_parent p WHERE p.arg_pk = c.arg_fk)
$$;

-- 3. Test manually before attaching
SELECT my_db.dq.invalid_amount_count(SELECT amount FROM my_db.sales.orders);

-- 4. Attach with a schedule and expectations.
--    The table you attach to is the first argument; name any other table explicitly.
ALTER TABLE my_db.sales.orders SET DATA_METRIC_SCHEDULE = '60 MINUTE';

ALTER TABLE my_db.sales.orders
  ADD DATA METRIC FUNCTION my_db.dq.invalid_amount_count ON (amount)
  EXPECTATION no_bad_amounts (VALUE = 0);

ALTER TABLE my_db.sales.orders
  ADD DATA METRIC FUNCTION my_db.dq.orphan_key_count
    ON (customer_id, TABLE (my_db.sales.customers(customer_id)))
  EXPECTATION no_orphans (VALUE = 0);

-- 5. Check status now
SELECT *
FROM TABLE(SYSTEM$EVALUATE_DATA_QUALITY_EXPECTATIONS(
       REF_ENTITY_NAME => 'my_db.sales.orders'));

-- Hide the body from other roles that can use it
ALTER FUNCTION my_db.dq.invalid_amount_count(TABLE(NUMBER(12,2))) SET SECURE;

-- Clean up: detach first, then drop
-- ALTER TABLE my_db.sales.orders DROP DATA METRIC FUNCTION my_db.dq.invalid_amount_count ON (amount);
-- DROP FUNCTION my_db.dq.invalid_amount_count(TABLE(NUMBER(12,2)));
```

## Notes
- Requires Enterprise Edition or higher. Attaching a DMF requires EXECUTE DATA METRIC FUNCTION on the account, USAGE on the custom DMF, and OWNERSHIP of the table.
- A DMF returns a NUMBER and its body is a single SELECT over the table arguments.
- The column types in `ON (...)` must match the DMF's argument types.
- A custom DMF can't be dropped while it is attached to a table. Find attachments with `INFORMATION_SCHEMA.DATA_METRIC_FUNCTION_REFERENCES`.
- For a simple foreign-key check, the system DMF `SNOWFLAKE.CORE.REFERENTIAL_INTEGRITY_COUNT` may be enough.

## References
- [Custom data metric functions](https://docs.snowflake.com/en/user-guide/data-quality-custom-dmfs)
- [CREATE DATA METRIC FUNCTION](https://docs.snowflake.com/en/sql-reference/sql/create-data-metric-function)
- [Use SQL to work with expectations](https://docs.snowflake.com/en/user-guide/data-quality-expectations)
