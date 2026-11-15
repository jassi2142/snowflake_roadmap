# Service user with key-pair auth and zero-downtime key rotation

topics: key-pair-auth, authentication
tags: security, service-accounts, authentication
level: intermediate

Create a password-less `TYPE = SERVICE` user for an ETL tool or app, authenticate it with an RSA key pair, and rotate the key without downtime using the user's second key slot (`RSA_PUBLIC_KEY_2`).

```bash
# 1. Generate an encrypted private key and its public key (run where the client will live)
openssl genrsa 2048 | openssl pkcs8 -topk8 -v2 des3 -inform PEM -out rsa_key.p8
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub

# Fingerprint to compare with Snowflake later
openssl rsa -pubin -in rsa_key.pub -outform DER | openssl dgst -sha256 -binary | openssl enc -base64
```

```sql
-- 2. Create the service user. Paste the public key body WITHOUT the BEGIN/END lines.
USE ROLE USERADMIN;
CREATE USER IF NOT EXISTS svc_etl
  TYPE = SERVICE                       -- no password, MFA or interactive login
  DEFAULT_ROLE = fr_etl
  DEFAULT_WAREHOUSE = etl_wh
  RSA_PUBLIC_KEY = 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...'
  COMMENT = 'ETL pipeline service user; owner: data-platform team';

GRANT ROLE fr_etl TO USER svc_etl;

-- 3. Confirm the fingerprint matches the openssl output (RSA_PUBLIC_KEY_FP)
DESC USER svc_etl;

-- 4. Rotation, step A: load the NEW key into the second slot. Both keys now work.
ALTER USER svc_etl SET RSA_PUBLIC_KEY_2 = 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEB...';

--    Step B: switch every client to the new private key and test.
--    Step C: remove the old key.
ALTER USER svc_etl UNSET RSA_PUBLIC_KEY;

-- Next rotation goes back the other way: SET RSA_PUBLIC_KEY = new, then UNSET RSA_PUBLIC_KEY_2.

-- 5. Optional: list users still on LEGACY_SERVICE or without a type, which should be migrated
SHOW USERS ->> SELECT "name", "type"
               FROM $1 WHERE "type" IS NULL OR "type" = 'LEGACY_SERVICE';
```

## Notes
- Works in all editions. Managing keys for another user requires OWNERSHIP of that user or the MODIFY PROGRAMMATIC AUTHENTICATION METHODS privilege on it.
- SERVICE users can't have a password and can't use MFA or SAML. Use key pairs, OAuth, or workload identity federation.
- Keys must be at least 2048-bit RSA. Keep the private key in a secrets manager, never in a repo, and give it a passphrase (the `des3` encryption above).
- Rotating with two slots means there's no point at which clients can't authenticate. Set a rotation interval, for example every 90 days.
- Use a network policy on the service user to limit where it can connect from (see `network-policy-rules`).

## References
- [Key-pair authentication and key-pair rotation](https://docs.snowflake.com/en/user-guide/key-pair-auth)
- [CREATE USER](https://docs.snowflake.com/en/sql-reference/sql/create-user)
- [User types](https://docs.snowflake.com/en/user-guide/admin-user-management#label-user-management-types)
