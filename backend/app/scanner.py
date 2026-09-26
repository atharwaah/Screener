from concurrent.futures import ThreadPoolExecutor, as_completed

from .indicators import (
    calculate_adaptive_ma,
    calculate_distance_from_resistance,
)
from .market_data import get_stock_data


# ============================================================
# Adaptive history thresholds
#
# A strict "must have 200 candles" rule hides every recently
# listed stock (IPOs, new listings) from the scanner entirely.
# Instead we use the longest MA / resistance lookback the
# available history actually supports, as long as it clears a
# sensible minimum - and we clearly flag the result as
# "partial history" so it's never confused with a fully
# confirmed 200-MA signal.
# ============================================================

TIMEFRAME_SETTINGS = {
    "1d": {
        "preferred_ma": 200,
        "minimum_ma": 50,
        "preferred_resistance": 252,
        "minimum_resistance": 20,
        "chart_count": 252,
    },
    "1wk": {
        "preferred_ma": 200,
        "minimum_ma": 26,
        "preferred_resistance": 52,
        "minimum_resistance": 8,
        "chart_count": 104,
    },
}


def scan_symbols_parallel(
    symbols,
    worker_fn,
    max_workers: int = 16,
):
    """
    Runs worker_fn(symbol) for every symbol in `symbols` concurrently
    using a thread pool. This is safe/effective here because the work
    is I/O-bound (network calls to Yahoo Finance, DB cache reads) and
    holds the GIL for very little of its time - a thread pool gives a
    large speedup for exactly this kind of workload, turning a
    multi-minute sequential 500-stock scan into tens of seconds.

    Results are returned in the same order as `symbols`. Any exception
    raised by worker_fn is caught per-symbol and turned into an
    {"symbol": ..., "status": "ERROR", "error": ...} dict instead of
    aborting the whole scan - matching the previous sequential
    behavior where one bad symbol didn't take down the rest.
    """

    results = [None] * len(symbols)

    def run(index, symbol):
        try:
            return index, worker_fn(symbol)
        except Exception as e:
            return index, {
                "symbol": symbol,
                "status": "ERROR",
                "error": str(e),
            }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = [
            executor.submit(run, index, symbol)
            for index, symbol in enumerate(symbols)
        ]

        for future in as_completed(futures):
            index, result = future.result()
            results[index] = result

    return results


def build_chart(
    data,
    ma_series,
    resistance_52w,
    candle_count,
):
    chart_data = data.tail(
        candle_count
    ).copy()

    chart_ma = (
        ma_series.tail(candle_count)
        if ma_series is not None
        else None
    )

    chart = []

    for index in range(
        len(chart_data)
    ):

        row = chart_data.iloc[index]

        ma_value = (
            chart_ma.iloc[index]
            if chart_ma is not None
            else None
        )

        date_value = chart_data.index[index]

        if hasattr(
            date_value,
            "strftime",
        ):
            date_string = date_value.strftime(
                "%Y-%m-%d"
            )
        else:
            date_string = str(
                date_value
            )

        chart.append({
            "date": date_string,
            "open": round(
                float(row["Open"]),
                2,
            ),
            "high": round(
                float(row["High"]),
                2,
            ),
            "low": round(
                float(row["Low"]),
                2,
            ),
            "close": round(
                float(row["Close"]),
                2,
            ),
            "volume": round(
                float(row["Volume"]),
                0,
            ),
            "ma200": (
                round(
                    float(ma_value),
                    2,
                )
                if ma_value is not None
                and ma_value == ma_value
                else None
            ),
            "resistance": round(
                resistance_52w,
                2,
            ),
        })

    return chart


def scan_stock(
    symbol: str,
    timeframe: str = "1wk",
    near_resistance_percent: float = 10,
    force_refresh: bool = False,
):

    if timeframe not in TIMEFRAME_SETTINGS:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    settings = TIMEFRAME_SETTINGS[timeframe]

    data = get_stock_data(
        symbol,
        timeframe,
        force_refresh=force_refresh,
    )

    if data.empty:

        return {
            "symbol": symbol,
            "status": "NO_DATA",
        }

    available_candles = len(data)

    current_price = float(
        data["Close"].iloc[-1]
    )

    current_high = float(
        data["High"].iloc[-1]
    )

    # --------------------------------------------------
    # Adaptive long-term MA (200, or the best available)
    # --------------------------------------------------

    ma_series, ma_period_used, ma_is_full = calculate_adaptive_ma(
        data,
        preferred_period=settings["preferred_ma"],
        minimum_period=settings["minimum_ma"],
    )

    if ma_series is None:

        return {
            "symbol": symbol,
            "status": "INSUFFICIENT_HISTORY",
            "current_price": current_price,
            "available_candles": available_candles,
            "timeframe": timeframe,
            "is_recent_listing": True,
            "min_candles_required": settings["minimum_ma"],
        }

    current_ma = ma_series.iloc[-1]

    if current_ma != current_ma:

        return {
            "symbol": symbol,
            "status": "INSUFFICIENT_HISTORY",
            "current_price": current_price,
            "available_candles": available_candles,
            "timeframe": timeframe,
            "is_recent_listing": True,
            "min_candles_required": settings["minimum_ma"],
        }

    # --------------------------------------------------
    # Adaptive 52-week (or best available) resistance
    # --------------------------------------------------

    preferred_resistance = settings["preferred_resistance"]
    minimum_resistance = settings["minimum_resistance"]

    resistance_lookback = min(
        preferred_resistance,
        available_candles - 1,
    )

    if resistance_lookback < minimum_resistance:

        return {
            "symbol": symbol,
            "status": "INSUFFICIENT_HISTORY",
            "current_price": current_price,
            "available_candles": available_candles,
            "timeframe": timeframe,
            "is_recent_listing": True,
            "min_candles_required": minimum_resistance + 1,
        }

    previous_data = data.iloc[
        -(resistance_lookback + 1):-1
    ]

    resistance_52w = float(
        previous_data["High"].max()
    )

    resistance_is_full = (
        resistance_lookback >= preferred_resistance
    )

    is_recent_listing = not (
        ma_is_full and resistance_is_full
    )

    distance = calculate_distance_from_resistance(
        current_price,
        resistance_52w,
    )

    above_ma = (
        current_price
        > float(current_ma)
    )

    near_resistance = (
        current_price <= resistance_52w
        and distance >= 0
        and distance <= near_resistance_percent
    )

    qualified = (
        above_ma
        and near_resistance
    )

    chart = build_chart(
        data=data,
        ma_series=ma_series,
        resistance_52w=resistance_52w,
        candle_count=settings["chart_count"],
    )

    return {
        "symbol": symbol,
        "status": (
            "WATCHLIST"
            if qualified
            else "NOT_QUALIFIED"
        ),
        "current_price": current_price,
        "current_high": current_high,
        "resistance_52w": resistance_52w,
        "resistance_lookback_used": resistance_lookback,
        "distance_percent": distance,
        "ma_200": float(current_ma),
        "ma_period_used": ma_period_used,
        "above_ma_200": above_ma,
        "near_resistance": near_resistance,
        "available_candles": available_candles,
        "timeframe": timeframe,
        "is_recent_listing": is_recent_listing,
        "chart": chart,
    }


def scan_new_52w_high(
    symbol: str,
    force_refresh: bool = False,
):

    minimum_lookback = 30

    data = get_stock_data(
        symbol,
        "1d",
        force_refresh=force_refresh,
    )

    if data.empty:

        return {
            "symbol": symbol,
            "status": "NO_DATA",
        }

    available_candles = len(data)

    if available_candles < (
        minimum_lookback + 1
    ):

        return {
            "symbol": symbol,
            "status": "INSUFFICIENT_HISTORY",
            "current_price": float(
                data["Close"].iloc[-1]
            ),
            "available_candles": available_candles,
            "timeframe": "1d",
            "is_recent_listing": True,
            "min_candles_required": minimum_lookback + 1,
        }

    lookback = min(
        252,
        available_candles - 1,
    )

    is_recent_listing = lookback < 252

    current = data.iloc[-1]

    previous_window = data.iloc[
        -(lookback + 1):-1
    ]

    current_price = float(
        current["Close"]
    )

    current_high = float(
        current["High"]
    )

    current_low = float(
        current["Low"]
    )

    current_open = float(
        current["Open"]
    )

    current_volume = float(
        current["Volume"]
    )

    previous_52w_high = float(
        previous_window["High"].max()
    )

    previous_high_row = previous_window[
        previous_window["High"]
        == previous_52w_high
    ].iloc[-1]

    previous_high_date = (
        previous_high_row.name
    )

    if hasattr(
        previous_high_date,
        "strftime",
    ):
        previous_high_date_string = (
            previous_high_date.strftime(
                "%Y-%m-%d"
            )
        )
    else:
        previous_high_date_string = str(
            previous_high_date
        )

    current_date = data.index[-1]

    if hasattr(
        current_date,
        "strftime",
    ):
        current_date_string = (
            current_date.strftime(
                "%Y-%m-%d"
            )
        )
    else:
        current_date_string = str(
            current_date
        )

    breakout_percent = (
        (
            current_high
            - previous_52w_high
        )
        / previous_52w_high
    ) * 100

    is_new_high = (
        current_high
        > previous_52w_high
    )

    return {
        "symbol": symbol,
        "status": (
            "NEW_52W_HIGH"
            if is_new_high
            else "NOT_NEW_52W_HIGH"
        ),
        "timeframe": "1d",
        "current_date": current_date_string,
        "current_price": current_price,
        "current_high": current_high,
        "current_low": current_low,
        "current_open": current_open,
        "volume": current_volume,
        "previous_52w_high": previous_52w_high,
        "previous_high_date": previous_high_date_string,
        "breakout_percent": breakout_percent,
        "available_candles": available_candles,
        "lookback_used": lookback,
        "is_recent_listing": is_recent_listing,
    }
