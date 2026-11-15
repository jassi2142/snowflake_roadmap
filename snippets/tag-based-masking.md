# Tag-based masking: one tag, every PII column protected

topics: tag-based-masking, tagging, masking
tags: governance, masking, tagging, abac
level: advanced

Rather than attaching a masking policy to each column, attach policies to a tag, then tag the columns, or a whole schema. Any column with the tag whose data type matches a policy on the tag is masked automatically, including columns added later. The policy reads the tag value, so one policy can mask differently for each sensitivity level.

```sql
USE ROLE governance_admin;   -- needs CREATE TAG, CREATE MASKING POLICY, APPLY MASKING POLICY, APPLY TAG
USE SCHEMA my_db.governance;

-- 1. Tag with a controlled vocabulary
CREATE TAG IF NOT EXISTS pii_level
  ALLOWED_VALUES 'restricted', 'confidential'
  COMMENT = 'Sensitivity of personal data in a column';

-- 2. One policy per data type. The policy reads the tag value on the column it is masking.
CREATE OR REPLACE MASKING POLICY pii_string_mask
  AS (val STRING) RETURNS STRING ->
  CASE
    WHEN IS_ROLE_IN_SESSION('PII_ADMIN') THEN val
    WHEN SYSTEM$GET_TAG_ON_CURRENT_COLUMN('my_db.governance.pii_level') = 'confidential'
         AND IS_ROLE_IN_SESSION('PII_READER') THEN val
    ELSE '***MASKED***'
  END;

CREATE OR REPLACE MASKING POLICY pii_number_mask
  AS (val NUMBER) RETURNS NUMBER ->
  CASE WHEN IS_ROLE_IN_SESSION('PII_ADMIN') THEN val ELSE NULL END;

-- 3. Attach both policies to the tag (at most one policy per data type per tag)
ALTER TAG pii_level SET
  MASKING POLICY pii_string_mask,
  MASKING POLICY pii_number_mask;

-- 4a. Tag individual columns...
ALTER TABLE my_db.crm.customers MODIFY COLUMN
  email     SET TAG my_db.governance.pii_level = 'confidential',
  ssn       SET TAG my_db.governance.pii_level = 'restricted';

-- 4b. ...or tag a whole schema: every STRING/NUMBER column in it inherits the protection
-- ALTER SCHEMA my_db.hr SET TAG my_db.governance.pii_level = 'restricted';

-- 5. Verify which policies apply to the table, and through which tag
SELECT ref_column_name, policy_name, tag_name, policy_status
FROM TABLE(my_db.INFORMATION_SCHEMA.POLICY_REFERENCES(
       REF_ENTITY_DOMAIN => 'TABLE',
       REF_ENTITY_NAME   => 'my_db.crm.customers'));

-- Clean up: unset tags from objects, then unset the policies from the tag
-- ALTER TABLE my_db.crm.customers MODIFY COLUMN email UNSET TAG my_db.governance.pii_level;
-- ALTER TAG my_db.governance.pii_level UNSET MASKING POLICY pii_string_mask, MASKING POLICY pii_number_mask;
```

## Notes
- Requires Enterprise Edition or higher. Setting a policy on a tag needs APPLY MASKING POLICY on the account. Setting the tag needs APPLY TAG on the account, or APPLY on that tag.
- A masking policy assigned directly to a column overrides the tag-based one.
- A tag can't be dropped while a policy is assigned to it, and a policy can't be dropped while it is assigned to a tag.
- Masking policies can't be assigned to system tags. To combine this with auto-classification, map classification results to your own tag (see the `auto-classify-pii` snippet).

## References
- [Tag-based masking policies](https://docs.snowflake.com/en/user-guide/tag-based-masking-policies)
- [Attribute-based access control using tag-based policies](https://docs.snowflake.com/en/user-guide/tag-based-policies)
- [SYSTEM$GET_TAG_ON_CURRENT_COLUMN](https://docs.snowflake.com/en/sql-reference/functions/system_get_tag_on_current_column)
