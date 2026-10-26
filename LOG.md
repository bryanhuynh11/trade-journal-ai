# Build log

Plans, decisions and changes, in order. Kept with Claude (Cowork) during the build.

---

## 2026-10-25: Plan

**Problem.** My trade stats come from the Tradovate export. They tell me *what* happened, not *why*. The why is in the notes I type after each trade, and those never turn into numbers.

**Shape picked.** A Python script that runs `claude -p` headless as one step in a pipeline. I considered:
- extending Docket (Artifact 2) with AI task breakdown, which was less useful to me day to day
- an MCP server over my trades, which is more setup and has a less clear model/code split
- a Claude Code hook for this log, which was the smallest option but has the least model work

**Cost check.** `claude -p` runs on the Claude Code access from class. No API key, nothing billed. I asked Claude to record the `total_cost_usd` that Claude Code reports anyway, so I can say what it *would* cost on the API.

**Model/code split (decided before writing code):**
- Model: note → `setup`, `mistakes`, `emotion`, `followed_plan`, `evidence`, `lesson`, `confidence`.
- Code: everything with a number or a clock in it.
- Rule: if code can *prove* a mistake from the CSV (outside killzone, oversized), the model is not allowed to tag it. Those are left out of the model's allowed list on purpose.
- Every model field gets validated. `evidence` must be an exact quote from the note. That is my hallucination check.

**Planned flow.** `template` (CSV → notes file to fill in) → `run` (tag + report).

---

## 2026-10-25: Build

- `tj/parse.py`: reads the Tradovate Performance CSV. It handles `$(22.50)` negatives, sorts by entry (Tradovate lists trades in exit order) and infers long/short from which timestamp comes first.
- `tj/facts.py` + `tj/rules.py`: killzones (NY time), R-multiple from `risk_usd`, rule flags. The daily counters reset per date.
- `tj/schema.py`: the output contract and `validate()`.
- `tj/tagger.py`: prompt, `claude -p --output-format json --tools "" --system-prompt … --no-session-persistence`, a JSON extractor that tolerates ``` fences, **one retry that feeds the validator errors back to the model**, then `UNTAGGED`. Notes that are empty never call the model.
- Cache: sha256 of (prompt version + model + prompt) → label, in `out/.tag_cache.jsonl`.
- `MockModel`: a keyword stand-in so the whole pipeline runs and tests pass without Claude.
- `tj/report.py`: per-trade table plus breakdowns by setup / killzone / issue / emotion, and a "model run" section with calls, rejections, time and cost.
- Sample day: 7 made-up MNQ trades with realistic notes. One is a revenge trade at 6 contracts, one is a bored lunch trade, and one has an empty note.

## 2026-10-25: Change: killzone bug (code, not model)

First mock run: my silver bullet trade at 10:04 came out as `killzone: none` and got flagged `outside_killzone`. The model wasn't involved. My `ny_am` window was 07:00–10:00, but the silver bullet window is 10:00–11:00. I changed `ny_am` to 07:00–11:00 and added a test (`10:30 → ny_am`). This is the payoff of the split: the bad flag was prefixed `rule:`, so I knew right away it was my code.

## 2026-10-25: First real run

- 6 calls, 0 validator rejections, ~6.4 s per call, ~40 s total.
- Labels I agree with: sweep reversal, silver bullet, order block, revenge + no_plan on trade 3, early_exit on trade 6.
- Debatable: trade 2 ("saw the candle ripping and FOMO'd") was tagged `breakout_chase`. That's fair, since it *was* a chase. Trade 5 ("bored at lunch") was tagged `fomo_entry` as well as `no_plan`. I'd say boredom isn't FOMO. Possible fix: add a `boredom_trade` mistake.
- Cost: the first call showed ~$0.06 (prompt cache warm-up); later calls were ~$0.003–0.01.

## 2026-10-25: Change: model metadata

`modelUsage` from `claude -p` can list more than one model per call (the CLI used a small model alongside the main one). I was only keeping the first key, so I now record all of them.

## 2026-10-25: Second real run (no cache)

- Same setup and mistake labels on all 6 trades. `confidence` moved by ±0.1 on two trades. Total API-equivalent cost: $0.0186 (~$0.003/trade), 38 s.
- A cached re-run makes 0 model calls and takes 0.08 s.
- Saved as `sample/example-report.md`.

## 2026-10-25: Tests

16 `unittest` tests, none of which call Claude:
- parsing (money, symbol roots, sort, sides, total P&L)
- killzones, rule flags, R-multiple
- validator: hallucinated evidence rejected, code-owned flag rejected, bad enums/ranges, fenced JSON
- tagger: **bad answer → retry with errors → ok**; always-bad → `UNTAGGED`; empty note → 0 calls; cache hit → 0 calls

## 2026-10-25: Change: local web UI

**Plan.** Using the CLI meant editing a CSV in a spreadsheet and reading a Markdown file, which made it hard to see the whole flow. I wanted a local web app that makes the model/code split visible.

**Decisions.**
- Flask, local only (127.0.0.1:5050; 5000 clashes with macOS AirPlay).
- I moved the pipeline steps out of `journal.py` into `tj/pipeline.py`, so the CLI and the web app call the *same* code. The UI adds no new model logic.
- Every field on screen has a badge: `CODE` (computed), `YOU` (typed), `MODEL` (Claude). `rule:` chips are blue (code) and `note:` chips are purple (model).
- Tagging runs in a background thread. The page polls `/api/day/<day>/job` for a progress bar, because 6 trades × ~6 s is too long for one blocking request.
- Each trade card on the report can expand to show the exact prompt sent, the validated JSON, and each attempt's time, cost and validator errors. That's the debugging view.
- Chart.js is bundled locally instead of loaded from a CDN, so the page works offline.

**Bugs found while building.**
- A bad "Risk $" value (like `abc`) was saved to the notes file *before* validation, which then broke the day page. Now `save_notes()` validates first and nothing invalid is written.
- The upload error message showed my full disk path. It now shows just the file name.

**Verified.** I clicked through import → notes → **Save & tag with Claude** → report with Playwright, using real `claude -p`: 6 calls, 0 rejections, 38.4 s. The labels matched the CLI runs (trade 3 came back `other` instead of `unclear` this time; both are reasonable for "no real setup"). There were no browser console errors, and the layout works at phone width. All 16 tests still pass.

---

## Next / ideas
- Add a `boredom_trade` mistake (see the first-run note).
- Run it on a real week of my own notes and compare the tags to what I'd pick by hand.
- Try `--model haiku` against the default and compare agreement, cost and latency.
- Weekly roll-up across many notes files.
