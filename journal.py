#!/usr/bin/env python3
"""Trade journal pipeline.

  1. python journal.py template <tradovate.csv>       -> notes/<name>.notes.csv  (you fill in note + risk_usd)
  2. python journal.py run notes/<name>.notes.csv     -> out/<name>.report.md + out/<name>.tagged.json

`run` calls `claude -p` once per trade that has a note (cached after the first time).
Add --mock to run the whole pipeline with a dumb keyword stand-in instead of Claude.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from tj import parse, facts, report
from tj.tagger import Tagger, ClaudeCLI, MockModel

ROOT = Path(__file__).parent
NOTE_COLS = ["id", "entry_time", "side", "root", "qty", "entry_price", "exit_price", "pnl", "killzone", "risk_usd", "note"]


def _portable(path):
    """Store the CSV path relative to the repo when possible so notes files survive a move."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT.resolve()))
    except ValueError:
        return str(p)


def cmd_template(args):
    trades = parse.read_tradovate(args.csv, args.tz)
    fs = facts.build_facts(trades)
    stem = Path(args.csv).stem
    out = Path(args.out or ROOT / "notes" / f"{stem}.notes.csv")
    if out.exists() and not args.force:
        sys.exit(f"{out} exists (it may have your notes in it). Use --force to overwrite.")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NOTE_COLS + ["source_csv"])
        w.writeheader()
        for x in fs:
            w.writerow({**{k: x.get(k, "") for k in NOTE_COLS if k not in ("risk_usd", "note")},
                        "risk_usd": "", "note": "", "source_csv": _portable(args.csv)})
    print(f"Wrote {len(fs)} trades to {out}\nFill in `note` (what you saw, why you took it, how you felt) "
          f"and `risk_usd` (stop distance in $), then:  python journal.py run {out}")


def cmd_run(args):
    notes_path = Path(args.notes)
    with notes_path.open(newline="") as f:
        note_rows = list(csv.DictReader(f))
    if not note_rows:
        sys.exit("notes file is empty")
    src = args.csv or note_rows[0].get("source_csv")
    if src and not Path(src).is_absolute() and not Path(src).exists():
        src = str(ROOT / src)
    if not src or not Path(src).exists():
        sys.exit(f"can't find the Tradovate CSV ({src!r}); pass it with --csv")

    # Re-derive every number from the original export -- never trust numbers typed into the notes file.
    trades = parse.read_tradovate(src, args.tz)
    by_id = {int(r["id"]): r for r in note_rows}
    if set(by_id) != {t.id for t in trades}:
        sys.exit("notes file trade ids don't match the CSV; regenerate with `template --force`")
    risks = {i: float(r["risk_usd"]) for i, r in by_id.items() if r.get("risk_usd", "").strip()}
    fs = facts.build_facts(trades, risks)

    backend = MockModel() if args.mock else ClaudeCLI(model=args.model)
    tagger = Tagger(backend, cache_path=None if args.no_cache else ROOT / "out" / ".tag_cache.jsonl")

    rows = []
    for x in fs:
        note = by_id[x["id"]].get("note", "")
        print(f"  trade {x['id']:>2}: ", end="", flush=True)
        tag = tagger.tag(x, note)
        print(f"{tag['status']:<16} {tag['setup']}")
        rows.append({**x, **tag})

    stem = notes_path.name.removesuffix(".notes.csv")
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{stem}.tagged.json").write_text(json.dumps({"trades": rows, "calls": tagger.log}, indent=2))
    md = report.render(rows, tagger.log, stem + (" (MOCK)" if args.mock else ""))
    (out_dir / f"{stem}.report.md").write_text(md)
    print(f"\nReport: {out_dir / (stem + '.report.md')}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tz", default="America/New_York", help="timezone of the export timestamps")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="make a notes file from a Tradovate Performance CSV")
    t.add_argument("csv")
    t.add_argument("--out")
    t.add_argument("--force", action="store_true")
    t.set_defaults(func=cmd_template)

    r = sub.add_parser("run", help="tag trades with Claude and write the report")
    r.add_argument("notes")
    r.add_argument("--csv", help="Tradovate CSV (defaults to the path saved in the notes file)")
    r.add_argument("--model", help="e.g. haiku, sonnet (default: your Claude Code default)")
    r.add_argument("--mock", action="store_true", help="use the keyword stand-in instead of Claude")
    r.add_argument("--no-cache", action="store_true")
    r.set_defaults(func=cmd_run)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
