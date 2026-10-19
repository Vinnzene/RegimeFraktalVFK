"""Tahap 9: Visualization Module"""
from __future__ import annotations
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def plot_setup(row: pd.Series, m30m: pd.DataFrame, output_dir: str = "reports/charts"):
    """
    Plot candlestick chart for a single setup with entry, SL, TP and exit markers.
    Includes OFI and CVD panels.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Determine time range
    t_entry = row["timestamp_entry"]
    t_exit = row["exit_timestamp"] if pd.notna(row["exit_timestamp"]) else t_entry + pd.Timedelta(hours=4)
    
    # Add context window
    start_time = t_entry - pd.Timedelta(hours=24) # ~48 bars before
    end_time = t_exit + pd.Timedelta(hours=12)    # ~24 bars after
    
    mask = (m30m["timestamp"] >= start_time) & (m30m["timestamp"] <= end_time)
    df_plot = m30m[mask].copy()
    
    if df_plot.empty:
        print(f"Warning: No market data found for trade at {t_entry}")
        return None
        
    # Create subplots: 1 for Price, 1 for OFI, 1 for CVD
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=("Price", "OFI", "CVD")
    )
    
    # Add Candlesticks
    fig.add_trace(go.Candlestick(
        x=df_plot['timestamp'],
        open=df_plot['open'],
        high=df_plot['high'],
        low=df_plot['low'],
        close=df_plot['close'],
        name='Price'
    ), row=1, col=1)
    
    # Subplots
    if "ofi" in df_plot.columns:
        fig.add_trace(go.Bar(x=df_plot['timestamp'], y=df_plot['ofi'], name='OFI'), row=2, col=1)
    if "cvd" in df_plot.columns:
        fig.add_trace(go.Scatter(x=df_plot['timestamp'], y=df_plot['cvd'], name='CVD'), row=3, col=1)

    # Plot Entry, SL, TP Lines (using shapes from t_setup/t_entry to t_exit)
    # Draw horizontal lines for the duration of the trade
    fig.add_shape(type="line", x0=t_entry, y0=row["entry"], x1=t_exit, y1=row["entry"], line=dict(color="blue", width=2, dash="dash"), row=1, col=1)
    fig.add_shape(type="line", x0=t_entry, y0=row["stop_loss"], x1=t_exit, y1=row["stop_loss"], line=dict(color="red", width=2, dash="dash"), row=1, col=1)
    if pd.notna(row.get("take_profit")):
        fig.add_shape(type="line", x0=t_entry, y0=row["take_profit"], x1=t_exit, y1=row["take_profit"], line=dict(color="green", width=2, dash="dash"), row=1, col=1)
        
    # Markers for Entry and Exit
    # Entry Marker
    fig.add_trace(go.Scatter(
        x=[t_entry], y=[row["entry"]], mode="markers", 
        marker=dict(symbol="triangle-up" if row["direction"]=="LONG" else "triangle-down", size=15, color="blue"),
        name="Entry"
    ), row=1, col=1)
    
    # Exit Marker
    if pd.notna(row.get("exit_price")):
        fig.add_trace(go.Scatter(
            x=[t_exit], y=[row["exit_price"]], mode="markers",
            marker=dict(symbol="x", size=12, color="black"),
            name=f"Exit ({row.get('outcome')})"
        ), row=1, col=1)
        
    # Formatting annotations
    info_text = (
        f"Regime 4H: {row.get('regime_4h', 'N/A')}<br>"
        f"Regime 1H: {row.get('regime_1h', 'N/A')}<br>"
        f"Bias: {row.get('bias', 'N/A')}<br>"
        f"Dir: {row.get('direction')}<br>"
        f"Entry: {row.get('entry')}<br>"
        f"SL: {row.get('stop_loss')}<br>"
        f"TP: {row.get('take_profit', 'N/A')}<br>"
        f"RR: {row.get('RR', 'N/A')}<br>"
        f"Outcome: {row.get('outcome')} ({row.get('R_multiple', 'N/A')} R)"
    )
    
    fig.add_annotation(
        xref="paper", yref="paper", x=0.01, y=0.99,
        text=info_text,
        showarrow=False,
        align="left",
        bgcolor="rgba(255, 255, 255, 0.8)",
        bordercolor="black"
    )
    
    fig.update_layout(
        title=f"Setup {row.get('direction')} at {t_entry}",
        xaxis_rangeslider_visible=False,
        height=800
    )
    
    # Save
    ts_str = t_entry.strftime('%Y%m%d_%H%M%S') if hasattr(t_entry, 'strftime') else str(t_entry)
    filename = f"setup_{row.get('direction')}_{ts_str}.html"
    fig.write_html(os.path.join(output_dir, filename))
    return fig

def plot_walk_forward_cumulative_r(log: pd.DataFrame, output_dir: str = "reports/charts"):
    os.makedirs(output_dir, exist_ok=True)
    if log.empty:
        return None
        
    valid = log[(log["setup_valid"] == True) & (log["outcome"] != "AMBIGUOUS")].copy()
    if valid.empty:
        return None
        
    valid = valid.sort_values("timestamp_entry")
    
    fig = go.Figure()
    
    if "r_gross" in valid.columns:
        valid["cumulative_R_gross"] = valid["r_gross"].cumsum()
        fig.add_trace(go.Scatter(
            x=valid["timestamp_entry"], y=valid["cumulative_R_gross"],
            mode="lines+markers", name="Cumulative R (Gross)",
            line=dict(color="royalblue", dash="dash")
        ))
        
    if "r_net" in valid.columns:
        valid["cumulative_R_net"] = valid["r_net"].cumsum()
        fig.add_trace(go.Scatter(
            x=valid["timestamp_entry"], y=valid["cumulative_R_net"],
            mode="lines+markers", name="Cumulative R (Net)",
            line=dict(color="forestgreen", width=2)
        ))
    else:
        valid["cumulative_R"] = valid["R_multiple"].cumsum()
        fig.add_trace(go.Scatter(
            x=valid["timestamp_entry"], y=valid["cumulative_R"],
            mode="lines+markers", name="Cumulative R",
            line=dict(color="forestgreen", width=2)
        ))
    
    # Add window boundaries
    if "window_id" in valid.columns:
        window_starts = valid.groupby("window_id")["timestamp_entry"].min()
        for wid, t_start in window_starts.items():
            if pd.notna(t_start):
                t_ms = int(t_start.timestamp() * 1000) if hasattr(t_start, "timestamp") else t_start
                fig.add_vline(x=t_ms, line_width=1, line_dash="dash", line_color="gray", annotation_text=f"W{wid}")
            
    fig.update_layout(title="Walk-Forward Cumulative R Curve (Gross vs Net with Fee/Slippage)", xaxis_title="Time", yaxis_title="Cumulative R")
    fig.write_html(os.path.join(output_dir, "cumulative_R.html"))
    return fig

def plot_regime_setup_distribution(log: pd.DataFrame, output_dir: str = "reports/charts"):
    os.makedirs(output_dir, exist_ok=True)
    if log.empty or "regime_4h" not in log.columns:
        return None
        
    valid = log[log["setup_valid"] == True]
    counts = valid.groupby(["regime_4h", "direction"]).size().unstack(fill_value=0).reset_index()
    
    fig = go.Figure()
    for col in counts.columns:
        if col != "regime_4h":
            fig.add_trace(go.Bar(name=col, x=counts["regime_4h"], y=counts[col]))
            
    fig.update_layout(barmode='stack', title="Regime vs Setup Distribution (Long/Short) - Historical")
    fig.write_html(os.path.join(output_dir, "regime_distribution.html"))
    return fig

def plot_setup_outcome_distribution(log: pd.DataFrame, output_dir: str = "reports/charts"):
    os.makedirs(output_dir, exist_ok=True)
    if log.empty:
        return None
        
    valid = log[log["setup_valid"] == True]
    counts = valid["outcome"].value_counts().reset_index()
    counts.columns = ["outcome", "count"]
    
    fig = go.Figure(data=[go.Pie(labels=counts["outcome"], values=counts["count"], hole=.3)])
    fig.update_layout(title="Setup Outcome Distribution (Historical Simulation)")
    fig.write_html(os.path.join(output_dir, "outcome_distribution.html"))
    return fig
