# Pull invoice fields and line items with AI_EXTRACT

topics: cortex-ai-functions, unstructured
tags: ai, documents, extraction, invoices
level: intermediate

Get header fields (vendor, invoice number, total) and the line-item table out of invoice PDFs with one AI_EXTRACT call per file. Confidence scores let you send uncertain results to a person for review.

```sql
USE ROLE my_ai_role;   -- needs SNOWFLAKE.CORTEX_USER
USE WAREHOUSE my_wh;   -- MEDIUM or smaller; larger warehouses do not speed it up

-- Stage with a directory table that holds invoice PDFs
CREATE STAGE IF NOT EXISTS my_db.my_schema.invoice_stage
  DIRECTORY = (ENABLE = TRUE)
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

-- 1. Quick entity extraction (simple question map)
SELECT
  relative_path,
  AI_EXTRACT(
    file           => TO_FILE('@my_db.my_schema.invoice_stage', relative_path),
    responseFormat => {
      'vendor':         'What is the name of the company that issued the invoice?',
      'invoice_number': 'What is the invoice number?',
      'invoice_date':   'What is the invoice date?',
      'total_amount':   'What is the total amount due?'
    }
  ) AS result
FROM DIRECTORY(@my_db.my_schema.invoice_stage);

-- 2. Header fields plus a line-item table, with scores
CREATE OR REPLACE TABLE my_db.my_schema.invoice_extract AS
SELECT
  relative_path,
  AI_EXTRACT(
    file           => TO_FILE('@my_db.my_schema.invoice_stage', relative_path),
    responseFormat => {
      'schema': {
        'type': 'object',
        'properties': {
          'vendor':       {'description': 'Name of the issuing company', 'type': 'string'},
          'total_amount': {'description': 'Total amount due',            'type': 'string'},
          'line_items': {
            'description': 'Invoice line items table',
            'type': 'object',
            'column_ordering': ['description', 'quantity', 'amount'],
            'properties': {
              'description': {'description': 'Item description', 'type': 'array'},
              'quantity':    {'description': 'Quantity',         'type': 'array'},
              'amount':      {'description': 'Line amount',      'type': 'array'}
            }
          }
        }
      }
    },
    scores => TRUE
  ) AS result
FROM DIRECTORY(@my_db.my_schema.invoice_stage)
WHERE relative_path ILIKE '%.pdf';

-- 3. Header view; flag low-confidence totals for manual review
SELECT
  relative_path,
  result:response:vendor::STRING                     AS vendor,
  result:response:total_amount::STRING               AS total_amount_raw,
  result:scoring:scores:total_amount:score::FLOAT    AS total_score,
  total_score < 0.8                                  AS needs_review,
  result:error::STRING                               AS error
FROM my_db.my_schema.invoice_extract;

-- 4. Explode the line-item columns (parallel arrays) into rows
SELECT
  e.relative_path,
  d.index                                                     AS line_no,
  d.value::STRING                                             AS item_description,
  e.result:response:line_items:quantity[d.index]::STRING      AS quantity,
  e.result:response:line_items:amount[d.index]::STRING        AS amount
FROM my_db.my_schema.invoice_extract e,
     LATERAL FLATTEN(input => e.result:response:line_items:description) d;
```

## Notes
- Extracted values are strings. Convert them with TRY_TO_NUMBER or TRY_TO_DATE after cleaning out currency symbols.
- A JSON `schema` response format cannot be mixed with other formats. Each call allows at most 100 entity questions or 10 table questions (one table counts as 10 entities).
- Billing counts each page as 970 tokens, plus prompt and output tokens. Scores cost nothing extra.
- Files must be under 100 MB. The page limit is 125 without cross-region inference and 1,000 with it.

## References
- [AI_EXTRACT](https://docs.snowflake.com/en/sql-reference/functions/ai_extract)
- [Extracting information from documents with AI_EXTRACT](https://docs.snowflake.com/en/user-guide/snowflake-cortex/document-extraction)
