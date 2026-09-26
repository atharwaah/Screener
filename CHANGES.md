# What changed and why

## 1. Weekly chart timeframe couldn't be selected (really: failed for recent listings)
`backend/app/scanner.py` required a hard 200 candles before computing anything.
Any stock without 200 weeks (or 200 days) of history returned
`INSUFFICIENT_HISTORY` with no `chart` key, and the frontend threw a hard
error. Verified this against your cache: Swiggy, Lenskart, Groww, FirstCry,
Ather Energy all failed on Weekly (some on Daily too) for exactly this reason.

**Fix:** `indicators.calculate_adaptive_ma()` now uses the best available MA
period (up to 200) instead of an all-or-nothing 200, with a sane minimum
(50 daily candles / 26 weekly candles) below which a stock is still marked
`INSUFFICIENT_HISTORY`. Same idea for the resistance lookback. Every result
now carries `is_recent_listing`, `ma_period_used`, `resistance_lookback_used`
so you can always tell a full 200-MA signal from a partial-history one.

Full re-scan of all 501 NIFTY 500 symbols against your cached data:
`insufficient_history_count` went from dropping ~90+ stocks silently to **0**,
with 16 of them now showing up correctly flagged as "New listing" in the
watchlist.

## 2. Chart wasn't interactive
`frontend/src/TradingChart.jsx` was a hand-drawn static SVG (hover tooltip
only, no zoom/pan). `lightweight-charts` was already sitting in your
`package.json`/`node_modules`, just never used. Rewired the whole component
to use it: real candlesticks, scroll/pinch zoom, drag-to-pan, crosshair with
an OHLC + MA + resistance tooltip, and a volume histogram pane.

## 3. Screener vs. NSE 52-week-high CSV mismatch
Not a bug. Cross-checked your `52WeekHigh.csv` against `nifty500.csv`: only
6 of the 90 NSE rows are even in the NIFTY 500 universe — the rest are SME
(`SM`), trade-to-trade (`BE`/`BZ`), and small/mid-caps outside your universe.
Ran your scanner against those 6 (ABDL, ENGINERSIN, INDGN, MCX, WELCORP,
ZYDUSLIFE) — all 6 were correctly caught. The backend now returns a
`universe_note` field on `/api/scan-nifty500-new-highs` explaining this, and
the frontend surfaces it as a banner on the New Highs tab.

## 4. Handling recently-listed stocks
Covered by fix #1 above, plus:
- `/api/scan-nifty500` and `/api/scan-nifty500-new-highs` now return separate
  `..._established` and `..._new_listings` buckets alongside the combined list.
- Frontend has an "Include recently listed stocks" toggle (on by default) and
  a "New listing" badge with a tooltip showing exactly what MA/lookback was
  used, so partial-history signals are never confused with confirmed ones.

## 5. UI improvements
- Adjustable "within X% of resistance" input (was hardcoded to 10%)
- Search box + sortable columns on both tables
- Quick symbol lookup in the top bar (type any NSE symbol, opens its chart)
- Friendly in-modal messages for insufficient-history / no-data instead of a
  generic thrown error
- Esc closes the chart modal; loading spinners instead of plain text
- Broadened CORS to also allow `http://127.0.0.1:5173` in `.env`

## Verified (offline, against your existing cache — no network needed)
- `python3 -m py_compile` on all backend modules: clean
- `npm run build` (vite) and `eslint`: clean, no errors
- Full FastAPI TestClient run of `/api/scan-nifty500` and
  `/api/scan-nifty500-new-highs` across all 501 symbols: 0 exceptions

## To run
Same as before — `pip install -r requirements.txt` + `uvicorn app.main:app`
for the backend, `npm install && npm run dev` for the frontend. Only
`AARTIPHARM_NS_1wk.pkl` was missing from your cache; everything else scans
straight from cache so a fresh weekly scan should be fast.
