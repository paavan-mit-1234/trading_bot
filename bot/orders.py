"""Order building and placement.

This sits between the CLI and the client. It validates the input, builds the
right set of parameters for the order type, hands it to the client, and pulls
the response apart into the fields the CLI prints.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .client import BinanceFuturesClient
from .logging_config import get_logger
from . import validators

logger = get_logger("orders")


@dataclass
class OrderRequest:
    """A validated, ready-to-send order request."""

    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str = "GTC"

    def summary(self) -> str:
        lines = [
            "Order request summary:",
            f"  symbol     : {self.symbol}",
            f"  side       : {self.side}",
            f"  type       : {self.order_type}",
            f"  quantity   : {self.quantity}",
        ]
        if self.price is not None:
            lines.append(f"  price      : {self.price}")
        if self.stop_price is not None:
            lines.append(f"  stopPrice  : {self.stop_price}")
        if self.order_type in {"LIMIT", "STOP_LIMIT"}:
            lines.append(f"  timeInForce: {self.time_in_force}")
        return "\n".join(lines)

    def to_params(self) -> dict[str, Any]:
        """Translate this request into Binance API parameters."""
        params: dict[str, Any] = {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": _fmt(self.quantity),
        }

        if self.order_type == "MARKET":
            params["type"] = "MARKET"
        elif self.order_type == "LIMIT":
            params["type"] = "LIMIT"
            params["price"] = _fmt(self.price)
            params["timeInForce"] = self.time_in_force
        elif self.order_type == "STOP_LIMIT":
            # Binance treats a stop-limit as type=STOP, carrying both the
            # trigger (stopPrice) and the limit price it rests at once hit.
            params["type"] = "STOP"
            params["price"] = _fmt(self.price)
            params["stopPrice"] = _fmt(self.stop_price)
            params["timeInForce"] = self.time_in_force
        else:  # pragma: no cover - guarded by validation
            raise validators.ValidationError(f"Unsupported order type {self.order_type}")

        return params


def build_order_request(
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity,
    price=None,
    stop_price=None,
    time_in_force: str = "GTC",
) -> OrderRequest:
    """Validate raw input and return an :class:`OrderRequest`.

    Raises :class:`validators.ValidationError` on bad input.
    """
    symbol = validators.validate_symbol(symbol)
    side = validators.validate_side(side)
    order_type = validators.validate_order_type(order_type)
    qty = validators.validate_quantity(quantity)

    price_dec: Decimal | None = None
    stop_dec: Decimal | None = None

    if order_type in {"LIMIT", "STOP_LIMIT"}:
        if price is None:
            raise validators.ValidationError(
                f"{order_type} orders require a --price."
            )
        price_dec = validators.validate_price(price)

    if order_type == "STOP_LIMIT":
        if stop_price is None:
            raise validators.ValidationError(
                "STOP_LIMIT orders require a --stop-price (the trigger price)."
            )
        stop_dec = validators.validate_price(stop_price, field="stop price")

    return OrderRequest(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=qty,
        price=price_dec,
        stop_price=stop_dec,
        time_in_force=time_in_force,
    )


def place_order(client: BinanceFuturesClient, request: OrderRequest) -> dict[str, Any]:
    """Send a validated order request and return the normalised response.

    Note: a market order comes back as an ack (status NEW, no fill price)
    because the match happens a moment later on the engine. The fill shows up
    in the account balance straight away. Reading the order back to show the
    fill price is not reliable on the demo environment, where the order-query
    endpoint returns -2013 for orders that do exist, so we report the ack.
    """
    params = request.to_params()
    logger.info("Placing %s %s order for %s", request.side, request.order_type, request.symbol)
    raw = client.new_order(**params)
    return _normalise_response(raw)


def _normalise_response(raw: dict[str, Any]) -> dict[str, Any]:
    """Pull out the fields we care about. Missing keys come back as None."""
    return {
        "orderId": raw.get("orderId"),
        "symbol": raw.get("symbol"),
        "status": raw.get("status"),
        "side": raw.get("side"),
        "type": raw.get("type"),
        "origQty": raw.get("origQty"),
        "executedQty": raw.get("executedQty"),
        "avgPrice": raw.get("avgPrice"),
        "price": raw.get("price"),
        "stopPrice": raw.get("stopPrice"),
        "_raw": raw,
    }


def _fmt(value: Decimal | None) -> str:
    """Format a Decimal without scientific notation or trailing noise."""
    if value is None:
        return ""
    return format(value.normalize(), "f")
