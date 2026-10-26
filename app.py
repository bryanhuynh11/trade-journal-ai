#!/usr/bin/env python3
"""Local web UI for the trade journal.   Run:  python app.py   then open http://127.0.0.1:5050

The web app is only a front end. It calls the same functions as the CLI (tj/pipeline.py),
so the model still does exactly one job: label each trade note via `claude -p`.
"""

import re
import shutil
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from tj import coach, history, pipeline, report, schema
from tj.tagger import build_prompt

ROOT = pipeline.ROOT
DATA_DIR = ROOT / "data"           # uploaded Tradovate CSVs (gitignored)
SAMPLE_CSV = ROOT / "sample" / "tradesea_2026-10-23.csv"
SAMPLE_NOTES = ROOT / "sample" / "2026-10-23.notes.csv"
SAMPLE_HISTORY = ROOT / "sample" / "history"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["DEMO"] = None          # set by build_demo.py: {"date": ..., "repo": ...} -> read-only snapshot


@app.context_processor
def inject_demo():
    return {"demo": app.config["DEMO"]}

JOBS: dict[str, dict] = {}         # stem -> progress of a running tag job
JOBS_LOCK = threading.Lock()


# ---------- helpers ----------

def notes_path(stem: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", stem):
        abort(404)
    p = pipeline.NOTES_DIR / f"{stem}.notes.csv"
    if not p.exists():
        abort(404)
    return p


def list_days():
    days = []
    for p in sorted(pipeline.NOTES_DIR.glob("*.notes.csv"), reverse=True):
        stem = pipeline.day_stem(p)
        rows = pipeline.read_notes(p)
        res = pipeline.load_result(stem)
        days.append({
            "stem": stem,
            "trades": len(rows),
            "with_notes": sum(1 for r in rows if r.get("note", "").strip()),
            "net": round(sum(float(r["pnl"]) for r in rows), 2),
            "tagged": res is not None,
            "mock": bool(res and res.get("mock")),
        })
    return days


@app.template_filter("money")
def money_filter(v):
    return report.money(v)


# ---------- pages ----------

@app.get("/")
def home():
    days = list_days()
    if app.config["DEMO"]:
        days = [d for d in days if d["stem"] == app.config["DEMO"]["stem"]]
    return render_template("home.html", days=days, error=request.args.get("error"))


@app.get("/how")
def how():
    return render_template("how.html", setups=sorted(schema.SETUPS), mistakes=sorted(schema.MISTAKES),
                           emotions=sorted(schema.EMOTIONS))


@app.post("/upload")
def upload():
    f = request.files.get("csv")
    if not f or not f.filename:
        return redirect(url_for("home", error="Choose a TradeSea (or Tradovate) CSV export first."))
    name = secure_filename(f.filename)
    if not name.lower().endswith(".csv"):
        return redirect(url_for("home", error="That isn't a .csv file."))
    DATA_DIR.mkdir(exist_ok=True)
    dest = DATA_DIR / name
    f.save(dest)
    stem = dest.stem
    if (pipeline.NOTES_DIR / f"{stem}.notes.csv").exists():
        return redirect(url_for("day", stem=stem))       # already imported: don't wipe their notes
    try:
        pipeline.make_template(dest)
    except (ValueError, pipeline.PipelineError) as e:
        dest.unlink(missing_ok=True)
        return redirect(url_for("home", error=str(e)))
    return redirect(url_for("day", stem=stem))


@app.post("/sample")
def load_sample():
    stem = "sample-2026-10-23"
    DATA_DIR.mkdir(exist_ok=True)
    csv_copy = DATA_DIR / f"{stem}.csv"
    shutil.copy(SAMPLE_CSV, csv_copy)
    out, _ = pipeline.make_template(csv_copy, force=True)
    filled = {int(r["id"]): r for r in pipeline.read_notes(SAMPLE_NOTES)}
    pipeline.save_notes(out, filled)
    return redirect(url_for("day", stem=stem))


@app.post("/sample-history")
def load_sample_history():
    """Two made-up weeks (sample/history) + the sample day, so the timeline and coach have data."""
    DATA_DIR.mkdir(exist_ok=True)
    load_sample()
    for src in sorted(SAMPLE_HISTORY.glob("tradesea_*.csv")):
        day_ = src.stem.removeprefix("tradesea_")
        stem = f"sample-{day_}"
        csv_copy = DATA_DIR / f"{stem}.csv"
        shutil.copy(src, csv_copy)
        out, _ = pipeline.make_template(csv_copy, force=True)
        filled = {int(r["id"]): r for r in pipeline.read_notes(SAMPLE_HISTORY / f"{day_}.notes.csv")}
        pipeline.save_notes(out, filled)
    return redirect(url_for("history_page"))


@app.get("/history")
def history_page():
    rows = history.load_all()
    if app.config["DEMO"]:
        rows = [r for r in rows if r["day"].startswith("sample-")]
    s = history.summary(rows)
    for r in rows:
        r["issues"] = report.all_issues(r)
    untagged = sorted({r["day"] for r in rows if not r["tagged"] and r["note"].strip()})
    points = [{"t": r["entry_time"], "pnl": r["pnl"], "qty": r["qty"], "setup": r["setup"], "day": r["day"],
               "id": r["id"], "side": r["side"], "kz": r["killzone"], "issues": report.all_issues(r)} for r in rows]
    return render_template("history.html", rows=rows, s=s, points=points, untagged=untagged,
                           context=history.coach_context(rows, s) if rows else "",
                           canned=(app.config["DEMO"] or {}).get("coach", []))


@app.post("/api/coach")
def api_coach():
    data = request.get_json(force=True) or {}
    rows = history.load_all()
    if not rows:
        return jsonify(ok=False, error="No trades yet. Import a day first."), 400
    ctx = history.coach_context(rows, history.summary(rows))
    try:
        backend = coach.make_backend(mock=bool(data.get("mock")))
        out = coach.ask(str(data.get("question", "")), ctx, data.get("history") or [], backend)
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}"), 500
    return jsonify(ok=True, **out)


@app.get("/day/<stem>")
def day(stem):
    p = notes_path(stem)
    try:
        fs, by_id = pipeline.load_day(p)
    except (ValueError, pipeline.PipelineError) as e:
        return redirect(url_for("home", error=f"{stem}: {e}"))
    rows = [{**x, "note": by_id[x["id"]].get("note", ""), "risk_input": by_id[x["id"]].get("risk_usd", "")} for x in fs]
    return render_template("day.html", stem=stem, rows=rows, tagged=pipeline.load_result(stem) is not None,
                           net=round(sum(r["pnl"] for r in rows), 2))


@app.get("/day/<stem>/report")
def day_report(stem):
    notes_path(stem)
    res = pipeline.load_result(stem)
    if not res:
        return redirect(url_for("day", stem=stem))
    rows, calls = res["trades"], res["calls"]

    for r in rows:
        r["issues"] = [] if report.all_issues(r) == ["clean"] else report.all_issues(r)
        if r["status"] not in ("skipped_no_note",):
            shown = {k: r[k] for k in ("id", "symbol", "root", "side", "qty", "entry_price", "exit_price",
                                       "entry_time", "hold_minutes", "pnl", "risk_usd", "r_multiple",
                                       "killzone", "rule_flags")}
            r["prompt"] = build_prompt(shown, r.get("note", ""))
        r["label"] = {k: r.get(k) for k in ("setup", "mistakes", "emotion", "followed_plan", "evidence",
                                            "lesson", "confidence")}
        r["calls"] = [c for c in calls if c["trade"] == r["id"]]

    equity, running = [], 0.0
    for r in rows:
        running += r["pnl"]
        equity.append({"label": f"#{r['id']} {r['entry_time'][11:16]}", "y": round(running, 2)})

    def chart(groups):
        return [{"k": k, "net": s["net_pnl"], "n": s["trades"], "wr": s["win_rate"]} for k, s in groups.items()]

    return render_template(
        "report.html", stem=stem, res=res, rows=rows, calls=calls,
        total=report._stats(rows),
        equity=equity,
        by_setup=chart(report.group_stats(rows, lambda r: r["setup"])),
        by_issue=chart(report.group_stats(rows, report.all_issues)),
        by_killzone=chart(report.group_stats(rows, lambda r: r["killzone"])),
        by_emotion=chart(report.group_stats(rows, lambda r: r["emotion"])),
        n_calls=len(calls),
        n_rejected=sum(1 for c in calls if not c["ok"]),
        secs=round(sum(c.get("seconds") or 0 for c in calls), 1),
        cost=sum(c.get("cost_usd") or 0 for c in calls),
        statuses={s: sum(1 for r in rows if r["status"] == s) for s in sorted({r["status"] for r in rows})},
    )


# ---------- JSON API used by the page's JavaScript ----------

@app.post("/api/day/<stem>/notes")
def api_save_notes(stem):
    p = notes_path(stem)
    data = request.get_json(force=True) or {}
    updates = {int(k): {"note": str(v.get("note", "")), "risk_usd": str(v.get("risk_usd", ""))}
               for k, v in data.get("trades", {}).items()}
    try:
        pipeline.save_notes(p, updates)
    except pipeline.PipelineError as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True)


@app.post("/api/day/<stem>/tag")
def api_tag(stem):
    p = notes_path(stem)
    opts = request.get_json(force=True) or {}
    with JOBS_LOCK:
        job = JOBS.get(stem)
        if job and not job["finished"]:
            return jsonify(ok=False, error="Already tagging this day."), 409
        try:
            backend = pipeline.make_backend(mock=bool(opts.get("mock")), model=opts.get("model") or None)
        except RuntimeError as e:
            return jsonify(ok=False, error=str(e)), 400
        job = JOBS[stem] = {"done": 0, "total": len(pipeline.read_notes(p)), "log": [],
                            "finished": False, "error": None}

    def progress(i, total, x, tag):
        job["done"], job["total"] = i, total
        job["log"].append({"id": x["id"], "status": tag["status"], "setup": tag["setup"],
                           "errors": tag.get("errors", [])})

    def run():
        try:
            pipeline.tag_day(p, backend, use_cache=not opts.get("no_cache"), on_progress=progress)
        except Exception as e:          # surface anything to the page instead of dying silently
            job["error"] = f"{type(e).__name__}: {e}"
        job["finished"] = True

    threading.Thread(target=run, daemon=True).start()
    return jsonify(ok=True)


@app.get("/api/day/<stem>/job")
def api_job(stem):
    notes_path(stem)
    return jsonify(JOBS.get(stem) or {"finished": True, "done": 0, "total": 0, "log": [], "error": None})


@app.get("/api/check-claude")
def api_check_claude():
    return jsonify(available=shutil.which("claude") is not None)


if __name__ == "__main__":
    pipeline.NOTES_DIR.mkdir(exist_ok=True)
    print("Trade Journal AI  ->  http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=False)
