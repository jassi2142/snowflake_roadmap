# Use a custom package that is not in the Anaconda channel

topics: udfs, stored-procedures, snowpark
tags: python, packages, dependencies
level: advanced

Your code needs a Python library that the Snowflake Anaconda channel does not provide, such as an internal helper wheel or a niche PyPI package. You have two supported options: install it from PyPI with ARTIFACT_REPOSITORY, or upload your own pure-Python package to a stage and reference it in IMPORTS.

```sql
USE SCHEMA my_db.my_schema;

-- Option A: install a public PyPI package through the shared PyPI repository
-- (role needs the SNOWFLAKE.PYPI_REPOSITORY_USER database role)
GRANT DATABASE ROLE SNOWFLAKE.PYPI_REPOSITORY_USER TO ROLE my_dev_role;

CREATE OR REPLACE FUNCTION slugify_text(s STRING)
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.12'
  ARTIFACT_REPOSITORY = snowflake.snowpark.pypi_shared_repository
  PACKAGES = ('python-slugify')
  HANDLER = 'run'
AS
$$
from slugify import slugify
def run(s):
    return slugify(s) if s else None
$$;

SELECT slugify_text('Hello Snowflake World!');

-- Option B: your own pure-Python package, uploaded to a stage
CREATE STAGE IF NOT EXISTS py_libs;
-- From a terminal (Snowflake CLI):
--   snow stage copy dist/mycompany_utils-1.0.0-py3-none-any.whl @my_db.my_schema.py_libs/ --overwrite
-- (PUT compresses by default; with PUT add AUTO_COMPRESS = FALSE)

CREATE OR REPLACE PROCEDURE clean_customers()
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.12'
  PACKAGES = ('snowflake-snowpark-python')
  IMPORTS = ('@my_db.my_schema.py_libs/mycompany_utils-1.0.0-py3-none-any.whl')
  HANDLER = 'main'
AS
$$
import os, sys

# Imported files are placed in the import directory. A pure-Python wheel is a
# zip archive, so add it to sys.path and Python's zipimport can load from it.
import_dir = sys._xoptions["snowflake_import_directory"]
sys.path.insert(0, os.path.join(import_dir, "mycompany_utils-1.0.0-py3-none-any.whl"))

from mycompany_utils import normalize_name   # your package

def main(session):
    df = session.table("customers")
    rows = df.select("name").limit(5).collect()
    return ", ".join(normalize_name(r["NAME"]) for r in rows)
$$;

CALL clean_customers();
```

## Notes
- Prefer Option A when the package is on PyPI. Snowflake resolves the package and its dependencies for you.
- Option B only works for pure-Python code. Packages with C extensions or native binaries will not import this way. Any dependencies must already be in `PACKAGES` or also be imported.
- The function owner needs READ on the stage. You cannot use a variable in IMPORTS, so new versions mean a new path and a `CREATE OR REPLACE`.
- In a Snowflake Notebook, you can add staged packages from the notebook's package settings instead of editing `sys.path` by hand.

## References
- [Using third-party packages](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python-packages)
- [Making dependencies available to your code](https://docs.snowflake.com/en/developer-guide/upload-dependencies)
- [Creating a Python UDF with code uploaded from a stage](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python-creating)
