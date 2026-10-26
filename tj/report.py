"""Stats and the markdown report. Plain code: all math happens here, never in the model."""

from collections import defaultdict


def _stats(rows: list[dict]) -> dict:
    n = len(rows)
    pnl = [r["pnl"] for r in rows]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    rs = [r["r_multiple"] for r in rows if r.get("r_multiple") is not None]
    return {
        "trades": n,
        "net_pnl": round(sum(pnl), 2),
        "win_rate": round(len(wins) / n, 3) if n else 0.0,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "profit_factor": round(sum(wins) / -sum(losses), 2) if losses else None,
        "expectancy": round(sum(pnl) / n, 2) if n else 0.0,
        "avg_r": round(sum(rs) / len(rs), 2) if rs else None,
    }


def group_stats(rows: list[dict], key) -> dict[str, dict]:
    buckets = defaultdict(list)
    for r in rows:
        keys = key(r)
        for k in (keys if isinstance(keys, list) else [keys]):
            buckets[k].append(r)
    return {k: _stats(v) for k, v in sorted(buckets.items(), key=lambda kv: -len(kv[1]))}


def all_issues(r: dict) -> list[str]:
    """Code-proven rule flags + model-tagged behavioural mistakes, kept distinguishable."""
    return [f"rule:{f}" for f in r["rule_flags"]] + [f"note:{m}" for m in r["mistakes"]] or ["clean"]


def money(v):
    return "—" if v is None else (f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}")


def _table(title: str, groups: dict[str, dict]) -> str:
    lines = [f"### {title}", "", "| | Trades | Net P&L | Win rate | Expectancy | Avg R |", "|---|---:|---:|---:|---:|---:|"]
    for k, s in groups.items():
        lines.append(f"| `{k}` | {s['trades']} | {money(s['net_pnl'])} | {s['win_rate']:.0%} | "
                     f"{money(s['expectancy'])} | {s['avg_r'] if s['avg_r'] is not None else '—'} |")
    return "\n".join(lines) + "\n"


def render(rows: list[dict], call_log: list[dict], source: str) -> str:
    total = _stats(rows)
    status = defaultdict(int)
    for r in rows:
        status[r["status"]] += 1
    calls = len(call_log)
    secs = sum(c.get("seconds") or 0 for c in call_log)
    cost = sum(c.get("cost_usd") or 0 for c in call_log)

    out = [f"# Trade journal — {source}", ""]
    out.append(f"**{total['trades']} trades · net {money(total['net_pnl'])} · win rate {total['win_rate']:.0%} · "
               f"profit factor {total['profit_factor'] if total['profit_factor'] is not None else '—'} · "
               f"avg R {total['avg_r'] if total['avg_r'] is not None else '—'}**")
    out.append("")
    out.append("> Numbers, killzones and `rule:` flags come from code. `setup`, `note:` mistakes, emotion and "
               "lesson come from the model reading your note, and each one passed the validator "
               "(evidence must be an exact quote from your note).")
    out.append("")

    out.append("## Trades\n")
    out.append("| # | Time | Side | Qty | P&L | R | Killzone | Setup (model) | Issues | Evidence | Lesson | Tag |")
    out.append("|---|---|---|---:|---:|---:|---|---|---|---|---|---|")
    for r in rows:
        ev = r["evidence"].replace("|", "/")
        out.append(f"| {r['id']} | {r['entry_time'][5:16]} | {r['side']} {r['root']} | {r['qty']} | {money(r['pnl'])} | "
                   f"{r['r_multiple'] if r['r_multiple'] is not None else '—'} | {r['killzone']} | `{r['setup']}` "
                   f"({r['confidence']:.1f}) | {', '.join(all_issues(r))} | “{ev}” | {r['lesson']} | {r['status']} |")
    out.append("")

    out.append("## Breakdown\n")
    out.append(_table("By setup", group_stats(rows, lambda r: r["setup"])))
    out.append(_table("By killzone", group_stats(rows, lambda r: r["killzone"])))
    out.append(_table("By issue", group_stats(rows, all_issues)))
    out.append(_table("By emotion", group_stats(rows, lambda r: r["emotion"])))

    out.append("## Model run\n")
    out.append(f"- Tag status: " + ", ".join(f"{k} {v}" for k, v in sorted(status.items())))
    out.append(f"- Model calls this run: {calls} ({sum(1 for c in call_log if not c['ok'])} rejected by validator), "
               f"{secs:.1f}s total, API-equivalent cost ${cost:.4f} (covered by the Claude Code plan, not billed)")
    failed = [r for r in rows if r["status"] == "failed"]
    for r in failed:
        out.append(f"- Trade {r['id']} UNTAGGED: {'; '.join(r.get('errors', []))}")
    out.append("")
    return "\n".join(out)
