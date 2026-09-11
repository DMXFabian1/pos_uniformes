"""El informe de validación: que cada número diga lo que dice, con muestras conocidas."""
import json

from scalper.storage import ParquetWriter
from scalper.validacion import (AMARILLO, NARANJA, NEGRO, ROJO, VERDE, analizar, formatear, nivel)

BASE = 1_700_000_000_000


def _fila(i=0, strategy="NBA_DIRECTIONAL", role="maker", filled=50.0, pnl=1.0, edge=0.02, edge_taker=0.01,
          exit_reason="target", entrada=0.50, freshness=300, feed="SANO", sombra=False, motivo="",
          adverse=None, mfe=None, mae=None, tfav=None, tadv=None, t_target=None, t_stop=None,
          experiment="exp-1", ts=None, contaminado=False, barrido=False):
    ts = BASE + i * 60_000 if ts is None else ts
    fila = {
        "run_id": "r", "mode": "paper", "signal_id": f"s{i}", "kind": "model_deviation", "condition_id": "c",
        "event_id": "e", "ts_signal": ts, "ts_fill": ts + 5_000, "ts_exit": ts + 20_000, "status": "closed",
        "exit_reason": exit_reason, "size_target": 50.0, "size_filled": filled,
        "cost": entrada * filled, "fees": 0.0, "payout": entrada * filled + pnl, "predicted_edge": edge,
        "predicted_pnl": edge * 50, "realized_pnl": pnl, "error": 0.0, "confidence": 0.6,
        "meta": json.dumps({"entry": entrada, "entry_role": role, "edge_taker": edge_taker}),
        "conf_heuristic": 0.6, "p_win_model": None, "model_version": None,
        "strategy": strategy, "entry_role": role, "ts_placed": ts + 1_000, "hold_s": 15.0,
        "fill_conservador": filled, "fill_optimista": filled, "queue_inicial": 100.0, "vol_cruzado": 200.0,
        "barrido": barrido, "edge_taker": edge_taker, "experiment": experiment,
        "freshness_ms": freshness, "feed_state": feed, "contaminado": contaminado,
        "sombra": sombra, "motivo_rechazo": motivo, "mfe": mfe, "mae": mae,
        "t_mfe_ms": 2_000 if mfe is not None else None, "t_mae_ms": 8_000 if mae is not None else None,
        "t_target_ms": t_target, "t_stop_ms": t_stop,
        "target_antes_que_stop": None if (t_target is None and t_stop is None) else
        (t_target is not None and (t_stop is None or t_target <= t_stop)),
        "proc_delay_ms": 12, "decision_delay_ms": 3, "exec_delay_ms": 400,
    }
    for k in ("adverse_100ms", "adverse_500ms", "adverse_1s", "adverse_2s", "adverse_5s",
              "adverse_10s", "adverse_30s", "adverse_60s"):
        fila[k] = (adverse or {}).get(k)
    for k in ("05t", "1t", "2t", "3t"):
        fila[f"t_fav_{k}_ms"] = (tfav or {}).get(k)
        fila[f"t_adv_{k}_ms"] = (tadv or {}).get(k)
    return fila


def _obs(i=0, strategy="NBA_DIRECTIONAL", llenada=True, espera=2_000, cola=100.0, sombra=False,
         cons=None, opt=None, freshness=300):
    return {
        "ts_ms": BASE + i * 60_000, "run_id": "r", "experiment": "exp-1", "signal_id": f"s{i}",
        "strategy": strategy, "condition_id": "c", "token_id": "t", "precio": 0.5, "size": 50.0,
        "distancia_bid_ticks": 0.0, "distancia_ask_ticks": 1.0, "spread_ticks": 1.0,
        "profundidad_propia": 120.0, "profundidad_contraria": 300.0, "cola_delante": cola,
        "imbalance_1t": 0.1, "imbalance_3t": 0.2, "vel_1s": 0.0, "vel_5s": 0.0, "vol_60s": 0.001,
        "trades_por_minuto": 6.0, "freshness_ms": freshness, "feed_state": "SANO", "hora_utc": 3,
        "tau_partido": 0.2, "seconds_left": None, "edge_net": 0.02,
        "llenada": llenada, "fraccion_llenada": 1.0 if llenada else 0.0,
        "espera_ms": espera if llenada else None, "vol_cruzado": 200.0, "barrido": False,
        "llenada_conservador": llenada if cons is None else cons,
        "llenada_optimista": llenada if opt is None else opt, "sombra": sombra,
    }


def _escribir(tmp_path, ledger=(), fills=(), decisiones=(), post=(), salud=()):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    for r in ledger:
        w.append("ledger", r)
    for r in fills:
        w.append("fill_observations", r)
    for r in decisiones:
        w.append("decisions", r)
    for r in post:
        w.append("post_fill", r)
    for r in salud:
        w.append("feed_health", r)
    w.close()


# ------------------------------------------------------------------ etiquetas de confianza
def test_las_etiquetas_de_confianza_no_prometen_mas_de_lo_que_hay():
    assert nivel(0) == "SOLO DESCRIPTIVO" and nivel(19) == "SOLO DESCRIPTIVO"
    assert nivel(20) == "PRELIMINAR" and nivel(99) == "PRELIMINAR"
    assert nivel(100) == "MEDIBLE" and nivel(250) == "EVIDENCIA MÁS FIRME"
    assert nivel(500) == "EVIDENCIA ROBUSTA"


# ------------------------------------------------------------------ 1 y 2: llenado
def test_tasa_observada_contra_la_necesaria(tmp_path):
    # 6 de 10 órdenes se llenan; cada llenada gana 1 USD; cruzar habría dado 0.01 x 50 = 0.50
    ledger = [_fila(i, pnl=1.0, edge_taker=0.01) for i in range(6)]
    fills = [_obs(i, llenada=i < 6) for i in range(10)]
    _escribir(tmp_path, ledger=ledger, fills=fills)
    inf = analizar(tmp_path)
    L = inf.llenado[0]
    assert L.ordenes == 10 and L.llenadas == 6 and L.tasa == 0.6
    assert L.requerida == 0.5                       # 0.50 de cruzar / 1.00 por orden llenada
    assert L.espera_mediana_s == 2.0 and L.cola_mediana == 100.0
    assert "necesario" in formatear(inf)


def test_si_se_llena_menos_de_lo_necesario_el_semaforo_se_pone_naranja(tmp_path):
    ledger = [_fila(i, pnl=1.0, edge_taker=0.016) for i in range(3)]   # cruzar daría 0.80 por orden
    fills = [_obs(i, llenada=i < 3) for i in range(10)]                # se llena el 30 %
    _escribir(tmp_path, ledger=ledger, fills=fills)
    inf = analizar(tmp_path)
    assert inf.llenado[0].requerida == 0.8 and inf.llenado[0].tasa == 0.3
    assert inf.estados[0].semaforo == NARANJA
    assert "se llena el 30 %" in inf.estados[0].motivo


def test_la_sensibilidad_al_llenado_separa_los_barridos(tmp_path):
    # tres fills limpios de +2 y uno barrido de -6: la media baja, la limpia no
    ledger = [_fila(i, pnl=2.0) for i in range(3)] + [_fila(3, pnl=-6.0, barrido=True)]
    fills = [_obs(i) for i in range(4)]
    _escribir(tmp_path, ledger=ledger, fills=fills)
    L = analizar(tmp_path).llenado[0]
    fila = {s["tasa"]: s for s in L.sensibilidad}
    assert fila[1.0]["ev_por_orden"] == 0.0          # (2+2+2-6)/4 = 0
    assert fila[1.0]["ev_sin_barridos"] == 2.0
    assert fila[0.5]["ev_por_orden"] == 0.0 and fila[0.5]["ev_sin_barridos"] == 1.0


# ------------------------------------------------------------------ 3 y 4: ventaja
def test_el_barrido_de_umbrales_muestra_donde_el_valor_esperado_cambia_de_signo(tmp_path):
    # las señales flojas pierden, las fuertes ganan
    ledger = [_fila(i, edge=0.006, pnl=-1.0) for i in range(5)] + \
             [_fila(5 + i, edge=0.04, pnl=+2.0) for i in range(5)]
    _escribir(tmp_path, ledger=ledger)
    por_umbral = {r["umbral"]: r for r in analizar(tmp_path).barrido_edge}
    assert por_umbral[0.005]["n"] == 10 and por_umbral[0.005]["media"] == 0.5
    assert por_umbral[0.02]["n"] == 5 and por_umbral[0.02]["media"] == 2.0
    assert por_umbral[0.04]["n"] == 5


def test_los_tramos_de_ventaja_usan_porcentaje_sobre_el_precio(tmp_path):
    # 0.02 sobre una entrada de 0.50 es el 4 %; sobre 0.10 es el 20 %
    _escribir(tmp_path, ledger=[_fila(0, edge=0.02, entrada=0.50), _fila(1, edge=0.02, entrada=0.10)])
    tramos = {r["tramo"]: r for r in analizar(tmp_path).tramos if r["n"]}
    assert set(tramos) == {"4-5 %", "10 %+"}
    assert tramos["4-5 %"]["n"] == 1 and tramos["10 %+"]["n"] == 1


def test_mas_ventaja_no_implica_mejor_resultado_y_el_informe_lo_deja_ver(tmp_path):
    ledger = [_fila(i, edge=0.004, entrada=0.5, pnl=1.0) for i in range(4)] + \
             [_fila(4 + i, edge=0.06, entrada=0.5, pnl=-3.0) for i in range(4)]
    _escribir(tmp_path, ledger=ledger)
    tramos = {r["tramo"]: r for r in analizar(tmp_path).tramos if r["n"]}
    assert tramos["0-1 %"]["media"] == 1.0 and tramos["10 %+"]["media"] == -3.0
    assert tramos["10 %+"]["drawdown"] == -12.0


# ------------------------------------------------------------------ 5, 6 y 7: después del fill
def test_la_seleccion_adversa_y_el_recorrido_se_promedian_por_estrategia(tmp_path):
    adv = {"adverse_100ms": 0.001, "adverse_1s": -0.004, "adverse_10s": -0.01, "adverse_60s": -0.02}
    ledger = [_fila(i, adverse=adv, mfe=0.006, mae=-0.012) for i in range(4)]
    _escribir(tmp_path, ledger=ledger)
    r = analizar(tmp_path).post_fill[0]
    assert r["adverse_100ms"] == 0.001 and r["adverse_10s"] == -0.01 and r["adverse_60s"] == -0.02
    assert r["mfe_medio"] == 0.006 and r["mae_medio"] == -0.012
    assert r["t_mfe_s"] == 2.0 and r["t_mae_s"] == 8.0
    assert r["a_favor"] == round(0.006 / 0.018, 3)      # el recorrido es el doble en contra


def test_los_tiempos_hasta_cada_movimiento_dan_mediana_y_cobertura(tmp_path):
    ledger = [_fila(0, tfav={"1t": 1_000}, tadv={"1t": 4_000}),
              _fila(1, tfav={"1t": 3_000}, tadv={"1t": 6_000}),
              _fila(2)]                                  # esta nunca se movió un tick
    _escribir(tmp_path, ledger=ledger)
    r = analizar(tmp_path).tiempos[0]
    assert r["fav_1t_s"] == 2.0 and r["fav_1t_pct"] == round(2 / 3, 3)
    assert r["adv_1t_s"] == 5.0
    assert r["fav_3t_s"] is None and r["fav_3t_pct"] == 0.0


def test_la_curva_por_horizonte_dice_donde_aparece_la_ventaja(tmp_path):
    post = []
    for i in range(3):
        for h, delta in ((1_000, 0.01), (60_000, 0.03), (900_000, -0.02)):
            post.append({"ts_ms": BASE + h, "run_id": "r", "experiment": "exp-1", "signal_id": f"s{i}",
                         "strategy": "NBA_DIRECTIONAL", "condition_id": "c", "token_id": "t",
                         "horizonte_ms": h, "entrada": 0.5, "mid": 0.5 + delta, "best_bid": 0.5 + delta - 0.01,
                         "best_ask": 0.5 + delta + 0.01, "delta": delta, "delta_bid": delta - 0.01,
                         "sombra": False, "contaminado": False, "feed_state": "SANO"})
    _escribir(tmp_path, ledger=[_fila(0)], post=post)
    curva = {r["horizonte_ms"]: r for r in analizar(tmp_path).horizontes}
    assert curva[1_000]["delta_medio"] == 0.01 and curva[60_000]["delta_medio"] == 0.03
    assert curva[900_000]["delta_medio"] == -0.02 and curva[900_000]["a_favor"] == 0.0
    assert curva[60_000]["delta_bid_medio"] == 0.02


# ------------------------------------------------------------------ 8 y 9: frescura
def test_el_informe_corta_por_frescura_del_libro(tmp_path):
    ledger = [_fila(i, freshness=100, pnl=2.0) for i in range(3)] + \
             [_fila(3 + i, freshness=3_000, pnl=-1.0) for i in range(2)]
    _escribir(tmp_path, ledger=ledger)
    tramos = {r["tramo"]: r for r in analizar(tmp_path).frescura}
    assert tramos["0-250ms"]["n_validas"] == 3 and tramos["0-250ms"]["pnl_medio"] == 2.0
    assert tramos["2-5s"]["n_validas"] == 2 and tramos["2-5s"]["pnl_medio"] == -1.0


def test_con_el_reloj_desfasado_el_corte_por_frescura_sigue_significando_algo(tmp_path):
    # Caso real: el reloj del contenedor iba ~200 ms por detrás del que estampa los mensajes, así
    # que `recv - ts` salía negativo en la mayoría de las decisiones. Sin descontar ese suelo, todas
    # esas filas caían en `10s+` y el informe daba a entender que se operaba con el libro rancio.
    ledger = [_fila(i, freshness=-180, pnl=2.0) for i in range(3)] + \
             [_fila(3 + i, freshness=-98, pnl=-1.0) for i in range(2)]
    _escribir(tmp_path, ledger=ledger)
    inf = analizar(tmp_path)
    tramos = {r["tramo"]: r for r in inf.frescura}
    assert "10s+" not in tramos
    assert tramos["0-250ms"]["n_validas"] == 5
    assert inf.salud["desfase_reloj_ms"] == -180.0
    # Y la frescura que se enseña es relativa al suelo, nunca negativa.
    assert inf.cadena["retraso_feed_ms"] >= 0


def test_los_umbrales_de_frescura_se_prueban_todos_sin_elegir_el_mejor(tmp_path):
    ledger = [_fila(0, freshness=200, pnl=1.0), _fila(1, freshness=3_000, pnl=-5.0)]
    _escribir(tmp_path, ledger=ledger)
    inf = analizar(tmp_path)
    por = {r["umbral_ms"]: r for r in inf.umbrales_frescura}
    assert por[250]["operaciones"] == 1 and por[250]["pnl"] == 1.0
    assert por[5_000]["operaciones"] == 2 and por[5_000]["pnl"] == -4.0
    assert "eso sería ajustar al ruido" in formatear(inf)


def test_las_posiciones_con_el_feed_viejo_no_se_mezclan(tmp_path):
    ledger = [_fila(i, pnl=1.0) for i in range(3)] + \
             [_fila(3 + i, pnl=50.0, feed="VIEJO", contaminado=True) for i in range(2)]
    _escribir(tmp_path, ledger=ledger)
    inf = analizar(tmp_path)
    assert inf.salud["posiciones_validas"] == 3 and inf.salud["posiciones_contaminadas"] == 2
    assert inf.post_fill[0]["n"] == 3                    # las sucias no inflan el resultado


def test_si_todo_se_decidio_con_el_feed_viejo_el_semaforo_es_negro(tmp_path):
    _escribir(tmp_path, ledger=[_fila(i, feed="CONGELADO", contaminado=True) for i in range(5)])
    inf = analizar(tmp_path)
    assert inf.estados[0].semaforo == NEGRO


# ------------------------------------------------------------------ 10: lo rechazado
def test_las_sombras_dicen_si_rechazamos_bien_y_nunca_tocan_el_resultado(tmp_path):
    reales = [_fila(i, pnl=1.0) for i in range(3)]
    sombras = [_fila(100 + i, pnl=5.0, sombra=True, motivo="bajo_el_minimo_requerido") for i in range(25)]
    _escribir(tmp_path, ledger=reales + sombras)
    inf = analizar(tmp_path)
    assert inf.salud["posiciones_validas"] == 3          # las sombras no cuentan como operaciones
    r = [x for x in inf.rechazos if x["motivo"] == "bajo_el_minimo_requerido"][0]
    assert r["seguidas"] == 25 and r["media"] == 5.0 and r["veredicto"] == "se rechazaban buenas"
    malas = [_fila(200 + i, pnl=-3.0, sombra=True, motivo="feed_atrasado") for i in range(20)]
    _escribir(tmp_path, ledger=malas)
    r2 = [x for x in analizar(tmp_path).rechazos if x["motivo"] == "feed_atrasado"][0]
    assert r2["veredicto"] == "bien rechazadas"


def test_un_rechazo_con_pocas_sombras_no_concluye_nada(tmp_path):
    sombras = [_fila(i, pnl=9.0, sombra=True, motivo="tope_posiciones") for i in range(3)]
    _escribir(tmp_path, ledger=sombras)
    r = analizar(tmp_path).rechazos[0]
    assert r["veredicto"] == "muestra insuficiente"


# ------------------------------------------------------------------ salidas y semáforo
def test_probabilidades_de_salida(tmp_path):
    ledger = [_fila(0, t_target=5_000, t_stop=None, exit_reason="target"),
              _fila(1, t_target=None, t_stop=3_000, exit_reason="stop"),
              _fila(2, t_target=9_000, t_stop=2_000, exit_reason="stop"),
              _fila(3, t_target=None, t_stop=None, exit_reason="time_stop")]
    _escribir(tmp_path, ledger=ledger)
    r = analizar(tmp_path).salidas[0]
    assert r["n"] == 4 and r["p_target"] == 0.5 and r["p_stop"] == 0.5
    assert r["p_target_antes"] == 0.25                   # solo la primera llegó antes al objetivo
    assert r["t_target_s"] == 7.0


def test_el_semaforo_solo_es_verde_con_el_intervalo_entero_por_encima_de_cero(tmp_path):
    _escribir(tmp_path, ledger=[_fila(i, pnl=1.0) for i in range(40)])
    assert analizar(tmp_path).estados[0].semaforo == VERDE


def test_el_semaforo_es_rojo_solo_con_evidencia_de_perdida(tmp_path):
    _escribir(tmp_path, ledger=[_fila(i, pnl=-1.0) for i in range(40)])
    assert analizar(tmp_path).estados[0].semaforo == ROJO


def test_una_estrategia_con_siete_operaciones_nunca_se_declara_muerta(tmp_path):
    _escribir(tmp_path, ledger=[_fila(i, pnl=-2.0) for i in range(7)])
    e = analizar(tmp_path).estados[0]
    assert e.semaforo == AMARILLO and "no alcanza para concluir" in e.motivo
    assert not e.listo_para_medir and any("faltan operaciones" in f for f in e.faltan)


def test_sin_datos_el_informe_se_imprime_igual(tmp_path):
    inf = analizar(tmp_path)
    texto = formatear(inf)
    assert "INFORME DE VALIDACIÓN" in texto and inf.estados == []


# ------------------------------------------------------------------ añadidos de la fase
def test_la_caida_esperada_depende_de_la_tasa_de_llenado(tmp_path):
    # una racha mala seguida de una buena: con llenado parcial la caída típica es menor
    pnls = [-2.0] * 6 + [3.0] * 6
    ledger = [_fila(i, pnl=x) for i, x in enumerate(pnls)]
    _escribir(tmp_path, ledger=ledger, fills=[_obs(i) for i in range(12)])
    L = analizar(tmp_path).llenado[0]
    por = {s["tasa"]: s for s in L.sensibilidad}
    assert por[1.0]["drawdown"] == -12.0                 # llenándolo todo se sufre la racha entera
    assert por[0.3]["drawdown"] > por[1.0]["drawdown"]   # con menos llenado, menos caída


def test_los_tramos_de_ventaja_traen_ordenes_y_llenado(tmp_path):
    # dos órdenes en el tramo 4-5 % (0.02 sobre 0.50), una de ellas llenada
    fills = [dict(_obs(0), edge_net=0.02, precio=0.50, llenada=True),
             dict(_obs(1), edge_net=0.02, precio=0.50, llenada=False)]
    _escribir(tmp_path, ledger=[_fila(0, edge=0.02, entrada=0.50)], fills=fills)
    tramos = {r["tramo"]: r for r in analizar(tmp_path).tramos if r.get("ordenes")}
    assert tramos["4-5 %"]["ordenes"] == 2 and tramos["4-5 %"]["llenadas"] == 1
    assert tramos["4-5 %"]["tasa_llenado"] == 0.5


def test_el_score_de_frescura_decae_a_la_mitad_cada_segundo():
    from scalper.salud import freshness_score
    assert freshness_score(0) == 1.0
    assert freshness_score(1000) == 0.5
    assert freshness_score(2000) == 0.25
    assert freshness_score(None) is None
    # Con el reloj desfasado, la escala se mide desde el suelo, no desde cero.
    assert freshness_score(-200, desfase_ms=-200) == 1.0
    assert freshness_score(800, desfase_ms=-200) == 0.5


def test_que_una_orden_se_llene_no_es_un_veredicto_sobre_si_gana(tmp_path):
    # Caso real: TENNIS_SPREAD_CAPTURE se llenaba bien y salía 🟢 EVIDENCIA POSITIVA en la tabla de
    # llenado, mientras su intervalo de confianza estaba entero por debajo de cero. La columna de
    # llenado responde a "¿se llena?", nunca a "¿gana?".
    from scalper.validacion import LLENA_OK, LLENA_SIN_MEDIDA
    ledger = [_fila(i, pnl=-3.0, edge_taker=0.0) for i in range(25)]
    fills = [_obs(i) for i in range(25)]
    _escribir(tmp_path, ledger=ledger, fills=fills)
    inf = analizar(tmp_path)
    assert inf.llenado[0].estado in (LLENA_OK, LLENA_SIN_MEDIDA)
    assert VERDE not in inf.llenado[0].estado
    assert inf.estados[0].semaforo == ROJO      # el veredicto de verdad sigue siendo el de abajo


def test_sin_tasa_necesaria_el_llenado_no_se_da_por_bueno(tmp_path):
    # La captura de spread entra por los dos lados: no hay "cruzar en vez de esperar" con el que
    # comparar, así que no se puede decir que se llene lo suficiente. Se dice que no hay medida.
    from scalper.validacion import LLENA_SIN_MEDIDA
    ledger = [_fila(i, pnl=1.0, edge_taker=None) for i in range(25)]
    fills = [_obs(i) for i in range(25)]
    _escribir(tmp_path, ledger=ledger, fills=fills)
    inf = analizar(tmp_path)
    assert inf.llenado[0].requerida is None
    assert inf.llenado[0].estado == LLENA_SIN_MEDIDA
