# Data Mesh on Snowflake

Data mesh is an operating model in which business domains own and publish their data as products, a central platform team provides self-serve infrastructure, and governance is federated: global standards are defined centrally and applied by each domain. Snowflake supports this model well because sharing, listings, database roles, and tag-based policies let domains publish governed, zero-copy data products without central pipelines that copy data between teams.

## How it works

The four data mesh principles map to Snowflake capabilities as follows.

**Domain ownership**

- Give each domain its own database (or, for strong autonomy and chargeback, its own account) with domain-owned roles, warehouses, and pipelines.
- Database roles let a domain manage access to its own objects without central tickets, while account-level functional roles stay under platform governance.

**Data as a product**

- A data product is a published interface (secure views, tables, semantic views, sometimes functions) with an owner, documentation, freshness and quality expectations, and versioning.
- **Secure data sharing** publishes products with no copies. In the same region, a share is live and zero-copy. Database roles can be granted to a share so consumers can map subsets of a product to different internal roles. A database role granted to a share can carry only read-only privileges and does not support future grants.
- **Listings** add discovery and metadata on top of shares. Organizational listings in the Internal Marketplace publish products to other accounts in the organization, and listings can use cross-cloud auto-fulfillment to replicate a product to consumers in other regions. Public Marketplace listings serve external consumers.

**Self-serve platform**

- The platform team provides templates and automation: provisioning of domain databases, standard role sets, warehouses with budgets, CI/CD for pipelines (for example dbt Projects on Snowflake or DCM projects), and observability.

**Federated computational governance**

- Define global tags (sensitivity, PII class, owner) and tag-based masking and row access policies centrally, then let domains apply tags to their objects. Policies then enforce themselves wherever the data travels within the account.
- Use access history, lineage, and data metric functions to verify product quality and usage. In multi-account meshes, aggregate this through ORGANIZATION_USAGE.

## Example

A sales domain publishes an orders product through a share, using database roles to separate standard and finance-only views:

```sql
USE ROLE sales_domain_admin;

CREATE SECURE VIEW sales_db.products.orders_v1 AS
  SELECT order_id, customer_id, order_date, region, net_amount
  FROM sales_db.curated.orders;

CREATE SECURE VIEW sales_db.products.orders_margin_v1 AS
  SELECT order_id, net_amount, cost_amount, net_amount - cost_amount AS margin
  FROM sales_db.curated.orders;

CREATE DATABASE ROLE sales_db.orders_reader;
CREATE DATABASE ROLE sales_db.orders_finance;
GRANT USAGE ON SCHEMA sales_db.products TO DATABASE ROLE sales_db.orders_reader;
GRANT SELECT ON VIEW sales_db.products.orders_v1 TO DATABASE ROLE sales_db.orders_reader;
GRANT DATABASE ROLE sales_db.orders_reader TO DATABASE ROLE sales_db.orders_finance;
GRANT SELECT ON VIEW sales_db.products.orders_margin_v1 TO DATABASE ROLE sales_db.orders_finance;

CREATE SHARE sales_orders_product;
GRANT USAGE ON DATABASE sales_db TO SHARE sales_orders_product;
GRANT DATABASE ROLE sales_db.orders_reader  TO SHARE sales_orders_product;
GRANT DATABASE ROLE sales_db.orders_finance TO SHARE sales_orders_product;
ALTER SHARE sales_orders_product ADD ACCOUNTS = myorg.marketing_prod;
```

The consumer account creates a database from the share and grants `orders_reader` or `orders_finance` to its own roles. The `_v1` suffix makes versioning explicit, so a breaking change ships as `orders_v2` alongside the old view.

## Best practices

- Publish products only through secure views or dedicated product schemas, never internal curated tables, so domains can refactor internals freely.
- Version product interfaces and announce deprecation windows. Treat schema changes to a published product like API changes.
- Standardize product metadata (owner, description, SLA, sensitivity tags, contact) and enforce it in CI before a listing or share is published.
- Keep the global tag taxonomy and policy library central, and require domains to tag their columns, which delegates enforcement without delegating policy design.
- Give each domain its own warehouses and budgets so costs follow ownership.
- Monitor product usage with access history to retire unused products and find highly used ones that need stronger SLAs.

## Common pitfalls

- Declaring a mesh while all pipelines still run through one central team, which renames the bottleneck without removing it.
- Letting domains invent their own sensitivity tags and policies, which produces inconsistent protection across products.
- Sharing base tables directly and then being unable to change them without breaking consumers.
- Forgetting that cross-region consumers need replication or auto-fulfillment, so a share alone will not reach them.
- Over-splitting into one account per team before the organization has the automation to baseline and govern many accounts.

## Learn more

- [Introduction to Secure Data Sharing](https://docs.snowflake.com/en/user-guide/data-sharing-intro)
- [GRANT DATABASE ROLE ... TO SHARE](https://docs.snowflake.com/en/sql-reference/sql/grant-database-role-share)

## Knowledge check

### A domain wants one share where marketing sees standard order columns and finance also sees margin. What is the cleanest design?
- [ ] Create two shares with duplicated views
- [x] Grant two database roles to one share and let the consumer map each database role to the appropriate internal role
- [ ] Use IMPORTED PRIVILEGES and a row access policy
- [ ] Share the base table and let the consumer create views
> Database roles in a share segment a product into subsets that the consumer grants independently, avoiding duplicate shares and preventing an all-or-nothing grant.

### How does federated computational governance typically work for PII on Snowflake?
- [ ] Each domain writes its own masking policies
- [ ] The platform team masks every column manually
- [x] Central teams define tags and tag-based policies, and domains apply the tags to their columns so protection is enforced automatically
- [ ] PII is removed before data reaches any domain
> Tag-based policies separate policy definition (central) from classification (domain), so enforcement is consistent while domains stay autonomous.

### A domain must change a column's data type in a product that 12 teams consume. What approach respects the data-as-a-product principle?
- [ ] Change the view in place and notify consumers afterwards
- [x] Publish a new versioned interface (for example orders_v2) alongside the old one and deprecate v1 on a communicated timeline
- [ ] Ask every consumer to copy the data before the change
- [ ] Revoke the share and recreate it
> Versioned interfaces let consumers migrate on their own schedule, which is how product contracts avoid breaking downstream users.
