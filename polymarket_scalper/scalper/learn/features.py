"""Features de una señal en el momento de emitirla. Nada de aquí puede depender del resultado.

Se calculan una vez en el motor, viajan en `signal.meta["features"]` hasta el ledger y de ahí
salen para entrenar: la misma función produce lo que ve el modelo en vivo y en entrenamiento,
así no hay desfase entre ambos.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..book import OrderBook
from ..discovery import MarketInfo
from ..micro import NOMBRES as MICRO
from ..signals.base import Signal

NUMERIC = [
    "edge_net", "edge_gross", "fee_est", "size", "conf_heuristic", "entry_price", "n_legs",
    "spread_ticks", "tpm", "mid_vol", "imbalance", "bid_depth", "ask_depth", "fee_rate", "tick_size",
    "volume_24h_log", "p_model", "p_market", "deviation", "tau", "lead", "pregame", "has_pregame",
    "wallet_score", "wallet_n_log", "wallet_roi", "their_usd_log", "hour_utc", "dow", "is_maker",
    "moneyness_bps", "elapsed_s", "seconds_left", "window_s", "market_skew", "prev_up_won", "prev_return_bps",
    "event_risk_score", "ms_since_event", "reaction_lag_ms", "queue_ahead", "edge_taker",
] + MICRO
CATEGORICAL = ["category", "sport", "league", "side", "sports_market_type", "horizon"]


@dataclass
class FeatureSchema:
    """Vocabulario de categóricas fijado al entrenar; en vivo lo que no está en el vocabulario va a 'other'."""
    vocab: dict[str, list[str]] = field(default_factory=dict)
    numeric: list[str] = field(default_factory=lambda: list(NUMERIC))
    categorical: list[str] = field(default_factory=lambda: list(CATEGORICAL))

    @classmethod
    def from_rows(cls, rows: list[dict[str, Any]], max_levels: int = 20) -> "FeatureSchema":
        vocab: dict[str, list[str]] = {}
        for c in CATEGORICAL:
            counts: dict[str, int] = {}
            for r in rows:
                v = str(r.get(c) or "")
                if v:
                    counts[v] = counts.get(v, 0) + 1
            vocab[c] = [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:max_levels]]
        return cls(vocab=vocab)

    @property
    def names(self) -> list[str]:
        out = list(self.numeric)
        for c in self.categorical:
            out += [f"{c}={v}" for v in self.vocab.get(c, [])]
        return out

    def vector(self, f: dict[str, Any]) -> list[float]:
        x = []
        for n in self.numeric:
            v = f.get(n)
            try:
                v = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                v = 0.0
            x.append(0.0 if math.isnan(v) or math.isinf(v) else v)
        for c in self.categorical:
            val = str(f.get(c) or "")
            x += [1.0 if val == v else 0.0 for v in self.vocab.get(c, [])]
        return x

    def to_dict(self) -> dict[str, Any]:
        return {"vocab": self.vocab, "numeric": self.numeric, "categorical": self.categorical}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FeatureSchema":
        return cls(vocab=d.get("vocab", {}), numeric=d.get("numeric", list(NUMERIC)),
                   categorical=d.get("categorical", list(CATEGORICAL)))


_MICRO_SET = set(MICRO)


def _log1p(x: Any) -> float:
    try:
        return math.log1p(max(float(x), 0.0))
    except (TypeError, ValueError):
        return 0.0


def build_features(s: Signal, m: MarketInfo | None, ts_ms: int, book: OrderBook | None) -> dict[str, Any]:
    meta = s.meta
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    entry = meta.get("entry")
    if entry is None and s.legs:
        entry = sum(l.price for l in s.legs if l.side == "BUY") / max(sum(1 for l in s.legs if l.side == "BUY"), 1)
    p_model, p_market = meta.get("p_model"), meta.get("p_market")
    f: dict[str, Any] = {
        "edge_net": s.edge_net, "edge_gross": s.edge_gross, "fee_est": s.fee_est, "size": s.size,
        "conf_heuristic": s.confidence, "entry_price": entry or 0.0, "n_legs": len(s.legs),
        "spread_ticks": meta.get("spread_ticks", book.spread_ticks if book is not None and book.is_valid else 0),
        "tpm": meta.get("tpm", 0.0), "mid_vol": meta.get("mid_vol", 0.0),
        "imbalance": meta.get("imbalance", book.imbalance() if book is not None else 0.0),
        "bid_depth": _log1p(book.depth_within("BUY", 5)) if book is not None else 0.0,
        "ask_depth": _log1p(book.depth_within("SELL", 5)) if book is not None else 0.0,
        "fee_rate": m.fee_rate if m else 0.0, "tick_size": m.tick_size if m else 0.01,
        "volume_24h_log": _log1p(m.volume_24h) if m else 0.0,
        "p_model": p_model or 0.0, "p_market": p_market or 0.0,
        "deviation": (p_model - p_market) if (p_model is not None and p_market is not None) else 0.0,
        "tau": meta.get("tau", 0.0) or 0.0, "lead": meta.get("lead", 0) or 0,
        "pregame": meta.get("pregame") or 0.0, "has_pregame": 1.0 if meta.get("pregame") is not None else 0.0,
        "wallet_score": meta.get("wallet_score", 0.0) or 0.0, "wallet_n_log": _log1p(meta.get("wallet_n", 0)),
        "wallet_roi": meta.get("wallet_roi", 0.0) or 0.0, "their_usd_log": _log1p(meta.get("their_usd", 0)),
        "moneyness_bps": meta.get("moneyness_bps") or 0.0, "elapsed_s": meta.get("elapsed_s") or 0.0,
        "seconds_left": meta.get("seconds_left") or 0.0, "window_s": meta.get("window_s") or 0.0,
        "market_skew": meta.get("market_skew") or 0.0,
        "prev_up_won": 1.0 if meta.get("prev_up_won") else (0.0 if meta.get("prev_up_won") is False else 0.5),
        "prev_return_bps": meta.get("prev_return_bps") or 0.0,
        "event_risk_score": meta.get("event_risk_score") or 0.0,
        "ms_since_event": meta.get("ms_since_event") or 0.0,
        "reaction_lag_ms": meta.get("reaction_lag_ms") or 0.0,
        "queue_ahead": meta.get("queue_ahead") or 0.0,
        "edge_taker": meta.get("edge_taker") if meta.get("edge_taker") is not None else 0.0,
        **{k: v for k, v in (meta.get("micro") or {}).items() if k in _MICRO_SET},
        "hour_utc": dt.hour, "dow": dt.weekday(),
        "is_maker": 1.0 if any(l.role == "maker" for l in s.legs) else 0.0,
        "category": m.category if m else "", "sport": meta.get("sport", ""), "league": meta.get("league", ""),
        "side": meta.get("side", ""), "sports_market_type": m.sports_market_type if m else "", "horizon": s.horizon,
    }
    return f


def features_from_ledger_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Recupera las features guardadas en el ledger. None si la fila es anterior a esta versión."""
    try:
        meta = json.loads(row.get("meta") or "{}")
    except json.JSONDecodeError:
        return None
    f = meta.get("features")
    if not isinstance(f, dict):
        return None
    return f
