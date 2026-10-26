#!/usr/bin/env python3
"""Generate a made-up 2-week trade history (TradeSea fills CSVs + filled-in notes) for the demo.

    python sample/make_history.py      -> sample/history/tradesea_2026-10-XX.csv + 2026-10-XX.notes.csv

Deterministic (fixed seed). The patterns are planted on purpose so the timeline and the coach have
something real to find: NY AM silver bullets work, chasing and revenge trades don't, lunch trades bleed,
and winners get cut early when the trader is nervous. NOT real account history.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent / "history"
rng = random.Random(490)
DAYS = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16",
        "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]
COMM = 0.37

# name: (NY window start, end, win prob, (win R lo, hi), qty, setup notes, loss notes, win notes)
ARCH = {
    "silver_bullet": ((10, 0), (10, 50), 0.70, (1.8, 3.2), 3,
        ["Silver bullet. SSL swept at {lvl}, entered the 1m FVG, target {tgt} BSL.",
         "10am silver bullet: sweep of the 9:50 low, displacement up, filled in the FVG.",
         "SB window. Took the FVG after the sell-side raid at {lvl}, stop under the swing."],
        ["Stopped out, the FVG didn't hold. Followed the plan though, calm.", "Took the stop, setup was valid. Fine."],
        ["Hit target. Calm, textbook.", "Paid to {tgt}. Confident, did what I planned."]),
    "sweep": ((2, 15), (4, 30), 0.62, (1.5, 2.6), 2,
        ["London sweep of the Asia {side_lvl} at {lvl}, waited for the MSS then entered.",
         "London: Asia {side_lvl} raided, shift on the 5m, entered on the retrace."],
        ["Stopped. Sweep kept going, no real displacement. Calm.", "Loss, fine, stop was where it should be."],
        ["Worked, took it to the London target. Calm.", "Clean, got paid. Felt good."]),
    "fvg": ((9, 35), (10, 0), 0.55, (1.2, 2.2), 2,
        ["NY open FVG entry after the 9:30 range, bias {bias} from the 1H.",
         "Entered the 5m FVG off the open, HTF bias {bias}."],
        ["Stopped, open was choppy. Ok.", "Loss. Probably too early in the open."],
        ["Worked. Held to target.", "Decent, partials at the first target."]),
    "chase": ((8, 32), (9, 5), 0.25, (0.8, 1.5), 3,
        ["Saw the news candle ripping and chased it.", "FOMO'd into the 8:30 move, no setup really, just didn't want to miss it.",
         "Jumped in before the range low was taken, too early, felt like it was leaving without me."],
        ["Reversed right after I got in. Anxious.", "Stopped, classic chase. Annoyed."],
        ["Got lucky, it kept going.", "Worked but I know it was a chase."]),
    "revenge": (None, None, 0.20, (0.5, 1.2), 6,
        ["Revenge trade after the last loss, doubled size to get it back.", "Right after the stop out, jumped back in bigger. Frustrated.",
         "Wanted the loss back immediately, no setup, went size."],
        ["Lost again. Should have walked away.", "Stopped again, frustrated."],
        ["Made it back but that was dumb.", "Won but it was gambling."]),
    "lunch": ((11, 20), (12, 50), 0.30, (0.6, 1.2), 2,
        ["Bored at lunch, shorted what looked like a top.", "Lunch chop, took a scalp off a 1m 'OB' with no real reason.",
         "Nothing going on, forced a trade at lunch."],
        ["Chopped out. Bored.", "Small loss, shouldn't have been in."],
        ["Small win, still a lunch trade.", "Scalped a few points, meh."]),
    "pm_ob": ((13, 40), (15, 15), 0.50, (1.0, 2.0), 2,
        ["PM session OB retest at {lvl} in line with the AM trend.", "Afternoon continuation, entered the {bias} OB retest."],
        ["Stopped, PM faded. Fine.", "Loss, PM was slow."],
        ["Worked, but I cut it early because I was nervous, it ran more after.", "Got paid, held most of it."]),
}
DAY_PLANS = [  # sequences of archetypes per day; "revenge" is inserted after a loss when the plan says so
    ["sweep", "silver_bullet"], ["chase", "revenge", "silver_bullet"], ["fvg", "lunch", "pm_ob"],
    ["silver_bullet", "pm_ob"], ["chase", "revenge", "lunch", "pm_ob"], ["sweep", "fvg", "silver_bullet"],
    ["fvg", "chase", "revenge"], ["silver_bullet", "lunch"], ["sweep", "silver_bullet", "pm_ob", "lunch"],
]


def fmt(t: str, **kw):
    return t.format(**kw)


def main():
    OUT.mkdir(exist_ok=True)
    price = 21150.0
    for day, plan in zip(DAYS, DAY_PLANS):
        trades, last_exit, last_loss = [], None, False
        for name in plan:
            start, end, p_win, (rlo, rhi), qty, setup_n, loss_n, win_n = ARCH[name]
            if name == "revenge":
                if not last_loss:
                    continue
                t0 = last_exit + timedelta(minutes=rng.randint(2, 7))
            else:
                a = datetime.fromisoformat(f"{day} {start[0]:02d}:{start[1]:02d}")
                b = datetime.fromisoformat(f"{day} {end[0]:02d}:{end[1]:02d}")
                t0 = a + timedelta(seconds=rng.randint(0, int((b - a).total_seconds())))
                if last_exit and t0 <= last_exit:
                    t0 = last_exit + timedelta(minutes=rng.randint(3, 15))
            side = rng.choice(["long", "short"])
            stop_pts = rng.choice([10, 12, 15, 18])
            win = rng.random() < p_win
            r = round(rng.uniform(rlo, rhi), 2) if win else -1.0
            if name == "pm_ob" and win and rng.random() < 0.5:
                r = round(rng.uniform(0.3, 0.6), 2)            # the "cut it early" winners
            hold = timedelta(minutes=rng.randint(3, 45))
            price += rng.uniform(-60, 60)
            entry = round(price * 4) / 4
            move = round(r * stop_pts * 4) / 4
            exit_ = entry + move if side == "long" else entry - move
            lvl = int(entry - stop_pts) if side == "long" else int(entry + stop_pts)
            note = " ".join([
                fmt(rng.choice(setup_n), lvl=lvl, tgt=int(exit_), side_lvl="low" if side == "long" else "high",
                    bias="bullish" if side == "long" else "bearish"),
                fmt(rng.choice(win_n if win else loss_n), tgt=int(exit_)),
            ])
            if name == "pm_ob" and win and r < 0.7:
                note = note.split(".")[0] + ". Cut it early at +" + str(int(abs(move))) + " because I was nervous, it ran more after."
            trades.append({"t0": t0, "t1": t0 + hold, "side": side, "qty": qty, "entry": entry, "exit": exit_,
                           "risk": stop_pts * 2 * qty, "note": note})
            last_exit, last_loss = t0 + hold, not win

        # TradeSea-style fills, Pacific time (NY - 3h)
        fills = []
        for t in trades:
            e_side, x_side = ("Buy", "Sell") if t["side"] == "long" else ("Sell", "Buy")
            for when, s, px in ((t["t0"], e_side, t["entry"]), (t["t1"], x_side, t["exit"])):
                fills.append({"Time": (when - timedelta(hours=3)).strftime("%m/%d/%Y %I:%M:%S %p"),
                              "Symbol": "MNQZ6", "Qty": t["qty"], "Side": s, "Avg Price": f"{px:.2f}",
                              "Commission": f"${COMM * t['qty']:.2f}", "Status": "Filled"})
        csv_path = OUT / f"tradesea_{day}.csv"
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(fills[0]))
            w.writeheader()
            w.writerows(fills)
        with (OUT / f"{day}.notes.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "note", "risk_usd"])
            for i, t in enumerate(sorted(trades, key=lambda t: t["t0"]), 1):
                w.writerow([i, t["note"], t["risk"]])
        print(f"{day}: {len(trades)} trades")


if __name__ == "__main__":
    main()
