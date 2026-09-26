from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TradeRequest(BaseModel):
    symbol: str
    quantity: int


class PositionOut(BaseModel):
    symbol: str
    quantity: int
    average_price: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_percent: Optional[float] = None


class TradeOut(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: datetime

    model_config = {"from_attributes": True}


class PortfolioOut(BaseModel):
    cash: float
    initial_cash: float
    positions_value: float
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    positions: list[PositionOut]


class ScanResult(BaseModel):

    symbol: str

    status: str

    current_price: Optional[float] = None

    resistance_52w: Optional[float] = None

    distance_percent: Optional[float] = None

    ma_200: Optional[float] = None

    above_ma_200: Optional[bool] = None

    near_resistance: Optional[bool] = None

    fresh_breakout: Optional[bool] = None

    available_candles: int = 0

    timeframe: Optional[str] = None