# Streamlit in Snowflake

Streamlit in Snowflake (SiS) lets you build and host interactive Python data apps directly inside your Snowflake account. Apps run on Snowflake compute, query data under Snowflake's access controls, and are shared with other users through roles, so you get dashboards and internal tools without deploying or securing a separate web server.

## How it works

A Streamlit app is a Snowflake object created with `CREATE STREAMLIT`, typically from files on a stage or a Git repository (the `FROM` clause) with a `MAIN_FILE` entry point. You can also create and edit apps in Snowsight. Viewers open the app in Snowsight, and the role that owns the app determines what data its queries can reach.

There are two runtime environments, and choosing between them is the most important design decision:

| | Warehouse runtime | Container runtime |
|---|---|---|
| App code runs on | A virtual warehouse | A compute pool node (Snowpark Container Services) |
| Instances | One personal instance per viewer | One shared, long-running instance for all viewers |
| Python packages | Snowflake Conda channel via `environment.yml` | PyPI and similar via `requirements.txt` or `pyproject.toml` (needs an external access integration) |
| Streamlit versions | Limited selection from 1.22 | 1.50 and later, any version |
| Caching | No cross-session caching | Full Streamlit caching shared across sessions |
| Query rights | Owner's rights | Owner's rights by default, with restricted caller's rights in Preview |

Some practical details:

- **Query warehouse**: in a container runtime, `QUERY_WAREHOUSE` runs the app's SQL while the compute pool runs the Python. In a warehouse runtime, `QUERY_WAREHOUSE` runs the app code itself, and you can switch to another warehouse for heavy queries inside the code.
- **Defaults**: with the 2026_06 behavior change bundle, new apps created without `RUNTIME_NAME` default to the container runtime (`SYSTEM$ST_CONTAINER_RUNTIME_PY3_11`). Specify `RUNTIME_NAME = 'SYSTEM$WAREHOUSE_RUNTIME'` to keep the warehouse runtime. Existing apps are not affected.
- **Compute pool**: if you omit `COMPUTE_POOL`, Snowflake uses the account parameter `DEFAULT_STREAMLIT_COMPUTE_POOL`, which is `SYSTEM_COMPUTE_POOL_CPU` for new accounts. That system pool runs three apps per node, and other pools run one app per node.
- **Container apps** suspend after three days of viewer inactivity and are subject to the Snowpark Container Services maintenance window.

## Example

A minimal app that reads a table and charts it:

```python
import streamlit as st

conn = st.connection("snowflake")

@st.cache_data(ttl=600)
def load_sales():
    return conn.query(
        "SELECT region, SUM(amount) AS total FROM sales.curated.orders GROUP BY region"
    )

st.title("Sales by region")
df = load_sales()
st.bar_chart(df, x="REGION", y="TOTAL")
```

Deploy it on the container runtime from a stage:

```sql
CREATE STREAMLIT analytics.apps.sales_dashboard
  FROM '@analytics.apps.app_stage/sales_dashboard'
  MAIN_FILE = 'streamlit_app.py'
  RUNTIME_NAME = 'SYSTEM$ST_CONTAINER_RUNTIME_PY3_11'
  COMPUTE_POOL = streamlit_pool
  QUERY_WAREHOUSE = reporting_wh;

GRANT USAGE ON STREAMLIT analytics.apps.sales_dashboard TO ROLE sales_analyst;
```

Viewers with the `sales_analyst` role can now open the app. The app's queries run with the owner role's privileges.

## Best practices

- Use the container runtime for frequently used apps. It starts faster for viewers, supports shared caching, and is generally cheaper per minute than a warehouse.
- Cache expensive queries with `st.cache_data` and set a `ttl`, so the app does not rerun the same SQL on every interaction.
- Give each app a dedicated owner role with only the privileges it needs, because queries run with the owner's rights.
- Keep app code in Git and deploy with `CREATE STREAMLIT ... FROM` a stage or repository, so changes are reviewed.
- Separate code compute from query compute: a small pool or warehouse for the app, a right-sized warehouse for its queries.
- Pin package versions (`==` in `requirements.txt`) for reproducible builds.

## Common pitfalls

- Assuming viewers see only the data their own role can access. By default, the app uses the owner's privileges.
- Caching viewer-specific query results in a container-runtime app, which can leak data across viewers who share the instance.
- Using `get_active_session()` in a container runtime app instead of `st.connection("snowflake").session()`.
- Relying on the old default runtime in scripts after the default changes, leading to errors about missing compute pools or unsupported clauses such as `IMPORTS`.
- Running warehouse-runtime apps on a large warehouse that stays awake for idle viewer sessions.

## Learn more

- [Runtime environments for Streamlit apps](https://docs.snowflake.com/en/developer-guide/streamlit/app-development/runtime-environments)
- [New Streamlits default to container runtime](https://docs.snowflake.com/en/release-notes/bcr-bundles/2026_06/bcr-2342)

## Knowledge check

### A dashboard is opened by 200 analysts every morning and loads the same heavy query. Which setup gives the best experience and cost?
- [ ] Warehouse runtime on an X-Large warehouse
- [x] Container runtime with st.cache_data on the heavy query, so all viewers share the cached result
- [ ] Warehouse runtime with one app copy per analyst
- [ ] A separate Streamlit app for each team
> The container runtime runs one shared instance, so cached results are reused across sessions, and viewers connect to an app that is already running.

### A viewer who has no SELECT on the HR schema can see HR data in an app. What explains this?
- [ ] Streamlit bypasses Snowflake security
- [x] The app's queries run with the owner role's privileges, and the owner role can read the HR schema
- [ ] The viewer inherited the ACCOUNTADMIN role
- [ ] Container runtimes always use caller's rights
> Streamlit apps use owner's rights for queries by default. Restrict the owner role, or use restricted caller's rights where available, to limit exposure.

### Your app needs a package that is only published on PyPI. What is required?
- [ ] Add it to environment.yml in a warehouse runtime
- [x] Use the container runtime with the package in requirements.txt and an external access integration to reach the package index
- [ ] Upload the wheel to a user stage
- [ ] Nothing; all PyPI packages are preinstalled
> The warehouse runtime only uses the Snowflake Conda channel. The container runtime installs packages from PyPI, which requires network access through an external access integration.
