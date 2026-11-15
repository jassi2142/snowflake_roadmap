# Cloud Platforms & Regions

Every Snowflake account is hosted on one cloud platform (Amazon Web Services, Microsoft Azure, or Google Cloud) in one specific geographic region. This choice affects where your data physically lives, which features are available, how much you pay, and how fast data moves to and from your other systems.

## How it works

When an account is created, you choose two things:

- **Cloud platform**: AWS, Azure, or Google Cloud. Snowflake runs the same service on all three, so SQL, tools, and most features behave the same way. Snowflake manages the cloud infrastructure; you do not need your own account with that provider just to use Snowflake.
- **Region**: a geographic location run by that provider, such as a US, European, or Asia Pacific region. Your account's storage and compute stay in that region.

Key points about regions:

- **One account, one region.** An account cannot span regions. An organization can, however, have multiple accounts in different regions and on different clouds.
- **Pricing varies.** The cost of credits and storage depends on edition, region, and pricing model.
- **Feature availability can vary.** Some features or preview releases reach certain regions or clouds first. Check the documentation for a feature before you depend on it.
- **Data transfer.** Moving data out of a region or to another cloud (for example, unloading to a bucket in another region, or replicating to another account) can incur data transfer charges. Loading data from cloud storage in the same region is usually the cheapest and fastest option.
- **Cross-region and cross-cloud work.** Database replication, failover (Business Critical and higher), and listings with cross-cloud auto-fulfillment let you share or protect data across regions and clouds.
- **Government regions.** Snowflake offers dedicated regions for regulated public-sector workloads, such as FedRAMP. These have specific edition requirements.

## Example

These context functions show where your current account is hosted:

```sql
SELECT CURRENT_REGION()       AS region,
       CURRENT_ACCOUNT()      AS account_locator,
       CURRENT_ORGANIZATION_NAME() AS org_name;
```

This command lists the regions available to your organization for creating or replicating accounts:

```sql
SHOW REGIONS;
```

## Best practices

- Choose the region closest to your data sources and users to reduce latency and data transfer costs.
- Choose the cloud where your data lake and applications already live. Same-cloud, same-region loading avoids egress charges.
- Check data residency requirements (for example, data must stay in the EU) before you create the account.
- Plan a secondary region early if you need disaster recovery.

## Common pitfalls

- Creating a trial in a random region and then finding that your S3 or Blob data sits elsewhere, which causes slow, costly loads.
- Assuming a newly announced feature is available in every region on day one.
- Forgetting that replication and cross-region unloads generate data transfer charges.

## Learn more

- [Supported cloud regions](https://docs.snowflake.com/en/user-guide/intro-regions)

## Knowledge check

### Your raw data is in an Amazon S3 bucket in a European AWS region. Where should you create your Snowflake account to load it most efficiently?
- [ ] On Azure, in a US region
- [x] On AWS, in the same European region
- [ ] On Google Cloud, in any region
- [ ] The region does not affect loading
> Same cloud and same region keeps data transfer fast and avoids cross-region egress charges.

### A company needs accounts in both a US region and an EU region. How is this done?
- [ ] One account can be configured to span both regions
- [x] Create separate accounts in each region within the same organization
- [ ] Set a session parameter to switch regions
- [ ] It is not possible
> Each account lives in a single region. Organizations can hold multiple accounts across regions and clouds.

### Which statement about features across clouds and regions is correct?
- [ ] Every feature always launches in every region at the same time
- [x] Most features behave the same across clouds, but availability can differ by region or cloud
- [ ] SQL syntax is different on each cloud
- [ ] Only AWS supports data sharing
> Snowflake provides a consistent service across clouds, but some features roll out to specific regions or clouds first.
