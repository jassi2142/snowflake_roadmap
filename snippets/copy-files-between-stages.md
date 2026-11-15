# Copy files between stages with COPY FILES

topics: stages, directory-tables
tags: files, stages, migration
level: beginner

Move raw files from an external landing stage into an internal archive stage, or between any two named stages, without downloading and re-uploading them. COPY FILES is serverless and works with whole stages, file lists, regex patterns, or a query.

```sql
USE SCHEMA my_db.my_schema;

-- Target internal stage (directory table lets you query what landed)
CREATE STAGE IF NOT EXISTS archive_stage DIRECTORY = (ENABLE = TRUE);

-- 1. Everything under a path
COPY FILES
  INTO @archive_stage/2026/11/
  FROM @landing_s3_stage/incoming/;

-- 2. Specific files only
COPY FILES
  INTO @archive_stage/manual/
  FROM @landing_s3_stage/incoming/
  FILES = ('orders_20261114.csv.gz', 'orders_20261115.csv.gz');

-- 3. Regex filter: only gzipped CSVs whose name contains "orders"
COPY FILES
  INTO @archive_stage/orders/
  FROM @landing_s3_stage
  PATTERN = '.*orders.*[.]csv[.]gz'
  DETAILED_OUTPUT = FALSE;          -- one summary row instead of one row per file

-- 4. Query as source: copy and rename files picked from a directory table
COPY FILES
  INTO @archive_stage/renamed/
  FROM (
    SELECT file_url,
           'orders_' || TO_CHAR(last_modified, 'YYYYMMDD') || '_' || SPLIT_PART(relative_path, '/', -1)
    FROM DIRECTORY(@landing_s3_stage)
    WHERE relative_path ILIKE 'incoming/%.csv.gz'
  );

ALTER STAGE archive_stage REFRESH;
SELECT relative_path, size, last_modified FROM DIRECTORY(@archive_stage);
```

## Notes
- Privileges: USAGE on external stages, READ on an internal source stage, WRITE on an internal target stage.
- Table stages are not supported, and user stages cannot be used when the source is a stage. Files larger than 5 GB and archived storage tiers (such as Glacier) are also not supported.
- Files with the same name in the target are overwritten. Snowflake keeps no copy history and does not clean up after a failed copy.
- Copying from an internal stage to an external stage in another region or cloud incurs data transfer charges. Copying into Snowflake (ingress) has no transfer charge.

## References
- [COPY FILES](https://docs.snowflake.com/en/sql-reference/sql/copy-files)
- [Directory tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables)
