# Multi-account Strategy

A Snowflake organization can contain many accounts, and deciding when to split workloads into separate accounts (by environment, region, cloud, business unit, or compliance boundary) is one of the most consequential and hardest-to-reverse platform decisions. A good strategy balances isolation and sovereignty against the overhead of replication, cross-account sharing, and duplicated administration, and it relies on organization-level tooling for visibility and governance.

## How it works

An **organization** is the container that links accounts for billing, account creation, and cross-account features. Each account is bound to a single cloud provider and region and has its own edition, users, roles, warehouses, and security parameters such as network policies and authentication policies. Mechanisms that connect accounts:

- **Organization administration**: the ORGADMIN role, or administrators in the **organization account**, create and manage accounts. The organization account is a special account for organization-wide administration.
- **ORGANIZATION_USAGE**: the `SNOWFLAKE.ORGANIZATION_USAGE` schema provides cross-account data such as metering, contracts, and accounts. In the organization account, **premium views** add organization-wide equivalents of many ACCOUNT_USAGE views (query, login, and access history, tags, policies, and more). Premium views incur additional costs based on the records processed. They are available by default only to organizations with a capacity contract, and they can take up to 24 hours to populate 365 days of history after the organization account is created. Most premium views now have typical latency under three hours.
- **Data movement**: secure data sharing works directly within the same region. Across regions or clouds, you use listings with cross-cloud auto-fulfillment, or replication and failover groups. Replication incurs data transfer and compute costs, and failover requires Business Critical Edition.
- **Identity**: users are per account, so SSO and SCIM integrations are configured per account (or managed through organization user features), not inherited automatically.

Common reasons to split accounts:

- **Environment isolation**: separate production from development and test when you need hard blast-radius boundaries, different security parameters, or stricter change control. Many organizations instead keep environments in one account, separated by database and role, to reduce overhead.
- **Region and cloud**: data residency, latency to applications, or the need for cloud-specific integrations.
- **Compliance boundaries**: workloads needing Business Critical or a different security posture can live in a dedicated account, so the whole estate does not pay for the higher edition.
- **Business unit autonomy and chargeback**: separate accounts give independent administration and clear billing. This pairs naturally with data mesh.
- **Partner and customer isolation**: reader accounts or dedicated accounts for external parties.

## Example

From the organization account (or as ORGADMIN), list accounts and compare credit consumption across the organization:

```sql
SHOW ACCOUNTS;

SELECT account_name,
       service_type,
       SUM(credits_used) AS credits_30d
FROM SNOWFLAKE.ORGANIZATION_USAGE.METERING_DAILY_HISTORY
WHERE usage_date >= DATEADD(day, -30, CURRENT_DATE())
GROUP BY account_name, service_type
ORDER BY credits_30d DESC;
```

Replicate a shared reference database to a regional account with a replication group:

```sql
-- In the source account
CREATE REPLICATION GROUP ref_data_rg
  OBJECT_TYPES = DATABASES
  ALLOWED_DATABASES = ref_db
  ALLOWED_ACCOUNTS = myorg.prod_eu
  REPLICATION_SCHEDULE = '60 MINUTE';

-- In the target account
CREATE REPLICATION GROUP ref_data_rg
  AS REPLICA OF myorg.prod_us.ref_data_rg;
```

## Best practices

- Start from the smallest set of accounts that satisfies hard requirements (residency, edition, legal isolation) and add accounts only for a documented reason. Each account multiplies administration.
- Standardize account baselines as code: network and authentication policies, SSO and SCIM, RBAC skeleton, resource monitors, budgets, and logging. Apply them to every new account automatically.
- Use a clear naming scheme such as `<bu>_<env>_<region>` and tag accounts for ownership and cost center.
- Centralize observability in the organization account using premium views, and budget for their cost.
- Prefer sharing and listings over copying data between accounts. Use replication groups where cross-region access or DR is required, and test failover regularly.
- Decide early whether development and test live in separate accounts, because changing this later means migrating objects, grants, and integrations.

## Common pitfalls

- Creating accounts per team with no baseline, which leads to inconsistent security settings across the estate.
- Assuming a share works across regions without replication or auto-fulfillment.
- Underestimating replication costs and egress for large, frequently changing databases.
- Planning on premium views for an on-demand organization without first confirming availability with Snowflake Support.
- Forgetting that users, roles, and integrations are per account, so access must be provisioned in each one.

## Learn more

- [Organization accounts](https://docs.snowflake.com/en/user-guide/organization-accounts)
- [Premium views in the organization account](https://docs.snowflake.com/en/user-guide/organization-accounts-premium-views)

## Knowledge check

### A company needs a small regulated workload to run on Business Critical Edition while the rest of the estate stays on Enterprise. What is a common approach?
- [ ] Upgrade every account to Business Critical
- [x] Place the regulated workload in a dedicated Business Critical account and share or replicate only the data it needs
- [ ] Use a separate database in the Enterprise account with stricter roles
- [ ] Use a reader account
> Edition is set per account, so isolating the regulated workload limits the higher edition to where it is needed.

### The CFO wants a single view of query and login activity across 40 accounts. Which capability provides it?
- [ ] ACCOUNT_USAGE in each account, exported nightly
- [x] Premium views in ORGANIZATION_USAGE in the organization account
- [ ] INFORMATION_SCHEMA in the primary account
- [ ] Replicating every account's SNOWFLAKE database
> Premium views in the organization account aggregate account-level history such as queries and logins across all accounts, at an additional cost.

### A provider account in AWS us-east-1 wants to give data to a business unit account in Azure West Europe. What is required?
- [ ] A direct share works across any region
- [ ] A reader account in the provider's region
- [x] Replication of the data, for example with replication groups or a listing with cross-cloud auto-fulfillment
- [ ] An external stage in both clouds
> Direct shares work within a region. Crossing regions or clouds requires the data to be replicated, either explicitly or through listing auto-fulfillment.
