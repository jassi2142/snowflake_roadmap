# Authentication Policies

Authentication policies are schema-level objects that control *how* users may authenticate: which methods, which clients, which identity providers, and whether MFA is required. They let architects express a login posture per user population - humans, administrators, service accounts - instead of relying on a single account-wide setting.

## How it works

An authentication policy can specify:

- `AUTHENTICATION_METHODS` - allowed methods, such as `PASSWORD`, `SAML`, `OIDC`, `OAUTH`, `KEYPAIR` and `PROGRAMMATIC_ACCESS_TOKEN`.
- `MFA_ENROLLMENT` - `REQUIRED` or `OPTIONAL`. When set, `CLIENT_TYPES` must include `SNOWFLAKE_UI`, because Snowsight is the only place users can enroll.
- `MFA_POLICY` - for example `ALLOWED_METHODS = ('PASSKEY','TOTP')` to exclude Duo, or `ENFORCE_MFA_ON_EXTERNAL_AUTHENTICATION = 'ALL'` to require Snowflake MFA even after SSO.
- `CLIENT_TYPES` - such as `SNOWFLAKE_UI`, `SNOWFLAKE_CLI`, `SNOWSQL` and `DRIVERS`. A client policy can also set minimum client versions.
- `SECURITY_INTEGRATIONS` - which SAML2 or OIDC integrations (IdPs) a user may use.
- Programmatic access token settings, such as default and maximum expiry and network policy requirements.

By default, all methods, clients and integrations are allowed.

### Attachment and precedence

- Set on the account (`ALTER ACCOUNT SET AUTHENTICATION POLICY`), on individual users, or on all users of a type (`... FOR ALL SERVICE USERS`).
- A **user-level policy overrides the account-level policy** - it replaces it rather than merging with it.
- Across policy types, evaluation order is: network policy, then authentication policy, then password policy (local auth only), then session policy. A request blocked by a network policy never reaches the authentication policy.
- Setting policies requires the `APPLY AUTHENTICATION POLICY` privilege (SECURITYADMIN has it by default); creating them requires `CREATE AUTHENTICATION POLICY` on the schema.
- Policies can be replicated with replication and failover groups.

### Trade-offs to design for

- **`CLIENT_TYPES` is best-effort.** Snowflake documents it as unsuitable as a sole security boundary; in particular it does not restrict the Snowflake REST APIs. Combine it with method and network restrictions.
- **Override semantics cut both ways.** A permissive user-level policy is the documented way to keep a break-glass administrator able to log in under a strict account policy, but every user-level policy is also an exception that must be reviewed.
- **Method/integration consistency.** Listing a SAML integration while allowing only `OAUTH` is rejected; an OIDC integration needs `OIDC` in the allowed methods.
- **Platform direction.** Snowflake's single-factor password deprecation overrides policies that tried to make MFA optional for Snowsight, so design policies that assume MFA for every password user.

## Example

A strict account-level baseline: SSO for people, no Duo, and Snowflake MFA for password users.

```sql
CREATE AUTHENTICATION POLICY security.policies.human_baseline
  AUTHENTICATION_METHODS = ('SAML', 'PASSWORD')
  SECURITY_INTEGRATIONS = ('OKTA_SSO')
  CLIENT_TYPES = ('SNOWFLAKE_UI', 'DRIVERS', 'SNOWFLAKE_CLI')
  MFA_ENROLLMENT = 'REQUIRED'
  MFA_POLICY = (ALLOWED_METHODS = ('PASSKEY', 'TOTP'));

ALTER ACCOUNT SET AUTHENTICATION POLICY security.policies.human_baseline;
```

Key-pair only for every service user, and a break-glass exception:

```sql
CREATE AUTHENTICATION POLICY security.policies.service_keypair
  AUTHENTICATION_METHODS = ('KEYPAIR')
  CLIENT_TYPES = ('DRIVERS', 'SNOWFLAKE_CLI');

ALTER ACCOUNT SET AUTHENTICATION POLICY security.policies.service_keypair
  FOR ALL SERVICE USERS;

CREATE AUTHENTICATION POLICY security.policies.breakglass
  AUTHENTICATION_METHODS = ('SAML', 'PASSWORD')
  CLIENT_TYPES = ('SNOWFLAKE_UI', 'SNOWFLAKE_CLI', 'SNOWSQL', 'DRIVERS');

ALTER USER breakglass_admin SET AUTHENTICATION POLICY security.policies.breakglass;
```

Audit where a policy is attached:

```sql
SELECT *
FROM TABLE(security.INFORMATION_SCHEMA.POLICY_REFERENCES(
  POLICY_NAME => 'security.policies.human_baseline'));
```

## Best practices

- Keep policies in a dedicated governance database and schema owned by a policy-admin role.
- Use type-scoped attachment (`FOR ALL SERVICE USERS`) rather than many per-user policies.
- Always create and test a break-glass policy before tightening the account policy.
- Review `POLICY_REFERENCES` regularly to catch stale user-level exceptions.

## Common pitfalls

- Locking yourself out by applying an SSO-only account policy before verifying the IdP integration.
- Assuming user and account policies combine; the user policy fully replaces the account one.
- Setting `MFA_ENROLLMENT` without `SNOWFLAKE_UI` in `CLIENT_TYPES`.
- Treating `CLIENT_TYPES` as a hard perimeter for API access.

## Learn more

- [Authentication policies](https://docs.snowflake.com/en/user-guide/authentication-policies)
- [CREATE AUTHENTICATION POLICY](https://docs.snowflake.com/en/sql-reference/sql/create-authentication-policy)

## Knowledge check

### An account policy allows only SAML. A user has a user-level policy allowing SAML and PASSWORD. What applies to that user?
- [ ] Only SAML, because the most restrictive policy wins
- [x] SAML and PASSWORD, because the user-level policy overrides the account-level policy
- [ ] Neither; conflicting policies block login
- [ ] The intersection of the two policies
> If a policy is set on both the account and the user, the user-level policy is enforced in place of the account policy.

### A team wants to prevent a vendor from calling Snowflake REST APIs by restricting CLIENT_TYPES to SNOWFLAKE_UI. What is the risk?
- [ ] There is none; CLIENT_TYPES fully blocks APIs
- [x] CLIENT_TYPES is best-effort and does not restrict REST API access, so it cannot be the only control
- [ ] SNOWFLAKE_UI also allows all drivers
- [ ] CLIENT_TYPES applies only to service users
> Snowflake documents CLIENT_TYPES as a best-effort control that does not restrict the REST APIs; combine it with authentication methods and network policies.

### A login comes from an IP address that is on the account network policy's blocked list. Which policies are evaluated?
- [ ] Authentication policy first, then network policy
- [x] Only the network policy; evaluation stops before the authentication policy
- [ ] Password policy, then authentication policy
- [ ] All policies, and the most permissive result applies
> Network policies are evaluated first; a blocked request never reaches authentication, password, or session policies.
