# Route support tickets with AI_CLASSIFY

topics: cortex-ai-functions
tags: ai, classification, support
level: beginner

Sort incoming support tickets into queues without training a model. AI_CLASSIFY takes the text and a list of categories, and can also take label descriptions, a task description, and multi-label mode.

```sql
USE ROLE my_ai_role;   -- needs SNOWFLAKE.CORTEX_USER
USE WAREHOUSE my_wh;

CREATE OR REPLACE TEMPORARY TABLE tickets (ticket_id INT, body STRING);
INSERT INTO tickets VALUES
  (101, 'I was charged twice for my subscription this month.'),
  (102, 'The mobile app crashes every time I open the settings page.'),
  (103, 'How do I add a second user to my account? Also my last invoice looks wrong.');

-- 1. Simple single-label classification
SELECT
  ticket_id,
  AI_CLASSIFY(body, ['billing', 'technical issue', 'account management']):labels[0]::STRING AS queue
FROM tickets;

-- 2. Descriptions, task description and multi-label output
SELECT
  ticket_id,
  AI_CLASSIFY(
    body,
    [
      {'label': 'billing',            'description': 'charges, invoices, refunds, payment methods'},
      {'label': 'technical issue',    'description': 'errors, crashes, bugs, performance problems'},
      {'label': 'account management', 'description': 'users, permissions, login, profile settings'}
    ],
    {
      'task_description': 'Assign customer support tickets to every team that must respond',
      'output_mode': 'multi'
    }
  ):labels AS queues
FROM tickets;

-- 3. Persist the routing result (one row per ticket/queue pair)
CREATE OR REPLACE TEMPORARY TABLE ticket_routing AS
SELECT t.ticket_id, q.value::STRING AS queue
FROM tickets t,
     LATERAL FLATTEN(
       input => AI_CLASSIFY(t.body, ['billing', 'technical issue', 'account management'],
                            {'output_mode': 'multi'}):labels
     ) q;

SELECT * FROM ticket_routing ORDER BY ticket_id;
```

## Notes
- Requires the `SNOWFLAKE.CORTEX_USER` database role.
- The result is an object with a `labels` array; single-label mode returns exactly one element.
- Categories are case sensitive. Use clear, mutually exclusive labels. Descriptions (25 words max each) improve accuracy but add input tokens to every call.
- On errors the function returns NULL for that row; pass `TRUE` as the fourth argument to get error details.

## References
- [AI_CLASSIFY](https://docs.snowflake.com/en/sql-reference/functions/ai_classify)
- [Snowflake Cortex AI Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql)
