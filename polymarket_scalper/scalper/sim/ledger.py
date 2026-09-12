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
    entrada_maker: MakerOrder | None = None      # orden puesta esperando llenarse (maker-first)
    orden_entrada: MakerOrder | None = None      # la misma orden, conservada tras llenarse o caducar (informe)
    ts_placed: int = 0               # cuándo se puso la orden maker
    ts_fill: int = 0                 # primer fill real
    ts_exit: int = 0
    adverse: dict[int, float | None] = field(default_factory=dict)   # horizonte_ms -> mid - precio de entrada
    mid_previo: float | None = None  # último mid observado (estado del libro) para las marcas
    obs_previa: tuple[float | None, float | None, float | None] | None = None   # (mid, bid, ask)
    horizontes_hechos: set = field(default_factory=set)
    cond_fill: dict[str, Any] = field(default_factory=dict)   # condiciones al poner la orden
    # --- calidad del dato con el que se decidió, y versión del motor que decidió
    experiment: str = ""
    freshness_ms: int = 0
    feed_state: str = "SANO"
    contaminado: bool = False
    # --- posición hipotética: se rechazó y se sigue solo para medir qué habría pasado
    sombra: bool = False
    motivo_rechazo: str = ""
    # --- recorrido del precio tras el fill (en la ventana corta del ledger)
    entrada_px: float | None = None
    tick: float = 0.01
    mfe: float | None = None
    mae: float | None = None
    t_mfe_ms: int | None = None
    t_mae_ms: int | None = None
    t_fav: dict[float, int] = field(default_factory=dict)    # ticks a favor -> ms hasta alcanzarlos
    t_adv: dict[float, int] = field(default_factory=dict)
    t_target_ms: int | None = None
    t_stop_ms: int | None = None
    # --- la cadena de retrasos, separada
    proc_delay_ms: int = 0        # del evento de mercado a que el motor termina de procesarlo
    decision_delay_ms: int = 0    # de ahí a que la señal existe
    exec_delay_ms: int = 0        # de la señal a que la orden está puesta
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
        o = self.orden_entrada or self.entrada_maker
        esc = o.escenarios() if o is not None else {}
        adv = {f"adverse_{_hz(h)}": (None if v is None else round(v, 5)) for h, v in self.adverse.items()}
        mov = {f"t_fav_{_tk(k)}t_ms": v for k, v in self.t_fav.items()}
        mov.update({f"t_adv_{_tk(k)}t_ms": v for k, v in self.t_adv.items()})
        antes = None
        if self.t_target_ms is not None or self.t_stop_ms is not None:
            antes = self.t_target_ms is not None and (self.t_stop_ms is None or self.t_target_ms <= self.t_stop_ms)
        hold = (self.ts_exit - self.ts_fill) / 1000 if (self.ts_fill and self.ts_exit and self.size_filled > 0) else None
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
            "strategy": s.strategy, "entry_role": s.meta.get("entry_role", "taker"),
            "ts_placed": self.ts_placed, "hold_s": None if hold is None else round(hold, 3),
            "fill_conservador": esc.get("conservador"), "fill_optimista": esc.get("optimista"),
            "queue_inicial": None if o is None else round(o.queue_inicial, 4),
            "vol_cruzado": None if o is None else round(o.vol_cruzado, 4),
            "barrido": None if o is None else bool(o.barrido),
            "causa_fill": None if o is None else (o.causa or None),
            "edge_taker": s.meta.get("edge_taker"),
            "experiment": self.experiment, "freshness_ms": self.freshness_ms, "feed_state": self.feed_state,
            "contaminado": self.contaminado, "sombra": self.sombra, "motivo_rechazo": self.motivo_rechazo,
            "mfe": None if self.mfe is None else round(self.mfe, 5),
            "mae": None if self.mae is None else round(self.mae, 5),
            "t_mfe_ms": self.t_mfe_ms, "t_mae_ms": self.t_mae_ms,
            "t_target_ms": self.t_target_ms, "t_stop_ms": self.t_stop_ms, "target_antes_que_stop": antes,
            "proc_delay_ms": self.proc_delay_ms, "decision_delay_ms": self.decision_delay_ms,
            "exec_delay_ms": self.exec_delay_ms,
            **adv, **mov,
        }


def _hz(h: int) -> str:
    return f"{h}ms" if h < 1000 else f"{h // 1000}s"


def _tk(k: float) -> str:
    """0.5 -> '05', 1 -> '1', 2 -> '2'. Los nombres de columna no admiten el punto."""
    return "05" if abs(k - 0.5) < 1e-9 else str(int(k))


def signal_row(s: Signal, run_id: str) -> dict[str, Any]:
    return {
        "ts_ms": s.ts_ms, "signal_id": s.signal_id, "kind": s.kind, "condition_id": s.condition_id,
        "event_id": s.event_id, "legs": dumps([l.__dict__ for l in s.legs]), "size": s.size,
        "edge_gross": s.edge_gross, "fee_est": s.fee_est, "edge_net": s.edge_net, "confidence": s.confidence,
        "horizon": s.horizon, "meta": dumps({**s.meta, "strategy": s.strategy}), "run_id": run_id,
    }
