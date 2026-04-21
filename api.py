from flask import Flask, jsonify
from walletapp.services.market_service import MarketService

app    = Flask(__name__)
market = MarketService()

@app.route("/price/<symbol>/<kind>")
def get_price(symbol, kind):
    price = market.get_price(symbol, kind)
    return jsonify({"symbol": symbol, "price": price})

if __name__ == "__main__":
    app.run()
