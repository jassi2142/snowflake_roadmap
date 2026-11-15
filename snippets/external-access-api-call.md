# Call a REST API from a Python UDF with external access

topics: external-access, udfs, network-policies
tags: python, api, secrets, egress
level: advanced

UDFs and procedures cannot reach the internet by default. A network rule names the allowed host, a secret holds the API key, and an external access integration links them so a specific function can call the API.

```sql
USE ROLE my_admin_role;   -- CREATE INTEGRATION is account-level (ACCOUNTADMIN or a delegated role)
USE SCHEMA my_db.my_schema;

-- 1. Egress rule: which host(s) may be called
CREATE OR REPLACE NETWORK RULE weather_api_rule
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('api.example-weather.com');

-- 2. Secret holding the API key
CREATE OR REPLACE SECRET weather_api_key
  TYPE = GENERIC_STRING
  SECRET_STRING = 'replace-with-real-key';

-- 3. Integration that ties rule + secret together
CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION weather_api_int
  ALLOWED_NETWORK_RULES = (weather_api_rule)
  ALLOWED_AUTHENTICATION_SECRETS = (weather_api_key)
  ENABLED = TRUE;

-- Let the developer role use them
GRANT USAGE ON INTEGRATION weather_api_int TO ROLE my_dev_role;
GRANT READ ON SECRET weather_api_key TO ROLE my_dev_role;

-- 4. Python UDF that calls the API
CREATE OR REPLACE FUNCTION get_temperature(city STRING)
  RETURNS FLOAT
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.12'
  HANDLER = 'get_temp'
  PACKAGES = ('requests')
  EXTERNAL_ACCESS_INTEGRATIONS = (weather_api_int)
  SECRETS = ('api_key' = weather_api_key)
AS
$$
import _snowflake
import requests

session = requests.Session()   # reuse connections across rows

def get_temp(city):
    key = _snowflake.get_generic_secret_string('api_key')
    resp = session.get(
        'https://api.example-weather.com/v1/current',
        params={'city': city},
        headers={'Authorization': f'Bearer {key}'},
        timeout=10,
    )
    resp.raise_for_status()
    return float(resp.json()['temp_c'])
$$;

SELECT city, get_temperature(city) AS temp_c
FROM (SELECT column1 AS city FROM VALUES ('Berlin'), ('Tokyo'));
```

## Notes
- Requests to any host not listed in the network rule are blocked. Keep `VALUE_LIST` as narrow as you can; you can append a port, e.g. `'host:443'`.
- The UDF runs once per row, so a large table means many API calls. Check the API's rate limits, or call it from a stored procedure that batches requests.
- Inside the handler, read secrets with `_snowflake.get_generic_secret_string` using the alias defined in `SECRETS`. Never log secret values.
- Clean up with `DROP FUNCTION get_temperature(STRING)`, then drop the integration, secret and network rule.

## References
- [External network access overview](https://docs.snowflake.com/en/developer-guide/external-network-access/external-network-access-overview)
- [CREATE EXTERNAL ACCESS INTEGRATION](https://docs.snowflake.com/en/sql-reference/sql/create-external-access-integration)
- [CREATE NETWORK RULE](https://docs.snowflake.com/en/sql-reference/sql/create-network-rule)
