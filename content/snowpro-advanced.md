# SnowPro Advanced

SnowPro Advanced is Snowflake's family of role-based certifications for experienced practitioners, building on SnowPro Core. Tracks target specific roles, such as architects, data engineers, data analysts, data scientists, and administrators, and test the ability to design and operate Snowflake solutions under real-world constraints rather than recall individual features.

## How it works

The set of available tracks, prerequisites, exam versions, question counts, durations, passing scores, and fees change over time. Confirm all of these on the official Snowflake certification site and the exam guide for your chosen track before you plan your study; do not rely on figures from third-party sources.

What distinguishes the advanced level is the style of thinking it rewards. Expect to reason about trade-offs among several valid options:

- **Architecture**: single versus multiple accounts, replication and failover across regions and clouds, data sharing versus replication, edition-dependent capabilities (for example, Business Critical for private connectivity and higher compliance requirements), and how to design for cost, security, and resilience together.
- **Data engineering**: choosing among COPY, Snowpipe, and Snowpipe Streaming for ingestion; streams and tasks versus dynamic tables for transformation; idempotent MERGE patterns; handling late data; Snowpark and UDFs; external access integrations; and monitoring pipelines.
- **Performance and cost**: reading Query Profile, pruning and clustering decisions, search optimization, query acceleration, warehouse sizing and multi-cluster policies, and resource monitors and budgets.
- **Security and governance**: role hierarchy design, secondary roles, masking and row access policies, tag-based policies, object tagging and classification, network policies, and authentication methods for service users.
- **Operations**: CI/CD, environment strategy, zero-copy cloning for testing, Time Travel recovery, and observability through Account Usage views.

## Example

Scenario practice is the most effective preparation. For example, compare two transformation designs for the same requirement and measure them:

```sql
-- Option A: declarative pipeline
CREATE OR REPLACE DYNAMIC TABLE dt_customer_revenue
  TARGET_LAG = '15 minutes'
  WAREHOUSE = transform_wh
  REFRESH_MODE = INCREMENTAL
AS
  SELECT customer_id, SUM(amount) AS revenue
  FROM orders
  GROUP BY customer_id;

-- Option B: imperative pipeline
CREATE OR REPLACE STREAM orders_stream ON TABLE orders;

CREATE OR REPLACE TASK apply_order_changes
  SCHEDULE = '15 MINUTES'
  WHEN SYSTEM$STREAM_HAS_DATA('orders_stream')
AS
  CALL apply_customer_revenue_changes();

-- Compare cost afterwards
SELECT warehouse_name, SUM(credits_used) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time > DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY warehouse_name;
```

Then write down why you would choose each option: freshness needs, procedural logic, operational ownership, and cost.

## Best practices

- Pass SnowPro Core first and gain real project experience in the track's domain.
- Study from the official exam guide for your specific track and map each objective to documentation and hands-on labs.
- Practice scenario reasoning: for each feature, know when not to use it.
- Track edition requirements and default values, since design questions often hinge on them.
- Review Account Usage views; many operational questions assume you know where to find evidence.

## Common pitfalls

- Treating advanced exams like Core and memorizing facts instead of trade-offs.
- Studying the wrong track's objectives.
- Relying on outdated material when features such as dynamic tables, Snowpark, and external access evolve quickly.
- Ignoring cost implications in design answers.

## Learn more

- [Snowflake certifications](https://learn.snowflake.com/en/certifications/)

## Knowledge check

### A global company needs its reporting database to remain available if its primary cloud region has an outage. Which design addresses this?
- [ ] Zero-copy clone the database into another schema
- [ ] Increase Time Travel retention to 90 days
- [x] Replicate the database to an account in another region and configure failover
- [ ] Use a multi-cluster warehouse
> Cross-region replication with failover provides availability during a regional outage; clones and Time Travel stay within the same account.

### A pipeline needs 5-minute freshness for an aggregate and also needs to send a webhook when certain rows change. What is a sound design?
- [ ] One dynamic table that calls an external function
- [x] A dynamic table for the aggregate, plus a stream and task calling a procedure with an external access integration for the webhook
- [ ] A materialized view with a task that polls it every minute
- [ ] Snowpipe with a 5-minute schedule
> Dynamic tables handle declarative refresh but cannot call procedures; side effects belong in a stream-driven task using external access.

### Queries on a 20 TB table filter by `event_date` but scan most micro-partitions. What should you investigate first?
- [ ] Increasing warehouse size
- [x] Pruning effectiveness and whether a clustering key on event_date would improve it
- [ ] Enabling the result cache
- [ ] Switching to a secure view
> Poor pruning means data is not well clustered on the filter column; a clustering key can reduce partitions scanned.
