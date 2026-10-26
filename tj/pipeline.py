"""The two pipeline steps as plain functions, shared by the CLI (journal.py) and the web app (app.py)."""

import csv
import json
from pathlib import Path

from . import parse, facts, report
from .tagger import Tagger, ClaudeCLI, MockModel

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "notes"
OUT_DIR = ROOT / "out"
CACHE = OUT_DIR / ".tag_cache.jsonl"
NOTE_COLS = ["id", "entry_time", "side", "root", "qty", "entry_price", "exit_price", "pnl", "killzone",
             "risk_usd", "note", "source_csv"]


class PipelineError(Exception):
    pass


def _portable(path) -> str:
    """Store the CSV path relative to the repo when possible so notes files survive a move."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _resolve(src: str) -> Path:
    p = Path(src)
    return p if p.is_absolute() else ROOT / p


# ---------- step 1: CSV -> notes file ----------

def make_template(csv_path, out_path=None, force=False, tz=None) -> tuple[Path, int]:
    trades = parse.read_trades(csv_path, tz)
    fs = facts.build_facts(trades)
    out = Path(out_path or NOTES_DIR / f"{Path(csv_path).stem}.notes.csv")
    if out.exists() and not force:
        raise PipelineError(f"{out.name} already exists (it may have your notes in it).")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NOTE_COLS)
        w.writeheader()
        for x in fs:
            w.writerow({**{k: x.get(k, "") for k in NOTE_COLS}, "risk_usd": "", "note": "",
                        "source_csv": _portable(csv_path)})
    return out, len(fs)


# ---------- reading / saving a day ----------

def read_notes(notes_path) -> list[dict]:
    with Path(notes_path).open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise PipelineError("notes file is empty")
    return rows


def load_day(notes_path, csv_path=None, tz=None) -> tuple[list[dict], dict[int, dict]]:
    """Returns (facts per trade, note rows by id). Every number is re-derived from the original CSV --
    numbers typed into the notes file are never trusted."""
    note_rows = read_notes(notes_path)
    src = _resolve(csv_path or note_rows[0].get("source_csv", ""))
    if not src.is_file():
        raise PipelineError(f"can't find the Tradovate CSV ({src})")
    trades = parse.read_trades(src, tz)
    by_id = {int(r["id"]): r for r in note_rows}
    if set(by_id) != {t.id for t in trades}:
        raise PipelineError("notes file trade ids don't match the CSV; regenerate the template")
    risks = {}
    for i, r in by_id.items():
        v = (r.get("risk_usd") or "").strip().lstrip("$")
        if v:
            try:
                risks[i] = float(v)
            except ValueError:
                raise PipelineError(f"trade {i}: risk_usd {v!r} is not a number")
    return facts.build_facts(trades, risks), by_id


def save_notes(notes_path, updates: dict[int, dict]):
    """updates: {id: {"note": ..., "risk_usd": ...}}. Only those two columns are ever written."""
    for i, u in updates.items():          # validate first so a typo never lands in the file
        v = u.get("risk_usd", "").strip().lstrip("$")
        if v:
            try:
                if float(v) < 0:
                    raise ValueError
            except ValueError:
                raise PipelineError(f"trade {i}: risk ${v!r} must be a positive number")
    rows = read_notes(notes_path)
    for r in rows:
        u = updates.get(int(r["id"]))
        if u:
            r["note"] = u.get("note", r["note"]).strip()
            r["risk_usd"] = u.get("risk_usd", r["risk_usd"]).strip()
    with Path(notes_path).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


# ---------- step 2: tag + report ----------

def make_backend(mock=False, model=None):
    return MockModel() if mock else ClaudeCLI(model=model)


def tag_day(notes_path, backend, use_cache=True, on_progress=None, csv_path=None) -> dict:
    """Tags every trade, writes out/<stem>.tagged.json and out/<stem>.report.md, returns the result dict.
    on_progress(i, total, facts, tag) is called after each trade (the web app uses it for the progress bar)."""
    fs, by_id = load_day(notes_path, csv_path)
    tagger = Tagger(backend, cache_path=CACHE if use_cache else None)
    rows = []
    for i, x in enumerate(fs, 1):
        tag = tagger.tag(x, by_id[x["id"]].get("note", ""))
        row = {**x, **tag, "note": by_id[x["id"]].get("note", "")}
        rows.append(row)
        if on_progress:
            on_progress(i, len(fs), x, tag)

    stem = day_stem(notes_path)
    mock = isinstance(backend, MockModel)
    result = {"day": stem, "mock": mock, "trades": rows, "calls": tagger.log}
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"{stem}.tagged.json").write_text(json.dumps(result, indent=2))
    (OUT_DIR / f"{stem}.report.md").write_text(report.render(rows, tagger.log, stem + (" (MOCK)" if mock else "")))
    return result


def day_stem(notes_path) -> str:
    return Path(notes_path).name.removesuffix(".notes.csv")


def load_result(stem) -> dict | None:
    p = OUT_DIR / f"{stem}.tagged.json"
    return json.loads(p.read_text()) if p.exists() else None
