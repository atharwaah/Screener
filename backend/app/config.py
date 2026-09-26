from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    CORS_ORIGINS: str = "http://localhost:5173"
    INITIAL_PAPER_CAPITAL: float = 100000

    # How many stocks to fetch/scan concurrently during a full-universe
    # scan (scan-market, scan-nifty500, scan-nifty500-new-highs). Higher
    # = faster scans, but more simultaneous requests hitting Yahoo
    # Finance at once, which raises the chance of rate-limiting/blocks
    # (especially from cloud-host IPs). 16 is a reasonable middle ground;
    # tune down if you start seeing more NO_DATA/ERROR results.
    SCAN_MAX_WORKERS: int = 16

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()