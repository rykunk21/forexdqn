"""
Train DQN agent on forex data.
"""

import json
import os
from datetime import datetime, date
from pathlib import Path

import numpy as np
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
from stable_baselines3.common.monitor import Monitor

from forexdqn.data.market_polygon import ForexData
from forexdqn.training.environment import ForexEnv


def load_data(pair: str, start_date: str, end_date: str):
    """Load and prepare data from Polygon."""
    data = ForexData()
    df = data.get_candles(
        pair=pair,
        from_date=start_date,
        to_date=end_date,
        multiplier=1,
        timespan='minute'
    )
    
    if len(df) == 0:
        raise ValueError(f"No data loaded for {pair}")
    
    print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    return df


def train():
    """Train DQN agent."""
    # Load config
    with open('config.json') as f:
        config = json.load(f)
    
    pair = "EUR_USD"
    
    # Load training data
    print("Loading training data...")
    train_df = load_data(pair, config['data']['train_start'], config['data']['train_end'])
    val_df = load_data(pair, config['data']['val_start'], config['data']['val_end'])
    
    # Create environments
    env = Monitor(ForexEnv(
        df=train_df,
        window_size=config['environment']['window_size'],
        max_position_hold=config['environment']['max_position_hold'],
        spread_pips=config['environment']['spread_pips'],
        initial_balance=config['environment']['initial_balance'],
    ))
    
    val_env = Monitor(ForexEnv(
        df=val_df,
        window_size=config['environment']['window_size'],
        max_position_hold=config['environment']['max_position_hold'],
        spread_pips=config['environment']['spread_pips'],
        initial_balance=config['environment']['initial_balance'],
    ))
    
    # Create output dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"outputs/{pair}_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Training with config: {config['training']}")
    print(f"Output: {output_dir}")
    
    # Create DQN model
    model = DQN(
        "MlpPolicy",
        env,
        learning_rate=config['training']['learning_rate'],
        buffer_size=config['training']['buffer_size'],
        learning_starts=10000,
        batch_size=config['training']['batch_size'],
        gamma=config['training']['gamma'],
        exploration_fraction=config['training']['exploration_fraction'],
        exploration_initial_eps=1.0,
        exploration_final_eps=0.05,
        verbose=1,
        tensorboard_log=str(output_dir / "tensorboard"),
    )
    
    # Callbacks
    checkpoint_callback = CheckpointCallback(
        save_freq=10000,
        save_path=str(output_dir / "checkpoints"),
        name_prefix="dqn"
    )
    
    eval_callback = EvalCallback(
        val_env,
        best_model_save_path=str(output_dir / "best"),
        log_path=str(output_dir / "logs"),
        eval_freq=5000,
        deterministic=True,
    )
    
    # Train
    model.learn(
        total_timesteps=config['training']['total_timesteps'],
        callback=[checkpoint_callback, eval_callback],
        progress_bar=True,
    )
    
    # Save final
    model.save(str(output_dir / "final_model"))
    print(f"Training complete! Model saved to {output_dir}")


if __name__ == "__main__":
    train()
