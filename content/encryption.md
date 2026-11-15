# Encryption & Tri-Secret Secure

All Snowflake data is encrypted at rest and in transit by default, with keys managed in a hierarchical model rooted in a cloud HSM. Tri-Secret Secure (TSS) adds a customer-managed key (CMK) to that hierarchy, giving you a cryptographic kill switch over your data - and an operational dependency you must engineer for.

## How it works

### Hierarchical key model

Each account has its own key hierarchy with four levels:

1. **Root key** - stored in a cloud-provider HSM (on AWS and Azure the HSM creates and stores it; on Google Cloud it is held via Cloud KMS in multi-tenant HSM partitions).
2. **Account master keys (AMK)** - one hierarchy per account, providing cryptographic tenant isolation.
3. **Table master keys (TMK)** - one per table.
4. **File keys** - encrypt individual data files.

Each parent key wraps the keys below it, which limits how much data any one key protects. Encryption uses AES.

### Rotation and rekeying

- **Rotation** (all editions): Snowflake-managed keys are rotated automatically when they are older than 30 days. Old versions are *retired* - used only to decrypt existing data - and new data is encrypted with the active key.
- **Periodic rekeying** (Enterprise Edition or higher): when a retired key is older than one year, Snowflake re-encrypts the data it protects with a new key and destroys the old one. It runs online with no downtime. Enable it with `ALTER ACCOUNT SET PERIODIC_DATA_REKEYING = TRUE`. Rekeyed files incur 7 days of additional Fail-safe storage charges; Time Travel and Fail-safe retention periods are not changed.

### Tri-Secret Secure

TSS (Business Critical or higher) combines a Snowflake-maintained key with your CMK - in AWS KMS, Azure Key Vault or Google Cloud KMS - into a **composite master key** that acts as the account master key. The composite key wraps the hierarchy; it never encrypts raw data directly. The "three secrets" are the two keys plus Snowflake user authentication.

Self-service activation uses system functions:

1. Create the CMK in your cloud KMS.
2. `SYSTEM$REGISTER_CMK_INFO` registers it (account administrators are emailed).
3. `SYSTEM$GET_CMK_CONFIG` produces the policy/consent details to authorize Snowflake on the KMS side; `SYSTEM$VERIFY_CMK_INFO` checks connectivity.
4. Wait the mandatory **72 hours** after registration, then call `SYSTEM$ACTIVATE_CMK_INFO`, which starts rekeying (typically under an hour, up to 24 hours).
5. `SYSTEM$GET_CMK_INFO` reports status at any time.

Only one CMK can be registered at a time. `SYSTEM$ACTIVATE_CMK_INFO('REKEY_SAME_CMK')` rekeys after a cloud-side automatic rotation; otherwise Snowflake picks up a new CMK version at its next 30-day AMK rotation. Private connectivity to the KMS is available through `SYSTEM$PROVISION_PRIVATELINK_ENDPOINT_TSS`.

### Operational trade-offs

- **Availability coupling.** Snowflake tolerates key unavailability for up to about 10 minutes; after that, all data operations in the account stop until access is restored.
- **Irreversibility.** Deleting the CMK or older CMK versions, or deprovisioning an Azure private endpoint for an active CMK, can make data permanently unreadable.
- **Feature interactions.** Hybrid tables require Dedicated Storage Mode with TSS; auto-fulfillment for listings needs Support to enable TSS for secure share areas.

## Example

Enable periodic rekeying (Enterprise or higher):

```sql
USE ROLE ACCOUNTADMIN;
ALTER ACCOUNT SET PERIODIC_DATA_REKEYING = TRUE;
```

Tri-Secret Secure self-service on AWS (argument values depend on your cloud):

```sql
SELECT SYSTEM$REGISTER_CMK_INFO('<cmk_arn>');
SELECT SYSTEM$GET_CMK_INFO();
SELECT SYSTEM$GET_CMK_CONFIG();       -- apply output to the KMS key policy
SELECT SYSTEM$VERIFY_CMK_INFO();
-- at least 72 hours after registration:
SELECT SYSTEM$ACTIVATE_CMK_INFO();
SELECT SYSTEM$GET_CMK_INFO();         -- "is being activated" ... then "is activated"
```

## Best practices

- Treat the CMK as tier-0 infrastructure: deletion protection, restricted key administrators, and monitoring of key policy changes.
- Never delete or revoke older CMK versions after rotation.
- Keep access to the old CMK until Snowflake confirms rekeying has completed.
- Document a breach playbook: revoking the CMK halts all operations account-wide.
- Enable periodic rekeying where compliance requires bounded key lifetimes, and budget for the extra Fail-safe storage.

## Common pitfalls

- Expecting TSS to protect against compromised Snowflake credentials; it protects against storage-level access, not authorized queries.
- Attempting activation before the 72-hour wait elapses.
- Cloud KMS outages or misconfigured key policies taking the whole account offline.
- Forgetting that rotation alone does not rewrite old data - rekeying does.

## Learn more

- [Understanding encryption key management in Snowflake](https://docs.snowflake.com/en/user-guide/security-encryption-manage)
- [Tri-Secret Secure self-service in Snowflake](https://docs.snowflake.com/en/user-guide/security-encryption-tss-self-serve)

## Knowledge check

### Your CMK becomes unreachable due to a KMS misconfiguration. What happens after roughly 10 minutes?
- [ ] Only new writes fail; reads continue from cache
- [x] All data operations in the account stop until key access is restored
- [ ] Snowflake falls back to its own key
- [ ] Only Time Travel queries fail
> Snowflake tolerates short key unavailability (up to about 10 minutes); after that, all data operations cease until the key is available.

### Compliance requires that no key protects data for more than about a year. Which feature addresses this beyond default rotation?
- [ ] Tri-Secret Secure
- [x] Periodic rekeying, which re-encrypts data protected by keys retired for more than one year
- [ ] Rotating the CMK every 30 days
- [ ] Network policies
> Rotation only retires keys; periodic rekeying (Enterprise or higher) re-encrypts data so retired keys can be destroyed.

### You registered a new CMK this morning and SYSTEM$ACTIVATE_CMK_INFO returns an error advising you to wait. Why?
- [ ] The account must first be upgraded to Enterprise
- [x] There is a mandatory 72-hour waiting period between registration and activation
- [ ] You must deregister Snowflake's key first
- [ ] Activation requires Snowflake Support in all cases
> Snowflake enforces a 72-hour wait after SYSTEM$REGISTER_CMK_INFO before Tri-Secret Secure can be activated.
