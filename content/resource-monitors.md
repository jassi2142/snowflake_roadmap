# Resource Monitors

A resource monitor is a Snowflake object that tracks credit usage by warehouses and can send notifications or suspend warehouses when usage reaches thresholds you define. It is the basic safety net that stops a forgotten or runaway warehouse from consuming an unexpected number of credits.

## How it works

A resource monitor has these main properties:

- **Credit quota**: the number of credits allowed per interval. Usage counts credits from the assigned warehouses plus the cloud services that support them (without the daily 10% cloud services adjustment).
- **Schedule**: by default, monitoring starts immediately and used credits reset to 0 at the start of each calendar month. You can set `FREQUENCY` (DAILY, WEEKLY, MONTHLY, YEARLY, NEVER) with a `START_TIMESTAMP`; if you set one you must set the other. Resets occur at 12:00 AM UTC.
- **Actions (triggers)**: thresholds as a percentage of the quota (values above 100 are allowed):
  - `NOTIFY`: send a notification only.
  - `SUSPEND`: notify and suspend assigned warehouses after running statements finish.
  - `SUSPEND_IMMEDIATE`: notify and suspend immediately, canceling running statements.
  
  Each monitor can have one SUSPEND, one SUSPEND_IMMEDIATE, and up to five NOTIFY actions.

**Monitor types**:

- An **account monitor** covers all warehouses in the account. There can be only one.
- A **warehouse monitor** covers the warehouses assigned to it. A warehouse can be assigned to only one warehouse monitor, and a monitor can have at most 500 warehouses.

Both levels apply: if either the account monitor or a warehouse's own monitor hits a suspend threshold, the warehouse is suspended.

Other important rules:

- Only ACCOUNTADMIN can create resource monitors; MONITOR and MODIFY privileges can be granted to other roles.
- Resource monitors work for **warehouses only**. They do not track serverless features or AI services; use budgets for those.
- A suspended warehouse cannot resume until the next interval, the quota or threshold is raised, the warehouse is unassigned, or the monitor is dropped.
- Notifications are disabled by default; each administrator must enable them and have a verified email.
- Suspension is not instantaneous, so usage can slightly exceed a threshold.

## Example

Create a monthly monitor with early warnings, a graceful suspend, and a hard stop, then assign it to a warehouse:

```sql
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE RESOURCE MONITOR analytics_rm
  WITH CREDIT_QUOTA = 500
  TRIGGERS ON 50 PERCENT DO NOTIFY
           ON 80 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND
           ON 110 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE analytics_wh SET RESOURCE_MONITOR = analytics_rm;
```

Create an account-level monitor:

```sql
CREATE RESOURCE MONITOR account_rm WITH CREDIT_QUOTA = 10000
  TRIGGERS ON 90 PERCENT DO SUSPEND;

ALTER ACCOUNT SET RESOURCE_MONITOR = account_rm;
```

Raise the quota mid-month after review:

```sql
ALTER RESOURCE MONITOR analytics_rm SET CREDIT_QUOTA = 750;
```

## Best practices

- Put an account-level monitor in place, plus warehouse monitors for key teams or workloads.
- Assign one warehouse per monitor when you need precise control; shared monitors let one warehouse's usage affect others.
- Leave a buffer, for example suspending at 90%, because suspension takes time.
- Use SUSPEND for normal limits and SUSPEND_IMMEDIATE only as a hard stop.
- Enable notifications for administrators and add up to five non-admin users to warehouse monitors with `NOTIFY_USERS`.
- Combine with budgets to cover serverless and AI spend.

## Common pitfalls

- Creating a monitor in SQL but never assigning it to a warehouse or the account, so it does nothing.
- Expecting resource monitors to cap Snowpipe, clustering, or Cortex costs.
- Forgetting that notifications must be enabled before anyone receives them.
- Using resource monitors for strict hourly control; they are designed for interval-level tracking.

## Learn more

- [Working with resource monitors](https://docs.snowflake.com/en/user-guide/resource-monitors)
- [CREATE RESOURCE MONITOR](https://docs.snowflake.com/en/sql-reference/sql/create-resource-monitor)

## Knowledge check

### You want warehouses to stop accepting new queries at 100% of quota but let running queries finish. Which action do you use?
- [ ] NOTIFY
- [x] SUSPEND
- [ ] SUSPEND_IMMEDIATE
- [ ] DROP
> SUSPEND waits for currently executing statements to complete before suspending the warehouse.

### A warehouse is assigned to a warehouse monitor with plenty of headroom, but the account monitor has reached its suspend threshold. What happens?
- [ ] Nothing, because the warehouse monitor overrides the account monitor
- [x] The warehouse is suspended
- [ ] Only new warehouses are blocked
- [ ] The warehouse monitor quota is automatically raised
> An account-level monitor does not get overridden by warehouse monitors; reaching either threshold suspends the warehouse.

### Which spend can a resource monitor NOT control?
- [ ] A user-managed X-Small warehouse
- [ ] A multi-cluster warehouse
- [x] Snowpipe and Automatic Clustering
- [ ] Warehouses assigned at the account level
> Resource monitors work only for warehouses; serverless features require budgets for monitoring.
