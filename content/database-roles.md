# Database Roles

A database role is a role that lives inside a single database and can only hold privileges on that database and its objects. Database roles let you package access with the data it protects, which makes databases self-contained for cloning, replication, and data sharing.

## How it works

- Create them with `CREATE DATABASE ROLE <db>.<name>`. The database owner, or a role with `CREATE DATABASE ROLE` on the database, can create them.
- They can receive privileges on the database, its schemas and its schema objects - including future grants - but not on account-level objects such as warehouses.
- **A database role cannot be activated in a session**, as neither a primary nor a secondary role. To use it, grant it to an account role (or to another database role in the same database), and activate the account role.
- **Account roles cannot be granted to database roles.** The flow is always database role into account role.
- Database roles are the recommended way to add objects to a **share**: grant privileges to a database role, then `GRANT DATABASE ROLE ... TO SHARE`. The consumer can then grant each shared database role to different account roles, giving fine-grained access inside one share.

Limitations relevant to sharing:

- If a database role is granted to a share, no other database roles can be granted to it.
- If a database role is granted to another database role, the grantee cannot be granted to a share.
- A database role with future grants cannot be shared, and you cannot add future grants to a database role already granted to a share.
- `IMPORTED PRIVILEGES` cannot be granted to a database role.

Snowflake also ships database roles in the shared `SNOWFLAKE` database (for example `SNOWFLAKE.OBJECT_VIEWER` or `SNOWFLAKE.USAGE_VIEWER`) for granting narrow access to account usage data.

## Example

Package read access inside the database, then expose it to an account role:

```sql
USE ROLE SYSADMIN;

CREATE DATABASE ROLE sales.reader;
GRANT USAGE ON SCHEMA sales.curated TO DATABASE ROLE sales.reader;
GRANT SELECT ON ALL TABLES IN SCHEMA sales.curated TO DATABASE ROLE sales.reader;

GRANT DATABASE ROLE sales.reader TO ROLE analyst;
```

Share two tiers of access from one share:

```sql
CREATE DATABASE ROLE sales.partner_basic;
CREATE DATABASE ROLE sales.partner_premium;

GRANT USAGE ON SCHEMA sales.curated TO DATABASE ROLE sales.partner_basic;
GRANT SELECT ON VIEW sales.curated.daily_summary TO DATABASE ROLE sales.partner_basic;

GRANT USAGE ON SCHEMA sales.curated TO DATABASE ROLE sales.partner_premium;
GRANT SELECT ON VIEW sales.curated.order_detail TO DATABASE ROLE sales.partner_premium;

CREATE SHARE sales_share;
GRANT USAGE ON DATABASE sales TO SHARE sales_share;
GRANT DATABASE ROLE sales.partner_basic   TO SHARE sales_share;
GRANT DATABASE ROLE sales.partner_premium TO SHARE sales_share;
```

On the consumer side, after creating a database from the share:

```sql
GRANT DATABASE ROLE partner_sales.partner_basic TO ROLE reporting;
```

Grant account-usage access without ACCOUNTADMIN:

```sql
GRANT DATABASE ROLE SNOWFLAKE.USAGE_VIEWER TO ROLE finops;
```

## Best practices

- Use database roles as the **access role** layer and account roles as the **functional role** layer.
- Keep database roles flat when you plan to share them, because nested or future-granted database roles cannot be shared.
- Use database roles so access definitions are replicated and cloned along with the database.
- Name them by access level (`reader`, `writer`, `admin`) for consistency across databases.

## Common pitfalls

- Trying `USE ROLE` with a database role - it cannot be activated directly.
- Attempting to grant warehouse usage to a database role; warehouses are account objects.
- Adding future grants to a database role that you intend to share.
- Expecting an account role to be grantable into a database role.

## Learn more

- [Overview of Access Control](https://docs.snowflake.com/en/user-guide/security-access-control-overview)
- [GRANT DATABASE ROLE ... TO SHARE](https://docs.snowflake.com/en/sql-reference/sql/grant-database-role-share)

## Knowledge check

### A developer runs USE ROLE sales.reader and gets an error. Why?
- [ ] The database role lacks OWNERSHIP
- [x] Database roles cannot be activated in a session; they must be granted to an account role
- [ ] Database roles must be activated as secondary roles
- [ ] The role name must be quoted
> Only account roles can be primary or secondary roles; database role privileges are used through an account role they are granted to.

### A provider wants partners in one share to see different views depending on their tier. What is the best approach?
- [ ] Create a separate database per tier
- [x] Grant each tier's privileges to a different database role and grant those database roles to the share
- [ ] Grant account roles to the share
- [ ] Use future grants on the shared database
> Multiple database roles in a share let the consumer map each tier to different account roles.

### Which grant is not allowed?
- [ ] GRANT DATABASE ROLE db.r1 TO ROLE analyst
- [ ] GRANT SELECT ON ALL TABLES IN SCHEMA db.s TO DATABASE ROLE db.r1
- [x] GRANT ROLE analyst TO DATABASE ROLE db.r1
- [ ] GRANT DATABASE ROLE db.r1 TO SHARE s1
> Account roles cannot be granted to database roles; the hierarchy flows from database roles up into account roles.
