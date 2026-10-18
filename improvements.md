# Improvements

Running list of changes. Items are added as they are reviewed; `[x]` means done.

## UI: clearer, cleaner, more readable and manageable

Raised while reviewing the Live Feed page (`/feed`).

- [x] **Live Feed is cluttered.** Cards replaced by one compact row per inspection: time, decision, defect class, severity and confidence, then code and device in small text. The model name and hash were dropped from the row (they are on the detail page).
- [x] **Repeated badges hide the signal.** Alerts are one red chip with a count (names on hover), and the risk badge is shown only for MEDIUM and HIGH.
- [x] **Make the feed manageable.** Filters for decision, risk and alerts-only (with a clear button), a Pause/Resume button, and a cap of the latest 40 rows.
- [x] **Improve readability.** Single-line rows with the decision first and details secondary. Other pages (Inspections, Overrides, Risk) have not been reviewed for the same clutter yet.

## Data observed while reviewing (affects how clean the demo looks)

- [ ] (Not fixed; reset the data before presenting, see below.) Nearly every record on the Live Feed is flagged `DUPLICATE_EVIDENCE` and `HIGH`. The Executive page shows 369 low-confidence, 343 possible-replay and 84 duplicate-evidence alerts. Cause found: the simulator's start frame is derived from the inspection count, and the stream overlaps frames an earlier run already sent (each new record is an exact copy of one from about 990 inspections earlier). A fresh database, with the simulator started once, produces unique frames. A later fix is to make the simulator track which frame indexes it has used.
- [ ] The database holds about 6,400 inspections from the simulator running in the background for hours. Reset to a small, clean dataset before presenting.

## Add further items below as they come up
