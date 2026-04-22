#!/usr/bin/env python3
"""
Forex DQN Trading System

Commands:
    python -m forexdqn fetch        # Download training data
    python -m forexdqn train        # Train DQN agent
    python -m forexdqn test         # Test APIs
"""

import argparse
import sys
from pathlib import Path

# Ensure we can import from forexdqn
sys.path.insert(0, str(Path(__file__).parent))


def test_command():
    """Test API connections."""
    print("Testing Polygon API...")
    try:
        from forexdqn.data.market_polygon import ForexData
        import datetime
        
        data = ForexData()
        end = datetime.date.today()
        start = end - datetime.timedelta(days=2)
        df = data.get_candles('EUR_USD', start, end, multiplier=1, timespan='hour')
        print(f"  ✓ Polygon: {len(df)} bars fetched")
    except Exception as e:
        print(f"  ✗ Polygon failed: {e}")
    
    print("\nTesting OANDA API...")
    try:
        from forexdqn.api.oanda import Oanda
        client = Oanda()
        prices = client.get_price('EUR_USD')
        print(f"  ✓ OANDA: bid={prices['bid']:.5f} ask={prices['ask']:.5f}")
    except Exception as e:
        print(f"  ✗ OANDA failed: {e}")
        print("    (May need to regenerate token at developer.oanda.com)")


def fetch_command(pair: str = "EUR_USD"):
    """Fetch training data."""
    from forexdqn.data.market_polygon import ForexData
    import datetime
    
    print(f"Fetching {pair} data...")
    data = ForexData()
    
    end = datetime.date.today()
    start = end - datetime.timedelta(days=180)
    
    df = data.get_candles(pair, start, end, multiplier=1, timespan='minute')
    
    output_file = Path(f'data/{pair}_1min.csv')
    output_file.parent.mkdir(exist_ok=True)
    df.to_csv(output_file)
    
    print(f"Saved {len(df)} bars to {output_file}")


def train_command():
    """Train DQN agent."""
    from forexdqn.training.train import train
    train()


def main():
    parser = argparse.ArgumentParser(description='Forex DQN Trading System')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # test
    test_parser = subparsers.add_parser('test', help='Test API connections')
    
    # fetch
    fetch_parser = subparsers.add_parser('fetch', help='Download training data')
    fetch_parser.add_argument('--pair', default='EUR_USD', help='Currency pair')
    
    # train
    train_parser = subparsers.add_parser('train', help='Train DQN agent')
    
    args = parser.parse_args()
    
    if args.command == 'test':
        test_command()
    elif args.command == 'fetch':
        fetch_command(args.pair)
    elif args.command == 'train':
        train_command()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
