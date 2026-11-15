# Passwords & MFA

Authentication is how Snowflake confirms who is connecting before any role or privilege is checked. Passwords are the simplest method, but Snowflake is phasing out password-only sign-ins: human users who use a password must add a second factor (MFA), and service users must move to methods that do not use passwords at all.

## How it works

Every login is tied to a **user** object. The user's `TYPE` property tells Snowflake what kind of identity it is:

- `TYPE = PERSON` (or not set / NULL) - a human user. Humans who sign in with a password must enroll in multi-factor authentication.
- `TYPE = SERVICE` - an application or pipeline. Service users cannot use a password; they authenticate with key pairs, OAuth, or similar non-interactive methods.
- `TYPE = LEGACY_SERVICE` - a temporary transition type that still allows a password for an application. Snowflake is deprecating it.

Snowflake is rolling out the deprecation of single-factor passwords in phases:

1. **Mandatory MFA for Snowsight** - human users signing in to Snowsight with a password must use a second factor.
2. **Strong authentication for new users** - new human users must use MFA on every surface, and `LEGACY_SERVICE` can no longer be set on new or existing users.
3. **Strong authentication for all users** - password-only sign-in is blocked for humans, and existing `LEGACY_SERVICE` users are converted to `SERVICE`.

Exact dates vary by account and are shown in the Strong Authentication Hub in Snowsight. Reader accounts and trial accounts are not covered by this rollout.

When a user is enrolled in MFA, they enter their password and then confirm with a second factor. Supported MFA methods are:

- **Passkeys** (recommended for security and usability)
- **Authenticator apps** that generate time-based one-time passcodes (TOTP)
- **Duo**

Users enroll in MFA through Snowsight. Users who sign in with SSO are not required to use Snowflake MFA by default, because Snowflake relies on the identity provider to enforce strong authentication.

## Example

Create a human user and a service user. The human user signs in with a password plus MFA; the service user has no password.

```sql
CREATE USER jane_doe
  TYPE = PERSON
  PASSWORD = 'Use-A-Long-Unique-Passphrase-42!'
  EMAIL = 'jane.doe@example.com'
  DEFAULT_ROLE = analyst
  MUST_CHANGE_PASSWORD = TRUE;

CREATE USER etl_service
  TYPE = SERVICE
  DEFAULT_ROLE = etl_role
  COMMENT = 'Nightly loader - authenticates with a key pair';
```

Find users who still have a local password, and help a locked-out user set up a new MFA method:

```sql
SHOW USERS;
SELECT "name", "type", "has_password"
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "has_password" = 'true';

-- User lost their authenticator; prompt them to enroll a new method
ALTER USER jane_doe ENROLL MFA;
```

## Best practices

- Set `TYPE` explicitly on every user so Snowflake applies the right rules.
- Prefer passkeys as the MFA method; they resist phishing better than codes.
- Never give applications a password; create them as `TYPE = SERVICE` and use key-pair or OAuth authentication.
- Keep a documented "break glass" admin user so you are not locked out if your identity provider fails.
- Check the Strong Authentication Hub regularly to see which users will be affected by the next phase.

## Common pitfalls

- Marking pipelines as `LEGACY_SERVICE` to avoid MFA. This is only a temporary bridge and is being removed.
- Assuming SSO users are affected by MFA enforcement in the same way as password users - by default they are not, unless you require it with an authentication policy.
- Leaving a password on users who actually sign in through SSO or key pairs; the unused password is still a credential that can be attacked.

## Learn more

- [Multi-factor authentication (MFA)](https://docs.snowflake.com/en/user-guide/security-mfa)
- [Planning for the deprecation of single-factor password sign-ins](https://docs.snowflake.com/en/user-guide/security-mfa-rollout)
- [Strong Authentication Hub](https://docs.snowflake.com/en/user-guide/strong-authentication-hub)

## Knowledge check

### A nightly data-loading script currently signs in with a username and password. What is the right long-term fix?
- [ ] Set the user to TYPE = LEGACY_SERVICE so the password keeps working
- [x] Set the user to TYPE = SERVICE and switch the script to key-pair or OAuth authentication
- [ ] Enroll the script's user in Duo MFA
- [ ] Set TYPE = PERSON and disable MFA for that user
> Service users should not use passwords at all. LEGACY_SERVICE is a temporary type being deprecated, and MFA requires a human to respond.

### A user was created without setting the TYPE property. How does Snowflake treat this user?
- [ ] As a service user
- [ ] As a legacy service user
- [x] As a human user (PERSON)
- [ ] The user cannot sign in until TYPE is set
> If TYPE is not set or is NULL, Snowflake treats the user as a human user, so MFA rules for password sign-ins apply.

### Which MFA method does Snowflake recommend for the best balance of security and usability?
- [ ] SMS codes
- [ ] Duo push notifications
- [x] Passkeys
- [ ] Emailed one-time links
> Snowflake recommends passkeys because of their security and usability. Supported methods are passkeys, TOTP authenticator apps, and Duo.
