# Time Travel

Time Travel lets you look at, copy, or restore data as it existed at an earlier point in time. If someone deletes the wrong rows, runs a bad update, or drops a table, you can query the old version or bring it back with plain SQL, without asking anyone for a backup. It is one of the most useful safety nets in Snowflake and requires no setup to start using.

## How it works

Whenever data in a table changes, Snowflake keeps the previous version for a period called the **data retention period**. During that period you can:

- **Query** historical data with the `AT` or `BEFORE` clause.
- **Clone** a table, schema, or database as it was at a past moment.
- **Restore** dropped tables, schemas, and databases with `UNDROP`.

You point to the moment you want in one of three ways:

- `TIMESTAMP` - a specific date and time.
- `OFFSET` - a number of seconds back from now (for example `-3600` for one hour ago).
- `STATEMENT` - a query ID; `BEFORE(STATEMENT => ...)` shows the data just before that query ran.

### Retention periods

| Edition and object type | Retention allowed |
| --- | --- |
| Standard Edition (any object) | 0 or 1 day |
| Enterprise Edition or higher, permanent objects | 0 to 90 days |
| Enterprise Edition or higher, transient and temporary objects | 0 or 1 day |

The default is **1 day**, and it is enabled automatically. You set the retention with the `DATA_RETENTION_TIME_IN_DAYS` parameter on the account, a database, a schema, or a table. Lower levels inherit from higher levels unless they set their own value. Setting it to 0 turns Time Travel off for that object. An administrator can also set `MIN_DATA_RETENTION_TIME_IN_DAYS` on the account to enforce a minimum.

Retention is counted from **when each change happens**, not from when the table was created. When the period ends, the old data moves into **Fail-safe** (for permanent tables), where only Snowflake Support can recover it.

Keeping history costs storage. Longer retention on tables that change often means more stored versions and a higher bill.

## Example

See the data as it was 5 minutes ago:

```sql
SELECT * FROM orders AT(OFFSET => -60*5);
```

See the data just before a mistaken DELETE, using that query's ID:

```sql
SELECT * FROM orders
  BEFORE(STATEMENT => '8e5d0ca9-005e-44e6-b858-a8f5b37c5726');
```

Recover from the mistake by cloning the table as it was before the DELETE, then swapping it in:

```sql
CREATE TABLE orders_restored CLONE orders
  BEFORE(STATEMENT => '8e5d0ca9-005e-44e6-b858-a8f5b37c5726');

ALTER TABLE orders SWAP WITH orders_restored;
```

Set a longer retention on an important table (Enterprise Edition or higher) and check it:

```sql
ALTER TABLE orders SET DATA_RETENTION_TIME_IN_DAYS = 30;

SHOW TABLES LIKE 'ORDERS';  -- see the retention_time column
```

## Best practices

- Keep at least 1 day of retention on every object; Snowflake recommends against setting it to 0 at the account level.
- Use longer retention only for critical tables where the recovery value justifies the storage cost.
- Use transient tables with short retention for staging data you can easily reload.
- When something goes wrong, find the query ID in query history and use `BEFORE(STATEMENT => ...)` for a precise restore point.

## Common pitfalls

- Waiting too long: once the retention period passes, Time Travel can no longer help.
- Setting a schema to 90 days but a table inside it to 1 day, then being surprised the table's history is shorter.
- Changing a schema's retention and expecting it to affect tables that were already dropped; dropped objects keep the retention they had.
- Assuming Time Travel queries use the old table structure; they use the current column definitions.

## Learn more

- [Understanding & using Time Travel](https://docs.snowflake.com/en/user-guide/data-time-travel)
- [AT | BEFORE](https://docs.snowflake.com/en/sql-reference/constructs/at-before)

## Knowledge check

### A colleague ran an UPDATE that overwrote a column 20 minutes ago. The table has the default retention. What is the most precise way to see the data before that update?
- [ ] Ask Snowflake Support to recover it from Fail-safe
- [x] Query the table with BEFORE(STATEMENT => '<query_id of the UPDATE>')
- [ ] Use UNDROP TABLE
- [ ] Query the table with AT(OFFSET => -86400)
> BEFORE with the statement's query ID returns the table exactly as it was immediately before that UPDATE ran.

### Your account is on Standard Edition. What is the longest Time Travel retention you can set on a permanent table?
- [ ] 0 days
- [x] 1 day
- [ ] 7 days
- [ ] 90 days
> Standard Edition allows only 0 or 1 day; up to 90 days requires Enterprise Edition or higher for permanent objects.

### When does a changed row's Time Travel window end?
- [ ] One retention period after the table was created
- [ ] At midnight UTC each day
- [x] One retention period after the change was made
- [ ] When the next change happens to the same row
> Retention is counted per change: end of Time Travel equals the time of the change plus the retention period.
