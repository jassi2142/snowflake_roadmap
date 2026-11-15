# Catalog Integrations

A catalog integration is an account-level Snowflake object that describes how to reach the catalog that tracks an Apache Iceberg (or Delta) table's metadata when Snowflake is not the catalog. It is the key building block for interoperating with AWS Glue, Snowflake Open Catalog, Databricks Unity Catalog, other Iceberg REST catalogs, plain metadata files in object storage, and Delta Sharing. Choosing the right integration and access pattern determines whether Snowflake can only read external tables or can participate as a full read-write engine.

## How it works

You need a catalog integration to create an Iceberg table that uses an external catalog, to create a table from metadata files in object storage, to integrate with Snowflake Open Catalog, to use an Iceberg REST catalog, or to access Iceberg tables in another Snowflake account through Horizon Catalog. One integration can serve many tables.

`CREATE CATALOG INTEGRATION` takes a `CATALOG_SOURCE` and `TABLE_FORMAT`. Common patterns:

- **Iceberg REST** (`CATALOG_SOURCE = ICEBERG_REST`): a `REST_CONFIG` block with `CATALOG_URI`, an optional `CATALOG_API_TYPE` (for example, `AWS_GLUE` for the Glue Iceberg REST endpoint), and `CATALOG_NAME`; plus a `REST_AUTHENTICATION` block (for example, `TYPE = SIGV4` with an IAM role, or OAuth or bearer tokens for other catalogs).
- **AWS Glue** (classic Glue integration) and **object storage** (metadata files without a catalog service), each with dedicated syntax.
- **Delta** sources, used with `TABLE_FORMAT = DELTA` for Delta table files.

**Trust setup for AWS.** After creating a Glue-backed integration, `DESCRIBE CATALOG INTEGRATION` returns `GLUE_AWS_IAM_USER_ARN` and `GLUE_AWS_EXTERNAL_ID`, which you add to the IAM role's trust policy. Snowflake provisions a single IAM user for all Glue integrations in an account. Recreating the integration produces a new external ID, and Snowflake does not validate permissions until you create a table that uses the integration.

**Storage access is separate.** The catalog integration resolves metadata; data access comes from an external volume or from **catalog-vended credentials**, where the catalog issues short-lived storage credentials.

**Catalog-linked databases.** `CREATE DATABASE ... LINKED_CATALOG = (CATALOG = '<integration>', ...)` links a database to a remote Iceberg REST catalog. Snowflake discovers and syncs namespaces and tables automatically, controlled by options such as `ALLOWED_NAMESPACES`, `BLOCKED_NAMESPACES`, `ALLOWED_WRITE_OPERATIONS`, `NAMESPACE_MODE`, and `SYNC_INTERVAL_SECONDS`. `CATALOG_CASE_SENSITIVITY` must match the remote catalog: Open Catalog is case-sensitive, while Glue and Unity Catalog are case-insensitive. You can read and write tables in the linked catalog while keeping it the source of truth.

**Defaults.** The `CATALOG` parameter can be set at the account, database, or schema level (the lowest scope wins), so new Iceberg tables pick up the integration automatically. Changes apply only to tables created afterwards, and a role needs `USAGE` on the integration.

## Example

Create a Glue Iceberg REST integration with SigV4, then link a database to it.

```sql
CREATE CATALOG INTEGRATION glue_rest_int
  CATALOG_SOURCE = ICEBERG_REST
  TABLE_FORMAT = ICEBERG
  CATALOG_NAMESPACE = 'analytics'
  REST_CONFIG = (
    CATALOG_URI = 'https://glue.us-west-2.amazonaws.com/iceberg'
    CATALOG_API_TYPE = AWS_GLUE
    CATALOG_NAME = '123456789012'
  )
  REST_AUTHENTICATION = (
    TYPE = SIGV4
    SIGV4_IAM_ROLE = 'arn:aws:iam::123456789012:role/snowflake-glue'
    SIGV4_SIGNING_REGION = 'us-west-2'
  )
  ENABLED = TRUE;

DESCRIBE CATALOG INTEGRATION glue_rest_int;

CREATE DATABASE glue_lake
  LINKED_CATALOG = (
    CATALOG = 'glue_rest_int',
    ALLOWED_NAMESPACES = ('analytics')
  ),
  EXTERNAL_VOLUME = 'lake_rw_vol'
  CATALOG_CASE_SENSITIVITY = CASE_INSENSITIVE;
```

Govern access to the linked tables with a database role.

```sql
CREATE DATABASE ROLE glue_lake.analyst;
GRANT USAGE ON SCHEMA glue_lake.analytics TO DATABASE ROLE glue_lake.analyst;
GRANT SELECT ON ALL ICEBERG TABLES IN SCHEMA glue_lake.analytics TO DATABASE ROLE glue_lake.analyst;
GRANT DATABASE ROLE glue_lake.analyst TO ROLE data_consumer;
```

## Best practices

- Prefer Iceberg REST plus catalog-linked databases over per-table registration; you avoid metadata drift and manual refresh.
- Scope links with `ALLOWED_NAMESPACES` so Snowflake only exposes what each domain needs.
- Decide the system of record explicitly: an external catalog for multi-engine ownership, or Snowflake as catalog (with `CONVERT TO MANAGED`) when Snowflake becomes the primary writer.
- Use vended credentials where the catalog supports them to centralize storage authorization in the catalog.
- Set default `CATALOG` parameters at the database or schema level to standardize table creation.
- Treat `CREATE OR REPLACE` on integrations as a breaking change that requires trust-policy updates.

## Common pitfalls

- Assuming the integration grants data access; without an external volume or vended credentials, queries fail.
- Setting the wrong `CATALOG_CASE_SENSITIVITY` and then being unable to resolve mixed-case identifiers.
- Assuming a successful `CREATE CATALOG INTEGRATION` proves permissions; validation happens on first table use.
- Using Lake Formation without granting `lakeformation:GetDataAccess` and data permissions to the role.
- Changing a database's default `CATALOG` and expecting existing tables to switch.

## Learn more

- [Configure a catalog integration](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration)
- [Catalog integration for Iceberg REST catalogs](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-rest)
- [CREATE DATABASE (catalog-linked)](https://docs.snowflake.com/en/sql-reference/sql/create-database-catalog-linked)

## Knowledge check

### A platform team registers 400 Glue tables individually as externally managed Iceberg tables, and new tables keep appearing in Glue. What design reduces operational overhead?
- [ ] Recreate the catalog integration daily
- [x] Use an Iceberg REST catalog integration with a catalog-linked database so namespaces and tables are discovered and synced
- [ ] Convert every table to an external table
- [ ] Copy the data into native tables nightly
> A catalog-linked database automatically discovers and stays in sync with the remote catalog's namespaces and tables, removing per-table registration.

### CREATE CATALOG INTEGRATION succeeds, but the first CREATE ICEBERG TABLE fails with an access error. What is the most likely explanation?
- [ ] Catalog integrations cannot be used for Glue
- [x] Snowflake validates the trust relationship only on first use, and the IAM trust policy is missing or has an outdated external ID
- [ ] The warehouse is suspended
> Snowflake does not verify permissions until a table references the integration. A missing trust policy, or one with the external ID from an earlier version of the integration, causes this failure.

### Which statement about storage access for externally managed Iceberg tables is correct?
- [ ] The catalog integration always includes storage credentials
- [x] Storage access comes from an external volume or catalog-vended credentials, separate from the catalog integration
- [ ] Snowflake copies the files into internal storage on first query
> The catalog integration resolves metadata. Reading the underlying files requires an external volume or short-lived credentials vended by the catalog.
