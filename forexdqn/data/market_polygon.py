# pip install polygon-api-client pandas

import os
import pandas as pd
from datetime import datetime, date
from typing import Optional, Union
from polygon import RESTClient

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from dotenv import load_dotenv
import os
from pathlib import Path

# Option A: Load from current directory
load_dotenv(dotenv_path='.keys')

# Polygon forex tickers are prefixed with C:
# OANDA format "EUR_USD" -> Polygon format "C:EURUSD"
def _to_polygon_ticker(pair: str) -> str:
    return "C:" + pair.replace("_", "").replace("-", "")


class ForexData:
    """
    Pulls historical OHLCV candles and tick/quote data from Polygon.io.

    Timespan options: 'minute', 'hour', 'day', 'week', 'month', 'quarter', 'year'
    Multiplier:       integer multiplier on timespan (e.g. multiplier=5, timespan='minute' = 5m candles)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ["POLYGON_API"]
        self.client = RESTClient(self.api_key)

    # ------------------------------------------------------------------
    # OHLCV Candles
    # ------------------------------------------------------------------

    def get_candles(
        self,
        pair: str,
        from_date: Union[str, date, datetime],
        to_date: Union[str, date, datetime],
        multiplier: int = 1,
        timespan: str = "hour",   # 'minute' | 'hour' | 'day' | 'week'
        sort: str = "asc",
    ) -> pd.DataFrame:
        """
        Returns OHLCV candles as a DataFrame indexed by datetime.

        Example:
            df = data.get_candles("EUR_USD", "2024-01-01", "2024-03-01",
                                   multiplier=4, timespan="hour")
        """
        ticker = _to_polygon_ticker(pair)

        # Use get_aggs instead of get_aggregate_bars (newer API)
        aggs = self.client.get_aggs(
            ticker=ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_=from_date,
            to=to_date,
            adjusted=True,
            sort=sort,
            limit=50000,
        )

        if not aggs:
            return pd.DataFrame()

        # Convert Agg objects to dicts
        bars = []
        for agg in aggs:
            bars.append({
                'o': agg.open,
                'h': agg.high,
                'l': agg.low,
                'c': agg.close,
                'v': agg.volume,
                'vw': getattr(agg, 'vwap', None),
                't': agg.timestamp,
                'n': getattr(agg, 'transactions', None),
            })

        df = pd.DataFrame(bars)
        df = df.rename(columns={
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "t": "timestamp",
            "n": "num_trades",
            "vw": "vwap",
        })

        # Polygon timestamps are millisecond epoch
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp")

        return df[["open", "high", "low", "close", "volume", "vwap", "num_trades"]]

    # ------------------------------------------------------------------
    # Historic Ticks
    # ------------------------------------------------------------------

    def get_ticks(
        self,
        pair: str,
        date: Union[str, datetime],
        limit: int = 500,
    ) -> pd.DataFrame:
        """
        Returns historic trade ticks for a single date.
        Note: tick data is only available on paid Polygon plans.

        Example:
            df = data.get_ticks("EUR_USD", "2024-06-01")
        """
        from_sym, to_sym = pair.replace("-", "_").split("_")

        ticks = self.client.get_historic_forex_ticks(
            from_symbol=from_sym,
            to_symbol=to_sym,
            date=date,
            limit=limit,
        )

        results = ticks.get("ticks", []) if isinstance(ticks, dict) else ticks
        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        if "t" in df.columns:
            df["timestamp"] = pd.to_datetime(df["t"], unit="ms", utc=True)
            df = df.drop(columns=["t"]).set_index("timestamp")

        return df

    # ------------------------------------------------------------------
    # NBBO Quotes
    # ------------------------------------------------------------------

    def get_quotes(
        self,
        pair: str,
        timestamp: Union[str, datetime],
        limit: int = 5000,
        order: str = "asc",
    ) -> pd.DataFrame:
        """
        Returns NBBO bid/ask quotes for a given timestamp or date range.

        Example:
            df = data.get_quotes("EUR_USD", "2024-06-01")
        """
        ticker = _to_polygon_ticker(pair).replace(":", "-")  # C:EURUSD -> C-EURUSD

        quotes = self.client.get_quotes(
            symbol=ticker,
            timestamp=timestamp,
            limit=limit,
            order=order,
        )

        if not quotes:
            return pd.DataFrame()

        df = pd.DataFrame(quotes if isinstance(quotes, list) else quotes.get("results", []))
        if "t" in df.columns:
            df["timestamp"] = pd.to_datetime(df["t"], unit="ns", utc=True)
            df = df.drop(columns=["t"]).set_index("timestamp")

        return df

def plot_candles(
    df: pd.DataFrame,
    pair: str = "EUR/USD",
    title: str = None,
    show_volume: bool = True,
    theme: str = "dark",  # "dark" | "light"
) -> go.Figure:
    """
    Renders an interactive candlestick chart with volume subplot.

    Args:
        df:          DataFrame from ForexData.get_candles() — must have OHLCV columns + datetime index
        pair:        Display name for the pair (e.g. "EUR/USD")
        title:       Optional chart title override
        show_volume: Whether to render volume bars below
        theme:       "dark" or "light"

    Example:
        df = data.get_candles("EUR_USD", "2024-06-01", "2024-06-07", multiplier=1, timespan="hour")
        fig = plot_candles(df, pair="EUR/USD")
        fig.show()
    """
    is_dark = theme == "dark"

    bg      = "#0f1117" if is_dark else "#ffffff"
    paper   = "#0f1117" if is_dark else "#f8f9fa"
    grid    = "#1e2130" if is_dark else "#e8e8e8"
    text    = "#c9d1d9" if is_dark else "#1a1a2e"
    up      = "#26a69a"   # teal green
    down    = "#ef5350"   # red
    vol_up  = "rgba(38, 166, 154, 0.27)"
    vol_dn  = "rgba(239, 83, 80, 0.27)"

    rows = 2 if show_volume else 1
    row_heights = [0.75, 0.25] if show_volume else [1.0]

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=row_heights,
    )

    # --- Candlesticks ---
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=pair,
            increasing=dict(line=dict(color=up, width=1), fillcolor=up),
            decreasing=dict(line=dict(color=down, width=1), fillcolor=down),
        ),
        row=1, col=1,
    )

    # --- VWAP line (if available) ---
    if "vwap" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["vwap"],
                name="VWAP",
                line=dict(color="#f0a500", width=1, dash="dot"),
                opacity=0.8,
            ),
            row=1, col=1,
        )

    # --- Volume bars ---
    if show_volume and "volume" in df.columns:
        colors = [up if c >= o else down
                for c, o in zip(df["close"], df["open"])]
        bar_colors = [vol_up if c >= o else vol_dn
                    for c, o in zip(df["close"], df["open"])]

        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["volume"],
                name="Volume",
                marker_color=bar_colors,
                marker_line_width=0,
            ),
            row=2, col=1,
        )

    # --- Layout ---
    chart_title = title or f"{pair} — Candlestick Chart"

    fig.update_layout(
        title=dict(text=chart_title, font=dict(color=text, size=16)),
        paper_bgcolor=paper,
        plot_bgcolor=bg,
        font=dict(color=text, family="monospace"),
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=60, r=40, t=60, b=40),
        hovermode="x unified",
    )

    axis_style = dict(
        gridcolor=grid,
        linecolor=grid,
        tickfont=dict(color=text, size=10),
        zerolinecolor=grid,
    )

    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)

    # Price axis: show enough decimal places for forex
    fig.update_yaxes(tickformat=".5f", row=1, col=1)

    return fig

# ------------------------------------------------------------------
# Quick smoke test
# ------------------------------------------------------------------

if __name__ == "__main__":
  
    data = ForexData()

    df = data.get_candles("EUR_USD", "2024-06-01", "2024-06-07", multiplier=1, timespan="hour")
    fig = plot_candles(df, pair="EUR/USD")
    fig.show()  # opens in browser

    # 5m chart
    df5 = data.get_candles("EUR_USD", "2024-06-03", "2024-06-04", multiplier=5, timespan="minute")
    fig5 = plot_candles(df5, pair="EUR/USD 5m", title="EUR/USD — 5 Minute Bars")
    fig5.show()