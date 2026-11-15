# CI/CD Pipelines

CI/CD for Snowflake means every change to database objects, transformation code, and platform configuration flows from Git through automated validation and deployment, rather than being run by hand. For senior engineers the design questions are less about which YAML to write and more about authentication, environment promotion, deployment ordering, blast radius, and how to make database deployments safe when data, unlike application binaries, cannot simply be replaced.

## How it works

**Building blocks.**

- **Source of truth**: a Git repository containing migrations or declarative definitions, dbt projects, procedure and UDF code, and infrastructure code (Terraform).
- **Runner**: GitHub Actions, GitLab CI, Azure DevOps, Jenkins, or similar.
- **Deployment tooling**: Snowflake CLI (`snow`), schemachange, Flyway or Liquibase, dbt, Terraform, or Snowflake-native options such as `EXECUTE IMMEDIATE FROM` a Git repository clone and dbt Projects on Snowflake.
- **Identity**: a dedicated service user per environment. Prefer key-pair authentication or workload identity federation (OIDC from the CI provider) over long-lived passwords; Snowflake service users (`TYPE = SERVICE`) cannot log in with passwords.

**Typical pipeline stages.**

1. **Pull request (CI)**: lint SQL, compile dbt, run unit tests, and deploy to an ephemeral environment, often a zero-copy clone of production or a per-PR database. Run dbt tests and data checks there.
2. **Merge to main**: deploy to a shared test or staging environment; run integration tests.
3. **Release**: tag a version and deploy to production after approval gates.

**Ordering and dependencies.** Deploy in dependency order: account objects (roles, warehouses, integrations) via Terraform, then schemas and tables via migrations, then views, functions, and procedures, then transformations (dbt), then tasks, resumed last. Suspend task graphs before altering them; Snowflake requires the root task to be suspended to modify tasks in a graph.

**Data-aware safety.** Databases carry state, so "rollback" usually means roll forward. Useful mechanisms:

- Zero-copy clones to rehearse migrations against production-shaped data.
- Time Travel and `UNDROP` as a recovery net within the retention period.
- Blue/green patterns with `ALTER TABLE ... SWAP WITH` or `ALTER SCHEMA ... SWAP WITH` to cut over atomically after validating a new build.
- Idempotent scripts (`CREATE OR ALTER`, `IF NOT EXISTS`) so reruns are harmless.

**Trade-offs.** Ephemeral clones per PR give strong isolation but incur compute and clone-management overhead; clean them up automatically. A single deployment tool reduces cognitive load, but most mature platforms combine Terraform (account level), migrations or declarative definitions (schema level), and dbt (transformations), with clear ownership boundaries.

## Example

A GitHub Actions job that deploys from a tagged release using the Snowflake CLI with key-pair authentication.

```yaml
name: deploy-prod
on:
  push:
    tags: ["v*"]
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    env:
      SNOWFLAKE_CONNECTIONS_PROD_ACCOUNT: ${{ secrets.SF_ACCOUNT }}
      SNOWFLAKE_CONNECTIONS_PROD_USER: ${{ secrets.SF_USER }}
      SNOWFLAKE_CONNECTIONS_PROD_AUTHENTICATOR: SNOWFLAKE_JWT
      SNOWFLAKE_CONNECTIONS_PROD_PRIVATE_KEY_RAW: ${{ secrets.SF_PRIVATE_KEY }}
      SNOWFLAKE_CONNECTIONS_PROD_ROLE: DEPLOY_PROD
      SNOWFLAKE_CONNECTIONS_PROD_WAREHOUSE: DEPLOY_WH
    steps:
      - uses: actions/checkout@v4
      - name: Install Snowflake CLI
        run: pip install snowflake-cli
      - name: Fetch repo clone and deploy
        run: |
          snow sql -c prod -q "ALTER GIT REPOSITORY platform.git.data_platform FETCH"
          snow sql -c prod -q "EXECUTE IMMEDIATE FROM @platform.git.data_platform/tags/${GITHUB_REF_NAME}/deploy/prod.sql"
```

The `environment: production` setting lets GitHub enforce required reviewers before the job runs. Check the Snowflake CLI and action documentation for current connection variable names and versions.

## Best practices

- Use separate service users and roles per environment; the prod deploy role should not be usable from PR jobs.
- Require approvals for production and deploy from immutable tags.
- Validate on clones of production data, and mask sensitive columns in non-production.
- Keep deployments idempotent and ordered by dependency; resume tasks as the final step.
- Store credentials in the CI secret store or use OIDC-based federation; rotate keys.
- Clean up ephemeral databases and clones automatically to control storage and cost.

## Common pitfalls

- Using ACCOUNTADMIN or a personal user in pipelines.
- Altering task graphs without suspending the root, causing deployment failures.
- `CREATE OR REPLACE TABLE` in deployments, destroying data and making streams stale.
- Allowing manual hotfixes in production that are never committed, causing drift.
- Assuming rollback scripts work without testing them.

## Learn more

- [DevOps with Snowflake](https://docs.snowflake.com/en/developer-guide/builders/devops-with-snowflake)
- [Working with Git repositories](https://docs.snowflake.com/en/developer-guide/git/git-operations)

## Knowledge check

### Your pipeline must deploy a change that adds a column to a fact table, updates three views, and modifies a child task in a running task graph. What deployment order is safest?
- [ ] Modify the child task first, then the table, then views
- [x] Suspend the root task, alter the table, apply the views, modify the child task, then resume the graph
- [ ] Recreate the table with CREATE OR REPLACE, then views, leaving tasks running
- [ ] Apply all changes in parallel to minimize downtime
> Dependencies flow from tables to views to tasks, and tasks in a graph can only be modified while the root task is suspended.

### Security asks that no long-lived passwords exist for CI. Which approach fits Snowflake best?
- [ ] A shared human user with MFA disabled
- [x] A service user per environment with key-pair authentication or workload identity federation from the CI provider
- [ ] Store the ACCOUNTADMIN password in the repository encrypted
- [ ] Use OAuth from an analyst's browser session
> Service users with key pairs or federated identity avoid stored passwords and limit privileges per environment.

### A risky refactor rebuilds a large reporting schema. How can you cut over atomically with a fallback?
- [ ] Drop the old schema and rebuild it in place
- [x] Build into a new schema, validate it, then use ALTER SCHEMA ... SWAP WITH; swap back if needed
- [ ] Deploy during low traffic and hope no queries run
- [ ] Use a stream to replay changes
> Swapping exchanges the two schemas in a single operation, and the old version remains available for a quick swap back.
