# Schema Change Management

Schema change management is the practice of versioning and deploying database changes (tables, views, procedures, grants) through code instead of running ad hoc SQL by hand. It keeps development, test, and production environments consistent, makes every change reviewable, and lets you rebuild or roll forward an environment reliably.

## How it works

There are two broad approaches.

**Imperative (migration-based).** You write ordered change scripts, and a tool records which scripts have run in a history table in the target database.

- **schemachange** is an open-source, Python-based tool from Snowflake Labs designed for Snowflake. Scripts follow naming conventions: versioned scripts (`V1.1__create_orders.sql`) run once in order, repeatable scripts (`R__views.sql`) rerun when their content changes, and always scripts (`A__grants.sql`) run every deployment. It records history in a change history table and supports Jinja templating for environment-specific values.
- **Flyway** and **Liquibase** are general-purpose migration tools that support Snowflake. Flyway uses versioned SQL files with a similar `V<version>__<description>.sql` convention. Liquibase uses changelogs (SQL, XML, YAML, or JSON) made of changesets tracked by ID and author, and supports rollback definitions.

**Declarative (state-based).** You describe the desired end state, and the tool computes the changes.

- Snowflake supports `CREATE OR ALTER` for several object types, which creates the object if missing or alters it to match the definition while preserving data where possible.
- Snowflake's DCM (Database Change Management) projects define objects declaratively and plan and deploy changes.
- Terraform is declarative for account-level objects such as warehouses, roles, and grants.

**Trade-offs.**

| | Imperative | Declarative |
| --- | --- | --- |
| Control | Exact SQL for each step, including data migrations | Tool generates changes |
| Readability | Must replay history to see current state | Code shows current state |
| Risk | Script order and drift between environments | Unexpected destructive diffs if tooling misreads intent |

Many teams combine them: declarative or idempotent definitions for views, procedures, and functions; versioned migrations for table changes that involve data.

**Snowflake helpers.** Zero-copy cloning lets you test migrations on a copy of production. Time Travel and `UNDROP` help recover from mistakes within the retention window. Snowflake's Git integration and `EXECUTE IMMEDIATE FROM` can run scripts stored in a repository.

## Example

A schemachange project layout and a versioned script:

```sql
-- migrations/V1.2__add_order_channel.sql
ALTER TABLE {{ database }}.sales.orders ADD COLUMN channel VARCHAR;

UPDATE {{ database }}.sales.orders
SET channel = 'web'
WHERE channel IS NULL;
```

A repeatable script using `CREATE OR ALTER` so it is safe to rerun:

```sql
-- migrations/R__orders_view.sql
CREATE OR ALTER VIEW {{ database }}.sales.v_orders AS
SELECT order_id, customer_id, order_date, amount, channel
FROM {{ database }}.sales.orders;
```

Deploying from CI (schemachange CLI; flags vary by version, so check its README):

```bash
schemachange deploy --config-folder ./config --root-folder ./migrations
```

## Best practices

- Never change shared environments by hand; every change goes through version control and a pipeline.
- Make scripts idempotent where possible (`IF NOT EXISTS`, `CREATE OR ALTER`).
- Separate data-changing migrations from object definitions, and review destructive changes explicitly.
- Test migrations against a zero-copy clone of production before deploying.
- Use one tool per object type to avoid two systems fighting over the same objects.
- Parameterize environment names with templating instead of maintaining copies of scripts.

## Common pitfalls

- Editing a versioned script that has already run; most tools will not rerun it, causing environments to diverge.
- Using `CREATE OR REPLACE TABLE` in migrations, which drops data and history and makes streams stale.
- Hotfixing production directly and forgetting to backport the change to code.
- Relying on rollback scripts that were never tested; plan to roll forward instead.

## Learn more

- [schemachange on GitHub](https://github.com/Snowflake-Labs/schemachange)
- [DevOps with Snowflake](https://docs.snowflake.com/en/developer-guide/builders/devops-with-snowflake)

## Knowledge check

### A developer edits `V1.3__add_index_table.sql` after it was deployed to production. What usually happens on the next deployment?
- [ ] The tool reruns the edited script automatically
- [x] The tool skips it because that version is already recorded, so environments diverge
- [ ] The tool rolls back version 1.3
- [ ] Snowflake rejects the script
> Versioned migrations run once; changes must be made in a new versioned script.

### Which change is safest to place in a repeatable script that reruns whenever its content changes?
- [ ] ALTER TABLE ... DROP COLUMN
- [ ] A one-time data backfill UPDATE
- [x] A view definition using CREATE OR ALTER VIEW
- [ ] CREATE OR REPLACE TABLE on a fact table
> Idempotent definitions such as views can safely be reapplied; destructive or one-time data changes belong in versioned scripts.

### Why test a migration against a zero-copy clone of production?
- [ ] Clones run migrations faster than production
- [x] It validates the change against realistic data and structure without affecting production or duplicating storage up front
- [ ] Clones automatically roll back failed migrations
- [ ] Production cannot run ALTER TABLE
> Cloning creates a full copy of metadata that shares storage, so you can rehearse changes safely and cheaply.
