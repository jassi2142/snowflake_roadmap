# Stages

A stage is a named location where data files sit before Snowflake loads them into tables, or after Snowflake unloads table data into files. Every bulk load (`COPY INTO <table>`), continuous load (Snowpipe), and unload (`COPY INTO <location>`) goes through a stage, so knowing the different stage types is the first step in working with files in Snowflake.

## How it works

Snowflake has two broad families of stages: **internal** stages, where Snowflake stores the files for you, and **external** stages, which point to a bucket or container in your own cloud storage.

Internal stages come in three types:

- **User stage** (`@~`): every user has one automatically. Only that user can access it, so it suits personal, ad hoc files.
- **Table stage** (`@%table_name`): every table has one automatically. Any user with access to the table can use it, but it can only load into that one table.
- **Named internal stage** (`@my_stage`): a database object you create with `CREATE STAGE`. It is the most flexible option because you can grant privileges on it, attach a default file format, and share it across many tables.

External stages are named objects created with `CREATE STAGE ... URL = '...'` that reference Amazon S3, Google Cloud Storage, or Microsoft Azure. Snowflake does not store or manage these files; it reads and writes them with credentials you provide. The recommended way to provide access is a **storage integration**, which avoids putting secret keys in SQL.

You move local files into an internal stage with the `PUT` command (run from a client such as SnowSQL or Snowflake CLI, not from a Snowsight worksheet), and download files with `GET`. For external stages, you upload files with your cloud provider's own tools. `LIST @stage` shows the files in any stage, and `REMOVE @stage/path` deletes them.

A stage can also have a **directory table**, which keeps a catalog of the files in the stage that you can query with SQL. Directory tables are commonly used with unstructured data.

## Example

Create a named internal stage with a default CSV file format, upload a file, and check that it arrived.

```sql
CREATE OR REPLACE FILE FORMAT my_csv_format
  TYPE = CSV
  SKIP_HEADER = 1;

CREATE OR REPLACE STAGE my_int_stage
  FILE_FORMAT = my_csv_format;

-- Run from SnowSQL or Snowflake CLI
PUT file:///tmp/orders.csv @my_int_stage;

LIST @my_int_stage;
```

Create an external stage that uses an existing storage integration, then load from it.

```sql
CREATE OR REPLACE STAGE my_s3_stage
  URL = 's3://mybucket/orders/'
  STORAGE_INTEGRATION = my_s3_int
  FILE_FORMAT = my_csv_format;

COPY INTO orders FROM @my_s3_stage;
```

## Best practices

- Use named stages for anything shared or production-grade; they support grants and default file formats.
- Use storage integrations for external stages instead of embedding access keys.
- Organize files with logical paths such as `orders/2026/11/11/` so you can load subsets by path.
- End stage URLs with a forward slash so the prefix does not accidentally match similarly named folders.
- Clean up loaded files (with `REMOVE` or `PURGE = TRUE`) so internal stages do not accumulate storage cost.

## Common pitfalls

- Trying to run `PUT` from a Snowsight worksheet; it must be run from a client that has access to your local file system.
- Expecting a table stage to load into a different table; it is tied to its own table.
- Forgetting that files in internal stages are billed as storage until you remove them.
- Assuming an external stage copies the data into Snowflake; it only references your bucket.

## Learn more

- [CREATE STAGE](https://docs.snowflake.com/en/sql-reference/sql/create-stage)
- [COPY INTO <table>](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)

## Knowledge check

### A team needs a stage that several analysts can load from, with a shared default file format and controlled access. Which stage type fits best?
- [ ] User stage
- [ ] Table stage
- [x] Named internal stage
- [ ] Any stage, since they all behave the same
> Named stages are database objects, so you can grant privileges on them and attach a default file format. User stages are private to one user and table stages are tied to a single table.

### Where do files referenced by an external stage physically live?
- [ ] In Snowflake-managed storage, copied when the stage is created
- [x] In your own cloud storage bucket or container
- [ ] In the user stage of the stage owner
> An external stage is only a pointer to a location in Amazon S3, Google Cloud Storage, or Azure. Snowflake does not store or manage those files.

### You want to upload a CSV file from your laptop into an internal stage. What should you use?
- [ ] COPY INTO from a Snowsight worksheet
- [x] The PUT command from a client such as SnowSQL or Snowflake CLI
- [ ] CREATE EXTERNAL TABLE
- [ ] GET
> PUT uploads local files into an internal stage and runs from a client with access to your file system. GET does the opposite, downloading files from a stage.
