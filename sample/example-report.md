# Trade journal — 2026-10-23

**7 trades · net $227.00 · win rate 57% · profit factor 2.05 · avg R 1.4**

> Numbers, killzones and `rule:` flags come from code. `setup`, `note:` mistakes, emotion and lesson come from the model reading your note, and each one passed the validator (evidence must be an exact quote from your note).

## Trades

| # | Time | Side | Qty | P&L | R | Killzone | Setup (model) | Issues | Evidence | Lesson | Tag |
|---|---|---|---:|---:|---:|---|---|---|---|---|---|
| 1 | 10-23 03:12 | short MNQ | 2 | $123.00 | 3.08 | london | `liquidity_sweep_reversal` (0.7) | clean | “London sweep of Asia high at 21490, waited for displacement down and shorted the FVG retest.” | Keep waiting for sweep, displacement, and FVG retest with a defined stop above the high; this patient process produced a 3R win. | ok |
| 2 | 10-23 08:47 | long MNQ | 3 | -$76.50 | -2.12 | ny_am | `breakout_chase` (0.5) | note:early_entry, note:fomo_entry | “Got in too early before the 8:30 news range low was even taken. Saw the candle ripping and FOMO'd.” | Wait for the news range low to be swept and confirmed before entering; don't chase a fast-moving candle. | ok |
| 3 | 10-23 08:55 | long MNQ | 6 | -$114.00 | -1.9 | ny_am | `unclear` (0.9) | rule:oversized, note:revenge_trade, note:no_plan | “Revenge trade after #2, doubled size to make it back. No real setup, just wanted green.” | After a loss, step away and wait for a defined setup; never increase size to recover losses. | ok |
| 4 | 10-23 10:04 | long MNQ | 3 | $279.00 | 9.3 | ny_am | `silver_bullet` (0.9) | clean | “Silver bullet window, FVG on the 1m after SSL sweep at 21365. Entered at the gap, target the 21420 BSL. Took it to target.” | Keep waiting for sweep-plus-FVG setups inside the silver bullet window with a defined liquidity target, as you did here. | ok |
| 5 | 10-23 11:21 | short MNQ | 2 | -$26.00 | -1.3 | none | `other` (0.6) | rule:outside_killzone, rule:over_max_trades, note:no_plan, note:fomo_entry | “Bored at lunch, shorted a 'top' with no setup.” | Skip trades made from boredom; if there's no defined setup and stop, stay flat and step away from the screen. | ok |
| 6 | 10-23 13:44 | long MNQ | 2 | $32.00 | 1.33 | ny_pm | `order_block` (0.8) | rule:over_max_trades, note:early_exit | “Cut it early at +4 because I was nervous after the morning, it ran another 30 pts after.” | Set a target before entry and hold to it; don't let earlier losses push you to exit a valid setup early. | ok |
| 7 | 10-23 15:10 | short MNQ | 1 | $9.50 | — | ny_pm | `no_note` (0.0) | rule:over_max_trades | “” |  | skipped_no_note |

## Breakdown

### By setup

| | Trades | Net P&L | Win rate | Expectancy | Avg R |
|---|---:|---:|---:|---:|---:|
| `liquidity_sweep_reversal` | 1 | $123.00 | 100% | $123.00 | 3.08 |
| `breakout_chase` | 1 | -$76.50 | 0% | -$76.50 | -2.12 |
| `unclear` | 1 | -$114.00 | 0% | -$114.00 | -1.9 |
| `silver_bullet` | 1 | $279.00 | 100% | $279.00 | 9.3 |
| `other` | 1 | -$26.00 | 0% | -$26.00 | -1.3 |
| `order_block` | 1 | $32.00 | 100% | $32.00 | 1.33 |
| `no_note` | 1 | $9.50 | 100% | $9.50 | — |

### By killzone

| | Trades | Net P&L | Win rate | Expectancy | Avg R |
|---|---:|---:|---:|---:|---:|
| `ny_am` | 3 | $88.50 | 33% | $29.50 | 1.76 |
| `ny_pm` | 2 | $41.50 | 100% | $20.75 | 1.33 |
| `london` | 1 | $123.00 | 100% | $123.00 | 3.08 |
| `none` | 1 | -$26.00 | 0% | -$26.00 | -1.3 |

### By issue

| | Trades | Net P&L | Win rate | Expectancy | Avg R |
|---|---:|---:|---:|---:|---:|
| `rule:over_max_trades` | 3 | $15.50 | 67% | $5.17 | 0.02 |
| `clean` | 2 | $402.00 | 100% | $201.00 | 6.19 |
| `note:fomo_entry` | 2 | -$102.50 | 0% | -$51.25 | -1.71 |
| `note:no_plan` | 2 | -$140.00 | 0% | -$70.00 | -1.6 |
| `note:early_entry` | 1 | -$76.50 | 0% | -$76.50 | -2.12 |
| `rule:oversized` | 1 | -$114.00 | 0% | -$114.00 | -1.9 |
| `note:revenge_trade` | 1 | -$114.00 | 0% | -$114.00 | -1.9 |
| `rule:outside_killzone` | 1 | -$26.00 | 0% | -$26.00 | -1.3 |
| `note:early_exit` | 1 | $32.00 | 100% | $32.00 | 1.33 |

### By emotion

| | Trades | Net P&L | Win rate | Expectancy | Avg R |
|---|---:|---:|---:|---:|---:|
| `calm` | 1 | $123.00 | 100% | $123.00 | 3.08 |
| `anxious` | 1 | -$76.50 | 0% | -$76.50 | -2.12 |
| `frustrated` | 1 | -$114.00 | 0% | -$114.00 | -1.9 |
| `confident` | 1 | $279.00 | 100% | $279.00 | 9.3 |
| `bored` | 1 | -$26.00 | 0% | -$26.00 | -1.3 |
| `fearful` | 1 | $32.00 | 100% | $32.00 | 1.33 |
| `unclear` | 1 | $9.50 | 100% | $9.50 | — |

## Model run

- Tag status: ok 6, skipped_no_note 1
- Model calls this run: 6 (0 rejected by validator), 38.2s total, API-equivalent cost $0.0186 (covered by the Claude Code plan, not billed)
