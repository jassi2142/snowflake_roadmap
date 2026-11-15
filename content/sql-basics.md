# SQL Essentials

SQL (Structured Query Language) is the main way to work with data in Snowflake. With a small set of commands you can create objects, load and change data, and ask questions of it. Snowflake supports standard SQL, including most DDL and DML defined in SQL:1999, so these skills carry over to other databases.

## How it works

SQL statements fall into a few groups:

- **DDL (Data Definition Language)** creates and changes objects: `CREATE`, `ALTER`, `DROP`, `SHOW`, `DESCRIBE`.
- **DML (Data Manipulation Language)** changes data: `INSERT`, `UPDATE`, `DELETE`, `MERGE`, plus `COPY INTO` for bulk loading.
- **Queries** read data with `SELECT`.
- **DCL (Data Control Language)** manages access: `GRANT` and `REVOKE`.

A `SELECT` query is built from clauses. They are evaluated in roughly this logical order:

1. `FROM` / `JOIN`: which tables to read and how to combine them
2. `WHERE`: filter rows
3. `GROUP BY`: group rows for aggregation (`SUM`, `COUNT`, `AVG`)
4. `HAVING`: filter groups
5. `SELECT`: choose and compute output columns
6. `ORDER BY`: sort the result
7. `LIMIT`: return only the first N rows

Other things to know when you start:

- **Context.** Before you query, set a role, a warehouse (for compute), a database, and a schema. You can also use fully qualified names: `database.schema.table`.
- **Identifiers.** Unquoted names are stored in uppercase and matched case-insensitively. Names in double quotes keep their exact case.
- **NULL** means "unknown". Use `IS NULL` instead of `= NULL`.
- **Ordering.** Without `ORDER BY`, the order of rows in a result is not guaranteed.
- **Joins.** `INNER JOIN` keeps only rows that match; `LEFT JOIN` keeps every row from the left table.

## Example

This creates a table, adds a few rows, and summarizes them.

```sql
USE WAREHOUSE learn_wh;
CREATE DATABASE IF NOT EXISTS learn_db;
USE SCHEMA learn_db.public;

CREATE OR REPLACE TABLE orders (
  order_id   INTEGER,
  customer   VARCHAR,
  amount     NUMBER(10,2),
  order_date DATE
);

INSERT INTO orders VALUES
  (1, 'Ana',  120.00, '2026-10-01'),
  (2, 'Ben',   75.50, '2026-10-02'),
  (3, 'Ana',   42.25, '2026-10-05');

SELECT customer, COUNT(*) AS orders, SUM(amount) AS total
FROM orders
WHERE order_date >= '2026-10-01'
GROUP BY customer
HAVING SUM(amount) > 50
ORDER BY total DESC;
```

This joins the orders table to the sample customer data. The `LIMIT` keeps the output small.

```sql
SELECT o.order_id, o.amount, c.c_mktsegment
FROM orders o
LEFT JOIN snowflake_sample_data.tpch_sf1.customer c
  ON c.c_custkey = o.order_id
LIMIT 10;
```

## Best practices

- Name columns explicitly instead of using `SELECT *` on large tables. Snowflake stores data by column, so fewer columns means less data scanned.
- Always add `ORDER BY` when the order of results matters.
- Use fully qualified names in scripts so they work whatever the session context is.
- Use `LIMIT` when you are exploring data.

## Common pitfalls

- Comparing with `= NULL`, which never returns true.
- Using double-quoted mixed-case names, and then having to quote them in every later query.
- Putting aggregate conditions in `WHERE` instead of `HAVING`.
- Forgetting to select a warehouse, so queries cannot run.

## Learn more

- [SQL command reference](https://docs.snowflake.com/en/sql-reference-commands)
- [SELECT](https://docs.snowflake.com/en/sql-reference/sql/select)

## Knowledge check

### You want only customers whose total spend is greater than 100. Where does the condition `SUM(amount) > 100` go?
- [ ] WHERE
- [x] HAVING
- [ ] ORDER BY
- [ ] FROM
> HAVING filters groups after aggregation. WHERE filters individual rows before grouping.

### A table is created as `CREATE TABLE "Sales" (...)`. Which query finds it?
- [ ] `SELECT * FROM sales;`
- [ ] `SELECT * FROM SALES;`
- [x] `SELECT * FROM "Sales";`
- [ ] Any of the above
> Double-quoted identifiers keep their case, so the name must be quoted exactly. Unquoted names are converted to uppercase.

### A query returns rows in a different order each time it runs. Why?
- [ ] The warehouse is unstable
- [x] There is no ORDER BY, so row order is not guaranteed
- [ ] The result cache is corrupted
- [ ] The table needs a clustering key
> SQL results have no defined order unless ORDER BY is specified.
