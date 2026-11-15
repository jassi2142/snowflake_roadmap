# Object Hierarchy

Everything in Snowflake is organized in a hierarchy of containers: an organization holds accounts, an account holds databases, databases hold schemas, and schemas hold tables, views, and other objects. Knowing this structure helps you name objects correctly, grant access at the right level, and organize your projects.

## How it works

From the top down:

1. **Organization.** Groups all the accounts owned by one company. It is used for managing accounts and billing across regions and clouds.
2. **Account.** A single Snowflake deployment in one cloud region. Some objects exist at the account level rather than inside a database:
   - Users and roles
   - Virtual warehouses
   - Databases
   - Resource monitors, network policies, and integrations
3. **Database.** A logical container for schemas.
4. **Schema.** A logical grouping of objects inside a database. Every database automatically gets a `PUBLIC` schema and an `INFORMATION_SCHEMA` (read-only metadata views).
5. **Schema-level objects** include:
   - Tables and views (including materialized and secure views)
   - Stages and file formats
   - Sequences
   - Functions (UDFs) and stored procedures
   - Streams, tasks, and pipes
   - Dynamic tables

**Fully qualified names.** A schema object's full name is `database.schema.object`, for example `learn_db.sales.orders`. If you leave out parts, Snowflake fills them in from the session's current database and schema.

**Access control follows the hierarchy.** To query a table, a role needs `USAGE` on the database, `USAGE` on the schema, and `SELECT` on the table. Granting only one of these is not enough.

Warehouses are account-level objects and do not belong to any database. Any role with `USAGE` on a warehouse can use it to query any database it has access to.

## Example

Build a small hierarchy and grant read access to an analyst role:

```sql
USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS learn_db;
CREATE SCHEMA IF NOT EXISTS learn_db.sales;

CREATE OR REPLACE TABLE learn_db.sales.orders (
  order_id INTEGER,
  amount   NUMBER(10,2)
);

USE ROLE SECURITYADMIN;
CREATE ROLE IF NOT EXISTS analyst;
GRANT USAGE  ON DATABASE learn_db                TO ROLE analyst;
GRANT USAGE  ON SCHEMA   learn_db.sales          TO ROLE analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA learn_db.sales TO ROLE analyst;
GRANT USAGE  ON WAREHOUSE learn_wh               TO ROLE analyst;
```

List the objects at each level:

```sql
SHOW DATABASES;
SHOW SCHEMAS IN DATABASE learn_db;
SHOW TABLES IN SCHEMA learn_db.sales;
```

## Best practices

- Use databases to separate environments or domains (for example `RAW`, `ANALYTICS`, `DEV`) and schemas to group related objects.
- Use fully qualified names in production code and scheduled jobs.
- Grant privileges to roles, not users, and grant at the level that fits (database, schema, or object).
- Use future grants, or schema-level grants, so new tables do not need manual grants.

## Common pitfalls

- Granting `SELECT` on a table but forgetting `USAGE` on its database and schema.
- Putting everything in the `PUBLIC` schema, which makes access control and organization harder later.
- Assuming a warehouse belongs to a database. It is an account-level object.

## Learn more

- [Databases, tables & views](https://docs.snowflake.com/en/guides-overview-db)

## Knowledge check

### A role has SELECT on `learn_db.sales.orders`, but queries fail with "does not exist or not authorized". What is most likely missing?
- [ ] A clustering key on the table
- [x] USAGE on the database and schema
- [ ] OWNERSHIP of the table
- [ ] A larger warehouse
> Access to schema objects requires USAGE on each parent container as well as the object privilege.

### Which object is account-level rather than schema-level?
- [ ] Table
- [ ] Stage
- [x] Virtual warehouse
- [ ] Stored procedure
> Warehouses, users, roles, and databases are account-level. Tables, stages, and procedures live in schemas.

### Your session's current schema is `learn_db.public`. What does `SELECT * FROM sales.orders` refer to?
- [ ] `public.sales.orders`
- [x] `learn_db.sales.orders`
- [ ] It always fails without a database name
- [ ] The first table named orders in any database
> A two-part name is read as schema.object, and the database comes from the session context.
