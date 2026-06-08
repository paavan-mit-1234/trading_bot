"""Command-line interface for the Binance Futures Testnet trading bot.

Examples
--------
    # Market buy
    python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

    # Limit sell
    python cli.py --symbol BTCUSDT --side SELL --type LIMIT \
        --quantity 0.001 --price 65000

    # Stop-limit buy (bonus order type)
    python cli.py --symbol BTCUSDT --side BUY --type STOP_LIMIT \
        --quantity 0.001 --price 66000 --stop-price 65900

    # Check connectivity / balance
    python cli.py --check
"""

from __future__ import annotations

import argparse
import os
import sys

from bot.client import (
    BinanceAPIError,
    BinanceFuturesClient,
    BinanceNetworkError,
    TESTNET_BASE_URL,
)
from bot.logging_config import get_logger
from bot.orders import build_order_request, place_order
from bot.validators import ValidationError

logger = get_logger("cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Place Market / Limit / Stop-Limit orders on the "
        "Binance USDT-M Futures Testnet.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--symbol", help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--side", help="BUY or SELL")
    parser.add_argument(
        "--type",
        dest="order_type",
        help="Order type: MARKET, LIMIT or STOP_LIMIT",
    )
    parser.add_argument("--quantity", help="Order quantity (base asset)")
    parser.add_argument("--price", help="Limit price (required for LIMIT / STOP_LIMIT)")
    parser.add_argument(
        "--stop-price",
        dest="stop_price",
        help="Trigger price (required for STOP_LIMIT)",
    )
    parser.add_argument(
        "--tif",
        dest="time_in_force",
        default="GTC",
        help="Time in force for LIMIT / STOP_LIMIT orders",
    )

    parser.add_argument(
        "--api-key",
        default=os.getenv("BINANCE_API_KEY"),
        help="API key (defaults to BINANCE_API_KEY env var)",
    )
    parser.add_argument(
        "--api-secret",
        default=os.getenv("BINANCE_API_SECRET"),
        help="API secret (defaults to BINANCE_API_SECRET env var)",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BINANCE_BASE_URL", TESTNET_BASE_URL),
        help="API base URL",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only test connectivity and print account balance, then exit.",
    )
    return parser


def _make_client(args: argparse.Namespace) -> BinanceFuturesClient:
    if not args.api_key or not args.api_secret:
        raise ValidationError(
            "Missing API credentials. Set BINANCE_API_KEY and BINANCE_API_SECRET "
            "environment variables, or pass --api-key / --api-secret."
        )
    return BinanceFuturesClient(
        api_key=args.api_key,
        api_secret=args.api_secret,
        base_url=args.base_url,
    )


def _run_check(client: BinanceFuturesClient) -> int:
    client.ping()
    print("Connectivity OK (ping succeeded).")
    balances = client.get_account_balance()
    usdt = next((b for b in balances if b.get("asset") == "USDT"), None)
    if usdt:
        print(f"USDT balance: {usdt.get('balance')} (available: {usdt.get('availableBalance')})")
    else:
        print("No USDT balance found on this account.")
    return 0


def _print_result(result: dict) -> None:
    print("\nOrder response details:")
    print(f"  orderId    : {result.get('orderId')}")
    print(f"  symbol     : {result.get('symbol')}")
    print(f"  status     : {result.get('status')}")
    print(f"  side       : {result.get('side')}")
    print(f"  type       : {result.get('type')}")
    print(f"  origQty    : {result.get('origQty')}")
    print(f"  executedQty: {result.get('executedQty')}")
    if result.get("avgPrice") is not None:
        print(f"  avgPrice   : {result.get('avgPrice')}")
    if result.get("price") not in (None, "0", "0.0"):
        print(f"  price      : {result.get('price')}")
    if result.get("stopPrice") not in (None, "0", "0.0"):
        print(f"  stopPrice  : {result.get('stopPrice')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        client = _make_client(args)

        if args.check:
            return _run_check(client)

        # An order needs the core four fields.
        missing = [
            name
            for name, val in (
                ("--symbol", args.symbol),
                ("--side", args.side),
                ("--type", args.order_type),
                ("--quantity", args.quantity),
            )
            if not val
        ]
        if missing:
            raise ValidationError(
                "Missing required argument(s): "
                + ", ".join(missing)
                + ". (Use --check to only test connectivity.)"
            )

        request = build_order_request(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
            time_in_force=args.time_in_force,
        )

        print(request.summary())
        logger.info("Submitting order: %s", request.to_params())

        result = place_order(client, request)
        _print_result(result)
        print("\n[SUCCESS] Order placed successfully.")
        return 0

    except ValidationError as exc:
        logger.error("Validation failed: %s", exc)
        print(f"\n[FAILURE] Invalid input: {exc}", file=sys.stderr)
        return 2
    except BinanceAPIError as exc:
        logger.error("Binance API rejected the order: %s", exc)
        print(f"\n[FAILURE] Binance API error (code={exc.code}): {exc}", file=sys.stderr)
        return 1
    except BinanceNetworkError as exc:
        logger.error("Network failure: %s", exc)
        print(f"\n[FAILURE] Network error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - last-resort safety net
        logger.exception("Unexpected error")
        print(f"\n[FAILURE] Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
