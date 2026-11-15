# Create a Trial Account

A Snowflake trial account lets you try the platform's features at no cost and with no contract. It is the fastest way to start learning: you get a real account with sample data, and you can practice everything in this roadmap.

## How it works

**Signing up**

You sign up with the self-service form on the Snowflake website. You need only a valid email address; no payment information is required. During sign-up you choose:

- **Cloud platform**: AWS, Azure, or Google Cloud
- **Region**: where the account will be hosted
- **Edition**: for example, Standard or Enterprise

These choices affect how quickly you use up your free balance. For example, some Enterprise Edition features use additional credits.

**How long it lasts**

The trial runs for **30 days from sign-up, or until you use up the free usage balance**, whichever comes first. Credits are used by running virtual warehouses and by serverless features (including AI features). Storage costs are also deducted from the balance at the standard on-demand rate for your cloud and region.

When the trial ends, the account is **suspended**. You can still log in, but you cannot run warehouses, load data, or run queries. To reactivate it, add a credit card and upgrade to a paid account. If you do not upgrade before the trial ends, any unused free balance expires.

**Tracking and upgrading**

Users with the ACCOUNTADMIN role can see the remaining balance in a tile in Snowsight's left navigation. To upgrade, add a credit card under **Admin » Billing**, then select **Upgrade**. Adding a card alone does not upgrade the account. Any remaining free credits still apply after you upgrade.

**Limitations**

Trial accounts do not support some features, including external network access, hybrid tables, outbound private connectivity, Snowflake Openflow, and Duo for MFA. AI features are disabled by default on self-service trials until you add a credit card. To cancel a trial, contact Snowflake Support; it cannot be done through the web interface.

## Example

After your first login, create a small, cost-safe warehouse and run a query against the shared sample data:

```sql
USE ROLE ACCOUNTADMIN;

CREATE WAREHOUSE IF NOT EXISTS trial_wh
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

USE WAREHOUSE trial_wh;

SELECT n_name, COUNT(*) AS customers
FROM snowflake_sample_data.tpch_sf1.customer c
JOIN snowflake_sample_data.tpch_sf1.nation n ON c.c_nationkey = n.n_nationkey
GROUP BY n_name
ORDER BY customers DESC;
```

## Best practices

- Choose the cloud and region where your practice data lives, and the edition you expect to use later.
- Check the warehouse size before you start or resume it. Small or Medium is usually enough for evaluation.
- Keep auto-suspend on, with a short timeout of 5 minutes or less.
- Create a non-ACCOUNTADMIN user and role for everyday work, to practice good security habits.

## Common pitfalls

- Leaving a large warehouse running overnight and using up the free balance in a few days.
- Expecting to export or recover work after the trial is suspended without upgrading.
- Trying hybrid tables or external network access on a trial and assuming the feature is broken.

## Learn more

- [Trial accounts](https://docs.snowflake.com/en/user-guide/admin-trial-account)
- [Snowflake in 20 minutes](https://docs.snowflake.com/en/user-guide/tutorials/snowflake-in-20minutes)

## Knowledge check

### When does a Snowflake trial end?
- [ ] After exactly 60 days
- [x] After 30 days or when the free usage balance is used up, whichever comes first
- [ ] Only when you cancel it
- [ ] After 30 days, no matter how much you use
> The trial lasts 30 days from sign-up or until the free balance is depleted, whichever happens first.

### You add a credit card to your trial account. What is the result?
- [ ] The account is upgraded to paid immediately
- [x] The card is saved, and you still need to select Upgrade to convert the account
- [ ] The trial is extended by 30 days
- [ ] Your free credits are removed
> Adding a card does not upgrade the account by itself. It does enable AI features on self-service trials.

### Which habit best protects your free credits?
- [ ] Use the largest warehouse so queries finish faster
- [ ] Turn off auto-suspend so warehouses start quickly
- [x] Use small warehouses with a short auto-suspend timeout
- [ ] Run all work under ACCOUNTADMIN
> Credits are used while warehouses run. Small sizes and short auto-suspend minimize consumption.
