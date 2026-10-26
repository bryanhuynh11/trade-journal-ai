"""Deterministic facts and rule checks about each trade. The model gets these as INPUT; it never computes them."""

from datetime import datetime

from . import rules


def killzone(ts: datetime) -> str:
    t = ts.time()
    for name, (start, end) in rules.KILLZONES.items():
        if start <= t < end:
            return name
    return "none"


def r_multiple(pnl: float, risk_usd: float | None) -> float | None:
    if not risk_usd or risk_usd <= 0:
        return None
    return round(pnl / risk_usd, 2)


def rule_flags(trade, trade_index_in_day: int, running_pnl_before: float) -> list[str]:
    """Rule breaks that code can prove from the numbers alone."""
    flags = []
    if killzone(trade.entry_time) == "none":
        flags.append("outside_killzone")
    limit = rules.MAX_CONTRACTS.get(trade.root)
    if limit is not None and trade.qty > limit:
        flags.append("oversized")
    if trade_index_in_day > rules.MAX_TRADES_PER_DAY:
        flags.append("over_max_trades")
    if running_pnl_before <= -rules.DAILY_LOSS_LIMIT_USD:
        flags.append("traded_past_loss_limit")
    return flags


def build_facts(trades, risks: dict[int, float] | None = None) -> list[dict]:
    """One fact dict per trade, in entry order."""
    risks = risks or {}
    out, running, i, day = [], 0.0, 0, None
    for t in trades:
        if t.entry_time.date() != day:          # counters reset each trading day
            day, running, i = t.entry_time.date(), 0.0, 0
        i += 1
        risk = risks.get(t.id)
        f = {
            "id": t.id,
            "symbol": t.symbol,
            "root": t.root,
            "side": t.side,
            "qty": t.qty,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "entry_time": t.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
            "hold_minutes": round((t.exit_time - t.entry_time).total_seconds() / 60, 1),
            "pnl": t.pnl,
            "risk_usd": risk,
            "r_multiple": r_multiple(t.pnl, risk),
            "killzone": killzone(t.entry_time),
            "rule_flags": rule_flags(t, i, running),
        }
        running += t.pnl
        out.append(f)
    return out
