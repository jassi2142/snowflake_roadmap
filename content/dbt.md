# dbt with Snowflake

dbt (data build tool) lets you build transformation pipelines as modular SQL SELECT statements with tests, documentation, and dependency management. With Snowflake you can run dbt in two ways: externally, with dbt Core or dbt Cloud connecting to Snowflake through the dbt-snowflake adapter, or natively with **dbt Projects on Snowflake**, where the project is stored and executed inside Snowflake.

## How it works

**Core dbt concepts.** A dbt project contains models (`.sql` files with a SELECT), sources, seeds, snapshots, tests, and macros. `ref()` and `source()` build a dependency graph (DAG), and dbt runs models in order. Materializations control what each model becomes: `view`, `table`, `incremental`, `ephemeral`, and with the Snowflake adapter, `dynamic_table`. Profiles define targets (for example `dev` and `prod`) with a role, warehouse, database, and schema.

**External dbt.** dbt Core or dbt Cloud runs on infrastructure outside Snowflake. It connects with a profile (`type: snowflake`), compiles models to SQL, and sends that SQL to your warehouse. Orchestration comes from dbt Cloud jobs, Airflow, or CI tools.

**dbt Projects on Snowflake.** You develop a project in Snowsight **Workspaces** (optionally connected to a Git repository through an API integration), then deploy it as a **dbt project object** with `CREATE DBT PROJECT`. You execute it with `EXECUTE DBT PROJECT`, and you schedule it with a task. Key points from the documentation:

- Each project folder needs a `profiles.yml` or `dbt_projects_profiles.yml` (the latter is specific to dbt Projects on Snowflake and is preferred when both exist). Account and user values are not needed because the project runs in your current Snowflake context.
- `dbt deps` must be run in the workspace to install packages; downloading from hub.getdbt.com or GitHub requires an **external access integration**. Dependencies are installed in the workspace, not by updating a deployed project object.
- Logging, tracing, and metrics can be enabled on the schema that holds the project object to monitor runs.

**Choosing.** External dbt suits teams already invested in dbt Cloud or an external orchestrator. dbt Projects on Snowflake removes separate infrastructure and keeps execution, scheduling (tasks), and governance in Snowflake.

## Example

A model with an incremental materialization, deduplicating late or repeated events with a unique key:

```sql
-- models/fct_orders.sql
{{ config(materialized='incremental', unique_key='order_id') }}

SELECT order_id, customer_id, order_date, amount, updated_at
FROM {{ source('raw', 'orders') }}
{% if is_incremental() %}
WHERE updated_at > (SELECT DATEADD(day, -3, MAX(updated_at)) FROM {{ this }})
{% endif %}
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC) = 1
```

Running a deployed dbt project object in Snowflake and scheduling it with a task:

```sql
EXECUTE DBT PROJECT analytics_db.dbt.sales_project ARGS = 'build --target prod';

CREATE OR REPLACE TASK analytics_db.dbt.nightly_dbt_build
  WAREHOUSE = transform_wh
  SCHEDULE = 'USING CRON 0 3 * * * UTC'
AS
  EXECUTE DBT PROJECT analytics_db.dbt.sales_project ARGS = 'build --target prod';

ALTER TASK analytics_db.dbt.nightly_dbt_build RESUME;
```

## Best practices

- Use separate targets (and ideally separate databases or schemas) for dev and prod, each with its own role.
- Add `unique`, `not_null`, and relationship tests to key models and run `dbt build` so tests gate downstream models.
- For incremental models, use `unique_key` and a lookback window to handle late-arriving data idempotently.
- Keep warehouses per environment and size them to the workload.
- Store the project in Git and promote through pull requests and CI.

## Common pitfalls

- Incremental filters that skip late data or create duplicates without a `unique_key`.
- Running prod builds with a developer's personal role.
- Forgetting the external access integration when `dbt deps` needs to download packages in Snowflake.
- Overusing `table` materializations for large models that rebuild fully every run.

## Learn more

- [dbt Projects on Snowflake](https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake)
- [Tutorial: Get started with dbt Projects on Snowflake](https://docs.snowflake.com/en/user-guide/tutorials/dbt-projects-on-snowflake-getting-started-tutorial)
- [dbt Snowflake setup](https://docs.getdbt.com/docs/local/connect-data-platform/snowflake-setup)

## Knowledge check

### In dbt Projects on Snowflake, `dbt deps` fails when downloading packages from hub.getdbt.com. What is most likely missing?
- [ ] A larger warehouse
- [x] An external access integration with a network rule allowing the package hosts
- [ ] A Snowflake stage for packages
- [ ] The account identifier in the profile
> Code running in Snowflake has no outbound access by default; downloading dependencies needs an external access integration.

### How is a deployed dbt project object typically run on a schedule inside Snowflake?
- [ ] With a dynamic table that calls dbt
- [x] With a task whose body is EXECUTE DBT PROJECT
- [ ] With a stream on the project object
- [ ] With Snowpipe
> Tasks schedule the EXECUTE DBT PROJECT command against the deployed project object.

### An incremental model has no `unique_key` and reprocesses the last 3 days on each run. What happens?
- [ ] dbt automatically deduplicates the rows
- [x] Rows in the overlap window are appended again, creating duplicates
- [ ] dbt switches to a full refresh
- [ ] The model fails to compile
> Without a unique_key, incremental runs append rows, so overlapping windows produce duplicates; a unique_key enables merge behavior.
