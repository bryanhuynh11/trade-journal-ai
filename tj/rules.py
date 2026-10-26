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

# Dollars per 1.00 point, per contract. Used to compute P&L from fill exports (TradeSea).
POINT_VALUE = {
    "MNQ": 2.0, "NQ": 20.0, "MES": 5.0, "ES": 50.0, "MYM": 0.5, "YM": 5.0,
    "M2K": 5.0, "RTY": 50.0, "MGC": 10.0, "GC": 100.0, "MCL": 100.0, "CL": 1000.0,
}

# Timezone the TradeSea fill times are written in. TradeSea shows times in your computer's
# local time zone, so for Seattle that's Pacific. Change it if your export says otherwise.
# (Times get converted to New York time before killzones are checked.)
FILLS_TZ = "America/Los_Angeles"
