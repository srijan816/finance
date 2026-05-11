"""Explain the application's decision and simulation process."""


def decision_process() -> str:
    return """# Quant Lab Decision Process

## 1. Data Ingestion

	- Historical OHLCV bars are fetched from the configured data provider.
	- Current default provider is yfinance/Yahoo, which is useful for research but not vendor-grade.
	- Every major output now carries a DEMO / RESEARCH / PRODUCTION_CANDIDATE status block.
	- Bars are aligned by common trading dates before portfolio simulation.
- Real production-grade point-in-time universes require Norgate, CRSP, or another vendor/security-master export.

## 2. Universe Selection

- If `--tickers` is supplied, the app treats that as a user-defined research universe.
- If `--universe sp500_wikipedia` is supplied, the app fetches real Wikipedia S&P 500 current constituents and selected component changes.
- The Wikipedia adapter is real data, but not complete enough to call survivorship-bias-free.
- User-supplied CSV universes can be loaded from `data/universes/<name>.csv` with `symbol,start_date,end_date,name,sector,source`.
- A symbol is eligible only when `start_date <= as_of <= end_date` or `end_date` is blank.

## 3. Signal Formation

- Momentum: stock is eligible when trailing 63-trading-day return is positive.
- Momentum rank: trailing 63-trading-day return.
- SMA-cross: stock is eligible when 20-day moving average is above 50-day moving average.
- SMA rank: `20-day average / 50-day average - 1`.
- Buy-hold: every stock is always eligible.
- No signal uses future bars.

## 4. Veil of Ignorance

- At rebalance date `T`, the signal uses `closes[:T]`, strictly excluding the rebalance date close and all future closes.
- This is enforced in `quant/simulator.py`.
- A regression test injects a future price spike and verifies it cannot affect selection.

## 5. Portfolio Construction

- The app selects the top `max_positions` qualifying names.
- Selected names receive equal target weights.
- If no names qualify, the target is 100% cash.
- Current implementation is long-only and cash-account style.

## 6. Execution Model

- The simulator generates orders to move from current holdings to target weights.
- Orders pass through `BrokerSimulator`.
- Broker tracks cash, shares, fills, rejected orders, fees, and slippage.
- Broker commission defaults to `0 bps`; configured fees are `notional * commission_bps / 10000`.
- Slippage worsens execution price for buys and sells.
- Volume cap limits order size using `volume * price * max_volume_participation`.
- Orders may be partially filled or rejected.

## 7. Mark-To-Market

- After execution, holdings are marked to subsequent closes.
- Daily portfolio returns are calculated from actual cash and share holdings.
- Metrics include total return, annual return, volatility, Sharpe, Sortino, Calmar, max drawdown, VaR, CVaR, alpha, beta, and information ratio.

## 8. Historical Decision Audit

- Decision audit asks: was BUY/HOLD correct over a forward horizon?
- BUY is correct when forward return or active return beats the neutral band.
- HOLD is correct when skipping the asset avoided weak forward/active return.
- Reports accuracy, Brier score, edge confidence interval, and p-values.

## 9. News And Fundamentals

- News support is point-in-time only.
- The app may only use articles with `published_at <= decision_time`.
- Current trading simulator does not yet use news or fundamentals in allocation.
- LLM output is not trusted as market truth; it is diagnostic/explanatory until a properly timestamped dataset exists.

## 10. Current Production Caveats

- Yahoo/yfinance is not exchange-grade or survivorship-bias-free.
- Wikipedia S&P 500 reconstruction is public and real, but incomplete.
- A true production run needs vendor-grade delisted securities, historical constituents, corporate actions, and a security master.
	- Execution is improved but still bar-based, not order-book based.
	- Current outputs should be treated as hypothesis-generation unless their status block says RESEARCH or PRODUCTION_CANDIDATE.
	"""
