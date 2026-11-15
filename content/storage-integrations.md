# Storage Integrations

A storage integration is an account-level Snowflake object that lets Snowflake access your cloud storage (Amazon S3, Google Cloud Storage, or Azure) through an identity managed by your cloud provider, instead of through access keys or SAS tokens embedded in SQL. It is the recommended way to secure external stages, and it centralizes which storage locations Snowflake is allowed to touch.

## How it works

When you create a storage integration, Snowflake associates it with a cloud identity provisioned for your Snowflake account (on AWS, an IAM user; on Google Cloud, a service account; on Azure, a service principal). You then grant that identity permission in your cloud account, so no secrets are exchanged.

The flow on AWS looks like this:

1. In AWS, create an IAM policy with the S3 permissions Snowflake needs and attach it to an IAM role.
2. In Snowflake, run `CREATE STORAGE INTEGRATION` with `STORAGE_AWS_ROLE_ARN` set to that role.
3. Run `DESC INTEGRATION` to retrieve the Snowflake IAM user ARN and the external ID.
4. In AWS, edit the role's trust policy so that the Snowflake IAM user, presenting that external ID, can assume the role.
5. Create external stages that reference the integration.

Important properties:

- `TYPE = EXTERNAL_STAGE` and `STORAGE_PROVIDER` (`'S3'`, `'GCS'`, or `'AZURE'`).
- `STORAGE_ALLOWED_LOCATIONS`: the buckets or paths that stages using this integration may reference.
- `STORAGE_BLOCKED_LOCATIONS`: optional paths to exclude.
- `ENABLED = TRUE`.

Privilege model: creating an integration requires ACCOUNTADMIN or a role with the global `CREATE INTEGRATION` privilege. To create a stage that uses the integration, a role needs `USAGE` on it. When you load through a named stage, the role that owns the stage must have `USAGE` on the integration; the role running `COPY` does not. If a `COPY` statement references the integration directly via `STORAGE_INTEGRATION =` instead of a named stage, the role running it needs `USAGE`.

For replication, storage integrations replicate only through replication or failover groups that include `STORAGE INTEGRATIONS` in `ALLOWED_INTEGRATION_TYPES`, and replication of account objects such as integrations requires Business Critical Edition or higher. After failover you must also configure the trust relationship for the secondary integration in your cloud account.

## Example

Create an S3 integration that allows one path and blocks a sensitive subfolder.

```sql
USE ROLE ACCOUNTADMIN;

CREATE STORAGE INTEGRATION s3_raw_int
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/snowflake-raw-access'
  STORAGE_ALLOWED_LOCATIONS = ('s3://acme-raw/landing/')
  STORAGE_BLOCKED_LOCATIONS = ('s3://acme-raw/landing/pii/');

-- Copy STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID into the AWS trust policy
DESC INTEGRATION s3_raw_int;

GRANT USAGE ON INTEGRATION s3_raw_int TO ROLE data_engineer;
```

The data engineering role can now create stages within the allowed location.

```sql
USE ROLE data_engineer;

CREATE STAGE raw_orders_stage
  URL = 's3://acme-raw/landing/orders/'
  STORAGE_INTEGRATION = s3_raw_int;
```

## Best practices

- Use storage integrations instead of `CREDENTIALS = (AWS_KEY_ID ...)` so secrets never appear in scripts or query history.
- Scope `STORAGE_ALLOWED_LOCATIONS` as narrowly as practical, and use separate integrations for separate trust boundaries (for example, raw versus curated buckets).
- Grant the cloud role only the actions needed: read-only for loading, plus write and delete only if you unload or purge.
- Restrict who holds `USAGE` on integrations; that privilege is what lets a role point stages at your buckets.
- Keep the integration creation in a controlled, admin-owned script.

## Common pitfalls

- Running `CREATE OR REPLACE STORAGE INTEGRATION`, which generates a new external ID and breaks the existing trust policy until you update it in the cloud provider.
- Creating a stage whose URL falls outside `STORAGE_ALLOWED_LOCATIONS`; Snowflake rejects it.
- Granting `USAGE` to the role running `COPY` but not to the role that owns the stage.
- Expecting a government-region or China-region bucket to work from an account in a different region type; storage integrations there are limited to accounts in the same region.

## Learn more

- [CREATE STORAGE INTEGRATION](https://docs.snowflake.com/en/sql-reference/sql/create-storage-integration)
- [Stage, pipe, and load history replication](https://docs.snowflake.com/en/user-guide/account-replication-stages-pipes-load-history)

## Knowledge check

### After an admin re-runs CREATE OR REPLACE STORAGE INTEGRATION with the same settings, all stages using it fail with an access error. Why?
- [ ] The integration was disabled by default
- [x] Recreating the integration produced a new external ID, so the cloud trust policy no longer matches
- [ ] Stages must be recreated whenever an integration exists for more than 24 hours
- [ ] Storage integrations only work with internal stages
> Recreating an integration generates new identity values such as the external ID. The trust policy in the cloud provider must be updated with the new values from DESC INTEGRATION.

### A role can run COPY INTO from a named external stage but does not have USAGE on the stage's storage integration. Will the load work?
- [x] Yes, as long as the role that owns the stage has USAGE on the integration
- [ ] No, the role running COPY always needs USAGE on the integration
- [ ] Only if the integration is owned by ACCOUNTADMIN
> For named stages, the stage owner's privilege on the integration is what matters. Only when COPY references the integration directly does the executing role need USAGE.

### What is the main security advantage of a storage integration over CREDENTIALS in a stage?
- [ ] It encrypts the files in the bucket
- [ ] It makes files load faster
- [x] Access is granted to a cloud identity through IAM, so no long-lived keys are stored in Snowflake SQL
> The integration relies on your cloud provider's identity and access management. Snowflake assumes a role you trust, and no secret keys are exchanged or embedded in scripts.
