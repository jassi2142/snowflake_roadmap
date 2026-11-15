# Drivers & Connectors

Drivers and connectors let applications, scripts, and third-party tools talk to Snowflake. Your own code, a BI dashboard, or an ETL tool almost always reaches Snowflake through one of them. Choosing the right one, and configuring it correctly, affects security, performance, and reliability.

## How it works

Snowflake provides native support for **JDBC** and **ODBC**, plus programmatic interfaces for **Python, Spark, Node.js, .NET, PHP, and Go**. These are available in all editions. The common pieces are:

- **Drivers** implement a standard database API so tools can run SQL:
  - **JDBC** for Java applications and many BI and ETL tools
  - **ODBC** for tools that use the ODBC standard, such as many desktop analytics tools
  - **Language drivers/connectors** such as the Snowflake Connector for Python, the Node.js driver, the .NET driver, the Go driver, and the PHP PDO driver
- **Connectors** link Snowflake to specific platforms. Examples include the Snowflake Connector for Spark and the Snowflake Connector for Kafka, which loads data from Kafka topics.
- **Snowflake SQL API** is a REST API for running SQL without installing a driver.
- **Ecosystem tools.** Many partner ETL, BI, and data science tools connect through these drivers.

Every connection needs the same basic information:

- An **account identifier** (preferably in the `orgname-accountname` form)
- A **user** and an **authentication method**, such as key-pair, OAuth, SSO through a browser, or programmatic access tokens
- An optional default **role, warehouse, database, and schema**

**SnowCD** (Snowflake Connectivity Diagnostic Tool) helps you find and fix network connectivity problems between clients and Snowflake.

## Example

A Python script using the Snowflake Connector for Python with key-pair authentication. Install it with `pip install snowflake-connector-python`.

```python
import snowflake.connector

conn = snowflake.connector.connect(
    account="myorg-myaccount",
    user="ETL_SERVICE",
    private_key_file="/secrets/rsa_key.p8",
    role="TRANSFORMER",
    warehouse="ETL_WH",
    database="LEARN_DB",
    schema="PUBLIC",
)

try:
    cur = conn.cursor()
    cur.execute(
        "SELECT customer, SUM(amount) FROM orders WHERE order_date >= %s GROUP BY customer",
        ("2026-10-01",),
    )
    for customer, total in cur.fetchall():
        print(customer, total)
finally:
    conn.close()
```

The query uses a bind parameter (`%s`) instead of string formatting, which prevents SQL injection.

## Best practices

- Use the official Snowflake driver for your language, and keep it up to date for security fixes and new features.
- Use key-pair or OAuth for service accounts instead of passwords, and store keys in a secrets manager.
- Always use bind variables for user-supplied values.
- Set a dedicated role and warehouse for each application so you can control access and track costs.
- Close connections, or use connection pooling, to avoid leaking sessions.

## Common pitfalls

- Building SQL by concatenating strings, which opens the door to SQL injection.
- Using outdated drivers that fall below supported versions or lack newer authentication methods.
- Leaving the warehouse or role unset, so the session falls back to user defaults that are wrong for the job.
- Diagnosing firewall or proxy problems by trial and error instead of using SnowCD.

## Learn more

- [Drivers](https://docs.snowflake.com/en/developer-guide/drivers)

## Knowledge check

### A Java-based BI tool needs to query Snowflake. Which interface does it most likely use?
- [ ] The Kafka connector
- [x] The JDBC driver
- [ ] SnowCD
- [ ] The PHP PDO driver
> Java applications and many BI tools connect through the JDBC driver.

### A script builds `"WHERE name = '" + user_input + "'"` before running a query. What is the problem and the fix?
- [ ] It is slow; use a bigger warehouse
- [x] It allows SQL injection; use bind parameters
- [ ] It uses too many credits; enable the result cache
- [ ] Nothing is wrong
> Concatenating user input into SQL allows injection. Bind variables pass values safely.

### Which tool helps diagnose network connectivity problems between a client and Snowflake?
- [ ] Snowsight Query Profile
- [ ] Snowflake Marketplace
- [x] SnowCD
- [ ] The SQL API
> SnowCD is a command-line diagnostic tool for finding and fixing client connectivity issues.
