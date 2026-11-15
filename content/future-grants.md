# Privileges & Future Grants

Privileges define exactly what a role can do on a securable object - read a table, use a warehouse, create a schema. Future grants extend this to objects that do not exist yet, so new tables and views are accessible to the right roles the moment they are created.

## How it works

**Privileges** are object-specific and fall into a few groups:

- **Global (account) privileges** such as `CREATE DATABASE`, `CREATE ROLE`, `MANAGE GRANTS`, `EXECUTE TASK`.
- **Account object privileges** on warehouses (`USAGE`, `OPERATE`, `MONITOR`, `MODIFY`), databases (`USAGE`, `CREATE SCHEMA`, `MONITOR`) and so on.
- **Schema privileges** such as `USAGE`, `CREATE TABLE`, `CREATE VIEW`.
- **Schema object privileges** such as `SELECT`, `INSERT`, `UPDATE` on tables or `USAGE` on functions.
- **OWNERSHIP**, which gives full control and the right to grant privileges on the object (except in managed access schemas).

To use an object inside a schema, a role needs privileges at every level of the container hierarchy - typically `USAGE` on the database and schema plus the object privilege. `SELECT` on a table without `USAGE` on its schema does nothing.

Three grant scopes exist:

1. **Single object** - `GRANT SELECT ON TABLE sales.public.orders TO ROLE r;`
2. **All existing objects** - `... ON ALL TABLES IN SCHEMA ...`. This is a one-time action that covers objects that exist now.
3. **Future objects** - `... ON FUTURE TABLES IN SCHEMA | DATABASE ...`. Snowflake applies the grant automatically to new objects of that type.

Important future-grant rules:

- If future grants on the same object type exist at both **database and schema level**, the **schema-level grants take precedence and the database-level ones are ignored** for that schema - even if they target different roles.
- Only one future grant of `OWNERSHIP` is allowed per object type in a container.
- Future grants are not applied when a table is renamed or swapped.
- Future grants are not supported for some object types (for example compute pools, external functions and image repositories).
- Future grants do not touch existing objects - pair them with an `ON ALL` grant.

## Example

Give a read-only role access to everything in a schema now and in the future:

```sql
USE ROLE SECURITYADMIN;

GRANT USAGE ON DATABASE sales TO ROLE sales_read;
GRANT USAGE ON SCHEMA sales.curated TO ROLE sales_read;

-- Existing objects
GRANT SELECT ON ALL TABLES IN SCHEMA sales.curated TO ROLE sales_read;
GRANT SELECT ON ALL VIEWS  IN SCHEMA sales.curated TO ROLE sales_read;

-- Objects created later
GRANT SELECT ON FUTURE TABLES IN SCHEMA sales.curated TO ROLE sales_read;
GRANT SELECT ON FUTURE VIEWS  IN SCHEMA sales.curated TO ROLE sales_read;
```

See the result of the precedence rule:

```sql
GRANT SELECT ON FUTURE TABLES IN DATABASE sales TO ROLE auditor;
GRANT INSERT ON FUTURE TABLES IN SCHEMA sales.staging TO ROLE loader;
-- New tables in sales.staging get only the loader grant; auditor gets nothing there.

SHOW FUTURE GRANTS IN SCHEMA sales.staging;
SHOW FUTURE GRANTS IN DATABASE sales;
```

## Best practices

- Always pair `ON FUTURE` with `ON ALL` when onboarding an existing schema.
- Prefer schema-level future grants and define every role you need at that level, so the precedence rule never surprises you.
- Grant privileges to access roles, not users.
- Use `SHOW GRANTS TO ROLE` and `SHOW FUTURE GRANTS` in regular access reviews.
- Avoid `GRANT ALL`; grant the specific privileges each role needs.

## Common pitfalls

- Adding one schema-level future grant and silently disabling all database-level future grants for that schema.
- Granting `SELECT` but forgetting `USAGE` on the database or schema.
- Expecting future grants to apply retroactively.
- Renaming or swapping tables and assuming future grants were reapplied.

## Learn more

- [GRANT <privileges> ... TO ROLE](https://docs.snowflake.com/en/sql-reference/sql/grant-privilege)
- [Overview of Access Control](https://docs.snowflake.com/en/user-guide/security-access-control-overview)

## Knowledge check

### Role R1 has SELECT on future tables in database D1. Later, role R2 is given INSERT on future tables in schema D1.S1. What does R1 get on new tables in D1.S1?
- [ ] SELECT, because database grants always apply
- [x] Nothing, because schema-level future grants take precedence and database-level ones are ignored for that schema
- [ ] SELECT and INSERT
- [ ] An error is raised when the table is created
> When both levels define future grants for the same object type, only the schema-level grants are applied in that schema.

### An analyst has SELECT on a table but still gets "object does not exist or not authorized". What is most likely missing?
- [ ] OWNERSHIP on the table
- [x] USAGE on the containing database and schema
- [ ] MANAGE GRANTS
- [ ] A future grant on the table
> Accessing a schema object requires USAGE on its database and schema in addition to the object privilege.

### You add GRANT SELECT ON FUTURE TABLES to a schema that already has 200 tables. What happens to the existing tables?
- [ ] They receive SELECT immediately
- [x] Nothing; you must also run GRANT SELECT ON ALL TABLES for existing objects
- [ ] They are recreated with the new grant
- [ ] They lose any existing grants
> Future grants only apply to objects created after the grant; existing objects need an ON ALL grant.
