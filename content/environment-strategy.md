# Environment Strategy

An environment strategy defines how development, test, and production are separated in Snowflake, how code and data move between them, and how sensitive data is protected outside production. The choice between separate accounts and separate databases within one account shapes security boundaries, cost visibility, governance overhead, and how cheaply you can give engineers realistic data.

## How it works

**Isolation models.**

| Model | Isolation | Pros | Cons |
| --- | --- | --- | --- |
| Separate accounts per environment (in one organization) | Strongest: separate users, roles, integrations, network policies, parameters | Clear blast radius; account-level changes (integrations, policies, parameters) can be tested safely; clean cost separation | Cross-account data movement needs replication or sharing; zero-copy cloning does not cross accounts; more administration |
| Separate databases per environment in one account (`DEV_`, `TEST_`, `PROD_`) | Logical, enforced by RBAC | Zero-copy clones from prod are instant; simple administration; one set of integrations | Account-level objects are shared; a misconfigured grant can expose prod; harder to test account-wide changes |
| Hybrid | Prod in its own account; dev and test share a non-prod account | Balances isolation and convenience | Non-prod data refresh requires replication or sharing from prod |

Regulated workloads usually justify separate production accounts. Smaller teams often start with database-level separation and a strict role model.

**Getting realistic data into lower environments.**

- **Zero-copy cloning** (`CREATE DATABASE ... CLONE`) creates a copy that shares storage with the source until data changes, so it is fast and cheap initially. Clones work within an account only. Cloning a database copies child objects; privileges on the source database itself are not copied to the clone, though child objects keep their grants by default.
- **Across accounts**, use database replication or secure data sharing from production, then clone locally in the target account.

**Protecting data outside production.** Cloned or replicated data is a copy of production data. Options:

- **Dynamic data masking** and row access policies (Enterprise Edition or higher) attached to sensitive columns. Policies travel with cloned objects, and policy bodies can check `CURRENT_ACCOUNT()` or the role so that lower environments always see masked values.
- **Static masking**: build sanitized copies with transformations (hashing, tokenization, synthetic values) and never expose raw prod data to dev.
- Use tag-based masking so newly classified columns are protected automatically.

**Promotion.** Code is promoted, not data: the same Git artifact is deployed to dev, then test, then prod through CI/CD, with environment-specific values (database names, warehouse sizes) supplied by templating or variables. Data flows from prod into lower environments, never in the reverse direction.

**Naming and parameterization.** Keep object names identical across environments except for a prefix or the account, so code needs only one variable (for example `{{ env }}_ANALYTICS`). Use separate warehouses and resource monitors per environment for cost control.

## Example

Refresh a test database from production with a clone, then grant access to the test role. A masking policy that is attached in production follows the cloned columns.

```sql
CREATE OR REPLACE MASKING POLICY governance.policies.mask_email
  AS (val STRING) RETURNS STRING ->
  CASE
    WHEN CURRENT_ROLE() IN ('PROD_PII_READER') THEN val
    ELSE REGEXP_REPLACE(val, '.+@', '****@')
  END;

ALTER TABLE prod_analytics.crm.customers
  MODIFY COLUMN email SET MASKING POLICY governance.policies.mask_email;

CREATE OR REPLACE DATABASE test_analytics CLONE prod_analytics;

GRANT USAGE ON DATABASE test_analytics TO ROLE test_engineer;
GRANT USAGE ON ALL SCHEMAS IN DATABASE test_analytics TO ROLE test_engineer;
GRANT SELECT ON ALL TABLES IN DATABASE test_analytics TO ROLE test_engineer;
```

Because the policy lives in a separate governance database, the cloned table still references it, and test roles see masked emails.

## Best practices

- Put production in its own account when compliance, network isolation, or account-level change testing matters.
- Promote code through CI/CD from a single artifact; never hand-edit production.
- Mask sensitive data in every non-production environment, ideally with policies based on role or account that cannot be bypassed by cloning.
- Automate clone refreshes and drops so stale or forgotten clones do not accumulate storage.
- Give each environment its own warehouses, roles, and resource monitors.
- Keep governance objects (policies, tags) in a dedicated database managed by a governance role.

## Common pitfalls

- Assuming clones are free forever; storage grows as the clone or source diverges.
- Cloning prod into dev without masking, exposing PII to broad roles.
- Expecting zero-copy cloning to work across accounts.
- Hardcoding database names in code, which blocks promotion.
- Letting data flow from dev back into prod.

## Learn more

- [Cloning considerations](https://docs.snowflake.com/en/user-guide/object-clone)
- [Understanding Dynamic Data Masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro)

## Knowledge check

### A bank must test changes to network policies and security integrations without risk to production. Which model fits best?
- [ ] One account with DEV_, TEST_, and PROD_ databases
- [x] Separate accounts for production and non-production
- [ ] One database with DEV and PROD schemas
- [ ] Separate warehouses per environment in one account
> Network policies and integrations are account-level, so only a separate account isolates their testing from production.

### Prod and test live in separate accounts. A team wants a fresh copy of prod data in test each week. What works?
- [ ] CREATE DATABASE test CLONE prod_account.prod_db
- [x] Replicate or share the prod database to the test account, then clone locally there
- [ ] Use Time Travel to read prod from test
- [ ] Copy data using COPY INTO from a worksheet
> Zero-copy cloning works only within an account; replication or sharing moves data across accounts first.

### Developers query a clone of prod in a lower environment. How can PII be protected without maintaining separate sanitized copies?
- [ ] Clones automatically strip PII
- [x] Attach masking policies to sensitive columns in prod; the clone keeps the policy references and non-privileged roles see masked values
- [ ] Revoke OWNERSHIP on the clone
- [ ] Use a larger warehouse for dev
> Masking policies stay attached to cloned columns, so the same role-based logic masks data in the lower environment.
