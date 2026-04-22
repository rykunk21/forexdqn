"""
Forex trading environment for RL.
Fixed episode length, continuous sizing, drawdown penalties.
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict


class ForexEnv(gym.Env):
    """
    Forex trading environment with:
    - Fixed max position hold (no infinite holding)
    - Continuous action sizing (-1 to +1)
    - Position state features
    - Drawdown penalty in reward
    """
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(
        self,
        df: pd.DataFrame,
        window_size: int = 60,
        max_position_hold: int = 240,  # 4 hours for 1min data
        spread_pips: float = 1.2,
        initial_balance: float = 10000.0,
    ):
        super().__init__()
        
        self.df = df.reset_index(drop=True)
        self.window_size = window_size
        self.max_position_hold = max_position_hold
        self.spread_pips = spread_pips
        self.initial_balance = initial_balance
        
        # Action space: continuous position size [-1, 1]
        # -1 = max short, 0 = flat, 1 = max long
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(1,), dtype=np.float32
        )
        
        # State space
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(window_size * 5 + 6,),  # price window + position features
            dtype=np.float32
        )
        
        # Position tracking
        self.position = 0.0  # -1 to 1
        self.position_steps = 0
        self.entry_price = 0.0
        self.max_position_size = 10000  # units
        
    def _get_observation(self) -> np.ndarray:
        """Current state: price window + position features."""
        # Get price window
        end_idx = self.current_step + 1
        start_idx = max(0, end_idx - self.window_size)
        
        window_df = self.df.iloc[start_idx:end_idx]
        
        # Pad if needed
        if len(window_df) < self.window_size:
            padding = self.window_size - len(window_df)
            pad = np.zeros((padding, 5))
            prices = np.vstack([pad, window_df[['open', 'high', 'low', 'close', 'volume']].values])
        else:
            prices = window_df[['open', 'high', 'low', 'close', 'volume']].values
        
        # Normalize prices
        current_price = self.df.iloc[self.current_step]['close']
        prices_norm = prices / current_price - 1.0  # relative to current
        
        # Position features
        position_features = np.array([
            self.position,  # current position size
            self.position_steps / self.max_position_hold,  # time held (normalized)
            self.entry_price / current_price - 1.0 if self.position != 0 else 0,  # entry distance
            self._unrealized_pnl(),  # current paper PnL
            self._max_drawdown(),  # worst drawdown since entry
            self.current_step / len(self.df),  # time in episode
        ], dtype=np.float32)
        
        obs = np.concatenate([prices_norm.flatten(), position_features])
        return obs.astype(np.float32)
    
    def _unrealized_pnl(self) -> float:
        """Current unrealized PnL."""
        if self.position == 0:
            return 0.0
        current_price = self.df.iloc[self.current_step]['close']
        if self.position > 0:  # long
            return (current_price - self.entry_price) * self.position * self.max_position_size
        else:  # short
            return (self.entry_price - current_price) * abs(self.position) * self.max_position_size
    
    def _max_drawdown(self) -> float:
        """Max drawdown since position entry."""
        if self.position == 0:
            return 0.0
        
        # Simple approximation using current unrealized PnL vs best seen
        unrealized = self._unrealized_pnl()
        # Assume best was at some point (simplified)
        return min(0.0, unrealized)  # only negative values
    
    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None):
        """Reset environment to start of episode."""
        super().reset(seed=seed)
        
        self.current_step = self.window_size
        self.position = 0.0
        self.position_steps = 0
        self.entry_price = 0.0
        self.balance = self.initial_balance
        
        obs = self._get_observation()
        info = {}
        
        return obs, info
    
    def step(self, action: np.ndarray):
        """
        Execute one timestep.
        Action: target position size [-1, 1]
        """
        target_position = np.clip(action[0], -1.0, 1.0)
        
        # Get current price
        current_price = self.df.iloc[self.current_step]['close']
        spread = self.spread_pips * 0.0001  # pips to price
        
        # Calculate reward
        reward = 0.0
        
        # If changing position
        if abs(target_position - self.position) > 0.01:
            # Close old position
            if self.position != 0:
                # PnL realization
                if self.position > 0:  # close long
                    exit_price = current_price - spread
                    pnl = (exit_price - self.entry_price) * self.position * self.max_position_size
                else:  # close short
                    exit_price = current_price + spread
                    pnl = (self.entry_price - exit_price) * abs(self.position) * self.max_position_size
                
                reward += pnl
                self.balance += pnl
            
            # Open new position
            if target_position != 0:
                self.entry_price = current_price + (spread if target_position > 0 else -spread)
                self.position = target_position
                self.position_steps = 0
            else:
                self.position = 0.0
                self.position_steps = 0
        
        # Time penalty (small cost per step to encourage decisions)
        reward -= 0.01
        
        # Drawdown penalty
        drawdown = self._max_drawdown()
        if drawdown < -100:  # more than $100 loss
            reward -= 1.0  # heavy penalty
        
        # Profit taking bonus
        unrealized = self._unrealized_pnl()
        if unrealized > 200:  # $200 profit
            reward += 0.5  # encourage closing
        
        # Increment
        self.current_step += 1
        self.position_steps += 1
        
        # Check termination
        terminated = False
        truncated = False
        
        # Episode ends at end of data
        if self.current_step >= len(self.df) - 1:
            terminated = True
        # Forced close if position held too long
        elif self.position_steps >= self.max_position_hold and self.position != 0:
            # Close position
            if self.position > 0:
                exit_price = current_price - spread
                pnl = (exit_price - self.entry_price) * self.position * self.max_position_size
            else:
                exit_price = current_price + spread
                pnl = (self.entry_price - exit_price) * abs(self.position) * self.max_position_size
            
            reward += pnl
            self.balance += pnl
            self.position = 0.0
            truncated = True  # forced exit
        
        obs = self._get_observation()
        info = {
            'balance': self.balance,
            'position': self.position,
            'unrealized_pnl': self._unrealized_pnl(),
        }
        
        return obs, reward, terminated, truncated, info
