import pandas as pd


def calculate_200_ma(
    data: pd.DataFrame,
    period: int = 200,
) -> pd.Series:
    return data["Close"].rolling(period).mean()


def calculate_adaptive_ma(
    data: pd.DataFrame,
    preferred_period: int = 200,
    minimum_period: int = 50,
):
    """
    Calculate a long-term moving average that degrades gracefully
    for recently-listed stocks that don't yet have `preferred_period`
    candles of history.

    Instead of refusing to compute anything below `preferred_period`
    candles (which hides every recent IPO from the scanner), this uses
    the longest MA that the available history actually supports, as
    long as it's at least `minimum_period` candles. This keeps recent
    listings visible (clearly flagged) instead of silently dropping
    them.

    Returns (ma_series, period_used, is_full_history).
    """

    available = len(data)

    if available >= preferred_period:
        period_used = preferred_period

    else:
        period_used = available

    if period_used < minimum_period:
        return None, period_used, False

    ma_series = data["Close"].rolling(
        period_used
    ).mean()

    is_full_history = (
        period_used >= preferred_period
    )

    return ma_series, period_used, is_full_history


def calculate_52_week_high(
    data: pd.DataFrame,
    timeframe: str,
) -> float | None:

    if data.empty:
        return None

    if timeframe == "1d":
        lookback = 252

    elif timeframe == "1wk":
        lookback = 52

    else:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    if len(data) < lookback:
        return None

    return float(
        data["High"].tail(lookback).max()
    )


def calculate_distance_from_resistance(
    price: float,
    resistance: float,
) -> float:

    if resistance <= 0:
        return 0

    return (
        (resistance - price)
        / resistance
    ) * 100
