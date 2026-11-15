# Fail-safe

Fail-safe is a last-resort data recovery period that begins after Time Travel ends. For 7 days, Snowflake keeps historical data from permanent tables so that its own engineers can attempt recovery after an extreme event, such as a major system failure or a security incident. You cannot query or restore Fail-safe data yourself, but understanding it helps you plan recovery and storage costs.

## How it works

Snowflake protects historical data in two stages, together called Continuous Data Protection:

1. **Time Travel** - a period you configure (by default 1 day). During this time **you** can query, clone, and undrop data.
2. **Fail-safe** - a fixed **7-day** period that starts immediately after Time Travel ends. During this time **only Snowflake** can recover data.

Key facts about Fail-safe:

- **Not configurable.** You cannot shorten, lengthen, or turn off the 7 days for permanent tables.
- **Not self-service.** There is no SQL command to read Fail-safe data. To request recovery, you open a case with Snowflake Support.
- **Best effort.** Recovery is not guaranteed and can take from several hours to several days.
- **Costs storage.** Data in Fail-safe counts toward your storage bill. Recovery itself uses Snowflake-managed serverless compute, billed under the `FAILSAFE_RECOVERY` service type.
- **Only for permanent objects.** Transient and temporary tables have no Fail-safe period, which is why they are cheaper for data you can easily recreate.

### A simple timeline

Suppose a permanent table has a 1-day retention period and you update a row on Day 5 at 1:00 PM:

| Period | Who can recover the old row |
| --- | --- |
| Day 5, 1:00 PM to Day 6, 1:00 PM | You, using Time Travel |
| Day 6, 1:00 PM to Day 13, 1:00 PM | Only Snowflake, through Fail-safe |
| After Day 13, 1:00 PM | No one; the data is gone |

A long-running Time Travel query can delay the move of data into Fail-safe until the query finishes.

### Viewing Fail-safe storage

As ACCOUNTADMIN, open **Admin » Cost management » Consumption** in Snowsight, filter **Usage Type** to **Storage**, and look at the Fail-safe portion of the storage breakdown. You can also query storage metrics with SQL.

## Example

Check how much storage each table uses for active data, Time Travel, and Fail-safe:

```sql
SELECT table_catalog, table_schema, table_name,
       active_bytes, time_travel_bytes, failsafe_bytes
FROM snowflake.account_usage.table_storage_metrics
WHERE deleted = FALSE
ORDER BY failsafe_bytes DESC
LIMIT 20;
```

Avoid Fail-safe storage for easily reloaded staging data by using a transient table:

```sql
CREATE TRANSIENT TABLE staging.raw_events (
  event_id   NUMBER,
  payload    VARIANT,
  loaded_at  TIMESTAMP_NTZ
);
```

Check recovery-related credits if Support has performed a Fail-safe recovery:

```sql
SELECT usage_date, credits_used
FROM snowflake.account_usage.metering_daily_history
WHERE service_type = 'FAILSAFE_RECOVERY';
```

## Best practices

- Rely on Time Travel (and backups, if you use them) for everyday recovery; treat Fail-safe as an emergency option only.
- Use transient tables for staging and scratch data to avoid paying for 7 days of Fail-safe storage on high-churn tables.
- Watch `failsafe_bytes` for tables that are frequently rewritten or truncated; they can accumulate large Fail-safe storage.
- Keep your Time Travel retention long enough that you rarely need Fail-safe.

## Common pitfalls

- Thinking Fail-safe is a way to read old data after Time Travel ends; it is not accessible to users.
- Planning a recovery process that depends on Fail-safe, which is best effort and may take days.
- Repeatedly dropping and recreating large permanent tables, which leaves each old copy in Fail-safe storage.
- Assuming transient tables are protected by Fail-safe; they are not.

## Learn more

- [Understanding and viewing Fail-safe](https://docs.snowflake.com/en/user-guide/data-failsafe)
- [Storage costs for Time Travel and Fail-safe](https://docs.snowflake.com/en/user-guide/data-cdp-storage-costs)

## Knowledge check

### A table's Time Travel period ended two days ago and you need yesterday's deleted rows. What can you do?
- [ ] Run SELECT ... AT(OFFSET => ...) against Fail-safe
- [ ] Run UNDROP TABLE
- [x] Open a case with Snowflake Support, knowing recovery is best effort
- [ ] Increase the retention period to bring the data back
> Only Snowflake can recover data from Fail-safe, and only on a best-effort basis; increasing retention does not restore data already moved to Fail-safe.

### Why might a team choose a transient table for a staging area that is reloaded every hour?
- [ ] Transient tables have a longer Fail-safe period
- [x] Transient tables have no Fail-safe period, so they avoid that extra storage cost
- [ ] Transient tables cannot be queried with Time Travel at all
- [ ] Transient tables are replicated automatically
> Transient tables skip Fail-safe, which saves storage for data that can easily be recreated.

### How long is the Fail-safe period for a permanent table, and can you change it?
- [ ] 1 day, configurable up to 90 days
- [ ] 90 days, fixed
- [x] 7 days, not configurable
- [ ] 7 days, configurable with DATA_RETENTION_TIME_IN_DAYS
> Fail-safe is a fixed 7-day period that starts after Time Travel ends; DATA_RETENTION_TIME_IN_DAYS only controls Time Travel.
