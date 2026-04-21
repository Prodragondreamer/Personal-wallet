import os
from flask import Flask, jsonify
from pycoingecko import CoinGeckoAPI
import yfinance as yf

app = Flask(__name__)
cg  = CoinGeckoAPI()

COIN_MAP = {
    "BTC":  "bitcoin",
    "ETH":  "ethereum",
    "USDC": "usd-coin",
    "SOL":  "solana",
    "BNB":  "binancecoin",
    "ADA":  "cardano",
    "DOGE": "dogecoin",
}

FALLBACK = {
    "ETH":  3000.00,
    "BTC":  65000.00,
    "USDC": 1.00,
    "SOL":  150.00,
    "AAPL": 190.00,
    "TSLA": 250.00,
    "MSFT": 420.00,
}

@app.route("/price/<symbol>/<kind>")
def get_price(symbol, kind):
    symbol = symbol.upper()
    try:
        if kind == "Cash" or symbol in ("USDC", "USDT", "DAI"):
            price = 1.0
        elif kind == "Crypto" or symbol in COIN_MAP:
            coin_id = COIN_MAP.get(symbol, symbol.lower())
            data    = cg.get_price(ids=coin_id, vs_currencies="usd")
            price   = float(data.get(coin_id, {}).get("usd", 0.0))
        else:
            data  = yf.Ticker(symbol).history(period="1d")
            price = float(data["Close"].iloc[-1]) if not data.empty else 0.0

        if price <= 0:
            price = FALLBACK.get(symbol, 0.0)

    except Exception:
        price = FALLBACK.get(symbol, 0.0)

    return jsonify({"symbol": symbol, "price": price})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
