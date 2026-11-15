# Layer masking, row access, projection and aggregation policies on one table

topics: privacy-policies, masking, row-access
tags: governance, privacy, data-sharing
level: advanced

Protect a patient-visits table at several levels at once: a row access policy limits which clinics a role can see, a masking policy hides patient names, a projection policy stops partner roles from selecting the ZIP code (they can still filter on it), and an aggregation policy forces partner roles to query in groups of at least 10 rows.

```sql
USE ROLE policy_admin;
USE SCHEMA my_db.governance;

-- Row access: internal roles see everything, partners see only clinics shared with them
CREATE OR REPLACE ROW ACCESS POLICY clinic_rap
  AS (clinic_id NUMBER) RETURNS BOOLEAN ->
  IS_ROLE_IN_SESSION('CLINICAL_STAFF')
  OR (IS_ROLE_IN_SESSION('PARTNER_ANALYST') AND clinic_id IN (101, 102));

-- Masking: only clinical staff see names
CREATE OR REPLACE MASKING POLICY name_mask
  AS (val STRING) RETURNS STRING ->
  CASE WHEN IS_ROLE_IN_SESSION('CLINICAL_STAFF') THEN val ELSE '***' END;

-- Projection: non-clinical roles can filter or join on ZIP but not select it
CREATE OR REPLACE PROJECTION POLICY zip_projection
  AS () RETURNS PROJECTION_CONSTRAINT ->
  CASE
    WHEN IS_ROLE_IN_SESSION('CLINICAL_STAFF') THEN PROJECTION_CONSTRAINT(ALLOW => true)
    ELSE PROJECTION_CONSTRAINT(ALLOW => false)
  END;

-- Aggregation: non-clinical roles must aggregate, with at least 10 rows per group
CREATE OR REPLACE AGGREGATION POLICY min_group_10
  AS () RETURNS AGGREGATION_CONSTRAINT ->
  CASE
    WHEN IS_ROLE_IN_SESSION('CLINICAL_STAFF') THEN NO_AGGREGATION_CONSTRAINT()
    ELSE AGGREGATION_CONSTRAINT(MIN_GROUP_SIZE => 10)
  END;

-- Attach all four. Row access and aggregation policies go on the table; masking and projection go on columns.
ALTER TABLE my_db.clinical.visits ADD ROW ACCESS POLICY clinic_rap ON (clinic_id);
ALTER TABLE my_db.clinical.visits MODIFY COLUMN patient_name SET MASKING POLICY name_mask;
ALTER TABLE my_db.clinical.visits MODIFY COLUMN zip_code SET PROJECTION POLICY zip_projection;
ALTER TABLE my_db.clinical.visits SET AGGREGATION POLICY min_group_10;

-- As PARTNER_ANALYST:
USE ROLE partner_analyst;
SELECT diagnosis_code, COUNT(*) AS visits          -- allowed: aggregated, clinic 101/102 rows only
FROM my_db.clinical.visits
WHERE zip_code LIKE '941%'                         -- allowed: filtering on a projection-constrained column
GROUP BY diagnosis_code;                           -- groups under 10 rows are combined into a remainder group

-- SELECT zip_code, patient_name FROM my_db.clinical.visits;   -- fails: needs aggregation, and zip_code can't be projected

-- See everything attached to the table
SELECT policy_kind, policy_name, ref_column_name, policy_status
FROM TABLE(my_db.INFORMATION_SCHEMA.POLICY_REFERENCES(
       REF_ENTITY_DOMAIN => 'TABLE', REF_ENTITY_NAME => 'my_db.clinical.visits'));
```

## Notes
- Requires Enterprise Edition or higher. Each policy type has its own CREATE and APPLY privileges, for example APPLY AGGREGATION POLICY on the account.
- Snowflake evaluates the policies in this order: it filters rows with the row access policy, rejects the query if it projects a constrained column, then applies masks.
- A projection policy's body can't reference a column protected by a masking policy, or a table protected by a row access policy. Equally, a projection-constrained column can't be one of the row access policy's arguments or a conditional masking column. Keep these columns separate, as here.
- Projection and aggregation policies reduce exposure but don't guarantee anonymity: a determined user can still narrow results with targeted filters. Combine them with trusted consumers and access-history reviews.
- To remove them: `ALTER TABLE ... UNSET AGGREGATION POLICY`, `... MODIFY COLUMN ... UNSET PROJECTION POLICY`, `... UNSET MASKING POLICY`, `... DROP ROW ACCESS POLICY clinic_rap`.

## References
- [Projection policies](https://docs.snowflake.com/en/user-guide/projection-policies)
- [Aggregation policies](https://docs.snowflake.com/en/user-guide/aggregation-policies)
- [Understanding row access policies](https://docs.snowflake.com/en/user-guide/security-row-intro)
- [Understanding Dynamic Data Masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro)
