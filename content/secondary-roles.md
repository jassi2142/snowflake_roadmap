# Secondary Roles

Secondary roles let a session use the combined privileges of several roles at once, instead of only the single primary role. They change how authorization is evaluated in every session, so architects need to understand both the convenience they provide and the boundaries they blur.

## How it works

Every session has exactly one **primary role** (set by `USE ROLE` or the user's `DEFAULT_ROLE`) and any number of **secondary roles** (set by `USE SECONDARY ROLES` or the user's `DEFAULT_SECONDARY_ROLES`).

Authorization rules:

- **CREATE statements are authorized by the primary role only**, and the new object is owned by the primary role. Only the primary role and the roles it inherits are considered when checking privileges needed to create an object.
- **Every other action** - SELECT, INSERT, DDL on existing objects, using a warehouse - can be authorized by the primary role, any secondary role, or anything they inherit. If any active secondary role owns an object, it can authorize DDL on that object.
- **User-based access control (UBAC)**: privileges granted directly to a user are considered only when secondary roles are set to `ALL`.
- Database roles and application roles can be neither primary nor secondary roles.

`CURRENT_SECONDARY_ROLES()` shows what is active. Options are `USE SECONDARY ROLES ALL`, `USE SECONDARY ROLES NONE`, or a specific list of roles.

### The default changed to ALL

With behavior change bundle 2024_08 (now generally enabled and no longer reversible at the bundle level), users with an unset `DEFAULT_SECONDARY_ROLES` were changed to `('ALL')`, and new users are created with `('ALL')` unless explicitly set to `()`. Users gain no new privileges, but by default every session now operates with the union of all their granted roles. Snowflake cites features such as Notebooks, Snowpark Container Services, UBAC and personal databases as reasons for the change.

### Controls and interactions

- **Session policies** with `ALLOWED_SECONDARY_ROLES` restrict which secondary roles may be activated; `ALLOWED_SECONDARY_ROLES = ()` blocks them entirely.
- **OAuth**: Snowflake OAuth does not support in-session switching to secondary roles; External OAuth supports secondary roles.
- **SCIM**: IdP-provisioned users may need a custom attribute if you want a non-default value for default secondary roles.

### Design trade-offs

- **Pro:** removes the need for "glue" parent roles purely to allow cross-database joins; users see all objects they are entitled to in Snowsight.
- **Con:** weakens role-as-context separation. A user who holds both a PII role and a broad analytics role uses both at once, so "switch to the restricted role for sensitive work" is no longer an effective boundary. Policies that use `CURRENT_ROLE()` evaluate only the primary role; policies that should consider all active roles must use `IS_ROLE_IN_SESSION()`.
- **Ownership surprises:** objects are always owned by the primary role, so a user may read via a secondary role but create into a schema only with the right primary role.

## Example

Activate all granted roles for a cross-database join, then return to a narrow context:

```sql
USE ROLE analyst;
USE SECONDARY ROLES ALL;
SELECT CURRENT_ROLE(), CURRENT_SECONDARY_ROLES();

SELECT o.order_id, c.segment
FROM sales.curated.orders o
JOIN crm.curated.customers c ON c.customer_id = o.customer_id;

USE SECONDARY ROLES NONE;
```

Set an explicit default for a user, and block secondary roles for a sensitive population:

```sql
ALTER USER svc_reporting SET DEFAULT_SECONDARY_ROLES = ();

CREATE SESSION POLICY security.policies.no_secondary
  ALLOWED_SECONDARY_ROLES = ();
ALTER USER pii_admin SET SESSION POLICY security.policies.no_secondary;
```

Write masking logic that respects secondary roles:

```sql
CREATE MASKING POLICY security.policies.mask_email AS (val STRING)
RETURNS STRING ->
  CASE WHEN IS_ROLE_IN_SESSION('PII_READER') THEN val ELSE '***MASKED***' END;
```

## Best practices

- Decide account-wide whether `ALL` is acceptable; enforce the decision with session policies rather than relying on user defaults.
- Use `IS_ROLE_IN_SESSION` in masking and row access policies.
- Set `DEFAULT_SECONDARY_ROLES = ()` explicitly for service users whose behavior must be deterministic.
- Keep sensitive privileges in roles granted only to users who need them, since role switching no longer isolates them.

## Common pitfalls

- Assuming a CREATE succeeds because a secondary role has the CREATE privilege - only the primary role counts.
- Writing policies with `CURRENT_ROLE()` and getting different results depending on which role is primary.
- Expecting secondary roles to work in Snowflake OAuth sessions.
- Overlooking that privileges granted directly to users apply only with `ALL`.

## Learn more

- [USE SECONDARY ROLES](https://docs.snowflake.com/en/sql-reference/sql/use-secondary-roles)
- [Default value of DEFAULT_SECONDARY_ROLES changed to ('ALL')](https://docs.snowflake.com/en/release-notes/bcr-bundles/2024_08/bcr-1692)
- [Overview of Access Control](https://docs.snowflake.com/en/user-guide/security-access-control-overview)

## Knowledge check

### A user's primary role is ANALYST; secondary roles are ALL and include ENGINEER, which has CREATE TABLE on schema S. ANALYST does not. What happens on CREATE TABLE S.T?
- [ ] The table is created and owned by ENGINEER
- [ ] The table is created and owned by ANALYST
- [x] The statement fails, because CREATE is authorized only by the primary role
- [ ] The table is created and owned by PUBLIC
> Object creation is authorized solely by the primary role and its inherited roles; secondary roles do not apply.

### A masking policy uses CURRENT_ROLE() = 'PII_READER'. Users with PII_READER as a secondary role see masked data. What is the fix?
- [ ] Grant PII_READER to PUBLIC
- [x] Use IS_ROLE_IN_SESSION('PII_READER') so all active roles are considered
- [ ] Set DEFAULT_SECONDARY_ROLES to NONE for everyone
- [ ] Use CURRENT_SECONDARY_ROLES() = 'PII_READER'
> CURRENT_ROLE returns only the primary role; IS_ROLE_IN_SESSION checks the primary role, secondary roles and their hierarchies.

### Security requires that a group of privileged users never operate with combined roles. What is the most robust control?
- [ ] Ask users to run USE SECONDARY ROLES NONE
- [ ] Remove their default role
- [x] Apply a session policy with ALLOWED_SECONDARY_ROLES = () to those users
- [ ] Revoke PUBLIC from them
> A session policy enforces the restriction regardless of user settings or client behavior.
