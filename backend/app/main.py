from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import paper_trading
from .config import settings
from .data_cache import load_cached_data_bulk
from .database import Base, engine, get_db
from .scanner import (
    scan_stock,
    scan_new_52w_high,
    scan_symbols_parallel,
)
from .schemas import PortfolioOut, TradeOut, TradeRequest
from .universe import (
    NIFTY_TEST_UNIVERSE,
    get_nifty_500_symbols,
)


app = FastAPI(
    title="52W Resistance Scanner API",
    version="1.0.0",
)


# ============================================================
# DATABASE TABLES (paper trading)
#
# Creates paper_accounts / paper_positions / trades on startup
# if they don't already exist. Needs DATABASE_URL in .env to
# point at a reachable database (Postgres by default; a local
# sqlite file also works, e.g. DATABASE_URL=sqlite:///./paper.db).
# ============================================================

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


# ============================================================
# CORS
# ============================================================

origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def root():
    return {
        "message": "52W Resistance Scanner API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# ============================================================
# SINGLE STOCK SCANNER
# ============================================================

@app.get("/api/scan")
def scan(
    symbol: str = Query(...),
    timeframe: str = Query("1wk"),
    near_resistance_percent: float = Query(
        10.0,
        ge=0,
        le=50,
    ),
    force_refresh: bool = Query(False),
):

    return scan_stock(
        symbol=symbol,
        timeframe=timeframe,
        near_resistance_percent=near_resistance_percent,
        force_refresh=force_refresh,
    )


# ============================================================
# TEST MARKET SCANNER
# ============================================================

@app.get("/api/scan-market")
def scan_market(
    timeframe: str = Query("1wk"),
    near_resistance_percent: float = Query(
        10.0,
        ge=0,
        le=50,
    ),
):

    results = scan_symbols_parallel(
        NIFTY_TEST_UNIVERSE,
        lambda symbol: scan_stock(
            symbol=symbol,
            timeframe=timeframe,
            near_resistance_percent=near_resistance_percent,
        ),
        max_workers=settings.SCAN_MAX_WORKERS,
    )

    return {
        "timeframe": timeframe,
        "near_resistance_percent": near_resistance_percent,
        "total_stocks": len(
            NIFTY_TEST_UNIVERSE
        ),
        "results": results,
    }


# ============================================================
# NIFTY 500 UNIVERSE
# ============================================================

@app.get("/api/universe")
def get_universe():

    symbols = get_nifty_500_symbols()

    return {
        "name": "NIFTY 500",
        "total_stocks": len(symbols),
        "symbols": symbols,
    }


# ============================================================
# NIFTY 500 RESISTANCE SCANNER
# ============================================================

@app.get("/api/scan-nifty500")
def scan_nifty500(
    timeframe: str = Query("1wk"),
    near_resistance_percent: float = Query(
        10.0,
        ge=0,
        le=50,
    ),
    force_refresh: bool = Query(False),
):

    symbols = get_nifty_500_symbols()

    preloaded_cache = (
        {} if force_refresh else load_cached_data_bulk(symbols, timeframe)
    )

    results = scan_symbols_parallel(
        symbols,
        lambda symbol: scan_stock(
            symbol=symbol,
            timeframe=timeframe,
            near_resistance_percent=near_resistance_percent,
            force_refresh=force_refresh,
            preloaded_cache=preloaded_cache,
        ),
        max_workers=settings.SCAN_MAX_WORKERS,
    )

    watchlist = []
    watchlist_established = []
    watchlist_new_listings = []
    insufficient_history = []
    no_data = []
    errors = []

    for result in results:

        status = result.get("status")

        if status == "WATCHLIST":
            watchlist.append(result)

            if result.get("is_recent_listing"):
                watchlist_new_listings.append(result)
            else:
                watchlist_established.append(result)

        elif status == "INSUFFICIENT_HISTORY":
            insufficient_history.append(result)

        elif status == "NO_DATA":
            no_data.append(result)

        elif status == "ERROR":
            errors.append(result)

    watchlist.sort(
        key=lambda x: x.get(
            "distance_percent",
            999,
        )
    )

    watchlist_established.sort(
        key=lambda x: x.get(
            "distance_percent",
            999,
        )
    )

    watchlist_new_listings.sort(
        key=lambda x: x.get(
            "distance_percent",
            999,
        )
    )

    return {
        "scanner": "NIFTY 500",
        "timeframe": timeframe,
        "near_resistance_percent": near_resistance_percent,
        "total_stocks": len(symbols),
        "watchlist_count": len(watchlist),
        "watchlist_established_count": len(
            watchlist_established
        ),
        "watchlist_new_listings_count": len(
            watchlist_new_listings
        ),
        "insufficient_history_count": len(
            insufficient_history
        ),
        "no_data_count": len(no_data),
        "error_count": len(errors),
        "watchlist": watchlist,
        "watchlist_established": watchlist_established,
        "watchlist_new_listings": watchlist_new_listings,
        "insufficient_history": insufficient_history,
        "no_data": no_data,
        "errors": errors,
        "results": results,
    }


# ============================================================
# NIFTY 500 NEW 52-WEEK HIGH SCANNER
# ============================================================

@app.get("/api/scan-nifty500-new-highs")
def scan_nifty500_new_highs(
    force_refresh: bool = Query(False),
):

    symbols = get_nifty_500_symbols()

    preloaded_cache = (
        {} if force_refresh else load_cached_data_bulk(symbols, "1d")
    )

    results = scan_symbols_parallel(
        symbols,
        lambda symbol: scan_new_52w_high(
            symbol,
            force_refresh=force_refresh,
            preloaded_cache=preloaded_cache,
        ),
        max_workers=settings.SCAN_MAX_WORKERS,
    )

    new_52w_high = []
    new_52w_high_established = []
    new_52w_high_new_listings = []
    insufficient_history = []
    no_data = []
    errors = []

    for result in results:

        status = result.get("status")

        if status == "NEW_52W_HIGH":
            new_52w_high.append(result)

            if result.get("is_recent_listing"):
                new_52w_high_new_listings.append(result)
            else:
                new_52w_high_established.append(result)

        elif status == "INSUFFICIENT_HISTORY":
            insufficient_history.append(result)

        elif status == "NO_DATA":
            no_data.append(result)

        elif status == "ERROR":
            errors.append(result)

    new_52w_high.sort(
        key=lambda x: x.get(
            "breakout_percent",
            0,
        ),
        reverse=True,
    )

    new_52w_high_established.sort(
        key=lambda x: x.get(
            "breakout_percent",
            0,
        ),
        reverse=True,
    )

    new_52w_high_new_listings.sort(
        key=lambda x: x.get(
            "breakout_percent",
            0,
        ),
        reverse=True,
    )

    return {
        "scanner": "NIFTY 500 NEW 52-WEEK HIGH",
        "universe_note": (
            "This scans only the NIFTY 500 universe, so counts will "
            "differ from NSE's exchange-wide 52-week-high list, which "
            "also includes SME, BE/BZ (trade-to-trade) and small-cap "
            "series outside the NIFTY 500."
        ),
        "timeframe": "1d",
        "total_stocks": len(symbols),
        "new_52w_high_count": len(new_52w_high),
        "new_52w_high_established_count": len(
            new_52w_high_established
        ),
        "new_52w_high_new_listings_count": len(
            new_52w_high_new_listings
        ),
        "insufficient_history_count": len(
            insufficient_history
        ),
        "no_data_count": len(no_data),
        "error_count": len(errors),
        "new_52w_high": new_52w_high,
        "new_52w_high_established": new_52w_high_established,
        "new_52w_high_new_listings": new_52w_high_new_listings,
        "insufficient_history": insufficient_history,
        "no_data": no_data,
        "errors": errors,
        "results": results,
    }


# ============================================================
# INDIVIDUAL STOCK - NEW 52W HIGH
# ============================================================

@app.get("/api/stock/{symbol}/new-52w-high")
def get_new_52w_high(
    symbol: str,
    force_refresh: bool = Query(False),
):

    return scan_new_52w_high(
        symbol,
        force_refresh=force_refresh,
    )


# ============================================================
# INDIVIDUAL STOCK - DAILY
# ============================================================

@app.get("/api/stock/{symbol}/daily")
def get_daily_stock(
    symbol: str,
    force_refresh: bool = Query(False),
):

    return scan_stock(
        symbol=symbol,
        timeframe="1d",
        near_resistance_percent=10.0,
        force_refresh=force_refresh,
    )


# ============================================================
# INDIVIDUAL STOCK - WEEKLY
# ============================================================

@app.get("/api/stock/{symbol}/weekly")
def get_weekly_stock(
    symbol: str,
    force_refresh: bool = Query(False),
):

    return scan_stock(
        symbol=symbol,
        timeframe="1wk",
        near_resistance_percent=10.0,
        force_refresh=force_refresh,
    )


# ============================================================
# INDIVIDUAL STOCK - CHART API
#
# Frontend uses:
#
# /api/stock/RELIANCE.NS/1d
# /api/stock/RELIANCE.NS/1wk
#
# Keep these routes because the chart component uses
# the timeframe directly.
# ============================================================

@app.get("/api/stock/{symbol}/{timeframe}")
def get_stock_chart(
    symbol: str,
    timeframe: str,
    force_refresh: bool = Query(False),
):

    if timeframe not in ("1d", "1wk"):
        return {
            "symbol": symbol,
            "status": "ERROR",
            "error": "Invalid timeframe. Use 1d or 1wk.",
        }

    return scan_stock(
        symbol=symbol,
        timeframe=timeframe,
        near_resistance_percent=10.0,
        force_refresh=force_refresh,
    )


# ============================================================
# PAPER TRADING
# ============================================================

@app.get("/api/paper/portfolio", response_model=PortfolioOut)
def get_paper_portfolio(db: Session = Depends(get_db)):
    return paper_trading.get_portfolio(db)


@app.post("/api/paper/buy", response_model=TradeOut)
def buy_paper_stock(
    order: TradeRequest,
    db: Session = Depends(get_db),
):
    try:
        return paper_trading.buy(db, order.symbol, order.quantity)
    except paper_trading.PaperTradingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/paper/sell", response_model=TradeOut)
def sell_paper_stock(
    order: TradeRequest,
    db: Session = Depends(get_db),
):
    try:
        return paper_trading.sell(db, order.symbol, order.quantity)
    except paper_trading.PaperTradingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/paper/trades", response_model=list[TradeOut])
def get_paper_trades(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return paper_trading.get_trades(db, limit=limit)


@app.post("/api/paper/reset")
def reset_paper_account(db: Session = Depends(get_db)):
    account = paper_trading.reset_account(db)
    return {
        "status": "RESET",
        "cash": account.cash,
        "initial_cash": account.initial_cash,
    }