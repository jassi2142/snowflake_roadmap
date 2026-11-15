# Zero-copy Cloning

Zero-copy cloning creates a full, independent copy of a table, schema, or database almost instantly, without physically duplicating the data. The clone starts by pointing at the same stored data as the original, so you only pay extra storage when either copy changes. Teams use it to create test environments, run risky changes safely, and take point-in-time snapshots.

## How it works

Snowflake stores table data in immutable files called micro-partitions. A clone is a **metadata operation**: the new object references the same micro-partitions as the source. Nothing is copied at creation time, which is why cloning even a large database is fast and initially adds no storage cost.

After cloning, the two objects are fully independent:

- Changes to the clone do not affect the source, and vice versa.
- When either side inserts, updates, or deletes data, Snowflake writes new micro-partitions for that side only. You pay storage only for these changed portions.

You create a clone with `CREATE <object> <name> CLONE <source>`. Commonly cloned objects include databases, schemas, tables, dynamic tables, streams, and external stages; see the CREATE ... CLONE reference for the full list.

### Cloning with Time Travel

Add `AT` or `BEFORE` to clone an object as it existed in the past, within its Time Travel retention period. This is a common way to recover from a bad change: clone the table as it was before the mistake.

### What carries over

- **Grants:** cloning a database or schema copies the grants on child objects (tables, views, etc.), but not grants on the database or schema container itself. Cloning a single table does not copy its grants unless you append `COPY GRANTS` (which copies explicit privileges, but does not inherit future grants).
- **Sequences:** if a sequence is defined in the *same* database or schema being cloned, the sequence is cloned and the cloned table points to the cloned sequence; if defined in an external database/schema, or if only the table itself is cloned, the cloned table references the original source sequence.
- **Tasks and alerts:** clones of tasks and alerts start **suspended** by default to prevent unwanted jobs in test environments; resume them explicitly.
- **Streams:** when a schema or database containing tables and streams is cloned, unconsumed records in the cloned streams are inaccessible.
- **Foreign keys:** if parent and child tables reside in the same schema being cloned, the cloned child table's foreign key references the cloned parent table; otherwise, it references the original parent table.
- **Policies and tags:** a cloned table keeps its masking and row access policies and tag assignments. If the policy lives in the same schema or database being cloned, the clone points to the cloned policy.
- **Clustering:** automatic clustering is suspended on a cloned table until you run `ALTER TABLE ... RESUME RECLUSTER`.
- **Pipes:** pipes that reference internal stages are not cloned; cloned auto-ingest pipes start in a stopped state.
- **Stages:** files in table stages are not copied, and internal named stages are cloned only with `INCLUDE INTERNAL STAGES`.
- **Not cloned:** external tables and internal stages are not cloned when cloning schemas or databases.

## Example

Create a development copy of a production database in seconds:

```sql
CREATE DATABASE analytics_dev CLONE analytics_prod;
```

Clone a single table and keep its access grants:

```sql
CREATE TABLE sales.public.orders_test CLONE sales.public.orders COPY GRANTS;
```

Clone a table as it was one hour ago:

```sql
CREATE TABLE sales.public.orders_1h_ago CLONE sales.public.orders
  AT(OFFSET => -3600);
```

After cloning a schema that contains tasks, resume the ones you need:

```sql
CREATE SCHEMA etl_test CLONE etl;
ALTER TASK etl_test.load_orders RESUME;
```

## Best practices

- Use clones for dev and test environments instead of copying data with `CREATE TABLE AS SELECT`.
- Clone before risky operations, such as large updates or schema migrations, so you have an instant fallback.
- Drop clones you no longer need; once they diverge from the source, they hold their own storage.
- Review tasks, pipes, and alerts in cloned schemas before resuming them so test copies do not write to production targets.
- Avoid running DML or renaming objects in the source while a large clone is in progress.

## Common pitfalls

- Expecting clones to remain "free" forever; storage grows as either object changes.
- Forgetting to re-grant privileges on a cloned database or schema container.
- Cloning a schema with Time Travel to a point before a child table's retention allows, which makes the clone fail (`IGNORE TABLES WITH INSUFFICIENT DATA RETENTION` can skip those tables).
- Assuming files in table stages were copied along with the table.

## Learn more

- [Cloning considerations](https://docs.snowflake.com/en/user-guide/object-clone)
- [CREATE ... CLONE](https://docs.snowflake.com/en/sql-reference/sql/create-clone)

## Knowledge check

### You clone a 5 TB table. How much additional storage does the clone use immediately after creation?
- [ ] 5 TB
- [ ] About half, because of compression
- [x] Essentially none, because the clone shares the source's micro-partitions
- [ ] It depends on the warehouse size
> Cloning is a metadata operation; storage is only added later for data that changes in either object.

### After cloning a schema that contains scheduled tasks, why don't the tasks in the clone run?
- [ ] Tasks cannot be cloned
- [x] Cloned tasks are suspended by default and must be resumed
- [ ] Tasks only run in the source schema
- [ ] The clone has no warehouse
> Snowflake suspends tasks in a cloned database or schema so they do not run unexpectedly; you resume them with ALTER TASK ... RESUME.

### You cloned a single table, and analysts who could query the original get permission errors on the clone. What would have prevented this?
- [ ] Cloning the table with Time Travel
- [x] Adding COPY GRANTS to the CREATE TABLE ... CLONE statement
- [ ] Making the clone a transient table
- [ ] Running UNDROP on the clone
> Cloning a single table does not copy its grants by default; COPY GRANTS copies all privileges except OWNERSHIP to the new table.
