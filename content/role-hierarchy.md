# Role Hierarchy Design

A role hierarchy is the structure you build by granting roles to other roles so that privileges flow upward. A good design keeps grants manageable as teams and databases grow, makes audits readable, and lets administrators manage every object without handing out excessive power.

## How it works

When role A is granted to role B, B inherits all of A's privileges (and everything A inherits). Users get the combined privileges of the roles they activate. A few rules shape the design:

- **Ownership is not inheritance.** The role that owns another role does not inherit its privileges; only granting the role creates inheritance.
- **Every object has one owner role**, by default the primary role that created it.
- **SYSADMIN should sit on top of all custom roles.** Otherwise SYSADMIN cannot manage those objects, and only roles with `MANAGE GRANTS` (SECURITYADMIN by default) can even see and re-grant them.
- **Database roles** can be part of the hierarchy (granted to account roles), but account roles cannot be granted to database roles.
- `WITH GRANT OPTION` on `GRANT ROLE` lets a recipient role grant that role onward; without it, the recipient only inherits.

### The functional / access role pattern

The most widely used design separates two layers:

- **Access roles** hold privileges on objects, for example `SALES_READ` (USAGE on database and schemas, SELECT on tables) and `SALES_WRITE`. These are often database roles so they live and replicate with the database.
- **Functional roles** represent jobs, for example `ANALYST` or `DATA_ENGINEER`. They hold no object privileges directly; they are granted the access roles they need, and they are granted to users.

All functional roles are then granted to SYSADMIN. Benefits: a new hire needs one grant; a new dataset needs one access role granted to the right functional roles; and `SHOW GRANTS` reads clearly.

Keep separate roles per environment (dev, test, prod) so a developer role can never reach production data by accident.

## Example

Build a two-layer hierarchy for a sales database:

```sql
USE ROLE SECURITYADMIN;

-- Access roles
CREATE ROLE sales_read;
CREATE ROLE sales_write;
GRANT USAGE ON DATABASE sales TO ROLE sales_read;
GRANT USAGE ON ALL SCHEMAS IN DATABASE sales TO ROLE sales_read;
GRANT SELECT ON ALL TABLES IN DATABASE sales TO ROLE sales_read;
GRANT ROLE sales_read TO ROLE sales_write;
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN DATABASE sales TO ROLE sales_write;

-- Functional roles
CREATE ROLE analyst;
CREATE ROLE data_engineer;
GRANT ROLE sales_read  TO ROLE analyst;
GRANT ROLE sales_write TO ROLE data_engineer;
GRANT USAGE ON WAREHOUSE analyst_wh TO ROLE analyst;

-- Connect to SYSADMIN and to users
GRANT ROLE analyst TO ROLE SYSADMIN;
GRANT ROLE data_engineer TO ROLE SYSADMIN;
GRANT ROLE analyst TO USER maria;
```

Inspect the result:

```sql
SHOW GRANTS TO ROLE analyst;
SHOW GRANTS OF ROLE sales_read;
```

## Best practices

- Use functional roles for people and access roles for privileges; avoid granting object privileges straight to functional roles.
- Grant every top-level custom role to SYSADMIN.
- Use future grants or managed access schemas so access roles stay correct as new objects appear.
- Name roles consistently, for example `<domain>_<env>_<level>`.
- Manage the hierarchy as code (Terraform, schemachange, DCM) rather than ad hoc.

## Common pitfalls

- Granting privileges directly to users or to dozens of individual roles, producing a hierarchy nobody can audit.
- Leaving a custom role disconnected from SYSADMIN, so its objects fall outside normal administration.
- Mixing environments in one role so a dev role reaches prod.
- Assuming the role that owns a role inherits its privileges.

## Learn more

- [Overview of Access Control](https://docs.snowflake.com/en/user-guide/security-access-control-overview)
- [GRANT ROLE](https://docs.snowflake.com/en/sql-reference/sql/grant-role)

## Knowledge check

### Role SALES_READ is granted to ANALYST, and ANALYST is granted to SYSADMIN. Which roles can SELECT the sales tables?
- [ ] Only SALES_READ
- [ ] SALES_READ and ANALYST only
- [x] SALES_READ, ANALYST, SYSADMIN, and roles above SYSADMIN such as ACCOUNTADMIN
- [ ] Only users granted SALES_READ directly
> Privileges flow upward through every role that has the granting role beneath it in the hierarchy.

### Why does the functional/access role pattern simplify onboarding?
- [ ] It removes the need for SYSADMIN
- [x] A new user needs only the functional role; object privileges are already bundled in access roles
- [ ] It grants every user ACCOUNTADMIN temporarily
- [ ] It replaces roles with direct user grants
> Functional roles aggregate access roles, so onboarding is a single role grant rather than many object grants.

### A role owns the role DEV_TEAM but was never granted DEV_TEAM. Does it inherit DEV_TEAM's privileges?
- [x] No; ownership of a role does not confer its privileges
- [ ] Yes; owners inherit everything they own
- [ ] Only SELECT privileges are inherited
- [ ] Only if DEV_TEAM is granted to PUBLIC
> Privilege inheritance only happens through role grants in the hierarchy, not through ownership of the role.
