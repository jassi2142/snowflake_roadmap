# Topic content guide

Each topic in `data/roadmap.json` has a file `content/<topic-id>.md` in this exact format.
Target 350-700 words of prose (excluding code), written for the topic's level.

```markdown
# <Topic title>

<2-3 sentence overview: what it is and why it matters.>

## How it works
<Explanation of the mechanics. Paragraphs and/or bullet lists. Mention edition requirements, limits and defaults where relevant.>

## Example
<One or more realistic, runnable Snowflake SQL (or CLI/Python) examples in fenced code blocks, with a sentence explaining each.>

## Best practices
- <bullet>

## Common pitfalls
- <bullet>

## Learn more
- [Link text](https://docs.snowflake.com/en/...)

## Knowledge check

### <Question 1 text>
- [ ] <wrong option>
- [x] <correct option>
- [ ] <wrong option>
- [ ] <wrong option>
> <1-2 sentence explanation of why the correct answer is right.>

### <Question 2 text>
...
```

Rules
- 3 questions per topic, exactly one `[x]` per question, 3-4 options, explanation line starting with `> `.
- Questions should test understanding (scenarios, trade-offs), not trivia. Advanced topics get scenario questions.
- Supported markdown: `#`/`##`/`###` headings, paragraphs, `-` lists, `1.` lists, fenced code, `` `code` ``, `**bold**`, `[text](https://...)` links, `> ` notes, and simple pipe tables.
- Do not use raw HTML.
- Facts (limits, defaults, edition requirements) must match current Snowflake documentation.
- Links must be real URLs; verify with `python scripts/check_links.py`.

# Snippet guide

Each snippet is `snippets/<snippet-id>.md`. Snippets are **original** code recipes. Never copy code or prose from third-party
blogs; `data/articles.json` only holds article titles/links, which the build attaches automatically by shared topic.

```markdown
# <Snippet title>

topics: <topic-id>, <topic-id>
tags: <tag>, <tag>
level: beginner | intermediate | advanced

<1-3 sentence description of the problem this solves.>

```sql
<complete, runnable code with comments; use placeholder names like my_db, my_wh>
```

## Notes
- <prerequisites: edition, privileges, required objects>
- <caveats, cost implications, how to clean up>

## References
- [Snowflake doc title](https://docs.snowflake.com/en/...)
```

Rules
- `topics` must be ids from `data/roadmap.json` (1-3). `tags` are free-form lowercase (e.g. `alerting`, `governance`, `python`).
- One or more fenced code blocks (`sql`, `python`, `yaml`, `bash`). Keep the whole snippet under ~120 lines of code.
- Syntax must match current Snowflake docs; compile-check SQL where possible.
