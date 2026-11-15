# Python scalar UDF and table function (UDTF) with packages

topics: udfs, snowpark
tags: python, udf, udtf
level: intermediate

A scalar UDF returns one value per row. A UDTF can return many rows per input row and keep state across a partition. Both can use packages from the Snowflake Anaconda channel through `PACKAGES`.

```sql
USE SCHEMA my_db.my_schema;
USE WAREHOUSE my_wh;

-- 1. Scalar UDF: normalise phone numbers with the phonenumbers package
CREATE OR REPLACE FUNCTION normalize_phone(raw STRING, region STRING)
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.12'
  PACKAGES = ('phonenumbers')
  HANDLER = 'normalize'
AS
$$
import phonenumbers

def normalize(raw, region):
    if raw is None:
        return None
    try:
        num = phonenumbers.parse(raw, region or 'US')
        return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None
$$;

SELECT normalize_phone('(415) 555-0132', 'US') AS e164;

-- 2. UDTF: split text into words and count them per partition
CREATE OR REPLACE FUNCTION word_counts(doc STRING)
  RETURNS TABLE (word STRING, cnt INT)
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.12'
  HANDLER = 'WordCounter'
AS
$$
import re
from collections import Counter

class WordCounter:
    def __init__(self):
        self.counts = Counter()          # state for the current partition

    def process(self, doc):
        if doc:
            self.counts.update(re.findall(r"[a-z']+", doc.lower()))
        return None                      # emit nothing per row

    def end_partition(self):
        for word, cnt in self.counts.most_common(5):
            yield (word, cnt)
$$;

-- Call the UDTF once per document group
WITH docs AS (
  SELECT * FROM VALUES
    ('faq', 'Reset your password in settings. Settings is under your profile.'),
    ('faq', 'Your password must be 12 characters.'),
    ('blog', 'Snowflake tables and Snowflake stages')
  AS t(category, body)
)
SELECT d.category, w.word, w.cnt
FROM docs d,
     TABLE(word_counts(d.body) OVER (PARTITION BY d.category)) w
ORDER BY d.category, w.cnt DESC;
```

## Notes
- List the packages available to you with `SELECT * FROM INFORMATION_SCHEMA.PACKAGES WHERE language = 'python'`. Using Anaconda packages requires accepting the Anaconda terms once per organization.
- Scalar UDFs run per row. For large tables, a vectorized UDF (pandas batches) is usually faster.
- In a UDTF, `process` runs for every row and `end_partition` runs once per partition. Without `OVER (PARTITION BY ...)`, Snowflake decides how rows are split up.

## References
- [Introduction to Python UDFs](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python-introduction)
- [Writing a UDTF in Python](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python-tabular-functions)
- [Using third-party packages](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python-packages)
