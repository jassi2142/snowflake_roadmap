# Replication Groups

A replication group is a named set of objects in a source account that Snowflake replicates as a unit, with point-in-time consistency, to one or more target accounts in the same organization. Targets receive read-only secondary copies that are refreshed on a schedule. Replication groups underpin cross-region and cross-cloud data distribution, read scale-out, migrations, and, combined with failover groups, disaster recovery.

## How it works

**Edition matrix.** Database and share replication are available on all editions. Replicating other account objects (users, roles, warehouses, resource monitors, integrations, network policies, account parameters, and so on) and failover/failback require **Business Critical Edition or higher**. Replication works across regions and cloud platforms, but not in the People's Republic of China.

**Topology.** An organization administrator first enables replication for the participating accounts. You then create a **primary** group in the source account, listing:

- `OBJECT_TYPES`: which kinds of objects are included (for example `DATABASES, SHARES`).
- `ALLOWED_DATABASES`, `ALLOWED_SHARES`, `ALLOWED_INTEGRATION_TYPES`: which specific objects.
- `ALLOWED_ACCOUNTS`: which target accounts may hold replicas.
- `REPLICATION_SCHEDULE`: an interval (`'10 MINUTE'`) or cron expression.

In each target, you create a **secondary** group `AS REPLICA OF` the primary. Snowflake runs an initial refresh automatically; subsequent refreshes follow the schedule or run manually with `ALTER REPLICATION GROUP ... REFRESH`.

**Consistency and scheduling semantics.** All objects in a group are refreshed together, so a secondary is a consistent snapshot of the group at one point in time. That is the main reason to group interdependent databases together: cross-database references (for example, a view over a table in another database, or a policy in a central governance database) are only consistent if both sides are in the same group. Only one refresh per group runs at a time; if a refresh overruns, the next starts when it completes. Interval schedules are measured from the start of the previous refresh.

**Refreshes are incremental** after the initial copy, but cost depends on change volume: you pay for data transfer between regions or clouds, compute used by the refresh, and storage in each target.

### What is and is not replicated

- Replicated database objects include permanent and transient tables, dynamic tables, views, sequences, tags, masking and row access policies, and (in replication or failover groups, not plain database replication) stages and pipes.
- **Not replicated:** temporary tables, external tables, hybrid tables, event tables, and temporary stages.
- Databases created from shares (inbound shares) cannot be replicated.
- Warehouses replicate in a suspended state; the REPLICATE and FAILOVER privileges themselves are not replicated.
- If roles are not replicated, ownership of new objects in the target goes to GLOBALORGADMIN.
- Streams on unsupported or dropped sources cause refreshes to fail; append-only streams are not supported on replicated sources.

**Edition guardrails.** Replicating from a Business Critical account to a lower-edition account is blocked by default to protect sensitive data; `IGNORE EDITION CHECK` overrides this deliberately.

## Example

In the source account, create a group that replicates two related databases and a share every 10 minutes:

```sql
CREATE REPLICATION GROUP sales_rg
  OBJECT_TYPES = DATABASES, SHARES
  ALLOWED_DATABASES = sales_db, governance_db
  ALLOWED_SHARES = sales_share
  ALLOWED_ACCOUNTS = myorg.analytics_eu
  REPLICATION_SCHEDULE = '10 MINUTE';
```

In the target account, create the secondary group (the initial refresh starts automatically), then trigger an extra refresh if needed:

```sql
CREATE REPLICATION GROUP sales_rg
  AS REPLICA OF myorg.prod_us.sales_rg;

ALTER REPLICATION GROUP sales_rg REFRESH;
```

Monitor refresh history and phases in the target:

```sql
SELECT phase_name, start_time, end_time, job_uuid
FROM TABLE(INFORMATION_SCHEMA.REPLICATION_GROUP_REFRESH_HISTORY('sales_rg'))
ORDER BY start_time DESC;
```

## Best practices

- Group databases that reference each other so refreshes are consistent and avoid dangling references.
- Split objects with different freshness needs into separate groups with different schedules, rather than one large group on the tightest schedule.
- Always set `REPLICATION_SCHEDULE`; manual refreshes are easy to forget.
- Track replication cost (transfer, compute, storage) per group and tune schedules to business RPO, not to "as fast as possible".
- Keep the refresh role's privileges stable; scheduled refreshes run as the group owner and fail if it lacks privileges.

## Common pitfalls

- Expecting writable replicas; secondary objects in a replication group are read-only.
- Relying on database replication for stages and pipes, which are supported only through replication or failover groups.
- Leaving external tables or hybrid tables in replicated databases and assuming they will exist in the target.
- Schedules shorter than refresh duration, which quietly turns into back-to-back refreshes and higher cost.

## Learn more

- [Introduction to replication and failover across multiple accounts](https://docs.snowflake.com/en/user-guide/account-replication-intro)
- [Replication considerations](https://docs.snowflake.com/en/user-guide/account-replication-considerations)

## Knowledge check

### A reporting database contains secure views over tables in a separate raw database. Both must be available in an EU account. How should you structure replication?
- [ ] Two replication groups with independent schedules
- [x] One replication group containing both databases
- [ ] Replicate only the reporting database; views resolve to the source account
- [ ] Use a share instead of replication
> Objects in one group refresh together with point-in-time consistency, which keeps cross-database references valid in the target.

### Your organization is on Enterprise Edition. Which can you replicate with a replication group?
- [ ] Users, roles, and warehouses
- [ ] Network policies and integrations
- [x] Databases and shares
- [ ] Everything except users
> Database and share replication are available on all editions; other account objects require Business Critical Edition or higher.

### A group is scheduled every 5 minutes, but each refresh takes 12 minutes because of heavy daily loads. What actually happens?
- [ ] Refreshes run in parallel every 5 minutes
- [ ] The schedule is rejected
- [x] Only one refresh runs at a time; the next starts when the current one finishes
- [ ] The group fails over automatically
> Snowflake guarantees a single executing refresh per group and delays the next until the current completes, so effective lag is driven by refresh duration.
