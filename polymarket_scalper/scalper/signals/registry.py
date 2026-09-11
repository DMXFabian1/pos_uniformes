from __future__ import annotations

from ..config import SignalsCfg, UpDownCfg
from .base import Detector
from .complement import ComplementDetector
from .model_deviation import ModelDeviationDetector
from .multi_outcome import MultiOutcomeDetector
from .smart_money import SmartMoneyDetector
from .spread import SpreadCaptureDetector
from .updown import UpDownDetector


def build_detectors(cfg: SignalsCfg, updown: UpDownCfg | None = None) -> list[Detector]:
    dets: list[Detector] = []
    if cfg.complement.enabled:
        dets.append(ComplementDetector(cfg.min_edge_net, cfg.target_size))
    if cfg.multi_outcome.enabled:
        dets.append(MultiOutcomeDetector(cfg.min_edge_net, cfg.target_size, cfg.multi_outcome.max_legs))
    if cfg.spread.enabled:
        s = cfg.spread
        dets.append(SpreadCaptureDetector(cfg.min_edge_net, cfg.target_size, s.min_spread_ticks,
                                          s.min_trades_per_minute, s.trade_window_seconds, s.vol_window_seconds,
                                          s.max_spread_ticks))
    if cfg.model_deviation.enabled:
        d = cfg.model_deviation
        dets.append(ModelDeviationDetector(d.min_edge_net, cfg.target_size, d.min_deviation, d.max_deviation,
                                           d.stop_fraction, d.min_tau, d.require_pregame))
    if cfg.smart_money.enabled:
        d = cfg.smart_money
        dets.append(SmartMoneyDetector(d.min_edge_net, cfg.target_size, d.min_score, d.min_closed, d.min_usd,
                                       d.max_chase_ticks, d.edge_fraction_of_roi, d.max_price))
    if updown is not None and updown.enabled:
        dets.append(UpDownDetector(updown.min_edge_net, cfg.target_size, updown.min_seconds_left, updown.max_edge_net))
    return dets
