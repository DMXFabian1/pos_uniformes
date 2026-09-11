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
from ..micro import instantanea
from ..models.crypto import UpDownModel, UpDownState
from ..reaction import ReactionEngine
from ..signals import MarketContext, Signal, build_detectors
from ..signals.base import Leg, TokenHistory, strategy_id
from ..storage import ParquetWriter, dumps
from .fill_model import FillModel
from .ledger import Position, signal_row

DECISION_DEDUPE_MS = 30_000      # el mismo motivo de NO TRADE en el mismo mercado se anota como mucho cada 30 s

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, cfg: Config, run_id: str, mode: str, writer: ParquetWriter | None = None):
        self.cfg = cfg
        self.run_id = run_id
        self.mode = mode
        self.writer = writer
        self.detectors = build_detectors(cfg.signals, cfg.updown)
        self.fill_model = FillModel(cfg.sim.slippage_ticks, cfg.sim.fill_baseline_prob, cfg.sim.seed)
        self.reaction = ReactionEngine()
        self._ultima_decision: dict[tuple[str, str, str], int] = {}
        self._marcas: list[Position] = []          # posiciones con horizontes de selección adversa pendientes
        self._por_escribir: list[Position] = []    # cerradas que esperan a completar sus marcas antes de ir al ledger
        self.markets: dict[str, MarketInfo] = {}
        self.token_to_cid: dict[str, str] = {}
        self.event_index: dict[str, list[str]] = defaultdict(list)
        self.books: dict[str, OrderBook] = {}
        self.history: dict[str, TokenHistory] = defaultdict(TokenHistory)
        self.ultimo_mid: dict[str, float] = {}     # para valorar posiciones que quedan abiertas
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
        # arrastre: cómo terminó la ventana anterior del mismo símbolo (la "racha" que ve el mercado)
        self.prev_window: dict[str, dict[str, Any]] = {}
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
            self.on_book(event[1], event[2], event[3], event[4] if len(event) > 4 else None)
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
        mids = {t.token_id: (cid, self.books[t.token_id].mid) for cid in cids
                for t in self.markets[cid].tokens if t.token_id in self.books and self.books[t.token_id].is_valid}
        self.reaction.on_game(ts_ms, prev, g, {k: v for k, v in mids.items() if v[1] is not None})
        self._drenar_reacciones()
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
        w = self.updown.pop(condition_id, None)
        if w is not None and info.get("up_won") is not None:
            strike, cierre = w.get("strike"), info.get("settle_price")
            self.prev_window[w["symbol"]] = {
                "up_won": bool(info["up_won"]), "end_ms": w["end_ms"],
                "return_bps": round((cierre / strike - 1) * 10000, 3) if (strike and cierre) else None,
            }
        ganador = info.get("winner_token")
        for pos in [p for p in self.positions if p.status == "open" and p.signal.condition_id == condition_id]:
            if pos.entrada_maker is not None and pos.size_filled <= 0:
                self.stats["entradas_maker_sin_llenar"] += 1
                self._close(pos, ts_ms, "sin_llenar")     # la ventana cerró y nunca nos llenaron
                continue
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
        self._registrar_rechazos(ctx, ts_ms)

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

    def on_book(self, ts_ms: int, token_id: str, book: OrderBook, delta: dict[str, Any] | None = None) -> None:
        self.now_ms = max(self.now_ms, ts_ms)
        if delta is not None:
            self.history[token_id].flujo.append((ts_ms, delta.get("side", ""), float(delta.get("delta", 0.0))))
        if book.is_valid:
            self.history[token_id].mids.append((ts_ms, book.mid))
            self.ultimo_mid[token_id] = book.mid
            self.reaction.on_book(ts_ms, token_id, book.mid, book.tick_size)
        self._marcar_adversa(ts_ms, token_id)
        self._process_pending(ts_ms)
        for pos in list(self.positions):
            if pos.status != "open":
                continue
            self._revisar_entrada(pos, ts_ms, token_id, book=book)
            for o in pos.maker_orders:
                if o.token_id == token_id and self.fill_model.maker_on_book(o, book, ts_ms) > 0:
                    self._after_maker_fill(pos, ts_ms)
        self._caducar_entradas(ts_ms)
        self._expire(ts_ms)
        self._check_directional(ts_ms, token_id)
        self._escribir_cerradas(ts_ms)
        cid = self.token_to_cid.get(token_id)
        if cid:
            self._maybe_detect(cid, ts_ms)

    def on_trade(self, ts_ms: int, token_id: str, trade: dict[str, Any]) -> None:
        self.now_ms = max(self.now_ms, ts_ms)
        self.history[token_id].trades.append((ts_ms, trade["price"], trade["size"], trade["side"]))
        self._process_pending(ts_ms)
        for pos in list(self.positions):
            if pos.status != "open":
                continue
            self._revisar_entrada(pos, ts_ms, trade=trade)
            for o in pos.maker_orders:
                if self.fill_model.maker_on_trade(o, trade, ts_ms) > 0:
                    self._after_maker_fill(pos, ts_ms)
        self._caducar_entradas(ts_ms)
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
        self._marcar_adversa(ts_ms)
        self._process_pending(ts_ms)
        self._caducar_entradas(ts_ms)
        self._expire(ts_ms)
        self._check_directional(ts_ms)
        self.reaction.expirar(ts_ms)
        self._drenar_reacciones()
        self._escribir_cerradas(ts_ms)

    # ------------------------------------------------------------ reacción del mercado
    def _drenar_reacciones(self) -> None:
        rows = self.reaction.drenar()
        if not rows:
            return
        self.stats["reacciones"] += sum(1 for r in rows if r["reacciono"])
        self.stats["sin_reaccion"] += sum(1 for r in rows if not r["reacciono"])
        if self.writer is not None:
            for r in rows:
                self.writer.append("reactions", r)

    # ------------------------------------------------------------ selección adversa
    def _marcar_adversa(self, ts_ms: int, token_id: str | None = None) -> None:
        """Rellena mid - precio_entrada en cada horizonte tras el fill.

        El mid es un estado: en el instante ts_fill + h vale lo último que se observó antes de ese
        instante. Por eso, al llegar una actualización a `ts_ms`, los horizontes que vencieron
        estrictamente antes toman el mid previo; el que vence justo ahora toma el nuevo.
        """
        for pos in list(self._marcas):
            tid = pos.signal.legs[0].token_id
            if token_id is not None and tid != token_id:
                continue
            book = self.books.get(tid)
            mid_ahora = book.mid if (book is not None and book.is_valid) else self.ultimo_mid.get(tid)
            precio = pos.fills[0].avg_price if pos.fills else None
            for h in self.cfg.sim.adverse_horizons_ms:
                vence = pos.ts_fill + h
                if pos.adverse.get(h, "x") is not None or ts_ms < vence:
                    continue
                mid = mid_ahora if (token_id is not None and vence == ts_ms) else pos.mid_previo
                if token_id is None:                       # tick: el estado no cambió desde la última vez
                    mid = pos.mid_previo
                pos.adverse[h] = None if (mid is None or precio is None) else (mid - precio)
            if token_id is not None:
                pos.mid_previo = mid_ahora
            if all(pos.adverse.get(h, "x") is not None for h in self.cfg.sim.adverse_horizons_ms):
                self._marcas.remove(pos)

    def _iniciar_marcas(self, pos: Position, ts_ms: int) -> None:
        """Primer fill de una posición direccional: empieza a medir qué hace el precio después."""
        if pos in self._marcas or pos.signal.horizon not in ("directional", "resolution"):
            return
        tid = pos.signal.legs[0].token_id
        book = self.books.get(tid)
        pos.mid_previo = book.mid if (book is not None and book.is_valid) else self.ultimo_mid.get(tid)
        pos.adverse = {h: None for h in self.cfg.sim.adverse_horizons_ms}
        self._marcas.append(pos)

    def _escribir_cerradas(self, ts_ms: int, forzar: bool = False) -> None:
        """Las cerradas van al ledger cuando sus marcas están completas (o el plazo venció)."""
        if self.writer is None:
            self._por_escribir.clear()
            return
        tope = max(self.cfg.sim.adverse_horizons_ms, default=0)
        for pos in list(self._por_escribir):
            if forzar or pos not in self._marcas or ts_ms >= pos.ts_fill + tope:
                if pos in self._marcas:
                    self._marcas.remove(pos)
                self._por_escribir.remove(pos)
                self.writer.append("ledger", pos.to_row(self.run_id, self.mode))

    # ------------------------------------------------------------ decisiones (incluidas NO TRADE)
    def _decision(self, ts_ms: int, cid: str, kind: str, decision: str, motivo: str, edge_net: float | None = None,
                  detalle: dict[str, Any] | None = None, strategy: str = "") -> None:
        clave = (cid, kind, motivo)
        if decision == "no_trade":
            ultimo = self._ultima_decision.get(clave, -10**12)
            if ts_ms - ultimo < DECISION_DEDUPE_MS:
                return
            self._ultima_decision[clave] = ts_ms
            self.stats["no_trade"] += 1
            self.stats[f"no_trade_{motivo}"] += 1
        if self.writer is not None:
            m = self.markets.get(cid)
            self.writer.append("decisions", {
                "ts_ms": ts_ms, "run_id": self.run_id, "condition_id": cid, "kind": kind,
                "strategy": strategy or strategy_id(kind, detalle or {}, m.category if m else ""),
                "decision": decision, "motivo": motivo, "edge_net": edge_net, "detalle": dumps(detalle or {}),
            })

    def _registrar_rechazos(self, ctx: MarketContext, ts_ms: int) -> None:
        for r in ctx.rechazos:
            r = dict(r)
            kind, motivo = r.pop("kind"), r.pop("motivo")
            self._decision(ts_ms, ctx.market.condition_id, kind, "no_trade", motivo, r.get("edge_net"), r)
        ctx.rechazos.clear()

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
        self._registrar_rechazos(ctx, ts_ms)

    def _context(self, m: MarketInfo) -> MarketContext:
        books = {t.token_id: self.books[t.token_id] for t in m.tokens if t.token_id in self.books}
        sibs = [self.markets[c] for c in self.event_index.get(m.event_id, []) if c in self.markets]
        ebooks = {t.token_id: self.books[t.token_id] for s in sibs for t in s.tokens if t.token_id in self.books}
        g, wp, pre = self._model_for(m.condition_id)
        ud, p_up = self._updown_state(m.condition_id)
        reaccion = self.reaction.estado(g.game_id, g.league, self.now_ms) if g is not None else None
        return MarketContext(m, books, self.history, sibs, ebooks, game=g, model_prob=wp, pregame=pre,
                            outcome_side=self.outcome_side.get(m.condition_id, {}), wallets=self.wallets,
                            updown=ud, updown_prob=p_up,
                            prev_window=self.prev_window.get(ud.symbol) if ud is not None else None,
                            reaction=reaccion)

    def _on_signal(self, s: Signal) -> None:
        self.stats["signals"] += 1
        # la misma oportunidad se re-detecta cada detect_interval_ms mientras siga abierta:
        # no se registra ni se opera dos veces
        for p in self.positions:
            if p.signal.kind == s.kind and (p.signal.condition_id == s.condition_id or
                                             (s.kind.startswith("multi") and p.signal.event_id == s.event_id)):
                self.stats["skipped_duplicate"] += 1
                return
        # microestructura en el instante de la señal: forma del libro, flujo y velocidad del mid
        m0 = self.markets.get(s.condition_id)
        tok0 = s.legs[0].token_id if s.legs else ""
        book0 = self.books.get(tok0)
        s.meta["micro"] = instantanea(book0, self.history.get(tok0), s.ts_ms)
        # fase 5: puntuar con el modelo aprendido (si hay) y guardar las features para entrenar después
        res = self.scorer.score(s, m0, s.ts_ms, book0)
        s.meta["features"] = res.features
        s.meta["conf_heuristic"] = res.p_heuristic
        s.meta["p_win_model"] = res.p_model
        s.meta["model_version"] = res.version
        s.confidence = round(res.p_blend, 4)
        m_cat = m0.category if m0 else ""
        s.strategy = strategy_id(s.kind, s.meta, m_cat)
        if self.writer is not None:
            self.writer.append("signals", signal_row(s, self.run_id))
        if res.gate:
            self.stats["skipped_low_pwin"] += 1
            self._decision(s.ts_ms, s.condition_id, s.kind, "no_trade", "modelo_p_win_baja", s.edge_net,
                           {"p_win": res.p_blend}, s.strategy)
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
            self._decision(s.ts_ms, s.condition_id, s.kind, "no_trade", "edge_implausible", s.edge_net, {}, s.strategy)
            return
        # riesgo: tope de posiciones, tope de USD por posición, por mercado y por partido/evento
        if len(self.positions) >= self.cfg.sim.max_open_positions:
            self.stats["skipped_max_positions"] += 1
            self._decision(s.ts_ms, s.condition_id, s.kind, "no_trade", "tope_posiciones", s.edge_net, {}, s.strategy)
            return
        per_share = self._collateral_per_share(s)
        m = self.markets.get(s.condition_id)
        tope_usd = self.cfg.sim.max_position_usd
        exp_mercado = self._exposicion(lambda p: p.signal.condition_id == s.condition_id)
        exp_evento = self._exposicion(lambda p: p.signal.event_id == s.event_id and s.event_id)
        tope_usd = min(tope_usd, self.cfg.sim.max_market_exposure_usd - exp_mercado,
                       self.cfg.sim.max_game_exposure_usd - exp_evento)
        if tope_usd <= 0:
            self.stats["skipped_exposure"] += 1
            self._decision(s.ts_ms, s.condition_id, s.kind, "no_trade", "tope_exposicion", s.edge_net,
                           {"mercado_usd": round(exp_mercado, 2), "evento_usd": round(exp_evento, 2)}, s.strategy)
            return
        max_size = tope_usd / per_share if per_share > 0 else s.size
        if max_size < s.size:
            min_sz = m.min_order_size if m else 5
            if max_size < min_sz:
                self.stats["skipped_too_small"] += 1
                self._decision(s.ts_ms, s.condition_id, s.kind, "no_trade", "tamano_minimo", s.edge_net, {}, s.strategy)
                return
            scale = max_size / s.size
            s.size = max_size
            for l in s.legs:
                l.size *= scale
        if per_share * s.size > self.cash:
            self.stats["skipped_no_cash"] += 1
            self._decision(s.ts_ms, s.condition_id, s.kind, "no_trade", "sin_efectivo", s.edge_net, {}, s.strategy)
            return
        pos = Position(signal=s, exec_ts=s.ts_ms + self.cfg.sim.latency_ms)
        self.positions.append(pos)
        self.stats["positions"] += 1
        self._decision(s.ts_ms, s.condition_id, s.kind, "trade", "", s.edge_net,
                       {"size": round(s.size, 2), "entry_role": s.meta.get("entry_role", "taker")}, s.strategy)

    def _exposicion(self, cond) -> float:
        """Colateral comprometido (abierto o pendiente) en las posiciones que cumplen la condición."""
        total = 0.0
        for p in self.positions:
            if not cond(p):
                continue
            if p.status == "open" and p.size_filled > 0:
                total += p.collateral
            else:
                total += self._collateral_per_share(p.signal) * p.signal.size
        return total

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
            elif s.meta.get("entry_role") == "maker":
                self._poner_entrada(pos, ts_ms)
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
        self._iniciar_marcas(pos, ts_ms)
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

    def _poner_entrada(self, pos: Position, ts_ms: int) -> None:
        """Pone la orden de compra y espera. No cruza el libro, así que no paga comisión."""
        leg = pos.signal.legs[0]
        book = self.books.get(leg.token_id)
        if book is None or not book.is_valid:
            self._close(pos, ts_ms, "no_book")
            return
        if book.best_ask <= leg.price + 1e-9:
            # el mercado ya bajó hasta nuestro precio: la ventaja se evaporó mientras esperábamos
            self._close(pos, ts_ms, "price_moved")
            return
        pos.entrada_maker = pos.orden_entrada = self.fill_model.place_maker(leg, book, ts_ms)
        pos.status = "open"
        pos.ts_placed = ts_ms

    def _revisar_entrada(self, pos: Position, ts_ms: int, token_id: str | None = None,
                         trade: dict[str, Any] | None = None, book: OrderBook | None = None) -> None:
        """Intenta llenar la orden de entrada con el trade o el libro que acaba de llegar."""
        o = pos.entrada_maker
        if o is None or o.done:
            return
        if token_id is not None and o.token_id != token_id:
            return
        llenado = 0.0
        if trade is not None:
            llenado = self.fill_model.maker_on_trade(o, trade, ts_ms)
        elif book is not None:
            llenado = self.fill_model.maker_on_book(o, book, ts_ms)
        if llenado <= 0:
            return
        primero = pos.size_filled <= 0
        pos.fills.extend(f for f in o.fills if f not in pos.fills)
        pos.cost = sum(f.notional for f in o.fills)          # sin comisión: la orden se puso, no se cruzó
        pos.size_filled = o.filled
        pos.inventory[o.token_id] = o.filled
        if primero:
            pos.ts_fill = ts_ms
            self.stats["entradas_maker_llenadas"] += 1
            if o.barrido:
                self.stats["entradas_maker_barridas"] += 1
            self._iniciar_marcas(pos, ts_ms)
        if o.done:
            self.stats["entradas_maker_completas"] += 1

    def _caducar_entradas(self, ts_ms: int) -> None:
        """Orden puesta que no se llenó a tiempo: se cancela. No cuesta nada, solo no pasó nada."""
        limite = self.cfg.signals.maker_entry_timeout_s * 1000
        for pos in [p for p in self.positions if p.status == "open" and p.entrada_maker is not None]:
            o = pos.entrada_maker
            if o.done or ts_ms - o.ts_placed < limite:
                continue
            pos.entrada_maker = None
            if o.filled <= 0:
                self.stats["entradas_maker_sin_llenar"] += 1
                self._close(pos, ts_ms, "sin_llenar")

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
        """Salidas de una posición direccional, en este orden: target, stop, time stop, tope duro.

        El stop mira el mejor bid, que es a lo que de verdad se vendería, no el mid. El time stop es
        la regla de scalping: si el precio no convergió en el plazo, la tesis de desalineación ya no
        vale y se sale, gane o pierda. El tope duro solo actúa si el time stop no encontró libro.
        """
        time_stop = self.cfg.sim.time_stop_directional_seconds * 1000
        max_hold = self.cfg.sim.max_hold_directional_seconds * 1000
        for pos in [p for p in self.positions if p.status == "open" and p.signal.horizon == "directional"
                    and p.size_filled > 0]:
            tid = pos.signal.legs[0].token_id
            if token_id is not None and tid != token_id:
                continue
            book = self.books.get(tid)
            if book is None or not book.is_valid:
                continue
            target, stop = pos.signal.meta.get("target"), pos.signal.meta.get("stop")
            reason = None
            if target is not None and book.best_bid >= target - 1e-9:
                reason = "target"
            elif stop is not None and book.best_bid <= stop + 1e-9:
                reason = "stop"
            elif ts_ms - pos.ts_fill >= time_stop:
                reason = "time_stop"
            elif ts_ms - pos.ts_fill >= max_hold:
                reason = "max_hold"
            if reason is None:
                continue
            # si quedaba parte de la orden de entrada sin llenar, se cancela: no se añade más
            pos.entrada_maker = None
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
    def _valorar(self, token_id: str, comprado: bool) -> float:
        """A cuánto vale una posición que sigue abierta.

        Orden: el precio que se puede tocar ahora, el último precio medio visto, y solo si no hay
        nada de eso, el peor caso. Valorar a cero una posición viva es mentir sobre el resultado.
        """
        book = self.books.get(token_id)
        if book is not None:
            tocable = book.best_bid if comprado else book.best_ask
            if tocable is not None:
                return tocable
            if book.mid is not None:
                return book.mid
        ultimo = self.ultimo_mid.get(token_id)
        if ultimo is not None:
            return ultimo
        return 0.0 if comprado else 1.0

    def _close(self, pos: Position, ts_ms: int, reason: str) -> None:
        # Inventario que sigue abierto al cerrar los libros: se valora a mercado, no a cero.
        # El motivo lleva el sufijo _stuck y queda fuera de las estadísticas, porque no es el
        # resultado de la señal sino de haber cortado la corrida a mitad.
        stuck = {t: sh for t, sh in pos.inventory.items() if abs(sh) > 1e-9}
        if stuck:
            for tid, sh in stuck.items():
                px = self._valorar(tid, comprado=sh > 0)
                if sh > 0:
                    pos.payout += sh * px
                else:
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
            self._por_escribir.append(pos)
            self._escribir_cerradas(ts_ms)
        if reason not in ("unfilled", "expired_unfilled", "spread_gone", "no_book", "price_moved"):
            log.info("cierre %s %s size=%.1f pred=%.4f real=%.4f err=%.4f (%s)", pos.signal.kind,
                     pos.signal.condition_id[:10], pos.size_filled, pos.predicted_pnl, pos.realized_pnl,
                     pos.realized_pnl - pos.predicted_pnl, reason)

    def close_all(self, ts_ms: int, reason: str = "end") -> None:
        for pos in list(self.positions):
            if pos.status == "open" and pos.size_filled <= 0 and pos.entrada_maker is not None:
                self._close(pos, ts_ms, "sin_llenar")       # orden puesta que nunca se llenó: no pasó nada
                continue
            if pos.status == "open":
                self._unwind_inventory(pos, ts_ms)
            self._close(pos, ts_ms, reason if pos.status == "open" else "unfilled")
        self.reaction.expirar(ts_ms + self.reaction.ventana_ms)
        self._drenar_reacciones()
        self._escribir_cerradas(ts_ms, forzar=True)

    def summary(self) -> dict[str, Any]:
        closed = [p for p in self.closed if p.size_filled > 0]
        return {
            "run_id": self.run_id, "mode": self.mode, "cash": round(self.cash, 4),
            "pnl": round(self.cash - self.cfg.sim.start_cash, 4), "positions_closed": len(self.closed),
            "positions_filled": len(closed), "open": len(self.positions), **dict(self.stats),
        }
