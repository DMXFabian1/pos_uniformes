import json
import random

from scalper.storage import ParquetWriter
from scalper.studies import estudiar, formatear


def _escribir(tmp_path, n=400, sobrerreaccion=0.10, informativo=False, seed=1):
    """Genera ventanas encadenadas donde el mercado se sesga según la racha anterior.

    sobrerreaccion: cuánto se aparta de 0,50 el precio de apertura tras una ventana ganada por Up.
    informativo: si True, ese sesgo además predice el resultado; si False, el resultado es 50/50.
    """
    rng = random.Random(seed)
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    cid = lambda i: f"0x{i:04d}"                                          # noqa: E731
    tok_up = lambda i: f"{i}-up"                                          # noqa: E731
    inicio = 1_700_000_000_000
    prev_up = True
    for i in range(n):
        start = inicio + i * 300_000
        end = start + 300_000
        sesgo = sobrerreaccion if prev_up else -sobrerreaccion
        p_up = 0.5 + sesgo
        p_real = p_up if informativo else 0.5
        up_won = rng.random() < p_real
        strike = 100000.0
        cierre = strike * (1.0005 if up_won else 0.9995)
        w.append("markets", {
            "ts_ms": start, "status": "updown", "condition_id": cid(i), "gamma_id": str(i), "question": "q",
            "slug": f"btc-updown-5m-{start // 1000}", "event_id": str(i), "event_slug": "e", "event_title": "t",
            "category": "crypto_updown",
            "tokens": json.dumps([{"token_id": tok_up(i), "outcome": "Up", "index": 0},
                                  {"token_id": f"{i}-down", "outcome": "Down", "index": 1}]),
            "neg_risk": False, "event_neg_risk": False, "tick_size": 0.01, "min_order_size": 5.0, "fee_rate": 0.07,
            "fee_type": "crypto_fees_v2", "volume_24h": 3000.0, "liquidity": 1000.0, "end_date": "", "tags": "[]",
            "accepting_orders": True, "sports_market_type": "", "game_start_time": "", "event_market_count": 1,
            "event_neg_risk_augmented": False, "event_game_id": "", "event_start_time": "",
        })
        w.append("quotes", {"ts_ms": start + 20_000, "token_id": tok_up(i), "condition_id": cid(i),
                            "best_bid": p_up - 0.01, "best_ask": p_up + 0.01, "bid_size": 100.0, "ask_size": 100.0,
                            "mid": p_up, "spread": 0.02, "bid_depth_5t": 500.0, "ask_depth_5t": 500.0})
        w.append("updown_windows", {"ts_ms": end, "condition_id": cid(i), "slug": f"btc-updown-5m-{start // 1000}",
                                    "symbol": "btc", "window_s": 300, "start_ms": start, "end_ms": end,
                                    "strike": strike, "strike_ts_ms": start, "settle_price": cierre,
                                    "up_won": up_won, "status": "resuelta"})
        prev_up = up_won
    w.close()


def test_study_detects_overreaction_and_favours_fading(tmp_path):
    _escribir(tmp_path, n=400, sobrerreaccion=0.10, informativo=False)
    est = estudiar(tmp_path)
    assert est.n == 400 and len(est.por_racha) == 2
    # el mercado se sesga hacia la racha, pero el resultado sigue siendo una moneda
    tras_up = next(g for g in est.por_racha if "subió" in g["grupo"])
    tras_down = next(g for g in est.por_racha if "bajó" in g["grupo"])
    assert tras_up["p_up_apertura"] > 0.55 and tras_down["p_up_apertura"] < 0.45
    assert 0.4 < tras_up["acabaron_up"] < 0.6                      # el sesgo no predijo nada
    a_favor = next(e for e in est.estrategias if "A FAVOR" in e["estrategia"])
    en_contra = next(e for e in est.estrategias if "EN CONTRA" in e["estrategia"])
    assert en_contra["pnl_usd"] > 0 > a_favor["pnl_usd"]           # conviene ir en contra
    assert en_contra["pnl_por_operacion"] > 1.0
    texto = formatear(est)
    assert "EN CONTRA" in texto and "AVISO" not in texto           # 400 muestras: sin aviso


def test_study_detects_an_informative_skew(tmp_path):
    _escribir(tmp_path, n=400, sobrerreaccion=0.10, informativo=True, seed=3)
    est = estudiar(tmp_path)
    tras_up = next(g for g in est.por_racha if "subió" in g["grupo"])
    assert tras_up["acabaron_up"] > 0.5                            # ahora el sesgo sí acertaba
    a_favor = next(e for e in est.estrategias if "A FAVOR" in e["estrategia"])
    en_contra = next(e for e in est.estrategias if "EN CONTRA" in e["estrategia"])
    assert a_favor["acierto"] > en_contra["acierto"]
    # con un sesgo del 10 % que sí es real, ir a favor no pierde contra el que va en contra
    assert a_favor["pnl_usd"] > en_contra["pnl_usd"]


def test_study_warns_with_few_samples(tmp_path):
    _escribir(tmp_path, n=25, sobrerreaccion=0.10, informativo=False)
    est = estudiar(tmp_path)
    assert est.n == 25
    assert "AVISO" in formatear(est) and "varios cientos" in formatear(est)


def test_study_without_data(tmp_path):
    est = estudiar(tmp_path)
    assert est.n == 0 and "faltan datos" in formatear(est)
