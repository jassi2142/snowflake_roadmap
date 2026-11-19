# Openflow

Snowflake Openflow is a fully managed data integration and streaming ingestion service built on Apache NiFi. It captures, routes, transforms, and loads structured and unstructured data from hundreds of enterprise sources—including relational databases via Change Data Capture (CDC), SaaS applications, Kafka event streams, and cloud document repositories—into Snowflake tables, Apache Iceberg tables, and downstream Dynamic Tables without requiring a separate third-party ETL/ELT platform.

## How it works

Openflow separates a Snowflake-managed **control plane** from an isolated, secure **data plane** where flows actually execute.

### 1. Architecture & Deployment Models

- **Deployment**: The underlying compute infrastructure hosting flow runtimes:
  - **Snowflake Deployment (SPCS)**: Runtimes execute inside Snowpark Container Services compute pools managed within Snowflake's security perimeter. Fully available across AWS, Azure, and GCP commercial regions.
  - **Bring Your Own Cloud (BYOC)**: The data plane runs inside the customer's private VPC (managed Kubernetes cluster) while Snowflake orchestrates the control plane. Designed for stringent data sovereignty, zero-egress policies, or on-premises networks reachable only via private VPC peering.
- **Data Connectivity Proxy**: A lightweight, outbound-only reverse proxy agent deployed in private data centers or on-premises networks. It connects internal databases (such as Oracle, Microsoft SQL Server, PostgreSQL, and MySQL) securely to Openflow runtimes over TLS without opening inbound firewall ports or configuring complex VPNs.
- **Runtimes & Flow Canvas**: A runtime is a scalable NiFi processing engine. In Snowsight, data engineers use an interactive visual flow canvas to configure FlowFiles, processor groups, transformations, and backpressure queue thresholds.
- **Connector Catalog**: Pre-packaged, zero-maintenance connectors for common enterprise sources (PostgreSQL CDC, Oracle CDC, MySQL CDC, SQL Server CDC, Salesforce, ServiceNow, Kafka, S3, Google Drive, SharePoint).

### 2. Gen 2 First-Class SQL Architecture

Openflow Gen 2 organizes all resources as native, schema-scoped Snowflake objects governed by standard Role-Based Access Control (RBAC):
- `CREATE OPENFLOW DEPLOYMENT` (Account-level object)
- `CREATE OPENFLOW RUNTIME ... IN DEPLOYMENT` (Schema-scoped object)
- `CREATE OPENFLOW CONNECTOR` (Schema-scoped object with declarative, versioned JSON configuration)

Gen 2 connector configurations can be managed as versioned code artifacts, stored in Git repositories, and promoted across environments using CI/CD pipelines.

### 3. CDC Ingestion into Dynamic Tables & Iceberg

Openflow captures insert, update, and delete operations from transactional database transaction logs in near real-time:
1. Openflow streams raw CDC records into a Bronze/landing table (including change metadata such as operation type and source commit timestamps).
2. A downstream **Dynamic Table** consumes the raw landing table with a target lag (e.g. `TARGET_LAG = '1 MINUTE'`), automatically handling deduplication, merges, and state reconstruction for analytics-ready Silver and Gold layers.
3. Openflow natively supports landing data directly into **Apache Iceberg tables** stored on external cloud storage (Amazon S3, Azure Blob, or Google Cloud Storage) backed by Snowflake Polaris or internal catalogs.

### 4. Security, Identity & Costs

- **Authentication**: Runtimes authenticate via **Snowflake Managed Tokens** (SPCS session tokens in Snowflake deployments; workload identity federation in BYOC), eliminating hard-coded credentials.
- **Execute-As Role**: Connectors inherit an `EXECUTE AS` role defining granular read/write privileges on target databases, schemas, and warehouses.
- **Secondary Roles**: Users must have `DEFAULT_SECONDARY_ROLES = ('ALL')`. Openflow cannot be operated while `ACCOUNTADMIN`, `ORGADMIN`, or `SECURITYADMIN` is active.
- **Cost Management**: Snowflake deployments consume credits based on the SPCS compute pool instance family and uptime. Runtimes can be suspended (`ALTER OPENFLOW RUNTIME ... SUSPEND`) and resumed programmatically to save credits during off-peak hours.

## Example

### Configuring a Gen 2 Deployment and Runtime

```sql
USE ROLE openflow_admin;

-- 1. Create a schema-scoped Gen 2 Runtime in an existing deployment
CREATE OPENFLOW RUNTIME cdc_db.ingestion.postgres_cdc_runtime
  IN DEPLOYMENT prod_openflow_deployment
  EXECUTE AS ROLE cdc_ingest_role
  COMMENT = 'High-throughput CDC runtime for production transactional DB';

-- 2. Verify runtime health and readiness
SHOW OPENFLOW RUNTIMES IN SCHEMA cdc_db.ingestion;

-- 3. Pair Openflow Bronze landing with an automated Dynamic Table
CREATE OR REPLACE DYNAMIC TABLE cdc_db.silver.customers_curated
  TARGET_LAG = '2 MINUTES'
  WAREHOUSE = transform_wh
AS
  SELECT
    payload:id::INT          AS customer_id,
    payload:name::STRING     AS full_name,
    payload:email::STRING    AS email_address,
    payload:updated_at::TIMESTAMP_NTZ AS last_modified
  FROM cdc_db.ingestion.raw_customers_cdc
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY payload:id
    ORDER BY payload:updated_at DESC
  ) = 1;
```

### Safely Draining and Decommissioning a Runtime

```sql
-- Suspend runtime and wait for in-flight flow queues to drain
ALTER OPENFLOW RUNTIME cdc_db.ingestion.postgres_cdc_runtime SUSPEND;
SELECT SYSTEM$WAIT_FOR_STABLE_OPENFLOW_RUNTIMES(600, 'cdc_db.ingestion.postgres_cdc_runtime');

-- Terminate and remove
ALTER OPENFLOW RUNTIME cdc_db.ingestion.postgres_cdc_runtime TERMINATE;
SELECT SYSTEM$WAIT_FOR_STABLE_OPENFLOW_RUNTIMES(600, 'cdc_db.ingestion.postgres_cdc_runtime');
DROP OPENFLOW RUNTIME cdc_db.ingestion.postgres_cdc_runtime;
```

## Best practices

- Use the **Data Connectivity Proxy** when capturing CDC data from on-premises databases to avoid opening public inbound firewall ports.
- Separate runtimes per business domain or environment (Dev, Test, Prod) so heavy streaming pipelines do not impact critical operational connectors.
- Stream CDC data into raw append-only landing tables, and let Dynamic Tables handle state merging and SCD2 logic.
- Manage connector configuration files in Git repositories and deploy them via the Snowflake CLI or Python APIs.
- Monitor backpressure thresholds and queue depth in the Snowsight Openflow canvas to identify slow downstream merges before queues fill.

## Common pitfalls

- Attempting to administer Openflow while `ACCOUNTADMIN` is the active role, which triggers policy errors.
- Forgetting to grant runtime-level privileges; in Gen 2, `USAGE` on a deployment does not grant privileges on child runtimes.
- Using `TERMINATE FORCE` instead of `TERMINATE`, which can drop uncommitted in-flight CDC messages from queues.
- Neglecting to set `DEFAULT_SECONDARY_ROLES = ('ALL')` on administrative user accounts.

## Learn more

- [Snowflake Openflow Overview](https://docs.snowflake.com/en/user-guide/data-integration/openflow/about)
- [Openflow Gen 2 Architecture](https://docs.snowflake.com/en/user-guide/data-integration/openflow/gen2/openflow-generations)
- [Data Connectivity Proxy Setup](https://docs.snowflake.com/en/user-guide/data-integration/openflow/setup-openflow-byoc)

## Knowledge check

### An enterprise must stream change data capture (CDC) from an on-premises Oracle database inside a private corporate data center into Snowflake without opening inbound firewall ports or configuring public IPs. Which solution fits best?
- [ ] Direct Snowpipe over public internet endpoints
- [x] Snowflake Openflow with the Data Connectivity Proxy deployed in the on-premises network
- [ ] An external stage pointing to a public AWS S3 bucket
- [ ] Scheduled Python UDFs executing continuous polling queries
> The Data Connectivity Proxy establishes a secure, outbound-only TLS tunnel from the on-premises private network to Openflow, enabling continuous database CDC without opening inbound firewall rules.

### How does Openflow Gen 2 improve pipeline governance and CI/CD compared to Gen 1?
- [ ] Gen 2 eliminates the need for SPCS compute pools
- [x] Deployments, runtimes, and connectors are first-class SQL objects with schema scoping and version-controlled declarative configurations
- [ ] Gen 2 requires ACCOUNTADMIN to configure every connector
- [ ] Gen 2 stores data strictly in temporary tables
> Gen 2 represents runtimes and connectors as first-class, schema-scoped Snowflake objects that can be versioned, scripted in SQL, and promoted through CI/CD pipelines with granular RBAC.

### What is the recommended architectural pattern for landing Openflow CDC streams and keeping downstream analytical models fresh?
- [ ] Write directly from Openflow into final reporting views using multi-statement transactions
- [x] Stream raw CDC changes into an append-only landing table and use Dynamic Tables with target lag to maintain curated tables
- [ ] Recreate the entire table hourly using CREATE TABLE AS SELECT
- [ ] Trigger manual stored procedures on every individual record
> Streaming CDC into a raw landing table and having Dynamic Tables incrementally merge changes with a target lag provides a resilient, automated medallion ELT pipeline with zero manual pipeline orchestration.
