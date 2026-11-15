# Failover Groups

A failover group is a replication group that can also be promoted. Its secondary copies in target accounts are read-only during normal operation, but during an outage or planned migration you promote a secondary to primary, making its objects writable in the new region or cloud. Failover groups are the core Snowflake mechanism for account-level business continuity, covering not just data but users, roles, warehouses, and integrations.

## How it works

Failover groups require **Business Critical Edition or higher** in every participating account, and they can only be replicated to Business Critical (or higher) accounts. They are not available in the People's Republic of China.

**Composition.** Like replication groups, a failover group declares `OBJECT_TYPES`, allowed objects, `ALLOWED_ACCOUNTS`, and a `REPLICATION_SCHEDULE`. For failover, the scope typically extends beyond databases to `USERS`, `ROLES`, `WAREHOUSES`, `RESOURCE MONITORS`, `INTEGRATIONS` (security, API, notification, storage, external access), `NETWORK POLICIES`, and `ACCOUNT PARAMETERS`, so the target can actually serve workloads after promotion. Stages and pipes are supported in replication and failover groups.

**Promotion.** In the target account, a role with the FAILOVER privilege runs `ALTER FAILOVER GROUP <name> PRIMARY`. Objects in that group become read-write in the new primary and read-only in the former primary. On failover, scheduled refreshes on secondaries are suspended; resume them with `ALTER FAILOVER GROUP ... RESUME` in each target.

**In-flight refreshes.** Snowflake refuses promotion while a refresh is running for that group, to protect integrity. You can wait, suspend future refreshes (`SUSPEND`), or suspend and cancel the current one (`SUSPEND IMMEDIATE`). Cancelling during the `SECONDARY_DOWNLOADING_METADATA` or `SECONDARY_DOWNLOADING_DATA` phases can leave the target inconsistent, so check the phase with `REPLICATION_GROUP_REFRESH_PROGRESS` first. In a regional outage, a refresh already in those phases proceeds to completion even if the source is unreachable.

**Bulk failover.** Snowsight's **Initiate failover** promotes several failover groups and Client Redirect connections at once, which gives the most consistent cutover. Advanced options let you skip groups being refreshed or force-cancel refreshes.

### Design decisions

- **Group granularity.** Multiple groups let you fail over independently and schedule critical databases more frequently. One group simplifies operations and guarantees cross-object consistency. A common pattern is one "account objects" group (users, roles, warehouses, integrations) plus a small number of data groups aligned to dependency boundaries.
- **RPO trade-off.** Data loss on unplanned failover is bounded by the time since the last completed refresh, which is roughly the schedule interval plus refresh duration. Tighter schedules cost more in transfer and compute.
- **Pipelines.** After failover, ingestion and transformation must restart in the new primary. Snowpipe Streaming channels must be reopened and missing rows re-inserted from offset tokens; Kafka connector offsets must be reset.
- **Failback** is the same operation in reverse once the original region is healthy.

## Example

Create a primary failover group in the source account:

```sql
CREATE FAILOVER GROUP prod_fg
  OBJECT_TYPES = USERS, ROLES, WAREHOUSES, RESOURCE MONITORS,
                 DATABASES, INTEGRATIONS, NETWORK POLICIES
  ALLOWED_DATABASES = sales_db, governance_db
  ALLOWED_INTEGRATION_TYPES = SECURITY INTEGRATIONS
  ALLOWED_ACCOUNTS = myorg.prod_dr
  REPLICATION_SCHEDULE = '10 MINUTE';
```

Create the secondary in the DR account:

```sql
CREATE FAILOVER GROUP prod_fg AS REPLICA OF myorg.prod_us.prod_fg;
```

Fail over gracefully from the DR account:

```sql
ALTER FAILOVER GROUP prod_fg SUSPEND;

SELECT phase_name, start_time, job_uuid
FROM TABLE(INFORMATION_SCHEMA.REPLICATION_GROUP_REFRESH_HISTORY('prod_fg'))
WHERE phase_name <> 'COMPLETED' AND phase_name <> 'CANCELED';  -- expect no rows

ALTER FAILOVER GROUP prod_fg PRIMARY;
```

Afterwards, in each remaining target account with a secondary:

```sql
ALTER FAILOVER GROUP prod_fg RESUME;
```

## Best practices

- Include users, roles, integrations, and network policies so authentication and access work immediately after promotion.
- Pair failover groups with Client Redirect connections and fail both over together.
- Script and rehearse the full sequence, including pipeline restarts, not just the `PRIMARY` command.
- Monitor refresh lag per group and alert when it exceeds your RPO target.
- Keep the FAILOVER privilege restricted to an on-call DR role.

## Common pitfalls

- Attempting promotion during a refresh and losing time under pressure; know the suspend/cancel procedure in advance.
- Replicating databases but not roles or integrations, so the promoted account is unusable for applications.
- Forgetting to resume scheduled refreshes on secondaries after failover.
- Assuming zero data loss; changes after the last completed refresh are not in the secondary.

## Learn more

- [Failing over account objects](https://docs.snowflake.com/en/user-guide/account-replication-failover-failback)
- [Introduction to replication and failover across multiple accounts](https://docs.snowflake.com/en/user-guide/account-replication-intro)
- [ALTER FAILOVER GROUP](https://docs.snowflake.com/en/sql-reference/sql/alter-failover-group)

## Knowledge check

### During a partial outage, ALTER FAILOVER GROUP prod_fg PRIMARY fails because the group is being refreshed. The refresh is in SECONDARY_DOWNLOADING_DATA. What is the safest action?
- [ ] Run SUSPEND IMMEDIATE and promote right away
- [x] Let the refresh finish (or suspend future refreshes and wait), then promote
- [ ] Drop the secondary group and recreate it
- [ ] Promote a different, unrelated group instead
> Cancelling during the downloading phases can leave the target inconsistent; allowing the phase to complete keeps replicas consistent before promotion.

### An application team says the DR account was "missing logins and the service account role" after a test failover, although all databases were present. What design fix addresses this?
- [ ] Increase the replication schedule frequency
- [ ] Use a replication group instead
- [x] Add USERS, ROLES, and relevant INTEGRATIONS to the failover group's OBJECT_TYPES
- [ ] Clone the roles manually after failover
> Failover groups can replicate account objects such as users, roles, and security integrations; without them the promoted account cannot authenticate or authorize workloads.

### A failover group refreshes every 15 minutes and refreshes typically take 5 minutes. What is a realistic worst-case data loss on an unplanned failover?
- [ ] Zero, because replication is synchronous
- [ ] Exactly 5 minutes
- [x] Roughly 20 minutes of changes, the interval plus refresh duration
- [ ] 24 hours, the default Time Travel period
> Replication is asynchronous; a secondary only reflects the last completed refresh, so loss is bounded by schedule interval plus refresh time.
