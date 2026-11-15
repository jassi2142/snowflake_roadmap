# Secure Data Sharing

Secure Data Sharing lets one Snowflake account (the provider) give other accounts (consumers) live, read-only access to selected objects without copying or moving data. Consumers always query the current data, and providers keep full control over what is shared and with whom.

## How it works

A **share** is a named object that records what is shared and which accounts can see it. No data is copied: sharing works through Snowflake's services layer and metadata, so shared data uses **no storage in the consumer account**. Consumers pay only for the compute (warehouses) they use to query it.

You can share databases, tables, dynamic tables, external tables, Iceberg tables, secure views, secure materialized views, semantic views, secure UDFs, Cortex Search services, and certain model types, among others. Shared objects are always **read-only** for the consumer.

Providers add objects to a share in one of two ways:

1. **Database roles (recommended)** - grant privileges to database roles, then grant those roles to the share. Consumers can map each database role to different account roles.
2. **Direct grants** - grant `USAGE` on the database and schema and `SELECT` on objects directly to the share. Consumers then grant `IMPORTED PRIVILEGES` on the whole database to their roles.

Regular views must be made secure before they can be shared (`CREATE SECURE VIEW` or `ALTER VIEW ... SET SECURE`), so the consumer cannot see the view definition or bypass its filters. To share data from several databases through one share, grant `REFERENCE_USAGE` on the other databases to the share.

Direct shares reach accounts in the **same region**. For other regions or clouds, replicate the data first, or use a listing with Cross-Cloud Auto-Fulfillment. For consumers without a Snowflake account, providers can create reader accounts.

## Example

Provider: share a curated secure view with a partner account.

```sql
USE ROLE ACCOUNTADMIN;

CREATE SECURE VIEW sales.curated.partner_orders AS
  SELECT order_id, order_date, region, amount
  FROM sales.raw.orders
  WHERE region = 'EMEA';

CREATE DATABASE ROLE sales.partner_reader;
GRANT USAGE ON SCHEMA sales.curated TO DATABASE ROLE sales.partner_reader;
GRANT SELECT ON VIEW sales.curated.partner_orders TO DATABASE ROLE sales.partner_reader;

CREATE SHARE emea_partner_share;
GRANT USAGE ON DATABASE sales TO SHARE emea_partner_share;
GRANT DATABASE ROLE sales.partner_reader TO SHARE emea_partner_share;

ALTER SHARE emea_partner_share ADD ACCOUNTS = partnerorg.partneracct;
```

Consumer: create a database from the share and grant access.

```sql
SHOW SHARES;
CREATE DATABASE emea_sales FROM SHARE providerorg.provideracct.emea_partner_share;
GRANT DATABASE ROLE emea_sales.partner_reader TO ROLE analyst;

SELECT region, SUM(amount) FROM emea_sales.curated.partner_orders GROUP BY region;
```

## Best practices

- Share secure views rather than base tables when you need to filter rows or hide columns.
- Use database roles so consumers can apply their own role-based access to shared objects.
- Use listings instead of raw shares when you need discovery, usage metrics, or cross-region delivery.
- Review `SHOW GRANTS TO SHARE` regularly and remove accounts that no longer need access.
- Consider row access and masking policies for consumer-specific restrictions.

## Common pitfalls

- Trying to share a regular (non-secure) view.
- Expecting consumers to modify shared tables; shared data is read-only.
- Trying to add a consumer in another region directly to a share without replication or auto-fulfillment.
- Granting `IMPORTED PRIVILEGES` and expecting per-object control; that grant covers the whole shared database.

## Learn more

- [About Secure Data Sharing](https://docs.snowflake.com/en/user-guide/data-sharing-intro)
- [Share data securely across regions and cloud platforms](https://docs.snowflake.com/en/user-guide/secure-data-sharing-across-regions-platforms)

## Knowledge check

### A consumer queries a 5 TB shared table every day. Who pays for what?
- [ ] The consumer pays storage and compute
- [x] The provider pays storage; the consumer pays only for the compute it uses to query
- [ ] The provider pays storage and the consumer's compute
- [ ] Neither, sharing is free
> No data is copied to the consumer, so storage stays with the provider; consumers pay for their own warehouses.

### A provider wants to share only EMEA rows from a table. What is the standard approach?
- [ ] Share the table and ask the consumer to filter
- [x] Create a secure view with the filter and share the view
- [ ] Clone the table into the consumer account
- [ ] Share a regular view
> Secure views enforce the filter and hide the definition; regular views cannot be shared.

### A partner account is in a different cloud region. Why does ALTER SHARE ... ADD ACCOUNTS not work for them?
- [ ] Shares are limited to five consumers
- [x] Direct shares work within a region; cross-region requires replication or a listing with auto-fulfillment
- [ ] The partner must be a reader account
- [ ] The share needs a secure UDF
> Cross-region and cross-cloud sharing relies on replication, which listings can automate with Cross-Cloud Auto-Fulfillment.
