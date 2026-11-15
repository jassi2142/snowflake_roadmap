# Parse every PDF on a stage with AI_PARSE_DOCUMENT

topics: cortex-ai-functions, directory-tables, unstructured
tags: ai, documents, ocr, pipeline
level: intermediate

Turn a folder of PDFs into searchable text. A directory table lists the staged files, TO_FILE turns each one into a FILE value, and AI_PARSE_DOCUMENT returns the text (OCR) or Markdown with tables (LAYOUT).

```sql
USE ROLE my_ai_role;   -- needs SNOWFLAKE.CORTEX_USER and READ on the stage
USE WAREHOUSE my_wh;

-- Internal stage with server-side encryption and a directory table
CREATE STAGE IF NOT EXISTS my_db.my_schema.docs_stage
  DIRECTORY = (ENABLE = TRUE)
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

-- Upload files with PUT (Snowflake CLI / SnowSQL), then refresh the directory table:
-- PUT file://C:/docs/*.pdf @my_db.my_schema.docs_stage AUTO_COMPRESS = FALSE;
ALTER STAGE my_db.my_schema.docs_stage REFRESH;

-- Target table
CREATE TABLE IF NOT EXISTS my_db.my_schema.parsed_docs (
  relative_path STRING,
  page_count    INT,
  content       STRING,
  parsed_at     TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Parse only files not parsed yet, in LAYOUT mode (keeps tables as Markdown)
INSERT INTO my_db.my_schema.parsed_docs (relative_path, page_count, content)
SELECT
  d.relative_path,
  p.doc:metadata:pageCount::INT,
  p.doc:content::STRING
FROM DIRECTORY(@my_db.my_schema.docs_stage) d,
     LATERAL (
       SELECT PARSE_JSON(
                AI_PARSE_DOCUMENT(
                  TO_FILE('@my_db.my_schema.docs_stage', d.relative_path),
                  {'mode': 'LAYOUT'}
                )
              ) AS doc
     ) p
WHERE d.relative_path ILIKE '%.pdf'
  AND d.relative_path NOT IN (SELECT relative_path FROM my_db.my_schema.parsed_docs);

-- Long documents: split into pages, one row per page
SELECT
  d.relative_path,
  pg.value:index::INT      AS page_index,
  pg.value:content::STRING AS page_text
FROM DIRECTORY(@my_db.my_schema.docs_stage) d,
     LATERAL FLATTEN(
       input => PARSE_JSON(
                  AI_PARSE_DOCUMENT(
                    TO_FILE('@my_db.my_schema.docs_stage', d.relative_path),
                    {'mode': 'OCR', 'page_split': TRUE}
                  )
                ):pages
     ) pg
WHERE d.relative_path = 'contracts/big_contract.pdf';
```

## Notes
- Modes: `OCR` (default, text only), `LAYOUT` (text plus structure such as tables), `AGENTIC` (also interprets charts and diagrams). `page_split` works for PDF, PPTX and DOCX only.
- The function returns a JSON string, so wrap it in PARSE_JSON before reading fields. Failed files return NULL.
- AI functions do not work on files in user stages, table stages, stages with `SNOWFLAKE_FULL` encryption, or stages with double-quoted names. Use `SNOWFLAKE_SSE` for internal stages.
- Cost is per page. To keep a pipeline running, schedule the INSERT with a task, or feed it from a stream on the directory table.

## References
- [AI_PARSE_DOCUMENT](https://docs.snowflake.com/en/sql-reference/functions/ai_parse_document)
- [Parsing documents with AI_PARSE_DOCUMENT](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document)
- [Directory tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables)
