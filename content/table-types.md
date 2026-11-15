# Table Types

Snowflake has several kinds of tables. Permanent, transient, and temporary tables differ in how long they live and how much data protection they get. There are also special types, such as external, dynamic, hybrid, and Iceberg tables. Choosing the right type saves storage costs and makes sure important data is protected.

## How it works

**Permanent, transient, and temporary tables**

These three differ in their Time Travel and Fail-safe protection. Time Travel lets you query or restore past data. Fail-safe is a further recovery period that only Snowflake can use for disaster recovery.

| Type | Time Travel (days) | Fail-safe (days) | Lifetime |
| --- | --- | --- | --- |
| Permanent | 0 or 1 (Standard); 0 to 90 (Enterprise and higher) | 7 | Until dropped |
| Transient | 0 or 1 | 0 | Until dropped |
| Temporary | 0 or 1 | 0 | Ends with the session |

- **Permanent** is the default. Use it for long-lived, important data such as fact tables.
- **Transient** tables have no Fail-safe, so they cost less in storage. After the Time Travel period ends, Snowflake cannot recover them. Use them only for data you can recreate, such as ETL work tables.
- **Temporary** tables exist only for the session that created them. Other sessions cannot see them, and they are dropped when the session ends.

You must state transient or temporary explicitly: `CREATE [ OR REPLACE ] [ TEMPORARY | TRANSIENT ] TABLE ...`.

Historical data costs storage. Snowflake keeps only the information needed to restore changed or deleted rows, and keeps full copies only when a table is dropped or truncated.

**Other table types**

- **External tables** reference data files in cloud storage (a data lake) without loading them.
- **Iceberg tables** store data in Apache Iceberg format in external cloud storage.
- **Dynamic tables** keep the results of a query up to date automatically, based on a target freshness (target lag).
- **Hybrid tables** support transactional (row-oriented) workloads alongside analytics. They are not available on trial accounts, and they do not support some standard table features, such as clustering keys.

## Example

Create one of each core type:

```sql
CREATE TABLE sales_fact (id INT, amount NUMBER(12,2));           -- permanent
CREATE TRANSIENT TABLE stg_sales (id INT, amount NUMBER(12,2));  -- transient
CREATE TEMPORARY TABLE scratch (id INT);                         -- temporary

SHOW TABLES LIKE '%SALES%';
```

The `kind` column in the SHOW TABLES output shows the type of each table. Changing a permanent table to transient requires recreating it:

```sql
CREATE TRANSIENT TABLE sales_fact_t AS SELECT * FROM sales_fact;
-- re-apply grants, then:
DROP TABLE sales_fact;
ALTER TABLE sales_fact_t RENAME TO sales_fact;
```

## Best practices

- Keep business-critical, long-lived data in permanent tables so Fail-safe protects it.
- Use transient tables, or a transient database or schema, for staging and intermediate data you can rebuild.
- Use temporary tables for session-scoped scratch work in scripts and procedures.
- Consider how long it would take to reload lost data. Fail-safe can be worth its extra cost.

## Common pitfalls

- Storing important data in transient tables to save money, then being unable to recover it after an incident.
- Expecting a temporary table to still exist in another worksheet or a later session.
- Trying to change a table's type with ALTER. You must recreate the table.
- Forgetting to re-apply grants when you recreate a table as another type.

## Learn more

- [Working with temporary and transient tables](https://docs.snowflake.com/en/user-guide/tables-temp-transient)
- [Storage costs for Time Travel and Fail-safe](https://docs.snowflake.com/en/user-guide/data-cdp-storage-costs)

## Knowledge check

### A nightly job rebuilds a staging table from source files each run. Which type keeps storage cost lowest while remaining persistent?
- [ ] Permanent
- [x] Transient
- [ ] Temporary
- [ ] External
> Transient tables persist between sessions but have no Fail-safe, which avoids the extra storage cost for data that can be rebuilt.

### How many days of Fail-safe does a permanent table have?
- [ ] 0
- [ ] 1
- [x] 7
- [ ] 90
> Permanent tables have a 7-day Fail-safe period after Time Travel. Transient and temporary tables have none.

### A procedure creates a TEMPORARY table, and a separate session later tries to query it. What happens?
- [ ] The query succeeds if both sessions use the same role
- [x] The query fails, because temporary tables are visible only to the session that created them
- [ ] The table has been converted to transient
- [ ] The data is recovered from Fail-safe
> Temporary tables are session-scoped and are dropped when that session ends.
