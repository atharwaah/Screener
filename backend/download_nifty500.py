import requests
from pathlib import Path


URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"

OUTPUT = (
    Path(__file__).resolve().parent
    / "data"
    / "nifty500.csv"
)


headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/csv,application/csv,"
        "application/octet-stream;q=0.9,*/*;q=0.8"
    ),
    "Referer": "https://www.niftyindices.com/",
}


print("Downloading NIFTY 500 list...")

response = requests.get(
    URL,
    headers=headers,
    timeout=30,
)

response.raise_for_status()

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT.write_bytes(
    response.content
)

print()
print("Download successful.")
print(f"Saved to: {OUTPUT}")
print(f"File size: {OUTPUT.stat().st_size} bytes")