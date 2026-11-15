# Redact PII from free text with AI_REDACT

topics: cortex-ai-functions, classification
tags: ai, pii, privacy, cortex
level: intermediate

Remove names, emails, phone numbers and other personal data from support tickets or call transcripts before analysts or downstream models see them. AI_REDACT replaces each detected value with a placeholder such as `[NAME]`, or in detect mode returns where each value was found.

```sql
USE ROLE analyst;   -- needs the SNOWFLAKE.CORTEX_USER database role
USE WAREHOUSE my_wh;

-- 1. Redact all supported categories
SELECT AI_REDACT('Hi, I am Dana Lee, call me on (415) 555-0134 or dana.lee@example.com');
-- Typical output: Hi, I am [NAME], call me on [PHONE_NUMBER] or [EMAIL]

-- 2. Redact only selected categories
SELECT AI_REDACT(
  input      => 'Dana Lee lives at 12 Main St, Springfield, card 4111 1111 1111 1111',
  categories => ['PAYMENT_CARD_DATA', 'ADDRESS']);

-- 3. Detect mode: get spans (category, start, end, text) without changing the text
SELECT s.value:category::STRING AS category,
       s.value:text::STRING     AS found_text
FROM (SELECT AI_REDACT(input => 'Contact Dana at dana.lee@example.com',
                       return_error_details => FALSE,
                       mode => 'detect') AS r) t,
     LATERAL FLATTEN(input => t.r:spans) s;

-- 4. Batch: build a redacted copy of a table. If a row fails, keep a NULL value and the error instead of failing the whole query.
ALTER SESSION SET AI_SQL_ERROR_HANDLING_USE_FAIL_ON_ERROR = FALSE;

CREATE OR REPLACE TABLE my_db.support.tickets_redacted AS
SELECT ticket_id,
       created_at,
       r:value::STRING AS body_redacted,
       r:error::STRING AS redact_error
FROM (
  SELECT ticket_id, created_at, AI_REDACT(body, TRUE) AS r
  FROM my_db.support.tickets
  WHERE created_at >= DATEADD(day, -7, CURRENT_DATE())
);

-- Review the rows that failed
SELECT ticket_id, redact_error FROM my_db.support.tickets_redacted WHERE redact_error IS NOT NULL;

-- 5. Estimate input tokens before a large run
SELECT SUM(AI_COUNT_TOKENS('ai_redact', body)) AS est_input_tokens
FROM my_db.support.tickets SAMPLE (1000 ROWS);
```

## Notes
- Billed per input and output token, like other Cortex AI functions. Test on a sample first and check that the function is available in your region.
- Supported categories: NAME, EMAIL, PHONE_NUMBER, DATE_OF_BIRTH, GENDER, AGE, ADDRESS, NATIONAL_ID, PASSPORT, TAX_IDENTIFIER, PAYMENT_CARD_DATA, DRIVERS_LICENSE, IP_ADDRESS. An unsupported category causes an error.
- Detection is best-effort. It works best on well-formed English text and mainly covers US PII, plus some UK and Canadian formats. Review the output before relying on it for compliance.
- Input plus output is limited to 4,096 tokens, and output to 1,024 tokens. Split longer text first, for example with `SNOWFLAKE.CORTEX.SPLIT_TEXT_RECURSIVE_CHARACTER`, then redact each chunk.
- The CTAS stores redacted text only. Restrict access to the raw source table separately.

## References
- [AI_REDACT](https://docs.snowflake.com/en/sql-reference/functions/ai_redact)
- [AI_COUNT_TOKENS](https://docs.snowflake.com/en/sql-reference/functions/ai_count_tokens)
