# External Volumes

An external volume is an account-level Snowflake object that connects Snowflake to your own cloud storage for Apache Iceberg tables. It holds the storage location definitions and the IAM entity Snowflake uses to read and write Iceberg data, metadata, and manifest files. For architects, the external volume is where storage topology, trust boundaries, write permissions, and cross-region behavior for the lakehouse get decided.

## How it works

`CREATE EXTERNAL VOLUME` takes a `STORAGE_LOCATIONS` list. Each entry names a location with a `STORAGE_PROVIDER` (`'S3'`, `'GCS'`, `'AZURE'`, or S3-compatible), a `STORAGE_BASE_URL`, and provider-specific identity settings, such as `STORAGE_AWS_ROLE_ARN` on AWS.

**Identity model.** As with storage integrations, Snowflake provisions a principal for your account (an IAM user on AWS, a service account on Google Cloud, a service principal on Azure) that assumes a role you control. No secrets are exchanged. The required cloud permissions depend on the catalog model:

- Snowflake-managed tables need read and write actions, for example on S3: `GetBucketLocation`, `GetObject`, `ListBucket`, `PutObject`, `DeleteObject`, `GetObjectVersion`, and `DeleteObjectVersion`. On Azure this corresponds to Storage Blob Data Contributor.
- Externally managed tables need only read actions (on Azure, Storage Blob Data Reader).

**ALLOW_WRITES.** This property defaults to TRUE. Snowflake-managed tables require it, and Snowflake verifies access the first time the volume is used for a managed table by writing, reading, listing, and deleting a test file. For read-only scenarios, such as Delta Direct tables, grant only read actions and set `ALLOW_WRITES = FALSE` so Snowflake's behavior matches the cloud permissions.

**Active storage location.** An external volume has exactly one active location for its lifetime, assigned the first time it is used in `CREATE ICEBERG TABLE`. If the list contains locations in the same cloud and region as your account, Snowflake picks the first such local location; otherwise it picks the first location in the list. Order the list deliberately, because this choice cannot be changed later.

**Path layout.** Table files are written under `STORAGE_BASE_URL`, using the table's `BASE_LOCATION` (or a `BASE_LOCATION_PREFIX`, or a default database/schema/table path). Snowflake appends a random ID to the directory so that recreated tables do not collide with old files.

**Alternatives and replication.** For Snowflake-managed tables, Snowflake storage removes the need for an external volume entirely. For externally managed tables, catalog-vended credentials can replace an external volume. To replicate Snowflake-managed Iceberg tables, include both the parent database and the external volume in the failover or replication group.

## Example

Create a read-write volume for Snowflake-managed tables and verify access.

```sql
CREATE OR REPLACE EXTERNAL VOLUME lake_rw_vol
  STORAGE_LOCATIONS = (
    (
      NAME = 'us-east-1-primary'
      STORAGE_PROVIDER = 'S3'
      STORAGE_BASE_URL = 's3://acme-lake/managed/'
      STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/snowflake-lake-rw'
    )
  )
  ALLOW_WRITES = TRUE;

-- Use the IAM user ARN and external ID in the role's trust policy
DESC EXTERNAL VOLUME lake_rw_vol;

SELECT SYSTEM$VERIFY_EXTERNAL_VOLUME('lake_rw_vol');
```

Create a separate read-only volume for tables owned by an external catalog.

```sql
CREATE OR REPLACE EXTERNAL VOLUME lake_ro_vol
  STORAGE_LOCATIONS = (
    (
      NAME = 'glue-owned'
      STORAGE_PROVIDER = 'S3'
      STORAGE_BASE_URL = 's3://acme-lake/glue/'
      STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/snowflake-lake-ro'
    )
  )
  ALLOW_WRITES = FALSE;
```

## Best practices

- Split volumes by trust boundary: read-only for externally managed tables, read-write for Snowflake-managed tables, and separate volumes for separate data domains.
- Put a same-region location first in `STORAGE_LOCATIONS` so the active location is local and avoids cross-region egress.
- Run `SYSTEM$VERIFY_EXTERNAL_VOLUME` after every trust-policy change and before creating tables.
- Use `BASE_LOCATION` or `BASE_LOCATION_PREFIX` conventions so file layout maps clearly to databases and teams.
- Restrict `USAGE` on external volumes; any role with it can point Iceberg tables at that storage.
- Consider Snowflake storage for managed tables if you do not need data in your own account.

## Common pitfalls

- Granting only read permissions in the cloud while leaving `ALLOW_WRITES = TRUE`, then failing verification when creating a managed table.
- Listing a remote-region location first and getting an unexpected, permanent active location.
- Hitting an STS error on AWS because STS is not activated in the Snowflake deployment region.
- Recreating the volume and breaking the trust relationship because identity values changed.
- Replicating a database with managed Iceberg tables but omitting the external volume from the group.

## Learn more

- [External volume storage for Apache Iceberg tables](https://docs.snowflake.com/en/user-guide/tables-iceberg-managing-external-volumes)
- [Configure an external volume for S3-compatible storage](https://docs.snowflake.com/en/user-guide/tables-iceberg-s3-compatible)

## Knowledge check

### An account in AWS us-east-1 creates an external volume listing an Azure location first and an S3 us-east-1 location second. Which becomes the active location?
- [ ] The Azure location, because it is first
- [x] The S3 us-east-1 location, because Snowflake prefers the first local location
- [ ] Both, with Snowflake balancing writes
> If the list contains locations on the same cloud and in the same region as the account, Snowflake uses the first of those. Only when there are none does it fall back to the first entry in the list.

### A team is creating Delta Direct Iceberg tables that Snowflake must never write to. How should the external volume and cloud role be configured?
- [ ] Grant full read-write permissions and keep ALLOW_WRITES = TRUE
- [x] Grant only read actions and set ALLOW_WRITES = FALSE
- [ ] Grant write permissions only and set ALLOW_WRITES = FALSE
> For read-only use, Snowflake recommends granting only read actions and setting ALLOW_WRITES to FALSE so that Snowflake's behavior matches the permissions.

### You are adding Snowflake-managed Iceberg tables to a failover group for disaster recovery. What must the group include?
- [ ] Only the parent database
- [ ] Only the external volume
- [x] Both the parent database and the external volume
> Snowflake replicates a Snowflake-managed Iceberg table when both its parent database and the external volume it uses are in the group.
