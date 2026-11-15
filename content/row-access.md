# Row Access Policies

A row access policy controls which rows a user can see in a table or view. Instead of creating one filtered view per region, team, or customer, you attach a single policy that evaluates each row against the querying user's context and silently removes rows they are not entitled to. It is the row-level counterpart to Dynamic Data Masking.

## How it works

Row access policies require **Enterprise Edition or higher**. A policy is a schema-level object with a **signature** (one or more typed input arguments) and a **body** that returns `BOOLEAN`. When a protected object is queried, Snowflake evaluates the body for each row, mapping the signature arguments to columns you specified when attaching the policy. Rows where the body returns `TRUE` are returned; all others are filtered out before the rest of the query runs.

Key mechanics:

- **Attaching.** Use `ALTER TABLE ... ADD ROW ACCESS POLICY <policy> ON (<col>, ...)`, or the `WITH ROW ACCESS POLICY` clause in `CREATE TABLE` / `CREATE VIEW`. Remove with `DROP ROW ACCESS POLICY`.
- **Mapping tables.** Most real policies look up entitlements in a mapping table (for example, which manager may see which region) using an `EXISTS` subquery. To speed up repeated lookups, replace the subquery with a **memoizable function** that caches the result.
- **Owner's rights.** Policies execute with the privileges of the policy owner, not the querying user. The querying role does not need SELECT on the mapping table, but the policy owner does.
- **Role hierarchy.** Snowflake recommends `IS_ROLE_IN_SESSION()` (account roles) or `IS_DATABASE_ROLE_IN_SESSION()` (database roles) over `CURRENT_ROLE()` when inherited roles should count.
- **Interaction with masking.** A given column can be referenced in either a masking policy signature or a row access policy signature, not both at the same time.

### Privileges

- `CREATE ROW ACCESS POLICY` on a schema to create policies (the schema owner has it automatically).
- `APPLY ROW ACCESS POLICY` on the account to add or drop any policy.
- `APPLY` on a specific policy to let object owners attach just that policy.

## Example

A mapping table defines which sales manager role can see which region:

```sql
CREATE TABLE security.salesmanagerregions (
  sales_manager VARCHAR,
  region        VARCHAR
);

INSERT INTO security.salesmanagerregions VALUES
  ('SALES_MGR_EMEA', 'EMEA'),
  ('SALES_MGR_NA',   'NA');
```

The policy lets executives see all rows and managers see only their mapped regions:

```sql
CREATE OR REPLACE ROW ACCESS POLICY security.sales_policy
  AS (sales_region VARCHAR) RETURNS BOOLEAN ->
    IS_ROLE_IN_SESSION('SALES_EXECUTIVE')
    OR EXISTS (
      SELECT 1 FROM security.salesmanagerregions m
      WHERE m.sales_manager = CURRENT_ROLE()
        AND m.region = sales_region
    );

ALTER TABLE sales.public.orders
  ADD ROW ACCESS POLICY security.sales_policy ON (region);
```

A user running `SELECT * FROM sales.public.orders` with role `SALES_MGR_EMEA` now receives only EMEA rows, with no change to the query.

To improve performance on large mapping tables, cache the allowed values in a memoizable function:

```sql
CREATE OR REPLACE FUNCTION security.allowed_regions(role_name VARCHAR)
  RETURNS ARRAY
  MEMOIZABLE
  AS 'SELECT ARRAY_AGG(region) FROM security.salesmanagerregions WHERE sales_manager = role_name';
```

## Best practices

- Store policies and mapping tables in a dedicated, tightly controlled governance schema.
- Transfer policy ownership to a least-privileged custom role rather than leaving it with SECURITYADMIN or ACCOUNTADMIN.
- Keep the policy body cheap: index-friendly lookups, memoizable functions, and no heavy joins.
- Protect the mapping table itself, because anyone who can change it can change who sees data.
- Test with each relevant role and audit with the `POLICY_REFERENCES` table function.

## Common pitfalls

- Using `CURRENT_ROLE()` and then being surprised that users who inherit a role through hierarchy see no rows.
- Writing `IN (subquery)` instead of `EXISTS`, or complex subqueries that degrade query performance.
- Assuming the querying user needs SELECT on the mapping table; it is the policy owner that needs access.
- Forgetting that a row access policy filters before aggregation, so totals differ by role. Document this for report consumers.

## Learn more

- [Use row access policies](https://docs.snowflake.com/en/user-guide/security-row-using)
- [Understanding row access policies](https://docs.snowflake.com/en/user-guide/security-row-intro)

## Knowledge check

### A policy uses CURRENT_ROLE() = 'SALES_MGR'. A user whose active role is REGIONAL_LEAD, which inherits SALES_MGR, sees no rows. What is the best fix?
- [ ] Grant SELECT on the mapping table to REGIONAL_LEAD
- [x] Rewrite the condition with IS_ROLE_IN_SESSION('SALES_MGR')
- [ ] Attach a second row access policy for REGIONAL_LEAD
- [ ] Make the table a secure view
> CURRENT_ROLE() returns only the active role, while IS_ROLE_IN_SESSION() evaluates the role hierarchy, which is what inherited access requires.

### Analysts querying a protected table do not have SELECT on the policy's mapping table, yet the policy works. Why?
- [ ] Snowflake caches the mapping table for all roles
- [ ] Mapping tables are always public
- [x] Row access policies run with the privileges of the policy owner
- [ ] The analysts inherit SECURITYADMIN at query time
> Policies execute with owner's rights, so only the policy owner needs access to referenced objects.

### Queries on a large fact table slowed down after adding a row access policy with an EXISTS lookup against a big entitlement table. What should you try first?
- [ ] Remove the policy and create one view per region
- [x] Replace the subquery with a memoizable function that caches the allowed values
- [ ] Increase the data retention period of the entitlement table
- [ ] Convert the fact table to a transient table
> Snowflake recommends memoizable functions to cache mapping-table lookups and reduce the per-query cost of policy evaluation.
