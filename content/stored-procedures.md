# Stored Procedures

A stored procedure is a named, reusable program stored in Snowflake that can run multiple SQL statements with procedural logic such as variables, loops, branching, and error handling. Procedures are how you package administrative operations and multi-step pipeline logic so they can be called with a single `CALL`, scheduled by tasks, and governed with privileges.

## How it works

**Languages.** You can write a procedure handler in SQL (Snowflake Scripting), Python, Java, JavaScript, or Scala. Handlers can be inline (in the `AS $$ ... $$` body) or, for Python, Java, and Scala, loaded from files on a stage.

**Procedures vs. UDFs.** A UDF computes a value inside a query and cannot run DDL or most DML. A procedure is called on its own with `CALL`, can execute DDL and DML, and returns at most a single value (or a table, with `RETURNS TABLE`). Use a procedure when you need side effects; use a UDF when you need a reusable expression in SELECT.

**Rights model.** Every procedure runs with one of these:

- **Owner's rights** (`EXECUTE AS OWNER`, the default): runs with the privileges of the role that owns the procedure. This lets you grant users a controlled operation without granting the underlying privileges.
- **Caller's rights** (`EXECUTE AS CALLER`): runs with the caller's privileges and session context. Useful for utility procedures that should only do what the caller could do anyway.

Owner's-rights procedures have restrictions on reading or changing the caller's session state, which protects the owner's privileges from misuse.

**Snowflake Scripting basics.** A body is a block: `DECLARE` (optional), `BEGIN ... END`, and `EXCEPTION` (optional). Inside SQL statements, reference variables and parameters with a colon prefix, such as `:p_days`. Use `LET` to declare inline, `RESULTSET` for query results, `FOR` loops over cursors, and `RAISE` or custom exceptions for errors.

**Privileges.** Creating requires `CREATE PROCEDURE` on the schema; calling requires `USAGE` on the procedure. Procedures are overloaded by argument signature, so grants and drops must include argument types.

## Example

A Snowflake Scripting procedure that purges old rows, logs the result, and handles errors.

```sql
CREATE OR REPLACE PROCEDURE purge_old_events(p_days NUMBER)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  rows_deleted NUMBER DEFAULT 0;
BEGIN
  DELETE FROM events
  WHERE event_ts < DATEADD(day, -1 * :p_days, CURRENT_TIMESTAMP());
  rows_deleted := SQLROWCOUNT;

  INSERT INTO maintenance_log (proc_name, rows_affected, run_at)
  VALUES ('purge_old_events', :rows_deleted, CURRENT_TIMESTAMP());

  RETURN 'Deleted ' || rows_deleted || ' rows';
EXCEPTION
  WHEN OTHER THEN
    RETURN 'Failed: ' || SQLERRM;
END;
$$;

CALL purge_old_events(90);
GRANT USAGE ON PROCEDURE purge_old_events(NUMBER) TO ROLE ops_role;
```

The same idea in Python using Snowpark, where the first handler argument is the session:

```sql
CREATE OR REPLACE PROCEDURE row_count(table_name STRING)
RETURNS NUMBER
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
AS
$$
def run(session, table_name):
    return session.table(table_name).count()
$$;
```

## Best practices

- Choose owner's rights deliberately for controlled privilege elevation, and keep those procedures narrow.
- Use bind variables (`:var`) or parameter binding; never build SQL by concatenating untrusted input.
- Handle exceptions and write to a log table or event table so task failures are diagnosable.
- Keep procedures idempotent so they can be retried by tasks safely.
- Store procedure source in Git and deploy through CI/CD.

## Common pitfalls

- Omitting the colon before variables inside SQL statements, which causes "invalid identifier" errors.
- Dropping or granting without the argument signature, for example `DROP PROCEDURE purge_old_events` instead of `DROP PROCEDURE purge_old_events(NUMBER)`.
- Expecting an owner's-rights procedure to see the caller's session variables.
- Using a procedure for logic that belongs in a set-based query or a UDF.

## Learn more

- [Stored procedures overview](https://docs.snowflake.com/en/developer-guide/stored-procedure/stored-procedures-overview)
- [Understanding caller's rights and owner's rights stored procedures](https://docs.snowflake.com/en/developer-guide/stored-procedure/stored-procedures-rights)

## Knowledge check

### A support role must be able to purge one table's old rows but must not have DELETE on the table. What design works?
- [ ] A caller's-rights procedure granted to the support role
- [x] An owner's-rights procedure owned by a role with DELETE, with USAGE granted to the support role
- [ ] A UDF that runs DELETE
- [ ] A secure view over the table
> Owner's-rights procedures run with the owner's privileges, so callers can perform the encapsulated operation without holding the underlying privilege.

### Inside a Snowflake Scripting procedure, `DELETE FROM t WHERE id = p_id;` fails with "invalid identifier P_ID". Why?
- [ ] Parameters must be declared in DECLARE
- [x] Variables and parameters used in SQL statements need a colon prefix, as in :p_id
- [ ] DELETE is not allowed in procedures
- [ ] The procedure must use EXECUTE AS CALLER
> Without the colon, Snowflake treats the name as a column identifier.

### When should you use a UDF instead of a stored procedure?
- [ ] When you need to run CREATE TABLE
- [ ] When you need to loop over many DML statements
- [x] When you need a reusable calculation called per row inside a SELECT
- [ ] When you need owner's-rights privilege elevation
> UDFs return values inside queries; procedures are invoked with CALL and are meant for side effects such as DDL and DML.
