"""Plain-code trading rules. Everything here is deterministic -- the model never decides these."""

from datetime import time

# Timezone the Tradovate export timestamps are written in (set in Tradovate settings).
EXPORT_TZ = "America/New_York"

# ICT killzones, New York time. (start, end) -- end is exclusive.
KILLZONES = {
    "asia":      (time(20, 0), time(23, 59, 59)),
    "london":    (time(2, 0),  time(5, 0)),
    "ny_am":     (time(7, 0),  time(11, 0)),   # includes the 10-11 silver bullet window
    "ny_lunch":  (time(12, 0), time(13, 0)),
    "ny_pm":     (time(13, 30), time(16, 0)),
}

# Personal risk rules. Breaking these is flagged by code, not by the model.
MAX_CONTRACTS = {"MNQ": 5, "MES": 5, "NQ": 1, "ES": 1}
MAX_TRADES_PER_DAY = 4
DAILY_LOSS_LIMIT_USD = 300.0
