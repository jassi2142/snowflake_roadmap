# Apache Iceberg Tables

Apache Iceberg is an open table format that stores data in Parquet files plus metadata files describing schemas, snapshots, and partitions. Snowflake Iceberg tables let you query and manage those tables with Snowflake's engine while keeping the data in an open format that other engines, such as Spark or Trino, can also read. They are the main way to build an open lakehouse on Snowflake.

## How it works

Every Iceberg table has a **catalog**, which tracks the current metadata file for the table, and **storage**, where the data and metadata files live. Snowflake supports two catalog models:

- **Snowflake-managed** (`CATALOG = 'SNOWFLAKE'`): Snowflake is the Iceberg catalog. Snowflake writes the table's metadata and the table supports full DML, so this model behaves most like a native table.
- **Externally managed**: another catalog, such as AWS Glue, Snowflake Open Catalog, Unity Catalog, or any Iceberg REST catalog, owns the table. Snowflake reaches it through a **catalog integration**. Snowflake can read these tables and, with catalog-linked databases on supported REST catalogs, can also write to them.

For storage, you can use an **external volume**, which points to your own S3, GCS, or Azure location and grants Snowflake access through your cloud provider's IAM. For Snowflake-managed tables, Snowflake also offers **Snowflake storage**, which removes the need to configure an external volume. Externally managed tables can alternatively use catalog-vended credentials.

Other key points:

- A **catalog-linked database** connects to a remote Iceberg REST catalog and automatically discovers and syncs its namespaces and tables.
- `ALTER ICEBERG TABLE ... CONVERT TO MANAGED` turns an externally managed table into a Snowflake-managed one without rewriting the data files.
- `COPY INTO` can load into Iceberg tables. With `LOAD_MODE = ADD_FILES_COPY`, Snowflake copies Iceberg-compatible Parquet files into the table location and registers them without rewriting them.
- `INFER_SCHEMA` with `KIND => 'ICEBERG'` returns Iceberg data types for creating tables from Parquet files.
- Iceberg tables differ from native tables in some features; for example, `VALIDATION_MODE` in `COPY` is not supported for Iceberg tables.

## Example

Create a Snowflake-managed Iceberg table on an existing external volume and use it like any other table.

```sql
CREATE OR REPLACE ICEBERG TABLE sales_iceberg (
  sale_id   NUMBER(38,0),
  region    STRING,
  amount    NUMBER(10,2),
  sale_date DATE
)
  CATALOG = 'SNOWFLAKE'
  EXTERNAL_VOLUME = 'lake_vol'
  BASE_LOCATION = 'sales_iceberg/';

INSERT INTO sales_iceberg VALUES (1, 'EMEA', 120.50, '2026-11-10');

SELECT region, SUM(amount) FROM sales_iceberg GROUP BY region;
```

Create a read-only table from Iceberg metadata files already in object storage, using a catalog integration for object storage.

```sql
CREATE ICEBERG TABLE events_ext
  EXTERNAL_VOLUME = 'lake_vol'
  CATALOG = 'object_store_catalog_int'
  METADATA_FILE_PATH = 'events/metadata/v12.metadata.json';
```

## Best practices

- Choose Snowflake-managed tables when Snowflake is the primary writer; choose external catalogs when another engine owns the table lifecycle.
- Use a catalog-linked database rather than creating many individual externally managed tables by hand.
- Separate external volumes by access level, for example read-only for external tables and read-write for Snowflake-managed tables.
- Use `KIND => 'ICEBERG'` with `INFER_SCHEMA` when deriving Iceberg schemas from Parquet.
- Set a default `CATALOG` at the account, database, or schema level so teams do not repeat the integration on every table.

## Common pitfalls

- Expecting to write to an externally managed table created from object-storage metadata; that pattern is read-only.
- Granting a cloud role only read permissions and then creating a Snowflake-managed table, which needs write and delete access.
- Assuming every native-table feature applies to Iceberg tables without checking the docs.
- Registering Parquet files from another Iceberg table with `ADD_FILES_COPY` instead of using `CONVERT TO MANAGED`.

## Learn more

- [Apache Iceberg tables](https://docs.snowflake.com/en/user-guide/tables-iceberg)
- [Configure a catalog integration](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration)

## Knowledge check

### Your team wants Snowflake to perform inserts and updates on a table and act as its catalog, while Spark jobs can still read the files. Which option fits best?
- [x] A Snowflake-managed Iceberg table
- [ ] An externally managed Iceberg table created from metadata files in object storage
- [ ] An external table
- [ ] A transient native table
> With Snowflake as the catalog, Snowflake supports full DML, while the data remains in the open Iceberg format that other engines can read.

### What does a catalog integration provide for an Iceberg table?
- [ ] Cloud storage credentials for the Parquet files
- [x] Information about the external catalog that tracks the table's metadata
- [ ] A virtual warehouse to query the table
> The catalog integration tells Snowflake how to reach the external Iceberg catalog. Storage access is handled separately by an external volume or vended credentials.

### A table is managed in AWS Glue, and you want Snowflake to take over as its catalog without rewriting the data files. What should you use?
- [ ] COPY INTO with LOAD_MODE = ADD_FILES_COPY
- [ ] CREATE OR REPLACE ICEBERG TABLE with CATALOG = 'SNOWFLAKE'
- [x] ALTER ICEBERG TABLE ... CONVERT TO MANAGED
> CONVERT TO MANAGED transfers catalog ownership to Snowflake while keeping the existing files, which Snowflake documents as the best practice for this migration.
