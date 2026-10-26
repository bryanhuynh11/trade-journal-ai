"""Read a Tradovate 'Performance' CSV export into Trade records. Plain code only."""

import csv
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import rules

TS_FORMATS = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S")


@dataclass
class Trade:
    id: int
    symbol: str          # e.g. MNQZ6
    root: str            # e.g. MNQ
    side: str            # long | short
    qty: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float

    def to_row(self) -> dict:
        d = asdict(self)
        d["entry_time"] = self.entry_time.strftime("%Y-%m-%d %H:%M:%S")
        d["exit_time"] = self.exit_time.strftime("%Y-%m-%d %H:%M:%S")
        return d


def parse_money(s: str) -> float:
    """'$45.00' -> 45.0, '$(22.50)' -> -22.5, '-12.5' -> -12.5"""
    s = s.strip()
    neg = s.startswith("(") or "(" in s or s.startswith("-")
    num = re.sub(r"[^0-9.]", "", s)
    if not num:
        raise ValueError(f"bad money value: {s!r}")
    v = float(num)
    return -v if neg else v


def parse_ts(s: str, tz: str = rules.EXPORT_TZ) -> datetime:
    s = s.strip()
    for fmt in TS_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=ZoneInfo(tz))
        except ValueError:
            continue
    raise ValueError(f"bad timestamp: {s!r}")


def symbol_root(symbol: str) -> str:
    """MNQZ6 -> MNQ, ESH27 -> ES (strip month code + year)."""
    m = re.match(r"^([A-Z0-9]+?)[FGHJKMNQUVXZ]\d{1,2}$", symbol.strip())
    return m.group(1) if m else symbol.strip()


REQUIRED = ["symbol", "qty", "buyPrice", "sellPrice", "pnl", "boughtTimestamp", "soldTimestamp"]


def read_tradovate(path: str | Path, tz: str = rules.EXPORT_TZ) -> list[Trade]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: not a Tradovate Performance export, missing columns {missing}")
        raw = list(reader)

    trades = []
    for r in raw:
        bought = parse_ts(r["boughtTimestamp"], tz)
        sold = parse_ts(r["soldTimestamp"], tz)
        long = bought <= sold
        trades.append(Trade(
            id=0,
            symbol=r["symbol"].strip(),
            root=symbol_root(r["symbol"]),
            side="long" if long else "short",
            qty=int(float(r["qty"])),
            entry_price=float(r["buyPrice"] if long else r["sellPrice"]),
            exit_price=float(r["sellPrice"] if long else r["buyPrice"]),
            entry_time=bought if long else sold,
            exit_time=sold if long else bought,
            pnl=parse_money(r["pnl"]),
        ))
    trades.sort(key=lambda t: t.entry_time)
    for i, t in enumerate(trades, 1):
        t.id = i
    return trades
