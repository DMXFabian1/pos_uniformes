import json
import time

from scalper.opportunities import Oportunidad, formatear, listar, por_grupo, resumen_grupo
from scalper.storage import ParquetWriter


def _mercado(w, cid, categoria, pregunta, ts):
    w.append("markets", {
        "ts_ms": ts, "status": "active", "condition_id": cid, "gamma_id": "1", "question": pregunta, "slug": "s",
        "event_id": "e", "event_slug": "es", "event_title": "et", "category": categoria,
        "tokens": json.dumps([{"token_id": cid + "-a", "outcome": "Up", "index": 0},
                              {"token_id": cid + "-b", "outcome": "Down", "index": 1}]),
        "neg_risk": False, "event_neg_risk": False, "tick_size": 0.01, "min_order_size": 5.0, "fee_rate": 0.07,
        "fee_type": "x", "volume_24h": 5000.0, "liquidity": 100.0, "end_date": "", "tags": "[]",
        "accepting_orders": True, "sports_market_type": "", "game_start_time": "", "event_market_count": 1,
        "event_neg_risk_augmented": False, "event_game_id": "", "event_start_time": "",
    })


def _senal(w, cid, kind, ts, edge, meta, size=50.0, conf=0.7, outcome="Up"):
    w.append("signals", {
        "ts_ms": ts, "signal_id": f"{kind}-{ts}", "kind": kind, "condition_id": cid, "event_id": "e",
        "legs": json.dumps([{"token_id": cid + "-a", "side": "BUY", "price": meta.get("entry", 0.5),
                             "size": size, "role": "taker", "outcome": outcome}]),
        "size": size, "edge_gross": edge + 0.01, "fee_est": 0.01, "edge_net": edge, "confidence": conf,
        "horizon": "resolution", "meta": json.dumps(meta), "run_id": "r",
    })


def _datos(tmp_path, ahora_ms=None):
    ahora = ahora_ms or int(time.time() * 1000)
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    _mercado(w, "0xbtc", "crypto_updown", "Bitcoin Up or Down - 9:05PM-9:10PM ET", ahora)
    _mercado(w, "0xnba", "nba", "Will the Lakers win on 2026-11-02?", ahora)
    _mercado(w, "0xatp", "tennis", "US Open ATP: Zverev vs Khachanov", ahora)
    _senal(w, "0xbtc", "updown_model", ahora - 20_000, 0.08,
           {"side": "up", "p_model": 0.68, "p_market": 0.52, "entry": 0.55, "moneyness_bps": 12.4,
            "seconds_left": 120, "tau": 0.4, "prev_up_won": True, "sport": "crypto", "league": "btc"})
    _senal(w, "0xnba", "model_deviation", ahora - 60_000, 0.05,
           {"side": "home", "p_model": 0.91, "p_market": 0.78, "entry": 0.80, "score": "102-88",
            "period": "Q4", "tau": 0.12, "league": "nba", "sport": "basketball"}, outcome="Lakers")
    _senal(w, "0xatp", "smart_money", ahora - 120_000, 0.03,
           {"wallet": "0xabc", "wallet_name": "Tobias1909", "their_usd": 8200, "their_price": 0.41,
            "wallet_n": 500, "wallet_roi": 0.223, "entry": 0.42}, outcome="Zverev")
    _senal(w, "0xbtc", "updown_model", ahora - 3_600_000, 0.20,
           {"side": "down", "p_model": 0.9, "entry": 0.30, "seconds_left": 60}, outcome="Down")
    w.close()
    return ahora


def test_lista_ordenada_por_ventaja_y_agrupada(tmp_path):
    _datos(tmp_path)
    ops = listar(tmp_path, minutos=120)
    assert len(ops) == 4
    # primero lo vigente, y dentro de eso lo más jugoso; lo caducado siempre al final
    assert [o.fresca for o in ops] == [True, True, True, False]
    vigentes = [o for o in ops if o.fresca]
    assert vigentes[0].edge_pct >= vigentes[1].edge_pct >= vigentes[2].edge_pct
    grupos = por_grupo(ops)
    assert set(grupos) == {"Cripto", "NBA", "Tenis"}
    btc = next(o for o in grupos["Cripto"] if o.fresca)
    assert btc.accion == "Comprar Up" and btc.precio == 0.55
    assert btc.inversion == round(0.55 * 50, 2) and btc.ganancia == round(0.08 * 50, 2)
    assert "Bitcoin va 12 puntos básicos por encima" in btc.razon
    assert "el modelo da 68 % a que suba" in btc.razon and "la ventana anterior terminó arriba" in btc.razon
    nba = grupos["NBA"][0]
    assert nba.accion == "Comprar Lakers" and "marcador 102-88" in nba.razon and "en Q4" in nba.razon
    ten = grupos["Tenis"][0]
    assert ten.accion == "Comprar Zverev" and "Tobias1909" in ten.razon and "8,200 USD" in ten.razon


def test_distingue_vigentes_de_caducadas(tmp_path):
    _datos(tmp_path)
    todas = listar(tmp_path, minutos=120)
    btc = [o for o in todas if o.grupo == "Cripto"]
    assert len(btc) == 2
    assert btc[0].fresca or btc[1].fresca
    vieja = next(o for o in btc if o.antiguedad_s > 600)
    assert not vieja.fresca                                  # una ventana de cripto de hace una hora no sirve
    solo = listar(tmp_path, minutos=120, solo_frescas=True)
    assert all(o.fresca for o in solo) and len(solo) < len(todas)
    assert "ya pudo cambiar" in formatear(todas)


def test_filtro_por_ventaja_minima(tmp_path):
    _datos(tmp_path)
    assert len(listar(tmp_path, minutos=120, min_edge=0.06)) == 2      # solo las de 0.08 y 0.20
    assert listar(tmp_path, minutos=120, min_edge=0.5) == []


def test_resumen_y_texto_sin_datos(tmp_path):
    assert listar(tmp_path, minutos=60) == []
    texto = formatear([])
    assert "no ve ninguna oportunidad" in texto and "buena señal" in texto
    assert resumen_grupo([])["total"] == 0
