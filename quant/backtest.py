"""Backtest harness using vectorbt."""
import numpy as np
import vectorbt as vbt
from datetime import datetime

def run_backtest(tickers, start, end, strategy="agent"):
    """Run backtest. Returns a list of result dicts."""
    from quant.data import fetch_bars
    
    results = []
    for ticker in tickers:
        try:
            bars = fetch_bars(ticker, start, end)
            if not bars:
                results.append({"ticker": ticker, "error": "No data fetched"})
                continue
            
            closes = np.array([b[4] for b in bars])
            if len(closes) < 20:
                results.append({"ticker": ticker, "error": f"Insufficient data: {len(closes)} bars"})
                continue
            
            returns = np.diff(closes) / closes[:-1]
            if len(returns) == 0 or np.std(returns) == 0:
                results.append({"ticker": ticker, "error": "No price variance"})
                continue
            
            sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
            
            cumulative = np.cumprod(1 + returns)
            peak = cumulative[0]
            max_dd = 0.0
            for c in cumulative:
                if c > peak:
                    peak = c
                dd = (peak - c) / peak
                if dd > max_dd:
                    max_dd = dd
            
            win_rate = float((returns > 0).sum() / len(returns))
            
            results.append({
                "ticker": ticker,
                "sharpe": round(sharpe, 2),
                "max_dd": round(float(max_dd) * 100, 1),
                "win_rate": round(float(win_rate) * 100, 1),
                "n_bars": len(closes),
            })
        except Exception as e:
            results.append({"ticker": ticker, "error": str(e)})
    
    return results
