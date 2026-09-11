"""Las métricas que deciden si una estrategia sirve, comprobadas con números conocidos."""
import json
import random

from scalper.evaluacion import bootstrap_ic, evaluar, evaluar_filas, formatear
from scalper.learn.train import walk_forward
from scalper.storage import ParquetWriter

DIA = 86_400_000


def _fila(i=0, strategy="NBA_DIRECTIONAL", role="maker", filled=50.0, target=50.0, pnl=1.0, edge=0.02,
          edge_taker=0.01, fees=0.0, exit_reason="target", cons=None, opt=None, adverse=None,
          ts=1_700_000_000_000, placed=None, ts_fill=None, barrido=False, queue=100.0, vol=200.0):
    fila = {
        "run_id": "r", "mode": "paper", "signal_id": f"s{i}", "kind": "model_deviation", "condition_id": "c",
        "event_id": "e", "ts_signal": ts, "ts_fill": ts_fill if ts_fill is not None else ts + 5000,
        "ts_exit": ts + 20_000, "status": "closed", "exit_reason": exit_reason, "size_target": target,
        "size_filled": filled, "cost": 30.0, "fees": fees, "payout": 30.0 + pnl, "predicted_edge": edge,
        "predicted_pnl": edge * target, "realized_pnl": pnl, "error": 0.0, "confidence": 0.6,
        "meta": json.dumps({}), "conf_heuristic": 0.6, "p_win_model": None, "model_version": None,
        "strategy": strategy, "entry_role": role, "ts_placed": placed if placed is not None else ts + 1000,
        "hold_s": 15.0, "fill_conservador": cons if cons is not None else filled,
        "fill_optimista": opt if opt is not None else filled, "queue_inicial": queue, "vol_cruzado": vol,
        "barrido": barrido, "edge_taker": edge_taker,
    }
    for k in ("adverse_100ms", "adverse_500ms", "adverse_1s", "adverse_2s", "adverse_5s", "adverse_10s"):
        fila[k] = (adverse or {}).get(k)
    return fila


# ------------------------------------------------------------------ tasa de llenado y break-even
def test_la_tasa_de_llenado_es_la_observada_no_la_supuesta():
    filas = [_fila(i, filled=50.0) for i in range(6)] + \
            [_fila(i + 6, filled=0.0, exit_reason="sin_llenar", pnl=0.0) for i in range(4)]
    e = evaluar_filas(filas, baseline=0.6)
    assert e.ejecucion.ordenes == 10 and e.ejecucion.llenadas == 6
    assert e.ejecucion.tasa_llenado == 0.6
    assert e.ejecucion.tasa_baseline == 0.6          # la referencia se muestra, no se usa


def test_los_tres_escenarios_se_reportan_por_separado():
    filas = [_fila(0, cons=0.0, opt=50.0), _fila(1, cons=50.0, opt=50.0),
             _fila(2, filled=0.0, cons=0.0, opt=30.0, exit_reason="sin_llenar", pnl=0.0)]
    x = evaluar_filas(filas).ejecucion
    assert x.tasa_llenado == round(2 / 3, 4)
    assert x.tasa_conservadora == round(1 / 3, 4)
    assert x.tasa_optimista == 1.0


def test_break_even_es_la_tasa_a_la_que_poner_la_orden_iguala_a_cruzar():
    # ventaja poniendo la orden 0.02, cruzando 0.01 → hace falta llenar más del 50 %
    filas = [_fila(i, edge=0.02, edge_taker=0.01) for i in range(8)] + \
            [_fila(i + 8, edge=0.02, edge_taker=0.01, filled=0.0, exit_reason="sin_llenar", pnl=0.0) for i in range(2)]
    x = evaluar_filas(filas).ejecucion
    assert x.break_even_llenado == 0.5
    assert x.tasa_llenado == 0.8 and x.margen_sobre_break_even == 0.3


def test_si_cruzar_el_libro_pierde_dinero_cualquier_llenado_gana():
    filas = [_fila(i, edge=0.02, edge_taker=-0.005) for i in range(4)]
    assert evaluar_filas(filas).ejecucion.break_even_llenado == 0.0


def test_las_entradas_taker_no_inflan_la_tasa_de_llenado():
    filas = [_fila(i, role="taker") for i in range(10)]
    x = evaluar_filas(filas).ejecucion
    assert x.ordenes == 0 and x.tasa_llenado is None      # no había ninguna orden esperando


def test_llenado_parcial_y_barridos_se_cuentan():
    filas = [_fila(0, filled=25.0, target=50.0), _fila(1, filled=50.0, target=50.0, barrido=True)]
    x = evaluar_filas(filas).ejecucion
    assert x.llenado_parcial_medio == 0.75 and x.barridas == 1


def test_espera_media_desde_que_se_pone_la_orden_hasta_que_se_llena():
    filas = [_fila(0, placed=1000, ts_fill=3000, ts=0), _fila(1, placed=1000, ts_fill=5000, ts=0)]
    assert evaluar_filas(filas).ejecucion.espera_media_s == 3.0


# ------------------------------------------------------------------ edge mínimo y selección adversa
def test_el_edge_minimo_suma_coste_de_salida_y_seleccion_adversa():
    adv = {"adverse_10s": -0.01}                    # el precio se va 1 centavo en contra tras llenarnos
    filas = [_fila(i, fees=0.5, filled=50.0, adverse=adv, edge=0.02) for i in range(4)]
    e = evaluar_filas(filas, margen=0.005)
    assert e.coste_salida == 0.01                   # 0.5 USD de comisión sobre 50 shares
    assert e.adversa["adverse_10s"] == -0.01
    assert e.edge_minimo_requerido == 0.025         # 0.01 + 0.01 + 0.005
    assert e.senales_sobre_minimo == 0.0            # ninguna señal de 0.02 llega al mínimo


def test_sin_seleccion_adversa_el_minimo_es_solo_coste_mas_margen():
    filas = [_fila(i, fees=0.0, adverse={"adverse_10s": 0.02}, edge=0.02) for i in range(4)]
    e = evaluar_filas(filas, margen=0.005)
    assert e.edge_minimo_requerido == 0.005 and e.senales_sobre_minimo == 1.0


def test_edge_aparente_contra_realizado():
    filas = [_fila(i, edge=0.02, pnl=0.5, filled=50.0) for i in range(4)]   # 0.01 por share realizado
    e = evaluar_filas(filas)
    assert e.edge_aparente == 0.02 and e.edge_realizado == 0.01 and e.captura == 0.5


# ------------------------------------------------------------------ significancia y resistencia
def test_bootstrap_devuelve_un_intervalo_que_contiene_la_media():
    rng = random.Random(3)
    xs = [rng.gauss(1.0, 1.0) for _ in range(300)]
    lo, hi = bootstrap_ic(xs)
    assert lo < sum(xs) / len(xs) < hi and lo > 0
    assert bootstrap_ic([1.0] * 10) is None          # con menos de 20 no se inventa un intervalo


def test_una_ventaja_que_cabe_en_la_suerte_da_un_intervalo_que_toca_el_cero():
    rng = random.Random(5)
    filas = [_fila(i, pnl=rng.gauss(0.02, 2.0)) for i in range(120)]
    e = evaluar_filas(filas)
    assert e.ic95 is not None and e.ic95[0] < 0 < e.ic95[1]


def test_el_escenario_conservador_descuenta_lo_que_no_se_habria_llenado():
    filas = [_fila(0, pnl=2.0, filled=50.0, cons=50.0), _fila(1, pnl=2.0, filled=50.0, cons=25.0),
             _fila(2, pnl=2.0, filled=50.0, cons=0.0)]
    e = evaluar_filas(filas)
    assert e.estres["base"] == 6.0
    assert e.estres["fill_conservador"] == 3.0       # 2 + 1 + 0
    filas2 = [_fila(0, pnl=2.0, fees=1.0)]
    assert evaluar_filas(filas2).estres["fees_x1.5"] == 1.5


def test_los_cierres_forzados_quedan_fuera_pero_se_ven_en_las_salidas():
    filas = [_fila(0, pnl=1.0), _fila(1, pnl=-50.0, exit_reason="end")]
    e = evaluar_filas(filas)
    assert e.n == 1 and e.pnl == 1.0
    assert e.salidas == {"target": 1, "end": 1}


def test_deciles_ordenan_el_resultado_por_ventaja_prometida():
    filas = [_fila(i, edge=0.001 * i, pnl=0.01 * i) for i in range(40)]
    e = evaluar_filas(filas)
    assert len(e.deciles) == 5
    assert e.deciles[0]["pnl_medio"] < e.deciles[-1]["pnl_medio"]


# ------------------------------------------------------------------ lectura desde disco
def test_evaluar_agrupa_por_estrategia_desde_el_ledger(tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    for i in range(5):
        w.append("ledger", _fila(i, strategy="NBA_DIRECTIONAL", pnl=1.0))
    for i in range(3):
        w.append("ledger", _fila(100 + i, strategy="CRYPTO_5M", pnl=-1.0))
    w.close()
    ests = evaluar(tmp_path)
    assert [e.strategy for e in ests] == ["CRYPTO_5M", "NBA_DIRECTIONAL"]
    assert ests[0].pnl == -3.0 and ests[1].pnl == 5.0
    texto = formatear(ests)
    assert "break-even" in texto and "referencia" in texto and "NBA_DIRECTIONAL" in texto


def test_sin_ledger_no_hay_metricas(tmp_path):
    assert evaluar(tmp_path) == []
    assert "Todavía no hay ledger" in formatear([])


# ------------------------------------------------------------------ validación hacia adelante
def test_walk_forward_necesita_muestra_y_reporta_por_pliegue(tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    rng = random.Random(7)
    base = 1_700_000_000_000
    for i in range(200):
        # la señal informativa: con edge alto casi siempre gana; el modelo debería encontrarlo
        edge = rng.choice([0.005, 0.05])
        gana = rng.random() < (0.8 if edge > 0.02 else 0.2)
        fila = _fila(i, ts=base + i * 60_000, pnl=1.0 if gana else -1.0, edge=edge,
                     exit_reason="target" if gana else "stop")
        fila["meta"] = json.dumps({"features": {"edge_net": edge, "conf_heuristic": 0.5, "entry_price": 0.5}})
        w.append("ledger", fila)
    w.close()
    wf = walk_forward(tmp_path, "model_deviation", folds=3, backend="logistic")
    assert wf.n_total == 200 and len(wf.folds) == 3
    assert all(f.brier_modelo is not None for f in wf.folds)
    assert wf.estable and wf.ganados >= 2        # la heurística es constante en 0.5: el modelo debe ganarle


def test_walk_forward_sin_datos_lo_dice(tmp_path):
    wf = walk_forward(tmp_path, "model_deviation")
    assert not wf.estable and "pocos ejemplos" in wf.razon


def test_el_triplete_bruto_ejecutable_conservador_y_realizado():
    """Los cuatro números de la misma operación, que casi nunca coinciden."""
    filas = []
    for i in range(4):
        f = _fila(i, edge=0.02, pnl=0.5, filled=50.0)     # realizado 0.01 por share
        f["meta"] = json.dumps({"edge_raw": 0.05, "edge_conservador": -0.004})
        filas.append(f)
    e = evaluar_filas(filas)
    assert e.edge_bruto == 0.05           # antes de cualquier coste
    assert e.edge_aparente == 0.02        # lo que prometió el detector tras comisiones
    assert e.edge_conservador == -0.004   # si hubiera que salir al bid de ese momento
    assert e.edge_realizado == 0.01       # lo que llegó al bolsillo
    assert "conservador" in formatear([e])


def test_las_filas_del_dado_no_cuentan_como_evidencia():
    """Una entrada maker sin escenarios de llenado es de cuando el fill salía de un dado."""
    vieja = _fila(0, role="maker", pnl=26.0, cons=None, opt=None)
    vieja["fill_conservador"] = None
    vieja["fill_optimista"] = None
    nueva = _fila(1, role="maker", pnl=-1.0)
    taker_viejo = _fila(2, role="taker", pnl=2.0)
    taker_viejo["fill_conservador"] = None
    e = evaluar_filas([vieja, nueva, taker_viejo])
    assert e.descartadas_del_dado == 1
    assert e.n == 2 and e.pnl == 1.0            # la vieja de +26 queda fuera; la taker se queda
    assert "anteriores a esta medición" in formatear([e])


def test_una_orden_que_nunca_se_lleno_no_es_del_dado():
    from scalper.evaluacion import es_del_dado

    # Llenada sin escenarios: eso sí salió del dado del 60 %.
    assert es_del_dado({"entry_role": "maker", "fill_conservador": None, "size_filled": 50.0})
    # Sin llenar: llega sin escenarios porque no hubo llenado, no porque se tirara un dado. Tirarla
    # dejaba fuera justo las órdenes que hacen falta para medir la tasa de llenado.
    assert not es_del_dado({"entry_role": "maker", "fill_conservador": None, "size_filled": 0.0})
    # Con escenarios, del modelo de cola.
    assert not es_del_dado({"entry_role": "maker", "fill_conservador": 50.0, "size_filled": 50.0})
    # Las taker nunca usaron el dado.
    assert not es_del_dado({"entry_role": "taker", "fill_conservador": None, "size_filled": 50.0})
