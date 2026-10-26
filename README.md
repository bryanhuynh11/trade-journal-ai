# trade-journal-ai

A futures trade journal where **Claude reads my trade notes and labels them**, and plain Python does everything else.

I trade MNQ/MES with ICT concepts. The numbers from my Tradovate export (P&L, win rate) are easy to get. The part that actually matters is what I wrote right after each trade ("FOMO'd", "revenge trade", "cut it early because I was nervous"), and that part was never in my stats. This pipeline turns those notes into structured tags so I can see, for example, that my `note:fomo_entry` trades lose money and my `clean` trades don't.

TCSS 490, Artifact 3: *a system where a model does some of the work every time it runs.*

## How it runs

```
Tradovate Performance CSV
        │
        ▼
python journal.py template <csv>     ← code: parse, sort, number trades, killzones
        │
        ▼
notes/<day>.notes.csv                ← me: fill in `note` and `risk_usd`
        │
        ▼
python journal.py run <notes.csv>
   ├─ code: re-derive every number from the CSV, R-multiples, rule flags
   ├─ MODEL: claude -p, once per trade with a note → JSON label
   ├─ code: validate → retry once with errors → else UNTAGGED
   ├─ code: cache valid labels (re-runs make 0 model calls)
   └─ code: stats by setup / killzone / issue / emotion → out/<day>.report.md
```

`claude -p` runs headless with `--tools ""` (the model can't read files or run commands), a fixed system prompt and `--no-session-persistence`. It uses my Claude Code login, **not** a paid API key.

## What the model is responsible for, and what code checks

| | Who | Why |
|---|---|---|
| Parsing the CSV, sorting, long/short, P&L | **Code** (`tj/parse.py`) | Exact arithmetic. A model could get it wrong and I'd never notice. |
| Killzone, R-multiple, hold time | **Code** (`tj/facts.py`) | It's just the clock and division. |
| Rule breaks: outside killzone, oversized, over max trades/day, past daily loss limit | **Code** (`tj/facts.py`, limits in `tj/rules.py`) | These can be proven from the numbers, so the model isn't allowed to tag them (they aren't in its allowed list). |
| **Setup** (sweep reversal, FVG, silver bullet, OB…) | **Model** | Only my free-text note says what I saw. |
| **Behavioural mistakes** (FOMO, revenge, moved stop, early exit…) | **Model** | Same reason: these come from what I wrote. |
| **Emotion, followed_plan, one-line lesson** | **Model** | Reading tone and summarizing is what the model is good at. |
| Every model field | **Code checks** (`tj/schema.py`) | Values must come from fixed lists. `confidence` must be 0–1. The lesson must be ≤140 chars. There can be no extra keys. **`evidence` must be an exact quote from my note**, so a label can't rest on something I never wrote. |
| Stats, grouping, report | **Code** (`tj/report.py`) | The model never does math. |

If something in the report is wrong, the `rule:` / `note:` prefix tells me who to blame: `rule:` comes from code, `note:` comes from the model.

## Quick start

```bash
# needs Python 3.10+ and Claude Code installed + logged in (`claude` on PATH). No pip installs.
python journal.py template sample/tradovate_2026-10-23.csv --out /tmp/try.notes.csv
python journal.py run sample/2026-10-23.notes.csv          # real Claude, ~6 s per trade
python journal.py run sample/2026-10-23.notes.csv --mock   # keyword stand-in, no Claude
python -m unittest discover tests                           # 16 tests, no Claude calls
```

For your own trades: Tradovate → Account Reports → Performance → export CSV, then `template`, fill in the notes, then `run`.
Edit `tj/rules.py` to set your own killzones and risk limits.

Example output: [`sample/example-report.md`](sample/example-report.md)

## Cost, latency, reliability

These are measured on the sample day (6 notes): about 6.4 s per model call, 0 validator rejections, and an API-equivalent cost of about $0.003 per trade. Claude Code reports that figure, but the plan covers it. A cached re-run makes no model calls and takes 0.08 s. Labels stayed the same across two runs. `confidence` moved by ±0.1. See [`LOG.md`](LOG.md).

## Files

- `journal.py`: CLI
- `tj/tagger.py`: **the only file that calls a model**. It holds the prompt, the `claude -p` call, JSON extraction, retry, cache and the mock
- `tj/schema.py`: the model's output contract and validator
- `tj/parse.py`, `tj/facts.py`, `tj/rules.py`, `tj/report.py`: plain code
- `LOG.md`: plan and change log
- `CLAUDE.md`: instructions for Claude Code when working in this repo

*The sample data is made up for the demo. It's not real account history.*
