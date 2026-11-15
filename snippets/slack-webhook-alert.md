# Send a Slack message from Snowflake with a webhook

topics: alerts, external-access
tags: alerting, notifications, slack, webhook
level: intermediate

Post messages to a Slack channel directly from SQL using a webhook notification integration. The secret part of the Slack webhook URL is stored in a Snowflake secret so it never appears in the integration definition.

```sql
USE ROLE accountadmin;          -- or a role with CREATE INTEGRATION on the account
USE SCHEMA my_db.my_schema;

-- 1. Store the secret part of the Slack URL (everything after /services/)
CREATE OR REPLACE SECRET my_db.my_schema.slack_webhook_secret
  TYPE = GENERIC_STRING
  SECRET_STRING = 'T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX';

-- 2. Create the webhook integration; SNOWFLAKE_WEBHOOK_SECRET is replaced by the secret,
--    SNOWFLAKE_WEBHOOK_MESSAGE by the message you send
CREATE OR REPLACE NOTIFICATION INTEGRATION slack_alerts_int
  TYPE = WEBHOOK
  ENABLED = TRUE
  WEBHOOK_URL = 'https://hooks.slack.com/services/SNOWFLAKE_WEBHOOK_SECRET'
  WEBHOOK_SECRET = my_db.my_schema.slack_webhook_secret
  WEBHOOK_BODY_TEMPLATE = '{"text": "SNOWFLAKE_WEBHOOK_MESSAGE"}'
  WEBHOOK_HEADERS = ('Content-Type'='application/json');

-- 3. Let the role that sends messages use the integration and read the secret
GRANT USAGE ON INTEGRATION slack_alerts_int TO ROLE my_pipeline_role;
GRANT READ ON SECRET my_db.my_schema.slack_webhook_secret TO ROLE my_pipeline_role;

-- 4. Send a message (sanitize to escape quotes and other characters that break the JSON body)
CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
  SNOWFLAKE.NOTIFICATION.TEXT_PLAIN(
    SNOWFLAKE.NOTIFICATION.SANITIZE_WEBHOOK_CONTENT('Nightly load finished: 12,345 rows')
  ),
  SNOWFLAKE.NOTIFICATION.INTEGRATION('slack_alerts_int')
);
```

## Notes
- Create an incoming webhook in your Slack app first; only the path after `/services/` goes in the secret.
- The sending role needs USAGE on the integration and READ on the secret (plus USAGE on the secret's database and schema).
- The same `CALL` works inside a task, stored procedure, or alert action.
- Clean up with `DROP NOTIFICATION INTEGRATION slack_alerts_int;` and `DROP SECRET my_db.my_schema.slack_webhook_secret;`.

## References
- [Sending webhook notifications](https://docs.snowflake.com/en/user-guide/notifications/webhook-notifications)
- [CREATE NOTIFICATION INTEGRATION (webhooks)](https://docs.snowflake.com/en/sql-reference/sql/create-notification-integration-webhooks)
- [SYSTEM$SEND_SNOWFLAKE_NOTIFICATION](https://docs.snowflake.com/en/sql-reference/stored-procedures/system_send_snowflake_notification)
