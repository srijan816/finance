"""Order, fill, and brokerage-style execution modeling."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ExecutionConfig:
    commission_bps: float = 0.0
    slippage_bps: float = 2.0
    max_volume_participation: float = 0.05
    min_notional: float = 25.0
    allow_fractional: bool = True
    reject_if_insufficient_cash: bool = False


@dataclass
class Order:
    submitted_at: str
    ticker: str
    side: str
    quantity: float
    reference_price: float

    @property
    def notional(self) -> float:
        return abs(self.quantity * self.reference_price)


@dataclass
class Fill:
    submitted_at: str
    filled_at: str
    ticker: str
    side: str
    quantity: float
    reference_price: float
    fill_price: float
    gross_notional: float
    fee: float
    slippage_cost: float

    def to_dict(self) -> dict:
        return {
            "submitted_at": self.submitted_at,
            "filled_at": self.filled_at,
            "ticker": self.ticker,
            "side": self.side,
            "quantity": round(self.quantity, 6),
            "reference_price": round(self.reference_price, 4),
            "fill_price": round(self.fill_price, 4),
            "gross_notional": round(self.gross_notional, 2),
            "fee": round(self.fee, 4),
            "slippage_cost": round(self.slippage_cost, 4),
        }


@dataclass
class RejectedOrder:
    submitted_at: str
    ticker: str
    side: str
    quantity: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "submitted_at": self.submitted_at,
            "ticker": self.ticker,
            "side": self.side,
            "quantity": round(self.quantity, 6),
            "reason": self.reason,
        }


class BrokerSimulator:
    """Cash-account broker simulator with long-only positions."""

    def __init__(self, initial_cash: float, config: ExecutionConfig | None = None):
        self.cash = float(initial_cash)
        self.positions: Dict[str, float] = {}
        self.config = config or ExecutionConfig()
        self.fills: List[Fill] = []
        self.rejected_orders: List[RejectedOrder] = []

    def equity(self, prices: Dict[str, float]) -> float:
        return self.cash + sum(self.positions.get(ticker, 0.0) * prices[ticker] for ticker in prices)

    def weights(self, prices: Dict[str, float]) -> Dict[str, float]:
        equity = self.equity(prices)
        if equity <= 0:
            return {ticker: 0.0 for ticker in prices}
        return {
            ticker: self.positions.get(ticker, 0.0) * price / equity
            for ticker, price in prices.items()
        }

    def rebalance_to_weights(
        self,
        date: str,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
        volumes: Dict[str, float],
    ) -> dict:
        starting_equity = self.equity(prices)
        orders = self._orders_for_targets(date, target_weights, prices, starting_equity)
        sells = [order for order in orders if order.side == "sell"]
        buys = [order for order in orders if order.side == "buy"]
        fills_before = len(self.fills)
        rejects_before = len(self.rejected_orders)
        for order in sells + buys:
            self.execute_order(order, date, volumes.get(order.ticker, 0.0))
        ending_equity = self.equity(prices)
        return {
            "starting_equity": starting_equity,
            "ending_equity": ending_equity,
            "fills": [fill.to_dict() for fill in self.fills[fills_before:]],
            "rejected_orders": [reject.to_dict() for reject in self.rejected_orders[rejects_before:]],
        }

    def execute_order(self, order: Order, filled_at: str, volume: float) -> None:
        if order.quantity <= 0:
            return
        if order.notional < self.config.min_notional:
            self._reject(order, "below_min_notional")
            return

        max_qty = self._max_fill_quantity(order, volume)
        qty = min(order.quantity, max_qty)
        if qty <= 0:
            self._reject(order, "no_volume_capacity")
            return
        if not self.config.allow_fractional:
            qty = int(qty)
            if qty <= 0:
                self._reject(order, "fractional_not_allowed")
                return

        slip = self.config.slippage_bps / 10_000
        fill_price = order.reference_price * (1 + slip if order.side == "buy" else 1 - slip)
        gross = qty * fill_price
        fee = gross * self.config.commission_bps / 10_000
        slippage_cost = qty * abs(fill_price - order.reference_price)

        if order.side == "buy":
            required_cash = gross + fee
            if required_cash > self.cash:
                if self.config.reject_if_insufficient_cash:
                    self._reject(order, "insufficient_cash")
                    return
                qty = max((self.cash / (fill_price * (1 + self.config.commission_bps / 10_000))), 0.0)
                if not self.config.allow_fractional:
                    qty = int(qty)
                gross = qty * fill_price
                fee = gross * self.config.commission_bps / 10_000
                slippage_cost = qty * abs(fill_price - order.reference_price)
                if gross + fee < self.config.min_notional:
                    self._reject(order, "insufficient_cash")
                    return
            self.cash -= gross + fee
            self.positions[order.ticker] = self.positions.get(order.ticker, 0.0) + qty
        else:
            owned = self.positions.get(order.ticker, 0.0)
            qty = min(qty, owned)
            if qty <= 0:
                self._reject(order, "no_position")
                return
            gross = qty * fill_price
            fee = gross * self.config.commission_bps / 10_000
            slippage_cost = qty * abs(fill_price - order.reference_price)
            self.cash += gross - fee
            remaining = owned - qty
            if remaining <= 1e-10:
                self.positions.pop(order.ticker, None)
            else:
                self.positions[order.ticker] = remaining

        self.fills.append(Fill(
            submitted_at=order.submitted_at,
            filled_at=filled_at,
            ticker=order.ticker,
            side=order.side,
            quantity=qty,
            reference_price=order.reference_price,
            fill_price=fill_price,
            gross_notional=gross,
            fee=fee,
            slippage_cost=slippage_cost,
        ))
        if qty < order.quantity:
            self._reject(Order(order.submitted_at, order.ticker, order.side, order.quantity - qty, order.reference_price), "partial_fill_volume_or_cash_limit")

    def cost_summary(self) -> dict:
        return {
            "fees": round(sum(fill.fee for fill in self.fills), 4),
            "slippage": round(sum(fill.slippage_cost for fill in self.fills), 4),
            "fills": len(self.fills),
            "rejected_orders": len(self.rejected_orders),
        }

    def _orders_for_targets(
        self,
        date: str,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
        equity: float,
    ) -> List[Order]:
        orders = []
        for ticker, price in prices.items():
            target_value = equity * target_weights.get(ticker, 0.0)
            current_value = self.positions.get(ticker, 0.0) * price
            delta_value = target_value - current_value
            if abs(delta_value) < self.config.min_notional:
                continue
            side = "buy" if delta_value > 0 else "sell"
            orders.append(Order(date, ticker, side, abs(delta_value) / price, price))
        return orders

    def _max_fill_quantity(self, order: Order, volume: float) -> float:
        if volume <= 0:
            return order.quantity
        max_notional = volume * order.reference_price * self.config.max_volume_participation
        return max_notional / order.reference_price

    def _reject(self, order: Order, reason: str) -> None:
        self.rejected_orders.append(RejectedOrder(
            submitted_at=order.submitted_at,
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            reason=reason,
        ))
