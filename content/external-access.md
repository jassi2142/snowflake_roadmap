# External Network Access

External network access lets code running inside Snowflake, such as Python, Java, or Scala UDFs and stored procedures, call endpoints outside Snowflake: REST APIs, SaaS services, package hubs, or your own services. It is built from three governed objects (network rules, secrets, and external access integrations) so that egress is explicit, auditable, and controlled by administrators rather than by whoever writes handler code.

## How it works

By default, handler code has no outbound network access. Enabling it is a layered design that separates **who defines where traffic can go** from **who writes code that uses it**:

1. **Network rule** (`CREATE NETWORK RULE`, schema-level): with `MODE = EGRESS` and `TYPE = HOST_PORT` (or `PRIVATE_HOST_PORT` for private connectivity), `VALUE_LIST` names allowed hosts and optional ports. If you omit a port, 443 is used. Requires `CREATE NETWORK RULE` on the schema.
2. **Secret** (`CREATE SECRET`, schema-level): holds credentials, for example `TYPE = GENERIC_STRING` for an API key, `TYPE = PASSWORD`, or `TYPE = OAUTH2` referencing a security integration. Requires `CREATE SECRET` on the schema.
3. **External access integration** (`CREATE EXTERNAL ACCESS INTEGRATION`, account-level): aggregates `ALLOWED_NETWORK_RULES` and `ALLOWED_AUTHENTICATION_SECRETS` and can be enabled or disabled as a kill switch. Requires `CREATE INTEGRATION` on the account plus `USAGE` on referenced secrets.
4. **Function or procedure**: declares `EXTERNAL_ACCESS_INTEGRATIONS = (...)` and `SECRETS = ('alias' = secret_name)`. The creating role needs `USAGE` on the integration and `READ` on the secret. Handler code retrieves credentials through the `_snowflake` module (for example `_snowflake.get_generic_secret_string('alias')` or `_snowflake.get_oauth_access_token('alias')`); requests to hosts not in an allowed rule are denied.

**Private connectivity.** Traffic can go over the public internet or through AWS PrivateLink, Azure Private Link, or Google Cloud Private Service Connect. Private connectivity for outbound traffic requires Business Critical Edition or higher, ACCOUNTADMIN for setup, and incurs additional charges.

**Observability.** Administrators can audit requests through the `EXTERNAL_ACCESS_HISTORY` Account Usage view.

**Design trade-offs.**

- Fine-grained integrations (one per external system) give clear blast-radius control and simpler audits, at the cost of more objects.
- Because only those with `READ` on a secret can build functions that use it, secrets become the real authorization boundary; keep secret ownership in a platform role.
- Owner's-rights procedures that use an integration let you expose a vetted capability (for example "post to Slack") without granting broad egress to callers.
- Snowflake limits the number of connections a UDF can make, so reuse a client or session created once at module load instead of per row.

## Example

Allow a Python UDF to call a weather API with an API key.

```sql
CREATE OR REPLACE NETWORK RULE platform.net.weather_api_rule
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('api.weather.example.com');

CREATE OR REPLACE SECRET platform.net.weather_api_key
  TYPE = GENERIC_STRING
  SECRET_STRING = 'replace-with-api-key';

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION weather_api_eai
  ALLOWED_NETWORK_RULES = (platform.net.weather_api_rule)
  ALLOWED_AUTHENTICATION_SECRETS = (platform.net.weather_api_key)
  ENABLED = TRUE;

GRANT USAGE ON INTEGRATION weather_api_eai TO ROLE data_engineer;
GRANT READ ON SECRET platform.net.weather_api_key TO ROLE data_engineer;

CREATE OR REPLACE FUNCTION analytics.udf.current_temp(city STRING)
RETURNS FLOAT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
HANDLER = 'get_temp'
EXTERNAL_ACCESS_INTEGRATIONS = (weather_api_eai)
SECRETS = ('api_key' = platform.net.weather_api_key)
PACKAGES = ('requests')
AS
$$
import _snowflake
import requests

session = requests.Session()

def get_temp(city):
    key = _snowflake.get_generic_secret_string('api_key')
    r = session.get("https://api.weather.example.com/v1/current",
                    params={"q": city}, headers={"X-API-Key": key}, timeout=10)
    r.raise_for_status()
    return r.json()["temp_c"]
$$;
```

## Best practices

- Allowlist exact hostnames; avoid broad wildcards.
- Store every credential in a secret, never as a literal in handler code.
- Keep network rules and secrets in a dedicated, tightly owned schema and create integrations through a platform role.
- Reuse HTTP sessions, set timeouts, and handle retries; calling an API once per row at scale is slow and can hit rate limits.
- Prefer procedures over UDFs for bulk API calls so you control batching.
- Audit with `EXTERNAL_ACCESS_HISTORY` and disable integrations quickly with `ENABLED = FALSE` during incidents.

## Common pitfalls

- Forgetting to list the secret in both the integration and the function's `SECRETS` clause.
- Granting `USAGE` on the integration but not `READ` on the secret, or vice versa.
- Assuming private connectivity works on Standard or Enterprise edition.
- Calling external APIs inside per-row UDFs on large tables, multiplying latency and cost.

## Learn more

- [Creating and using an external access integration](https://docs.snowflake.com/en/developer-guide/external-network-access/creating-using-external-network-access)
- [External network access examples](https://docs.snowflake.com/en/developer-guide/external-network-access/external-network-access-examples)
- [CREATE EXTERNAL ACCESS INTEGRATION](https://docs.snowflake.com/en/sql-reference/sql/create-external-access-integration)

## Knowledge check

### Security wants developers to call only an approved CRM API, and wants the ability to cut off access instantly without redeploying code. What design meets both goals?
- [ ] Give developers ACCOUNTADMIN and ask them to use only the CRM host
- [x] A platform-owned network rule and secret in an integration granted to developers, which admins can set ENABLED = FALSE
- [ ] Hard-code the API key in each UDF and rotate it during incidents
- [ ] Use a network policy with ALLOWED_IP_LIST
> The integration restricts egress to approved rules and secrets, and disabling it immediately blocks all functions that use it.

### A company on Enterprise Edition wants UDF traffic to a vendor to traverse AWS PrivateLink instead of the internet. What is the blocker?
- [ ] Network rules cannot use HOST_PORT
- [ ] Python UDFs cannot use external access
- [x] Private connectivity for outbound traffic requires Business Critical Edition or higher
- [ ] Secrets cannot be used with PrivateLink
> Outbound private connectivity requires Business Critical (or higher), ACCOUNTADMIN setup, and has additional cost.

### A UDF enriching 50 million rows creates a new HTTPS connection per row and starts failing. What is the best fix?
- [ ] Add more network rules
- [ ] Increase the warehouse size
- [x] Create the HTTP client once at module scope, batch calls (ideally in a procedure), and add timeouts and retries
- [ ] Switch the secret to TYPE = PASSWORD
> Snowflake limits connections per UDF; reusing connections and batching reduce resource exhaustion and API load.
