# Trading Bot for Binance Futures Testnet (USDT-M)

A small Python command line tool I wrote to place orders on the Binance
Futures Testnet. It supports Market, Limit and Stop-Limit orders, validates
what you type before sending anything, and writes a log file of every request
and response so you can see exactly what happened.

It talks to the testnet directly over signed REST calls. I went with plain
`requests` instead of a wrapper library so the request signing and logging are
all visible in one place and easy to follow.

## What it does

- Places MARKET, LIMIT and STOP_LIMIT orders
- Handles both BUY and SELL
- Checks your input first (symbol, side, type, quantity, price) and tells you
  what is wrong if something does not look right
- Keeps the API/client code and the CLI code in separate layers
- Logs requests, responses and errors to `logs/trading_bot.log`
- Catches the usual failure cases: bad input, API rejections, network problems

## Layout

```
trading_bot/
  bot/
    __init__.py
    client.py          # signed REST client (signing, requests, logging, errors)
    orders.py          # builds and sends the order, tidies up the response
    validators.py      # input checks
    logging_config.py  # log setup (file + console)
  cli.py               # command line entry point
  requirements.txt
  .env.example
  README.md
  logs/                # created on first run
```

## Setup

1. Get a testnet account. Binance has folded the old Futures Testnet into its
   "demo trading" product, so go to https://demo.binance.com and open a demo
   trading account (it is free and uses fake money).
2. Create an API key and secret under the demo account's API management page
   (https://demo.binance.com/en/my/settings/api-management). Copy the secret
   when it is shown, you only get to see it once.
3. Fund the demo futures wallet. On the demo USDⓈ-M Futures wallet page there
   is a "Reset Asset" button that drops in a balance of test USDT/USDC/BTC.
   Click it if your futures balance is 0, otherwise orders fail with
   "Margin is insufficient".
4. Go into the project folder:
   ```
   cd trading_bot
   ```
5. Optionally make a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # macOS / Linux
   ```
6. Install the one dependency:
   ```
   pip install -r requirements.txt
   ```
7. Give it your credentials. Either set environment variables:
   ```
   # Windows PowerShell
   $env:BINANCE_API_KEY="your_key"
   $env:BINANCE_API_SECRET="your_secret"

   # macOS / Linux
   export BINANCE_API_KEY="your_key"
   export BINANCE_API_SECRET="your_secret"
   ```
   or copy `.env.example` to `.env` and fill it in, or just pass
   `--api-key` and `--api-secret` on the command line.

## Running it

Check that the keys work and see your balance first:

```
python cli.py --check
```

Market order:

```
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

Limit order:

```
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 65000
```

Stop-Limit order. It waits until the price hits the trigger (`--stop-price`)
and then places a limit order at `--price`:

```
python cli.py --symbol BTCUSDT --side BUY --type STOP_LIMIT --quantity 0.001 --price 66000 --stop-price 65900
```

Run `python cli.py --help` to see everything.

The arguments:

| Argument       | Needed for          | What it is                          |
|----------------|---------------------|-------------------------------------|
| `--symbol`     | every order         | trading pair, e.g. BTCUSDT          |
| `--side`       | every order         | BUY or SELL                         |
| `--type`       | every order         | MARKET, LIMIT or STOP_LIMIT         |
| `--quantity`   | every order         | amount in the base asset            |
| `--price`      | LIMIT, STOP_LIMIT   | limit price                         |
| `--stop-price` | STOP_LIMIT          | trigger price                       |
| `--tif`        | optional            | time in force, default GTC          |
| `--api-key`    | optional            | overrides BINANCE_API_KEY           |
| `--api-secret` | optional            | overrides BINANCE_API_SECRET        |
| `--base-url`   | optional            | defaults to the testnet URL         |
| `--check`      |                     | test the connection and show balance|

## What the output looks like

```
Order request summary:
  symbol     : BTCUSDT
  side       : BUY
  type       : MARKET
  quantity   : 0.001

Order response details:
  orderId    : 1234567890
  symbol     : BTCUSDT
  status     : FILLED
  side       : BUY
  type       : MARKET
  origQty    : 0.001
  executedQty: 0.001
  avgPrice   : 64950.10

[SUCCESS] Order placed successfully.
```

## Logging

Everything goes to `logs/trading_bot.log`, which rotates at 1 MB and keeps the
last 5 files. INFO lines show the high level steps and also print to the
console. DEBUG lines hold the full request params and response body and stay in
the file. Errors are written with enough detail to figure out what broke. The
API secret and the request signature are kept out of the logs on purpose.

## Exit codes

| Code | Meaning                                |
|------|----------------------------------------|
| 0    | order went through                     |
| 1    | API error, network error or a crash    |
| 2    | input did not pass validation          |

## Assumptions

- This is only for the USDT-M Futures Testnet. The keys come from the demo
  trading account (https://demo.binance.com), but the REST host is still
  https://testnet.binancefuture.com, which is what the bot defaults to. You can
  point it elsewhere with `--base-url` if Binance moves it again.
- The bot syncs to Binance server time on the first signed call and offsets its
  timestamps from that, so a local clock that is off by a second or two does not
  get requests rejected with error -1021.
- I assumed the account is in one-way position mode, which is the default, so
  orders do not send a `positionSide`. If you switched to hedge mode you would
  need to add that.
- The bot checks that quantity and price are positive and well formed. It does
  not pull `exchangeInfo` to round values to each symbol's tick and step size,
  so pick quantities and prices that already fit the symbol's rules.
- A stop-limit is sent as Binance order `type=STOP`, which carries both the
  trigger (`stopPrice`) and the limit `price` it rests at once triggered.
