# Snowflake Editions

Snowflake offers four editions: Standard, Enterprise, Business Critical, and Virtual Private Snowflake (VPS). Each one adds features or higher levels of service on top of the one below it. Your edition decides which features you can use, and together with your region and pricing model it sets your per-credit and storage costs.

## How it works

Each edition builds on the one below it:

- **Standard** is the entry-level edition, with full access to Snowflake's standard features. It includes virtual warehouses, Time Travel of up to 1 day, Fail-safe, encryption of all data, SSO, MFA, network policies, Snowpipe, streams and tasks, dynamic tables, data sharing, and Snowpark.
- **Enterprise** adds features for large organizations, including:
  - Extended Time Travel of up to 90 days
  - Multi-cluster virtual warehouses
  - Materialized views
  - Search optimization and query acceleration
  - Column-level security (masking policies) and row access policies
  - The ACCESS_HISTORY view
  - Periodic rekeying of encrypted data
- **Business Critical** (formerly called Enterprise for Sensitive Data) adds stronger data protection. It includes Tri-Secret Secure (customer-managed keys), private connectivity such as AWS PrivateLink, Azure Private Link, and Google Cloud Private Service Connect, support for PHI (HIPAA and HITRUST CSF) and PCI DSS workloads, and account failover/failback for business continuity. Before you store PHI, you must sign a business associate agreement (BAA) with Snowflake.
- **VPS** includes everything in Business Critical, but runs in a completely separate Snowflake environment that shares no hardware with accounts outside the VPS. It has a dedicated metadata store and its own pool of compute resources.

Your account pricing also depends on whether it is **On Demand** (usage-based, with no long-term commitment) or **Capacity** (discounted pricing in exchange for an upfront commitment).

## Example

You can check your current edition with SQL if you have access to the ORGANIZATION_USAGE schema:

```sql
SELECT edition
FROM SNOWFLAKE.ORGANIZATION_USAGE.ACCOUNTS
WHERE account_name = CURRENT_ACCOUNT();
```

Here is a feature that needs Enterprise Edition or higher. On Standard Edition, setting retention above 1 day is not allowed.

```sql
ALTER TABLE sales SET DATA_RETENTION_TIME_IN_DAYS = 30;
```

## Best practices

- Pick the edition based on concrete requirements, such as compliance needs (HIPAA, PCI DSS), concurrency (multi-cluster), or governance (masking and row access policies).
- Remember that higher editions cost more per credit, so every workload pays the higher rate, not only the workloads that use the premium features.
- When you start a trial, choose the edition you plan to use in production so you can test the features you will actually have.

## Common pitfalls

- Designing a solution around materialized views, masking policies, or 90-day Time Travel, then deploying it on Standard Edition.
- Assuming Business Critical is required for basic encryption. All editions encrypt all data automatically.
- Forgetting that a signed BAA must be in place before you store PHI, even on Business Critical.

## Learn more

- [Snowflake editions](https://docs.snowflake.com/en/user-guide/intro-editions)

## Knowledge check

### A retailer needs masking policies on customer email columns. What is the minimum edition?
- [ ] Standard
- [x] Enterprise
- [ ] Business Critical
- [ ] Virtual Private Snowflake
> Column-level security through masking policies is available in Enterprise Edition and higher.

### A healthcare company will store PHI and needs private connectivity to Snowflake. Which edition fits with the least extra cost?
- [ ] Standard
- [ ] Enterprise
- [x] Business Critical
- [ ] Any edition, as long as data is encrypted
> Business Critical adds PHI/HIPAA support and private connectivity. A BAA must also be signed.

### What is the maximum Time Travel retention on Standard Edition?
- [x] 1 day
- [ ] 7 days
- [ ] 30 days
- [ ] 90 days
> Standard Edition supports up to 1 day of Time Travel. Extended retention of up to 90 days requires Enterprise or higher.
