# Network rules + network policy for a service user

topics: network-policies, key-pair-auth
tags: security, network, service-accounts
level: intermediate

Lock a service user down so it can only connect from your ETL servers' IP range, with one known-bad address in that range blocked. Network rules hold the identifiers, the network policy decides which rules are allowed or blocked, and activating the policy on the user applies it.

```sql
-- 1. Network rules live in a schema; keep them in a dedicated security schema
USE ROLE SECURITYADMIN;
CREATE DATABASE IF NOT EXISTS security_db;
CREATE SCHEMA   IF NOT EXISTS security_db.network;

CREATE OR REPLACE NETWORK RULE security_db.network.etl_servers_ipv4
  TYPE = IPV4
  MODE = INGRESS
  VALUE_LIST = ('203.0.113.0/24')
  COMMENT = 'ETL server subnet (allowed)';

CREATE OR REPLACE NETWORK RULE security_db.network.decommissioned_host
  TYPE = IPV4
  MODE = INGRESS
  VALUE_LIST = ('203.0.113.99')
  COMMENT = 'Old ETL host inside the subnet (blocked)';

-- 2. Policy: allow the subnet, block the single host. Blocked always wins over allowed.
--    Anything not in an allowed IPv4 rule is blocked automatically.
CREATE NETWORK POLICY IF NOT EXISTS etl_service_policy
  ALLOWED_NETWORK_RULE_LIST = ('security_db.network.etl_servers_ipv4')
  BLOCKED_NETWORK_RULE_LIST = ('security_db.network.decommissioned_host')
  COMMENT = 'Ingress for svc_etl only';

-- 3. Activate on the user (overrides any account-level policy for this user)
ALTER USER svc_etl SET NETWORK_POLICY = etl_service_policy;

-- 4. Verify
DESC NETWORK POLICY etl_service_policy;
SHOW PARAMETERS LIKE 'NETWORK_POLICY' IN USER svc_etl;

-- 5. Change the subnet later without touching the policy: edit the rule
-- ALTER NETWORK RULE security_db.network.etl_servers_ipv4 SET VALUE_LIST = ('203.0.113.0/24', '198.51.100.0/28');

-- Add another rule to the existing allowed list (SET would replace the whole list)
-- ALTER NETWORK POLICY etl_service_policy ADD ALLOWED_NETWORK_RULE_LIST = ('security_db.network.dr_site_ipv4');

-- Clean up
-- ALTER USER svc_etl UNSET NETWORK_POLICY;
-- DROP NETWORK POLICY etl_service_policy;
```

## Notes
- Works in all editions. Creating policies requires SECURITYADMIN or the global CREATE NETWORK POLICY privilege. Creating rules requires CREATE NETWORK RULE on the schema. Activating a policy on a user requires OWNERSHIP of the user and USAGE on the policy.
- Precedence: a policy on a security integration overrides one on a user, which overrides the account-level policy. A user has at most one policy.
- Test on a single user before setting `ALTER ACCOUNT SET NETWORK_POLICY`. At account level your own current IP must be in the allowed list, or the statement fails.
- Restricting internal stage access on AWS also requires `ENFORCE_NETWORK_RULES_FOR_INTERNAL_STAGES = TRUE` at account level.
- Use network rules, not the older `ALLOWED_IP_LIST` / `BLOCKED_IP_LIST` parameters, for new policies, and don't mix the two in one policy.

## References
- [Controlling network traffic with network policies](https://docs.snowflake.com/en/user-guide/network-policies)
- [Network rules](https://docs.snowflake.com/en/user-guide/network-rules)
- [CREATE NETWORK POLICY](https://docs.snowflake.com/en/sql-reference/sql/create-network-policy)
