
import json
import oandapyV20
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
from oandapyV20.contrib.requests import MarketOrderRequest, LimitOrderRequest
from oandapyV20.contrib.requests import TakeProfitDetails, StopLossDetails
from oandapyV20.exceptions import V20Error

from dotenv import load_dotenv
import os
from pathlib import Path

# Option A: Load from current directory
load_dotenv(dotenv_path='.keys')

# --- Config ---
ACCESS_TOKEN = os.getenv('OANDA_DEMO_API')
ACCOUNT_ID   = os.getenv('OANDA_TEST_ACCOUNT')
ENVIRONMENT  = "practice"              # "practice" or "live"

# --- Client ---
api = oandapyV20.API(access_token=ACCESS_TOKEN, environment=ENVIRONMENT)

class Oanda:

    def __init__(self):
        pass

    def get_price(self, instrument: str) -> dict:
        """Fetch current bid/ask for an instrument."""
        r = pricing.PricingInfo(ACCOUNT_ID, params={"instruments": instrument})
        rv = api.request(r)
        price = rv["prices"][0]
        return {
            "bid": float(price["bids"][0]["price"]),
            "ask": float(price["asks"][0]["price"]),
        }


    def place_market_order(self, instrument: str, units: int, stop_loss: float, take_profit: float):
        """
        Place a market order with SL/TP.
        units > 0 = buy (long), units < 0 = sell (short)
        """
        order = MarketOrderRequest(
            instrument=instrument,
            units=units,
            stopLossOnFill=StopLossDetails(price=stop_loss).data,
            takeProfitOnFill=TakeProfitDetails(price=take_profit).data,
        )
        r = orders.OrderCreate(ACCOUNT_ID, data=order.data)
        try:
            rv = api.request(r)
            print("Order placed:")
            print(json.dumps(rv, indent=2))
            return rv
        except V20Error as e:
            print(f"Order failed: {e.code} - {e.msg}")
            return None


    def place_limit_order(self, instrument: str, units: int, price: float):
        """Place a limit order at a specific price."""
        order = LimitOrderRequest(
            instrument=instrument,
            units=units,
            price=price,
        )
        r = orders.OrderCreate(ACCOUNT_ID, data=order.data)
        try:
            rv = api.request(r)
            print("Limit order placed:")
            print(json.dumps(rv, indent=2))
            return rv
        except V20Error as e:
            print(f"Limit order failed: {e.code} - {e.msg}")
            return None


if __name__ == "__main__":
    client = Oanda()
    instrument = "EUR_USD"

    # Check current price
    prices = client.get_price(instrument)
    print(f"EUR/USD  bid={prices['bid']}  ask={prices['ask']}")

    # Example: buy 10,000 units with SL 20 pips below ask, TP 40 pips above
    ask = prices["ask"]
    pip = 0.0001
    client.place_market_order(
        instrument=instrument,
        units=100,
        stop_loss=round(ask - 20 * pip, 5),
        take_profit=round(ask + 40 * pip, 5),
    )
