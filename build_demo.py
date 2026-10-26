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
from tj import coach, history, pipeline

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs"
STEM = "sample-2026-10-23"
REPO = "https://github.com/bryanhuynh11/trade-journal-ai"

PAGES = {                      # url in the Flask app -> file in the static site
    "/": "index.html",
    "/how": "how.html",
    f"/day/{STEM}": "notes.html",
    f"/day/{STEM}/report": "report.html",
    "/history": "history.html",
}
COACH_QUESTIONS = [
    "What's my biggest leak right now?",
    "Give me 3 concrete rules for next week based on this.",
]


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
    client.post("/sample-history")                           # sample day + 2-week history (TradeSea fills + notes)
    stems = sorted(pipeline.day_stem(p) for p in pipeline.NOTES_DIR.glob("sample-*.notes.csv"))

    backend = pipeline.make_backend(mock=args.mock)
    for stem in stems:
        res = pipeline.load_result(stem)
        if args.reuse and res and res.get("mock") == args.mock:
            continue
        print(f"Tagging {stem}" + (" (MOCK)" if args.mock else " with claude -p") + "...")
        # the tag cache only holds answers that came from Claude and passed the validator, so reusing it is honest
        pipeline.tag_day(pipeline.NOTES_DIR / f"{stem}.notes.csv", backend, use_cache=not args.mock,
                         on_progress=lambda i, n, x, t: print(f"  {i}/{n} {t['status']:<16} {t['setup']}"))
    for stem in stems:
        if pipeline.load_result(stem).get("mock") and not args.mock:
            raise SystemExit(f"{stem} has MOCK tags; run without --reuse")

    # Real coach answers for the static chat panel (the public page can't call Claude live).
    rows = [r for r in history.load_all() if r["day"].startswith("sample-")]
    ctx = history.coach_context(rows, history.summary(rows))
    cb = coach.make_backend(mock=args.mock)
    canned, convo = [], []
    for q in COACH_QUESTIONS:
        print(f"Coach: {q}")
        out = coach.ask(q, ctx, convo, cb)
        print(f"  {out['seconds']}s, {out['checked']} figures, unverified={out['unverified']}")
        canned.append({"q": q, "a": out["answer"], "checked": out["checked"], "unverified": out["unverified"],
                       "seconds": out["seconds"]})
        convo += [{"role": "user", "content": q}, {"role": "assistant", "content": out["answer"]}]

    webapp.app.config["DEMO"] = {"date": date.today().strftime("%b %d, %Y"), "repo": REPO, "stem": STEM, "coach": canned}
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
