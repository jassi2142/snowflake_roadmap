# SSO (SAML) & OAuth

Single sign-on (SSO) lets people log in to Snowflake with their corporate identity provider (IdP) instead of a Snowflake password, while OAuth lets applications act on a user's behalf with short-lived tokens. Together they centralize identity, move MFA enforcement to the IdP, and remove passwords from both people and BI tools.

## How it works

**SAML 2.0 SSO.** You create a `SAML2` security integration that describes the IdP (Okta, Microsoft Entra ID, AD FS, or any SAML 2.0 provider). Snowflake is the service provider:

- Provide IdP details either with `METADATA_URL` (supported for Okta and Entra ID, preferred because certificate changes can be refreshed) or with `SAML2_ISSUER`, `SAML2_SSO_URL`, `SAML2_PROVIDER` and `SAML2_X509_CERT`.
- `SAML2_SNOWFLAKE_ISSUER_URL` and `SAML2_SNOWFLAKE_ACS_URL` must match the Snowflake URL configured in the IdP. They default to the legacy account-locator URL, so set them if you use the organization-account URL or PrivateLink URL.
- `SAML2_ENABLE_SP_INITIATED` shows a login button in Snowflake. `ALLOWED_USER_DOMAINS` and `ALLOWED_EMAIL_PATTERNS` map users to the right IdP when you have several.
- The SAML assertion's NameID must match the user's `LOGIN_NAME` (email address format by default).
- Creating integrations requires `CREATE INTEGRATION`, held only by ACCOUNTADMIN by default.

By default, Snowflake does not require its own MFA for SSO users; it trusts the IdP. An authentication policy can add Snowflake MFA on top.

**OAuth** has two flavors:

| | Snowflake OAuth | External OAuth |
| --- | --- | --- |
| Token issuer | Snowflake | Your authorization server (Okta, Entra ID, PingFederate, custom) |
| Integration type | `TYPE = OAUTH` | `TYPE = EXTERNAL_OAUTH` |
| Typical use | Partner tools and custom apps using the authorization-code flow | Central token governance, programmatic clients without a browser |
| Secondary roles | Not supported for in-session switching | Supported |

In External OAuth, the token's `scope` selects the role (for example `session:role:analyst`). ACCOUNTADMIN, GLOBALORGADMIN, ORGADMIN and SECURITYADMIN are blocked by default unless you change `EXTERNAL_OAUTH_ADD_PRIVILEGED_ROLES_TO_BLOCKED_LIST`. A network policy attached to the integration overrides account- and user-level network policies.

## Example

A SAML integration for Okta using its metadata URL:

```sql
CREATE SECURITY INTEGRATION okta_sso
  TYPE = SAML2
  ENABLED = TRUE
  METADATA_URL = 'https://example.okta.com/app/abc123/sso/saml/metadata'
  SAML2_SNOWFLAKE_ISSUER_URL = 'https://myorg-myacct.snowflakecomputing.com'
  SAML2_SNOWFLAKE_ACS_URL = 'https://myorg-myacct.snowflakecomputing.com/fed/login'
  SAML2_ENABLE_SP_INITIATED = TRUE
  SAML2_SP_INITIATED_LOGIN_PAGE_LABEL = 'Okta SSO';
```

A Snowflake OAuth integration for a custom BI app, blocking an admin role from tokens:

```sql
CREATE SECURITY INTEGRATION bi_oauth
  TYPE = OAUTH
  ENABLED = TRUE
  OAUTH_CLIENT = CUSTOM
  OAUTH_CLIENT_TYPE = 'CONFIDENTIAL'
  OAUTH_REDIRECT_URI = 'https://bi.example.com/oauth/callback'
  OAUTH_ISSUE_REFRESH_TOKENS = TRUE
  OAUTH_REFRESH_TOKEN_VALIDITY = 86400
  BLOCKED_ROLES_LIST = ('SYSADMIN');
```

An External OAuth integration for Entra ID that is restricted by a network policy:

```sql
CREATE SECURITY INTEGRATION entra_ext_oauth
  TYPE = EXTERNAL_OAUTH
  ENABLED = TRUE
  EXTERNAL_OAUTH_TYPE = AZURE
  EXTERNAL_OAUTH_ISSUER = '<entra_issuer>'
  EXTERNAL_OAUTH_JWS_KEYS_URL = '<entra_jwks_url>'
  EXTERNAL_OAUTH_TOKEN_USER_MAPPING_CLAIM = 'upn'
  EXTERNAL_OAUTH_SNOWFLAKE_USER_MAPPING_ATTRIBUTE = 'login_name'
  NETWORK_POLICY = 'corp_only';
```

## Best practices

- Prefer `METADATA_URL` so IdP certificate rotation does not break logins.
- Pair SSO with SCIM so users and roles are provisioned from the IdP.
- Remove local passwords from SSO users, and keep one break-glass admin with a strong alternate method.
- Use authentication policies to restrict which integrations and methods each user population may use.
- Keep privileged roles blocked from OAuth tokens unless there is a clear need.

## Common pitfalls

- Issuer or ACS URL mismatch between the IdP and Snowflake, often after switching to PrivateLink or organization URLs.
- NameID values that do not match `LOGIN_NAME`, causing "user not found" failures.
- Expecting secondary roles to work with Snowflake OAuth sessions.
- Forgetting to define a scope in External OAuth tokens; the connection fails without one.

## Learn more

- [CREATE SECURITY INTEGRATION (SAML2)](https://docs.snowflake.com/en/sql-reference/sql/create-security-integration-saml2)
- [Introduction to OAuth](https://docs.snowflake.com/en/user-guide/oauth-intro)
- [External OAuth overview](https://docs.snowflake.com/en/user-guide/oauth-ext-overview)

## Knowledge check

### After moving to a PrivateLink URL, SAML logins fail with an ACS URL error. What is the most likely fix?
- [ ] Recreate users with new login names
- [x] Set SAML2_SNOWFLAKE_ISSUER_URL and SAML2_SNOWFLAKE_ACS_URL to the URL configured in the IdP
- [ ] Disable SAML2_ENABLE_SP_INITIATED
- [ ] Switch to External OAuth
> These properties default to the legacy URL and must match the Snowflake URL registered in the IdP.

### Your security team wants all token issuance and MFA challenges governed by the corporate authorization server, including for headless clients. Which option fits?
- [ ] Snowflake OAuth
- [x] External OAuth
- [ ] SAML2 with SAML2_FORCE_AUTHN = TRUE
- [ ] Password authentication with a network policy
> External OAuth delegates token issuance to your own authorization server and supports clients without browser access.

### An External OAuth token requests session:role:securityadmin and the login is rejected. Why?
- [ ] SECURITYADMIN cannot be granted to users
- [ ] Scopes must use the ANY role
- [x] Privileged roles such as SECURITYADMIN are blocked by default for External OAuth
- [ ] The integration needs a network policy
> ACCOUNTADMIN, GLOBALORGADMIN, ORGADMIN and SECURITYADMIN are blocked unless EXTERNAL_OAUTH_ADD_PRIVILEGED_ROLES_TO_BLOCKED_LIST is set to FALSE.
