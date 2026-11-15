# Extract structured JSON from text with AI_COMPLETE

topics: cortex-ai-functions, variant
tags: ai, llm, structured-output, json
level: intermediate

Free-text columns such as product reviews often hide facts you want as columns. AI_COMPLETE with a `response_format` makes the model return JSON in a fixed shape, so you can cast fields straight into typed columns.

```sql
USE ROLE my_ai_role;          -- needs the SNOWFLAKE.CORTEX_USER database role
USE WAREHOUSE my_wh;          -- small warehouse is enough; tokens drive the cost

-- Sample data
CREATE OR REPLACE TEMPORARY TABLE reviews (review_id INT, review_text STRING);
INSERT INTO reviews VALUES
  (1, 'The blender arrived two days late but works great. 4 stars, would buy again.'),
  (2, 'Headphones broke after a week. Support never answered. Want a refund!');

-- Option A: response_format as a TYPE OBJECT literal
SELECT
  review_id,
  AI_COMPLETE(
    model           => 'claude-sonnet-5',
    prompt          => 'Extract product, sentiment and whether a refund is requested from this review: ' || review_text,
    response_format => TYPE OBJECT(product STRING, sentiment STRING, rating INT, wants_refund BOOLEAN)
  ) AS extracted
FROM reviews;

-- Option B: response_format as a JSON schema, then flatten into typed columns
WITH raw AS (
  SELECT
    review_id,
    AI_COMPLETE(
      model           => 'llama3.3-70b',
      prompt          => 'Extract the fields from this review: ' || review_text,
      model_parameters => {'temperature': 0},
      response_format => {
        'type': 'json',
        'schema': {
          'type': 'object',
          'properties': {
            'product':      {'type': 'string'},
            'sentiment':    {'type': 'string', 'enum': ['positive', 'neutral', 'negative']},
            'wants_refund': {'type': 'boolean'}
          },
          'required': ['product', 'sentiment', 'wants_refund']
        }
      }
    ) AS j
  FROM reviews
)
SELECT
  review_id,
  j:product::STRING       AS product,
  j:sentiment::STRING     AS sentiment,
  j:wants_refund::BOOLEAN AS wants_refund
FROM raw;
```

## Notes
- The role must have the `SNOWFLAKE.CORTEX_USER` database role. Model availability depends on region; enable cross-region inference if a model is not available locally.
- Cost is per token (input + output). Test on a `LIMIT 10` sample before running on a full table.
- `temperature: 0` makes output more repeatable. Structured output enforces the shape, but you should still validate values before using them downstream.

## References
- [AI_COMPLETE (single string)](https://docs.snowflake.com/en/sql-reference/functions/ai_complete-single-string)
- [AI_COMPLETE structured outputs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/complete-structured-outputs)
