"""TradeSea / fills-export parsing. Run: python -m unittest discover tests"""

import csv
import tempfile
import unittest
from pathlib import Path

from tj import parse, parse_fills

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "sample" / "tradesea_2026-10-23.csv"


def write(rows, headers=("Time", "Symbol", "Qty", "Side", "Avg Price", "Commission", "Status")):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    w = csv.writer(f)
    w.writerow(headers)
    w.writerows(rows)
    f.close()
    return f.name


class TestFills(unittest.TestCase):
    def test_sample_matches_tradovate_day(self):
        ts = parse.read_trades(SAMPLE)                        # auto-detects TradeSea
        tv = parse.read_trades(ROOT / "sample" / "tradovate_2026-10-23.csv")
        self.assertEqual(len(ts), 7)
        self.assertEqual([t.side for t in ts], [t.side for t in tv])
        self.assertEqual([t.entry_time for t in ts], [t.entry_time for t in tv])   # Pacific -> NY conversion
        self.assertAlmostEqual(ts[0].pnl, 123.0 - 4 * 0.37)                       # gross - commission

    def test_scale_out_is_one_trade(self):
        t = parse.read_trades(SAMPLE)[3]
        self.assertEqual((t.qty, t.entry_price), (3, 21372.75))
        self.assertAlmostEqual(t.pnl, (44.5 * 2 + 50.5) * 2 - 6 * 0.37)

    def test_cancelled_orders_ignored(self):
        p = write([["10/23/2026 06:00:00", "MNQZ6", 1, "Buy", "100", "0", "Canceled"],
                   ["10/23/2026 06:01:00", "MNQZ6", 1, "Buy", "100", "0", "Filled"],
                   ["10/23/2026 06:02:00", "MNQZ6", 1, "Sell", "110", "0", "Filled"]])
        ts = parse.read_trades(p)
        self.assertEqual((len(ts), ts[0].pnl), (1, 20.0))

    def test_scale_in_fifo(self):
        p = write([["10/23/2026 06:00:00", "MESZ6", 1, "Buy", "100", "0", "Filled"],
                   ["10/23/2026 06:01:00", "MESZ6", 1, "Buy", "102", "0", "Filled"],
                   ["10/23/2026 06:02:00", "MESZ6", 2, "Sell", "104", "0", "Filled"]])
        t = parse.read_trades(p)[0]
        self.assertEqual((t.qty, t.entry_price), (2, 101.0))
        self.assertAlmostEqual(t.pnl, (4 + 2) * 5.0)          # MES = $5/pt

    def test_flip_splits_into_two_trades(self):
        p = write([["10/23/2026 06:00:00", "MNQZ6", 1, "Buy", "100", "0", "Filled"],
                   ["10/23/2026 06:01:00", "MNQZ6", 2, "Sell", "105", "0", "Filled"],   # close long + open short
                   ["10/23/2026 06:02:00", "MNQZ6", 1, "Buy", "101", "0", "Filled"]])
        a, b = parse.read_trades(p)
        self.assertEqual((a.side, a.pnl, b.side, b.pnl), ("long", 10.0, "short", 8.0))

    def test_open_position_at_end_is_skipped(self):
        p = write([["10/23/2026 06:00:00", "MNQZ6", 1, "Buy", "100", "0", "Filled"]])
        self.assertEqual(parse.read_trades(p), [])

    def test_header_aliases(self):
        p = write([["2026-10-23 06:00:00", "/MNQZ26", 1, "B", "100", "$0.37", "Filled"],
                   ["2026-10-23 06:05:00", "/MNQZ26", 1, "S", "90", "$0.37", "Filled"]],
                  headers=("Fill Time", "Contract", "Quantity", "B/S", "Fill Price", "Fees", "Status"))
        self.assertAlmostEqual(parse.read_trades(p)[0].pnl, -20.74)

    def test_symbol_roots(self):
        for s, r in [("MNQZ6", "MNQ"), ("/MNQZ26", "MNQ"), ("NQH7", "NQ"), ("MES 12-26", "MES"),
                     ("ESZ6.CME", "ES"), ("MGCG7", "MGC")]:
            self.assertEqual(parse_fills.symbol_root(s), r)
        with self.assertRaises(ValueError):
            parse_fills.symbol_root("ZBZ6")

    def test_unknown_file_rejected(self):
        with self.assertRaises(ValueError):
            parse.read_trades(write([["1", "2"]], headers=("a", "b")))


if __name__ == "__main__":
    unittest.main()
