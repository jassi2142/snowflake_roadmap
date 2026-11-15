# Access History & Lineage

Access History records, for every SQL statement, which objects and columns were read, which were written, which policies were enforced, and which DDL changed object definitions. Because each record links a user, a query, and specific columns, it serves both as an audit trail for compliance and as the raw material for column-level lineage and impact analysis. For architects, it is the primary system of record for "who touched this data, and where did it go?"

## How it works

Access History requires **Enterprise Edition or higher**. It is exposed through the `ACCESS_HISTORY` view in `SNOWFLAKE.ACCOUNT_USAGE` (and in `ORGANIZATION_USAGE`). In ACCOUNT_USAGE the view has a latency of up to about **3 hours** and retains data for **1 year**, so it is suited to auditing and analytics, not real-time alerting. Archive it to your own table if you need longer retention.

Each row represents one SQL statement. The key columns:

| Column | Meaning |
| --- | --- |
| `direct_objects_accessed` | Objects named in the query, such as a view and the view columns projected |
| `base_objects_accessed` | Underlying base tables and columns that actually supplied data, including filter and join columns |
| `objects_modified` | Write targets for INSERT, UPDATE, DELETE, MERGE, COPY, CTAS, with per-column `directSourceColumns` and `baseSourceColumns` |
| `object_modified_by_ddl` | DDL changes to databases, schemas, tables, views, columns, including setting policies and tags |
| `policies_referenced` | Masking and row access policies enforced, including policies on underlying objects in a view chain |
| `parent_query_id`, `root_query_id` | Link statements executed inside stored procedures back to the calling query |

The JSON arrays are nested, so analysis relies on `LATERAL FLATTEN`.

### Read lineage vs write lineage

- **Read side:** the split between direct and base objects answers both "which view did the analyst query?" and "which physical tables did that expose?" A column used only in a `WHERE` clause still appears in base objects, which matters for privacy audits.
- **Write side:** `objects_modified` records, for each target column, the source columns that produced it. Chaining these records over time yields column-level lineage across pipelines, which supports impact analysis (what breaks if I drop this column) and provenance (where did this value come from).

### Design considerations

- **Stored procedures and multi-statement requests** produce many rows; use `parent_query_id` and `root_query_id` to reassemble the logical operation.
- **Policy auditing:** `policies_referenced` lets governance teams prove a masking policy was in force for a given query without reconstructing policy history manually.
- **Cost and scale:** the view is large in busy accounts. Filter on `query_start_time` first, and materialize daily aggregates (for example, table popularity or unused columns) into your own tables.
- **Gaps:** access history describes SQL activity inside Snowflake. Lineage through external tools appears only if those tools act through Snowflake SQL or are integrated with Snowflake's lineage features.

## Example

Find which users read a sensitive column in the last 30 days, including through views:

```sql
SELECT ah.user_name,
       ah.query_start_time,
       obj.value:"objectName"::STRING  AS base_table,
       col.value:"columnName"::STRING  AS column_name
FROM snowflake.account_usage.access_history ah,
     LATERAL FLATTEN(ah.base_objects_accessed) obj,
     LATERAL FLATTEN(obj.value:"columns") col
WHERE ah.query_start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND obj.value:"objectName"::STRING = 'CRM.PUBLIC.CUSTOMERS'
  AND col.value:"columnName"::STRING = 'EMAIL';
```

Derive column-level write lineage: which source columns fed each target column:

```sql
SELECT ah.query_id,
       tgt.value:"objectName"::STRING AS target_table,
       tcol.value:"columnName"::STRING AS target_column,
       src.value:"objectName"::STRING AS source_object,
       src.value:"columnName"::STRING AS source_column
FROM snowflake.account_usage.access_history ah,
     LATERAL FLATTEN(ah.objects_modified) tgt,
     LATERAL FLATTEN(tgt.value:"columns") tcol,
     LATERAL FLATTEN(tcol.value:"directSourceColumns") src
WHERE ah.query_start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP());
```

List distinct masking policies enforced in queries:

```sql
SELECT DISTINCT p.value:"policyName"::STRING AS policy_name
FROM snowflake.account_usage.access_history ah,
     LATERAL FLATTEN(ah.policies_referenced) obj,
     LATERAL FLATTEN(obj.value:"columns") c,
     LATERAL FLATTEN(c.value:"policies") p;
```

## Best practices

- Always bound queries by `query_start_time`; full scans over a year of history are slow and expensive.
- Grant access through SNOWFLAKE database roles rather than broad IMPORTED PRIVILEGES where possible.
- Persist curated lineage edges and popularity metrics into governed tables for dashboards and longer retention.
- Use base objects, not direct objects, when the question is "was this physical data exposed?"

## Common pitfalls

- Expecting events to appear immediately; latency can be up to about three hours.
- Counting stored procedure activity incorrectly because child statements are separate rows.
- Assuming one year of history is kept forever; older records age out.
- Building lineage only from `direct_objects_accessed`, which misses the base tables behind views.

## Learn more

- [Access History](https://docs.snowflake.com/en/user-guide/access-history)
- [ACCESS_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/access_history)

## Knowledge check

### An analyst queried a view that filters a base table on an SSN column but does not project it. An auditor asks whether SSN was accessed. Where does Access History show this?
- [ ] Nowhere, because the column was not projected
- [ ] In direct_objects_accessed for the view
- [x] In base_objects_accessed, which includes columns used for filtering
- [ ] Only in QUERY_HISTORY query text
> Columns used to determine the result, such as WHERE clause columns, are recorded in base_objects_accessed even when not projected.

### Security wants an alert within minutes whenever someone reads a restricted table. Is ACCOUNT_USAGE.ACCESS_HISTORY a good primary source?
- [ ] Yes, it is updated in real time
- [x] Not on its own, because the view can lag by up to about three hours
- [ ] Yes, but only for Business Critical accounts
- [ ] No, because it does not record reads
> Access History is designed for audit and lineage analysis; its latency makes it unsuitable as the sole source for near-real-time alerting.

### You need to know which upstream columns produced a column in a reporting table loaded by INSERT ... SELECT. Which field gives this directly?
- [ ] policies_referenced
- [ ] object_modified_by_ddl
- [x] objects_modified, via each column's directSourceColumns
- [ ] parent_query_id
> For write operations, objects_modified lists each target column with the source columns that fed it, which is the basis for column-level lineage.
