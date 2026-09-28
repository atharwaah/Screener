from __future__ import annotations

from sqlalchemy.orm import Session

from .config import settings
from .market_data import get_stock_data
from .models import PaperAccount, PaperPosition, Trade


class PaperTradingError(Exception):
    """Raised for invalid trade requests (bad symbol, insufficient cash/shares)."""


def get_or_create_account(db: Session) -> PaperAccount:
    """
    This is a single-user tool, so there is exactly one paper account
    (id=1). Created on first use with the configured starting capital.
    """

    account = (
        db.query(PaperAccount)
        .order_by(PaperAccount.id.asc())
        .first()
    )

    if account is not None:
        return account

    account = PaperAccount(
        initial_cash=settings.INITIAL_PAPER_CAPITAL,
        cash=settings.INITIAL_PAPER_CAPITAL,
    )

    db.add(account)
    db.commit()
    db.refresh(account)

    return account


def get_current_price(
    symbol: str,
    force_refresh: bool = False,
) -> float:
    """
    Returns the latest available daily price.

    Paper trading must not use the scanner's 4-hour cache for fills
    or open-position valuation, otherwise LTP and P&L can remain
    stuck at the entry price for hours.
    """

    data = get_stock_data(
        symbol,
        "1d",
        force_refresh=force_refresh,
    )

    if data.empty:
        raise PaperTradingError(
            f"No market data available for {symbol}"
        )

    return float(data["Close"].iloc[-1])


def _get_position(
    db: Session,
    account_id: int,
    symbol: str,
) -> PaperPosition | None:

    return (
        db.query(PaperPosition)
        .filter(
            PaperPosition.account_id == account_id,
            PaperPosition.symbol == symbol,
        )
        .first()
    )


def buy(db: Session, symbol: str, quantity: int) -> Trade:

    if quantity <= 0:
        raise PaperTradingError("Quantity must be a positive whole number")

    symbol = symbol.strip().upper()
    if not symbol.endswith(".NS"):
        symbol = f"{symbol}.NS"

    account = get_or_create_account(db)
    price = get_current_price(symbol, force_refresh=True)
    cost = price * quantity

    if cost > account.cash:
        raise PaperTradingError(
            f"Insufficient paper cash: need Rs.{cost:.2f}, have Rs.{account.cash:.2f}"
        )

    position = _get_position(db, account.id, symbol)

    if position is None:
        position = PaperPosition(
            account_id=account.id,
            symbol=symbol,
            quantity=quantity,
            average_price=price,
        )
        db.add(position)
    else:
        total_cost = (
            position.quantity * position.average_price
        ) + cost
        position.quantity += quantity
        position.average_price = total_cost / position.quantity

    account.cash -= cost

    trade = Trade(
        account_id=account.id,
        symbol=symbol,
        side="BUY",
        quantity=quantity,
        price=price,
    )
    db.add(trade)

    db.commit()
    db.refresh(trade)

    return trade


def sell(db: Session, symbol: str, quantity: int) -> Trade:

    if quantity <= 0:
        raise PaperTradingError("Quantity must be a positive whole number")

    symbol = symbol.strip().upper()
    if not symbol.endswith(".NS"):
        symbol = f"{symbol}.NS"

    account = get_or_create_account(db)
    position = _get_position(db, account.id, symbol)

    if position is None or position.quantity < quantity:
        held = position.quantity if position else 0
        raise PaperTradingError(
            f"Cannot sell {quantity} {symbol}: only {held} held"
        )

    price = get_current_price(symbol, force_refresh=True)
    proceeds = price * quantity

    position.quantity -= quantity
    account.cash += proceeds

    if position.quantity == 0:
        db.delete(position)

    trade = Trade(
        account_id=account.id,
        symbol=symbol,
        side="SELL",
        quantity=quantity,
        price=price,
    )
    db.add(trade)

    db.commit()
    db.refresh(trade)

    return trade


def get_portfolio(db: Session) -> dict:

    account = get_or_create_account(db)

    positions = (
        db.query(PaperPosition)
        .filter(PaperPosition.account_id == account.id)
        .order_by(PaperPosition.symbol.asc())
        .all()
    )

    position_rows = []
    positions_value = 0.0

    for position in positions:

        try:
            current_price = get_current_price(position.symbol, force_refresh=True)
        except PaperTradingError:
            current_price = None

        market_value = None
        unrealized_pnl = None
        unrealized_pnl_percent = None

        if current_price is not None:
            market_value = current_price * position.quantity
            cost_basis = position.average_price * position.quantity
            unrealized_pnl = market_value - cost_basis
            unrealized_pnl_percent = (
                (unrealized_pnl / cost_basis) * 100
                if cost_basis > 0
                else 0
            )
            positions_value += market_value

        position_rows.append({
            "symbol": position.symbol,
            "quantity": position.quantity,
            "average_price": position.average_price,
            "current_price": current_price,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_percent": unrealized_pnl_percent,
        })

    total_value = account.cash + positions_value
    total_pnl = total_value - account.initial_cash
    total_pnl_percent = (
        (total_pnl / account.initial_cash) * 100
        if account.initial_cash > 0
        else 0
    )

    return {
        "cash": account.cash,
        "initial_cash": account.initial_cash,
        "positions_value": positions_value,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_percent": total_pnl_percent,
        "positions": position_rows,
    }


def get_trades(db: Session, limit: int = 100) -> list[Trade]:

    account = get_or_create_account(db)

    return (
        db.query(Trade)
        .filter(Trade.account_id == account.id)
        .order_by(Trade.timestamp.desc())
        .limit(limit)
        .all()
    )


def reset_account(db: Session) -> PaperAccount:
    """Wipes positions and trade history and resets cash to the starting capital."""

    account = get_or_create_account(db)

    db.query(PaperPosition).filter(
        PaperPosition.account_id == account.id
    ).delete()

    db.query(Trade).filter(
        Trade.account_id == account.id
    ).delete()

    account.cash = account.initial_cash

    db.commit()
    db.refresh(account)

    return account
