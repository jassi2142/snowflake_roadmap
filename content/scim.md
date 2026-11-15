# SCIM Provisioning

SCIM (System for Cross-domain Identity Management) lets your identity provider create, update, and deactivate Snowflake users and roles automatically. For organizations with thousands of identities, it is the difference between access that tracks HR events within minutes and access that drifts until the next manual audit.

## How it works

A `TYPE = SCIM` security integration exposes a SCIM 2.0 REST endpoint in your account. The IdP calls it with a bearer token to push changes:

- **Users** in the IdP become Snowflake users; attribute changes and deactivations flow through.
- **Groups** in the IdP become Snowflake **roles**, and group membership becomes role grants to users.

Key parameters:

- `SCIM_CLIENT` - `'OKTA'`, `'AZURE'` (Microsoft Entra ID) or `'GENERIC'` for any other SCIM 2.0 client.
- `RUN_AS_ROLE` - the role that owns every user and role created through SCIM. Built-in values are `OKTA_PROVISIONER`, `AAD_PROVISIONER` and `GENERIC_SCIM_PROVISIONER` (case-sensitive), or a custom role. You create this role and grant it `CREATE USER` and `CREATE ROLE`.
- `NETWORK_POLICY` - restricts SCIM traffic; an integration-level network policy overrides account and user policies.
- `SYNC_PASSWORD` - defaults to `FALSE`. Supported for Okta and custom clients only; Entra ID does not support password synchronization.

A SCIM integration cannot actually be disabled; the `ENABLED` property has no functional effect. `DESC SECURITY INTEGRATION` returns a `SCIM_ENDPOINT_ID` used in the request URLs, and `SYSTEM$GENERATE_SCIM_ACCESS_TOKEN` issues the token you paste into the IdP.

### Design decisions

- **Ownership model.** Because the provisioner role owns SCIM-created objects, only that role (or a role above it) can alter them. Grant the provisioner role to SECURITYADMIN or ACCOUNTADMIN so administrators keep control, but avoid manually editing SCIM-managed users: the IdP is the source of truth and will overwrite or conflict with changes.
- **Groups as functional roles only.** Map IdP groups to *functional* roles (for example `ANALYST_FINANCE`) and keep *access* roles (privileges on databases and warehouses) managed in Snowflake via SQL or infrastructure-as-code. Then grant access roles to the SCIM-created functional roles. This keeps privilege design out of the IdP while letting the IdP drive membership.
- **Pair with SSO.** SCIM provisions identities; SAML or OAuth authenticates them. Without a password sync, SCIM users normally have no Snowflake password at all.
- **User attributes.** Provisioned users can receive properties such as default role, default warehouse and default secondary roles through custom SCIM attributes; decide on these defaults deliberately.

## Example

Set up Entra ID provisioning with a dedicated provisioner role:

```sql
USE ROLE ACCOUNTADMIN;

CREATE ROLE IF NOT EXISTS AAD_PROVISIONER;
GRANT CREATE USER ON ACCOUNT TO ROLE AAD_PROVISIONER;
GRANT CREATE ROLE ON ACCOUNT TO ROLE AAD_PROVISIONER;
GRANT ROLE AAD_PROVISIONER TO ROLE ACCOUNTADMIN;

CREATE OR REPLACE SECURITY INTEGRATION aad_provisioning
  TYPE = SCIM
  SCIM_CLIENT = 'AZURE'
  RUN_AS_ROLE = 'AAD_PROVISIONER'
  NETWORK_POLICY = 'entra_scim_only';

SELECT SYSTEM$GENERATE_SCIM_ACCESS_TOKEN('AAD_PROVISIONING');
```

Wire SCIM-managed functional roles to Snowflake-managed access roles:

```sql
-- FINANCE_ANALYSTS was created by SCIM from an Entra group
GRANT ROLE finance_read TO ROLE "FINANCE_ANALYSTS";
```

## Best practices

- Use a dedicated provisioner role per integration; never use ACCOUNTADMIN as `RUN_AS_ROLE`.
- Restrict the SCIM endpoint with a network policy limited to your IdP's egress addresses.
- Treat the SCIM token as a secret, store it in the IdP only, and regenerate it on a schedule.
- Keep `SYNC_PASSWORD = FALSE` and authenticate SCIM users through SSO.
- Monitor provisioning errors in the IdP and audit SCIM-owned objects with `SHOW USERS` and `SHOW ROLES`.

## Common pitfalls

- Lowercase built-in role names in `RUN_AS_ROLE` - they must be uppercase.
- Granting privileges directly to SCIM-created roles in an ad hoc way, recreating the drift SCIM was meant to fix.
- Editing SCIM-owned users manually and having the IdP overwrite the change.
- Renaming or dropping an IdP group without realizing it changes or removes the matching Snowflake role.

## Learn more

- [Snowflake SCIM support](https://docs.snowflake.com/en/user-guide/scim-intro)
- [CREATE SECURITY INTEGRATION (SCIM)](https://docs.snowflake.com/en/sql-reference/sql/create-security-integration-scim)

## Knowledge check

### An administrator cannot alter a user that was provisioned by Okta. What is the most likely reason?
- [ ] SCIM users are read-only for everyone
- [x] The user is owned by the RUN_AS_ROLE provisioner role, which the administrator's role does not inherit
- [ ] SCIM integrations lock users until the token expires
- [ ] The user has SYNC_PASSWORD enabled
> Objects created by SCIM are owned by the RUN_AS_ROLE; only that role or roles above it in the hierarchy can modify them.

### You want the IdP to control who is in which team, but keep warehouse and database privileges version-controlled in Snowflake. What design fits best?
- [ ] Grant all object privileges directly to SCIM-created roles from the IdP
- [x] Map IdP groups to functional roles via SCIM, and grant Snowflake-managed access roles to those functional roles
- [ ] Disable group sync and grant roles to users manually
- [ ] Use SYNC_PASSWORD so the IdP manages privileges
> Separating functional roles (membership from the IdP) from access roles (privileges in Snowflake) keeps both sides authoritative for what they own.

### Your organization uses Microsoft Entra ID and asks for password synchronization into Snowflake. What is accurate?
- [ ] Set SYNC_PASSWORD = TRUE on the AZURE integration
- [ ] Use RUN_AS_ROLE = 'GENERIC_SCIM_PROVISIONER'
- [x] Entra ID SCIM integrations do not support password synchronization; use SSO instead
- [ ] Passwords sync automatically for all SCIM clients
> SYNC_PASSWORD is supported for Okta and custom clients only, and SSO is the recommended way for SCIM users to authenticate.
