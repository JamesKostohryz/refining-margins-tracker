# refining-margins-tracker

Daily live feed of the U.S. NY Harbor 2-1-1 crack spread, used to drive the
current-quarter gross-refining-margin (GRM) input of the PBF quarterly EPS model.

**What it does.** A GitHub Action runs each weekday after NYMEX settle, fetches
NY-Harbor-delivery RBOB + ULSD futures plus WTI and Brent, computes a **NYH 2-1-1
crack** ($/bbl), appends it to `data/history.csv`, and writes the **quarter-to-date
average** to `data/latest.csv`.

**Why 2-1-1 x capture.** PBF's realized GRM has run ~53% of the NYH 2-1-1 through
2026 (Q2: $23.40 vs $43.48 = 54%; Q3: $34.56 vs ~$65 = 53%). The Google Sheet
control panel reads `data/latest.csv` via `IMPORTDATA`, multiplies the QTD crack by
a tunable capture ratio to get an estimated realized GRM, and flows it through the
EPS engine for the quarter in progress.

**WCS.** No reliable free live feed for the WTI-WCS heavy-sour differential, which
is the second driver of PBF's capture. It is a manual context input in the sheet:
wide WCS (>~$18) -> top of the capture band; narrow -> the bottom.

**Sources.** Primary stooq (CSV, no key); fallback yfinance. No API key required.
`data/latest.csv` is the file the Sheet pulls; `data/history.csv` is the full log.
