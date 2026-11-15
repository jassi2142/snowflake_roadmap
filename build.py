"""Build dist/index.html from data/roadmap.json + content/*.md + src/template.html."""
import hashlib
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUIZ_HEADING = re.compile(r"^## Knowledge check\s*$", re.M)


def parse_quiz(text, topic_id, warnings):
    """Parse the '## Knowledge check' block into [{q, options, answer, explain}]."""
    questions = []
    for block in re.split(r"^### ", text, flags=re.M)[1:]:
        lines = [l.rstrip() for l in block.strip().splitlines()]
        q = {"q": lines[0].strip(), "options": [], "answer": -1, "explain": ""}
        for l in lines[1:]:
            m = re.match(r"^\s*-\s*\[( |x|X)\]\s+(.*)", l)
            if m:
                if m.group(1).lower() == "x":
                    q["answer"] = len(q["options"])
                q["options"].append(m.group(2).strip())
            elif l.startswith(">"):
                q["explain"] = (q["explain"] + " " + l.lstrip("> ").strip()).strip()
        if q["answer"] < 0 or len(q["options"]) < 2:
            warnings.append(f"{topic_id}: malformed question '{q['q'][:50]}'")
            continue
        # Deterministic shuffle so the correct answer's position varies but builds are reproducible.
        rng = random.Random(hashlib.sha256(f"{topic_id}:{q['q']}".encode()).hexdigest())
        order = list(range(len(q["options"])))
        rng.shuffle(order)
        q["options"] = [q["options"][i] for i in order]
        q["answer"] = order.index(q["answer"])
        questions.append(q)
    return questions


def load_snippets(ids, warnings):
    """Parse snippets/*.md: '# title', then 'topics:', 'tags:', 'level:' header lines, then markdown body."""
    snippets = {}
    for f in sorted((ROOT / "snippets").glob("*.md")):
        lines = f.read_text(encoding="utf-8").splitlines()
        title = lines[0].lstrip("# ").strip() if lines else f.stem
        meta, i = {}, 1
        while i < len(lines) and (not lines[i].strip() or re.match(r"^(topics|tags|level):", lines[i])):
            m = re.match(r"^(topics|tags|level):\s*(.*)", lines[i])
            if m:
                meta[m.group(1)] = m.group(2).strip()
            i += 1
        topics = [t.strip() for t in meta.get("topics", "").split(",") if t.strip()]
        bad = [t for t in topics if t not in ids]
        if bad:
            warnings.append(f"snippet {f.stem}: unknown topics {bad}")
        if "```" not in "\n".join(lines):
            warnings.append(f"snippet {f.stem}: no code block")
        snippets[f.stem] = {
            "title": title,
            "topics": [t for t in topics if t in ids],
            "tags": [t.strip().lower() for t in meta.get("tags", "").split(",") if t.strip()],
            "level": meta.get("level", "intermediate"),
            "body": "\n".join(lines[i:]).strip(),
        }
    return snippets


def load_articles(ids):
    f = ROOT / "data" / "articles.json"
    if not f.exists():
        return {"source": None, "articles": []}
    data = json.loads(f.read_text(encoding="utf-8"))
    for a in data["articles"]:
        a["topics"] = [t for t in a.get("topics", []) if t in ids]
    return data


def main():
    roadmap = json.loads((ROOT / "data" / "roadmap.json").read_text(encoding="utf-8"))
    content, warnings, ids = {}, [], set()
    valid_tracks = {tr["id"] for tr in roadmap.get("tracks", [])}
    for sec in roadmap["sections"]:
        for grp in sec["groups"]:
            for t in grp["topics"]:
                if t["id"] in ids:
                    warnings.append(f"{t['id']}: duplicate topic id")
                ids.add(t["id"])
                for tr in t.get("tracks", []):
                    if tr not in valid_tracks:
                        warnings.append(f"{t['id']}: unknown track '{tr}'")
                f = ROOT / "content" / f"{t['id']}.md"
                if not f.exists():
                    warnings.append(f"{t['id']}: missing content file")
                    continue
                text = f.read_text(encoding="utf-8")
                parts = QUIZ_HEADING.split(text, maxsplit=1)
                quiz = parse_quiz(parts[1], t["id"], warnings) if len(parts) == 2 else []
                if not quiz:
                    warnings.append(f"{t['id']}: no knowledge check")
                content[t["id"]] = {"body": parts[0].rstrip(), "quiz": quiz}

    orphans = sorted(p.stem for p in (ROOT / "content").glob("*.md") if p.stem not in ids)
    if orphans:
        warnings.append("content files not in roadmap.json: " + ", ".join(orphans))
    snippets = load_snippets(ids, warnings)
    articles = load_articles(ids)
    for w in warnings:
        print("WARN", w, file=sys.stderr)

    payload = json.dumps({"roadmap": roadmap, "content": content, "snippets": snippets, "articles": articles},
                         ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # never close the <script> tag early
    html = (ROOT / "src" / "template.html").read_text(encoding="utf-8")
    html = html.replace("__ROADMAP_DATA__", payload).replace("__BUILD_DATE__", date.today().isoformat())

    out = ROOT / "dist" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    n_q = sum(len(c["quiz"]) for c in content.values())
    print(f"Built {out} ({len(ids)} topics, {len(content)} with content, {n_q} questions, "
          f"{len(snippets)} snippets, {len(articles['articles'])} articles, {len(warnings)} warnings)")


if __name__ == "__main__":
    main()
