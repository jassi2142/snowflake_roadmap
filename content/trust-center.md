# Trust Center

The Trust Center is a Snowsight feature that continuously evaluates your Snowflake account against security recommendations and reports risks it finds. It runs background checks called scanners, surfaces findings with severity and remediation guidance, and can notify you proactively. For administrators it acts as a single place to measure and improve an account's security posture.

## How it works

You open it in Snowsight under **Governance & security » Trust Center**. Reader accounts are not supported.

### Scanners and scanner packages

A **scanner** is a background process that checks your account for a specific risk. Scanners are grouped into **scanner packages**:

- **Security Essentials:** checks that an authentication policy forces human users who use passwords to enroll in MFA, that those users are enrolled, that an account-level network policy restricts access to trusted IPs, and related basics. It is **enabled by default, cannot be deactivated**, and its fixed-schedule runs incur no serverless cost (other runs do).
- **CIS Benchmarks:** evaluates the account against the Center for Internet Security Snowflake Benchmarks. Runs daily by default.
- **Threat Intelligence:** identifies risks such as password-only human users without MFA, dormant user sign-ins, users with many authentication failures, logins from unusual IPs, and new administrator grants.
- **AI Security:** monitors AI-related configurations, for example privileged ownership of Cortex Search services or agents accessing sensitive data without masking or row access policies.
- **Data Security:** detects anomalous volumes of data unloaded to stages.

Packages other than Security Essentials are deactivated by default; when enabled, they run immediately and then on their schedule, using serverless compute that you pay for.

Scanners are either **schedule-based** (run at set times) or **event-driven** (react to events, typically reporting within an hour, sometimes up to four hours).

### Findings: violations and detections

- A **violation** is a persistent configuration problem, such as users without MFA. It stays open until the configuration is fixed and the scanner runs again, or until you mark it resolved with a justification.
- A **detection** is a one-time event, such as a login from a suspicious IP. You investigate it but cannot remediate the past event directly.

Each finding has a severity (low, medium, high, critical) and remediation guidance. The Overview tab summarizes posture and can generate a PDF posture report. In an organization account, an Organization tab aggregates violations across accounts.

Note that some CIS checks only verify that a control exists, not that it is effective. For example, a check may pass if at least one masking policy exists, even if sensitive columns are not protected.

### Access control

An ACCOUNTADMIN grants one of two application roles:

- `SNOWFLAKE.TRUST_CENTER_VIEWER`: view findings and posture.
- `SNOWFLAKE.TRUST_CENTER_ADMIN`: also manage scanner packages, scanners, schedules, and violation status.

## Example

Create separate admin and viewer roles for the Trust Center:

```sql
USE ROLE ACCOUNTADMIN;

CREATE ROLE trust_center_admin_role;
GRANT APPLICATION ROLE SNOWFLAKE.TRUST_CENTER_ADMIN TO ROLE trust_center_admin_role;

CREATE ROLE trust_center_viewer_role;
GRANT APPLICATION ROLE SNOWFLAKE.TRUST_CENTER_VIEWER TO ROLE trust_center_viewer_role;

GRANT ROLE trust_center_admin_role TO USER security_lead;
GRANT ROLE trust_center_viewer_role TO USER auditor;
```

A typical remediation for a Security Essentials violation is enforcing MFA for human users through an authentication policy:

```sql
CREATE AUTHENTICATION POLICY security.policies.require_mfa
  MFA_ENROLLMENT = REQUIRED;

ALTER ACCOUNT SET AUTHENTICATION POLICY security.policies.require_mfa;
```

After remediation, the violation clears on the next scheduled scan of its package, or sooner if you run the package on demand.

## Best practices

- Review the Security Essentials findings first; they cover the most common account takeover risks.
- Enable CIS Benchmarks and Threat Intelligence in production accounts and set up notifications for high and critical findings.
- Grant TRUST_CENTER_VIEWER to auditors and TRUST_CENTER_ADMIN only to the security team.
- Record a justification whenever you resolve a violation without changing configuration, so audits have context.
- Enable the AI Security package if you use Cortex Agents or other AI features.

## Common pitfalls

- Assuming a fixed violation disappears immediately; it remains until the next scanner run.
- Treating a passing CIS check as proof that sensitive data is protected.
- Enabling many packages with frequent schedules without budgeting for serverless compute.
- Expecting to resolve violations from the Organization tab; that must be done in the account that owns them.

## Learn more

- [Trust Center](https://docs.snowflake.com/en/user-guide/trust-center/overview)
- [Using the Trust Center](https://docs.snowflake.com/en/user-guide/trust-center/using-the-trust-center)

## Knowledge check

### A scanner reports that a login came from a known malicious IP address yesterday. What type of finding is this, and what can you do with it?
- [ ] A violation; fix the configuration and it disappears
- [x] A detection; investigate it and take preventive action, since the past event cannot be remediated
- [ ] A violation that must be resolved from the Organization tab
- [ ] A benchmark result that only appears in the PDF report
> Detections represent one-time events, while violations represent ongoing configuration problems that can be remediated.

### An auditor needs to read all findings but must not change scanner settings. Which grant is appropriate?
- [ ] ACCOUNTADMIN
- [ ] SNOWFLAKE.TRUST_CENTER_ADMIN
- [x] SNOWFLAKE.TRUST_CENTER_VIEWER
- [ ] SECURITYADMIN
> The viewer application role allows viewing findings and posture, while scanner and finding management require the admin role.

### You enforced MFA through an authentication policy, but the related violation is still listed an hour later. What is the most likely reason?
- [ ] The fix was ineffective because MFA cannot be enforced by policy
- [x] Violations remain until the next scheduled run of the scanner package, unless you run it on demand
- [ ] Violations are only refreshed weekly
- [ ] Security Essentials cannot detect authentication policies
> The Trust Center keeps showing a remediated violation until the scanner package runs again.
