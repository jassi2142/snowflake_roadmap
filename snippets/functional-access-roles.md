# Access roles + functional roles with future grants in a managed access schema

topics: role-hierarchy, future-grants, managed-access
tags: security, rbac, access-control
level: intermediate

Set up the standard two-layer RBAC pattern. Access roles hold privileges on one schema (read or write). Functional roles match job functions and inherit access roles. Users only get functional roles. Future grants cover tables created later, and a managed access schema stops object owners from granting access around the model.

```sql
-- 1. Managed access schema: only the schema owner (or MANAGE GRANTS) can grant on objects in it
USE ROLE SYSADMIN;
CREATE DATABASE IF NOT EXISTS my_db;
CREATE SCHEMA IF NOT EXISTS my_db.sales WITH MANAGED ACCESS;

-- 2. Roles (USERADMIN creates roles)
USE ROLE USERADMIN;
CREATE ROLE IF NOT EXISTS ar_sales_ro COMMENT = 'Access role: read my_db.sales';
CREATE ROLE IF NOT EXISTS ar_sales_rw COMMENT = 'Access role: write my_db.sales';
CREATE ROLE IF NOT EXISTS fr_analyst  COMMENT = 'Functional role: analysts';
CREATE ROLE IF NOT EXISTS fr_engineer COMMENT = 'Functional role: data engineers';

-- 3. Privileges go to access roles only
USE ROLE SECURITYADMIN;   -- has MANAGE GRANTS, so it can grant in managed access schemas
GRANT USAGE ON DATABASE my_db                       TO ROLE ar_sales_ro;
GRANT USAGE ON SCHEMA   my_db.sales                 TO ROLE ar_sales_ro;
GRANT SELECT ON ALL TABLES    IN SCHEMA my_db.sales TO ROLE ar_sales_ro;
GRANT SELECT ON ALL VIEWS     IN SCHEMA my_db.sales TO ROLE ar_sales_ro;
GRANT SELECT ON FUTURE TABLES IN SCHEMA my_db.sales TO ROLE ar_sales_ro;
GRANT SELECT ON FUTURE VIEWS  IN SCHEMA my_db.sales TO ROLE ar_sales_ro;

GRANT ROLE ar_sales_ro TO ROLE ar_sales_rw;         -- write includes read
GRANT CREATE TABLE, CREATE VIEW ON SCHEMA my_db.sales TO ROLE ar_sales_rw;
GRANT INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES    IN SCHEMA my_db.sales TO ROLE ar_sales_rw;
GRANT INSERT, UPDATE, DELETE, TRUNCATE ON FUTURE TABLES IN SCHEMA my_db.sales TO ROLE ar_sales_rw;

-- 4. Functional roles inherit access roles, plus compute
GRANT ROLE ar_sales_ro TO ROLE fr_analyst;
GRANT ROLE ar_sales_rw TO ROLE fr_engineer;
GRANT USAGE ON WAREHOUSE analyst_wh TO ROLE fr_analyst;
GRANT USAGE ON WAREHOUSE etl_wh     TO ROLE fr_engineer;

-- 5. Attach the functional roles to SYSADMIN so admins can manage the objects they create
GRANT ROLE fr_analyst  TO ROLE SYSADMIN;
GRANT ROLE fr_engineer TO ROLE SYSADMIN;

-- 6. Users get functional roles only
GRANT ROLE fr_analyst TO USER jdoe;
ALTER USER jdoe SET DEFAULT_ROLE = fr_analyst;

-- 7. Verify
SHOW FUTURE GRANTS IN SCHEMA my_db.sales;
SHOW GRANTS TO ROLE ar_sales_ro;
SHOW GRANTS OF ROLE fr_analyst;
```

## Notes
- Works in all editions. Run role DDL as USERADMIN and grants as SECURITYADMIN, and don't use ACCOUNTADMIN for day-to-day setup.
- Future grants only apply to objects created after the grant. Keep the `ON ALL ...` grants for existing objects.
- If future grants exist at both database and schema level, the schema-level ones take precedence for that schema and the database-level ones are ignored. Pick one level per object type.
- Future grants are not applied when you rename or swap a table into the schema.
- Database roles are a good alternative for access roles when the database is shared or cloned between environments, because they move with the database.

## References
- [Overview of access control](https://docs.snowflake.com/en/user-guide/security-access-control-overview)
- [Access control considerations](https://docs.snowflake.com/en/user-guide/security-access-control-considerations)
- [GRANT <privileges> (future grants)](https://docs.snowflake.com/en/sql-reference/sql/grant-privilege)
- [CREATE SCHEMA (WITH MANAGED ACCESS)](https://docs.snowflake.com/en/sql-reference/sql/create-schema)
