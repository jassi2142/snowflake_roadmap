# BCDR Strategy & Testing

Business continuity and disaster recovery (BCDR) in Snowflake is a design that combines Time Travel, backups, replication and failover groups, Client Redirect, and rehearsed runbooks. The architect maps each failure mode to a control, sets recovery point and recovery time objectives (RPO and RTO) per workload, and proves them with regular drills.

## How it works

### Map failure modes to controls

| Failure mode | Primary control | Notes |
| --- | --- | --- |
| Bad DML, accidental drop | Time Travel, UNDROP, clone with AT/BEFORE | Self-service; up to 90 days on Enterprise+ for permanent objects |
| Data deleted beyond Time Travel | Fail-safe | 7 days, Snowflake Support only, best effort, hours to days |
| Ransomware, insider deletion, regulatory immutability | Backups (backup sets and policies) | Retention lock and legal hold require Business Critical |
| Regional or cloud outage | Failover groups plus Client Redirect | Business Critical; asynchronous replication |
| Read scale-out, distribution | Replication groups | Database and share replication on all editions |

Time Travel and replication do not protect against a privileged actor who drops data and lowers retention; a replicated drop replicates. Backups with a **retention lock** cannot be deleted before expiry even by ACCOUNTADMIN or ORGADMIN, which is why they belong in a cyber-resilience design.

### RPO and RTO

- **RPO (data loss).** Replication is asynchronous. A secondary reflects the last *completed* refresh, so worst-case loss is approximately the `REPLICATION_SCHEDULE` interval plus refresh duration. Only one refresh per group runs at a time, so long refreshes stretch the effective interval. Measure actual lag from `REPLICATION_GROUP_REFRESH_HISTORY` rather than assuming the schedule.
- **RTO (downtime).** Driven by how fast you can decide, promote failover groups (`ALTER FAILOVER GROUP ... PRIMARY`), promote connections (`ALTER CONNECTION ... PRIMARY`), update CNAMEs for private connectivity, resume warehouses, and restart pipelines. Most RTO lives in people and pipelines, not in the promote command.
- **Tiering.** Put critical databases in their own failover group with a tight schedule, and less critical ones in groups with cheaper schedules. Cost scales with change volume, transfer distance, and frequency.

### What is and is not replicated

Plan explicitly for gaps. Temporary tables, external tables, hybrid tables, event tables, and temporary stages are not replicated; databases created from inbound shares cannot be replicated; stages and pipes are replicated only in replication or failover groups, not plain database replication. Warehouses arrive suspended. Without replicating users, roles, integrations, and network policies (Business Critical), the DR account cannot authenticate or authorize workloads. Anything outside Snowflake, such as external storage, orchestration, identity provider configuration, and partner tools, needs its own DR plan.

### Drills

A credible plan is tested. A typical drill: suspend refreshes, verify none are in progress, promote failover groups and connections (Snowsight bulk failover helps), run smoke tests and pipeline restarts, record timings, then fail back and resume refreshes on all secondaries. Snowflake can also quiesce a primary failover group for controlled exercises. Afterwards, compare measured RPO and RTO against targets and update the runbook.

## Example

A tiered layout: account objects and tier-1 data every 10 minutes, tier-2 data hourly.

```sql
CREATE FAILOVER GROUP tier1_fg
  OBJECT_TYPES = USERS, ROLES, WAREHOUSES, INTEGRATIONS, NETWORK POLICIES, DATABASES
  ALLOWED_DATABASES = orders_db, governance_db
  ALLOWED_INTEGRATION_TYPES = SECURITY INTEGRATIONS
  ALLOWED_ACCOUNTS = myorg.prod_dr
  REPLICATION_SCHEDULE = '10 MINUTE';

CREATE FAILOVER GROUP tier2_fg
  OBJECT_TYPES = DATABASES
  ALLOWED_DATABASES = marketing_db
  ALLOWED_ACCOUNTS = myorg.prod_dr
  REPLICATION_SCHEDULE = 'USING CRON 0 * * * * UTC';
```

Measure recent refresh durations in the DR account to estimate real RPO:

```sql
SELECT start_time, end_time,
       DATEDIFF('second', start_time, end_time) AS refresh_seconds
FROM TABLE(INFORMATION_SCHEMA.REPLICATION_GROUP_REFRESH_HISTORY('tier1_fg'))
ORDER BY start_time DESC
LIMIT 20;
```

Immutable hourly backups for a critical table, retained 90 days:

```sql
CREATE BACKUP POLICY governance.policies.hourly_backup_policy
  SCHEDULE = '60 MINUTE'
  EXPIRE_AFTER_DAYS = 90;

CREATE BACKUP SET governance.backups.orders_backups
  FOR TABLE orders_db.public.orders
  WITH BACKUP POLICY governance.policies.hourly_backup_policy;

-- Restore a specific backup to a new table
CREATE TABLE orders_db.public.orders_restored
  FROM BACKUP SET governance.backups.orders_backups IDENTIFIER '<backup_id>';
```

## Best practices

- Define RPO and RTO per workload, then derive group boundaries and schedules from them.
- Replicate account objects, not just data, and pair every failover group with a Client Redirect plan.
- Use locked backups for cyber resilience; replication alone propagates destructive changes.
- Drill at least on a regular cadence, time every step, and include pipeline restart and failback.

## Common pitfalls

- Equating "replication enabled" with "DR ready" without testing authentication, network policies, and pipelines.
- Ignoring non-replicated objects such as external tables until the first real failover.
- Promoting during an in-flight refresh and cancelling in an unsafe phase.
- Forgetting to resume refreshes after failover, silently breaking protection for the next incident.

## Learn more

- [Introduction to replication and failover across multiple accounts](https://docs.snowflake.com/en/user-guide/account-replication-intro)
- [Failing over account objects](https://docs.snowflake.com/en/user-guide/account-replication-failover-failback)
- [Backups for disaster recovery and immutable storage](https://docs.snowflake.com/en/user-guide/backups)

## Knowledge check

### An attacker with ACCOUNTADMIN drops production databases and sets retention to 0. Failover groups replicate every 10 minutes. Which control most reliably preserves recoverable data?
- [ ] The DR secondary, because drops are not replicated
- [ ] Fail-safe, because it is self-service
- [x] Backups protected by a retention lock
- [ ] Client Redirect to the DR account
> Replication propagates destructive changes, Fail-safe is best effort and Support-only, while locked backups cannot be deleted before expiry even by ACCOUNTADMIN.

### Leadership asks for a 5-minute RPO. Refreshes for the critical group take about 8 minutes. What is the honest assessment?
- [ ] Set REPLICATION_SCHEDULE to '1 MINUTE' and the RPO is met
- [x] The RPO cannot be met as designed; reduce group scope or change volume, or accept a higher RPO
- [ ] Use a replication group instead of a failover group
- [ ] Increase Time Travel retention
> Only one refresh runs at a time, so effective lag is at least the refresh duration; meeting a lower RPO requires smaller or faster refreshes.

### A DR drill promoted all failover groups and connections successfully, but ingestion stopped. What should the runbook add?
- [ ] Replicating the SNOWFLAKE database
- [x] Steps to restart pipelines in the new primary, such as reopening Snowpipe Streaming channels and resetting connector offsets
- [ ] A second Client Redirect connection with a different name
- [ ] Converting tables to transient
> Failover moves data and objects, but ingestion and transformation pipelines must be restarted and reconciled in the newly promoted account.
