# Understanding Costs

Snowflake charges for what you use rather than for fixed servers. Your bill is made of three parts: **compute**, **storage** and **data transfer**. Understanding how each one is measured is the first step to predicting spend and avoiding surprises.

## How it works

**Credits.** Compute is measured in Snowflake **credits**, a unit of consumption. Your cost is the number of credits used multiplied by your price per credit, which depends on your contract, edition and region.

**1. Compute** has several sources:

- **Virtual warehouses** are the compute clusters you create to run queries and load data. They use credits only while running. Each size up (X-Small, Small, Medium, Large and so on) roughly doubles both compute power and credits per hour. Billing is **per second with a 60-second minimum** each time a warehouse starts or resumes. Suspending and resuming within the first minute starts a new minimum each time. A suspended warehouse uses no credits.
- **Serverless features** such as Snowpipe, Automatic Clustering, Search Optimization, materialized view maintenance, serverless tasks and serverless alerts use compute managed by Snowflake. They are billed per second of compute-hours at rates that vary by feature.
- **Cloud services** handle logins, query compilation, metadata and security. Cloud services credits are only billed if daily cloud services usage exceeds **10% of daily warehouse usage**; the adjustment is calculated daily in UTC. Serverless compute does not count toward that 10%.
- **Compute pools** run Snowpark Container Services.

**2. Storage** is a flat rate per terabyte per month, based on the average compressed bytes stored each day. It includes table data, data kept for Time Travel and Fail-safe, and files in internal stages.

**3. Data transfer.** Loading data in (ingress) is free. Moving data **out** to a different region or cloud provider (egress) is charged per terabyte.

Snowflake features such as Cortex AI also have their own usage-based pricing.

## Example

Credits used per day by service over the last 30 days, including the cloud services adjustment:

```sql
SELECT usage_date,
       service_type,
       SUM(credits_used_compute)              AS compute_credits,
       SUM(credits_used_cloud_services)       AS cloud_services_credits,
       SUM(credits_adjustment_cloud_services) AS cloud_services_adjustment,
       SUM(credits_billed)                    AS billed_credits
FROM snowflake.account_usage.metering_daily_history
WHERE usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY usage_date, service_type
ORDER BY usage_date, billed_credits DESC;
```

Average storage per day, split into tables, stages and Fail-safe:

```sql
SELECT usage_date,
       storage_bytes  / POWER(1024, 4) AS table_tb,
       stage_bytes    / POWER(1024, 4) AS stage_tb,
       failsafe_bytes / POWER(1024, 4) AS failsafe_tb
FROM snowflake.account_usage.storage_usage
WHERE usage_date >= DATEADD('day', -30, CURRENT_DATE())
ORDER BY usage_date;
```

A quick worked example: a Small warehouse uses 2 credits per hour. If it runs for 90 minutes in total in a day, it uses 3 credits. If it resumes for a 10-second query, you pay for 60 seconds.

## Best practices

- Set **auto-suspend** on every warehouse so idle warehouses stop billing.
- Start with a small warehouse size and increase only when a workload needs it.
- Use **budgets** and **resource monitors** to get notified about, or limit, spending.
- Review the **Cost management** pages in Snowsight (**Admin » Cost management**) regularly.
- Use `METERING_DAILY_HISTORY` when you need credits actually billed, because most views show cloud services before the 10% adjustment.

## Common pitfalls

- Leaving a warehouse running with a long auto-suspend or none at all.
- Forgetting that serverless features (clustering, search optimization, materialized views) add credits without a warehouse.
- Assuming storage is only "live" data; Time Travel, Fail-safe and stages also count.
- Running many very short sessions that resume a warehouse repeatedly and pay the 60-second minimum each time.

## Learn more

- [Understanding overall cost](https://docs.snowflake.com/en/user-guide/cost-understanding-overall)
- [Understanding compute cost](https://docs.snowflake.com/en/user-guide/cost-understanding-compute)
- [Exploring compute cost](https://docs.snowflake.com/en/user-guide/cost-exploring-compute)

## Knowledge check

### A warehouse resumes, runs a 15-second query and then suspends. How much compute time is billed?
- [ ] 15 seconds
- [x] 60 seconds, because of the minimum charge each time a warehouse starts
- [ ] A full hour
- [ ] Nothing, because queries under a minute are free
> Warehouses are billed per second with a 60-second minimum each time they start or resume.

### On a day with 100 warehouse credits and 8 cloud services credits, how many cloud services credits are billed?
- [ ] 8
- [ ] 10
- [x] 0
- [ ] 18
> Cloud services are billed only for usage above 10% of daily warehouse usage; 8 is below the 10-credit threshold, so the adjustment cancels it.

### Which of these is not charged by Snowflake?
- [ ] Storage of data in Time Travel
- [ ] Transferring data to another cloud region
- [x] Loading data into Snowflake from cloud storage (ingress)
- [ ] Running a serverless task
> Snowflake does not charge data ingress fees; it charges for egress, storage and compute.
