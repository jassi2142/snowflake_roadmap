# Find inactive users and generate DISABLE statements

topics: account-usage, authentication, scim
tags: security, user-management, audit
level: intermediate

List users who haven't logged in for 90 days (or who never logged in after their account was created), and generate `ALTER USER ... SET DISABLED = TRUE` statements to review. The query only produces the statements: nothing is disabled until you run them yourself.

```sql
USE ROLE USERADMIN;      -- or SECURITYADMIN; reading ACCOUNT_USAGE also needs IMPORTED PRIVILEGES on SNOWFLAKE
USE WAREHOUSE my_wh;

SET inactive_days = 90;

-- 1. Review list. Users who never logged in are measured from their creation date.
SELECT
  name,
  login_name,
  type,                                          -- PERSON, SERVICE, LEGACY_SERVICE, or NULL
  owner,
  created_on,
  last_success_login,
  DATEDIFF(day, COALESCE(last_success_login, created_on), CURRENT_TIMESTAMP()) AS days_inactive,
  'ALTER USER "' || REPLACE(name, '"', '""') || '" SET DISABLED = TRUE;'      AS disable_stmt
FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
WHERE deleted_on IS NULL
  AND disabled = FALSE
  AND COALESCE(last_success_login, created_on) < DATEADD(day, -$inactive_days, CURRENT_TIMESTAMP())
  AND name NOT IN ('SNOWFLAKE')                  -- add break-glass admins and known exceptions here
ORDER BY days_inactive DESC;

-- 2. Cross-check: successful logins per user in the same window, from LOGIN_HISTORY.
--    Anyone listed here is active and should not be in step 1.
SELECT user_name, MAX(event_timestamp) AS last_login_event
FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
WHERE is_success = 'YES'
  AND event_timestamp >= DATEADD(day, -$inactive_days, CURRENT_TIMESTAMP())
GROUP BY user_name;

-- 3. After review, copy the disable_stmt values and run them, for example:
-- ALTER USER "JDOE" SET DISABLED = TRUE;

-- Re-enable if needed
-- ALTER USER "JDOE" SET DISABLED = FALSE;
```

## Notes
- `SNOWFLAKE.ACCOUNT_USAGE.USERS` can lag by up to about 2 hours. Use `SHOW USERS` if you need current values.
- Disabling blocks the user from logging in. It doesn't drop the user, their objects or their grants, so it's easy to undo.
- If users are provisioned through SCIM, manage their lifecycle in the identity provider so the two systems don't disagree.
- Generate the statements with the query, but don't run them automatically. Have a person review the list first, especially for service accounts that run rarely, such as quarter-end jobs.
- The double-quote escaping in `disable_stmt` keeps names with special characters or mixed case working.

## References
- [USERS view](https://docs.snowflake.com/en/sql-reference/account-usage/users)
- [LOGIN_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/login_history)
- [ALTER USER](https://docs.snowflake.com/en/sql-reference/sql/alter-user)
