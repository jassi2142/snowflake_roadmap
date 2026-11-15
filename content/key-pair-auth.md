# Key-pair Authentication (incl. rotation, service users)

Key-pair authentication lets a client prove its identity by signing a token with a private key whose matching public key is registered on the Snowflake user. It is the standard choice for service users - pipelines, schedulers, and applications - because it needs no password and no human to approve an MFA prompt.

## How it works

You generate an RSA key pair (minimum 2048 bits) locally, keep the private key on the client, and assign the public key to the Snowflake user. At connection time the driver signs a JWT with the private key, and Snowflake verifies it against the registered public key. The private key never leaves the client, and if it is encrypted, its passphrase is never sent to Snowflake either.

Key points:

- Keys are PEM-encoded; the private key uses PKCS#8 format. Encrypted private keys are recommended - use AES-256-CBC rather than Triple DES.
- Supported clients include Snowflake CLI, SnowSQL, the Python, JDBC, ODBC, Node.js, .NET, Go and PHP PDO drivers, and the Spark and Kafka connectors. Not every client supports encrypted private keys, so check the support table for your client.
- To assign a key, a role needs `OWNERSHIP` on the user or the `MODIFY PROGRAMMATIC AUTHENTICATION METHODS` privilege on the user. This lets a team manage its own service user's keys without being a user administrator.
- Pair key-pair authentication with `TYPE = SERVICE` users, which cannot use passwords.

There are two ways to register keys:

1. **Named key pairs (recommended)** - `ALTER USER ... ADD KEY PAIR` registers a named key. It supports role restriction, named key management and expiration. `ROTATE KEY PAIR` replaces the public key and keeps the previous key valid for a grace period (24 hours by default, controlled by `EXPIRE_ROTATED_KEY_PAIR_AFTER_HOURS`; 0 expires it immediately).
2. **User properties** - `RSA_PUBLIC_KEY` and `RSA_PUBLIC_KEY_2` let you attach up to two public keys. You rotate by loading the new key into the empty slot, switching clients, then unsetting the old one. This approach does not support role restriction or expiration.

## Example

Generate an encrypted private key and its public key with OpenSSL:

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -v2 aes-256-cbc -inform PEM -out rsa_key.p8
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
```

Create a service user, delegate key management, and register a named key (paste the key body without the BEGIN/END lines):

```sql
CREATE USER svc_ingest TYPE = SERVICE DEFAULT_ROLE = ingest_role;

GRANT MODIFY PROGRAMMATIC AUTHENTICATION METHODS ON USER svc_ingest
  TO ROLE ingest_admin;

ALTER USER svc_ingest ADD KEY PAIR primary_key
  PUBLIC_KEY = 'MIIBIjANBgkqh...';
```

Rotate it later with no downtime; the old key keeps working for 24 hours by default:

```sql
ALTER USER svc_ingest ROTATE KEY PAIR primary_key
  PUBLIC_KEY = 'MIIBIjANBgkqh...new...';

SHOW USER KEY PAIRS FOR USER svc_ingest;
```

The legacy two-slot rotation pattern:

```sql
ALTER USER svc_ingest SET RSA_PUBLIC_KEY_2 = 'MIIBIjANBgkqh...new...';
-- deploy the new private key to clients, then:
ALTER USER svc_ingest UNSET RSA_PUBLIC_KEY;
```

## Best practices

- Store private keys in a secrets manager, not in source control or container images.
- Encrypt private keys and keep the passphrase in a separate secret.
- Rotate on a fixed schedule and use the grace period so in-flight jobs keep working.
- Verify a key by comparing the `RSA_PUBLIC_KEY_FP` fingerprint from `DESC USER` with the fingerprint of your local public key.
- Use one key per workload so you can revoke one without breaking others.

## Common pitfalls

- Including the `-----BEGIN PUBLIC KEY-----` delimiters in the SQL statement.
- Removing the old key before every client has switched to the new private key.
- Encrypting keys with Triple DES; some newer SDKs reject them.
- Leaving a password on the service user "just in case", which defeats the point.

## Learn more

- [Key-pair authentication and key-pair rotation](https://docs.snowflake.com/en/user-guide/key-pair-auth)
- [ALTER USER ... ROTATE KEY PAIR](https://docs.snowflake.com/en/sql-reference/sql/alter-user-rotate-key-pair)

## Knowledge check

### A platform team wants app owners to rotate keys on their own service users without granting them USERADMIN. What should you grant?
- [ ] MANAGE GRANTS on the account
- [x] MODIFY PROGRAMMATIC AUTHENTICATION METHODS on each service user
- [ ] CREATE USER on the account
- [ ] OWNERSHIP on the app's database
> MODIFY PROGRAMMATIC AUTHENTICATION METHODS on a user (or OWNERSHIP of the user) is what allows assigning public keys, scoped to that specific user.

### You rotate a named key pair with ROTATE KEY PAIR and do not set any extra option. What happens to the old key?
- [ ] It is invalidated immediately
- [x] It stays valid for a default grace period of 24 hours
- [ ] It stays valid until you run REMOVE KEY PAIR
- [ ] It moves into the RSA_PUBLIC_KEY_2 slot
> By default the prior key remains valid for 24 hours; EXPIRE_ROTATED_KEY_PAIR_AFTER_HOURS changes this, and 0 expires it immediately.

### Using the RSA_PUBLIC_KEY and RSA_PUBLIC_KEY_2 properties, what is the correct zero-downtime rotation order?
- [ ] Unset RSA_PUBLIC_KEY, then set the new key, then update clients
- [x] Set the new key in the unused slot, update clients to the new private key, then unset the old key
- [ ] Update clients first, then set the new key
- [ ] Replace RSA_PUBLIC_KEY in place with the new value
> Snowflake accepts either registered key, so loading the new key into the free slot before switching clients avoids failed connections.
