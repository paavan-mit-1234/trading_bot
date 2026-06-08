"""Binance Futures Testnet (USDT-M) REST client.

Talks to the signed REST API with plain ``requests``. Doing the signing by
hand keeps all of it in one file and easy to read. Every request and response
is logged, with the secret and signature kept out.

API docs: https://binance-docs.github.io/apidocs/futures/en/
Testnet base URL: https://testnet.binancefuture.com
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from .logging_config import get_logger

logger = get_logger("client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW_MS = 5000


class BinanceAPIError(RuntimeError):
    """Raised when Binance returns an error response (non-2xx / error code)."""

    def __init__(self, message: str, *, code: int | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


class BinanceNetworkError(RuntimeError):
    """Raised when the request never completed (timeout, DNS, connection)."""


class BinanceFuturesClient:
    """Minimal signed client for the Binance USDT-M Futures Testnet."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = 10,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret are required.")
        self.api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": api_key})

        # Difference between Binance's clock and ours, in ms. Worked out once
        # on the first signed call so a slightly off local clock doesn't get
        # our requests rejected with -1021.
        self._time_offset_ms: int | None = None

    # ----------------------------------------------------------------- public

    def ping(self) -> bool:
        """Connectivity check against the public ping endpoint."""
        self._request("GET", "/fapi/v1/ping", signed=False)
        return True

    def get_server_time(self) -> int:
        """Return Binance server time in milliseconds."""
        data = self._request("GET", "/fapi/v1/time", signed=False)
        return int(data["serverTime"])

    def get_account_balance(self) -> list[dict[str, Any]]:
        """Return USDT-M futures account balances (signed)."""
        return self._request("GET", "/fapi/v2/balance", signed=True)

    def new_order(self, **params: Any) -> dict[str, Any]:
        """Place an order via ``POST /fapi/v1/order`` (signed).

        Whatever is in ``params`` goes straight to the API (symbol, side, type,
        quantity, price, timeInForce, stopPrice and so on). The bot.orders
        module is what decides those values, so this stays generic.
        """
        return self._request("POST", "/fapi/v1/order", signed=True, params=params)

    # ---------------------------------------------------------------- internal

    def _request(
        self,
        method: str,
        path: str,
        *,
        signed: bool,
        params: dict[str, Any] | None = None,
    ) -> Any:
        params = dict(params or {})
        url = f"{self.base_url}{path}"

        if signed:
            params["timestamp"] = self._timestamp()
            params["recvWindow"] = RECV_WINDOW_MS
            params["signature"] = self._sign(params)

        logger.info("API request: %s %s", method, path)
        logger.debug("Request params: %s", _redact(params))

        try:
            response = self._session.request(
                method, url, params=params, timeout=self.timeout
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Network error calling %s %s: %s", method, path, exc)
            raise BinanceNetworkError(f"Network error calling {path}: {exc}") from exc

        return self._handle_response(response, method, path)

    def _handle_response(self, response: requests.Response, method: str, path: str) -> Any:
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}

        logger.debug("Response [%s]: %s", response.status_code, payload)

        if not response.ok:
            code = payload.get("code") if isinstance(payload, dict) else None
            msg = payload.get("msg", response.text) if isinstance(payload, dict) else response.text
            logger.error(
                "API error on %s %s -> HTTP %s, code=%s, msg=%s",
                method, path, response.status_code, code, msg,
            )
            raise BinanceAPIError(msg, code=code, status=response.status_code)

        logger.info("API success: %s %s -> HTTP %s", method, path, response.status_code)
        return payload

    def _timestamp(self) -> int:
        """Local time corrected by the offset to Binance's server clock.

        The offset is fetched once and reused. If the time endpoint can't be
        reached we fall back to the raw local clock rather than failing.
        """
        if self._time_offset_ms is None:
            try:
                server_ms = self.get_server_time()
                self._time_offset_ms = server_ms - int(time.time() * 1000)
                logger.info("Clock offset to Binance: %d ms", self._time_offset_ms)
            except Exception as exc:  # noqa: BLE001 - offset is best-effort
                logger.warning("Could not sync server time, using local clock: %s", exc)
                self._time_offset_ms = 0
        return int(time.time() * 1000) + self._time_offset_ms

    def _sign(self, params: dict[str, Any]) -> str:
        query = urlencode(params)
        return hmac.new(self._api_secret, query.encode("utf-8"), hashlib.sha256).hexdigest()


def _redact(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of params with the signature redacted for safe logging."""
    safe = dict(params)
    if "signature" in safe:
        safe["signature"] = "***REDACTED***"
    return safe
