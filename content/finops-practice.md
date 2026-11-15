# FinOps Operating Model (showback/chargeback, governance, KPIs, review cadence)

Tools such as budgets, tags and attribution views tell you *where* money goes; a FinOps operating model decides *who acts on it, how often, and against which targets*. On a consumption-priced platform like Snowflake, where any engineer can scale a warehouse in one statement, cost is an engineering property that needs the same ownership and feedback loops as reliability.

## How it works

A workable model has four layers.

**1. Visibility (the data foundation).** Build a curated cost mart from `METERING_DAILY_HISTORY` (billed credits including the cloud services adjustment), `WAREHOUSE_METERING_HISTORY`, `QUERY_ATTRIBUTION_HISTORY`, feature-specific serverless histories, `TABLE_STORAGE_METRICS` and `TAG_REFERENCES`. For multi-account organizations, the `ORGANIZATION_USAGE` schema adds cross-account views, including `USAGE_IN_CURRENCY_DAILY` for spend in currency. Persist daily snapshots; Account Usage keeps one year.

**2. Allocation: showback, then chargeback.**

- *Showback* reports attributed cost to owners without moving money. It builds trust in the numbers and is the right starting point.
- *Chargeback* moves cost into team budgets. It drives stronger behavior but requires attribution accurate enough to survive disputes, a published policy for shared costs (idle warehouse time, platform services, shared storage), and a stable methodology.

Most organizations run showback for at least a few cycles, measure the untagged share, and move to chargeback only when unallocated spend is small and stable.

**3. Governance and guardrails.** Preventive and detective controls:

- Tag policy enforced at provisioning (infrastructure as code, SCIM for user tags, `ALLOWED_VALUES` on tags).
- Warehouse standards: auto-suspend defaults, size ceilings per environment, multi-cluster limits.
- **Budgets** with tag-based scope for forecast-based notifications, plus custom actions where automatic response is acceptable.
- **Resource monitors** where hard warehouse credit limits are required.
- **Alerts** on anomalies such as a warehouse exceeding its trailing average.
- Change control for cost-significant features: enabling search optimization, clustering, materialized views or long Time Travel retention should be reviewed like a schema change.

**4. Optimization loop and cadence.**

- *Daily (automated)*: anomaly alerts and budget notifications routed to owning teams.
- *Weekly (engineering)*: top query patterns by attributed credits, spilling and pruning offenders, idle-heavy warehouses, new serverless spend.
- *Monthly (business)*: showback or chargeback statements, budget versus actual, unit-cost trends, a prioritized optimization backlog with owners.
- *Quarterly (leadership)*: capacity commitment planning against forecast, architectural decisions (workload isolation, table design), KPI target review.

**KPIs.** Choose metrics that reward efficiency, not just lower spend:

- *Unit cost*: credits per business unit of value (per thousand orders, per dashboard view, per pipeline run).
- *Allocation coverage*: percentage of credits attributed to an owner; untagged share should trend toward zero.
- *Idle ratio*: metered warehouse credits minus attributed query credits, divided by metered credits.
- *Forecast accuracy*: actual versus budgeted spend per team.
- *Storage efficiency*: historical bytes (Time Travel, Fail-safe, retained for clones) relative to active bytes.
- *Optimization throughput*: savings realized from backlog items per period.

## Example

A monthly KPI query for idle ratio per warehouse:

```sql
WITH metered AS (
  SELECT warehouse_name, SUM(credits_used_compute) AS metered_credits
  FROM snowflake.account_usage.warehouse_metering_history
  WHERE start_time >= DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE()))
    AND start_time <  DATE_TRUNC('month', CURRENT_DATE())
  GROUP BY warehouse_name
),
attributed AS (
  SELECT warehouse_name, SUM(credits_attributed_compute) AS query_credits
  FROM snowflake.account_usage.query_attribution_history
  WHERE start_time >= DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE()))
    AND start_time <  DATE_TRUNC('month', CURRENT_DATE())
  GROUP BY warehouse_name
)
SELECT m.warehouse_name,
       m.metered_credits,
       COALESCE(a.query_credits, 0) AS query_credits,
       1 - COALESCE(a.query_credits, 0) / NULLIF(m.metered_credits, 0) AS idle_ratio
FROM metered m
LEFT JOIN attributed a USING (warehouse_name)
ORDER BY m.metered_credits DESC;
```

Allocation coverage: share of warehouse credits on tagged warehouses:

```sql
SELECT SUM(IFF(tr.tag_value IS NULL, 0, wmh.credits_used_compute))
         / NULLIF(SUM(wmh.credits_used_compute), 0) AS tagged_share
FROM snowflake.account_usage.warehouse_metering_history wmh
LEFT JOIN snowflake.account_usage.tag_references tr
  ON tr.object_id = wmh.warehouse_id
 AND tr.domain = 'WAREHOUSE'
 AND tr.tag_name = 'COST_CENTER'
WHERE wmh.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP());
```

## Best practices

- Give every warehouse, database and service user a named owner, recorded as a tag.
- Publish the allocation methodology and change it only at period boundaries.
- Track unit cost alongside total spend so growth in value is not mistaken for waste.
- Route alerts to the owning team, not only to a central platform team.
- Treat optimization items like engineering work: estimate savings, assign owners, verify results with the same query hash before and after.

## Common pitfalls

- Starting with chargeback before attribution is trusted, leading to disputes instead of action.
- Optimizing for lowest spend and degrading SLAs; KPIs must balance cost with performance.
- Relying on monthly invoices only; by then the money is spent.
- Centralizing all optimization in one team, which then becomes a bottleneck and lacks workload context.
- Ignoring serverless and storage costs because dashboards focus on warehouses.

## Learn more

- [Attributing cost](https://docs.snowflake.com/en/user-guide/cost-attributing)
- [Monitor credit usage with budgets](https://docs.snowflake.com/en/user-guide/budgets)
- [Exploring compute cost](https://docs.snowflake.com/en/user-guide/cost-exploring-compute)

## Knowledge check

### A company wants to start charging teams for Snowflake usage, but 35% of credits are on untagged or shared resources. What is the recommended next step?
- [ ] Launch chargeback immediately and split untagged cost evenly
- [x] Run showback while enforcing tagging at provisioning, and move to chargeback once unallocated spend is small and stable
- [ ] Charge all untagged cost to the platform team permanently
- [ ] Stop using shared warehouses entirely
> Chargeback requires trusted attribution; showback builds confidence and exposes tagging gaps while governance reduces the unallocated share.

### Total Snowflake spend grew 40% year over year while orders processed grew 80%. Which KPI best shows whether efficiency improved?
- [ ] Total credits per month
- [x] Unit cost, such as credits per thousand orders
- [ ] Number of warehouses
- [ ] Average warehouse size
> Unit cost normalizes spend by business volume; here cost per order fell, indicating better efficiency despite higher total spend.

### Which cadence assignment fits a mature FinOps operating model?
- [ ] Review anomalies quarterly and commitments daily
- [x] Automated daily anomaly and budget alerts, weekly engineering review of top cost drivers, monthly showback or chargeback, quarterly capacity and KPI planning
- [ ] One annual review of the invoice
- [ ] Weekly chargeback statements with daily methodology changes
> Fast feedback belongs in automated alerts, technical optimization in a weekly loop, financial reporting monthly, and strategic commitments and targets quarterly.
