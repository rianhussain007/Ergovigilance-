# Case Study Template — pilot → revenue proof

Fill one per site after the §4.5 label handoff. Numbers come from the
`pilot_metrics.py` ledger + the ergonomist agreement JSON — never from
memory, never from research-track vintages.

## Customer (publish only with written permission)

- Site / line:
- Cameras / shifts:
- Pilot window (dates):

## Deployment (facts)

- Compose bundle version / image tags:
- Uptime over window (from ledger):
- Restarts (from ledger):
- In-place upgrades performed (count + "no data loss" evidence):

## Results (ledger-backed)

| Metric (window total / mean) | Value | Source |
|---|---|---|
| Clips saved / truncated | / | ledger `clips_saved`, `clips_truncated` (truncated must be 0) |
| Alerts reviewed / dismissed-as-false | / | ledger + operator log |
| False-alert rate week 1 → week 2 | → | operator dismiss reasons |
| Identity bind coverage | | ledger `distinct_workers` |
| Ergonomist agreement (per band) | | `pilot_labels_ergonomist.csv` + agreement JSON |

## Customer quote

> (Verbatim, approved by the named contact. No paraphrase of numbers.)

— Name, title, date. Written approval filed: ____

## Safe-Claims guardrails (read before publishing)

- Quote **only** the Safe Claims number (87.6% LOW/MEDIUM) or the
  pilot's own ergonomist agreement stats — never 94.1/97.6/88.6/86.4/76.9%.
- "Screening aid, not a medical device" appears in the published piece.
- No HIGH claims unless the ergonomist certified HIGH examples (§4.5).
- Industry benchmarks ($42k/injury, 40%) labeled as benchmarks, not results.
- Reviewer sign-off: ____ Date: ____
