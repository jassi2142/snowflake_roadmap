# Enterprise RBAC Framework

An enterprise RBAC framework is a deliberate, automated design for Snowflake roles: a layer of access roles that hold privileges on objects, a layer of functional roles that map to job functions and identity provider groups, and tight controls on the system administrator roles. Without one, grants accumulate ad hoc, audits become guesswork, and least privilege is impossible to demonstrate.

## How it works

Snowflake grants privileges to roles, and roles to users or other roles. Privileges flow up the hierarchy. There is no technical difference between kinds of custom roles. The framework is a convention about how you use them:

- **Access roles** hold privileges on a narrow scope, for example read or read-write on one schema. Users never get them directly.
- **Functional roles** represent business functions (analyst, data engineer, finance) and are composed of access roles. They are what users activate.
- **Database roles** are scoped to a single database, so the database owner can manage them independently, and they can be granted to shares. They are an excellent implementation for access roles: one set per database or schema, granted to account-level functional roles. Granting a database role to an account role implicitly grants USAGE on the database. Database roles cannot be activated directly in a session.
- **System roles**: SYSADMIN owns the object hierarchy, so grant top-level custom roles to SYSADMIN or ACCOUNTADMIN cannot manage objects they create. SECURITYADMIN holds the global MANAGE GRANTS privilege, USERADMIN creates users and roles, and ACCOUNTADMIN sits at the top.

Supporting mechanisms:

- **Managed access schemas** take grant decisions away from object owners. Only the schema owner or a role with MANAGE GRANTS can grant, which centralizes control.
- **Future grants** (`GRANT ... ON FUTURE TABLES IN SCHEMA`) keep access roles current as objects are created. Note that a database role granted to a share does not support future grants.
- **SCIM provisioning** from an identity provider (for example Okta or Microsoft Entra ID) creates users and maps IdP groups to Snowflake roles, so joiners, movers, and leavers are handled by HR-driven group membership instead of tickets.

**ACCOUNTADMIN controls** recommended by Snowflake: assign it to a limited number of people but at least two (to allow mutual recovery), require MFA, never make it a user's default role, and do not use it to create objects or run automation.

## Example

Access roles as database roles, functional roles as account roles:

```sql
USE ROLE SYSADMIN;
CREATE DATABASE ROLE sales_db.sales_curated_r;
CREATE DATABASE ROLE sales_db.sales_curated_rw;

USE ROLE SECURITYADMIN;
GRANT USAGE ON SCHEMA sales_db.curated TO DATABASE ROLE sales_db.sales_curated_r;
GRANT SELECT ON ALL TABLES IN SCHEMA sales_db.curated TO DATABASE ROLE sales_db.sales_curated_r;
GRANT SELECT ON FUTURE TABLES IN SCHEMA sales_db.curated TO DATABASE ROLE sales_db.sales_curated_r;

GRANT DATABASE ROLE sales_db.sales_curated_r TO DATABASE ROLE sales_db.sales_curated_rw;
GRANT INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA sales_db.curated
  TO DATABASE ROLE sales_db.sales_curated_rw;

USE ROLE USERADMIN;
CREATE ROLE fr_sales_analyst;   -- mapped to IdP group via SCIM

USE ROLE SECURITYADMIN;
GRANT DATABASE ROLE sales_db.sales_curated_r TO ROLE fr_sales_analyst;
GRANT USAGE ON WAREHOUSE wh_sales_xs TO ROLE fr_sales_analyst;
GRANT ROLE fr_sales_analyst TO ROLE SYSADMIN;
```

The read-write role inherits read, the functional role receives only read, and the hierarchy rolls up to SYSADMIN.

Audit direct user grants, which should be rare in an RBAC framework:

```sql
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES WHERE granted_to = 'USER';
```

## Best practices

- Adopt a strict naming convention that encodes scope and level, for example `<db>_<schema>_r`, `_rw`, and `_owner` for access roles, `fr_<function>` for functional roles, and `wh_<team>_<size>` for warehouses.
- Generate every grant from code (Terraform, DCM projects, or scripted templates) driven by a role catalog, and treat manual grants as drift to detect and revert.
- Use managed access schemas for curated and consumption layers so table owners cannot grant access sideways.
- Keep separate owner roles (often service roles for pipelines) from consumer roles, and give service users key-pair or OAuth authentication with their own functional roles.
- Let SCIM own group-to-role membership, and keep break-glass ACCOUNTADMIN accounts outside SCIM with MFA and monitoring.
- Review `GRANTS_TO_ROLES`, `GRANTS_TO_USERS`, and login history regularly, and alert on grants of ACCOUNTADMIN or SECURITYADMIN.

## Common pitfalls

- Granting object privileges directly to functional roles, which multiplies grants and makes access hard to reason about.
- Creating custom role trees that are not attached to SYSADMIN, so administrators cannot manage the resulting objects.
- Forgetting that cloned databases and schemas keep grants on their child objects, which can unintentionally copy production access into a development clone.
- Relying on future grants alone and missing the `GRANT ... ON ALL` needed for objects that already exist.
- Making ACCOUNTADMIN a default role, or using it in CI pipelines.

## Learn more

- [Access control best practices](https://docs.snowflake.com/en/user-guide/security-access-control-considerations)
- [GRANT DATABASE ROLE ... TO SHARE](https://docs.snowflake.com/en/sql-reference/sql/grant-database-role-share)
- [SCIM overview](https://docs.snowflake.com/en/user-guide/scim-intro)

## Knowledge check

### A data domain team wants to manage read access to its own database without involving the central security team for every table. Which construct fits best?
- [ ] Grant OWNERSHIP of all tables to the users
- [x] Database roles inside the domain database, owned by the domain team, granted to account-level functional roles
- [ ] Direct user grants (UBAC) on every table
- [ ] A single shared read role for the entire account
> Database roles let database owners manage access to their own objects independently, while composing cleanly into the account-level role hierarchy.

### After a reorganization, analysts still have access to data from their previous team. What is the most scalable control to prevent this?
- [ ] Quarterly manual reviews of SHOW GRANTS output
- [ ] Granting roles directly to users with expiry comments
- [x] Mapping IdP groups to functional roles through SCIM, so changes in group membership automatically add and remove roles
- [ ] Using a single PUBLIC-based role for everyone
> SCIM makes the identity provider the source of truth, so movers and leavers are handled through group membership changes rather than manual revocations.

### Why should table owners in the curated layer generally not be able to grant SELECT on their tables to arbitrary roles?
- [ ] Owners do not have that ability in any schema
- [x] It bypasses the central access model; managed access schemas restrict grants to the schema owner or a role with MANAGE GRANTS
- [ ] It forces tables to become transient
- [ ] Future grants stop working
> In regular schemas, object owners can grant access freely. Managed access schemas centralize grant decisions, which is necessary for enforceable least privilege.
