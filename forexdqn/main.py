
from api.oanda import Oanda

def main():
    client = Oanda()
    instrument = "EUR_USD"

    # Check current price
    prices = client.get_price(instrument)
    print(f"EUR/USD  bid={prices['bid']}  ask={prices['ask']}")

    # Example: buy 100 units with SL 20 pips below ask, TP 40 pips above
    ask = prices["ask"]
    pip = 0.0001
    client.place_market_order(
        instrument=instrument,
        units=100,
        stop_loss=round(ask - 20 * pip, 5),
        take_profit=round(ask + 40 * pip, 5),
    )

if __name__ == "__main__":
    main()