# Client Redirect

Client Redirect gives applications a stable connection URL that can be repointed to a different Snowflake account, in another region or cloud, without changing client configuration. During an outage you promote a connection in the DR account and clients reconnect there using the same hostname. It is the connectivity half of a Snowflake BCDR design, complementing failover groups, which handle the data and account objects.

## How it works

Client Redirect requires **Business Critical Edition or higher** and is not available in the People's Republic of China.

**Connection objects.** Redirect is implemented with a **connection** object. Its URL has the form:

`<organization_name>-<connection_name>.snowflakecomputing.com`

The hostname does not identify an account. It resolves to whichever account currently holds the **primary connection**. Secondary connections in other accounts are linked replicas and must have the **same name** as the primary. The accounts holding primary and secondary connections must be in **different regions**. Connection names must be unique across connection and account names in the organization, and the organization name becomes part of the URL, so confirm it is acceptable before creating connections.

**Lifecycle.**

1. In the source account, `CREATE CONNECTION` and `ALTER CONNECTION ... ENABLE FAILOVER TO ACCOUNTS ...`. Only ACCOUNTADMIN can run these commands.
2. In each target account, `CREATE CONNECTION ... AS REPLICA OF <org>.<account>.<connection>`.
3. Point clients (drivers, connectors, BI tools) at the connection URL instead of an account URL.
4. On outage, in the target, `ALTER CONNECTION <name> PRIMARY`. Snowflake updates resolution so the URL lands on the new account.
5. On recovery, promote the original connection back to primary (failback).

**Private connectivity.** If the account uses private connectivity, you must create and maintain a DNS CNAME record for the connection URL yourself, and update it during failover and failback. This is a frequent gap in runbooks.

### Architectural considerations

- **Redirect is not replication.** Redirecting clients to an account that lacks current data, users, roles, network policies, or integrations produces authentication failures or stale results. Promote the matching failover groups at the same time; Snowsight's bulk failover can promote groups and connections together.
- **Application resilience.** Redirect changes where new connections land, so design applications to retry failed connections and make writes idempotent, and validate the switchover end to end with your real drivers, connection pools, and network path.
- **Monitoring.** Snowsight (Admin » Accounts » Replication » Client Redirect) shows connections and usage counts for the last 7 days; `SHOW CONNECTIONS` lists primary and secondary connections. Snowsight monitoring is not available for accounts using private connectivity.

## Example

In the source account:

```sql
CREATE CONNECTION prod_conn;

SHOW REPLICATION ACCOUNTS;

ALTER CONNECTION prod_conn
  ENABLE FAILOVER TO ACCOUNTS myorg.prod_dr;

SHOW CONNECTIONS;
```

In the DR account, create the linked secondary with the same name:

```sql
CREATE CONNECTION prod_conn
  AS REPLICA OF myorg.prod_us.prod_conn;
```

Clients use `myorg-prod_conn.snowflakecomputing.com` as their host. During an outage, in the DR account:

```sql
ALTER CONNECTION prod_conn PRIMARY;
```

After the original region recovers, in the original account:

```sql
ALTER CONNECTION prod_conn PRIMARY;
```

To decommission, drop all secondary connections first, then the primary.

## Best practices

- Create one connection per workload class (for example BI, ETL, applications) if you may need to fail them over independently.
- Make the connection URL the only Snowflake hostname in client configuration; hard-coded account URLs defeat redirect.
- Include connection promotion in the same runbook step as failover group promotion.
- Automate CNAME updates when using private connectivity, and test them in drills.
- Ensure network policies and identity provider settings in the DR account allow the same clients.

## Common pitfalls

- Naming the secondary connection differently from the primary, which fails.
- Placing primary and secondary connections in the same region.
- Redirecting before failover groups are promoted, sending users to read-only or stale objects.
- Forgetting failback, leaving production running in the DR region indefinitely.

## Learn more

- [Redirecting client connections](https://docs.snowflake.com/en/user-guide/client-redirect)
- [CREATE CONNECTION](https://docs.snowflake.com/en/sql-reference/sql/create-connection)

## Knowledge check

### After promoting the DR connection, BI users reach the DR account but get errors that their tables are read-only. What was missed?
- [ ] The connection must be recreated with a new name
- [x] The relevant failover groups were not promoted to primary in the DR account
- [ ] Client Redirect does not support BI tools
- [ ] DNS caching prevented the redirect
> Client Redirect only moves connectivity; objects remain read-only until their failover groups are promoted in the new primary account.

### Your account uses private connectivity. What additional step does Client Redirect require during failover?
- [ ] None; Snowflake updates private endpoints automatically
- [x] Create and update a DNS CNAME record for the connection URL yourself
- [ ] Disable private connectivity during the failover
- [ ] Create a new connection in the DR account
> With private connectivity, you manage the CNAME record for the connection URL and must update it when redirecting.

### Which statement about the connection URL is correct?
- [ ] It contains the account locator of the primary account
- [ ] It must be changed in every client after failover
- [x] It contains the organization and connection names and resolves to the account holding the primary connection
- [ ] It works only within one cloud provider
> The hostname is organization_name-connection_name.snowflakecomputing.com and resolves to whichever account has the primary connection, across regions and clouds.
