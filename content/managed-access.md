# Managed Access Schemas

A managed access schema centralizes grant decisions: object owners inside the schema lose the ability to grant privileges on their objects, and only the schema owner or a role with `MANAGE GRANTS` can do so. It is Snowflake's main lever for moving from discretionary, owner-driven access control to a governed model where a security team approves every grant.

## How it works

In a regular schema, the role that owns an object (usually the role that created it) can grant privileges on it to anyone. That is discretionary access control (DAC), and it scales poorly: any engineer who can create a table can share it.

In a managed access schema:

- Objects still have owners, and owners can still alter or drop them.
- **Grant authority moves** to the schema owner (the role with `OWNERSHIP` on the schema) and to roles with the global `MANAGE GRANTS` privilege (SECURITYADMIN by default).
- This applies to future grants defined in the schema as well, centralizing privilege management.

Create one with `CREATE SCHEMA ... WITH MANAGED ACCESS`, or convert an existing schema with `ALTER SCHEMA ... ENABLE MANAGED ACCESS` (and back with `DISABLE MANAGED ACCESS`).

### Interaction with future grants and ownership

- Database-level future grants apply to both regular and managed access schemas.
- A future grant of `OWNERSHIP` defined at database level does not apply to new objects in a managed access schema.
- Inside a managed access schema, a future grant of `OWNERSHIP` can only target a role subordinate to the schema owner.
- Before transferring ownership of a managed access schema to another role, you must revoke all open future grants of `OWNERSHIP` in it.

### Design trade-offs

- **Governance vs. velocity.** Managed access removes self-service sharing. Pair it with well-defined future grants to access roles so routine access needs no ticket, and reserve manual grants for exceptions.
- **Who owns the schema matters.** The schema owner becomes a grant authority. Make it a dedicated, non-human "schema admin" role (often an access-management role) rather than an engineering team role, or you have only moved discretion up one level.
- **Ownership of objects.** A common pattern is to have a deployment role create objects (so CI/CD owns them) while the managed schema prevents that deployment role from granting access outside the approved model.
- **Third-party tooling.** Tools that grant privileges on objects they create (for example some ELT or clean-room tooling) need either the schema owner role or `MANAGE GRANTS`, or a special registration path; check before converting.

## Example

Create a governed schema owned by an access-admin role, with future grants doing the routine work:

```sql
USE ROLE SYSADMIN;
CREATE SCHEMA finance.curated WITH MANAGED ACCESS;
GRANT OWNERSHIP ON SCHEMA finance.curated TO ROLE finance_access_admin COPY CURRENT GRANTS;

USE ROLE finance_access_admin;
GRANT USAGE ON SCHEMA finance.curated TO ROLE finance_read;
GRANT SELECT ON FUTURE TABLES IN SCHEMA finance.curated TO ROLE finance_read;
GRANT SELECT ON FUTURE VIEWS  IN SCHEMA finance.curated TO ROLE finance_read;
```

A developer whose role owns a table in the schema can no longer share it:

```sql
USE ROLE finance_dev;
GRANT SELECT ON TABLE finance.curated.gl_entries TO ROLE marketing;
-- fails: object owners cannot grant privileges in a managed access schema
```

Convert an existing schema and verify:

```sql
ALTER SCHEMA finance.raw ENABLE MANAGED ACCESS;
SHOW SCHEMAS LIKE 'RAW' IN DATABASE finance;  -- check the options column
```

## Best practices

- Use managed access for any schema holding sensitive or regulated data.
- Assign schema ownership to a dedicated access-administration role.
- Encode standard access as future grants so the governance model is not a bottleneck.
- Audit grants periodically with `SHOW GRANTS ON SCHEMA` and `SHOW FUTURE GRANTS IN SCHEMA`.

## Common pitfalls

- Expecting managed access to stop owners from dropping or altering objects - it only changes who can grant.
- Forgetting to revoke future OWNERSHIP grants before transferring schema ownership.
- Making a broad engineering role the schema owner, which re-creates discretionary sharing.
- Converting schemas used by tools that rely on owner grants without testing them first.

## Learn more

- [Overview of Access Control](https://docs.snowflake.com/en/user-guide/security-access-control-overview)
- [GRANT <privileges> ... TO ROLE](https://docs.snowflake.com/en/sql-reference/sql/grant-privilege)

## Knowledge check

### In a managed access schema, role DEV owns table T. Which role can grant SELECT on T to role BI?
- [ ] DEV, because it owns the table
- [x] The schema owner or a role with MANAGE GRANTS
- [ ] Any role with USAGE on the schema
- [ ] Only ACCOUNTADMIN
> Managed access removes grant authority from object owners and centralizes it in the schema owner and MANAGE GRANTS holders.

### A team wants managed access but also wants analysts to see new tables without filing tickets. What design fits?
- [ ] Keep a regular schema and trust table owners
- [x] Use a managed access schema with schema-level future grants to an analyst access role
- [ ] Grant MANAGE GRANTS to all analysts
- [ ] Transfer ownership of every table to the analyst role
> Future grants defined by the schema owner automate routine access while keeping grant authority centralized.

### You try to transfer ownership of a managed access schema and the command fails. What should you check first?
- [ ] Whether the schema contains views
- [x] Whether open future grants of OWNERSHIP exist in the schema; they must be revoked first
- [ ] Whether MANAGE GRANTS is granted to PUBLIC
- [ ] Whether the schema is transient
> Snowflake requires revoking open future OWNERSHIP grants before ownership of a managed access schema can be transferred.
