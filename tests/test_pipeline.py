"""Run with:  python -m unittest discover tests   (no extra installs, no Claude calls)."""

import json
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tj import parse, facts, schema
from tj.tagger import Tagger, MockModel, extract_json

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "sample" / "tradovate_2026-10-23.csv"
NY = ZoneInfo("America/New_York")

GOOD = {"setup": "fvg_entry", "mistakes": [], "emotion": "calm", "followed_plan": True,
        "evidence": "shorted the FVG retest", "lesson": "Repeat it.", "confidence": 0.8}
NOTE = "London sweep, then shorted the FVG retest. Calm."


class TestParse(unittest.TestCase):
    def test_money(self):
        self.assertEqual(parse.parse_money("$45.00"), 45.0)
        self.assertEqual(parse.parse_money("$(22.50)"), -22.5)
        self.assertEqual(parse.parse_money("$1,234.50"), 1234.5)

    def test_symbol_root(self):
        self.assertEqual(parse.symbol_root("MNQZ6"), "MNQ")
        self.assertEqual(parse.symbol_root("ESH27"), "ES")

    def test_sample_sorted_and_sides(self):
        ts = parse.read_tradovate(SAMPLE)
        self.assertEqual([t.id for t in ts], list(range(1, 8)))
        self.assertTrue(all(a.entry_time <= b.entry_time for a, b in zip(ts, ts[1:])))
        self.assertEqual(ts[0].side, "short")          # sold first
        self.assertEqual(ts[0].entry_price, 21482.25)
        self.assertAlmostEqual(sum(t.pnl for t in ts), 227.0)


class TestFacts(unittest.TestCase):
    def kz(self, h, m):
        return facts.killzone(datetime(2026, 10, 23, h, m, tzinfo=NY))

    def test_killzones(self):
        self.assertEqual(self.kz(3, 0), "london")
        self.assertEqual(self.kz(10, 30), "ny_am")     # silver bullet window counts
        self.assertEqual(self.kz(11, 30), "none")
        self.assertEqual(self.kz(14, 0), "ny_pm")

    def test_rule_flags_on_sample(self):
        fs = facts.build_facts(parse.read_tradovate(SAMPLE))
        self.assertIn("oversized", fs[2]["rule_flags"])          # 6 MNQ > 5
        self.assertIn("outside_killzone", fs[4]["rule_flags"])   # 11:21
        self.assertIn("over_max_trades", fs[4]["rule_flags"])    # 5th trade
        self.assertEqual(fs[0]["rule_flags"], [])

    def test_r_multiple(self):
        self.assertEqual(facts.r_multiple(123, 40), 3.08)
        self.assertIsNone(facts.r_multiple(10, None))


class TestValidator(unittest.TestCase):
    def test_good(self):
        self.assertEqual(schema.validate(GOOD, NOTE), [])

    def test_hallucinated_evidence_rejected(self):
        bad = {**GOOD, "evidence": "waited for the order block"}
        self.assertTrue(any("exact quote" in e for e in schema.validate(bad, NOTE)))

    def test_code_owned_flag_rejected(self):
        bad = {**GOOD, "mistakes": ["outside_killzone"]}     # model may not tag what code checks
        self.assertTrue(schema.validate(bad, NOTE))

    def test_bad_enums_and_ranges(self):
        bad = {**GOOD, "setup": "vibes", "confidence": 1.7, "lesson": "x" * 200, "extra": 1}
        self.assertEqual(len(schema.validate(bad, NOTE)), 4)

    def test_extract_json_with_fences(self):
        self.assertEqual(extract_json('Sure!\n```json\n{"a": "}"}\n```'), {"a": "}"})


class FlakyModel:
    """First answer invents evidence; second answer is fine. Proves the retry loop works."""
    def __init__(self):
        self.calls = []

    def __call__(self, prompt):
        self.calls.append(prompt)
        ans = GOOD if len(self.calls) > 1 else {**GOOD, "evidence": "made up quote"}
        return json.dumps(ans), {"seconds": 0, "cost_usd": 0}


class TestTagger(unittest.TestCase):
    F = {"id": 1, "pnl": 10.0}

    def test_retry_then_ok(self):
        m = FlakyModel()
        out = Tagger(m).tag(self.F, NOTE)
        self.assertEqual(out["status"], "ok_after_retry")
        self.assertIn("rejected by the validator", m.calls[1])

    def test_gives_up_untagged(self):
        always_bad = lambda p: ("not json at all", {})
        out = Tagger(always_bad).tag(self.F, NOTE)
        self.assertEqual((out["status"], out["setup"]), ("failed", "UNTAGGED"))

    def test_empty_note_never_calls_model(self):
        m = FlakyModel()
        out = Tagger(m).tag(self.F, "   ")
        self.assertEqual((out["status"], len(m.calls)), ("skipped_no_note", 0))

    def test_cache(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            m = FlakyModel()
            Tagger(m, cache_path=Path(d) / "c.jsonl").tag(self.F, NOTE)
            n = len(m.calls)
            out = Tagger(m, cache_path=Path(d) / "c.jsonl").tag(self.F, NOTE)
            self.assertEqual((out["status"], len(m.calls)), ("cached", n))

    def test_mock_backend_passes_validator(self):
        out = Tagger(MockModel()).tag(self.F, NOTE)
        self.assertEqual(out["status"], "ok")


if __name__ == "__main__":
    unittest.main()
