# UNDROP

`UNDROP` brings back a table, schema, database, or certain other objects that were dropped, as long as they are still within their Time Travel retention period. It is the quickest fix for an accidental `DROP`: one command restores the object, its data, and its contents in place. It works because a dropped object is not deleted right away; Snowflake keeps it for the retention period.

## How it works

When you drop a table, schema, or database, Snowflake marks it as dropped and keeps it for the object's **data retention period** (1 day by default, up to 90 days on Enterprise Edition or higher for permanent objects). During that window you can restore it. After the window closes, the object moves into Fail-safe and `UNDROP` can no longer help.

Objects that support UNDROP include:

- Tables, dynamic tables, and Iceberg tables
- Schemas and databases
- Notebooks, tags, external volumes, and accounts

`UNDROP` restores the object to its **most recent state before the DROP**. Restoring a schema or database brings back the objects it contained.

### Finding dropped objects

Use the `HISTORY` keyword with `SHOW` commands. The output includes a `dropped_on` column; rows with a value there are dropped versions that can still be restored. If an object was dropped several times, each version appears as its own row.

```sql
SHOW TABLES HISTORY LIKE 'customers' IN SCHEMA crm.public;
SHOW SCHEMAS HISTORY IN DATABASE crm;
SHOW DATABASES HISTORY;
```

### Rules to remember

- **Name conflicts.** If an object with the same name already exists, `UNDROP` fails. Rename the existing object first.
- **Most recent version first.** `UNDROP` restores the most recently dropped version. To get an older version, restore and rename the newer ones first.
- **Privileges.** You need OWNERSHIP of the dropped object and the CREATE privilege for that object type in the target schema or database.
- **Location.** Tables and schemas are restored only in the current schema or database, even if you type a fully qualified name, so set your context with `USE` first.
- **Zero retention.** An object dropped while its retention was set to 0 cannot be undropped.
- **Child retention.** When you drop a whole database or schema, its children are kept for the parent's retention period, not their own.

## Example

A table was dropped by mistake and needs to come back:

```sql
USE SCHEMA crm.public;

DROP TABLE customers;           -- the mistake

UNDROP TABLE customers;         -- the fix

SELECT COUNT(*) FROM customers; -- data is back
```

Someone already created a new, empty `customers` table after the drop. Rename it, then restore the original:

```sql
USE SCHEMA crm.public;

ALTER TABLE customers RENAME TO customers_new_empty;
UNDROP TABLE customers;
```

Restore an entire schema or database:

```sql
UNDROP SCHEMA crm.staging;
UNDROP DATABASE crm;
```

Check how long a dropped object will be kept:

```sql
SHOW TABLES HISTORY IN SCHEMA crm.public
  ->> SELECT "name", "retention_time", "dropped_on"
      FROM $1
      WHERE "dropped_on" IS NOT NULL;
```

## Best practices

- Act quickly; with the default 1-day retention, you have only 24 hours.
- Run `SHOW ... HISTORY` before undropping so you know which version you are restoring.
- Avoid `CREATE OR REPLACE` on important tables in shared environments; it drops the old table and makes recovery more confusing.
- Keep a non-zero retention period on any object you might need to recover.
- Drop child tables explicitly before dropping a schema if you want their own longer retention to apply.

## Common pitfalls

- Trying `UNDROP` while a new object with the same name exists, and getting an error.
- Running `UNDROP` with a fully qualified name from another schema context and expecting it to restore elsewhere.
- Assuming `CREATE TABLE` with the original name brings the old data back; it creates a new, separate table.
- Forgetting that objects dropped after their retention expired cannot be recovered with `UNDROP`.

## Learn more

- [UNDROP](https://docs.snowflake.com/en/sql-reference/sql/undrop)
- [Understanding & using Time Travel](https://docs.snowflake.com/en/user-guide/data-time-travel)

## Knowledge check

### You run UNDROP TABLE sales and get an error that the object already exists. What should you do?
- [ ] Wait for the retention period to end
- [x] Rename the existing sales table, then run UNDROP TABLE sales again
- [ ] Use CREATE TABLE sales CLONE sales
- [ ] Contact Snowflake Support for Fail-safe recovery
> UNDROP fails when an object with the same name exists; renaming the current object frees the name so the dropped version can be restored.

### The table events was dropped, recreated, and dropped again. Which version does UNDROP TABLE events restore first?
- [ ] The oldest dropped version
- [x] The most recently dropped version
- [ ] Both versions merged together
- [ ] Neither; you must specify a timestamp
> UNDROP restores the most recent dropped version; to reach older versions you rename restored tables and undrop again.

### A table had DATA_RETENTION_TIME_IN_DAYS = 0 and was dropped an hour ago. Can you undrop it?
- [ ] Yes, UNDROP always works for 24 hours
- [ ] Yes, but only with ACCOUNTADMIN
- [x] No, an object with no retention period cannot be restored with UNDROP
- [ ] Only if it was in a transient schema
> A retention period of 0 disables Time Travel for the object, so there is nothing for UNDROP to restore.
