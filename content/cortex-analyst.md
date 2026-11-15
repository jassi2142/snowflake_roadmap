# Cortex Analyst & Semantic Views

Cortex Analyst turns natural-language business questions into SQL, and semantic views are the schema-level objects that give it, and any SQL client, a governed business model of your data. Getting the semantic layer right is the main determinant of text-to-SQL accuracy, and it also provides a single definition of metrics that BI tools, agents, and engineers can share.

## How it works

A **semantic view** (`CREATE SEMANTIC VIEW`) declares:

- **TABLES**: logical tables over physical tables or views, with `PRIMARY KEY` and `UNIQUE` columns that define join cardinality.
- **RELATIONSHIPS**: foreign-key style joins between logical tables, including `ASOF` joins and range joins (`BETWEEN ... EXCLUSIVE`, Preview).
- **FACTS**: row-level expressions (which can be `PRIVATE`).
- **DIMENSIONS**: attributes to group and filter by. Dimensions can be backed by a Cortex Search service for fuzzy value matching.
- **METRICS**: aggregations, including derived metrics across tables, window-function metrics, semi-additive metrics (`NON ADDITIVE BY`), and `USING (relationship)` to disambiguate multiple join paths.
- **AI instructions**: `AI_SQL_GENERATION`, `AI_QUESTION_CATEGORIZATION`, and `AI_VERIFIED_QUERIES` (curated question and SQL pairs).

Clause order matters: FACTS must come before DIMENSIONS, which come before METRICS. At least one dimension or metric is required.

Semantic views are queryable with plain SQL through the `SEMANTIC_VIEW(...)` clause, so they double as a metrics layer. The engine generates the joins and aggregation grain, which prevents fan-out double counting. Cortex Analyst consumes the same object through its REST API or as a tool in Cortex Agents. Some advanced constructs, such as level-of-detail (LOD) metrics, currently work only in SQL and are not yet used by Cortex Analyst or agents.

**Privileges**: creating one requires `CREATE SEMANTIC VIEW` on the schema and SELECT on the referenced tables. Querying requires only SELECT on the semantic view itself, like a standard view.

Authoring paths: DDL, or YAML via `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML` (pass TRUE as the third argument to validate without creating). `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW` round-trips back to YAML, which is useful for Git-based workflows. `CREATE OR ALTER SEMANTIC VIEW` preserves grants. Note that it unsets properties you omit and does not change tags.

## Example

A compact semantic view over the TPC-H sample data, with a verified query:

```sql
CREATE OR REPLACE SEMANTIC VIEW analytics.semantic.revenue_sv
  TABLES (
    orders AS SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS PRIMARY KEY (o_orderkey)
      WITH SYNONYMS ('sales orders'),
    customers AS SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER PRIMARY KEY (c_custkey)
  )
  RELATIONSHIPS (
    orders_to_customers AS orders (o_custkey) REFERENCES customers
  )
  DIMENSIONS (
    customers.market_segment AS c_mktsegment COMMENT = 'Customer market segment',
    orders.order_year AS YEAR(o_orderdate)
  )
  METRICS (
    orders.total_revenue AS SUM(o_totalprice) COMMENT = 'Gross order value',
    orders.order_count AS COUNT(o_orderkey)
  )
  COMMENT = 'Revenue analysis'
  AI_SQL_GENERATION 'Round currency values to 2 decimal places.';
```

Query it directly in SQL. The engine resolves joins and grain:

```sql
SELECT * FROM SEMANTIC_VIEW(
  analytics.semantic.revenue_sv
  DIMENSIONS customers.market_segment, orders.order_year
  METRICS orders.total_revenue
)
ORDER BY order_year, market_segment;
```

## Best practices

- Model by business domain with a bounded scope. Several focused semantic views usually outperform one sprawling view, and agents can route across multiple views.
- Declare primary keys accurately. Cardinality inference drives join correctness and fan-out protection.
- Invest in descriptions, synonyms, sample values, and verified queries for the questions users actually ask. These are the highest-leverage accuracy inputs.
- Encode tricky semantics explicitly: `NON ADDITIVE BY` for balances and snapshots, `USING` for role-playing joins, and derived metrics for ratios.
- Keep definitions in source control (DDL or YAML) and deploy through CI/CD. Build an evaluation set of question and expected-result pairs and run it on every change.
- Grant SELECT on the semantic view instead of the base tables when you want consumers to use governed metrics only.

## Common pitfalls

- Pointing Cortex Analyst at raw, wide tables with cryptic column names and no descriptions, then blaming the model for poor accuracy.
- Defining two relationships between the same tables without `USING` on metrics, which makes queries fail with a multi-path error.
- Summing snapshot measures such as account balances across time because the metric was not marked non-additive.
- Using `CREATE OR REPLACE` without `COPY GRANTS` and silently dropping consumer grants.
- Relying on LOD metrics in an agent experience before checking that Cortex Analyst supports them.

## Learn more

- [CREATE SEMANTIC VIEW](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)
- [Using SQL commands to create and manage semantic views](https://docs.snowflake.com/en/user-guide/views-semantic/sql)
- [YAML vs DDL authoring for semantic views](https://docs.snowflake.com/en/user-guide/views-semantic/yaml-vs-ddl)

## Knowledge check

### A flights table joins to an airports table twice (departure and arrival). Queries asking for flight counts by city fail. What is the correct fix in the semantic view?
- [ ] Remove one of the relationships
- [x] Define metrics with USING (relationship_name) so each metric specifies which join path to use
- [ ] Mark the airports dimensions as PRIVATE
- [ ] Add an AI_SQL_GENERATION instruction telling Analyst which column to use
> Multiple relationship paths are ambiguous. The USING clause binds each metric to a specific relationship, for example departure versus arrival counts.

### A finance user asks for "total balance by year" and gets a figure that sums every daily snapshot. Which modeling change fixes this at the source?
- [ ] Add a verified query for that exact question
- [ ] Change the metric to AVG(balance)
- [x] Declare the metric with NON ADDITIVE BY on the date dimensions so the latest snapshot per period is aggregated
- [ ] Use a window function in the BI tool
> NON ADDITIVE BY makes the metric semi-additive: rows are sorted by the listed dimensions and the last snapshot is aggregated, which is the correct semantics for balances.

### You want BI developers to use governed revenue metrics without being able to query the underlying order tables. What grant model achieves this?
- [ ] Grant SELECT on the base tables and rely on naming conventions
- [x] Grant SELECT on the semantic view only, because querying a semantic view does not require SELECT on its base tables
- [ ] Grant REFERENCES on the semantic view
- [ ] Share the YAML file with the developers
> As with standard views, SELECT on the semantic view is sufficient to query it, so base tables can stay restricted to the owning role.
