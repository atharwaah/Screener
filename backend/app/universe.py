from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

NIFTY_500_FILE = DATA_DIR / "nifty500.csv"


NIFTY_TEST_UNIVERSE = [
    "TCS.NS",
    "INFY.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "ITC.NS",
    "LT.NS",
    "AXISBANK.NS",
    "M&M.NS",
    "SUNPHARMA.NS",
    "MARUTI.NS",
    "TITAN.NS",
    "TRENT.NS",
]


def get_nifty_500_symbols() -> list[str]:

    if not NIFTY_500_FILE.exists():

        raise FileNotFoundError(
            f"NIFTY 500 file not found: {NIFTY_500_FILE}"
        )

    df = pd.read_csv(
        NIFTY_500_FILE
    )

    if "Symbol" not in df.columns:

        raise ValueError(
            "nifty500.csv must contain a 'Symbol' column."
        )

    symbols = []

    for symbol in df["Symbol"].dropna():

        symbol = str(symbol).strip()

        if not symbol:
            continue

        if not symbol.endswith(".NS"):
            symbol = f"{symbol}.NS"

        symbols.append(symbol)

    return sorted(set(symbols))