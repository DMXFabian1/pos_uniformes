"""El motor congelado y las comprobaciones que invalidan una corrida.

`muestra-3` promocionó un modelo a las 5 h 53 min de una corrida de 8 h y siguió escribiendo filas
con el mismo `experiment_id`: 186 de 680 posiciones decididas por otro motor, sin forma de
separarlas después. Estas pruebas fijan que eso no pueda repetirse en silencio.
"""
import polars as pl
import pytest

from scalper import calidad, experimento as ex
from scalper.storage import ParquetWriter


# --------------------------------------------------------------------------- la huella
def test_la_huella_cubre_el_codigo_de_simulacion_no_solo_el_commit(cfg, tmp_path, monkeypatch):
    # Con el árbol sucio el commit no describe lo que corre: se puede editar el modelo de llenado y
    # seguir informando del mismo commit. Por eso el código de simulación entra por su cuenta.
    cfg.data_dir = str(tmp_path)
    monkeypatch.setattr(ex, "commit_actual", lambda: ("abc1234", True))
    monkeypatch.setattr(ex, "modelos_en_uso", lambda _d: {})
    a = ex.congelar(cfg)
    monkeypatch.setattr(ex, "version_simulador", lambda *_a, **_k: "otro-codigo")
    b = ex.congelar(cfg)
    assert a.huella != b.huella
    assert a.simulador != b.simulador


def test_la_huella_distingue_si_el_reentrenamiento_podia_cambiar_el_motor(cfg, tmp_path, monkeypatch):
    cfg.data_dir = str(tmp_path)
    monkeypatch.setattr(ex, "commit_actual", lambda: ("abc1234", False))
    monkeypatch.setattr(ex, "modelos_en_uso", lambda _d: {})
    cfg.learn.enabled = True
    con = ex.congelar(cfg)
    cfg.learn.enabled = False
    sin = ex.congelar(cfg)
    assert con.reentrenamiento and not sin.reentrenamiento
    assert con.huella != sin.huella          # "podía cambiar" es parte de la identidad del motor


def test_un_modelo_promocionado_a_mitad_aborta_la_corrida(cfg, tmp_path, monkeypatch):
    cfg.data_dir = str(tmp_path)
    monkeypatch.setattr(ex, "commit_actual", lambda: ("abc1234", False))
    monkeypatch.setattr(ex, "modelos_en_uso", lambda _d: {})
    exp = ex.congelar(cfg)
    ex.assert_engine_frozen(cfg, exp)        # nada ha cambiado: pasa
    monkeypatch.setattr(ex, "modelos_en_uso", lambda _d: {"spread_capture": 2})
    with pytest.raises(ex.MotorCambiado) as e:
        ex.assert_engine_frozen(cfg, exp)
    assert "spread_capture" in str(e.value)


def test_mover_un_umbral_a_mitad_aborta_la_corrida(cfg, tmp_path, monkeypatch):
    cfg.data_dir = str(tmp_path)
    monkeypatch.setattr(ex, "commit_actual", lambda: ("abc1234", False))
    monkeypatch.setattr(ex, "modelos_en_uso", lambda _d: {})
    exp = ex.congelar(cfg)
    cfg.signals.min_edge_net = cfg.signals.min_edge_net + 0.01
    with pytest.raises(ex.MotorCambiado) as e:
        ex.assert_engine_frozen(cfg, exp)
    assert "min_edge_net" in str(e.value)


def test_cambiar_de_commit_a_mitad_aborta_la_corrida(cfg, tmp_path, monkeypatch):
    cfg.data_dir = str(tmp_path)
    monkeypatch.setattr(ex, "commit_actual", lambda: ("abc1234", False))
    monkeypatch.setattr(ex, "modelos_en_uso", lambda _d: {})
    exp = ex.congelar(cfg)
    monkeypatch.setattr(ex, "commit_actual", lambda: ("def5678", False))
    with pytest.raises(ex.MotorCambiado) as e:
        ex.assert_engine_frozen(cfg, exp)
    assert "commit" in str(e.value)


# --------------------------------------------------------------------------- calidad del dato
def _escribir(tmp_path, tabla, filas):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    for f in filas:
        w.append(tabla, f)
    w.close()


def _obs(i=0, llenada=True):
    return {"ts_ms": 1_700_000_000_000 + i, "run_id": "r", "experiment": "exp-1",
            "signal_id": f"s{i}", "strategy": "TENNIS_SPREAD_CAPTURE", "condition_id": "c",
            "token_id": "t", "precio": 0.5, "size": 50.0, "llenada": llenada}


def test_si_no_queda_ninguna_orden_sin_llenar_falta_el_denominador(tmp_path):
    # Sin las órdenes que no se llenan no existe una tasa de llenado: todo parece llenarse siempre.
    _escribir(tmp_path, "fill_observations", [_obs(i) for i in range(5)])
    inf = calidad.verificar(tmp_path)
    assert not inf.valida
    assert any("denominador" in p.detalle for p in inf.graves)


def test_con_ordenes_sin_llenar_la_comprobacion_pasa(tmp_path):
    _escribir(tmp_path, "fill_observations", [_obs(i, llenada=i < 3) for i in range(5)])
    problemas = calidad.ordenes_conservadas(tmp_path)
    assert problemas == []


def test_un_ts_fill_a_cero_no_es_un_reloj_roto(tmp_path):
    # Es el centinela de "nunca se llenó", que es justo lo que hay que conservar.
    _escribir(tmp_path, "ledger", [{
        "ts_ms": 1_700_000_000_000, "run_id": "r", "experiment": "exp-1", "signal_id": "s",
        "kind": "spread_capture", "condition_id": "c", "event_id": "e",
        "ts_signal": 1_700_000_000_000, "ts_fill": 0, "ts_exit": 1_700_000_060_000,
        "status": "closed", "exit_reason": "sin_llenar", "size_filled": 0.0, "realized_pnl": 0.0,
        "sombra": False,
    }])
    assert calidad.timestamps_posibles(tmp_path) == []


def test_cerrar_antes_de_llenarse_delata_dos_relojes_restados(tmp_path):
    _escribir(tmp_path, "ledger", [{
        "ts_ms": 1_700_000_000_000, "run_id": "r", "experiment": "exp-1", "signal_id": "s",
        "kind": "spread_capture", "condition_id": "c", "event_id": "e",
        "ts_signal": 1_700_000_000_000, "ts_fill": 1_700_000_060_000, "ts_exit": 1_700_000_010_000,
        "status": "closed", "exit_reason": "expired", "size_filled": 50.0, "realized_pnl": -6.4,
        "sombra": False,
    }])
    problemas = calidad.timestamps_posibles(tmp_path)
    assert problemas and "antes de llenarse" in problemas[0].detalle


def test_dos_experimentos_en_una_corrida_la_invalidan(tmp_path):
    base = {"ts_ms": 1_700_000_000_000, "run_id": "muestra-x", "signal_id": "s",
            "kind": "spread_capture", "condition_id": "c", "event_id": "e",
            "status": "closed", "exit_reason": "expired", "size_filled": 50.0,
            "realized_pnl": -1.0, "sombra": False}
    _escribir(tmp_path, "ledger", [{**base, "experiment": "exp-a"}, {**base, "experiment": "exp-b"}])
    problemas = calidad.un_solo_motor(tmp_path, "muestra-x")
    assert problemas and "2 experimentos" in problemas[0].detalle


def test_dos_versiones_de_modelo_en_una_corrida_la_invalidan(tmp_path):
    base = {"ts_ms": 1_700_000_000_000, "run_id": "muestra-x", "experiment": "exp-a", "signal_id": "s",
            "kind": "spread_capture", "condition_id": "c", "event_id": "e",
            "status": "closed", "exit_reason": "expired", "size_filled": 50.0,
            "realized_pnl": -1.0, "sombra": False}
    _escribir(tmp_path, "ledger", [{**base, "model_version": None}, {**base, "model_version": 2}])
    problemas = calidad.modelo_inmutable(tmp_path, "muestra-x")
    # Pasar de "sin modelo" a "con modelo v2" es la promoción a mitad de corrida: son dos motores.
    assert problemas and "se promocionó un modelo a mitad" in problemas[0].detalle
    assert "sin modelo" in problemas[0].detalle and "v2" in problemas[0].detalle


def _punto(**kw):
    base = {"ts_ms": 1_700_000_000_000, "run_id": "r", "experiment": "exp-1",
            "partial_leg_id": "pl-1", "strategy": "TENNIS_SPREAD_CAPTURE", "condition_id": "c",
            "token_id": "t", "horizonte_ms": 1_000, "best_bid": 0.45, "best_ask": 0.55,
            "mid": 0.50, "salida_precio": 0.45, "contrafactual_pnl": -0.5, "incompleto": None}
    base.update(kw)
    return base


def test_un_pnl_sin_precio_de_salida_solo_puede_venir_del_mid(tmp_path):
    _escribir(tmp_path, "partial_leg_track", [_punto(salida_precio=None)])
    problemas = calidad.precio_ejecutable(tmp_path)
    assert problemas and "del mid" in problemas[0].detalle


def test_un_hueco_sin_motivo_es_un_fallo(tmp_path):
    _escribir(tmp_path, "partial_leg_track", [_punto(contrafactual_pnl=None, incompleto=None)])
    problemas = calidad.precio_ejecutable(tmp_path)
    assert problemas and "tiene que decir por qué" in problemas[0].detalle


def test_usar_el_mid_como_precio_de_salida_se_detecta(tmp_path):
    # Si el precio de salida coincide exactamente con el mid una y otra vez, no salió del libro.
    _escribir(tmp_path, "partial_leg_track",
              [_punto(partial_leg_id=f"pl-{i}", salida_precio=0.50) for i in range(20)])
    problemas = calidad.precio_ejecutable(tmp_path)
    assert problemas and "sustituto" in problemas[0].detalle


def test_una_pata_sin_t0_no_se_puede_situar_en_el_tiempo(tmp_path):
    _escribir(tmp_path, "partial_legs", [{
        "ts_ms": 1_700_000_000_000, "run_id": "r", "experiment": "exp-1", "partial_leg_id": "pl-1",
        "signal_id": "s", "strategy": "TENNIS_SPREAD_CAPTURE", "condition_id": "c",
        "token_id": "t", "lado": "BUY", "t0_ms": 0, "desenlace": "caducada",
    }])
    problemas = calidad.patas_completas(tmp_path)
    assert problemas and "sin T0" in problemas[0].detalle


def test_un_identificador_de_pata_repetido_es_un_fallo(tmp_path):
    fila = {"ts_ms": 1_700_000_000_000, "run_id": "r", "experiment": "exp-1",
            "partial_leg_id": "pl-1", "signal_id": "s", "strategy": "TENNIS_SPREAD_CAPTURE",
            "condition_id": "c", "token_id": "t", "lado": "BUY",
            "t0_ms": 1_700_000_000_000, "desenlace": "caducada"}
    _escribir(tmp_path, "partial_legs", [fila, dict(fila)])
    problemas = calidad.patas_completas(tmp_path)
    assert problemas and "repetidos" in problemas[0].detalle


def test_el_resultado_hipotetico_no_puede_llegar_al_ledger(tmp_path):
    # El esquema es la primera defensa y la más fuerte: aunque alguien intente escribir una columna
    # contrafactual en el ledger, no llega al archivo. La comprobación de `pnl_separado` es la
    # segunda, por si el esquema cambiara.
    from scalper.storage import SCHEMAS

    assert not [c for c in SCHEMAS["ledger"].names if "contrafactual" in c]
    _escribir(tmp_path, "ledger", [{
        "ts_ms": 1_700_000_000_000, "run_id": "r", "experiment": "exp-1", "signal_id": "s",
        "kind": "spread_capture", "condition_id": "c", "event_id": "e",
        "status": "closed", "exit_reason": "expired", "size_filled": 50.0,
        "realized_pnl": -6.4, "sombra": False, "contrafactual_pnl": -0.5,
    }])
    guardadas = calidad._filas(tmp_path, "ledger").columns
    assert "contrafactual_pnl" not in guardadas
    assert calidad.pnl_separado(tmp_path) == []


def test_el_resultado_realizado_no_puede_vivir_en_la_trayectoria(tmp_path):
    from scalper.storage import SCHEMAS

    assert not [c for c in SCHEMAS["partial_leg_track"].names
                if c in ("realized_pnl", "pnl_realizado")]
