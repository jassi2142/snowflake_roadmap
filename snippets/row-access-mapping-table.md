# Row access policy driven by a mapping table

topics: row-access, role-hierarchy
tags: governance, row-level-security
level: intermediate

Show each team only the rows for its own regions. The role-to-region entitlements live in a table, so you can grant or remove access with an INSERT or DELETE instead of changing the policy.

```sql
USE ROLE rap_admin;   -- needs CREATE TABLE, CREATE ROW ACCESS POLICY, APPLY ROW ACCESS POLICY
USE SCHEMA my_db.governance;

-- 1. Entitlements: which role can see which region
CREATE TABLE IF NOT EXISTS region_entitlements (
  role_name STRING NOT NULL,   -- uppercase role name
  region    STRING NOT NULL
);

INSERT INTO region_entitlements (role_name, region) VALUES
  ('SALES_EMEA', 'EMEA'),
  ('SALES_AMER', 'AMER'),
  ('SALES_AMER', 'LATAM');

-- 2. Policy: admins see everything, others see the regions mapped to any role active in their session
CREATE OR REPLACE ROW ACCESS POLICY region_rap
  AS (row_region STRING) RETURNS BOOLEAN ->
  IS_ROLE_IN_SESSION('SALES_ADMIN')
  OR EXISTS (
    SELECT 1
    FROM my_db.governance.region_entitlements e
    WHERE e.region = row_region
      AND IS_ROLE_IN_SESSION(e.role_name)
  );

-- 3. Attach to the table on the region column (one row access policy per table/view)
ALTER TABLE my_db.sales.orders
  ADD ROW ACCESS POLICY my_db.governance.region_rap ON (region);

-- 4. Test
USE ROLE sales_emea;
SELECT region, COUNT(*) FROM my_db.sales.orders GROUP BY region;   -- EMEA only

-- Grant a new entitlement without touching the policy
-- INSERT INTO my_db.governance.region_entitlements VALUES ('SALES_EMEA', 'APAC');

-- Clean up
-- ALTER TABLE my_db.sales.orders DROP ROW ACCESS POLICY my_db.governance.region_rap;
-- DROP ROW ACCESS POLICY my_db.governance.region_rap;
```

## Notes
- Requires Enterprise Edition or higher.
- The policy owner, not the querying user, needs SELECT on the mapping table. Keep the mapping table in a governance schema that analysts cannot write to, or anyone who can write to it can give themselves access.
- Keep the mapping table small and give it a simple key. Snowflake evaluates the subquery while filtering rows, so large or complex lookups slow down every query on the table.
- Rows are hidden, not masked: aggregates such as COUNT(*) only reflect the rows the role can see.
- To swap policies, drop the old one and add the new one in the same ALTER TABLE statement so no unprotected window opens in between.

## References
- [Understanding row access policies](https://docs.snowflake.com/en/user-guide/security-row-intro)
- [Use row access policies](https://docs.snowflake.com/en/user-guide/security-row-using)
- [CREATE ROW ACCESS POLICY](https://docs.snowflake.com/en/sql-reference/sql/create-row-access-policy)
