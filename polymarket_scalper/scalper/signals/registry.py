from __future__ import annotations

from ..config import SignalsCfg
from .base import Detector
from .complement import ComplementDetector
from .multi_outcome import MultiOutcomeDetector
from .spread import SpreadCaptureDetector


def build_detectors(cfg: SignalsCfg) -> list[Detector]:
    dets: list[Detector] = []
    if cfg.complement.enabled:
        dets.append(ComplementDetector(cfg.min_edge_net, cfg.target_size))
    if cfg.multi_outcome.enabled:
        dets.append(MultiOutcomeDetector(cfg.min_edge_net, cfg.target_size, cfg.multi_outcome.max_legs))
    if cfg.spread.enabled:
        s = cfg.spread
        dets.append(SpreadCaptureDetector(cfg.min_edge_net, cfg.target_size, s.min_spread_ticks,
                                          s.min_trades_per_minute, s.trade_window_seconds, s.vol_window_seconds))
    return dets
