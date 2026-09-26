from __future__ import annotations

import pandas as pd
import yfinance as yf

from .data_cache import (
    load_cached_data,
    save_cached_data,
)


TIMEFRAME_CONFIG = {
    "1d": {
        "interval": "1d",
        "period": "2y",
    },
    "1wk": {
        "interval": "1wk",
        "period": "10y",
    },
}


def get_stock_data(
    symbol: str,
    timeframe: str,
    force_refresh: bool = False,
) -> pd.DataFrame:

    if timeframe not in TIMEFRAME_CONFIG:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    cached_data = load_cached_data(
        symbol,
        timeframe,
        force_refresh=force_refresh,
    )

    if cached_data is not None:
        print(
            f"[CACHE] {symbol} {timeframe}"
        )

        return cached_data

    print(
        f"[YAHOO] Downloading {symbol} {timeframe}"
    )

    config = TIMEFRAME_CONFIG[timeframe]

    try:
        ticker = yf.Ticker(symbol)

        data = ticker.history(
            period=config["period"],
            interval=config["interval"],
            auto_adjust=False,
            actions=False,
        )

    except Exception as e:

        print(
            f"[ERROR] Yahoo failed for {symbol}: {e}"
        )

        return pd.DataFrame()

    if data.empty:

        print(
            f"[NO DATA] {symbol}"
        )

        return pd.DataFrame()

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:

        print(
            f"[INVALID DATA] {symbol} missing {missing_columns}"
        )

        return pd.DataFrame()

    data = data.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )

    data = data[required_columns]

    save_cached_data(
        symbol,
        timeframe,
        data,
    )

    return data