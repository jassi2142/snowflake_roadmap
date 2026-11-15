# Send a Microsoft Teams message from Snowflake

topics: alerts, external-access
tags: alerting, notifications, teams, webhook
level: intermediate

Notify a Microsoft Teams channel from SQL through a Teams workflow (Power Automate) webhook. A Teams workflow URL carries its own signature, so the full URL goes into the integration.

```sql
USE ROLE accountadmin;          -- or a role with CREATE INTEGRATION on the account
USE SCHEMA my_db.my_schema;

-- 1. Paste the full workflow URL from Teams ("Post to a channel when a webhook request is received").
--    Remove any ":443" port from the host if present.
CREATE OR REPLACE NOTIFICATION INTEGRATION teams_alerts_int
  TYPE = WEBHOOK
  ENABLED = TRUE
  WEBHOOK_URL = 'https://my-tenant.westus.logic.azure.com/workflows/abc123/triggers/manual/paths/invoke?api-version=2016-06-01&sig=XXXX'
  WEBHOOK_BODY_TEMPLATE = '{"text": "SNOWFLAKE_WEBHOOK_MESSAGE"}'
  WEBHOOK_HEADERS = ('Content-Type'='application/json');

GRANT USAGE ON INTEGRATION teams_alerts_int TO ROLE my_pipeline_role;

-- 2. Send a test message
CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
  SNOWFLAKE.NOTIFICATION.TEXT_PLAIN(
    SNOWFLAKE.NOTIFICATION.SANITIZE_WEBHOOK_CONTENT('Warehouse credit usage exceeded today''s threshold')
  ),
  SNOWFLAKE.NOTIFICATION.INTEGRATION('teams_alerts_int')
);
```

## Notes
- The body shape your Teams workflow expects depends on how the flow is built; adjust `WEBHOOK_BODY_TEMPLATE` to match (for example an Adaptive Card payload).
- The sending role needs USAGE on the integration.
- Treat the workflow URL as a credential: anyone with it can post to the channel. Limit who can DESCRIBE or own the integration.
- Clean up with `DROP NOTIFICATION INTEGRATION teams_alerts_int;`.

## References
- [Sending webhook notifications](https://docs.snowflake.com/en/user-guide/notifications/webhook-notifications)
- [CREATE NOTIFICATION INTEGRATION (webhooks)](https://docs.snowflake.com/en/sql-reference/sql/create-notification-integration-webhooks)
