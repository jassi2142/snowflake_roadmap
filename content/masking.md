# Dynamic Data Masking

Dynamic Data Masking is a column-level security feature that hides sensitive values at query time based on who is asking. The data stored in the table never changes; instead, Snowflake rewrites each query so that authorized users see real values and everyone else sees masked, hashed, or NULL values. This lets one table serve many audiences without maintaining separate redacted copies.

## How it works

Dynamic Data Masking requires **Enterprise Edition or higher**. The core object is a **masking policy**, a schema-level object that contains a SQL expression (usually a `CASE`) taking the column value as input and returning either the original value or a masked version.

- **Query rewrite.** When a query touches a protected column, Snowflake applies the policy expression everywhere the column appears: projections, `WHERE` and join predicates, `ORDER BY`, and `GROUP BY`. Users cannot bypass the policy by filtering or joining on the raw column.
- **Execution context.** Policies typically branch on context functions such as `CURRENT_ROLE()` or `IS_ROLE_IN_SESSION()`, or on `CURRENT_ACCOUNT()` to unmask only in production.
- **Matching data types.** The input and output data types of a policy must match. You cannot mask a `TIMESTAMP` column by returning the string `'***'`; return a fabricated timestamp instead.
- **Conditional masking.** A policy can accept additional columns from the same row (for example, a consent flag) so the masking decision depends on row data as well as the user.
- **Subqueries and lookups.** A policy can consult an entitlement table. Use `EXISTS` when a subquery appears in the policy body, and consider a memoizable function to cache lookups for performance.
- **Applying policies.** You set a policy on a table or view column with `ALTER TABLE ... MODIFY COLUMN ... SET MASKING POLICY`, or at creation time in `CREATE TABLE` / `CREATE VIEW`.

### Privileges

| Privilege | Object | Purpose |
| --- | --- | --- |
| CREATE MASKING POLICY | Schema | Create policies |
| APPLY MASKING POLICY | Account | Set or unset any policy on any column |
| APPLY | Masking policy | Let object owners set one specific policy |

Separating these privileges lets a security team own policy logic while data owners only attach approved policies.

## Example

Create a dedicated policy administrator role and grant it the needed privileges:

```sql
USE ROLE USERADMIN;
CREATE ROLE masking_admin;

USE ROLE SECURITYADMIN;
GRANT CREATE MASKING POLICY ON SCHEMA governance.policies TO ROLE masking_admin;
GRANT APPLY MASKING POLICY ON ACCOUNT TO ROLE masking_admin;
```

Define a partial mask for emails: analysts see everything, support sees only the domain, everyone else sees a fixed mask.

```sql
USE ROLE masking_admin;

CREATE OR REPLACE MASKING POLICY governance.policies.email_mask
  AS (val STRING) RETURNS STRING ->
  CASE
    WHEN CURRENT_ROLE() IN ('ANALYST') THEN val
    WHEN CURRENT_ROLE() IN ('SUPPORT') THEN REGEXP_REPLACE(val, '.+\@', '*****@')
    ELSE '********'
  END;

ALTER TABLE crm.public.customers
  MODIFY COLUMN email SET MASKING POLICY governance.policies.email_mask;
```

A conditional policy that unmasks only when the customer has consented. The second argument is mapped to another column with `USING`:

```sql
CREATE OR REPLACE MASKING POLICY governance.policies.email_consent_mask
  AS (email STRING, consent STRING) RETURNS STRING ->
  CASE
    WHEN CURRENT_ROLE() = 'ANALYST' AND consent = 'YES' THEN email
    ELSE '********'
  END;

ALTER TABLE crm.public.customers
  MODIFY COLUMN email UNSET MASKING POLICY;

ALTER TABLE crm.public.customers
  MODIFY COLUMN email SET MASKING POLICY governance.policies.email_consent_mask
  USING (email, consent);
```

## Best practices

- Centralize policies in a dedicated governance database and schema, owned by a custom role rather than ACCOUNTADMIN.
- Prefer `IS_ROLE_IN_SESSION()` over `CURRENT_ROLE()` when you want role hierarchy and secondary roles to count.
- Keep policy logic simple and reuse a small set of policies per data type; consider tag-based masking to scale.
- Use `DESCRIBE MASKING POLICY` or `GET_DDL` before changing a policy, and test with several roles after each change.

## Common pitfalls

- Returning a different data type than the input, which fails at policy creation or query time.
- Hashing with `SHA2` and assuming it is irreversible or collision-free; hashes of low-cardinality values can be guessed.
- Forgetting that masked values still flow into joins and aggregates, which can change query results for masked users.
- Granting APPLY MASKING POLICY too broadly, allowing anyone to unset protection.

## Learn more

- [Using Dynamic Data Masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-use)
- [Understanding Dynamic Data Masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro)

## Knowledge check

### A user with a role that should see masked emails runs `SELECT COUNT(*) FROM customers WHERE email = 'jane@example.com'`. What happens?
- [ ] The filter uses the raw value, so the user can confirm whether Jane exists
- [x] The policy is applied in the WHERE clause too, so the comparison is against the masked value
- [ ] The query fails because masked columns cannot be filtered
- [ ] The policy is ignored for aggregate queries
> Snowflake rewrites every occurrence of the protected column, including predicates, so unauthorized users cannot probe raw values through filters.

### You need to mask a TIMESTAMP_NTZ column for non-HR users. Which policy body is valid?
- [ ] Return the string '***MASKED***' for non-HR users
- [x] Return a fixed timestamp such as DATE_FROM_PARTS(0001, 01, 01)::TIMESTAMP_NTZ for non-HR users
- [ ] Return NULL cast to VARCHAR for non-HR users
- [ ] Return the column cast to VARCHAR with digits replaced
> Masking policy input and output types must match, so a timestamp column must return a timestamp value.

### Your security team wants to own policy definitions, but table owners should attach only one approved policy to their own columns. What is the best privilege design?
- [ ] Grant APPLY MASKING POLICY on the account to every table owner
- [ ] Transfer ownership of the policy to each table owner
- [x] Keep CREATE MASKING POLICY with the security role and grant APPLY on that specific policy to table owners
- [ ] Grant ACCOUNTADMIN to table owners during deployments
> The policy-level APPLY privilege decentralizes set/unset operations for a single policy while the security team keeps control of its logic.
