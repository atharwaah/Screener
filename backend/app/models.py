from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from .database import Base


class PriceCache(Base):
    """
    DB-backed replacement for the old .pkl-file cache.

    Storing this in the database (instead of local disk) means it
    survives a redeploy/restart on hosts with an ephemeral
    filesystem (e.g. Render's free web services) - the price data
    isn't lost every time the service spins down or redeploys.
    """

    __tablename__ = "price_cache"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            name="uq_price_cache_symbol_timeframe",
        ),
    )

    id = Column(Integer, primary_key=True)

    symbol = Column(String(30), nullable=False, index=True)

    timeframe = Column(String(10), nullable=False)

    # The OHLCV DataFrame, serialized via df.to_json(orient="table").
    data = Column(Text, nullable=False)

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True)
    initial_cash = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True)

    account_id = Column(
        Integer,
        ForeignKey("paper_accounts.id"),
        nullable=False,
    )

    symbol = Column(String(30), nullable=False)

    quantity = Column(Integer, nullable=False)

    average_price = Column(Float, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)

    account_id = Column(
        Integer,
        ForeignKey("paper_accounts.id"),
        nullable=False,
    )

    symbol = Column(String(30), nullable=False)

    side = Column(String(10), nullable=False)

    quantity = Column(Integer, nullable=False)

    price = Column(Float, nullable=False)

    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )