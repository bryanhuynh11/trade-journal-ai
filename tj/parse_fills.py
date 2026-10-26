"""Turn a fills/orders export (TradeSea, used by Vest Markets and other prop firms) into round-trip trades.

Fill exports list every execution (Time, Symbol, Qty, Side, Avg Price, Commission, Status).
This module pairs them into trades: one trade = flat -> in a position -> flat again.
P&L = points x contract point value x qty, minus commissions. Plain code -- no model.
"""

import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import rules
from .parse import Trade, parse_money

# Header aliases, compared after lowercasing and removing spaces/underscores/slashes.
ALIASES = {
    "time":       ["time", "datetime", "filltime", "date", "timestamp", "executiontime", "filledtime", "createdtime"],
    "symbol":     ["symbol", "contract", "instrument", "ticker"],
    "qty":        ["qty", "quantity", "filledqty", "fillqty", "size", "filled"],
    "side":       ["side", "action", "bs", "buysell", "direction"],
    "price":      ["avgprice", "averageprice", "avgfillprice", "fillprice", "price", "executionprice"],
    "commission": ["commission", "commissions", "fees", "fee", "comm"],
    "status":     ["status", "orderstatus"],
}
REQUIRED = ["time", "symbol", "qty", "side", "price"]
TS_FORMATS = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S",
              "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f", "%m/%d/%y %H:%M:%S")


def _norm(h: str) -> str:
    return re.sub(r"[\s_/\-().]", "", h.strip().lower())


def map_columns(fieldnames) -> dict[str, str]:
    norm = {_norm(f): f for f in fieldnames or []}
    found = {}
    for key, options in ALIASES.items():
        for o in options:
            if o in norm:
                found[key] = norm[o]
                break
    return found


def looks_like_fills(fieldnames) -> bool:
    cols = map_columns(fieldnames)
    return all(k in cols for k in REQUIRED)


def symbol_root(symbol: str) -> str:
    """'/MNQZ25' / 'MNQZ5' / 'MNQ 12-25' / 'MNQZ25.CME' -> 'MNQ' (longest known root wins)."""
    s = symbol.strip().upper().lstrip("/")
    for root in sorted(rules.POINT_VALUE, key=len, reverse=True):
        if s.startswith(root):
            rest = s[len(root):]
            if not rest or not rest[0].isalpha() or re.match(r"^[FGHJKMNQUVXZ]\d", rest):
                return root
    raise ValueError(f"unknown contract {symbol!r}: add its $/point to POINT_VALUE in tj/rules.py")


def parse_time(s: str, tz: str) -> datetime:
    s = s.strip()
    s = re.sub(r"\s*(UTC|Z)$", "", s)
    for fmt in TS_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=ZoneInfo(tz)).astimezone(ZoneInfo(rules.EXPORT_TZ))
        except ValueError:
            continue
    raise ValueError(f"unrecognised time format {s!r}: add it to TS_FORMATS in tj/parse_fills.py")


def read_fills(path, tz: str | None = None) -> list[dict]:
    tz = tz or rules.FILLS_TZ
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = map_columns(reader.fieldnames)
        missing = [k for k in REQUIRED if k not in cols]
        if missing:
            raise ValueError(f"{Path(path).name}: can't find columns for {missing} (headers: {reader.fieldnames})")
        fills = []
        for r in reader:
            status = r.get(cols.get("status", ""), "Filled") or "Filled"
            if status.strip().lower() not in ("filled", "fill", "complete", "completed", "executed"):
                continue                      # cancelled / rejected / working orders aren't trades
            qty = abs(int(float(r[cols["qty"]])))
            if qty == 0:
                continue
            side = r[cols["side"]].strip().lower()
            if side.startswith("b"):
                sign = 1
            elif side.startswith("s"):
                sign = -1
            else:
                raise ValueError(f"unknown side {r[cols['side']]!r}")
            comm = r.get(cols.get("commission", ""), "") or "0"
            fills.append({
                "time": parse_time(r[cols["time"]], tz),
                "symbol": r[cols["symbol"]].strip(),
                "root": symbol_root(r[cols["symbol"]]),
                "signed_qty": sign * qty,
                "price": float(str(r[cols["price"]]).replace(",", "")),
                "commission": abs(parse_money(comm)) if comm.strip() else 0.0,
            })
    fills.sort(key=lambda x: x["time"])
    return fills


def fills_to_trades(fills: list[dict]) -> list[Trade]:
    """Pair fills into flat-to-flat round trips per contract. A fill that flips the position
    closes the old trade and opens a new one with the leftover quantity."""
    open_ = {}          # symbol -> working trade
    pos = defaultdict(int)
    done = []

    for f in fills:
        sym, q = f["symbol"], f["signed_qty"]
        pv = rules.POINT_VALUE[f["root"]]
        comm_per = f["commission"] / abs(q)
        while q:
            cur = pos[sym]
            if cur == 0 or (cur > 0) == (q > 0):              # opening or adding
                t = open_.setdefault(sym, {"symbol": sym, "root": f["root"], "dir": 1 if q > 0 else -1,
                                           "entry_time": f["time"], "in_qty": 0, "in_val": 0.0,
                                           "out_qty": 0, "out_val": 0.0, "pnl": 0.0, "lots": []})
                t["in_qty"] += abs(q)
                t["in_val"] += abs(q) * f["price"]
                t["lots"].append([abs(q), f["price"]])
                t["pnl"] -= comm_per * abs(q)
                pos[sym] += q
                q = 0
            else:                                              # reducing / closing
                t = open_[sym]
                close = min(abs(q), abs(cur))
                t["out_qty"] += close
                t["out_val"] += close * f["price"]
                t["pnl"] -= comm_per * close
                left = close
                while left:                                    # FIFO against entry lots
                    lot = t["lots"][0]
                    n = min(left, lot[0])
                    t["pnl"] += (f["price"] - lot[1]) * t["dir"] * n * pv
                    lot[0] -= n
                    left -= n
                    if lot[0] == 0:
                        t["lots"].pop(0)
                pos[sym] += close if q > 0 else -close
                q += -close if q > 0 else close
                if pos[sym] == 0:
                    t["exit_time"] = f["time"]
                    done.append(open_.pop(sym))

    trades = []
    for t in sorted(done, key=lambda t: t["entry_time"]):
        trades.append(Trade(
            id=0, symbol=t["symbol"], root=t["root"], side="long" if t["dir"] > 0 else "short",
            qty=t["in_qty"],
            entry_price=round(t["in_val"] / t["in_qty"], 4),
            exit_price=round(t["out_val"] / t["out_qty"], 4),
            entry_time=t["entry_time"], exit_time=t["exit_time"], pnl=round(t["pnl"], 2),
        ))
    for i, t in enumerate(trades, 1):
        t.id = i
    return trades
    # Positions still open at the end of the file are left out on purpose (not a finished trade yet).


def read_tradesea(path, tz: str | None = None) -> list[Trade]:
    return fills_to_trades(read_fills(path, tz))
