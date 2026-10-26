"""The coach chat: the second (and last) place a model is used.

Model's job: read the code-computed stats + my recent notes and answer my question about how to
improve, in plain words. It never computes anything.

Code around it:
  - builds the context (tj/history.coach_context) -- the model sees nothing else
  - runs `claude -p` headless with no tools
  - NUMBER CHECK: every $ amount and % in the answer must appear in the stats the model was given.
    Any that don't are flagged in the UI as "not in your stats", so a made-up figure can't pass silently.
"""

import re

from .tagger import ClaudeCLI, MockModel

SYSTEM = (
    "You are a futures trading-process coach for one trader. You only see their own journal stats and notes. "
    "Coach their PROCESS (setups, timing, discipline, risk, emotions). Do not predict markets, recommend "
    "instruments, or give investment advice. Use only numbers that appear in the STATS block, copied exactly "
    "as written there (same $ and % formatting); never compute new numbers. If the data is too thin to say "
    "something, say so. Be direct and specific. Plain text, no markdown headings; short bullet lines are fine. "
    "Max ~170 words."
)

MAX_TURNS = 6            # how much earlier conversation is sent back each time


def build_prompt(question: str, context: str, history: list[dict]) -> str:
    convo = ""
    for m in history[-MAX_TURNS:]:
        who = "TRADER" if m.get("role") == "user" else "COACH"
        convo += f"{who}: {str(m.get('content', ''))[:1200]}\n"
    return (f"STATS (computed by code from my trade exports -- the only numbers you may use):\n{context}\n\n"
            + (f"EARLIER IN THIS CHAT:\n{convo}\n" if convo else "")
            + f"TRADER: {question.strip()[:800]}\nCOACH:")


# ---------- number check ----------

_NUM = re.compile(r"-?\$-?\d[\d,]*(?:\.\d+)?|-?\d+(?:\.\d+)?%")


def _parse(tok: str) -> tuple[str, float, bool]:
    """'-$1,234.50' -> ('$', 1234.5, True has decimals); '57%' -> ('%', 57.0, False)"""
    kind = "%" if tok.endswith("%") else "$"
    raw = tok.replace(",", "").replace("$", "").replace("%", "").lstrip("-")
    return kind, abs(float(raw)), "." in raw


def check_numbers(answer: str, context: str) -> dict:
    """Every $ amount and % the coach writes must match a number in the stats it was given.
    Signs are ignored ("-$118.44" may be written "a $118.44 loss"); a whole-number figure may round
    a stat ("$213" for $212.94), but nothing else passes."""
    dollars = {_parse(t)[1] for t in _NUM.findall(context) if not t.endswith("%")}
    dollars |= {abs(float(x)) for x in re.findall(r"(?<![\w.%$])-?\d+\.\d{2}(?![\d%])", context)}   # table cells
    pcts = {_parse(t)[1] for t in _NUM.findall(context) if t.endswith("%")}
    found = _NUM.findall(answer)
    bad = []
    for tok in found:
        kind, v, has_dec = _parse(tok)
        pool = pcts if kind == "%" else dollars
        tol = 0.005 if has_dec else 0.5
        if not any(abs(v - a) <= tol for a in pool):
            bad.append(tok)
    return {"checked": len(found), "unverified": sorted(set(bad))}


# ---------- ask ----------

class MockCoach(MockModel):
    def __call__(self, prompt):
        return ("(mock coach) I can't really read your stats in mock mode. Run without Mock to ask Claude.",
                {"seconds": 0.0, "cost_usd": 0.0, "model": "mock"})


def make_backend(mock=False, model=None):
    return MockCoach() if mock else ClaudeCLI(model=model, system=SYSTEM, timeout=180)


def ask(question: str, context: str, history: list[dict], backend) -> dict:
    if not question.strip():
        raise ValueError("empty question")
    text, meta = backend(build_prompt(question, context, history))
    text = text.strip()
    return {"answer": text, **check_numbers(text, context), **meta}
