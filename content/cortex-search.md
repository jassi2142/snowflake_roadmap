# Cortex Search

Cortex Search is a managed hybrid retrieval service: you declare a source query, and Snowflake builds and maintains the embeddings, the keyword index, and a low-latency serving endpoint for it. It is the standard retrieval layer for RAG applications and Cortex Agents on Snowflake, and it replaces the need to run a separate vector database alongside your warehouse.

## How it works

A service is defined with `CREATE CORTEX SEARCH SERVICE ... AS <query>`. Behind the scenes it has two halves with different cost and scaling characteristics:

- **Indexing (refresh)**: a warehouse that you specify runs the source query, computes embeddings, and builds the index. Freshness is governed by `TARGET_LAG`, in the same way as dynamic tables. `REFRESH_MODE` defaults to `INCREMENTAL`, which requires change tracking on the base objects. Snowflake tries to enable change tracking automatically. Set `TARGET_LAG` shorter than the source tables' Time Travel retention, or the service may lose track of changes and need to be recreated.
- **Serving**: a managed endpoint answers queries through the Python API, the REST API (`.../cortex-search-services/<name>:query`), or `SNOWFLAKE.CORTEX.SEARCH_PREVIEW`, which is meant for testing only. Serving can auto-suspend after inactivity with `AUTO_SUSPEND` (minimum 1800 seconds; disabled by default).

Retrieval combines vector similarity, lexical matching, and a semantic reranker by default. Design levers that matter:

- **Single-index vs multi-index**: `ON <col>` creates a single searchable text column with managed embeddings. `TEXT INDEXES ... VECTOR INDEXES ...` (multi-index, Preview) lets you index several columns, bring your own vectors, and weight text against vector scores per query. A multi-index service must have at least one vector index.
- **Embedding model**: `EMBEDDING_MODEL` defaults to `snowflake-arctic-embed-m-v1.5`. It cannot be altered after creation, and models differ in cost per token and regional availability. Changing models means a full rebuild.
- **PRIMARY KEY**: optional, but it enables an optimized refresh path that re-embeds only changed rows. Periodic compaction is controlled by `FULL_INDEX_BUILD_INTERVAL_DAYS` (default 1). Primary key columns must be TEXT.
- **ATTRIBUTES**: columns you can filter on with `@eq`, `@contains`, `@gte`, `@lte`, `@primarykey`, combined with `@and`, `@or`, `@not`.
- **Scoring**: `scoring_config` supports numeric boosts, time decays, index weights, and disabling the reranker (`"reranker": "none"`) to cut latency.

Limits worth knowing: `limit` defaults to 10 and maxes at 1000 results. Responses are capped at 10 MB for the REST and Python APIs and 300 KB for `SEARCH_PREVIEW`.

**Security model**: queries run with **owner's rights**. Any role with USAGE on the service can retrieve any indexed row, regardless of row access or masking policies on the source tables for that role. Treat a search service as a published data product and scope its source query accordingly.

## Example

Index support transcripts with filterable region and agent attributes:

```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE support_db.search.transcript_svc
  ON transcript_text
  PRIMARY KEY (transcript_id)
  ATTRIBUTES region, agent_id
  WAREHOUSE = search_refresh_wh
  TARGET_LAG = '1 hour'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
AS
  SELECT transcript_id, transcript_text, region, agent_id, call_date
  FROM support_db.curated.transcripts;
```

The primary key enables incremental re-embedding of only the rows that changed.

Validate results from SQL before wiring up the REST API:

```sql
SELECT PARSE_JSON(
  SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'support_db.search.transcript_svc',
    '{
       "query": "customer cannot reset password",
       "columns": ["transcript_id", "transcript_text", "call_date"],
       "filter": {"@eq": {"region": "EMEA"}},
       "limit": 5
     }'
  )
)['results'] AS results;
```

## Best practices

- Chunk long documents upstream (for example after `AI_PARSE_DOCUMENT`) so each row is a coherent passage. Retrieval quality is driven more by chunking than by model choice.
- Use a dedicated refresh warehouse per service to isolate cost and avoid contention with other workloads.
- Define a PRIMARY KEY on any service with frequent small updates to avoid re-embedding the corpus.
- Put security filtering into the source query (or build one service per audience) because serving uses owner's rights.
- Enable `REQUEST_LOGGING` during tuning so you can analyze real queries, then evaluate relevance against a labeled question set before changing models or weights.
- For multi-index services, pass `multi_index_query` to search only the indexes you need, which reduces cost.

## Common pitfalls

- Using `SEARCH_PREVIEW` as the production query path. It has higher latency and a much smaller response cap.
- Recreating a base table (for example with `CREATE OR REPLACE`), which drops change tracking and breaks incremental refresh.
- Expecting `CREATE OR REPLACE` on the service to be seamless: the old index is unavailable from commit until the new index finishes building.
- Choosing an embedding model without checking regional availability, then discovering it cannot be changed without a rebuild.
- Granting USAGE broadly on a service built over sensitive tables, which exposes rows that source policies would otherwise hide.

## Learn more

- [Cortex Search overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search)
- [Query a Cortex Search Service](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service)

## Knowledge check

### A search service indexes an HR documents table that has a row access policy. Analysts with USAGE on the service report seeing documents they cannot query directly. Why?
- [ ] The row access policy is only evaluated on refresh, not on queries
- [x] Cortex Search serves queries with owner's rights, so callers see whatever the owner's role could index
- [ ] Cortex Search ignores policies only when the reranker is enabled
- [ ] The analysts must have SELECT on the base table cached
> Search services execute with owner's rights. Access control must be designed into the source query or by creating separate services per audience.

### A 50 million row corpus receives a few thousand updates per hour, and refresh costs are high. Which change gives the largest reduction?
- [ ] Switch REFRESH_MODE to FULL
- [ ] Increase TARGET_LAG to 1 minute
- [x] Define a PRIMARY KEY so refreshes re-embed only the changed rows
- [ ] Disable the reranker in scoring_config
> With a primary key, the service uses an optimized refresh path that processes only changed rows instead of recomputing embeddings for the corpus.

### Your team wants to evaluate a different embedding model on an existing production service. What must you plan for?
- [ ] Run ALTER CORTEX SEARCH SERVICE SET EMBEDDING_MODEL during a quiet period
- [x] EMBEDDING_MODEL cannot be altered, so you need a new service (or CREATE OR REPLACE), which rebuilds the index and has its own availability gap
- [ ] Only the query-time model changes; stored vectors are reused
- [ ] Models can be switched per query with scoring_config
> The embedding model is fixed at creation. Building a parallel service and comparing relevance before cutting over avoids the gap that CREATE OR REPLACE introduces.
