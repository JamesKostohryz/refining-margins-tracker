#!/usr/bin/env python3
"""
PBF live refining-margin tracker.

WHY: PBF's reported quarterly adjusted EPS is driven by its realized gross
refining margin ($/bbl), which has tracked ~53% of the NY Harbor 2-1-1 crack
over 2026 (Q2: $23.40 vs 2-1-1 $43.48 = 54%; Q3: $34.56 vs ~$65 = 53%). This
script fetches the live NYMEX futures legs (NY-Harbor-delivery RBOB + ULSD, plus
WTI and Brent), computes a NYH-2-1-1 proxy, accumulates a quarter-to-date average,
and writes it so a Google Sheet can flow it through the EPS engine. It does NOT
track WCS (no reliable free live feed) -- WCS is a manual context input in the
sheet; wide WCS = capture at the top of the band, narrow = the bottom.

Runs on GitHub Actions (open internet). Primary source stooq (CSV, no key),
fallback yfinance. Brent is optional; if it is missing the WTI-based crack is used.
"""
import csv, datetime as dt, io, sys, urllib.request, os

STOOQ = "https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv"
LEGS = {"wti": "cl.f", "brent": "cb.f", "rbob": "rb.f", "ulsd": "ho.f"}
YF   = {"wti": "CL=F", "brent": "BZ=F", "rbob": "RB=F", "ulsd": "HO=F"}
GAL = 42.0  # gallons per barrel (products quoted $/gal)

def fetch_stooq(sym):
    with urllib.request.urlopen(STOOQ.format(sym=sym), timeout=20) as r:
        rows = list(csv.DictReader(io.StringIO(r.read().decode())))
    if rows and rows[0].get("Close") not in (None, "", "N/D"):
        return float(rows[0]["Close"])
    raise ValueError(f"no close for {sym}")

def fetch_yf(yf_sym):
    import yfinance as yf
    h = yf.Ticker(yf_sym).history(period="5d")
    return float(h["Close"].dropna().iloc[-1])

def price(leg):
    try:
        return fetch_stooq(LEGS[leg])
    except Exception as e:
        print(f"  stooq {leg} failed ({e}); trying yfinance", file=sys.stderr)
        return fetch_yf(YF[leg])

def nyh_211(rbob_gal, ulsd_gal, crude_bbl):
    """NYH 2-1-1 proxy $/bbl: 2 crude -> 1 gasoline + 1 distillate."""
    return (rbob_gal * GAL + ulsd_gal * GAL) / 2.0 - crude_bbl

def quarter_of(d):
    return f"{d.year}Q{(d.month - 1)//3 + 1}"

def main():
    today = dt.date.today()
    p = {}
    for leg in ("wti", "rbob", "ulsd"):      # essential legs
        p[leg] = price(leg)
    try:
        p["brent"] = price("brent")          # preferred crude leg; optional
    except Exception as e:
        print(f"  brent unavailable ({e}); using WTI-based crack", file=sys.stderr)
        p["brent"] = None

    crack_wti = nyh_211(p["rbob"], p["ulsd"], p["wti"])
    crack_brent = nyh_211(p["rbob"], p["ulsd"], p["brent"]) if p["brent"] else None

    hist = "data/history.csv"
    rows = []
    if os.path.exists(hist):
        with open(hist) as f:
            rows = list(csv.DictReader(f))
    rows = [r for r in rows if r["date"] != today.isoformat()]
    rows.append({"date": today.isoformat(), "quarter": quarter_of(today),
                 "rbob": f"{p['rbob']:.4f}", "ulsd": f"{p['ulsd']:.4f}",
                 "wti": f"{p['wti']:.2f}", "brent": (f"{p['brent']:.2f}" if p['brent'] else ""),
                 "nyh_211_brent": (f"{crack_brent:.2f}" if crack_brent is not None else ""),
                 "nyh_211_wti": f"{crack_wti:.2f}"})
    rows.sort(key=lambda r: r["date"])
    cols = ["date","quarter","rbob","ulsd","wti","brent","nyh_211_brent","nyh_211_wti"]
    with open(hist, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

    cq = quarter_of(today)
    qrows = [r for r in rows if r["quarter"] == cq]
    def avg(key):
        vals = [float(r[key]) for r in qrows if r.get(key) not in (None, "")]
        return sum(vals)/len(vals) if vals else None
    qtd_brent, qtd_wti = avg("nyh_211_brent"), avg("nyh_211_wti")
    qtd = qtd_brent if qtd_brent is not None else qtd_wti
    basis = "brent" if qtd_brent is not None else "wti"
    latest = crack_brent if crack_brent is not None else crack_wti

    out = [("as_of", today.isoformat()), ("current_quarter", cq),
           ("days_in_qtd", str(len(qrows))),
           ("nyh_211_qtd", f"{qtd:.2f}" if qtd is not None else ""),
           ("nyh_211_qtd_basis", basis),
           ("nyh_211_latest", f"{latest:.2f}"),
           ("nyh_211_qtd_brent", f"{qtd_brent:.2f}" if qtd_brent is not None else ""),
           ("nyh_211_qtd_wti", f"{qtd_wti:.2f}" if qtd_wti is not None else ""),
           ("rbob_usd_gal", f"{p['rbob']:.4f}"), ("ulsd_usd_gal", f"{p['ulsd']:.4f}"),
           ("wti_usd_bbl", f"{p['wti']:.2f}"),
           ("brent_usd_bbl", f"{p['brent']:.2f}" if p['brent'] else "")]
    with open("data/latest.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["key","value"]); w.writerows(out)
    print("OK", today, cq, "QTD 2-1-1 =", qtd, basis)

if __name__ == "__main__":
    main()
