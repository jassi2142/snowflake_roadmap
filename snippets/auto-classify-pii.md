# Auto-classify PII and tag it with your own tags

topics: classification, tagging, tag-based-masking
tags: governance, classification, pii
level: intermediate

Have Snowflake find sensitive columns for you. First run a one-off `SYSTEM$CLASSIFY` to test, then attach a classification profile to a database so new and changed tables are classified in the background. A tag map converts the detected semantic categories into your own `pii_level` tag, so tag-based masking protects new columns without anyone tagging them by hand.

```sql
-- 0. One-time grants (as ACCOUNTADMIN) for the data engineer role
USE ROLE ACCOUNTADMIN;
GRANT DATABASE ROLE SNOWFLAKE.CLASSIFICATION_ADMIN TO ROLE data_engineer;
GRANT EXECUTE AUTO CLASSIFICATION ON DATABASE my_db TO ROLE data_engineer;
GRANT CREATE SNOWFLAKE.DATA_PRIVACY.CLASSIFICATION_PROFILE ON SCHEMA my_db.governance TO ROLE data_engineer;
GRANT APPLY TAG ON ACCOUNT TO ROLE data_engineer;

USE ROLE data_engineer;
USE SCHEMA my_db.governance;

-- 1. Ad hoc: classify one table and review the result (no tags set)
CALL SYSTEM$CLASSIFY('my_db.crm.customers', {'sample_count': 1000});

-- 2. Profile: classify tables right away, reclassify every 30 days,
--    set system tags, and map categories to the user-defined tag pii_level
CREATE OR REPLACE SNOWFLAKE.DATA_PRIVACY.CLASSIFICATION_PROFILE pii_profile({
  'minimum_object_age_for_classification_days': 0,
  'maximum_classification_validity_days': 30,
  'auto_tag': true,
  'tag_map': {
    'column_tag_map': [
      {'tag_name': 'my_db.governance.pii_level', 'tag_value': 'restricted',
       'semantic_categories': ['NATIONAL_IDENTIFIER', 'TAX_IDENTIFIER', 'PASSPORT']},
      {'tag_name': 'my_db.governance.pii_level', 'tag_value': 'confidential',
       'semantic_categories': ['NAME', 'EMAIL', 'PHONE_NUMBER']}
    ]
  }
});

SELECT pii_profile!DESCRIBE();

-- 3. Dry run the profile on one table: the "tags" array shows what would be set
CALL SYSTEM$CLASSIFY('my_db.crm.customers', 'my_db.governance.pii_profile');

-- 4. Turn on automatic classification for the whole database (starts after about 1 hour)
ALTER DATABASE my_db SET CLASSIFICATION_PROFILE = 'my_db.governance.pii_profile';

-- 5. Later: read the latest result for a table
CALL SYSTEM$GET_CLASSIFICATION_RESULT('my_db.crm.customers');

-- Stop automatic classification
-- ALTER DATABASE my_db UNSET CLASSIFICATION_PROFILE;
```

## Notes
- Requires Enterprise Edition or higher. Using `auto_tag` with `SYSTEM$CLASSIFY` requires a role with OWNERSHIP on the schema.
- The `pii_level` tag must already exist (see `tag-based-masking`). Attach masking policies to it so that columns tagged by classification are masked straight away.
- Setting `minimum_object_age_for_classification_days` or `maximum_classification_validity_days` switches the profile from Autopilot to custom scheduling. Omit both to let Snowflake choose when to classify.
- If a tag was set manually and conflicts with a tag that automatic classification wants to apply, Snowflake records an error. Review results and errors in Trust Center.
- Optional AI mode (`'ai_mode': true`) uses LLMs, billed under the AI_SENSITIVE_DATA_CLASSIFICATION service type.

## References
- [Use SQL to set up sensitive data classification](https://docs.snowflake.com/en/user-guide/classify-auto)
- [SYSTEM$CLASSIFY](https://docs.snowflake.com/en/sql-reference/stored-procedures/system_classify)
- [Native semantic categories](https://docs.snowflake.com/en/user-guide/classify-native)
