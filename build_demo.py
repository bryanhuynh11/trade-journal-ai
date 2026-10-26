#!/usr/bin/env python3
"""Build the public read-only demo into docs/ (served by GitHub Pages).

    python build_demo.py            # tags the sample day with real `claude -p`, then renders the pages
    python build_demo.py --reuse    # skip tagging, reuse the last result in out/
    python build_demo.py --mock     # no Claude (for testing the build only -- don't publish this)

The demo is a snapshot: plain HTML + CSS + Chart.js, no server and no Claude calls, so it can be
public and stays up forever. The live app (python app.py) is still local-only, because it calls
`claude -p` on my own Claude Code login.
"""

import argparse
import re
import shutil
from datetime import date
from pathlib import Path

import app as webapp
from tj import pipeline

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs"
STEM = "sample-2026-10-23"
REPO = "https://github.com/bryanhuynh11/trade-journal-ai"

PAGES = {                      # url in the Flask app -> file in the static site
    "/": "index.html",
    "/how": "how.html",
    f"/day/{STEM}": "notes.html",
    f"/day/{STEM}/report": "report.html",
}


def relink(html: str) -> str:
    def fix(m):
        attr, url = m.group(1), m.group(2)
        if url in PAGES:
            return f'{attr}="{PAGES[url]}"'
        if url.startswith("/static/"):
            return f'{attr}="{url[1:]}"'
        return m.group(0)
    return re.sub(r'(href|src)="(/[^"]*)"', fix, html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    client = webapp.app.test_client()
    client.post("/sample")                                   # fresh sample day (TradeSea fills + my notes)
    notes = pipeline.NOTES_DIR / f"{STEM}.notes.csv"

    if not (args.reuse and pipeline.load_result(STEM)):
        print("Tagging the sample day" + (" (MOCK)" if args.mock else " with claude -p") + "...")
        res = pipeline.tag_day(notes, pipeline.make_backend(mock=args.mock), use_cache=False,
                               on_progress=lambda i, n, x, t: print(f"  {i}/{n} {t['status']:<16} {t['setup']}"))
    res = pipeline.load_result(STEM)
    if res.get("mock") and not args.mock:
        raise SystemExit("last result is MOCK; run without --reuse to tag with Claude")

    webapp.app.config["DEMO"] = {"date": date.today().strftime("%b %d, %Y"), "repo": REPO, "stem": STEM}
    try:
        for url, fname in PAGES.items():
            r = client.get(url)
            if r.status_code != 200:
                raise SystemExit(f"{url} -> {r.status_code}")
            (OUT / fname).write_text(relink(r.get_data(as_text=True)))
            print(f"  wrote docs/{fname}")
    finally:
        webapp.app.config["DEMO"] = None

    shutil.copytree(ROOT / "static", OUT / "static", dirs_exist_ok=True)
    (OUT / ".nojekyll").write_text("")                       # tell GitHub Pages to serve files as-is
    print(f"\nDone. Open docs/index.html to check, then push. Live at https://bryanhuynh11.github.io/trade-journal-ai/")


if __name__ == "__main__":
    main()
