# Auto-suspend & Auto-resume

Auto-suspend and auto-resume let Snowflake turn a warehouse off when it is idle and back on when work arrives. Because warehouses are billed only while running, these two settings are the simplest and most effective way to avoid paying for idle compute.

## How it works

- **Auto-suspend** is enabled by default. You set the number of seconds of inactivity (`AUTO_SUSPEND`) after which Snowflake suspends the warehouse. Setting it to `0` or `NULL` disables auto-suspend, so the warehouse runs until you suspend it manually.
- **Auto-resume** is enabled by default (`AUTO_RESUME = TRUE`). When a statement that needs a warehouse is submitted and that warehouse is the current warehouse for the session, Snowflake resumes it automatically.
- A suspended warehouse consumes no credits. Each resume is billed for a minimum of 60 seconds, then per second.
- Resuming is usually very fast (often a second or two), but can take longer depending on size and resource availability.
- When a warehouse suspends, its local data cache is dropped. The first queries after a resume may be slower while the cache is rebuilt.
- For a multi-cluster warehouse, these settings apply to the whole warehouse, not individual clusters. Auto-suspend happens only when the warehouse is down to its minimum number of clusters and idle; auto-resume applies only when the entire warehouse is suspended.

If auto-resume is disabled, a query sent to a suspended warehouse will not start it; someone must run `ALTER WAREHOUSE ... RESUME`. This is useful when you want to tightly control who can incur cost.

## Example

Create a warehouse that suspends after 5 minutes of inactivity and resumes on demand:

```sql
CREATE WAREHOUSE reporting_wh
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 300
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;
```

Change an existing warehouse to suspend after 60 seconds:

```sql
ALTER WAREHOUSE reporting_wh SET AUTO_SUSPEND = 60;
```

Disable auto-resume and control the warehouse manually:

```sql
ALTER WAREHOUSE reporting_wh SET AUTO_RESUME = FALSE;
ALTER WAREHOUSE reporting_wh RESUME;
ALTER WAREHOUSE reporting_wh SUSPEND;
```

Check current settings in the `auto_suspend` and `auto_resume` columns:

```sql
SHOW WAREHOUSES LIKE 'REPORTING_WH';
```

## Best practices

- Keep auto-suspend low for most warehouses; Snowflake recommends values such as 5 or 10 minutes or less because billing is per second.
- Match the value to gaps in your workload. If queries arrive every 2-3 minutes, a 1-minute auto-suspend causes constant suspend/resume cycles, each paying the 60-second minimum.
- For BI dashboards that benefit from a warm cache, a slightly longer auto-suspend may improve user experience; weigh this against idle cost.
- Keep auto-resume on for interactive and scheduled workloads so users and jobs are not blocked.
- Consider disabling auto-suspend only for heavy, steady workloads that need zero startup delay, and understand the continuous cost.

## Common pitfalls

- Disabling auto-suspend on a large warehouse "temporarily" and forgetting about it. An idle X-Large still burns 16 credits per hour (Gen1).
- Setting auto-suspend so low that the warehouse thrashes between suspended and running.
- Expecting the warehouse cache to survive a suspension; it does not.
- Assuming a suspended warehouse with auto-resume off will start when a scheduled job runs; the job fails instead.

## Learn more

- [Warehouse considerations](https://docs.snowflake.com/en/user-guide/warehouses-considerations)
- [Overview of warehouses](https://docs.snowflake.com/en/user-guide/warehouses-overview)

## Knowledge check

### Queries reach a warehouse steadily every 2 to 3 minutes during business hours. Which auto-suspend setting is most sensible?
- [ ] 30 seconds, to minimize idle time
- [x] A value somewhat longer than the typical gap, such as 5 minutes
- [ ] 0, to disable auto-suspend entirely
- [ ] 24 hours
> A value just longer than the normal gap avoids repeated suspend/resume cycles that each incur the 60-second minimum, while still suspending when activity stops.

### How do you disable auto-suspend for a warehouse in SQL?
- [ ] Set AUTO_RESUME = FALSE
- [x] Set AUTO_SUSPEND to 0 or NULL
- [ ] Set AUTO_SUSPEND to -1
- [ ] Set INITIALLY_SUSPENDED = FALSE
> Specifying 0 or NULL for AUTO_SUSPEND disables automatic suspension.

### After a warehouse auto-resumes, the first few dashboard queries are slower than usual. What is the most likely reason?
- [ ] Auto-resume always starts a smaller warehouse first
- [x] The warehouse cache was dropped when it suspended and is being rebuilt
- [ ] The result cache is disabled after a resume
- [ ] Queries are throttled for 60 seconds after resume
> Suspending a warehouse drops its local data cache, so early queries after a resume must read more data from storage.
