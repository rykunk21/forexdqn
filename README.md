# Forex DQN

Deep Q-Learning for forex trading. PPO/DQN agents trained on Polygon.io historical data, executed on OANDA.

## Setup

```bash
# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add API keys (create .keys file)
cat > .keys << EOF
POLYGON_API=your_polygon_key
OANDA_DEMO_API=your_oanda_token
OANDA_TEST_ACCOUNT=your_account_id
EOF
```

## Usage

```bash
# Test APIs
python -m forexdqn test

# Download training data
python -m forexdqn fetch --pair EUR_USD

# Train agent
python -m forexdqn train
```

## Architecture

- **Fixed episode length**: Max 240 steps (4 hours) per position
- **Continuous sizing**: Actions in [-1, 1] for position size
- **Reward shaping**: PnL + drawdown penalty + time cost
- **State features**: Price window + position + unrealized PnL

## Config

Edit `config.json`:
- `training`: DQN hyperparameters
- `environment`: position hold limits, spread
- `data`: train/val date ranges
