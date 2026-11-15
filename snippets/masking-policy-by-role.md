# Role-aware masking policy with IS_ROLE_IN_SESSION

topics: masking, role-hierarchy
tags: governance, masking, pii
level: intermediate

Show full email addresses only to roles that are allowed to see PII, a partially masked value to support staff, and a fixed mask to everyone else. `IS_ROLE_IN_SESSION` checks the whole active role hierarchy (and secondary roles), so it keeps working when the allowed role is granted to other roles.

```sql
USE ROLE masking_admin;           -- custom role with CREATE MASKING POLICY + APPLY MASKING POLICY
USE SCHEMA my_db.governance;

-- 1. Policy: input and return types must match the column type
CREATE OR REPLACE MASKING POLICY email_mask
  AS (val STRING) RETURNS STRING ->
  CASE
    WHEN IS_ROLE_IN_SESSION('PII_READER') THEN val                          -- full value
    WHEN IS_ROLE_IN_SESSION('SUPPORT')    THEN REGEXP_REPLACE(val, '^[^@]+', '*****')  -- *****@example.com
    ELSE '***MASKED***'
  END
  COMMENT = 'Email masking by role hierarchy';

-- 2. Attach to a column (one masking policy per column)
ALTER TABLE my_db.sales.customers
  MODIFY COLUMN email SET MASKING POLICY my_db.governance.email_mask;

-- 3. Test with roles that land in each branch
USE ROLE support;
SELECT customer_id, email FROM my_db.sales.customers LIMIT 5;   -- *****@example.com
USE ROLE analyst;
SELECT customer_id, email FROM my_db.sales.customers LIMIT 5;   -- ***MASKED***

-- 4. Find where the policy is used
SELECT policy_name, ref_entity_name, ref_column_name, policy_status
FROM TABLE(my_db.INFORMATION_SCHEMA.POLICY_REFERENCES(
       POLICY_NAME => 'my_db.governance.email_mask'));

-- Replace the policy in place without a protection gap
-- ALTER TABLE my_db.sales.customers MODIFY COLUMN email
--   SET MASKING POLICY my_db.governance.email_mask_v2 FORCE;

-- Clean up
-- ALTER TABLE my_db.sales.customers MODIFY COLUMN email UNSET MASKING POLICY;
-- DROP MASKING POLICY my_db.governance.email_mask;
```

## Notes
- Requires Enterprise Edition or higher.
- The creating role needs CREATE MASKING POLICY on the schema. Applying it needs APPLY MASKING POLICY on the account, or APPLY on the policy plus OWNERSHIP of the table.
- `CURRENT_ROLE()` only checks the primary role. `IS_ROLE_IN_SESSION` also matches inherited and secondary roles, which is usually what you want.
- Role names in the policy are string literals and are case-sensitive: use the uppercase form.
- A policy can't be dropped while it is attached to a column. Unset it first.

## References
- [Understanding Dynamic Data Masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro)
- [CREATE MASKING POLICY](https://docs.snowflake.com/en/sql-reference/sql/create-masking-policy)
- [IS_ROLE_IN_SESSION](https://docs.snowflake.com/en/sql-reference/functions/is_role_in_session)
