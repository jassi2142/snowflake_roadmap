# Create and query a Cortex Search service

topics: cortex-search
tags: ai, search, rag
level: advanced

Build hybrid (keyword plus vector) search over a table of text chunks, then query it from SQL with SEARCH_PREVIEW. This is the retrieval step of a RAG application.

```sql
USE ROLE my_search_role;   -- CREATE CORTEX SEARCH SERVICE on schema, SELECT on source, USAGE on warehouse,
                           -- plus SNOWFLAKE.CORTEX_USER (or CORTEX_EMBED_USER)
USE SCHEMA my_db.my_schema;

-- Source table: one row per chunk of a knowledge-base article
CREATE OR REPLACE TABLE kb_chunks (
  chunk_id   STRING,
  article    STRING,
  product    STRING,
  updated_at DATE,
  chunk_text STRING
);
INSERT INTO kb_chunks VALUES
  ('a1-1', 'Reset password', 'portal', '2026-09-01', 'To reset your password open Settings, choose Security and click Reset.'),
  ('a2-1', 'Export reports', 'reports', '2026-10-12', 'Reports can be exported to CSV or PDF from the Share menu.'),
  ('a3-1', 'SSO setup',      'portal', '2026-08-20', 'Single sign-on uses SAML 2.0. An admin must upload the IdP metadata.');

-- Search service: index chunk_text, allow filtering on product
CREATE OR REPLACE CORTEX SEARCH SERVICE kb_search
  ON chunk_text
  PRIMARY KEY (chunk_id)
  ATTRIBUTES product
  WAREHOUSE = my_search_wh
  TARGET_LAG = '1 hour'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-m-v1.5'
AS
  SELECT chunk_id, article, product, updated_at, chunk_text
  FROM kb_chunks;

-- Check status
SHOW CORTEX SEARCH SERVICES IN SCHEMA my_db.my_schema;

-- Query from SQL (good for testing; use the REST or Python API in apps)
SELECT PARSE_JSON(
  SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'my_db.my_schema.kb_search',
    '{
       "query":   "how do I log in with my company identity provider",
       "columns": ["article", "chunk_text"],
       "filter":  {"@eq": {"product": "portal"}},
       "limit":   3
     }'
  )
):results AS results;

-- Flatten the results into rows
SELECT r.value:article::STRING AS article, r.value:chunk_text::STRING AS chunk
FROM LATERAL FLATTEN(
  input => PARSE_JSON(
    SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
      'my_db.my_schema.kb_search',
      '{"query": "export to pdf", "columns": ["article","chunk_text"], "limit": 2}'
    )
  ):results
) r;

-- Clean up
-- DROP CORTEX SEARCH SERVICE kb_search;
```

## Notes
- Refreshes run on the service warehouse to meet `TARGET_LAG`. Snowflake recommends a dedicated warehouse no larger than MEDIUM. Change tracking is enabled on the source tables automatically.
- A text-only `PRIMARY KEY` enables a cheaper incremental refresh path. `EMBEDDING_MODEL`, `REFRESH_MODE` and `INITIALIZE` cannot be changed after the service is created.
- Cost has three parts: warehouse refreshes, embedding tokens, and serving compute while the service is active. Set `AUTO_SUSPEND` (minimum 1800 seconds) to suspend serving when idle.
- Only columns listed in `ATTRIBUTES` can be used in `filter`.

## References
- [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search)
- [Query a Cortex Search Service](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service)
- [SEARCH_PREVIEW](https://docs.snowflake.com/en/sql-reference/functions/search_preview-snowflake-cortex)
