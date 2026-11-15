# System-defined Roles

Every Snowflake account comes with a small set of built-in roles that handle account administration. Understanding what each one is for - and what it should *not* be used for - is the foundation of a safe access-control setup.

## How it works

In Snowflake, privileges are granted to **roles**, and roles are granted to **users** (and to other roles). The system-defined roles are created by Snowflake, cannot be dropped, and the privileges Snowflake gave them cannot be revoked.

| Role | Purpose |
| --- | --- |
| **GLOBALORGADMIN** | Organization-level tasks such as managing accounts and viewing organization usage. Exists only in the organization account. |
| **ORGADMIN** | Older organization-management role used from a regular account; being phased out in favor of GLOBALORGADMIN. |
| **ACCOUNTADMIN** | The top-level role in an account. It includes SYSADMIN and SECURITYADMIN. Grant it to very few people. |
| **SECURITYADMIN** | Manages any grant in the account through the `MANAGE GRANTS` privilege, and inherits USERADMIN. |
| **USERADMIN** | Creates and manages users and roles (`CREATE USER`, `CREATE ROLE`). |
| **SYSADMIN** | Creates warehouses, databases and other objects. |
| **PUBLIC** | A pseudo-role automatically granted to every user and role. Anything granted to PUBLIC is available to everyone. |

The built-in hierarchy looks like this: USERADMIN is inside SECURITYADMIN; SECURITYADMIN and SYSADMIN are both inside ACCOUNTADMIN; PUBLIC sits at the bottom. A role "inside" another means its privileges are inherited by the role above it. ORGADMIN is separate from this hierarchy.

Two important details:

- `MANAGE GRANTS` lets SECURITYADMIN grant and revoke privileges, but not create objects by itself.
- Snowflake recommends granting every **custom role** that owns objects up to SYSADMIN. If you do not, SYSADMIN cannot manage those objects.

## Example

Typical first steps an administrator runs in a new account:

```sql
-- USERADMIN creates people and roles
USE ROLE USERADMIN;
CREATE ROLE analyst;
CREATE USER maria TYPE = PERSON DEFAULT_ROLE = analyst;
GRANT ROLE analyst TO USER maria;

-- SYSADMIN creates objects
USE ROLE SYSADMIN;
CREATE WAREHOUSE analyst_wh WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60;
CREATE DATABASE sales;

-- SECURITYADMIN wires privileges and the hierarchy
USE ROLE SECURITYADMIN;
GRANT USAGE ON WAREHOUSE analyst_wh TO ROLE analyst;
GRANT USAGE ON DATABASE sales TO ROLE analyst;
GRANT ROLE analyst TO ROLE SYSADMIN;
```

Check who holds the most powerful role:

```sql
SHOW GRANTS OF ROLE ACCOUNTADMIN;
```

## Best practices

- Limit ACCOUNTADMIN to a few named administrators who use strong authentication, and do not make it anyone's default role.
- Do daily work in custom roles, not system roles.
- Do not add business privileges (like SELECT on tables) to system roles; grant them to a custom role and grant that role to the system role if needed.
- Grant all custom roles up to SYSADMIN so administrators can manage everything.
- Be careful with PUBLIC; anything granted to it is visible to every user.

## Common pitfalls

- Using ACCOUNTADMIN to create everyday objects, which leaves objects owned by the most privileged role.
- Creating custom roles that are not connected to SYSADMIN, leaving "orphaned" objects.
- Thinking SECURITYADMIN can create any object; it manages grants, but creating objects needs separate privileges.
- Granting data access to PUBLIC for convenience.

## Learn more

- [Overview of Access Control](https://docs.snowflake.com/en/user-guide/security-access-control-overview)

## Knowledge check

### Which system role should create a new user account for a new analyst?
- [ ] SYSADMIN
- [x] USERADMIN
- [ ] PUBLIC
- [ ] ORGADMIN
> USERADMIN is dedicated to user and role management and holds the CREATE USER and CREATE ROLE privileges.

### A data engineer creates a custom role that owns several tables but never grants it to SYSADMIN. What is the consequence?
- [ ] The tables are deleted after 24 hours
- [x] SYSADMIN cannot manage those objects through the role hierarchy
- [ ] The role is automatically granted to PUBLIC
- [ ] Nothing; SYSADMIN owns all objects automatically
> SYSADMIN only inherits privileges of roles granted to it, so an unconnected custom role leaves its objects outside SYSADMIN's control.

### Which statement about ACCOUNTADMIN is correct?
- [ ] It should be the default role for all developers
- [ ] It can be dropped and recreated if needed
- [x] It includes SYSADMIN and SECURITYADMIN and should be granted to only a few users
- [ ] It is the same as PUBLIC
> ACCOUNTADMIN encapsulates SYSADMIN and SECURITYADMIN and is the top-level role, so access to it must be tightly limited.
