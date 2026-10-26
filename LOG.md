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

## 2026-10-25: Change: TradeSea support (I trade Vest Markets on TradeSea, not Tradovate)

**Problem.** The parser only read Tradovate's Performance report, which already has one row per round-trip trade with P&L. TradeSea exports **orders/fills** instead (Time, Symbol, Qty, Side, Avg Price, Commission, Status), with no P&L and no notion of a "trade".

**Decision.** This is still 100% a code job. Pairing fills and computing P&L is exact arithmetic, so it goes in a new `tj/parse_fills.py`, not in the model. The model's job and the validator don't change at all.

**What it does.**
- `parse.read_trades()` looks at the headers and picks Tradovate or TradeSea. Header names are matched loosely ("Avg Price" / "Fill Price", "Side" / "B/S", "Commission" / "Fees"...) because I haven't seen a real export yet.
- It skips orders that aren't `Filled` (cancelled stops etc.).
- It pairs fills per contract into flat → position → flat round trips, FIFO against entry lots. A fill that flips long→short closes one trade and opens the next. A position still open at the end of the file is left out.
- P&L = points × `POINT_VALUE` (MNQ $2, MES $5, NQ $20, ES $50, ...) × contracts − commission.
- Fill times are read as Pacific (`FILLS_TZ`) and converted to New York for killzones.
- New sample `sample/tradesea_2026-10-23.csv`: the same 7-trade day as fills in Pacific time, with a two-part scale-out on trade 4, a cancelled stop, and $0.37/contract/side commission. The "Load sample day" button in the UI now uses it.

**Tests.** 9 new (25 total):
- the TradeSea sample gives the same 7 trades and entry times as the Tradovate one
- scale-out stays one trade, and scale-in uses FIFO average entry
- a flip becomes two trades, and a still-open position is skipped
- cancelled orders are ignored
- header aliases, contract roots (`/MNQZ26`, `MES 12-26`, `ESZ6.CME`)
- unknown files are rejected with a clear message

**Still unverified.** The exact TradeSea column names and time format come from a third-party import guide (TradesViz), not from my own export. Next step: export one real day from TradeSea and run it through.

## 2026-10-25: Change: public demo for my professor

**Goal.** A link my professor can open any time.

**Options considered.**
- *Tunnel from my Mac* (ngrok/cloudflared). It only works while my laptop is on and the app is running, and anyone with the link could run Claude on my login.
- *Host the Flask app* with mock tagging. It's always up, but it fakes the one part the assignment is about.
- **Static snapshot of a real run** (chosen). It's always up, free, can't be misused, and shows real Claude output.

**What I built.**
- `build_demo.py` tags the sample day with real `claude -p` (or `--reuse` the last result), then renders Overview / How it works / Notes / Report through Flask's test client with a `DEMO` flag. It rewrites links to relative `.html` files, copies `static/`, and writes everything to `docs/` with `.nojekyll`.
- Demo mode: a banner saying it's a read-only snapshot with a link to the repo, read-only note fields, the Tag button replaced by "See the result →", and an Overview page written for someone seeing it for the first time.
- Screenshots moved to `docs/img/`. Added the macOS double-click launcher to the repo.

**Verified.** I served `docs/` locally and loaded every page in Chromium: all links are relative, there are 0 failed requests and 0 JS errors, and the charts render. On this real run trade 2 came back `unclear` (it was `breakout_chase` before). That's model variance on a vague-ish note, and something to measure in the eval.

## 2026-10-25: Change: timeline of all trades + "what could I do better?" coach chat

**Plan.** I wanted to see every past trade on one timeline with a total P&L chart, and to ask Claude how to improve.

**Model/code split for the new parts.**
- Code (`tj/history.py`): merges every imported day, re-deriving numbers from each CSV and merging Claude's tags where present. It computes the running P&L, max drawdown, P&L by day / hour / setup / issue / emotion / side, and a tilt check (the trade right after a loss, same day only).
- Model (`tj/coach.py`): a second `claude -p` call with a coaching system prompt (process only, no market calls, no investment advice). It sees **only** `history.coach_context()`, the code-computed stats plus my 15 most recent notes. The UI shows that exact text under "What Claude sees".
- Code check: `coach.check_numbers()` pulls every $ amount and % out of the answer and matches it against the numbers in the context. Signs are ignored and whole-dollar rounding is allowed; anything else gets flagged ⚠ under the answer. This is the coach's version of the tagger's "evidence must be an exact quote" rule. The model can phrase things however it likes, but it can't invent a number without it showing.
- The chat keeps the last 6 turns, so follow-up questions work.

**UI.** A new "Timeline & coach" page:
- stat tiles
- a timeline with one bar per trade and a running-total line (click a bar to open that day)
- P&L by day, by hour, by setup and by issue
- the tilt check and a scrollable trade log
- a sticky chat panel with suggested questions

"Tag them with Claude" tags every untagged day in a row. "Load 2-week sample" loads 33 made-up trades.

**Sample data.** `sample/make_history.py` (fixed seed) generates 9 more TradeSea days with planted patterns: silver bullets work, chasing and revenge trades lose, lunch trades bleed, PM winners get cut early.

**Verified.**
- Tagged all 10 days through the UI with real `claude -p` (33 trades, 0 validator rejections).
- Asked the coach 2 questions. Both answers named the planted leaks: FOMO and early entries in the 08:00 NY hour, `no_plan`, and the 08:47 FOMO → 08:55 revenge pair at double size. Both suggested sensible rules.
- Every figure in both answers passed the number check.
- One thing I didn't expect: the tilt check shows the trade *after* a loss is actually net positive (54% win rate). Revenge trades are only part of those trades. The coach handled that correctly: it said revenge trades are "$6.24 net, but your notes call them gambling", rather than calling them fine.
- 8 new tests (33 total): equity, drawdown, after-loss logic, and number-check pass/fail cases.
- The public demo now includes the timeline page with the two real coach answers baked in (the static site can't call Claude).
- Fixed a phone-width overflow (grid children needed `min-width: 0`).

---

## Next / ideas
- Add a `boredom_trade` mistake (see the first-run note).
- Run it on a real week of my own notes and compare the tags to what I'd pick by hand.
- Try `--model haiku` against the default and compare agreement, cost and latency.
- Weekly roll-up across many notes files.
