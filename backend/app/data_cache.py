from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import StringIO

import pandas as pd

from .database import SessionLocal
from .models import PriceCache

# ============================================================
# DB-backed price cache
#
# This used to be local .pkl files under backend/data/cache.
# That works fine locally, but on hosts with an ephemeral
# filesystem (e.g. Render's free web services) those files are
# wiped on every restart/redeploy, forcing a full re-download
# from Yahoo every time. Storing the cache in the same database
# as paper trading fixes that: it survives restarts, and is
# shared across every instance/worker instead of being local to
# one machine's disk.
#
# Public function signatures are unchanged from the old file
# cache, so market_data.py / scanner.py needed no changes.
# ============================================================

CACHE_MAX_AGE_HOURS = 4


def _get_row(db, symbol: str, timeframe: str) -> PriceCache | None:
    return (
        db.query(PriceCache)
        .filter(
            PriceCache.symbol == symbol,
            PriceCache.timeframe == timeframe,
        )
        .first()
    )


def _is_fresh(updated_at: datetime) -> bool:
    return (
    datetime.now(timezone.utc).replace(tzinfo=None) - updated_at
    ) < timedelta(hours=CACHE_MAX_AGE_HOURS)


def load_cached_data(
    symbol: str,
    timeframe: str,
    force_refresh: bool = False,
) -> pd.DataFrame | None:

    if force_refresh:
        return None

    db = SessionLocal()

    try:
        row = _get_row(db, symbol, timeframe)

        if row is None or not _is_fresh(row.updated_at):
            return None

        try:
            data = pd.read_json(StringIO(row.data), orient="table")

            if not isinstance(data, pd.DataFrame) or data.empty:
                return None

            return data

        except Exception as e:
            print(f"Cache decode failed for {symbol} {timeframe}: {e}")
            return None

    finally:
        db.close()


def save_cached_data(
    symbol: str,
    timeframe: str,
    data: pd.DataFrame,
) -> None:

    db = SessionLocal()

    try:
        payload = data.to_json(orient="table", date_format="iso")

        row = _get_row(db, symbol, timeframe)

        if row is None:
            row = PriceCache(
                symbol=symbol,
                timeframe=timeframe,
                data=payload,
                updated_at=datetime.utcnow(),
            )
            db.add(row)
        else:
            row.data = payload
            row.updated_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"Cache save failed for {symbol} {timeframe}: {e}")

    finally:
        db.close()


def delete_cached_data(
    symbol: str,
    timeframe: str,
) -> None:

    db = SessionLocal()

    try:
        db.query(PriceCache).filter(
            PriceCache.symbol == symbol,
            PriceCache.timeframe == timeframe,
        ).delete()
        db.commit()

    except Exception as e:
        db.rollback()
        print(f"Could not delete cache for {symbol}: {e}")

    finally:
        db.close()


def clear_cache() -> None:

    db = SessionLocal()

    try:
        db.query(PriceCache).delete()
        db.commit()

    except Exception as e:
        db.rollback()
        print(f"Could not clear cache: {e}")

    finally:
        db.close()
