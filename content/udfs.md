# User-Defined Functions

A user-defined function (UDF) is a custom function you create in Snowflake and call from SQL just like a built-in function. UDFs let you encapsulate business logic, reuse calculations across queries, and bring Python, Java, Scala, or JavaScript code to your data without moving it out of Snowflake.

## How it works

**Kinds of functions.**

- **Scalar UDF**: returns one value per input row, for example `normalize_phone(phone)`.
- **User-defined table function (UDTF)**: returns a set of rows per input and is called in the FROM clause with `TABLE(...)`, often with a `LATERAL` join.
- **User-defined aggregate function (UDAF)**: aggregates many rows into one value (supported for Python).

**Languages.** Handlers can be written in SQL, JavaScript, Python, Java, or Scala. SQL UDFs are simple expressions or queries and are often the fastest choice because the optimizer can inline them. Python, Java, and Scala UDFs run in a secure sandbox on the warehouse and can use packages (for Python, from the Snowflake Anaconda channel via `PACKAGES`) or code staged as files via `IMPORTS`.

**Vectorized Python UDFs** receive batches of rows as pandas DataFrames instead of one row at a time, which reduces per-row overhead for numeric and ML workloads.

**UDF vs. stored procedure.** A UDF is used inside an expression and returns a value; it is not meant to run DDL or DML. A procedure is invoked with `CALL` and is used for side effects. If your logic changes data, it belongs in a procedure.

**Security and governance.**

- **Secure UDFs** (`CREATE SECURE FUNCTION`) hide the function definition from non-owners and prevent certain optimizations that could expose data, at some performance cost.
- Calling a UDF requires `USAGE` on it. UDFs are overloaded by signature, so grants and drops must include argument types.
- Python, Java, and Scala UDFs have no network access by default; outbound calls require an external access integration.

## Example

A SQL scalar UDF for a reusable calculation:

```sql
CREATE OR REPLACE FUNCTION net_price(price NUMBER(12,2), discount_pct NUMBER(5,2))
RETURNS NUMBER(12,2)
AS
$$
  price * (1 - discount_pct / 100)
$$;

SELECT order_id, net_price(list_price, discount) AS net
FROM order_lines;
```

A Python scalar UDF using a package:

```sql
CREATE OR REPLACE FUNCTION clean_email(email STRING)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
HANDLER = 'clean'
AS
$$
def clean(email):
    if email is None:
        return None
    return email.strip().lower()
$$;
```

A SQL UDTF that returns rows, called with `TABLE()`:

```sql
CREATE OR REPLACE FUNCTION orders_for_customer(cust_id NUMBER)
RETURNS TABLE (order_id NUMBER, order_date DATE, amount NUMBER(12,2))
AS
$$
  SELECT order_id, order_date, amount
  FROM orders
  WHERE customer_id = cust_id
$$;

SELECT * FROM TABLE(orders_for_customer(42));
```

## Best practices

- Prefer SQL UDFs for simple expressions; use Python, Java, or Scala when you need libraries or complex logic.
- Use vectorized Python UDFs for heavy per-row numeric work.
- Keep UDFs deterministic and side-effect free so results are predictable and cacheable.
- Use secure UDFs only when you need to protect logic or data; they limit optimizations.
- Version UDF source in Git and deploy with CI/CD, including grants with full signatures.

## Common pitfalls

- Writing per-row Python for logic that a built-in SQL function already handles, which is slower.
- Forgetting the argument signature when granting or dropping an overloaded function.
- Expecting a UDF to make HTTP calls without an external access integration.
- Using a UDF to modify data; that requires a stored procedure.

## Learn more

- [User-defined functions overview](https://docs.snowflake.com/en/developer-guide/udf/udf-overview)

## Knowledge check

### You need a function that, for each input row containing a JSON array, returns one output row per array element with custom parsing in Python. What should you create?
- [ ] A scalar Python UDF
- [x] A Python UDTF called with TABLE() in the FROM clause
- [ ] A stored procedure
- [ ] A secure SQL UDF
> A UDTF returns zero or more rows per input row, which fits one-to-many expansion.

### A Python UDF scoring millions of rows with numpy is slow. What change is most likely to help?
- [ ] Convert it to a stored procedure
- [x] Rewrite it as a vectorized UDF that processes pandas batches
- [ ] Mark it SECURE
- [ ] Add an external access integration
> Vectorized UDFs process batches of rows at once, reducing per-row invocation overhead.

### Why might a team choose `CREATE SECURE FUNCTION`?
- [ ] To make the function run faster
- [ ] To allow the function to run DML
- [x] To hide the function definition from non-owners and prevent optimizations that could expose underlying data
- [ ] To allow outbound network calls
> Secure UDFs protect logic and data from exposure, with a potential performance trade-off.
