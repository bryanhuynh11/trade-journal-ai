"""The ONLY place a model is called.

Model's job (and nothing else): read the trader's free-text note for one trade,
plus the facts code already computed, and return a JSON label (schema.py).

Code around it: builds the prompt, runs `claude -p` headless with no tools,
pulls the JSON out, validates it, retries once with the errors, caches results,
and falls back to UNTAGGED if the model still can't produce a valid answer.
"""

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import schema

PROMPT_VERSION = "v3"   # bump when the prompt changes so the cache doesn't serve stale tags

SYSTEM = (
    "You label futures trades for a trading journal. You read ONE trade's journal note "
    "and output ONE JSON object. No prose, no markdown fences."
)

TEMPLATE = """Label this trade from the trader's note. The numbers below were computed by code and are correct; do not recompute or contradict them.

FACTS (from code):
{facts}

TRADER'S NOTE (written right after the trade):
\"\"\"{note}\"\"\"

Return exactly this JSON object:
{{
  "setup": one of {setups},
  "mistakes": list drawn from {mistakes} -- [] if the note shows none. Only tag what the NOTE supports. Do NOT tag killzone, size, trade count, or loss limit; code already checks those,
  "emotion": one of {emotions},
  "followed_plan": true | false | null (null if the note doesn't say),
  "evidence": an EXACT substring copied from the note that best supports your labels,
  "lesson": one actionable sentence, max {max_lesson} characters,
  "confidence": number 0-1, how sure you are of the setup label
}}
If the note is too vague to tell the setup, use "unclear" and a low confidence."""


def build_prompt(facts: dict, note: str) -> str:
    shown = {k: v for k, v in facts.items() if k != "id"}
    return TEMPLATE.format(
        facts=json.dumps(shown, indent=2),
        note=note.strip(),
        setups=sorted(schema.SETUPS),
        mistakes=sorted(schema.MISTAKES),
        emotions=sorted(schema.EMOTIONS),
        max_lesson=schema.MAX_LESSON_CHARS,
    )


def extract_json(text: str):
    """Pull the first {...} object out of model text (tolerates ``` fences and stray prose)."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON object in response")


# ---------- backends ----------

class ClaudeCLI:
    """Runs `claude -p` headless. Uses your Claude Code login, not a paid API key."""

    def __init__(self, model: str | None = None, timeout: int = 120, system: str | None = None):
        if not shutil.which("claude"):
            raise RuntimeError("`claude` not found on PATH. Install Claude Code or use --mock.")
        self.model, self.timeout, self.system = model, timeout, system or SYSTEM

    def __call__(self, prompt: str) -> tuple[str, dict]:
        cmd = ["claude", "-p", "--output-format", "json", "--tools", "",
               "--system-prompt", self.system, "--no-session-persistence"]
        if self.model:
            cmd += ["--model", self.model]
        t0 = time.time()
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=self.timeout)
        if p.returncode != 0:
            raise RuntimeError(f"claude exited {p.returncode}: {p.stderr.strip()[:300]}")
        wrapper = json.loads(p.stdout)
        if wrapper.get("is_error"):
            raise RuntimeError(f"claude error: {str(wrapper.get('result'))[:300]}")
        meta = {
            "seconds": round(time.time() - t0, 1),
            "cost_usd": wrapper.get("total_cost_usd"),   # what it WOULD cost on the API; covered by Claude Code plan
            "model": ",".join(wrapper.get("modelUsage", {}) or {}) or self.model,
        }
        return wrapper.get("result", ""), meta


class MockModel:
    """Keyword-rule stand-in so the pipeline and tests run without Claude. Not smart on purpose."""

    def __call__(self, prompt: str) -> tuple[str, dict]:
        note = prompt.split('"""')[1].strip()
        low = note.lower()
        setup = "unclear"
        for kw, s in [("silver bullet", "silver_bullet"), ("sweep", "liquidity_sweep_reversal"),
                      ("fvg", "fvg_entry"), ("order block", "order_block"), ("ob ", "order_block"),
                      ("breaker", "breaker_block"), ("ote", "ote_retracement"), ("smt", "smt_divergence"),
                      ("chase", "breakout_chase")]:
            if kw in low:
                setup = s
                break
        mistakes = [m for kw, m in [("fomo", "fomo_entry"), ("revenge", "revenge_trade"),
                                    ("moved my stop", "moved_stop"), ("no stop", "no_stop"),
                                    ("too early", "early_entry"), ("cut it", "early_exit")] if kw in low]
        out = {"setup": setup, "mistakes": mistakes, "emotion": "unclear", "followed_plan": None,
               "evidence": note[:60], "lesson": "Mock tag -- run without --mock for real labels.",
               "confidence": 0.3}
        return json.dumps(out), {"seconds": 0.0, "cost_usd": 0.0, "model": "mock"}


# ---------- the guarded call ----------

UNTAGGED = {"setup": "UNTAGGED", "mistakes": [], "emotion": "unclear", "followed_plan": None,
            "evidence": "", "lesson": "", "confidence": 0.0}


class Tagger:
    def __init__(self, backend, cache_path: str | Path | None = None, max_attempts: int = 2):
        self.backend, self.max_attempts = backend, max_attempts
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache = {}
        if self.cache_path and self.cache_path.exists():
            for line in self.cache_path.read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.cache[rec["key"]] = rec["tag"]
        self.log: list[dict] = []   # one entry per model call, for the run log / cost table

    def tag(self, facts: dict, note: str) -> dict:
        if not note.strip():
            return {**UNTAGGED, "setup": "no_note", "status": "skipped_no_note"}

        prompt = build_prompt(facts, note)
        key = hashlib.sha256(f"{PROMPT_VERSION}|{getattr(self.backend, 'model', '')}|{prompt}".encode()).hexdigest()
        if key in self.cache:
            return {**self.cache[key], "status": "cached"}

        errors, attempt_prompt = [], prompt
        for attempt in range(1, self.max_attempts + 1):
            try:
                text, meta = self.backend(attempt_prompt)
                obj = extract_json(text)
                errors = schema.validate(obj, note)
            except Exception as e:      # CLI failure, timeout, bad JSON -- all count as a failed attempt
                text, meta, obj, errors = "", {}, None, [f"{type(e).__name__}: {e}"]
            self.log.append({"trade": facts["id"], "attempt": attempt, "ok": not errors,
                             "errors": errors, **meta})
            if not errors:
                self._save(key, obj)
                return {**obj, "status": "ok" if attempt == 1 else "ok_after_retry"}
            attempt_prompt = (prompt + "\n\nYour previous answer was rejected by the validator:\n- "
                              + "\n- ".join(errors) + "\nReturn a corrected JSON object only.")

        return {**UNTAGGED, "status": "failed", "errors": errors}

    def _save(self, key, obj):
        self.cache[key] = obj
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_path.open("a") as f:
                f.write(json.dumps({"key": key, "tag": obj}) + "\n")
