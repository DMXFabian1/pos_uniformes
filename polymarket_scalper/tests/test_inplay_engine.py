from scalper.sim.engine import Engine
from scalper.wallets import WalletProfile
from conftest import make_market


def _engine(cfg, markets, maker_first=False):
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    cfg.signals.spread.enabled = False
    cfg.signals.complement.enabled = False
    cfg.signals.maker_first = maker_first        # estos casos verifican la ruta que cruza el libro
    eng = Engine(cfg, "test", "replay")
    eng.set_markets(markets)
    return eng


def _game(gid="g1", score="0-0", period="", elapsed="", live=False, ended=False, league="nba"):
    return {"game_id": gid, "league": league, "sport": "", "home": "Lakers", "away": "Celtics", "status": "",
            "live": live, "ended": ended, "score": score, "period": period, "elapsed": elapsed}


def test_model_deviation_signal_and_exit_on_target(cfg):
    m = make_market(fee=0.03, outcomes=("Lakers", "Celtics"))
    m.event_game_id = "g1"
    m.sports_market_type = "moneyline"
    eng = _engine(cfg, [m])
    h, a = m.tokens[0].token_id, m.tokens[1].token_id
    # precio previo: Lakers 55 %
    eng.books[h].apply_snapshot([{"price": 0.54, "size": 500}], [{"price": 0.56, "size": 500}], 1000)
    eng.books[a].apply_snapshot([{"price": 0.44, "size": 500}], [{"price": 0.46, "size": 500}], 1000)
    eng.on_game(1000, "g1", _game())
    assert "g1" in eng.pregame and abs(eng.pregame["g1"].home - 0.55) < 0.02
    # arranca el partido y el mercado sube a 0.70; Lakers +12 a 6 min del final: el modelo dice ~0.98
    eng.books[h].apply_snapshot([{"price": 0.69, "size": 500}], [{"price": 0.71, "size": 500}], 1500)
    eng.books[a].apply_snapshot([{"price": 0.29, "size": 500}], [{"price": 0.31, "size": 500}], 1500)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    assert eng.positions and eng.positions[0].signal.kind == "model_deviation"
    sig = eng.positions[0].signal
    assert sig.meta["side"] == "home" and sig.meta["p_model"] > 0.9 and sig.legs[0].token_id == h
    eng.tick(2200)
    pos = eng.positions[0]
    assert pos.status == "open" and pos.inventory[h] == sig.size
    # el mercado converge: bid por encima del target -> salida con ganancia
    eng.books[h].apply_snapshot([{"price": 0.98, "size": 500}], [{"price": 0.99, "size": 500}], 3000)
    eng.on_book(3000, h, eng.books[h])
    assert pos.status == "closed" and pos.exit_reason == "target" and pos.realized_pnl > 0


def test_model_deviation_settles_at_game_end(cfg):
    m = make_market(fee=0.03, outcomes=("Lakers", "Celtics"))
    m.event_game_id = "g1"
    eng = _engine(cfg, [m])
    h, a = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[h].apply_snapshot([{"price": 0.54, "size": 500}], [{"price": 0.56, "size": 500}], 1000)
    eng.books[a].apply_snapshot([{"price": 0.44, "size": 500}], [{"price": 0.46, "size": 500}], 1000)
    eng.on_game(1000, "g1", _game())
    eng.books[h].apply_snapshot([{"price": 0.69, "size": 500}], [{"price": 0.71, "size": 500}], 1500)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    eng.tick(2200)
    pos = eng.positions[0]
    eng.on_game(9000, "g1", _game(score="112-100", period="Q4", elapsed="12:00", live=False, ended=True))
    assert pos.status == "closed" and pos.exit_reason == "game_end"
    assert abs(pos.payout - pos.size_filled) < 1e-9 and pos.realized_pnl > 0       # ganó: paga 1 por share


def test_no_model_signal_when_game_advanced_without_pregame(cfg):
    m = make_market(fee=0.03, outcomes=("Lakers", "Celtics"))
    m.event_game_id = "g1"
    eng = _engine(cfg, [m])
    h, a = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[h].apply_snapshot([{"price": 0.54, "size": 500}], [{"price": 0.56, "size": 500}], 1000)
    eng.books[a].apply_snapshot([{"price": 0.44, "size": 500}], [{"price": 0.46, "size": 500}], 1000)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))   # arrancamos tarde
    assert not eng.positions and "g1" not in eng.pregame


def test_smart_money_follows_only_profiled_wallets(cfg):
    m = make_market(fee=0.0)
    eng = _engine(cfg, [m])
    y = m.tokens[0].token_id
    eng.books[y].apply_snapshot([{"price": 0.40, "size": 500}], [{"price": 0.42, "size": 500}], 1000)
    flow = {"wallet": "0xsmart", "name": "s", "side": "BUY", "usd": 5000, "price": 0.41, "token_id": y, "size": 12000}
    eng.on_flow(1000, m.condition_id, flow)
    assert not eng.positions                                            # sin perfil no se sigue
    good = WalletProfile(ts_ms=1, wallet="0xsmart", name="s", n_closed=120, wins=80, losses=30, total_bought=1e6,
                         realized_pnl=2e5, roi=0.2, win_rate=0.73, win_rate_adj=0.72, roi_adj=0.18, score=0.8,
                         biggest_win=1e4, biggest_loss=-5e3, n_open=10, open_value=1e4, open_pnl=0, first_ts=0, last_ts=0)
    eng.attach_wallets({"0xsmart": good})
    eng.on_flow(1500, m.condition_id, flow)
    assert eng.positions and eng.positions[0].signal.kind == "smart_money"
    assert eng.positions[0].signal.meta["wallet"] == "0xsmart"
    # con fee del 5 % (deportes), entrar y salir como taker se come la hipótesis: no hay señal
    eng.positions.clear()
    m.fee_rate = 0.05
    eng.on_flow(1600, m.condition_id, flow)
    assert not eng.positions
    m.fee_rate = 0.0
    # si el ask ya se fue lejos de su precio, no se persigue
    eng.books[y].apply_snapshot([{"price": 0.50, "size": 500}], [{"price": 0.52, "size": 500}], 2000)
    eng.on_flow(2000, m.condition_id, flow)
    assert not eng.positions


def test_directional_stop_and_price_moved(cfg):
    m = make_market(fee=0.03, outcomes=("Lakers", "Celtics"))
    m.event_game_id = "g1"
    eng = _engine(cfg, [m])
    h, a = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[h].apply_snapshot([{"price": 0.54, "size": 500}], [{"price": 0.56, "size": 500}], 1000)
    eng.books[a].apply_snapshot([{"price": 0.44, "size": 500}], [{"price": 0.46, "size": 500}], 1000)
    eng.on_game(1000, "g1", _game())
    eng.books[h].apply_snapshot([{"price": 0.69, "size": 500}], [{"price": 0.71, "size": 500}], 1500)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    assert eng.positions
    # el precio se dispara antes de ejecutar: no entrar
    eng.books[h].apply_snapshot([{"price": 0.80, "size": 500}], [{"price": 0.82, "size": 500}], 2050)
    eng.tick(2200)
    assert eng.closed and eng.closed[-1].exit_reason == "price_moved" and not eng.positions
