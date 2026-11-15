# Data Classification

Sensitive data classification automatically scans tables and views to detect columns containing personal or sensitive information, such as names, email addresses, and national identifiers. It labels those columns with system tags and can apply your own tags, which in turn can trigger masking policies. Knowing where sensitive data lives is a prerequisite for protecting it and for meeting regulatory requirements.

## How it works

Sensitive data classification requires **Enterprise Edition or higher** and runs on serverless compute, so it consumes credits (shown as service type `SENSITIVE_DATA_CLASSIFICATION` in metering views).

### Categories and system tags

Each column identified as sensitive receives two categories:

- **Semantic category:** the type of data, such as `NAME`, `EMAIL`, `NATIONAL_IDENTIFIER`, or `TAX_IDENTIFIER`. Snowflake provides native categories, and you can define **custom classifiers** for domain-specific data such as internal medical or finance codes.
- **Privacy category:** the sensitivity: `IDENTIFIER`, `QUASI_IDENTIFIER`, or `SENSITIVE` (for example salary or health data).

These are recorded with the system tags `SNOWFLAKE.CORE.SEMANTIC_CATEGORY` and `SNOWFLAKE.CORE.PRIVACY_CATEGORY`.

### Classification profiles

A **classification profile** (an instance of `SNOWFLAKE.DATA_PRIVACY.CLASSIFICATION_PROFILE`) defines how classification behaves:

- Whether tags are applied automatically (`auto_tag`) or proposed for review.
- A **tag map** that maps semantic categories to your own tags, for example `NAME` to `pii = 'Highly Confidential'`.
- Which native categories (and, for some, which country codes) to detect.
- Whether views are classified (`classify_views`); views are excluded by default and can cost more than tables.
- Scheduling. **Autopilot** is the default: Snowflake classifies new objects shortly after creation and reclassifies on its own cadence. Setting `minimum_object_age_for_classification_days` or `maximum_classification_validity_days` switches to custom scheduling.
- Optional **AI mode**, which uses an LLM to find additional semantic categories and incurs token charges.

You attach a profile to a database (or a schema, which overrides the database setting) with `ALTER DATABASE ... SET CLASSIFICATION_PROFILE`. There is a one-hour delay before classification begins. You can also configure all of this in the **Trust Center** in Snowsight.

### Scope and limits

Supported: standard, external, Iceberg, dynamic, and event tables, plus views, materialized views, and secure views. Unsupported column types include `BINARY`, `GEOGRAPHY`, `VECTOR`, `UUID`, and `DECFLOAT`; JSON is the only supported semi-structured format. A profile can be set on at most 1,000 databases, and tables with more than 10,000 columns cannot be classified automatically. Consumers cannot classify shared tables.

## Example

Grant a data engineer what they need:

```sql
USE ROLE ACCOUNTADMIN;
GRANT USAGE ON DATABASE mydb TO ROLE data_engineer;
GRANT EXECUTE AUTO CLASSIFICATION ON DATABASE mydb TO ROLE data_engineer;
GRANT DATABASE ROLE SNOWFLAKE.CLASSIFICATION_ADMIN TO ROLE data_engineer;
GRANT CREATE SNOWFLAKE.DATA_PRIVACY.CLASSIFICATION_PROFILE ON SCHEMA mydb.sch TO ROLE data_engineer;
GRANT APPLY TAG ON ACCOUNT TO ROLE data_engineer;
```

Create a profile with a tag map, test it on one table (the output shows which tags were set), then enable it for the database:

```sql
USE ROLE data_engineer;

CREATE OR REPLACE SNOWFLAKE.DATA_PRIVACY.CLASSIFICATION_PROFILE mydb.sch.pii_profile({
  'auto_tag': true,
  'classify_views': false,
  'tag_map': {
    'column_tag_map': [
      {'tag_name': 'governance.tags.pii', 'tag_value': 'highly sensitive',
       'semantic_categories': ['NAME', 'NATIONAL_IDENTIFIER']},
      {'tag_name': 'governance.tags.pii', 'tag_value': 'sensitive',
       'semantic_categories': ['EMAIL']}
    ]
  }
});

CALL SYSTEM$CLASSIFY('mydb.sch.customers', 'mydb.sch.pii_profile');

ALTER DATABASE mydb SET CLASSIFICATION_PROFILE = 'mydb.sch.pii_profile';
```

Attach a masking policy to the mapped tag so classified columns are masked automatically:

```sql
ALTER TAG governance.tags.pii SET MASKING POLICY governance.policies.pii_string_mask;
```

## Best practices

- Test profiles with `SYSTEM$CLASSIFY` on representative tables before enabling them on whole databases.
- Combine the tag map with tag-based masking so newly landed sensitive columns are protected without manual work.
- Restrict detection to the categories you care about to reduce noise.
- Leave views out unless needed; classify base tables instead to control cost.
- Track spend in `METERING_HISTORY` filtered on `SENSITIVE_DATA_CLASSIFICATION`.

## Common pitfalls

- Expecting immediate results after setting a profile; classification starts after about an hour.
- Manually tagging columns with values that conflict with the tag map, which produces classification errors.
- Treating classification as complete coverage; free-form text and unsupported data types are not detected.
- Enabling AI mode without accounting for additional token costs or cross-region inference requirements.

## Learn more

- [Introduction to sensitive data classification](https://docs.snowflake.com/en/user-guide/classify-intro)
- [Use SQL to set up sensitive data classification](https://docs.snowflake.com/en/user-guide/classify-auto)

## Knowledge check

### You want every column Snowflake classifies as EMAIL to be masked automatically, including in tables created next month. What combination achieves this?
- [ ] A row access policy on each schema
- [x] A classification profile with a tag map to a user-defined tag, plus a masking policy assigned to that tag
- [ ] Manually tagging each EMAIL column with SNOWFLAKE.CORE.SEMANTIC_CATEGORY
- [ ] Running SYSTEM$CLASSIFY nightly from a task
> The tag map applies your tag when classification finds EMAIL, and tag-based masking protects any column that carries that tag.

### What is the difference between the semantic and privacy categories assigned to a classified column?
- [ ] Semantic is for tables and privacy is for columns
- [x] Semantic describes the type of data, privacy describes its sensitivity level
- [ ] Semantic categories are user-defined and privacy categories are system-defined
- [ ] They are synonyms used in different interfaces
> A semantic category such as NAME identifies the kind of attribute, while IDENTIFIER, QUASI_IDENTIFIER, or SENSITIVE describes how sensitive it is.

### Before enabling automatic classification on a large production database, how can you validate a profile's tag mappings on a limited scope first?
- [ ] Set the profile on the database and roll back if needed
- [x] Call SYSTEM$CLASSIFY on a sample table with the classification profile and review the output
- [ ] Query TAG_REFERENCES for the database
- [ ] Enable AI mode, which runs in preview first
> SYSTEM$CLASSIFY lets you test a profile, including tag mappings, against a single table before attaching the profile to a database.
