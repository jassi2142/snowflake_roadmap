# Snowflake Roadmap - Project Summary

An interactive, self-contained learning roadmap for Snowflake, inspired by the format of
[roadmap.sh](https://roadmap.sh/postgresql-dba). It takes learners from fundamentals to senior-level
platform architecture, administration and data engineering. All roadmap content and code are original.

## At a glance

| Item | Count |
| --- | --- |
| Roadmap sections | 17 |
| Topics (Beginner / Intermediate / Advanced) | 131 |
| Knowledge-check questions | 393 (3 per topic) |
| Snippet library recipes | 46 |
| Community articles indexed (titles and links only) | 366 |
| Verified links | 294, all working |

## Features

- **Roadmap view**: sections sit on a central spine, each linked to a box of labelled topic groups. Topics are marked
  Required, Recommended or Optional and tagged with a level (B / I / A).
- **Topic panel**: overview, how it works, examples, best practices, common pitfalls, doc links and an interactive
  knowledge check, plus related snippets and community articles.
- **Progress tracking**: Done / In progress / Skip per topic, progress counts per section and overall, and a quiz score.
  Progress is saved in browser storage.
- **Bookmarks & Data Portability**: Star/bookmark topics to create a focused revision list, filter by bookmarked topics,
  and export/import progress, bookmarks, and quiz scores as JSON to prevent data loss and sync across devices.
- **Role-Based Learning Tracks**: Curated learning paths for **SnowPro Core** (64 topics), **Data Engineer** (76 topics),
  **Administrator & FinOps** (71 topics), and **Platform Architect** (64 topics), with track-specific progress tracking
  and visual highlighting.
- **Filters**: by track, level (to target senior professionals), starred topics, and full-text search.
- **Snippet Library**: searchable, filterable by tag and level, with Copy buttons on code blocks.
- **Community Articles**: an index of the Cloudyard author's posts (Sachin Mittal), filterable by category and roadmap
  topic, with links back to the original site.
- **Syntax Highlighting**: Built-in zero-dependency regex tokenizer for SQL and Python code blocks with theme-aware
  syntax colors (keywords, functions, strings, numbers, comments) in both light and dark modes.
- **Practice Exam & Mock Test Mode**: Dedicated practice test engine drawing from all 384 scenario questions with
  configurable question count (15, 30, 60, or all), track filtering, study mode (instant feedback & explanations),
  and exam simulation (75% passing threshold, domain-by-domain score breakdown, and answer review).
- **Self-contained output**: a single `dist/index.html` with no server, no CDN and no network calls. It adapts to
  light/dark mode and mobile screens.

## Roadmap sections

1. Snowflake Fundamentals
2. Getting Started
3. Compute & Warehouses
4. Data Ingestion
5. Semi-structured & Unstructured Data
6. Pipelines & Transformation
7. Security
8. Data Governance
9. Data Protection & Business Continuity
10. Performance Tuning
11. Monitoring & FinOps
12. Data Sharing & Collaboration
13. Open Formats & Lakehouse
14. AI, ML & Apps
15. DevOps & Automation
16. Advanced Architecture (multi-account strategy, enterprise RBAC, medallion, data mesh, hybrid tables, migration)
17. Certification

## Project structure

```text
Snowflake_Study/
  .github/workflows/
    deploy.yml              # GitHub Actions: automated build and deploy to GitHub Pages
    link_check.yml          # GitHub Actions: weekly scheduled link validation
  .gitignore                # Git ignore rules
  build.py                  # Builds dist/index.html from the sources below
  CONTENT_GUIDE.md          # Format rules for topics and snippets
  PROJECT_SUMMARY.md        # This file
  data/
    roadmap.json            # Sections > groups > topics (id, title, type, level, tracks)
    articles.json           # Community article metadata (generated)
  content/<topic-id>.md     # One file per topic, including its knowledge check
  snippets/<snippet-id>.md  # Original code recipes with topics/tags/level headers
  src/template.html         # Page layout, styles and JavaScript
  scripts/
    check_links.py          # Checks every link in content/ and snippets/
    index_articles.py       # Re-crawls the article listing (metadata only)
  dist/index.html           # Build output - open in any browser
```

## How to use

```bash
# Rebuild the site after editing roadmap.json, content/ or snippets/
python build.py

# Check all documentation links (exits non-zero on failures)
python scripts/check_links.py

# Refresh the community article index, then rebuild
python scripts/index_articles.py
python build.py
```

Then open `dist/index.html` in a browser.

`build.py` reports missing content files, malformed quiz questions, unknown topic ids in snippets and orphan files.
It also shuffles quiz answer order in a repeatable way, so correct answers are spread evenly across positions.

## Adding content

- **New topic**: add it to `data/roadmap.json`, create `content/<id>.md` following `CONTENT_GUIDE.md`, then rebuild.
- **New snippet**: create `snippets/<id>.md` with `topics:`, `tags:` and `level:` header lines, then rebuild.
  It appears automatically in the library and in each linked topic's panel.

## Licensing and attribution decisions

- **roadmap.sh**: its repository is "all rights reserved", so only the *format* was used; no content or code was copied.
- **Cloudyard (cloudyard.in)**: "All rights reserved". Only article titles, URLs, dates and categories are stored, and
  the site credits the author and links back. No article text or code was copied; all snippets are written from
  Snowflake documentation.

## Accuracy notes and known limitations

- Topic content and snippets were checked against current Snowflake documentation, and facts that couldn't be
  verified were left out. Even so, some SQL examples are untested against real objects. Test them in a trial account
  before relying on them.
- Snippets that rest partly on general knowledge: the custom wheel "Option B" approach, the Snowpark async-job method
  names, and the Teams webhook body (it depends on your Power Automate flow).
- Snowflake renamed `IMMUTABLE WHERE` to `FROZEN WHERE` for dynamic tables (the legacy syntax is still accepted);
  the snippets use `FROZEN WHERE`.
- Progress is saved per browser. Clearing browser storage resets it.

## Possible next steps

- Hands-on labs per topic, runnable in a trial account with sample datasets
- Streamlit in Snowflake (SiS) companion app or Snowflake Native App variant
- Periodic content review against Snowflake release notes
