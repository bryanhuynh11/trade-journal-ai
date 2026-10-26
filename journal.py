#!/usr/bin/env python3
"""Trade journal pipeline (command-line version; `python app.py` is the web version).

  1. python journal.py template <tradovate.csv>       -> notes/<name>.notes.csv  (you fill in note + risk_usd)
  2. python journal.py run notes/<name>.notes.csv     -> out/<name>.report.md + out/<name>.tagged.json

`run` calls `claude -p` once per trade that has a note (cached after the first time).
Add --mock to run the whole pipeline with a dumb keyword stand-in instead of Claude.
"""

import argparse
import sys

from tj import pipeline


def cmd_template(args):
    out, n = pipeline.make_template(args.csv, args.out, args.force, args.tz)
    print(f"Wrote {n} trades to {out}\nFill in `note` (what you saw, why you took it, how you felt) "
          f"and `risk_usd` (stop distance in $), then:  python journal.py run {out}")


def cmd_run(args):
    def progress(i, total, x, tag):
        print(f"  trade {x['id']:>2}: {tag['status']:<16} {tag['setup']}")

    backend = pipeline.make_backend(args.mock, args.model)
    pipeline.tag_day(args.notes, backend, use_cache=not args.no_cache, on_progress=progress, csv_path=args.csv)
    print(f"\nReport: {pipeline.OUT_DIR / (pipeline.day_stem(args.notes) + '.report.md')}")


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
    try:
        args.func(args)
    except pipeline.PipelineError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
