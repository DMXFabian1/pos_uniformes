import json
import random

from scalper.readiness import MIN_DIAS, MIN_POSICIONES, evaluar, formatear
from scalper.storage import ParquetWriter

DIA = 86_400_000


def _ledger(tmp_path, kind="updown_model", n=150, media=0.6, ruido=1.0, dias=10.0, seed=1,
            forzados=0, p_modelo=None, p_heuristica=None):
    rng = random.Random(seed)
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    base = 1_700_000_000_000
    paso = int(dias * DIA / max(n, 1))
    for i in range(n + forzados):
        forzado = i >= n
        pnl = 0.0 if forzado else rng.gauss(media, ruido)
        w.append("ledger", {
            "run_id": "r", "mode": "paper", "signal_id": f"s{i}", "kind": kind, "condition_id": "c",
            "event_id": "e", "ts_signal": base + i * paso, "ts_fill": 0, "ts_exit": 0, "status": "closed",
            "exit_reason": "end" if forzado else "updown_settle", "size_target": 50.0, "size_filled": 50.0,
            "cost": 20.0, "fees": 0.5, "payout": 20.0 + pnl, "predicted_edge": 0.01, "predicted_pnl": media,
            "realized_pnl": -50.0 if forzado else pnl, "error": 0.0, "confidence": 0.6,
            "meta": json.dumps({}), "conf_heuristic": p_heuristica if p_heuristica is not None else 0.6,
            "p_win_model": p_modelo, "model_version": 1 if p_modelo is not None else None,
        })
    w.close()


def test_señal_rentable_con_muestra_grande_queda_lista(tmp_path):
    _ledger(tmp_path, n=200, media=0.6, ruido=1.0, dias=12)
    inf = evaluar(tmp_path)
    v = inf.veredictos[0]
    assert v.n == 200 and v.pnl > 0 and v.t > 2 and v.listo and not v.motivos
    assert inf.listas == ["updown_model"] and inf.alguna_lista
    texto = formatear(inf)
    assert "LISTA" in texto and "la capa que firma órdenes no está construida" in texto


def test_muestra_pequeña_no_basta_aunque_gane(tmp_path):
    _ledger(tmp_path, n=30, media=2.0, ruido=0.5, dias=12)
    v = evaluar(tmp_path).veredictos[0]
    assert v.pnl > 0 and not v.listo
    assert any("faltan posiciones" in m for m in v.motivos)


def test_ganancia_que_cabe_en_la_suerte_no_basta(tmp_path):
    _ledger(tmp_path, n=200, media=0.05, ruido=5.0, dias=12, seed=4)
    v = evaluar(tmp_path).veredictos[0]
    assert v.n >= MIN_POSICIONES and abs(v.t) < 2 and not v.listo
    assert any("cabe en la suerte" in m for m in v.motivos)


def test_señal_perdedora_nunca_queda_lista(tmp_path):
    _ledger(tmp_path, n=200, media=-0.5, ruido=1.0, dias=12)
    v = evaluar(tmp_path).veredictos[0]
    assert v.pnl < 0 and not v.listo and any("no positiva" in m for m in v.motivos)


def test_los_cierres_forzados_no_cuentan(tmp_path):
    """Liquidar al terminar una corrida corta no dice nada de la señal y no debe hundir el veredicto."""
    _ledger(tmp_path, n=200, media=0.6, ruido=1.0, dias=12, forzados=40)
    v = evaluar(tmp_path).veredictos[0]
    assert v.n == 200 and v.listo                       # los 40 forzados quedan fuera
    assert v.pnl > 0


def test_pocos_dias_bloquean_aunque_los_numeros_den(tmp_path):
    _ledger(tmp_path, n=300, media=0.6, ruido=1.0, dias=2)
    inf = evaluar(tmp_path)
    v = inf.veredictos[0]
    assert v.pnl > 0 and v.t > 2 and not v.listo
    assert any("días de datos" in m for m in v.motivos) and inf.dias < MIN_DIAS


def test_modelo_peor_que_la_heuristica_bloquea(tmp_path):
    _ledger(tmp_path, n=200, media=0.6, ruido=1.0, dias=12, p_modelo=0.05, p_heuristica=0.6)
    v = evaluar(tmp_path).veredictos[0]
    assert v.brier_modelo is not None and v.brier_modelo > v.brier_heuristica
    assert not v.listo and any("peor que la heurística" in m for m in v.motivos)


def test_sin_datos(tmp_path):
    inf = evaluar(tmp_path)
    assert not inf.alguna_lista and "no hay ledger" in inf.aviso
    assert "No:" in formatear(inf)
