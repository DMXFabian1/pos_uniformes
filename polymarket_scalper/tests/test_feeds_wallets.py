import asyncio

from scalper.flow import FlowPoller, flow_row, trade_key
from scalper.sports_feed import normalize_game, state_key
from scalper.wallets import score_wallet


def test_normalize_game_esports_and_tennis():
    es = {"gameId": 1674255, "leagueAbbreviation": "cs2", "homeTeam": "BetBoom", "awayTeam": "Astralis",
          "status": "running", "score": "7-6|1-1|Bo3", "period": "3/3", "live": True, "ended": False}
    r = normalize_game(es, 1)
    assert r["game_id"] == "1674255" and r["league"] == "cs2" and r["score"] == "7-6|1-1|Bo3" and r["live"]
    tn = {"gameId": 6187493, "leagueAbbreviation": "challenger", "homeTeam": "A", "awayTeam": "B",
          "status": "inprogress", "eventState": {"type": "tennis", "score": "7-6(7-2), 0-0", "period": "S2",
                                                  "live": True, "ended": False}}
    r2 = normalize_game(tn, 2)
    assert r2["sport"] == "tennis" and r2["score"] == "7-6(7-2), 0-0" and r2["period"] == "S2" and r2["live"]
    assert state_key(r2) != state_key(normalize_game({**tn, "eventState": {**tn["eventState"], "score": "7-6(7-2), 1-0"}}, 3))
    assert state_key(r2) == state_key(normalize_game(tn, 99))          # mismo estado, otro ts


def test_flow_row_and_dedupe():
    t = {"proxyWallet": "0xABC", "name": "n", "pseudonym": "p", "side": "BUY", "size": "100", "price": "0.45",
         "asset": "1", "conditionId": "0xc", "outcome": "Yes", "outcomeIndex": 0, "title": "t", "slug": "s",
         "eventSlug": "e", "timestamp": 1788960000, "transactionHash": "0xh"}
    r = flow_row(t)
    assert r["wallet"] == "0xabc" and r["usd"] == 45.0 and r["ts_ms"] == 1788960000000
    got = []

    class FakeApi:
        def __init__(self):
            self.pages = [[{**t, "timestamp": 1788960002}, {**t, "timestamp": 1788960001}, t],
                          [{**t, "timestamp": 1788960003}, {**t, "timestamp": 1788960002}, {**t, "timestamp": 1788960001}]]

        async def trades(self, limit=1000, offset=0, **kw):
            return self.pages.pop(0)

    async def handler(x):
        got.append(x["timestamp"])

    fp = FlowPoller(FakeApi(), handler, poll_seconds=0)
    assert asyncio.run(fp.poll_once()) == 3
    assert got == [1788960000, 1788960001, 1788960002]                  # orden cronológico
    assert asyncio.run(fp.poll_once()) == 1 and got[-1] == 1788960003   # solo el nuevo
    assert trade_key(t) == trade_key(dict(t))


def test_score_wallet_shrinks_small_samples_and_rewards_track_record():
    assert score_wallet([])["score"] == 0.5
    one_win = [{"realizedPnl": 1000, "totalBought": 500, "timestamp": 1}]
    s1 = score_wallet(one_win)
    assert 0.5 < s1["score"] < 0.75                                      # una operación no convence
    many = [{"realizedPnl": 100, "totalBought": 300, "timestamp": i} for i in range(40)] + \
           [{"realizedPnl": -80, "totalBought": 300, "timestamp": i} for i in range(10)]
    s2 = score_wallet(many)
    assert s2["n_closed"] == 50 and s2["wins"] == 40 and s2["losses"] == 10
    assert s2["win_rate"] == 0.8 and s2["score"] > s1["score"] > 0.5
    losers = [{"realizedPnl": -50, "totalBought": 100, "timestamp": i} for i in range(30)]
    assert score_wallet(losers)["score"] < 0.3
    # cosechador de 0.999: gana casi siempre pero el ROI es ~0 -> score moderado, no alto
    farmer = [{"realizedPnl": 5, "totalBought": 5000, "timestamp": i} for i in range(50)]
    sf = score_wallet(farmer)
    assert sf["wins"] == 0 and sf["losses"] == 0 and abs(sf["score"] - 0.5) < 0.01   # neutral: no demuestra nada
    assert sf["score"] < s2["score"]


def test_discovery_only_market_types_filter():
    from scalper.discovery import parse_market
    from scalper.config import Config
    cfg = Config.model_validate({"categories": {"tennis": {"tag_id": 864, "default_fee_rate": 0.05}},
                                 "discovery": {"only_market_types": ["moneyline", ""]}})
    assert cfg.discovery.only_market_types == ["moneyline", ""]
    ev = {"id": "1", "slug": "e", "title": "A vs B", "gameId": 7, "markets": []}
    base = {"id": "m", "question": "q", "conditionId": "0x1", "clobTokenIds": '["1","2"]', "outcomes": '["A","B"]',
            "enableOrderBook": True, "acceptingOrders": True, "feesEnabled": True, "feeSchedule": {"rate": 0.05}}
    ml = parse_market({**base, "sportsMarketType": "moneyline"}, ev, "tennis", 0.05)
    tot = parse_market({**base, "sportsMarketType": "tennis_match_totals"}, ev, "tennis", 0.05)
    fut = parse_market({**base}, ev, "tennis", 0.05)
    keep = [m for m in (ml, tot, fut) if m.sports_market_type in cfg.discovery.only_market_types]
    assert [m.sports_market_type for m in keep] == ["moneyline", ""]


def test_collector_shutdown_flushes_buffer_on_interrupt(cfg, tmp_path):
    """En Windows Ctrl+C llega como excepción: el cierre debe volcar igual lo pendiente."""
    import asyncio
    from scalper.collector import Collector
    from scalper.storage import ParquetWriter, scan

    cfg.data_dir = str(tmp_path)
    cfg.collector.prevent_sleep = False
    col = Collector(cfg, writer=ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9))

    async def boom():
        raise KeyboardInterrupt

    col._run_inner = boom
    col.writer.append("trades", {"ts_ms": 1_700_000_000_000, "token_id": "t", "condition_id": "c", "price": 0.5,
                                 "size": 1.0, "side": "BUY", "fee_rate_bps": 0.0, "tx_hash": "0x"})
    asyncio.run(col.run())                       # no debe propagar la interrupción
    assert col._closed and scan(tmp_path, "trades").collect().height == 1
    asyncio.run(col._shutdown())                 # idempotente
    assert scan(tmp_path, "trades").collect().height == 1


def test_el_lector_de_flujo_cuenta_los_huecos_cuando_la_pagina_viene_entera_nueva():
    """Si todo lo que llega es nuevo, entre consulta y consulta hubo más trades de los que caben."""
    import asyncio

    from scalper.flow import FlowPoller

    base = {"proxyWallet": "0xabc", "side": "BUY", "size": 100, "price": 0.45, "asset": "t",
            "conditionId": "c", "outcome": "Yes", "outcomeIndex": 0, "title": "x", "slug": "s",
            "eventSlug": "e", "transactionHash": "0xh"}
    paginas = [[{**base, "timestamp": 1, "transactionHash": "a"}],
               [{**base, "timestamp": 2, "transactionHash": "b"}],
               [{**base, "timestamp": 3, "transactionHash": "c"}]]

    class Api:
        async def trades(self, limit=2000, offset=0, **kw):
            return paginas.pop(0)

    async def handler(x):
        pass

    fp = FlowPoller(Api(), handler, poll_seconds=0)
    assert asyncio.run(fp.poll_once()) == 1 and fp.paginas_llenas == 0   # la primera no cuenta
    assert asyncio.run(fp.poll_once()) == 1 and fp.paginas_llenas == 1
    assert asyncio.run(fp.poll_once()) == 1 and fp.paginas_llenas == 2
