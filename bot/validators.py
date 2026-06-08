"""Input checks.

Everything the user types passes through here before it reaches the client.
Each function raises :class:`ValidationError` with a message that says what was
wrong, so the user finds out before the order goes anywhere.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}


class ValidationError(ValueError):
    """Raised when user input fails validation."""


def validate_symbol(symbol: str) -> str:
    """Normalise and sanity-check a trading symbol (e.g. ``BTCUSDT``)."""
    if not symbol or not symbol.strip():
        raise ValidationError("Symbol must not be empty.")
    cleaned = symbol.strip().upper()
    if not cleaned.isalnum():
        raise ValidationError(
            f"Symbol '{symbol}' is invalid; expected something like BTCUSDT."
        )
    return cleaned


def validate_side(side: str) -> str:
    """Validate the order side and return the canonical upper-case form."""
    cleaned = (side or "").strip().upper()
    if cleaned not in VALID_SIDES:
        raise ValidationError(
            f"Side '{side}' is invalid; choose one of {sorted(VALID_SIDES)}."
        )
    return cleaned


def validate_order_type(order_type: str) -> str:
    """Validate the order type and return the canonical upper-case form."""
    cleaned = (order_type or "").strip().upper().replace("-", "_")
    if cleaned not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Order type '{order_type}' is invalid; "
            f"choose one of {sorted(VALID_ORDER_TYPES)}."
        )
    return cleaned


def validate_quantity(quantity) -> Decimal:
    """Validate quantity is a positive number."""
    value = _to_decimal(quantity, "quantity")
    if value <= 0:
        raise ValidationError(f"Quantity must be positive, got {quantity}.")
    return value


def validate_price(price, *, field: str = "price") -> Decimal:
    """Validate a price is a positive number."""
    value = _to_decimal(price, field)
    if value <= 0:
        raise ValidationError(f"{field.capitalize()} must be positive, got {price}.")
    return value


def _to_decimal(raw, field: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"{field.capitalize()} '{raw}' is not a valid number.")
