# Network Policies & Rules

Network policies control which network locations can reach your Snowflake account, user, or integration. Network rules are the building blocks: small, reusable lists of IP ranges or private endpoint IDs that policies allow or block. Together they let you say "only our offices, our VPN, and our private endpoints may connect".

## How it works

**Network rules** are schema-level objects. Each rule groups identifiers of one `TYPE`:

- `IPV4` (and `IPV6`) address ranges in CIDR notation
- `AWSVPCEID` - AWS VPC endpoint IDs used with PrivateLink
- `AZURELINKID` - Azure Private Link endpoint IDs
- `COMPUTE_POOL` - to allow Snowpark Container Services compute pools

A rule's `MODE` says what it protects: `INGRESS` for the Snowflake service, `INTERNAL_STAGE` for internal stages on AWS (used with `AWSVPCEID`), and `EGRESS` for outbound access used by external access integrations. A rule never says "allow" or "block" itself - the network policy decides that.

**Network policies** reference rules in `ALLOWED_NETWORK_RULE_LIST` and `BLOCKED_NETWORK_RULE_LIST`:

- Once a rule of a type is in the allowed list, every other identifier of that type is blocked automatically.
- The **blocked list always wins** over the allowed list.
- Private connectivity rules (`AWSVPCEID`, `AZURELINKID`) take precedence over IPv4/IPv6 rules for requests that arrive over private connectivity.
- An empty policy allows no IPv4 addresses. `0.0.0.0/0` means all IPv4 addresses.

A policy does nothing until it is **activated** on the account, a user, or a security integration. The most specific level wins:

1. Security integration (most specific)
2. User
3. Account (most general)

Only SECURITYADMIN, or a role with the right privileges, can activate policies on the account. The older `ALLOWED_IP_LIST` / `BLOCKED_IP_LIST` parameters still exist, but network rules are the recommended approach.

## Example

Create rules for office IPs and a blocked address, combine them in a policy, and activate it for the account:

```sql
USE ROLE SECURITYADMIN;

CREATE NETWORK RULE security.net.office_ips
  MODE = INGRESS
  TYPE = IPV4
  VALUE_LIST = ('203.0.113.0/24', '198.51.100.10')
  COMMENT = 'HQ and VPN egress';

CREATE NETWORK RULE security.net.blocked_ip
  MODE = INGRESS
  TYPE = IPV4
  VALUE_LIST = ('203.0.113.99');

CREATE NETWORK POLICY corp_access
  ALLOWED_NETWORK_RULE_LIST = ('security.net.office_ips')
  BLOCKED_NETWORK_RULE_LIST = ('security.net.blocked_ip');

ALTER ACCOUNT SET NETWORK_POLICY = corp_access;
```

Give a service user its own, narrower policy (user level overrides the account policy):

```sql
CREATE NETWORK RULE security.net.etl_nat
  MODE = INGRESS TYPE = IPV4 VALUE_LIST = ('192.0.2.15/32');

CREATE NETWORK POLICY etl_only
  ALLOWED_NETWORK_RULE_LIST = ('security.net.etl_nat');

ALTER USER svc_ingest SET NETWORK_POLICY = etl_only;
```

Add a rule without replacing the existing list:

```sql
ALTER NETWORK POLICY corp_access ADD ALLOWED_NETWORK_RULE_LIST = ('security.net.new_office');
```

## Best practices

- Create many small, commented rules (per region, per application) instead of one giant list.
- Scope policies narrowly - to users or integrations - wherever possible.
- Test a policy on a single user before activating it for the account, and confirm your own IP is allowed.
- Give service users dedicated policies limited to their known egress IPs.
- Keep network rules in a dedicated governance database with restricted ownership.

## Common pitfalls

- Activating an account policy that does not include your current IP and locking yourself out.
- Expecting the allowed list to override a blocked entry - blocked always takes precedence.
- Forgetting that a user-level policy completely replaces the account-level one for that user.
- Using IPv6 rules to protect internal stages; only IPv4 rules can protect internal stages.

## Learn more

- [Controlling network traffic with network policies](https://docs.snowflake.com/en/user-guide/network-policies)

## Knowledge check

### An IP address appears in both the allowed and the blocked network rules of the same policy. What happens?
- [ ] It is allowed, because allowed lists are checked first
- [x] It is blocked, because the blocked list takes precedence
- [ ] The policy fails to activate
- [ ] It depends on rule creation order
> Snowflake always applies blocked values over allowed values.

### A network policy is set on the account and a different one on user BOB. Which applies when BOB logs in with a password?
- [ ] Both, combined
- [ ] The account policy
- [x] The user-level policy
- [ ] Neither
> The most specific policy wins; a user-level policy overrides the account-level policy (a security-integration policy would override both).

### You add a single IPv4 rule with your office range to a policy's allowed list. What about all other public IPv4 addresses?
- [ ] They remain allowed until added to a blocked list
- [x] They are blocked automatically
- [ ] Only private IPv4 addresses remain allowed
- [ ] They are allowed for Snowsight only
> Adding an IPv4 rule to the allowed list means only those addresses of that type are allowed; there is no need to block the rest explicitly.
