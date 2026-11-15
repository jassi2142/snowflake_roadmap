# Directory Tables

A directory table is a file catalog layered on a stage that stores metadata about each staged file, including its path, size, timestamp, checksum, and Snowflake file URL. It turns a bucket or internal stage into something you can query with SQL, which is the foundation for governed access to unstructured files and for file-driven processing pipelines.

## How it works

A directory table is an **implicit object on a stage**, not a separate database object, and it has no grantable privileges of its own. Access is controlled through stage privileges. Both internal and external stages support directory tables. You enable one with `DIRECTORY = (ENABLE = TRUE)` in `CREATE STAGE`, or later with `ALTER STAGE ... SET DIRECTORY`.

You query it with the `DIRECTORY` table function. Output columns:

| Column | Description |
| --- | --- |
| RELATIVE_PATH | Path of the file within the stage |
| SIZE | File size in bytes |
| LAST_MODIFIED | When the file was last updated in the stage |
| MD5 | MD5 checksum |
| ETAG | ETag header |
| FILE_URL | Snowflake file URL for the file |

**Refreshing metadata.** The directory table only knows about files registered in its metadata.

- **Manual refresh**: `ALTER STAGE ... REFRESH`, optionally with `SUBPATH` to limit the listing. After creating a stage with a directory table you must refresh it. Manual refresh lists the stage and can be slow or expensive for large or fast-growing stages. The documentation states that directory tables on internal stages require manual refreshes.
- **Automated refresh**: for external stages, you can use your cloud provider's event messaging service so new and changed files are registered automatically. Manual refreshes on an external stage block simultaneous automated refreshes until they complete.

Refresh output reports a status per file, such as REGISTERED_NEW, REGISTERED_UPDATE, REGISTER_SKIPPED, REGISTER_FAILED, UNREGISTERED, or UNREGISTER_FAILED.

**Billing.**

- Automated refreshes incur an event-notification overhead that appears as **Snowpipe charges** and grows with the number of files added. You can estimate it with `PIPE_USAGE_HISTORY`.
- Manual refreshes incur a small maintenance overhead billed as cloud services and do not appear in `PIPE_USAGE_HISTORY`.
- `AUTO_REFRESH_REGISTRATION_HISTORY` reports files registered and credits billed; `STAGE_DIRECTORY_FILE_REGISTRATION_HISTORY` shows metadata history and refresh errors.

**Privileges.** Querying requires READ on an internal stage, or READ or USAGE on an external stage. Refreshing requires WRITE on an internal stage, or WRITE or USAGE on an external stage.

## Example

Create an external stage with a directory table:

```sql
CREATE STAGE images_stage
  URL = 's3://acme-media/images/'
  STORAGE_INTEGRATION = media_int
  DIRECTORY = (ENABLE = TRUE);
```

Refresh only a recent partition of the path:

```sql
ALTER STAGE images_stage REFRESH SUBPATH = '2026/11/';
```

Find large PNG files:

```sql
SELECT relative_path, size, last_modified, file_url
FROM DIRECTORY(@images_stage)
WHERE relative_path LIKE '%.png'
  AND size > 1000000
ORDER BY last_modified DESC;
```

Join files to business metadata in a view:

```sql
CREATE VIEW product_images AS
SELECT p.product_id, p.product_name, d.relative_path, d.size, d.file_url
FROM DIRECTORY(@images_stage) d
JOIN products p
  ON d.relative_path = p.image_path;
```

## Best practices

- Use automated refresh for large or busy external stages; manual refreshes list the entire path.
- When refreshing manually, use a selective `SUBPATH` and a date-based folder layout.
- Track registration errors with `STAGE_DIRECTORY_FILE_REGISTRATION_HISTORY`.
- Grant stage READ or USAGE narrowly, since the directory table inherits stage access.
- Use the directory table as the source for downstream processing, joining on RELATIVE_PATH or FILE_URL.

## Common pitfalls

- Querying a new directory table and seeing no rows because it was never refreshed.
- Running frequent full manual refreshes on stages with millions of files.
- Being surprised by Snowpipe line items that are actually directory table auto-refresh overhead.
- Trying to grant privileges on the directory table itself.

## Learn more

- [Directory tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables)
- [Manage directory tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables-manage)
- [Query directory tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables-query)

## Knowledge check

### You enable a directory table on an existing internal stage and SELECT FROM DIRECTORY returns zero rows, although files exist. What should you do?
- [ ] Grant SELECT on the directory table
- [x] Run ALTER STAGE ... REFRESH to register the files
- [ ] Recreate the stage with SNOWFLAKE_SSE
- [ ] Resume the warehouse
> The directory table only reflects registered metadata, so it must be refreshed after it is enabled.

### The bill shows unexpected Snowpipe charges, but you have no pipes. Which directory table feature could explain this?
- [ ] Manual refresh with SUBPATH
- [x] Automated refresh via cloud event notifications
- [ ] Querying FILE_URL
- [ ] Creating a view over DIRECTORY()
> Event-notification overhead for automated directory table refreshes is billed as Snowpipe charges.

### How is access to a directory table controlled?
- [ ] With GRANT SELECT ON DIRECTORY TABLE
- [x] Through privileges on the stage, such as READ for internal stages
- [ ] Directory tables are readable by PUBLIC
- [ ] Through a resource monitor
> A directory table has no privileges of its own; querying it requires the appropriate stage privileges.
