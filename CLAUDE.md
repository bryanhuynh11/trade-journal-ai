# CLAUDE.md

Context for Claude Code when working in this repo.

## The one rule of this project
The model does exactly one thing: it turns one trade's free-text note, plus code-computed facts, into a JSON label (see `tj/schema.py`). Everything else is plain Python. Keep it that way.

- Never move arithmetic, killzones, or rule checks into the prompt. If code can prove it from the CSV, it belongs in `tj/facts.py`.
- Never let a model field reach the report without going through `schema.validate()`.
- `tj/tagger.py` is the only file that may call `claude`. Tests must never call it: use `MockModel` or a fake backend.
- If you change the prompt or the schema, bump `PROMPT_VERSION` in `tj/tagger.py` so the cache doesn't serve stale tags.
- If you change killzones, setups, or mistakes, update the README table and the tests in the same change.

## Commands
- Tests: `python -m unittest discover tests`
- Demo without Claude: `python journal.py run sample/2026-10-23.notes.csv --mock`
- Real run: `python journal.py run sample/2026-10-23.notes.csv`

## Log
After any meaningful change, add a dated entry to `LOG.md`: what was planned, what changed, and why.
