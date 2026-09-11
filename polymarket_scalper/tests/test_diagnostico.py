import json

from scalper.diagnostico import formatear, radiografia
from scalper.storage import ParquetWriter


def _datos(tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    base = 1_700_000_000_000

    def mercado(cid, cat, fee, tick, n_tokens=2):
        w.append("markets", {
            "ts_ms": base, "status": "active", "condition_id": cid, "gamma_id": "1", "question": f"q {cid}",
            "slug": "s", "event_id": "e", "event_slug": "es", "event_title": "et", "category": cat,
            "tokens": json.dumps([{"token_id": f"{cid}-{i}", "outcome": "Up", "index": i} for i in range(n_tokens)]),
            "neg_risk": False, "event_neg_risk": False, "tick_size": tick, "min_order_size": 5.0, "fee_rate": fee,
            "fee_type": "x", "volume_24h": 1000.0, "liquidity": 10.0, "end_date": "", "tags": "[]",
            "accepting_orders": True, "sports_market_type": "", "game_start_time": "", "event_market_count": 1,
            "event_neg_risk_augmented": False, "event_game_id": "", "event_start_time": "",
        })

    def quote(tok, cid, spread, i):
        mid = 0.50
        w.append("quotes", {"ts_ms": base + i * 5000, "token_id": tok, "condition_id": cid,
                            "best_bid": mid - spread / 2, "best_ask": mid + spread / 2, "bid_size": 200.0,
                            "ask_size": 200.0, "mid": mid, "spread": spread, "bid_depth_5t": 500.0,
                            "ask_depth_5t": 500.0})

    def trade(tok, cid, i, size=10.0):
        w.append("trades", {"ts_ms": base + i * 1000, "token_id": tok, "condition_id": cid, "price": 0.5,
                            "size": size, "side": "BUY", "fee_rate_bps": 0.0, "tx_hash": "0x"})

    # cripto: muy activo, spread siempre de 1 tick, comisión alta
    mercado("0xc", "crypto_updown", 0.07, 0.01)
    for i in range(20):
        quote("0xc-0", "0xc", 0.01, i)
        trade("0xc-0", "0xc", i, 20.0)
    # tenis: spreads anchos la mitad del tiempo, poco movimiento
    mercado("0xt", "tennis", 0.05, 0.01)
    for i in range(20):
        quote("0xt-0", "0xt", 0.01 if i % 2 else 0.05, i)
    trade("0xt-0", "0xt", 5)
    # nba: dos mercados, ninguno se mueve
    for k in range(2):
        mercado(f"0xn{k}", "nba", 0.03, 0.01)
        for i in range(10):
            quote(f"0xn{k}-0", f"0xn{k}", 0.01, i)
    w.close()


def test_radiografia_encuentra_donde_hay_movimiento(tmp_path):
    _datos(tmp_path)
    rx = radiografia(tmp_path)
    por_cat = {c["categoria"]: c for c in rx.categorias}
    assert rx.categorias[0]["categoria"] == "crypto_updown"        # ordenado por actividad real
    assert por_cat["crypto_updown"]["trades"] == 20
    assert por_cat["nba"]["trades"] == 0 and por_cat["nba"]["muertos_pct"] == 100.0
    assert rx.tokens_seguidos == 8 and rx.tokens_con_trades == 2 and rx.tokens_muertos == 6


def test_radiografia_mide_spread_y_coste_de_entrar(tmp_path):
    _datos(tmp_path)
    por_cat = {c["categoria"]: c for c in radiografia(tmp_path).categorias}
    assert por_cat["crypto_updown"]["spread_1_tick_pct"] == 100.0
    assert por_cat["crypto_updown"]["spread_3mas_pct"] == 0.0
    assert 45 < por_cat["tennis"]["spread_3mas_pct"] < 55          # la mitad del tiempo, 5 ticks
    # cruzar el libro cuesta medio tick más la comisión sobre p(1-p)
    assert abs(por_cat["crypto_updown"]["coste_entrar"] - (0.005 + 0.07 * 0.25)) < 1e-9
    assert por_cat["nba"]["coste_entrar"] < por_cat["tennis"]["coste_entrar"] < por_cat["crypto_updown"]["coste_entrar"]
    texto = formatear(radiografia(tmp_path))
    assert "DÓNDE HAY MOVIMIENTO" in texto and "la comisión es cero" in texto


def test_radiografia_sin_datos(tmp_path):
    rx = radiografia(tmp_path)
    assert rx.aviso and "faltan datos" in formatear(rx)
