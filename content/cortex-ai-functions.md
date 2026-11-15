# Cortex AI Functions

Cortex AI Functions are SQL functions that run large language models and other AI models directly inside Snowflake, so you can classify, filter, summarize, extract, translate, and embed text, images, and documents without moving data out of the platform. Because they are ordinary SQL functions, you can apply them to millions of rows in a SELECT statement, a dynamic table, or a task, and govern them with the same roles you already use.

## How it works

Each function sends its input to a model hosted inside the Snowflake service perimeter and returns a value (a string, a boolean, an object, or a vector). The main families are:

- **General generation**: `AI_COMPLETE` sends a prompt (and optionally files such as images) to a model you choose. Use it for most free-form generative tasks.
- **Task-specific functions**: `AI_CLASSIFY` (assign categories), `AI_FILTER` (return TRUE/FALSE for a natural-language condition), `AI_EXTRACT` (pull fields out of text or files), `AI_SENTIMENT`, `AI_SUMMARIZE`, `AI_TRANSLATE`, `AI_REDACT` (remove PII), `AI_PARSE_DOCUMENT` (OCR or layout extraction from staged documents), and `AI_TRANSCRIBE` (audio and video).
- **Aggregate functions**: `AI_AGG` reduces a whole column of text with an instruction, and `AI_SUMMARIZE_AGG` produces a general summary. Both work on data sets larger than a model's context window.
- **Embedding and similarity**: `AI_EMBED` and `AI_SIMILARITY` support semantic search and clustering.
- **Helpers**: `PROMPT` builds templated prompts from several columns, `TO_FILE` references a staged file, and `AI_COUNT_TOKENS` estimates token usage before you run a large job.

Key operational facts:

- **Access**: your role needs the `USE AI FUNCTIONS` account privilege and the `SNOWFLAKE.CORTEX_USER` (or `AI_FUNCTIONS_USER`) database role.
- **Cost**: you are billed per token processed. Task-specific functions add their own internal prompt, and extras such as category descriptions and few-shot examples in `AI_CLASSIFY` also count as input tokens.
- **Availability**: functions and models vary by region. Some functions are Preview features, so check the status of each one before relying on it in production.
- **Error handling**: by default, a row that cannot be processed returns NULL instead of failing the whole query. Pass the optional `return_error_details` argument (TRUE) to get an object with `value` and `error` fields.
- **Files**: functions that read files need them on a stage that uses server-side encryption (for example `SNOWFLAKE_SSE`). User stages and table stages are not supported.

## Example

Classify support tickets and keep only the ones where the customer is asking for a refund:

```sql
SELECT
    ticket_id,
    AI_CLASSIFY(
        body,
        ['billing', 'technical issue', 'account access', 'feature request']
    ):labels[0]::STRING AS category
FROM support.tickets
WHERE AI_FILTER(PROMPT('The customer in this ticket is asking for a refund: {0}', body));
```

`AI_FILTER` evaluates the natural-language predicate for each row. `AI_CLASSIFY` returns an object whose `labels` array holds the chosen category.

Summarize themes per product across thousands of reviews:

```sql
SELECT
    product_id,
    AI_AGG(review_text, 'Summarize the most common complaints in these product reviews') AS complaints
FROM sales.reviews
GROUP BY product_id;
```

`AI_AGG` is an aggregate function, so it works with GROUP BY like `SUM` or `COUNT`.

## Best practices

- Prefer the task-specific function (`AI_CLASSIFY`, `AI_EXTRACT`, `AI_SENTIMENT`) over hand-written `AI_COMPLETE` prompts when one fits. They are simpler and easier to keep consistent.
- Test prompts on a small `LIMIT` sample and use `AI_COUNT_TOKENS` to estimate cost before you run a job over a full table.
- Store AI outputs in a table (or an incremental pipeline) instead of recomputing them in every dashboard query.
- Write clear, descriptive category labels and, where the choice is ambiguous, add short label descriptions or a `task_description`.
- Grant `CORTEX_USER` only to roles that need it, and use budgets or monitoring to watch AI spend.

## Common pitfalls

- Calling AI functions inside a frequently refreshed view or BI query, which bills tokens again on every refresh.
- Assuming a NULL result means "no match". It may mean the row failed, so enable `return_error_details` while you debug.
- Putting files on a user or table stage, or a client-side-encrypted stage, and then getting errors when you reference them.
- Using a model that is not available in your region without checking regional availability or cross-region inference settings.
- Expecting deterministic results. LLM output can vary, so validate a sample before downstream logic depends on it.

## Learn more

- [Snowflake Cortex AI Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql)
- [AI_CLASSIFY reference](https://docs.snowflake.com/en/sql-reference/functions/ai_classify)
- [AI_AGG reference](https://docs.snowflake.com/en/sql-reference/functions/ai_agg)

## Knowledge check

### You need to tag 5 million product reviews as positive, negative, or neutral, and you want the simplest, most consistent approach. Which option fits best?
- [ ] Write a custom prompt for AI_COMPLETE and parse the free-text answer
- [x] Use a task-specific function such as AI_SENTIMENT or AI_CLASSIFY and store the results in a table
- [ ] Export the reviews to an external LLM API through a stored procedure
- [ ] Use AI_SUMMARIZE_AGG over the whole column
> Task-specific functions return structured output with a fixed prompt, which makes large-scale labeling simpler and more consistent, and persisting the results avoids paying for tokens again on every query.

### A query using AI_FILTER returns NULL for a handful of rows while the rest succeed. What is the most likely explanation?
- [ ] The whole query failed and Snowflake returned partial results
- [x] Those rows could not be processed, and by default AI functions return NULL for failed rows instead of failing the query
- [ ] NULL means the predicate evaluated to FALSE
- [ ] The warehouse was too small
> By default, AI functions return NULL for rows they cannot process. Setting return_error_details to TRUE returns an object with an error message so you can diagnose the problem.

### Why might an AI_CLASSIFY job cost more after you add descriptions to every category and several few-shot examples?
- [ ] Descriptions force Snowflake to use a larger warehouse
- [ ] Few-shot examples are billed as a separate monthly feature
- [x] Descriptions and examples are sent as input tokens on every call, which increases token consumption
- [ ] Cost does not change; only accuracy changes
> Labels, descriptions, and examples are added to the prompt for each row, so they increase the number of input tokens billed for every classification.
