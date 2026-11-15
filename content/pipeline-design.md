# Pipeline Design Patterns

Snowflake offers several ways to build transformation pipelines: streams plus tasks, dynamic tables, and dbt (external or dbt Projects on Snowflake). Choosing between them, and making each pipeline idempotent, replayable, and correct under late or duplicate data, is an architectural decision that determines operating cost and incident frequency for years.

## How it works

**Choosing an engine.**

| Approach | Strengths | Trade-offs |
| --- | --- | --- |
| Streams + tasks | Full imperative control, MERGE/DELETE logic, procedural steps, triggered runs | You own offsets, ordering, retries, and failure semantics |
| Dynamic tables | Declarative, dependency inference, snapshot-consistent refresh, incremental where supported | Minimum 60-second lag, SELECT-only definitions, less control over refresh internals |
| dbt | Modular SQL, tests, docs, lineage, CI-friendly, environment targets | Batch-oriented; incremental logic is your responsibility; needs an orchestrator (task or external) |

These compose well: dynamic tables or dbt for set-based transformation, streams and tasks for procedural CDC application, SCD handling, or external side effects. dbt can also materialize dynamic tables.

**Idempotency.** A step is idempotent when re-running it for the same input produces the same result. This is what makes retries (`TASK_AUTO_RETRY_ATTEMPTS`, `EXECUTE TASK ... RETRY LAST`) and backfills safe. Techniques:

- Use `MERGE` on a business key instead of blind `INSERT`.
- Deduplicate the source within the batch (`QUALIFY ROW_NUMBER() OVER (PARTITION BY key ORDER BY event_ts DESC) = 1`) so MERGE sees one row per key; a MERGE where multiple source rows match one target row is nondeterministic.
- For partition-style loads, delete-then-insert a bounded window (for example, one day) inside one transaction.
- Consume streams inside explicit transactions when several statements must see the same delta; the offset advances only on commit, so a failed run replays the same changes.

**SCD Type 2.** Keep history by closing the current row and inserting a new version. A common pattern is a single MERGE driven by a union: one branch matches existing current rows to expire them, the other carries a NULL key so it always lands in `WHEN NOT MATCHED` and inserts the new version. Use a hash of tracked attributes to detect real changes cheaply.

**Late-arriving data.** Decide on event time versus load time. Incremental models that filter on `max(loaded_at)` miss late events keyed by event time; reprocess a trailing window (for example, the last 3 days) with idempotent MERGE, or base CDC on streams, which capture changes by commit rather than by event timestamp.

**Backfills.** Parameterize date ranges (task graph `CONFIG`, dbt vars), run against a zero-copy clone first, and keep backfill compute separate from production warehouses. For dynamic tables, a backfill of base data is picked up by normal refresh; a definition change triggers reinitialization.

## Example

SCD Type 2 from a stream of customer changes, applied in one MERGE:

```sql
MERGE INTO dim_customer d
USING (
  SELECT s.customer_id AS join_key, s.*
  FROM customer_changes s
  UNION ALL
  SELECT NULL AS join_key, s.*
  FROM customer_changes s
  JOIN dim_customer d
    ON d.customer_id = s.customer_id AND d.is_current
  WHERE d.attr_hash <> s.attr_hash
) src
ON d.customer_id = src.join_key AND d.is_current
WHEN MATCHED AND d.attr_hash <> src.attr_hash THEN
  UPDATE SET d.is_current = FALSE, d.valid_to = src.changed_at
WHEN NOT MATCHED THEN
  INSERT (customer_id, name, tier, attr_hash, valid_from, valid_to, is_current)
  VALUES (src.customer_id, src.name, src.tier, src.attr_hash, src.changed_at, NULL, TRUE);
```

Here `customer_changes` is a deduplicated view over a stream (one row per key, `attr_hash` precomputed). Existing changed customers are expired by the first branch and re-inserted by the NULL-key branch; brand-new customers insert through the first branch.

## Best practices

- Default to declarative (dynamic tables or dbt) and drop to streams and tasks where you need procedural control.
- Make every step idempotent before enabling automatic retries.
- Deduplicate source batches before MERGE and enforce one row per key.
- Model late data explicitly with a reprocessing window and document the lateness SLA.
- Rehearse backfills on clones and isolate their compute.
- Monitor freshness (dynamic table lag, task history, stream `STALE_AFTER`) as first-class signals.

## Common pitfalls

- MERGE with duplicate source keys, causing nondeterministic results or errors.
- Incremental filters on load time that silently drop late events.
- Multiple consumers on one stream, so each sees partial changes.
- `CREATE OR REPLACE` on source tables during maintenance, which makes downstream streams stale.
- Mixing orchestration layers (external scheduler, tasks, and dynamic table lag) without a single owner of freshness.

## Learn more

- [Dynamic tables](https://docs.snowflake.com/en/user-guide/dynamic-tables/overview)
- [Introduction to streams](https://docs.snowflake.com/en/user-guide/streams-intro)
- [Create a sequence of tasks with a task graph](https://docs.snowflake.com/en/user-guide/tasks-graphs)

## Knowledge check

### A task graph has automatic retries enabled. One child task appends rows with INSERT and occasionally fails mid-graph. What is the main risk, and the fix?
- [ ] Retries are blocked for INSERT; switch to serverless
- [x] Retries can duplicate rows; make the step idempotent with MERGE on a key or delete-then-insert of a bounded window
- [ ] Retries reset stream offsets; drop the stream before each run
- [ ] There is no risk because tasks are transactional across the whole graph
> Retries are only safe when steps are idempotent; blind INSERT can apply the same batch twice.

### A dbt incremental model filters `WHERE event_ts > (SELECT MAX(event_ts) FROM {{ this }})`. Mobile events can arrive up to 48 hours late. What happens and what should change?
- [ ] Nothing; dbt handles late data automatically
- [ ] Late events are duplicated; switch to a full refresh
- [x] Late events older than the current max are skipped; reprocess a trailing window with a unique_key merge
- [ ] dbt fails the run; add a test
> Filtering on max event time skips late rows; a lookback window combined with merge on a unique key captures them idempotently.

### A team needs a simple aggregated reporting layer with 15-minute freshness, but also needs to call an external API whenever an order is cancelled. What design fits best?
- [ ] One dynamic table that calls the API through an external function
- [x] Dynamic tables for the reporting layer, and a stream plus task (calling a procedure) for the cancellation side effect
- [ ] Only dbt models scheduled every 15 minutes
- [ ] A single task that rebuilds everything with CREATE OR REPLACE TABLE
> Dynamic tables suit declarative SELECT-based layers but cannot call procedures or external functions; procedural side effects belong in streams and tasks.
