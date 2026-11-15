# Tag-based Masking

Tag-based masking binds masking policies to an object tag instead of to individual columns. Once the tag is set on a database, schema, table, or column, every column whose data type matches a policy on the tag is protected automatically, including columns created later. For large estates this turns column-by-column policy assignment into an attribute-based access control (ABAC) model that scales with schema growth.

## How it works

Tag-based masking requires **Enterprise Edition**. The workflow is: create a tag, create masking policies, attach the policies to the tag with `ALTER TAG ... SET MASKING POLICY`, then set the tag on objects.

**One policy per data type per tag.** A tag can hold one masking policy for each data type, for example one for `STRING`, one for `NUMBER`, one for `TIMESTAMP_LTZ`. When a tagged column's type matches a policy signature, that policy applies. Columns without a matching policy are untouched, so plan coverage for every type you store.

**Where to set the tag.**

- **Database or schema:** uses tag inheritance; all current and future tables and views in the container are protected when types match. This is the main design lever for "secure by default" landing zones.
- **Table:** the tag applies to all columns, and new columns added later are protected, analogous to future grants.
- **Column:** the most precise option.

**Precedence.** If a column has a directly assigned masking policy and a tag-based policy, the **direct policy wins**. If a column ends up mapped to multiple masking policies through different tags, queries on it fail with an error ("mapped to multiple masking policies by tags"), and `POLICY_REFERENCES` reports `MULTIPLE_MASKING_POLICY_ASSIGNED_TO_THE_COLUMN`.

**Value-driven policies.** Policy bodies can call `SYSTEM$GET_TAG_ON_CURRENT_COLUMN()` or `SYSTEM$GET_TAG_ON_CURRENT_TABLE()` to branch on the tag's string value, so stewards can change protection by changing a tag value rather than editing policy SQL. Tag names in those calls must be sufficiently qualified or queries fail at runtime.

**Conditional policies** can be attached to a tag; their extra arguments map to columns by name. If the table lacks a column with that name and type, queries fail.

**Privileges.** Assigning a policy to a tag requires the global `APPLY MASKING POLICY` privilege. Setting a tag-based policy on a database or schema additionally requires `APPLY TAG` on the account, or schema ownership plus `APPLY` on the tag.

### Limitations and trade-offs

- A masking policy cannot be assigned to a system tag.
- Neither the tag nor the policy can be dropped while they are linked; nor can their parent schema or database.
- A materialized view cannot be created over a table protected by a tag-based masking policy, and adding such a policy later invalidates existing materialized views.
- A table with a tag-based-masked column cannot serve as a mapping table for other policies.
- Tags applied directly to semantic views do not trigger tag-based masking; tag the base table or column instead.
- When a table is cloned or moved to another schema, protection inherited from the source schema or database does not follow it; the target container's tag-based policy (if any) applies.

## Example

Create a generic policy per data type and attach both to one tag:

```sql
USE ROLE tag_admin;
CREATE OR REPLACE TAG governance.tags.pii;

USE ROLE masking_admin;
CREATE OR REPLACE MASKING POLICY governance.masking_policies.pii_string
  AS (val STRING) RETURNS STRING ->
  CASE WHEN IS_ROLE_IN_SESSION('PII_READER') THEN val ELSE '***MASKED***' END;

CREATE OR REPLACE MASKING POLICY governance.masking_policies.pii_number
  AS (val NUMBER) RETURNS NUMBER ->
  CASE WHEN IS_ROLE_IN_SESSION('PII_READER') THEN val ELSE -1 END;

ALTER TAG governance.tags.pii SET
  MASKING POLICY governance.masking_policies.pii_string,
  MASKING POLICY governance.masking_policies.pii_number;
```

Protect an entire schema, including tables created later:

```sql
ALTER SCHEMA hr.employees SET TAG governance.tags.pii = 'schema_default';
```

Replace a policy atomically, avoiding an unprotected window:

```sql
ALTER TAG governance.tags.pii
  SET MASKING POLICY governance.masking_policies.pii_string_v2 FORCE;
```

Verify coverage:

```sql
SELECT policy_name, ref_column_name, tag_name, policy_status
FROM TABLE(hr.INFORMATION_SCHEMA.POLICY_REFERENCES(
  REF_ENTITY_DOMAIN => 'TABLE',
  REF_ENTITY_NAME   => 'hr.employees.salaries'));
```

## Best practices

- Pair tag-based masking with sensitive data classification and a tag map so newly classified columns are masked without human action.
- Keep one canonical tag per sensitivity class and a complete set of per-type policies on it.
- Use `FORCE` for replacement; an `UNSET` followed by `SET` leaves data unprotected between statements.
- Before rolling out at schema or database level, query `TAG_REFERENCES` and `POLICY_REFERENCES` to find conflicts.

## Common pitfalls

- Missing a data type, for example protecting `STRING` but not `VARIANT`, leaving JSON payloads exposed.
- Stacking tags from different teams on one column, which causes query failures instead of masking.
- Expecting protection to survive a clone into a different schema when it was inherited from the source container.

## Learn more

- [Tag-based masking policies](https://docs.snowflake.com/en/user-guide/tag-based-masking-policies)
- [Attribute-based access control (ABAC) using tag-based policies](https://docs.snowflake.com/en/user-guide/tag-based-policies)

## Knowledge check

### A column has a directly assigned masking policy and also inherits a tag-based masking policy of the same data type from its schema. Which policy is enforced?
- [ ] The tag-based policy, because it is set at a higher level
- [x] The directly assigned policy
- [ ] Both, applied in sequence
- [ ] Neither; the query fails
> Snowflake documents that a masking policy directly assigned to a column takes precedence over a tag-based masking policy.

### Two teams attach different STRING masking policies to two different tags, and both tags land on the same column. What do users experience?
- [ ] The most restrictive policy wins
- [ ] The tag applied most recently wins
- [x] Queries on the column fail with an error about multiple masking policies
- [ ] The column is returned unmasked
> A column can be protected by only one masking policy; multiple tag-mapped policies cause a runtime error until the conflict is resolved.

### You need to swap the STRING policy on a production tag without any window where data is exposed. What should you run?
- [ ] ALTER TAG ... UNSET MASKING POLICY, then ALTER TAG ... SET MASKING POLICY
- [x] ALTER TAG ... SET MASKING POLICY new_policy FORCE
- [ ] DROP MASKING POLICY old_policy, then set the new one
- [ ] CREATE OR REPLACE TAG with the new policy
> FORCE replaces the policy of the same data type in a single statement, whereas two statements leave a gap and dropping a linked policy is not allowed.
