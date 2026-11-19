# Snowflake Notebooks & Workspaces

Snowflake Notebooks provide an interactive, collaborative development environment built directly into Snowsight. They combine Python, SQL, Markdown, and embedded Streamlit elements into a single computational document. With native Git integration, package management via Anaconda, and the choice between standard Virtual Warehouses and containerized GPU compute pools, Notebooks and Workspaces serve as the unified home for modern data engineering, exploratory data analysis (EDA), and machine learning in Snowflake.

## How it works

Historically, data scientists and analysts had to run local Jupyter environments or separate cloud notebook services, creating governance gaps and requiring data extraction over networks. Snowflake Notebooks bring computation directly to governed data inside Snowflake's security perimeter.

### 1. Multi-Language Execution & Interactive UI

- **Cell Types**: Notebooks support **Python** (via Snowpark Python), **SQL**, and **Markdown** cells within the same session. Variables, DataFrames, and query results pass seamlessly between Python and SQL cells (e.g., query a SQL table, assign it to a Snowpark DataFrame, and run Pandas operations).
- **Embedded Streamlit**: Engineers can render interactive Streamlit widgets (such as `st.slider`, `st.dataframe`, `st.line_chart`, `st.selectbox`) directly inside notebook cells for immediate, interactive visual exploration without building a separate web app.
- **Package Management**: Native integration with the **Anaconda channel** allows data teams to import hundreds of curated scientific, data engineering, and machine learning packages (`numpy`, `pandas`, `scikit-learn`, `xgboost`, `pytorch`, `transformers`) with automatic dependency resolution and zero local installation.

### 2. Compute Execution: Warehouses vs. Container Compute Pools

Snowflake Notebooks offer flexible compute engines tailored to workload demands:
- **Virtual Warehouse Runtime**: The notebook runs on standard virtual warehouses (X-Small to 6X-Large). Best suited for SQL transformations, Snowpark data processing, and lightweight Python scripting. It leverages standard per-second warehouse billing and auto-suspend.
- **Container Runtime (Snowpark Container Services)**: The notebook executes inside dedicated container compute pools on SPCS. This unlocks:
  - **GPU Acceleration**: Access to Nvidia GPU instances (e.g. A10G, H100) for deep learning training, fine-tuning large language models, and high-performance tensor computing.
  - **Custom PyPI & System Packages**: Freedom to `pip install` packages not included in the Anaconda channel, run custom C/C++ libraries, and configure custom environment images.
  - **Enhanced Memory & CPU**: High-memory machine types for in-memory model fitting.

### 3. Workspaces, Artifacts & Modern Application Development

In the Snowsight interface, **Workspaces** organize related assets into collaborative project hubs:
- **Git Version Control**: Notebooks connect directly to Git repositories (GitHub, GitLab, Bitbucket). Developers can branch, pull, edit, commit, and push notebook revisions directly from Snowsight.
- **Artifacts & Templates**: Workspaces support creating reusable project templates, code bundles, dbt projects, and containerized application packages.
- **Full-Stack Web Apps**: In addition to Streamlit, Snowflake now supports deploying **Next.js web applications** directly on Snowpark Container Services, giving developers the ability to build rich, custom web frontends powered directly by Snowflake data.

## Example

### Multi-Language Cell Interaction in Snowflake Notebooks

```sql
-- Cell 1 (SQL): Query and filter high-value accounts into a temporary view
CREATE OR REPLACE TEMPORARY VIEW v_high_value_customers AS
SELECT
  customer_id,
  account_balance,
  signup_date,
  DATEDIFF('day', signup_date, CURRENT_DATE()) AS tenure_days
FROM prod_db.curated.customers
WHERE account_balance > 10000;
```

```python
# Cell 2 (Python): Ingest SQL view into Snowpark DataFrame and compute metrics
import snowflake.snowpark.functions as F
import streamlit as st

# Reference the SQL view seamlessly
df = session.table("v_high_value_customers")
pdf = df.to_pandas()

# Cell 3 (Streamlit): Render interactive slider and dynamic histogram
min_tenure = st.slider("Filter by Minimum Customer Tenure (Days):", 0, 1000, 90)
filtered_data = pdf[pdf["TENURE_DAYS"] >= min_tenure]

st.metric("Total High-Value Customers", len(filtered_data))
st.bar_chart(filtered_data.set_index("CUSTOMER_ID")["ACCOUNT_BALANCE"])
```

### Scheduling a Notebook to Run via Snowflake Tasks

```sql
-- Execute a production notebook automatically on a schedule
CREATE OR REPLACE TASK run_daily_ml_notebook_task
  WAREHOUSE = ml_wh
  SCHEDULE = 'USING CRON 0 6 * * * America/New_York'
AS
  EXECUTE NOTEBOOK my_db.analytics.customer_churn_notebook();

ALTER TASK run_daily_ml_notebook_task RESUME;
```

## Best practices

- Use Virtual Warehouse compute for general SQL and Snowpark data preparation; switch to Container Runtimes (SPCS) only when GPU acceleration or uncurated external PyPI packages are strictly needed.
- Connect every production notebook to a Git repository to ensure version control, code review, and disaster recovery.
- Use `EXECUTE NOTEBOOK` inside Snowflake Tasks to automate production machine learning pipelines and periodic data reporting without external orchestrators.
- Pin package versions in the notebook environment settings to avoid unexpected pipeline breakage when new library versions release.

## Common pitfalls

- Leaving containerized GPU compute pools running indefinitely; ensure compute pools are configured with auto-suspend timeouts.
- Hard-coding sensitive API keys or credentials directly in notebook cells instead of using Snowflake Secrets and session context.
- Running large Pandas conversions (`.to_pandas()`) on massive multi-terabyte datasets, leading to out-of-memory errors on smaller warehouse sizes (keep processing in Snowpark DataFrames whenever possible).
- Relying on legacy Dashboards instead of modern Snowflake Notebooks and Streamlit apps for exploratory analysis.

## Learn more

- [About Snowflake Notebooks](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-about)
- [Snowflake Notebooks Container Runtime](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-container-runtime)
- [Executing Notebooks in Tasks](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-schedule)

## Knowledge check

### When should a data science team choose the Container Runtime on SPCS over a standard Virtual Warehouse for their Snowflake Notebook?
- [ ] Only when querying standard SQL views
- [x] When the workload requires GPU hardware acceleration for deep learning or custom libraries outside the curated Anaconda channel
- [ ] When they want queries to run without any compute charges
- [ ] When using Git repositories
> Container Runtimes run on Snowpark Container Services compute pools, providing access to GPUs and custom Python environments, whereas virtual warehouses are optimized for standard CPU-based Snowpark and SQL processing.

### How can a data engineer automate a completed Snowflake Notebook to run every morning at 6:00 AM?
- [ ] Export the notebook as a CSV file to an external stage
- [x] Schedule a Snowflake Task using the EXECUTE NOTEBOOK statement
- [ ] Keep a browser tab open in Snowsight with an auto-refresh plugin
- [ ] Re-run the notebook manually from the Snowsight mobile app
> Snowflake supports automating notebooks natively using `EXECUTE NOTEBOOK <notebook_name>()` inside a scheduled Snowflake Task.

### What is the primary benefit of embedding Streamlit components inside Snowflake Notebook cells?
- [ ] It converts SQL queries into C++ machine code
- [x] It allows developers to build interactive UI widgets (sliders, charts, dropdowns) for live visual data exploration directly within the document
- [ ] It bypasses role-based access control for faster dashboards
- [ ] It disables all logging in Event Tables
> Streamlit in Snowflake Notebooks enables interactive data applications and live visual exploratory analysis directly inside cell outputs without requiring a standalone web app deployment.
