# Private Connectivity (AWS PrivateLink, Azure Private Link, GCP Private Service Connect)

Private connectivity lets clients reach Snowflake through private endpoints in your own cloud network instead of over the public internet. It is a Business Critical (or higher) capability and a common requirement for regulated workloads, but it is a networking and DNS project as much as a Snowflake one, and it does not by itself block public access.

## How it works

Each cloud provider offers an endpoint service that Snowflake exposes inside its VPC/VNet:

- **AWS PrivateLink** - you create an interface VPC endpoint to Snowflake's endpoint service. Cross-region PrivateLink is supported for Snowflake's endpoint service (not for PaaS services such as S3 or KMS).
- **Azure Private Link** - you create a private endpoint in your VNet to Snowflake.
- **Google Cloud Private Service Connect** - you create a PSC endpoint in your VPC.

These features control **inbound** connectivity from your network to Snowflake. Reaching private resources *from* Snowflake (outbound) is a separate capability.

The AWS workflow illustrates the general pattern:

1. **Authorize.** Generate a federated token in AWS, then call `SYSTEM$AUTHORIZE_PRIVATELINK('<aws_account_id>', '<federated_token>')`. The federated token expires after 12 hours. `SYSTEM$GET_PRIVATELINK` confirms authorization. Third-party or managed-service AWS accounts must be authorized through Snowflake Support.
2. **Get endpoint details.** `SYSTEM$GET_PRIVATELINK_CONFIG()` returns the endpoint service ID (`privatelink-vpce-id`) and the hostnames to resolve, such as `privatelink-account-url`, `regionless-snowsight-privatelink-url`, and OCSP cache hostnames.
3. **Create the endpoint** and a security group allowing ports 443 and 80 (port 80 is used by the OCSP cache server).
4. **Configure DNS.** Create CNAME records mapping each hostname from the config output to the endpoint's DNS name. Records must resolve to private IPs inside your network.
5. **Connect** using the privatelink URLs.

### Architecture decisions

- **Public access stays open by default.** To force private-only access, activate a network policy whose allowed list contains `AWSVPCEID` or `AZURELINKID` network rules. For private-connectivity requests, those rule types take precedence over IPv4 rules.
- **Internal stages are separate.** On AWS, protecting internal stages requires S3 private connectivity and a network rule with `MODE = INTERNAL_STAGE` and `TYPE = AWSVPCEID`.
- **Identity URLs change.** SAML integrations must use the PrivateLink URL in `SAML2_SNOWFLAKE_ISSUER_URL` and `SAML2_SNOWFLAKE_ACS_URL` if users log in through it.
- **Hybrid networks.** On AWS, on-premises environments can combine AWS Direct Connect (a separate AWS service) with PrivateLink; the privatelink hostnames must be resolvable from on-premises DNS resolvers.
- **Tri-Secret Secure** can also use private connectivity to reach your KMS (`SYSTEM$PROVISION_PRIVATELINK_ENDPOINT_TSS`).

## Example

Authorize and inspect AWS PrivateLink:

```sql
USE ROLE ACCOUNTADMIN;

SELECT SYSTEM$AUTHORIZE_PRIVATELINK('123456789012', '<federated_token_json>');
SELECT SYSTEM$GET_PRIVATELINK();

SELECT key, value
FROM TABLE(FLATTEN(INPUT => PARSE_JSON(SYSTEM$GET_PRIVATELINK_CONFIG())));
```

Make the account private-only once DNS and endpoints are tested:

```sql
CREATE NETWORK RULE security.net.corp_vpce
  MODE = INGRESS
  TYPE = AWSVPCEID
  VALUE_LIST = ('vpce-0fa383eb170331202');

CREATE NETWORK POLICY private_only
  ALLOWED_NETWORK_RULE_LIST = ('security.net.corp_vpce');

ALTER USER test_admin SET NETWORK_POLICY = private_only;   -- test first
ALTER ACCOUNT SET NETWORK_POLICY = private_only;           -- then enforce
```

## Best practices

- Treat DNS as the critical path: automate CNAME records from `SYSTEM$GET_PRIVATELINK_CONFIG` output.
- Validate private-only access on one user before setting the account policy.
- Allow the OCSP hostnames and port 80 to avoid certificate-validation failures.
- Document the endpoint IDs used in network rules, and update rules when endpoints are recreated.

## Common pitfalls

- Assuming PrivateLink blocks public internet access - it does not without a network policy.
- DNS records resolving to public IPs, which silently sends traffic over the internet.
- Forgetting SAML issuer/ACS URLs, which breaks SSO after the cutover.
- Letting the 12-hour federated token expire mid-process.

## Learn more

- [AWS PrivateLink and Snowflake](https://docs.snowflake.com/en/user-guide/admin-security-privatelink)
- [Controlling network traffic with network policies](https://docs.snowflake.com/en/user-guide/network-policies)

## Knowledge check

### After enabling AWS PrivateLink, an auditor shows that the account is still reachable from the internet. What is missing?
- [ ] A second VPC endpoint
- [x] A network policy whose allowed list contains AWSVPCEID network rules
- [ ] Tri-Secret Secure
- [ ] Re-running SYSTEM$AUTHORIZE_PRIVATELINK
> PrivateLink adds a private path but does not close the public one; a network policy restricting access to your VPC endpoint IDs does.

### Clients connect through PrivateLink but intermittently fail certificate checks. What should you check?
- [ ] Whether the warehouse is suspended
- [x] DNS and firewall rules for the OCSP cache hostnames and port 80
- [ ] The SCIM integration
- [ ] Whether the user has MFA enabled
> The OCSP cache server listens on port 80 and has its own privatelink hostname that must resolve privately and be allowed.

### Users log in through Okta SSO. After switching to PrivateLink URLs, SSO fails. Which change is required?
- [ ] Create a new Okta tenant
- [ ] Use External OAuth instead
- [x] Update SAML2_SNOWFLAKE_ISSUER_URL and SAML2_SNOWFLAKE_ACS_URL to the PrivateLink URL and match them in the IdP
- [ ] Enable SAML2_FORCE_AUTHN
> The issuer and ACS URLs must match the URL users connect through, including PrivateLink URLs.
