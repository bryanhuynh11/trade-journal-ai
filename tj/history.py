"""All past trades across every imported day: the timeline, the totals, and the stats the coach is given.
Plain code only -- every number here is computed, never generated."""

from collections import defaultdict
from datetime import datetime

from . import pipeline, report


def load_all() -> list[dict]:
    """Every trade from every notes file, in time order. Numbers are re-derived from each day's CSV;
    Claude's labels are merged in where that day has been tagged."""
    rows = []
    for p in sorted(pipeline.NOTES_DIR.glob("*.notes.csv")):
        stem = pipeline.day_stem(p)
        try:
            fs, by_id = pipeline.load_day(p)
        except Exception:
            continue                                   # a broken day shouldn't take down the history page
        res = pipeline.load_result(stem) or {}
        tags = {t["id"]: t for t in res.get("trades", [])}
        for x in fs:
            t = tags.get(x["id"], {})
            rows.append({
                **x,
                "day": stem,
                "date": x["entry_time"][:10],
                "note": by_id[x["id"]].get("note", ""),
                "setup": t.get("setup", "untagged"),
                "mistakes": t.get("mistakes", []),
                "emotion": t.get("emotion", "unclear"),
                "lesson": t.get("lesson", ""),
                "evidence": t.get("evidence", ""),
                "tagged": bool(t) and not res.get("mock"),
            })
    rows.sort(key=lambda r: r["entry_time"])
    return rows


def _issues(r):
    return report.all_issues(r)


def summary(rows: list[dict]) -> dict:
    if not rows:
        return {"trades": 0}
    total = report._stats(rows)

    # equity curve + max drawdown (peak-to-trough on cumulative P&L)
    equity, running, peak, max_dd = [], 0.0, 0.0, 0.0
    for r in rows:
        running += r["pnl"]
        peak = max(peak, running)
        max_dd = min(max_dd, running - peak)
        equity.append(round(running, 2))

    days = defaultdict(list)
    for r in rows:
        days[r["date"]].append(r)
    by_day = [{"date": d, "pnl": round(sum(x["pnl"] for x in v), 2), "trades": len(v)} for d, v in sorted(days.items())]
    green = [d for d in by_day if d["pnl"] > 0]

    # what happens right after a loss (tilt check)
    after_loss = [b for a, b in zip(rows, rows[1:]) if a["pnl"] < 0 and a["date"] == b["date"]]

    hour = lambda r: datetime.strptime(r["entry_time"], "%Y-%m-%d %H:%M:%S").strftime("%H:00 NY")

    return {
        "trades": total["trades"],
        "total": total,
        "equity": equity,
        "max_drawdown": round(max_dd, 2),
        "by_day": by_day,
        "green_days": len(green),
        "best_day": max(by_day, key=lambda d: d["pnl"]),
        "worst_day": min(by_day, key=lambda d: d["pnl"]),
        "after_loss": report._stats(after_loss) if after_loss else None,
        "tagged": sum(1 for r in rows if r["tagged"]),
        "by_setup": report.group_stats(rows, lambda r: r["setup"]),
        "by_issue": report.group_stats(rows, _issues),
        "by_killzone": report.group_stats(rows, lambda r: r["killzone"]),
        "by_emotion": report.group_stats(rows, lambda r: r["emotion"]),
        "by_hour": dict(sorted(report.group_stats(rows, hour).items())),
        "by_side": report.group_stats(rows, lambda r: r["side"]),
        "first": rows[0]["date"],
        "last": rows[-1]["date"],
    }


def coach_context(rows: list[dict], s: dict, recent: int = 15) -> str:
    """The ONLY data the coach sees: code-computed stats plus my recent notes and Claude's earlier labels."""
    if not rows:
        return "No trades imported yet."

    def table(name, groups):
        lines = [f"{name}: group | trades | net $ | win rate | expectancy $ | avg R"]
        for k, v in groups.items():
            lines.append(f"  {k} | {v['trades']} | {v['net_pnl']:.2f} | {v['win_rate']:.0%} | "
                         f"{v['expectancy']:.2f} | {v['avg_r'] if v['avg_r'] is not None else '-'}")
        return "\n".join(lines)

    m = report.money
    t = s["total"]
    out = [
        f"PERIOD: {s['first']} to {s['last']}, {len(s['by_day'])} trading days, {t['trades']} trades "
        f"({s['tagged']} with Claude labels).",
        f"TOTAL: net {m(t['net_pnl'])}, win rate {t['win_rate']:.0%}, avg win {m(t['avg_win'])}, "
        f"avg loss {m(t['avg_loss'])}, profit factor {t['profit_factor']}, expectancy {m(t['expectancy'])}/trade, "
        f"avg R {t['avg_r']}, max drawdown {m(s['max_drawdown'])}.",
        f"DAYS: {s['green_days']} green of {len(s['by_day'])}; best {s['best_day']['date']} {m(s['best_day']['pnl'])}; "
        f"worst {s['worst_day']['date']} {m(s['worst_day']['pnl'])}.",
    ]
    if s["after_loss"]:
        a = s["after_loss"]
        out.append(f"NEXT TRADE AFTER A LOSS (same day): {a['trades']} trades, net {m(a['net_pnl'])}, "
                   f"win rate {a['win_rate']:.0%}.")
    out += [table("BY SETUP", s["by_setup"]), table("BY ISSUE (rule: = code-proven, note: = from my notes)", s["by_issue"]),
            table("BY KILLZONE", s["by_killzone"]), table("BY HOUR (entry)", s["by_hour"]),
            table("BY EMOTION", s["by_emotion"]), table("BY SIDE", s["by_side"])]
    out.append(f"MY {min(recent, len(rows))} MOST RECENT TRADES (newest last):")
    for r in rows[-recent:]:
        out.append(f"  {r['entry_time'][:16]} {r['side']} {r['qty']} {r['root']} {m(r['pnl'])} "
                   f"[{r['killzone']}] setup={r['setup']} issues={','.join(_issues(r))} "
                   f"note=\"{(r['note'] or '-')[:160]}\"")
    return "\n".join(out)
