# SnowPro Quick Syntax & Cheat Sheet

A comprehensive, high-yield reference guide and syntax cheat sheet for the Snowflake SnowPro Core and Advanced certification exams. It condenses the essential DDL/DML commands, architecture rules, edition differences, and tricky exam edge cases into a rapid revision handbook.

## How it works

The SnowPro certification tests both architectural principles and exact syntax behavior. This cheat sheet organizes the core knowledge areas into quick-recall rules.

### 1. Architecture & Editions Matrix

Snowflake is a hybrid shared-disk and shared-nothing columnar database built from three independent layers:
- **Database Storage:** Remote cloud object storage (S3, GCS, Azure Blob). Stores encrypted, immutable, proprietary micro-partitions (50 MB–500 MB uncompressed).
- **Virtual Warehouses (Compute):** Independent, multi-node MPP clusters running on cloud virtual machines. Contains a local SSD cache that is **purged when the warehouse suspends**.
- **Cloud Services:** Global coordinator (stateless compute) managing authentication, RBAC, query compilation, metadata optimization, and the **24-hour Result Cache**.

| Feature / Capability | Standard | Enterprise | Business Critical | VPS |
| :--- | :--- | :--- | :--- | :--- |
| **Time Travel** | 1 day | Up to 90 days | Up to 90 days | Up to 90 days |
| **Multi-Cluster Warehouses** | No | Yes (concurrency scale-out) | Yes | Yes |
| **Materialized Views** | No | Yes | Yes | Yes |
| **Customer-Managed Keys (Tri-Secret)** | No | No | Yes | Yes |
| **PrivateLink Support** | No | Add-on | Yes (native) | Yes |
| **Compliance (HIPAA, PCI-DSS)** | No | No | Yes | Yes |
| **Dedicated Metadata Layer** | No (shared) | No (shared) | No (shared) | Yes (isolated) |

### 2. High-Yield Exam Rules & Edge Cases

- **Table Types & Fail-safe:**
  - *Permanent:* Default. 0–90 days Time Travel (1 day for Standard) + **7-day non-configurable Fail-safe**.
  - *Transient:* 0 or 1 day Time Travel; **0 days Fail-safe**.
  - *Temporary:* Session-scoped. 0 or 1 day Time Travel; **0 days Fail-safe**. Hidden duplicate names take precedence within session.
- **Zero-Copy Cloning Caveats:**
  - *Tasks & Alerts:* Start **suspended** in the clone; resume explicitly.
  - *Sequences:* If the sequence is in the *same* schema being cloned, the sequence is cloned; if in a *different* schema or only the table is cloned, the clone references the source sequence.
  - *Stages & Tables:* Internal named stages and external tables are **not cloned**.
  - *Grants:* Cloning a table does not copy grants unless `COPY GRANTS` is appended. `COPY GRANTS` does not inherit future grants.
- **Caching Mechanics:**
  - *Result Cache:* Retained for **24 hours** from first execution; each reuse resets the timer up to **31 days**. Does not require a running warehouse. Reuse requires exact syntax match, identical privileges, no runtime evaluation functions (e.g. `CURRENT_TIMESTAMP`), and unchanged micro-partitions.
  - *Warehouse Cache:* Local SSD storage on virtual warehouse nodes; **dropped completely on suspend**.
  - *Metadata Cache:* Answers `COUNT(*)`, `MIN()`, and `MAX()` without spinning up a warehouse.
- **Data Types & Storage:**
  - `NUMBER(p, s)`: Precision ($p \le 38$) does **not** increase storage; scale ($s$) does affect compression and storage.
  - `VARCHAR`: Default length is 16 MB if unstated.
  - Delimiters: Both single quotes `'string'` and dollar signs `$$string with 'quote'$$` are supported.
  - Intervals: Order of addition matters across leap years (`+ INTERVAL '1 day, 1 year'` $\ne$ `+ INTERVAL '1 year, 1 day'`).

## Example

Essential DDL and administrative syntax frequently tested on the exam:

```sql
-- 1. Create Transient Table from Clone
CREATE OR REPLACE TRANSIENT TABLE stg_orders CLONE prod.public.orders COPY GRANTS;

-- 2. Stage Definition with Directory Table
CREATE OR REPLACE STAGE incoming_files_stage
  URL = 's3://company-landing/raw/'
  STORAGE_INTEGRATION = s3_int
  DIRECTORY = (ENABLE = TRUE, AUTO_REFRESH = TRUE);

-- Refresh directory metadata manually if needed
ALTER STAGE incoming_files_stage REFRESH;

-- 3. Ingestion with validation and purge
COPY INTO orders
FROM @incoming_files_stage
FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1)
ON_ERROR = 'CONTINUE'
PURGE = TRUE;

-- 4. Result Reuse via RESULT_SCAN without re-running query
SHOW TABLES IN SCHEMA prod.public;
SELECT * FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "rows" > 100000;

-- 5. CDC Stream and Triggered Serverless Task
CREATE OR REPLACE STREAM orders_stream ON TABLE orders;

CREATE OR REPLACE TASK process_orders_task
  USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'XSMALL'
  SCHEDULE = '5 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('orders_stream')
AS
  MERGE INTO orders_target t USING orders_stream s ON t.id = s.id
  WHEN MATCHED AND s.METADATA$ACTION = 'DELETE' THEN DELETE
  WHEN MATCHED THEN UPDATE SET t.status = s.status
  WHEN NOT MATCHED AND s.METADATA$ACTION = 'INSERT' THEN INSERT VALUES (s.id, s.status);

ALTER TASK process_orders_task RESUME;
```

## Best practices

- Memorize the edition requirements: Enterprise is required for Multi-Cluster Warehouses, 90-day Time Travel, and Materialized Views; Business Critical is required for HIPAA/PCI and Tri-Secret Secure.
- Use `COPY GRANTS` whenever cloning production tables into test schemas to retain existing role access.
- Prefer Transient tables for staging layers to avoid paying 7-day Fail-safe storage fees on intermediate data.
- Run `PUT` and `GET` exclusively from client tools (SnowSQL, CLI, Python connector); they do not execute in browser worksheets.

## Common pitfalls

- Assuming `PUT` works in Snowsight worksheets; it is a client-side command requiring local filesystem access.
- Confusing scaling up (resizing to a larger warehouse for single large queries) with scaling out (adding clusters to a multi-cluster warehouse for concurrency).
- Expecting cloned tasks to run immediately; they are created in a suspended state by design.
- Forgetting that the Warehouse SSD cache is completely erased when `AUTO_SUSPEND` triggers.

## Learn more

- [Snowflake Architecture & Overview](https://docs.snowflake.com/en/user-guide/intro-key-concepts)
- [Snowflake Editions Reference](https://docs.snowflake.com/en/user-guide/intro-editions)
- [Object Cloning Considerations](https://docs.snowflake.com/en/user-guide/object-clone)

## Knowledge check

### You clone a production schema containing tables, a sequence, and several automated tasks into a staging environment. What is the initial state of the cloned tasks and sequence?
- [ ] Tasks run immediately on schedule; the cloned tables point to the original production sequence
- [x] Tasks are created in a suspended state; because the sequence is in the same cloned schema, the cloned tables reference the newly cloned sequence
- [ ] Tasks are suspended; internal stages and external tables in the schema are cloned with Time Travel
- [ ] Tasks are dropped; the sequence is converted to a static numeric column
> Cloned tasks and alerts are always created suspended. When an entire schema or database is cloned, child sequences within it are cloned alongside their tables, and cloned tables reference the new cloned sequence.

### Which edition of Snowflake is the MINIMUM requirement to configure Tri-Secret Secure (customer-managed encryption keys) and HIPAA compliance?
- [ ] Standard Edition
- [ ] Enterprise Edition
- [x] Business Critical Edition
- [ ] Virtual Private Snowflake (VPS)
> Business Critical Edition (formerly Enterprise for Sensitive Data) is the minimum tier providing customer-managed encryption keys (Tri-Secret Secure), HIPAA support, and PCI-DSS compliance.

### A query executes in 25 seconds. If the exact same query is submitted 5 minutes later by another user with the same role, and the warehouse has remained suspended, how will Snowflake execute it?
- [ ] The query fails because the warehouse is suspended and cannot process SQL
- [ ] The virtual warehouse resumes, re-reads data from local SSD cache, and completes in 2 seconds
- [x] Snowflake returns the result from the Cloud Services Result Cache in milliseconds without resuming the warehouse
- [ ] The query must run on a multi-cluster warehouse to leverage cached query profiles
> Persisted query results in the Result Cache live in the Cloud Services layer and are retained for 24 hours. If underlying micro-partitions and query syntax are unchanged, results are returned without requiring warehouse compute.
