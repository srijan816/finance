# IBKR Bot Integration Plan

This document explains how Quant Lab can be connected to an existing Interactive Brokers account for a small-capital live or paper allocation.

## Feasibility

Integration is feasible.

IBKR supports automated trading through the Trader Workstation API and IB Gateway. The API can request market data, inspect account state, read positions, place orders, modify orders, and monitor fills. For a small controlled allocation, the safest path is:

```text
Quant Lab signal engine
-> target portfolio and order proposal
-> pre-trade risk checks
-> manual approval or paper mode
-> IBKR order submission
-> fill monitoring
-> reconciliation and journal
```

The first live version should not be fully autonomous.

## Best API Choice

The practical options are:

1. IB Gateway or Trader Workstation plus TWS API.
2. A Python wrapper such as `ib_insync` or `ib_async`.
3. IBKR Client Portal API.

For this project, the most practical path is IB Gateway plus a Python wrapper. IB Gateway is lighter than the full TWS desktop UI, and the Python wrapper makes account, order, and contract flows easier to manage.

## Important Operational Constraints

IBKR automation is real, but it has operational friction:

- TWS or IB Gateway must be running and authenticated.
- Sessions may require periodic re-authentication.
- Market data may require subscriptions.
- API permissions must be enabled in IBKR settings.
- Live trading should use account-level and strategy-level kill switches.
- Orders placed through API will appear in IBKR like normal orders.

## Hong Kong Context

You mentioned:

- Small IBKR commission, around $1 per trade.
- No Hong Kong capital gains tax.

The no-capital-gains-tax point helps the strategy because it reduces tax drag from rebalancing. But commissions still matter. A $1 commission is small for $2,000-$5,000 swing trades, but large for tiny frequent trades. The bot should therefore:

- Avoid too many small orders.
- Prefer position sizes where commission is a small fraction of notional.
- Batch rebalances.
- Avoid excessive churn.
- Track realized commission per strategy.

## Required Safety Features Before Live Trading

Before sending live orders, the bot should enforce:

| Safety Control | Rule |
|---|---|
| Max allocation | Never exceed the capital sleeve assigned to the bot. |
| Max position | Cap each position, for example 10-20% of bot sleeve. |
| Max order size | Cap per-order notional. |
| Max daily orders | Prevent runaway loops. |
| Max daily loss | Disable new buys after threshold loss. |
| Stop orders | Every live long position must have a stop plan. |
| Reconciliation | Compare local positions to IBKR positions after every order. |
| Manual approve mode | Required for first live phase. |
| Paper mode | Required before any live order. |
| Kill switch | Immediate flatten-or-disable mechanism. |

## Recommended Implementation Phases

### Phase 1: Signal-Only

Run:

```bash
quant recommend-v2 --json-output
```

Store the recommendations, but place no orders.

### Phase 2: Paper Shadow Mode

Create an IBKR adapter that:

- Connects to IBKR paper account.
- Reads account cash and positions.
- Converts recommendations to proposed orders.
- Logs what it would do.
- Places no live orders.

### Phase 3: Paper Execution

Allow paper orders only:

- Buy limit orders near pullback or breakout entries.
- Protective stop orders after fill.
- Position and allocation caps.
- Full order/fill journal.

### Phase 4: Live Manual Approval

Generate orders but require confirmation before sending them.

Example:

```text
Proposed order:
BUY 4.8 AVGO limit 431.50
Attached stop 398.44
Capital sleeve usage after order: 37%
Type YES to send.
```

### Phase 5: Limited Autonomous Live Trading

Only after paper and manual live phases are stable:

- Use small allocation.
- Only trade highly liquid stocks/ETFs.
- Only use limit orders.
- Never trade options initially.
- Keep max daily orders very low.

## Proposed Module Design

Future files:

```text
quant/brokers/ibkr.py
quant/order_planner.py
quant/risk.py
quant/reconcile.py
tests/test_order_planner.py
tests/test_risk.py
```

The broker adapter should be a thin boundary. The strategy engine should not know IBKR-specific details.

## Order Planner

The order planner should convert target allocations into orders:

```text
recommendations + account state + current positions
-> target dollar allocation
-> desired shares
-> delta shares
-> order proposal
```

It should support:

- Fractional shares if available for the instrument/account.
- Whole-share fallback.
- Limit buy orders.
- Stop-loss orders.
- No trade if expected position is too small after commission.

## Commission Model

Use an IBKR commission setting such as:

```text
commission_per_order = 1.00 USD
minimum_trade_notional = 500.00 USD
```

This prevents the strategy from placing uneconomic small orders.

## First Live Bot Configuration

A conservative first live allocation might be:

```text
bot_sleeve = 2,000 to 5,000 USD
max_positions = 3
max_position_pct = 35%
max_daily_orders = 3
order_type = limit only
allow_shorts = false
allow_options = false
manual_approval = true
```

## Bottom Line

Direct IBKR integration is possible, and this codebase is now moving toward a structure that can support it. The right next step is not full automation. The right next step is a paper-shadow IBKR adapter that reads the account, produces proposed orders, and logs them without trading. Once that is reliable, paper execution and then small live manual-approval trading are realistic.
