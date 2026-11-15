# Budgets

Budgets let you set a monthly credit spending limit for the whole account or for a group of objects, and get notified when Snowflake forecasts that you will exceed it. They are an early-warning tool for cost control that covers both warehouses and serverless features.

## How it works

There are two types of budget:

- **Account budget** – monitors all credit usage in the account. You must **activate** it before using budgets.
- **Custom budgets** – monitor a specific group of supported objects. Objects can be added individually or through **tags**, and adding a database or schema adds the supported objects it contains.

Key behaviors from the documentation:

- The **spending limit** is in credits and is used for **alerting and notification only**; budgets do not stop workloads by themselves.
- The interval is one **calendar month**, from 12:00 AM UTC on the first day to the last day of the month.
- Budgets use **time-series forecasting**. A notification is sent daily when spending is projected to exceed the limit. You can also set a threshold percentage of the limit.
- Notifications can go to email addresses, a cloud queue (Amazon SNS, Azure Event Grid or Google Cloud Pub/Sub), or a webhook (for example Slack, Microsoft Teams or PagerDuty).
- You can configure **custom actions** that call your own stored procedures at a threshold, for example to suspend warehouses, and **cycle-start actions** that run at the start of each month.
- The default **refresh interval** is up to **6.5 hours**. A **low latency budget** refreshes every hour but increases the budget's own compute cost by a factor of 12.
- Supported services include warehouses, Automatic Clustering, materialized views, Snowpipe, Query Acceleration, replication, search optimization, serverless tasks and alerts, Snowpark Container Services and others.

**Backfill.** If you activate the account budget mid-month, data from the start of the month is backfilled. For custom budgets, history is backfilled only for resources added **by tag**; individually added resources start from the day they are added, so the first month's forecast may be inaccurate.

**Tags vs. individual objects.** An object added individually can belong to only one custom budget; adding it to a second budget silently removes it from the first. Objects included through tags can be in multiple budgets.

**Privileges.** Application roles `BUDGET_VIEWER` and `BUDGET_ADMIN` manage the account budget. For custom budgets, you need the `SNOWFLAKE.BUDGET_CREATOR` database role, the `CREATE SNOWFLAKE.CORE.BUDGET` privilege on the schema, and `APPLYBUDGET` on each object or tag you add.

## Example

Create a custom budget and set its monthly limit:

```sql
USE SCHEMA budgets_db.budgets_schema;

CREATE SNOWFLAKE.CORE.BUDGET marketing_budget();

CALL marketing_budget!SET_SPENDING_LIMIT(500);
```

Add all resources tagged `cost_center = 'marketing'`:

```sql
GRANT APPLYBUDGET ON TAG cost_mgmt_db.tags.cost_center TO ROLE budget_admin;

CALL budgets_db.budgets_schema.marketing_budget!ADD_RESOURCE_TAG(
  SELECT SYSTEM$REFERENCE('TAG', 'cost_mgmt_db.tags.cost_center', 'SESSION', 'applybudget'),
  'marketing');
```

Review which resources the budget covers, and switch to hourly refresh during a cost investigation:

```sql
CALL marketing_budget!GET_LINKED_RESOURCES();
CALL marketing_budget!SET_REFRESH_TIER('TIER_1H');
```

You can also create and edit budgets in Snowsight under **Admin » Cost management » Budgets**.

## Best practices

- Activate the account budget first, then add custom budgets for teams or projects.
- Add resources through **tags** so new objects are covered automatically and history is backfilled.
- Set a threshold below 100% so teams have time to react.
- Combine budgets with **resource monitors** when you need hard limits on warehouses.
- Use low latency budgets temporarily, then return to the default refresh interval.

## Common pitfalls

- Expecting a budget to suspend warehouses automatically; that requires a custom action or a resource monitor.
- Adding the same object individually to two custom budgets and losing it from the first.
- Leaving budgets on hourly refresh permanently and paying 12 times the budget compute cost.
- Judging the first month's forecast for individually added resources, which has no backfilled history.

## Learn more

- [Monitor credit usage with budgets](https://docs.snowflake.com/en/user-guide/budgets)
- [Custom budgets](https://docs.snowflake.com/en/user-guide/budgets/custom-budget)

## Knowledge check

### A team's custom budget has a 1,000-credit limit and spending is forecast to reach 1,300. What happens by default?
- [ ] Their warehouses are suspended
- [x] A notification is sent to the configured recipients, but workloads keep running
- [ ] New queries are blocked until next month
- [ ] The limit is automatically raised
> Budget spending limits are for alerting and notification only; stopping workloads requires a custom action or a resource monitor.

### Why is adding objects to a custom budget by tag usually better than adding them one by one?
- [ ] Tags make the budget refresh every hour
- [x] Tagged objects are covered automatically, can belong to multiple budgets, and get historical backfill for the month
- [ ] Tags reduce the cost of the objects
- [ ] Individually added objects are not supported
> Tag-based membership scales to new objects, allows an object to appear in several budgets, and is the only method that backfills the current month's data.

### During a cost incident, you switch a budget to a one-hour refresh interval. What trade-off should you remember?
- [ ] Notifications are disabled
- [ ] Serverless costs are excluded
- [x] The budget's own compute cost increases by a factor of 12
- [ ] The budget resets its monthly limit
> A low latency budget refreshes hourly instead of up to every 6.5 hours, which makes its compute cost 12 times higher.
