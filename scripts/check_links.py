"""Check every link in content/*.md. Usage: python scripts/check_links.py"""
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\]\((https?://[^)\s]+)\)")
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def check(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 link-checker"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(200_000).decode("utf-8", "ignore")
            m = TITLE.search(body)
            title = " ".join(m.group(1).split()) if m else ""
            return url, r.status, r.geturl(), title
    except urllib.error.HTTPError as e:
        return url, e.code, url, ""
    except Exception as e:  # network errors, timeouts
        return url, "ERR", url, str(e)[:80]


def main():
    uses = {}
    files = sorted((ROOT / "content").glob("*.md")) + sorted((ROOT / "snippets").glob("*.md"))
    for f in files:
        for u in LINK.findall(f.read_text(encoding="utf-8")):
            uses.setdefault(u, []).append(f.stem)
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(check, uses))
    bad = 0
    for url, status, final, title in results:
        soft404 = "not found" in title.lower() or "404" in title
        ok = status == 200 and not soft404
        bad += not ok
        flag = "OK " if ok else "BAD"
        redirect = f" -> {final}" if final.rstrip("/") != url.rstrip("/") else ""
        print(f"{flag} {status} {url}{redirect} | {title[:70]} | {','.join(uses[url])}")
    print(f"\n{len(results)} unique links, {bad} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
