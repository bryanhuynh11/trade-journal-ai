"""Timeline stats + coach guardrails. No Claude calls."""

import unittest

from tj import coach, history


def row(t, pnl, setup="fvg_entry", day="d1", kz="ny_am", risk=None):
    return {"entry_time": t, "pnl": pnl, "setup": setup, "day": day, "date": t[:10], "killzone": kz,
            "side": "long", "qty": 1, "root": "MNQ", "r_multiple": (pnl / risk) if risk else None,
            "rule_flags": [], "mistakes": [], "emotion": "calm", "note": "n", "tagged": True}


ROWS = [row("2026-10-12 09:40:00", 100), row("2026-10-12 09:55:00", -50), row("2026-10-12 10:10:00", -30),
        row("2026-10-13 10:05:00", -80), row("2026-10-13 10:30:00", 200)]


class TestHistory(unittest.TestCase):
    def test_equity_and_drawdown(self):
        s = history.summary(ROWS)
        self.assertEqual(s["equity"], [100, 50, 20, -60, 140])
        self.assertEqual(s["max_drawdown"], -160)                 # peak 100 -> trough -60
        self.assertEqual([d["pnl"] for d in s["by_day"]], [20, 120])
        self.assertEqual(s["green_days"], 2)

    def test_after_loss_same_day_only(self):
        s = history.summary(ROWS)
        # after -50 comes -30 (same day). -30 is the last trade of 10-12, so the next day doesn't count.
        # after -80 (10-13) comes +200.
        self.assertEqual((s["after_loss"]["trades"], s["after_loss"]["net_pnl"]), (2, 170))

    def test_context_has_the_numbers(self):
        ctx = history.coach_context(ROWS, history.summary(ROWS))
        self.assertIn("net $140.00", ctx)
        self.assertIn("max drawdown -$160.00", ctx)


class TestCoachNumberCheck(unittest.TestCase):
    CTX = "TOTAL: net $212.94, win rate 57%, avg loss $-74.50\n  ny_am | 3 | -118.44 | 33% | 5.17 | -"

    def test_exact_and_rounded_pass(self):
        r = coach.check_numbers("Net $212.94 (about $213), win rate 57%, ny_am lost $118.44 at 33%.", self.CTX)
        self.assertEqual((r["checked"], r["unverified"]), (5, []))

    def test_sign_ignored(self):
        self.assertEqual(coach.check_numbers("avg loss of $74.50", self.CTX)["unverified"], [])

    def test_made_up_numbers_flagged(self):
        r = coach.check_numbers("You'd make $500 more with an 80% win rate, or $212.90.", self.CTX)
        self.assertEqual(r["unverified"], ["$212.90", "$500", "80%"])

    def test_prompt_contains_context_and_history(self):
        p = coach.build_prompt("why?", "STATS_HERE", [{"role": "user", "content": "hi"},
                                                      {"role": "assistant", "content": "hello"}])
        self.assertIn("STATS_HERE", p)
        self.assertIn("TRADER: hi", p)
        self.assertIn("COACH: hello", p)
        self.assertTrue(p.endswith("TRADER: why?\nCOACH:"))

    def test_mock_backend(self):
        out = coach.ask("q", self.CTX, [], coach.make_backend(mock=True))
        self.assertIn("mock", out["answer"])


if __name__ == "__main__":
    unittest.main()
