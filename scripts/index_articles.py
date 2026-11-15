"""Index article metadata (title, URL, date, category) from the Cloudyard author listing.

Only metadata is stored -- article text and code are NOT copied (the site is "All rights reserved").
Each article is mapped to roadmap topic ids by keyword rules, so topic panels can link to it.

Usage: python scripts/index_articles.py
"""
import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://cloudyard.in/author/sachin2021/"
SOURCE = {"name": "Cloudyard", "author": "Sachin Mittal", "url": BASE}

# <h2 ...><a href="URL">TITLE</a></h2> ... By Sachin Mittal -- <a>DATE</a> -- <a href=".../category/...">CATEGORY</a>
POST = re.compile(
    r'<h2[^>]*>\s*<a href="(https://cloudyard\.in/\d{4}/\d{2}/[^"]+)"[^>]*>(.*?)</a>\s*</h2>(.*?)(?=<h2|</main>|$)', re.S)
DATE = re.compile(r'<a href="https://cloudyard\.in/\d{4}/\d{2}/\d{2}/"[^>]*>(.*?)</a>', re.S)
CATEGORY = re.compile(r'<a href="https://cloudyard\.in/category/[^"]+"[^>]*>(.*?)</a>', re.S)

# Keyword (regex, case-insensitive, matched against the title) -> roadmap topic ids.
RULES = [
    (r"\bdmf\b|data metric|data quality", ["data-metric-functions"]),
    (r"lineage|what breaks|access_history", ["access-history"]),
    (r"metadata objects", ["copy-into"]),
    (r"iceberg|pyiceberg|horizon rest|delta direct|fabric", ["iceberg-tables", "catalog-integrations"]),
    (r"cortex agent|\bagent\b|\bmcp\b|skills", ["cortex-agents"]),
    (r"cortex analyst|semantic", ["cortex-analyst"]),
    (r"cortex search", ["cortex-search"]),
    (r"cortex|genai|gen ai|\bai\b|ai_redact|ai_parse|document ai|claude|llm", ["cortex-ai-functions"]),
    (r"masking|redact|pii|decryption|policies|policy", ["masking", "tag-based-masking"]),
    (r"\btag", ["tagging"]),
    (r"dynamic table|immutable where", ["dynamic-tables"]),
    (r"\btask\b|execute task", ["tasks"]),
    (r"stream\b|cdc", ["streams"]),
    (r"\bdbt\b", ["dbt"]),
    (r"ci/cd|ci-cd|devops|azure devops|github", ["ci-cd"]),
    (r"alert|slack|teams|email|notification|incident|n8n", ["alerts"]),
    (r"external access|live data|external function|api", ["external-access"]),
    (r"snowpark|collect_nowait|async", ["snowpark"]),
    (r"\.whl|python package|notebook", ["snowpark", "udfs"]),
    (r"streamlit|unified ai app", ["streamlit"]),
    (r"query acceleration", ["qas"]),
    (r"external table", ["external-tables"]),
    (r"copy files|datasync|s3|azure blob|copy into|snowpipe|load", ["copy-into", "stages"]),
    (r"cost|credit|finops", ["credit-usage", "cost-attribution"]),
    (r"password|oauth|salesforce|login|authentication", ["authentication", "sso-oauth"]),
    (r"dml error|error logging", ["copy-into"]),
    (r"timestamp|timezone", ["data-types"]),
    (r"javascript procedure|stored procedure|procedure", ["stored-procedures"]),
    (r"clon|time travel", ["cloning", "time-travel"]),
    (r"undrop|recover table", ["undrop"]),
    (r"serverless task|triggered task|finalizer|child task|tasks?\b|retry last|setvalue|getvalue", ["tasks"]),
    (r"schema (evolution|detection)", ["infer-schema"]),
    (r"directory table|unstructured|pdf|excel|zip file|snowflakefile", ["unstructured", "directory-tables"]),
    (r"event table|logging", ["event-tables"]),
    (r"streams? on|change_tracking|transaction block with streams", ["streams"]),
    (r"scd2|merge|duplicate|data comparison|data pipeline|pipeline", ["pipeline-design"]),
    (r"sql scripting|exception handling|execute immediate|error handling|get_ddl|js proc|javascript|caller.s rights", ["stored-procedures"]),
    (r"udf|anaconda|third-party packages", ["udfs"]),
    (r"python|pandas|read_sql|fetch_pandas|to_sql|connector|odbc|spark|glue|kinesis|firehose|\badf\b", ["drivers-connectors"]),
    (r"cach", ["caching"]),
    (r"materialized view", ["materialized-views"]),
    (r"micro.?partition|pruning|clustering|table partition", ["micro-partitions", "pruning-clustering"]),
    (r"spilling", ["spilling"]),
    (r"performance|long run|query_history|query history", ["query-profile", "query-history-analysis"]),
    (r"resource monitor", ["resource-monitors"]),
    (r"multicluster|multi-cluster", ["multi-cluster"]),
    (r"budget massacre|common mistakes|storage and cloud services|stale storage", ["credit-usage", "storage-cost"]),
    (r"secondary role", ["secondary-roles"]),
    (r"ownership|privileges|inactive users|provisioning in aad|okta|sso", ["role-hierarchy", "sso-oauth", "scim"]),
    (r"exfiltration|encryption|kms|data protection|high availability", ["encryption", "network-policies"]),
    (r"storage integration|internal stage|external stage|\bput\b|file format|pattern with regex|huge file|copy process|feed file|file validation|validate sql file|insert csv|csv|split file|extra comma", ["copy-into", "stages", "file-formats"]),
    (r"qualify|match_recognize|pivot|connect_by|cte|common table|sampling|sequence|identity|truncate|system function|parameters|unsupported subquery|null columns|column comments|table types|get_object_references", ["snowflake-sql-extensions", "sql-basics"]),
    (r"secure view|dynamic view|view refresh|view definition|views\b", ["views"]),
    (r"architecture|reference architecture|deployment framework", ["medallion-architecture", "architecture"]),
    (r"migrat|dms|oracle", ["migration-strategy"]),
    (r"pre-production|data refresh approach", ["environment-strategy"]),
    (r"transaction lock", ["sql-basics"]),
    (r"pipe ownership|snowpipe", ["snowpipe"]),
    (r"ddl changes", ["access-history"]),
    (r"marketplace", ["listings"]),
    (r"snowsql", ["snowflake-cli"]),
    (r"overview|unique features|webui", ["what-is-snowflake", "snowsight"]),
    (r"share|sharing|listing", ["secure-shares"]),
    (r"warehouse", ["warehouse-basics"]),
    (r"rbac|role\b|grant", ["role-hierarchy"]),
    (r"semi-structured|json|flatten|variant", ["variant", "flatten"]),
]


def text(s):
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
    try:  # repair UTF-8 that was double-decoded as cp1252 on the source site (e.g. "â€“")
        s = s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return s


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (roadmap article indexer)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def topics_for(title, valid):
    found = []
    for pat, ids in RULES:
        if re.search(pat, title, re.I):
            found += [i for i in ids if i in valid and i not in found]
    return found


def main():
    roadmap = json.loads((ROOT / "data" / "roadmap.json").read_text(encoding="utf-8"))
    valid = {t["id"] for s in roadmap["sections"] for g in s["groups"] for t in g["topics"]}
    articles, seen, page = [], set(), 1
    while True:
        url = BASE if page == 1 else f"{BASE}page/{page}/"
        try:
            body = fetch(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
            raise
        found = 0
        for href, title, rest in POST.findall(body):
            if href in seen:
                continue
            seen.add(href)
            found += 1
            d, c = DATE.search(rest), CATEGORY.search(rest)
            t = text(title)
            # The date link can hold both the published and the updated date; keep the first (published).
            date = text(d.group(1)) if d else ""
            m = re.match(r"[A-Z][a-z]+ \d{1,2}, \d{4}", date)
            articles.append({"title": t, "url": href, "date": m.group(0) if m else date,
                             "category": text(c.group(1)) if c else "", "topics": topics_for(t, valid)})
        print(f"page {page}: {found} articles")
        if not found:
            break
        page += 1

    out = {"source": SOURCE, "articles": articles}
    (ROOT / "data" / "articles.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    unmapped = sum(1 for a in articles if not a["topics"])
    print(f"{len(articles)} articles indexed, {unmapped} without a topic mapping")


if __name__ == "__main__":
    main()
