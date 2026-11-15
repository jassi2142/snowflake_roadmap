# Reader Accounts

A reader account is a Snowflake account that a data provider creates and pays for, so that a consumer who is not a Snowflake customer can still query shared data. It is the quickest way to give an outside party SQL access to your data without asking them to sign a Snowflake contract.

## How it works

- The provider creates the reader account with `CREATE MANAGED ACCOUNT ... TYPE = READER`. This needs ACCOUNTADMIN or a role with the global `CREATE ACCOUNT` privilege.
- The reader account is **owned and managed by the provider**, uses the **same edition and region** as the provider, and can consume data **only from the provider account that created it**.
- The provider pays for **all credits** used by warehouses in the reader account. Those warehouses can consume an unlimited number of credits unless you set up resource monitors.
- Reader account users have no support contract with Snowflake; the provider handles their questions and opens Support tickets on their behalf.
- By default a provider can create up to **75** reader accounts. A dropped reader account still counts against that limit for 7 days.

What reader account users can and cannot do:

- They can query shared data and work with it, for example by creating materialized views.
- They cannot upload or modify data. Commands such as `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `COPY INTO <table>`, `CREATE STAGE`, `CREATE PIPE` and `CREATE SHARE` are blocked.

If the consumer needs to load and combine their own data, they need a full Snowflake account instead.

## Example

Provider: create the reader account and add it to a share.

```sql
USE ROLE ACCOUNTADMIN;

CREATE MANAGED ACCOUNT acme_reader
  ADMIN_NAME = acme_admin,
  ADMIN_PASSWORD = 'Choose-A-Strong-Passphrase-1!',
  TYPE = READER,
  COMMENT = 'Reader account for Acme Corp';

SHOW MANAGED ACCOUNTS;

-- Use the account locator returned above
ALTER SHARE emea_partner_share ADD ACCOUNTS = <reader_account_locator>;
```

Wait up to five minutes for provisioning. Then, logged in to the reader account as its administrator, set up compute, cost controls and access:

```sql
USE ROLE ACCOUNTADMIN;

CREATE RESOURCE MONITOR acme_monthly WITH CREDIT_QUOTA = 50
  TRIGGERS ON 90 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;

CREATE WAREHOUSE reader_wh
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;
ALTER WAREHOUSE reader_wh SET RESOURCE_MONITOR = acme_monthly;

CREATE DATABASE partner_sales FROM SHARE <provider_account_locator>.emea_partner_share;

CREATE USER acme_analyst PASSWORD = 'Temp-Passphrase-123!' MUST_CHANGE_PASSWORD = TRUE;
GRANT IMPORTED PRIVILEGES ON DATABASE partner_sales TO ROLE PUBLIC;
GRANT USAGE ON WAREHOUSE reader_wh TO ROLE PUBLIC;
```

## Best practices

- Always attach a resource monitor and short auto-suspend to every reader account warehouse - you are paying for it.
- Keep warehouses small; reader account workloads are usually light queries.
- Track usage with the `READER_ACCOUNT_USAGE` schema in the `SNOWFLAKE` database.
- Create named users with roles instead of sharing the admin login.
- Move consumers to full accounts when they need to load their own data or want to pay for their own compute.

## Common pitfalls

- Forgetting resource monitors and receiving an unexpected bill for consumer queries.
- Expecting reader users to upload files or join their own data - writes are blocked.
- Dropping and recreating reader accounts to stay under the 75 limit, not realizing dropped accounts count for 7 days.
- Trying to share data from a different provider into the same reader account.

## Learn more

- [Manage reader accounts](https://docs.snowflake.com/en/user-guide/data-sharing-reader-create)
- [Configure a reader account](https://docs.snowflake.com/en/user-guide/data-sharing-reader-config)

## Knowledge check

### Who pays for queries run by users in a reader account?
- [ ] The reader account's users, by credit card
- [x] The provider account that created the reader account
- [ ] Snowflake, as a free tier
- [ ] The consumer's cloud provider
> The provider owns the reader account and is responsible for all credits its warehouses consume.

### A consumer using a reader account asks to load their CRM file and join it to your shared data. What should you recommend?
- [ ] Grant them INSERT on the shared tables
- [ ] Use COPY INTO in the reader account
- [x] Move them to a full Snowflake account, because reader accounts cannot load or modify data
- [ ] Create a stage in the reader account
> Reader accounts block data loading and modification; consumers who need to combine their own data need a full account.

### What is the most important control to configure right after creating a reader account?
- [ ] A SCIM integration
- [x] A resource monitor on its warehouses
- [ ] Tri-Secret Secure
- [ ] A clean room
> Reader account warehouses can consume unlimited credits billed to the provider unless a resource monitor limits them.
