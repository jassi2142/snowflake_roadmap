# Snowsight (Web UI)

Snowsight is Snowflake's web interface. In your browser you can write and run SQL and Python, explore data and objects, build charts and dashboards, monitor queries and costs, and administer your account. For most beginners it is the first and main place they work with Snowflake.

## How it works

You sign in to Snowsight with your account URL and credentials. The interface is organized into areas you reach from the left navigation menu. Menu labels can change between releases, but the main capabilities are:

- **Worksheets and notebooks.** SQL worksheets let you write and run queries, view results, and see simple charts. Notebooks combine SQL and Python cells for step-by-step analysis.
- **Data / catalog browsing.** You can browse databases, schemas, tables, views, and stages, preview data, and see column definitions and privileges without writing SQL.
- **Dashboards.** You can turn query results into charts and arrange them into dashboards to share.
- **Query monitoring.** Query history shows past and running queries. The **Query Profile** shows each step of a query's execution plan, including how many micro-partitions were scanned compared with the total.
- **Administration.** Users with the right roles can manage warehouses, users and roles, billing, and usage. In a trial, the ACCOUNTADMIN role sees a tile with the remaining free balance.
- **Marketplace and apps.** You can find data and applications in the Snowflake Marketplace, and work with Streamlit apps.

**Session context matters.** Every worksheet has its own role, warehouse, database, and schema. Snowsight shows them in the worksheet's context selectors. The **role** controls what you can see and do. The **warehouse** provides compute for queries. If you cannot see an object, check your role first.

## Example

Paste this into a new SQL worksheet. The `USE` statements set the worksheet context, and the query runs on the selected warehouse.

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE learn_wh;
USE SCHEMA snowflake_sample_data.tpch_sf1;

SELECT o_orderpriority,
       COUNT(*)          AS orders,
       AVG(o_totalprice) AS avg_price
FROM orders
GROUP BY o_orderpriority
ORDER BY o_orderpriority;
```

After it runs, switch the results to a chart, then open the Query Profile from query details to see how the query was executed.

This statement shows your current context:

```sql
SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA();
```

## Best practices

- Set the role and warehouse explicitly at the top of each worksheet so it gives the same results whenever it runs.
- Use the Query Profile to understand slow queries before you increase the warehouse size.
- Organize worksheets into folders, and give them clear names.
- Use a lower-privilege role for daily work; switch to ACCOUNTADMIN only for admin tasks.

## Common pitfalls

- Getting "object does not exist or not authorized" because the worksheet is using a role without access.
- Running queries on a large warehouse that was selected in an old worksheet.
- Assuming a chart or dashboard updates itself. Dashboards show query results and must be refreshed.

## Learn more

- [Snowsight overview](https://docs.snowflake.com/en/user-guide/ui-snowsight)

## Knowledge check

### A colleague shared a table with you, but it does not appear in your Snowsight worksheet. What should you check first?
- [ ] Whether the warehouse is large enough
- [x] Whether the worksheet's active role has privileges on the table
- [ ] Whether your browser cache is cleared
- [ ] Whether the table has a clustering key
> Object visibility depends on the active role's privileges. The warehouse affects only compute.

### Where in Snowsight can you see how many micro-partitions a query scanned?
- [ ] The billing page
- [x] The Query Profile for that query
- [ ] The worksheet's context selector
- [ ] The Marketplace
> The Query Profile shows the execution plan with statistics such as partitions scanned and partitions total.

### What does the warehouse selected in a worksheet control?
- [ ] Which databases you can see
- [x] The compute resources used to run your queries
- [ ] Where the data is stored
- [ ] Your password policy
> A warehouse supplies compute. Access is controlled by roles, and data lives in the storage layer.
