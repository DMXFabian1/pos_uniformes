"""Posiciones y registro predicción-vs-realidad."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..signals.base import Signal
from ..storage import dumps
from .fill_model import Fill, MakerOrder


@dataclass
class Position:
    signal: Signal
    status: str = "pending"          # pending | open | closed
    exec_ts: int = 0                 # cuándo puede ejecutarse (latencia)
    fills: list[Fill] = field(default_factory=list)
    maker_orders: list[MakerOrder] = field(default_factory=list)
    ts_fill: int = 0
    ts_exit: int = 0
    size_filled: float = 0.0
    cost: float = 0.0                # USD gastados (compras / colateral)
    fees: float = 0.0
    payout: float = 0.0              # USD recibidos (ventas / merge / resolución)
    realized_pnl: float = 0.0
    exit_reason: str = ""
    inventory: dict[str, float] = field(default_factory=dict)   # token -> shares (+largo / -corto)

    @property
    def predicted_pnl(self) -> float:
        return self.signal.predicted_pnl

    @property
    def collateral(self) -> float:
        return max(self.cost - self.payout, 0.0) if self.status == "open" else 0.0

    def to_row(self, run_id: str, mode: str) -> dict[str, Any]:
        s = self.signal
        return {
            "run_id": run_id, "mode": mode, "signal_id": s.signal_id, "kind": s.kind, "condition_id": s.condition_id,
            "event_id": s.event_id, "ts_signal": s.ts_ms, "ts_fill": self.ts_fill, "ts_exit": self.ts_exit,
            "status": self.status, "exit_reason": self.exit_reason, "size_target": s.size,
            "size_filled": self.size_filled, "cost": round(self.cost, 6), "fees": round(self.fees, 6),
            "payout": round(self.payout, 6), "predicted_edge": s.edge_net, "predicted_pnl": round(s.predicted_pnl, 6),
            "realized_pnl": round(self.realized_pnl, 6), "error": round(self.realized_pnl - s.predicted_pnl, 6),
            "confidence": s.confidence,
            "meta": dumps({**s.meta, "legs": [l.__dict__ for l in s.legs],
                           "fills": [f.__dict__ for f in self.fills]}),
            "conf_heuristic": s.meta.get("conf_heuristic", s.confidence),
            "p_win_model": s.meta.get("p_win_model"),
            "model_version": s.meta.get("model_version"),
        }


def signal_row(s: Signal, run_id: str) -> dict[str, Any]:
    return {
        "ts_ms": s.ts_ms, "signal_id": s.signal_id, "kind": s.kind, "condition_id": s.condition_id,
        "event_id": s.event_id, "legs": dumps([l.__dict__ for l in s.legs]), "size": s.size,
        "edge_gross": s.edge_gross, "fee_est": s.fee_est, "edge_net": s.edge_net, "confidence": s.confidence,
        "horizon": s.horizon, "meta": dumps(s.meta), "run_id": run_id,
    }
