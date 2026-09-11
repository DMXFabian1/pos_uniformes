"""Motor común de replay y paper trading.

Recibe eventos de mercado (book, delta, trade, resolution), corre los detectores, simula
ejecución con latencia/slippage/fees y cierra posiciones, registrando cada una en el ledger
con su ganancia predicha y la realizada. Ese error es lo que la fase 4 aprenderá a reducir.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from ..book import OrderBook
from ..config import Config
from ..discovery import MarketInfo
from ..learn import ModelStore, Scorer
from ..models import GameState, ModelRegistry, WinProb, match_outcome, parse_game
from ..models.crypto import UpDownModel, UpDownState
from ..signals import MarketContext, Signal, build_detectors
from ..signals.base import Leg, TokenHistory
from ..storage import ParquetWriter
from .fill_model import FillModel
from .ledger import Position, signal_row

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, cfg: Config, run_id: str, mode: str, writer: ParquetWriter | None = None):
        self.cfg = cfg
        self.run_id = run_id
        self.mode = mode
        self.writer = writer
        self.detectors = build_detectors(cfg.signals, cfg.updown)
        self.fill_model = FillModel(cfg.sim.slippage_ticks, cfg.sim.maker_fill_prob, cfg.sim.seed)
        self.markets: dict[str, MarketInfo] = {}
        self.token_to_cid: dict[str, str] = {}
        self.event_index: dict[str, list[str]] = defaultdict(list)
        self.books: dict[str, OrderBook] = {}
        self.history: dict[str, TokenHistory] = defaultdict(TokenHistory)
        self.positions: list[Position] = []
        self.closed: list[Position] = []
        self.cash = cfg.sim.start_cash
        self.last_detect: dict[str, int] = {}
        self.stats: dict[str, int] = defaultdict(int)
        self.now_ms = 0
        # in-play
        self.models = ModelRegistry(cfg.models.sigma_basketball, cfg.models.sigma_by_league, cfg.models.soccer_total_goals)
        self.games: dict[str, GameState] = {}                 # game_id -> último estado
        self.game_to_cids: dict[str, list[str]] = defaultdict(list)
        self.pregame: dict[str, WinProb] = {}                 # game_id -> prob previa (del mercado)
        self.outcome_side: dict[str, dict[str, str]] = {}    # cid -> token -> home|away|draw
        self.wallets: dict[str, Any] = {}                     # wallet -> WalletProfile
        # "Up or Down": ventana por mercado y último precio de referencia por símbolo
        self.updown_model = UpDownModel(cfg.updown.annual_vol, cfg.updown.default_annual_vol)
        self.updown: dict[str, dict[str, Any]] = {}
        self.spot: dict[str, tuple[int, float]] = {}
        lc = cfg.learn
        self.scorer = Scorer(ModelStore(cfg.data_dir), lc.shrink_n, lc.min_train, lc.min_p_win, lc.size_floor, lc.enabled)

    # ------------------------------------------------------------ mercados
    def set_markets(self, markets: list[MarketInfo]) -> None:
        self.markets = {m.condition_id: m for m in markets}
        self.token_to_cid = {t.token_id: m.condition_id for m in markets for t in m.tokens}
        self.event_index = defaultdict(list)
        for m in markets:
            self.event_index[m.event_id].append(m.condition_id)
        self.game_to_cids = defaultdict(list)
        for m in markets:
            if m.event_game_id:
                self.game_to_cids[m.event_game_id].append(m.condition_id)
        for m in markets:
            for t in m.tokens:
                b = self.books.get(t.token_id)
                if b is None:
                    self.books[t.token_id] = OrderBook(t.token_id, m.condition_id, m.tick_size)
                else:
                    b.tick_size = m.tick_size

    def attach_wallets(self, profiles: dict[str, Any]) -> None:
        """Comparte el diccionario de perfiles del WalletTracker (paper) o uno cargado (replay)."""
        self.wallets = profiles

    def attach_books(self, books: dict[str, OrderBook]) -> None:
        """Comparte los libros del recolector (paper trading) en vez de mantener copias."""
        self.books = books

    # ------------------------------------------------------------ eventos
    async def on_event(self, event: tuple) -> None:
        """Listener compatible con Collector.add_listener."""
        kind = event[0]
        if kind == "markets":
            self.set_markets(event[2])
        elif kind == "book" or kind == "delta":
            self.on_book(event[1], event[2], event[3])
        elif kind == "trade":
            self.on_trade(event[1], event[2], event[3])
        elif kind == "resolution":
            self.on_resolution(event[1], event[2], event[3])
        elif kind == "game":
            self.on_game(event[1], event[2], event[3])
        elif kind == "flow":
            self.on_flow(event[1], event[2], event[3])
        elif kind == "price":
            self.on_price(event[1], event[2], event[3])
        elif kind == "updown":
            self.on_updown(event[1], event[2], event[3])
        elif kind == "updown_settle":
            self.on_updown_settle(event[1], event[2], event[3])

    def on_game(self, ts_ms: int, game_id: str, row: dict[str, Any]) -> None:
        self.now_ms = max(self.now_ms, ts_ms)
        g = parse_game({**row, "ts_ms": ts_ms})
        prev = self.games.get(game_id)
        self.games[game_id] = g
        cids = self.game_to_cids.get(game_id, [])
        if not cids:
            return
        for cid in cids:
            self._ensure_sides(cid, g)
        if not g.live and not g.ended:
            self._capture_pregame(game_id, cids)
        elif g.live and game_id not in self.pregame and prev is not None and not prev.live:
            self._capture_pregame(game_id, cids)          # último precio antes de arrancar
        if g.ended:
            self._settle_game(ts_ms, game_id, g, cids)
            return
        self._process_pending(ts_ms)
        self._check_directional(ts_ms)
        for cid in cids:
            self.last_detect.pop(cid, None)              # un cambio de marcador siempre se evalúa
            self._maybe_detect(cid, ts_ms)

    # ------------------------------------------------------------ "Up or Down"
    def on_price(self, ts_ms: int, symbol: str, row: dict[str, Any]) -> None:
        self.now_ms = max(self.now_ms, ts_ms)
        self.spot[symbol] = (ts_ms, float(row["price"]))
        self._process_pending(ts_ms)
        for cid, w in list(self.updown.items()):
            if w["symbol"] == symbol and ts_ms < w["end_ms"]:
                self._maybe_detect(cid, ts_ms)

    def on_updown(self, ts_ms: int, condition_id: str, info: dict[str, Any]) -> None:
        self.now_ms = max(self.now_ms, ts_ms)
        mi = info.get("market")
        if mi is not None and condition_id not in self.markets:
            self.markets[condition_id] = mi
            for t in mi.tokens:
                self.token_to_cid[t.token_id] = condition_id
                self.books.setdefault(t.token_id, OrderBook(t.token_id, condition_id, mi.tick_size))
        self.updown[condition_id] = {k: info[k] for k in ("strike", "symbol", "start_ms", "end_ms", "window_s")}
        self._maybe_detect(condition_id, ts_ms)

    def on_updown_settle(self, ts_ms: int, condition_id: str, info: dict[str, Any]) -> None:
        """La ventana venció: las posiciones abiertas cobran 1 por share del lado ganador."""
        self.now_ms = max(self.now_ms, ts_ms)
        self.updown.pop(condition_id, None)
        ganador = info.get("winner_token")
        for pos in [p for p in self.positions if p.status == "open" and p.signal.condition_id == condition_id]:
            pago = sum(sh for t, sh in pos.inventory.items() if t == ganador and sh > 0)
            pos.payout += pago
            pos.inventory = {}
            self._close(pos, ts_ms, "updown_settle")

    def _updown_state(self, cid: str) -> tuple[UpDownState | None, float | None]:
        w = self.updown.get(cid)
        if w is None or not w.get("strike"):
            return None, None
        spot = self.spot.get(w["symbol"])
        if spot is None:
            return None, None
        st = UpDownState(symbol=w["symbol"], strike=float(w["strike"]), spot=spot[1],
                         seconds_left=max(0.0, (w["end_ms"] - max(self.now_ms, spot[0])) / 1000),
                         window_seconds=float(w["window_s"]), spot_ts_ms=spot[0])
        try:
            return st, self.updown_model.prob_up(st)
        except Exception:  # noqa: BLE001
            log.exception("modelo up/down falló en %s", cid[:10])
            return st, None

    def on_flow(self, ts_ms: int, condition_id: str, flow: dict[str, Any]) -> None:
        self.now_ms = max(self.now_ms, ts_ms)
        m = self.markets.get(condition_id)
        if m is None:
            return
        ctx = self._context(m)
        for det in self.detectors:
            fn = getattr(det, "on_flow", None)
            if fn is None:
                continue
            try:
                for sig in fn(ctx, flow, ts_ms):
                    self._on_signal(sig)
            except Exception:  # noqa: BLE001
                log.exception("detector %s falló en flow", det.kind)

    def _ensure_sides(self, cid: str, g: GameState) -> None:
        if cid in self.outcome_side:
            return
        m = self.markets.get(cid)
        if m is None:
            return
        sides: dict[str, str] = {}
        for t in m.tokens:
            side = match_outcome(t.outcome, g.home, g.away, m.question)
            if side is None and m.is_binary and t.outcome.lower() == "no":
                other = match_outcome(m.tokens[0].outcome, g.home, g.away, m.question)
                if other in ("home", "away") and not (m.event_neg_risk and len(self.event_index.get(m.event_id, [])) > 2):
                    side = "away" if other == "home" else "home"
            if side is not None:
                sides[t.token_id] = side
        self.outcome_side[cid] = sides

    def _market_probs(self, cids: list[str]) -> WinProb | None:
        """Prob. implícita por lado a partir de los mids de los mercados enlazados al partido."""
        acc: dict[str, list[float]] = defaultdict(list)
        for cid in cids:
            m = self.markets.get(cid)
            if m is None or (m.sports_market_type and m.sports_market_type not in ("moneyline", "child_moneyline")):
                continue
            for tid, side in self.outcome_side.get(cid, {}).items():
                b = self.books.get(tid)
                if b is not None and b.is_valid:
                    acc[side].append(b.mid)
        if "home" not in acc or "away" not in acc:
            return None
        ph = sum(acc["home"]) / len(acc["home"])
        pa = sum(acc["away"]) / len(acc["away"])
        pd = sum(acc["draw"]) / len(acc["draw"]) if acc.get("draw") else 0.0
        tot = ph + pa + pd
        if tot <= 0:
            return None
        return WinProb(home=ph / tot, away=pa / tot, draw=pd / tot, model="market")

    def _capture_pregame(self, game_id: str, cids: list[str]) -> None:
        wp = self._market_probs(cids)
        if wp is not None:
            self.pregame[game_id] = wp

    def _model_for(self, cid: str) -> tuple[GameState | None, WinProb | None, WinProb | None]:
        m = self.markets.get(cid)
        if m is None or not m.event_game_id:
            return None, None, None
        g = self.games.get(m.event_game_id)
        if g is None:
            return None, None, None
        pre = self.pregame.get(m.event_game_id)
        if pre is None and g.live:
            # sin precio previo: solo se acepta el mercado actual como proxy si el partido recién empieza
            model = self.models.get(g.sport)
            tau = getattr(model, "remaining_fraction", lambda _g: None)(g) if model else None
            early = (tau is not None and tau >= 1 - self.cfg.models.pregame_proxy_max_progress) or                     (g.sport == "tennis" and g.extra.get("sets_home", 0) + g.extra.get("sets_away", 0) == 0
                     and g.extra.get("games_home", 0) + g.extra.get("games_away", 0) <= 2)
            if early:
                self._capture_pregame(m.event_game_id, self.game_to_cids.get(m.event_game_id, []))
                pre = self.pregame.get(m.event_game_id)
            if pre is None:
                return g, None, None
        try:
            wp = self.models.prob(g, pre)
        except Exception:  # noqa: BLE001
            log.exception("modelo falló para %s", g.game_id)
            wp = None
        return g, wp, pre

    def _settle_game(self, ts_ms: int, game_id: str, g: GameState, cids: list[str]) -> None:
        """Partido terminado: liquida posiciones direccionales con el marcador final."""
        if g.home_score == g.away_score and g.sport != "tennis":
            winner = "draw"
        else:
            winner = "home" if g.home_score > g.away_score else "away"
        for pos in list(self.positions):
            if pos.status != "open" or pos.signal.condition_id not in cids:
                continue
            sides = self.outcome_side.get(pos.signal.condition_id, {})
            payout = 0.0
            for tid, sh in pos.inventory.items():
                side = sides.get(tid)
                if side is None:
                    continue
                payout += sh * (1.0 if side == winner else 0.0)
            pos.payout += payout
            pos.inventory = {t: s for t, s in pos.inventory.items() if sides.get(t) is None}
            self._close(pos, ts_ms, "game_end")

    def on_book(self, ts_ms: int, token_id: str, book: OrderBook) -> None:
        self.now_ms = max(self.now_ms, ts_ms)
        if book.is_valid:
            self.history[token_id].mids.append((ts_ms, book.mid))
        self._process_pending(ts_ms)
        for pos in self.positions:
            if pos.status == "open" and pos.maker_orders:
                for o in pos.maker_orders:
                    if o.token_id == token_id and self.fill_model.maker_on_book(o, book, ts_ms) > 0:
                        self._after_maker_fill(pos, ts_ms)
        self._expire(ts_ms)
        self._check_directional(ts_ms, token_id)
        cid = self.token_to_cid.get(token_id)
        if cid:
            self._maybe_detect(cid, ts_ms)

    def on_trade(self, ts_ms: int, token_id: str, trade: dict[str, Any]) -> None:
        self.now_ms = max(self.now_ms, ts_ms)
        self.history[token_id].trades.append((ts_ms, trade["price"], trade["size"], trade["side"]))
        self._process_pending(ts_ms)
        for pos in self.positions:
            if pos.status == "open" and pos.maker_orders:
                for o in pos.maker_orders:
                    if self.fill_model.maker_on_trade(o, trade, ts_ms) > 0:
                        self._after_maker_fill(pos, ts_ms)
        self._expire(ts_ms)
        cid = self.token_to_cid.get(token_id)
        if cid:
            self._maybe_detect(cid, ts_ms)

    def on_resolution(self, ts_ms: int, condition_id: str, data: dict[str, Any]) -> None:
        winners = {t["token_id"]: bool(t["winner"]) for t in data.get("tokens", [])}
        for pos in list(self.positions):
            if pos.status != "open":
                continue
            if not any(t in winners for t in pos.inventory):
                continue
            payout = sum(sh * (1.0 if winners.get(t) else 0.0) for t, sh in pos.inventory.items() if sh > 0)
            pos.payout += payout
            pos.inventory = {}
            self._close(pos, ts_ms, "resolution")

    def tick(self, ts_ms: int) -> None:
        """Llamar periódicamente aunque no lleguen eventos (latencia y expiraciones)."""
        self.now_ms = max(self.now_ms, ts_ms)
        self._process_pending(ts_ms)
        self._expire(ts_ms)
        self._check_directional(ts_ms)

    # ------------------------------------------------------------ detección
    def _maybe_detect(self, cid: str, ts_ms: int) -> None:
        last = self.last_detect.get(cid, 0)
        if ts_ms - last < self.cfg.signals.detect_interval_ms:
            return
        self.last_detect[cid] = ts_ms
        m = self.markets.get(cid)
        if m is None:
            return
        ctx = self._context(m)
        for det in self.detectors:
            try:
                signals = det.detect(ctx, ts_ms)
            except Exception:  # noqa: BLE001
                log.exception("detector %s falló en %s", det.kind, cid[:10])
                continue
            for s in signals:
                self._on_signal(s)

    def _context(self, m: MarketInfo) -> MarketContext:
        books = {t.token_id: self.books[t.token_id] for t in m.tokens if t.token_id in self.books}
        sibs = [self.markets[c] for c in self.event_index.get(m.event_id, []) if c in self.markets]
        ebooks = {t.token_id: self.books[t.token_id] for s in sibs for t in s.tokens if t.token_id in self.books}
        g, wp, pre = self._model_for(m.condition_id)
        ud, p_up = self._updown_state(m.condition_id)
        return MarketContext(m, books, self.history, sibs, ebooks, game=g, model_prob=wp, pregame=pre,
                            outcome_side=self.outcome_side.get(m.condition_id, {}), wallets=self.wallets,
                            updown=ud, updown_prob=p_up)

    def _on_signal(self, s: Signal) -> None:
        self.stats["signals"] += 1
        # la misma oportunidad se re-detecta cada detect_interval_ms mientras siga abierta:
        # no se registra ni se opera dos veces
        for p in self.positions:
            if p.signal.kind == s.kind and (p.signal.condition_id == s.condition_id or
                                             (s.kind.startswith("multi") and p.signal.event_id == s.event_id)):
                self.stats["skipped_duplicate"] += 1
                return
        # fase 5: puntuar con el modelo aprendido (si hay) y guardar las features para entrenar después
        m0 = self.markets.get(s.condition_id)
        book0 = self.books.get(s.legs[0].token_id) if s.legs else None
        res = self.scorer.score(s, m0, s.ts_ms, book0)
        s.meta["features"] = res.features
        s.meta["conf_heuristic"] = res.p_heuristic
        s.meta["p_win_model"] = res.p_model
        s.meta["model_version"] = res.version
        s.confidence = round(res.p_blend, 4)
        if self.writer is not None:
            self.writer.append("signals", signal_row(s, self.run_id))
        if res.gate:
            self.stats["skipped_low_pwin"] += 1
            return
        if res.size_mult < 1.0:
            s.size *= res.size_mult
            for l in s.legs:
                l.size *= res.size_mult
            self.stats["sized_down"] += 1
        # el tope de plausibilidad es para arbitrajes (un libro roto parece dinero gratis); las señales
        # direccionales tienen su propio tope de desvío en el detector
        if s.horizon != "directional" and s.edge_net > self.cfg.signals.max_edge_net:
            self.stats["skipped_implausible"] += 1
            return
        # riesgo: tope de posiciones, tope de USD por posición
        if len(self.positions) >= self.cfg.sim.max_open_positions:
            self.stats["skipped_max_positions"] += 1
            return
        per_share = self._collateral_per_share(s)
        max_size = self.cfg.sim.max_position_usd / per_share if per_share > 0 else s.size
        if max_size < s.size:
            m = self.markets.get(s.condition_id)
            min_sz = m.min_order_size if m else 5
            if max_size < min_sz:
                self.stats["skipped_too_small"] += 1
                return
            scale = max_size / s.size
            s.size = max_size
            for l in s.legs:
                l.size *= scale
        if per_share * s.size > self.cash:
            self.stats["skipped_no_cash"] += 1
            return
        pos = Position(signal=s, exec_ts=s.ts_ms + self.cfg.sim.latency_ms)
        self.positions.append(pos)
        self.stats["positions"] += 1

    @staticmethod
    def _collateral_per_share(s: Signal) -> float:
        if s.kind == "spread_capture":
            bid = next((l.price for l in s.legs if l.side == "BUY"), 0.0)
            ask = next((l.price for l in s.legs if l.side == "SELL"), 1.0)
            return bid + (1 - ask)
        if s.kind == "complement_sell":
            return 1.0
        return sum(l.price for l in s.legs if l.side == "BUY")

    # ------------------------------------------------------------ ejecución
    def _process_pending(self, ts_ms: int) -> None:
        for pos in [p for p in self.positions if p.status == "pending" and ts_ms >= p.exec_ts]:
            s = pos.signal
            if s.kind == "spread_capture":
                self._place_makers(pos, ts_ms)
            else:
                self._execute_taker(pos, ts_ms)

    def _execute_taker(self, pos: Position, ts_ms: int) -> None:
        s = pos.signal
        m = self.markets.get(s.condition_id)
        if s.horizon == "directional":
            leg = s.legs[0]
            book = self.books.get(leg.token_id)
            if book is None or not book.is_valid:
                self._close(pos, ts_ms, "no_book")
                return
            if book.best_ask > leg.price + self.cfg.sim.max_entry_slip_ticks * book.tick_size + 1e-9:
                self._close(pos, ts_ms, "price_moved")
                return
        fills = []
        for leg in s.legs:
            book = self.books.get(leg.token_id)
            lm = self.markets.get(self.token_to_cid.get(leg.token_id, ""), m)
            rate = lm.fee_rate if lm else 0.0
            if book is None or not book.is_valid:
                fills.append(None)
                continue
            fills.append(self.fill_model.fill_taker(leg, book, rate, ts_ms))
        got = min((f.shares for f in fills if f is not None), default=0.0)
        if any(f is None for f in fills):
            got = 0.0
        pos.ts_fill = ts_ms
        pos.size_filled = got
        # patas llenadas de más se deshacen contra el mismo libro (costo real de un arb roto)
        for leg, f in zip(s.legs, fills):
            if f is None:
                continue
            keep = min(f.shares, got)
            if keep > 0:
                scaled = f.notional * keep / f.shares
                fee = f.fee * keep / f.shares
                pos.fills.append(type(f)(f.token_id, f.side, keep, f.avg_price, scaled, fee, ts_ms, "taker"))
                if leg.side == "BUY":
                    pos.cost += scaled
                    pos.inventory[leg.token_id] = pos.inventory.get(leg.token_id, 0) + keep
                else:
                    pos.payout += scaled
                    pos.inventory[leg.token_id] = pos.inventory.get(leg.token_id, 0) - keep
                pos.fees += fee
            excess = f.shares - keep
            if excess > 0:
                book = self.books[leg.token_id]
                rate = self.markets[self.token_to_cid[leg.token_id]].fee_rate
                undo_leg = type(leg)(leg.token_id, "SELL" if leg.side == "BUY" else "BUY", 0.0, excess, "taker")
                u = self.fill_model.fill_taker(undo_leg, book, rate, ts_ms)
                # costo de deshacer = (lo que pagamos por el exceso) - (lo que recuperamos), ambos con fee
                paid = f.notional * excess / f.shares + f.fee * excess / f.shares
                self._adjust_unwind(pos, leg.side, paid, u.notional, u.fee)
        if got <= 0:
            self._close(pos, ts_ms, "unfilled")
            return
        pos.status = "open"
        if s.kind == "complement_buy":
            pos.payout += got                       # merge SÍ+NO -> 1 USD por share
            pos.inventory = {}
            self._close(pos, ts_ms, "merge")
        elif s.kind == "complement_sell":
            pos.cost += got                         # colateral usado para mint
            pos.inventory = {}
            self._close(pos, ts_ms, "mint")
        elif s.kind == "multi_buy_all_yes":
            pos.payout += got                       # exactamente un SÍ paga 1
            pos.inventory = {}
            self._close(pos, ts_ms, "guaranteed")
        elif s.kind == "multi_buy_all_no":
            pos.payout += got * (s.meta.get("n", len(s.legs)) - 1)
            pos.inventory = {}
            self._close(pos, ts_ms, "guaranteed")
        # horizon "directional": sale por target/stop/tiempo/fin de partido
        # horizon "resolution" (up/down): queda abierta hasta la liquidación; vender antes
        # pagaría la comisión de cripto por segunda vez

    @staticmethod
    def _adjust_unwind(pos: Position, side: str, paid_or_received: float, undo_notional: float, undo_fee: float) -> None:
        if side == "BUY":
            pos.cost += paid_or_received
            pos.payout += undo_notional
        else:
            pos.payout += paid_or_received
            pos.cost += undo_notional
        pos.fees += undo_fee

    def _place_makers(self, pos: Position, ts_ms: int) -> None:
        s = pos.signal
        book = self.books.get(s.legs[0].token_id)
        if book is None or not book.is_valid:
            self._close(pos, ts_ms, "no_book")
            return
        # si el spread ya se cerró, no hay nada que capturar
        if book.best_ask - book.best_bid < 2 * book.tick_size - 1e-9:
            self._close(pos, ts_ms, "spread_gone")
            return
        pos.maker_orders = [self.fill_model.place_maker(l, book, ts_ms) for l in s.legs]
        pos.status = "open"
        pos.ts_fill = ts_ms

    def _after_maker_fill(self, pos: Position, ts_ms: int) -> None:
        # sincroniza fills e inventario con las órdenes maker
        pos.fills = [f for o in pos.maker_orders for f in o.fills]
        inv: dict[str, float] = {}
        cost = payout = 0.0
        for o in pos.maker_orders:
            for f in o.fills:
                if o.side == "BUY":
                    cost += f.notional
                    inv[o.token_id] = inv.get(o.token_id, 0) + f.shares
                else:
                    payout += f.notional
                    inv[o.token_id] = inv.get(o.token_id, 0) - f.shares
        pos.cost, pos.payout, pos.inventory = cost, payout, inv
        pos.size_filled = max(o.filled for o in pos.maker_orders)
        if all(o.done for o in pos.maker_orders):
            pos.inventory = {}
            self._close(pos, ts_ms, "both_filled")

    def _check_directional(self, ts_ms: int, token_id: str | None = None) -> None:
        max_hold = self.cfg.sim.max_hold_directional_seconds * 1000
        for pos in [p for p in self.positions if p.status == "open" and p.signal.horizon == "directional"]:
            tid = pos.signal.legs[0].token_id
            if token_id is not None and tid != token_id:
                continue
            book = self.books.get(tid)
            if book is None or not book.is_valid:
                continue
            mid = book.mid
            target, stop = pos.signal.meta.get("target"), pos.signal.meta.get("stop")
            reason = None
            if target is not None and book.best_bid >= target - 1e-9:
                reason = "target"
            elif stop is not None and mid <= stop + 1e-9:
                reason = "stop"
            elif ts_ms - pos.ts_fill >= max_hold:
                reason = "max_hold"
            if reason is None:
                continue
            self._unwind_inventory(pos, ts_ms)
            self._close(pos, ts_ms, reason)

    def _expire(self, ts_ms: int) -> None:
        max_hold = self.cfg.sim.max_hold_seconds * 1000
        for pos in [p for p in self.positions if p.status == "open" and p.maker_orders]:
            if ts_ms - pos.ts_fill < max_hold:
                continue
            self._unwind_inventory(pos, ts_ms)
            self._close(pos, ts_ms, "expired" if pos.size_filled > 0 or pos.fills else "expired_unfilled")

    def _unwind_inventory(self, pos: Position, ts_ms: int) -> None:
        for tid, sh in list(pos.inventory.items()):
            if abs(sh) < 1e-9:
                continue
            book = self.books.get(tid)
            if book is None or not book.is_valid:
                continue
            rate = self.markets[self.token_to_cid[tid]].fee_rate
            leg = Leg(tid, "SELL" if sh > 0 else "BUY", 0.0, abs(sh), "taker")
            f = self.fill_model.fill_taker(leg, book, rate, ts_ms)
            pos.fills.append(f)
            if sh > 0:
                pos.payout += f.notional
                left = sh - f.shares
            else:
                pos.cost += f.notional
                left = sh + f.shares
            pos.fees += f.fee
            pos.inventory[tid] = left
        pos.inventory = {t: s for t, s in pos.inventory.items() if abs(s) > 1e-9}

    # ------------------------------------------------------------ cierre
    def _close(self, pos: Position, ts_ms: int, reason: str) -> None:
        # inventario que no se pudo deshacer: se valora al peor caso razonable, nunca como ganancia
        stuck = {t: sh for t, sh in pos.inventory.items() if abs(sh) > 1e-9}
        if stuck:
            for tid, sh in stuck.items():
                book = self.books.get(tid)
                if sh > 0:
                    px = book.best_bid if book is not None and book.best_bid is not None else 0.0
                    pos.payout += sh * px
                else:
                    px = book.best_ask if book is not None and book.best_ask is not None else 1.0
                    pos.cost += -sh * px
            pos.inventory = {}
            reason = f"{reason}_stuck"
        pos.status = "closed"
        pos.ts_exit = ts_ms
        pos.exit_reason = reason
        pos.realized_pnl = pos.payout - pos.cost - pos.fees
        self.cash += pos.realized_pnl
        if pos in self.positions:
            self.positions.remove(pos)
        self.closed.append(pos)
        self.stats[f"closed_{reason}"] += 1
        if self.writer is not None:
            self.writer.append("ledger", pos.to_row(self.run_id, self.mode))
        if reason not in ("unfilled", "expired_unfilled", "spread_gone", "no_book", "price_moved"):
            log.info("cierre %s %s size=%.1f pred=%.4f real=%.4f err=%.4f (%s)", pos.signal.kind,
                     pos.signal.condition_id[:10], pos.size_filled, pos.predicted_pnl, pos.realized_pnl,
                     pos.realized_pnl - pos.predicted_pnl, reason)

    def close_all(self, ts_ms: int, reason: str = "end") -> None:
        for pos in list(self.positions):
            if pos.status == "open":
                self._unwind_inventory(pos, ts_ms)
            self._close(pos, ts_ms, reason if pos.status == "open" else "unfilled")

    def summary(self) -> dict[str, Any]:
        closed = [p for p in self.closed if p.size_filled > 0]
        return {
            "run_id": self.run_id, "mode": self.mode, "cash": round(self.cash, 4),
            "pnl": round(self.cash - self.cfg.sim.start_cash, 4), "positions_closed": len(self.closed),
            "positions_filled": len(closed), "open": len(self.positions), **dict(self.stats),
        }
