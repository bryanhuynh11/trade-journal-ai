"""The contract between the model and the code.

The model must return exactly this JSON shape. Code checks every field; anything
that fails is retried once with the error, then marked UNTAGGED. Nothing the model
says reaches the report without passing validate().
"""

SETUPS = {
    "liquidity_sweep_reversal",  # took a high/low then reversed
    "fvg_entry",                 # entry in a fair value gap
    "order_block",
    "breaker_block",
    "silver_bullet",             # FVG entry inside the 10-11 / 2-3 silver bullet window
    "ote_retracement",           # 62-79% fib retracement entry
    "smt_divergence",
    "breakout_chase",            # not an ICT setup -- chasing momentum
    "other",
    "unclear",                   # note doesn't say enough to tell
}

# Behavioural mistakes only the trader's own words can reveal.
# Mistakes code can prove (outside killzone, oversized, over max trades, past loss limit)
# are deliberately NOT here -- see facts.rule_flags().
MISTAKES = {
    "fomo_entry",
    "early_entry",          # didn't wait for confirmation
    "no_stop",
    "moved_stop",
    "revenge_trade",
    "early_exit",           # cut a winner before target
    "held_loser",           # ignored stop / hoped
    "ignored_htf_bias",
    "no_plan",
}

EMOTIONS = {"calm", "confident", "anxious", "frustrated", "greedy", "fearful", "bored", "unclear"}

MAX_LESSON_CHARS = 140


def validate(obj, note: str) -> list[str]:
    """Return a list of problems. Empty list == valid."""
    errs = []
    if not isinstance(obj, dict):
        return ["response is not a JSON object"]

    expected = {"setup", "mistakes", "emotion", "followed_plan", "evidence", "lesson", "confidence"}
    extra = set(obj) - expected
    missing = expected - set(obj)
    if missing:
        errs.append(f"missing keys: {sorted(missing)}")
    if extra:
        errs.append(f"unexpected keys: {sorted(extra)}")

    if obj.get("setup") not in SETUPS:
        errs.append(f"setup must be one of {sorted(SETUPS)}")

    m = obj.get("mistakes")
    if not isinstance(m, list) or any(x not in MISTAKES for x in m):
        errs.append(f"mistakes must be a list drawn from {sorted(MISTAKES)} (use [] for none)")
    elif len(set(m)) != len(m):
        errs.append("mistakes contains duplicates")

    if obj.get("emotion") not in EMOTIONS:
        errs.append(f"emotion must be one of {sorted(EMOTIONS)}")

    if obj.get("followed_plan") not in (True, False, None):
        errs.append("followed_plan must be true, false, or null")

    ev = obj.get("evidence")
    if not isinstance(ev, str) or not ev.strip():
        errs.append("evidence must be a non-empty exact quote from the note")
    elif _norm(ev) not in _norm(note):
        # Anti-hallucination check: the quote has to actually be in what the trader wrote.
        errs.append("evidence is not an exact quote from the note")

    lesson = obj.get("lesson")
    if not isinstance(lesson, str) or not lesson.strip():
        errs.append("lesson must be a non-empty string")
    elif len(lesson) > MAX_LESSON_CHARS:
        errs.append(f"lesson must be <= {MAX_LESSON_CHARS} characters")

    c = obj.get("confidence")
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
        errs.append("confidence must be a number from 0 to 1")

    return errs


def _norm(s: str) -> str:
    return " ".join(s.lower().replace("’", "'").split())
