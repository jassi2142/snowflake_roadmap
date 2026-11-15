# Listings & Marketplace

A listing wraps a share or a Native App package with metadata - title, description, terms, sample queries, regions - so data products can be discovered and delivered at scale. Listings power the public Snowflake Marketplace, the Internal Marketplace within an organization, and private offers to specific accounts.

## How it works

A **data product** (a share or an application package) is attached to a listing. The listing then controls who can get it and how:

- **Private listings** target specific consumer accounts. They are the modern alternative to adding accounts to a share directly, and they work across regions.
- **Public listings on the Snowflake Marketplace** are discoverable by all Snowflake customers. They can be free, limited trial, or paid. Offering Marketplace listings requires a **provider profile**, and paid listings also require setting up payments.
- **Organization listings (Internal Marketplace)** publish data products to other accounts in your own organization.

Listings can be managed in Snowsight's Provider Studio or with SQL (`CREATE LISTING`, `ALTER LISTING`), where the listing content is described in a YAML **manifest**.

### Cross-Cloud Auto-Fulfillment

Direct shares only work in one region. Listings solve this with **Cross-Cloud Auto-Fulfillment**:

- Snowflake replicates the data product to a Snowflake-managed **secure share area** in each consumer region, only when needed: private listings are fulfilled after the target consumers get the listing; Marketplace listings are fulfilled when a consumer in that region gets it.
- Refresh can be interval-based (from 1 minute up to 8 days), schedule-based, or triggered on demand with `SYSTEM$TRIGGER_LISTING_REFRESH`.
- The default refresh type is object-level (`SUB_DATABASE`), which replicates only the objects in the data product. `FULL_DATABASE` is deprecated.
- There is a default 10 TB limit on data product size, which an administrator can raise.
- Providers pay the replication, storage and compute costs of auto-fulfillment. It is not available on trial accounts.
- Refresh history is available through `LISTING_REFRESH_HISTORY`, and Snowflake emails a daily summary of failed refreshes to the listing's contact address.

Consumers "get" a listing, which creates a read-only database (or installs an app) in their account. They pay for their own compute.

## Example

Create a private listing for a partner, with auto-fulfillment to their region:

```sql
USE ROLE ACCOUNTADMIN;

CREATE EXTERNAL LISTING emea_orders_listing
  SHARE emea_partner_share AS
$$
title: "EMEA Orders"
subtitle: "Daily EMEA order facts"
description: "Curated daily order data for EMEA partners."
listing_terms:
  type: "OFFLINE"
targets:
  accounts: ["PARTNERORG.PARTNERACCT"]
auto_fulfillment:
  refresh_type: "SUB_DATABASE"
  refresh_schedule: "60 MINUTE"
$$
PUBLISH = TRUE
REVIEW = FALSE;

SHOW LISTINGS;
```

Trigger a refresh after your pipeline finishes:

```sql
SELECT SYSTEM$TRIGGER_LISTING_REFRESH('LISTING', 'EMEA_ORDERS_LISTING');
```

Consumers can browse and get listings in Snowsight under Marketplace; once installed, the data appears as a normal read-only database they can grant to their roles.

## Best practices

- Use listings rather than raw shares for any external consumer - you get discovery, terms, usage metrics and cross-region delivery.
- Share curated secure views and document them with sample queries in the listing.
- Use trigger-based refresh after ETL completes so consumers never see half-loaded data.
- Keep data products lean with object-level fulfillment to control replication cost.
- Monitor consumption and refresh history to understand adoption and catch failures.

## Common pitfalls

- Expecting auto-fulfillment to be free; replication costs land on the provider.
- Adding large or unrelated objects to a data product and paying to replicate them everywhere.
- Forgetting that interval-based and schedule-based refreshes cannot run together - one overrides the other.
- Publishing to the Marketplace before setting up a provider profile.

## Learn more

- [Use listings as a provider](https://docs.snowflake.com/en/collaboration/provider-becoming)
- [Auto-fulfillment for listings](https://docs.snowflake.com/en/collaboration/provider-listings-auto-fulfillment)

## Knowledge check

### A provider in AWS us-east-1 wants to share with a consumer on Azure in Europe without managing replication. What should they use?
- [ ] A direct share with ALTER SHARE ADD ACCOUNTS
- [x] A private listing with Cross-Cloud Auto-Fulfillment
- [ ] A reader account
- [ ] A database clone
> Listings with auto-fulfillment replicate the data product to the consumer's region automatically; direct shares are single-region.

### When is a public Marketplace listing's data product replicated to a new region?
- [ ] Immediately on publish, to every region
- [x] When a consumer in that region gets the listing
- [ ] Only when the provider replicates it manually
- [ ] Once per month
> Auto-fulfillment fulfills Marketplace listings to a region on demand, after a consumer there gets the listing.

### A provider's ETL finishes at irregular times, and consumers must see data right after each load. Which refresh approach fits best?
- [ ] An 8-day interval
- [ ] FULL_DATABASE refresh
- [x] Trigger a refresh with SYSTEM$TRIGGER_LISTING_REFRESH when the pipeline completes
- [ ] Ask consumers to refresh their databases
> Trigger-based refresh lets the provider push updates exactly when new data is ready.
