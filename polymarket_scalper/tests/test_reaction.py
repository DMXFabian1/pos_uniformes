"""Market Reaction Engine: mide el retraso entre el partido y el precio en vez de suponerlo."""
from scalper.models.base import GameState
from scalper.reaction import ReactionEngine


def _g(score=(0, 0), period="Q1", live=True, ended=False):
    return GameState("g1", "nba", "basketball", "Lakers", "Celtics", live, ended, score[0], score[1], period)


def test_cambio_de_marcador_seguido_de_movimiento_del_mid_da_una_reaccion_con_su_retraso():
    r = ReactionEngine(umbral_ticks=1)
    assert r.on_game(1000, None, _g(), {"h": ("c1", 0.55)}) == "inicio"
    r.on_book(1500, "h", 0.56, 0.01)                        # reacciona al inicio (1 tick)
    assert r.on_game(10_000, _g(), _g(score=(3, 0)), {"h": ("c1", 0.56)}) == "marcador"
    r.on_book(10_200, "h", 0.565, 0.01)                     # medio tick: todavía no cuenta
    r.on_book(12_000, "h", 0.58, 0.01)                      # 2 ticks: reacción a los 2 s
    rows = r.drenar()
    assert len(rows) == 2
    ultima = rows[-1]
    assert ultima["evento"] == "marcador" and ultima["lag_ms"] == 2000 and ultima["reacciono"]
    assert abs(ultima["movimiento"] - 0.02) < 1e-9
    assert r.typical_lag_ms("nba") == 1250                  # mediana de 500 y 2000


def test_sin_movimiento_en_la_ventana_se_registra_como_no_reaccion():
    r = ReactionEngine(ventana_ms=5000)
    r.on_game(1000, _g(), _g(score=(2, 0)), {"h": ("c1", 0.55), "a": ("c1", 0.45)})
    r.on_book(2000, "h", 0.552, 0.01)
    r.expirar(3000)
    assert r.drenar() == []                                  # aún dentro de la ventana
    r.expirar(6001)
    rows = r.drenar()
    assert len(rows) == 2 and not any(x["reacciono"] for x in rows)
    assert rows[0]["lag_ms"] is None and r.typical_lag_ms("nba") is None


def test_un_evento_nuevo_cierra_el_anterior_pendiente():
    r = ReactionEngine()
    r.on_game(1000, _g(), _g(score=(2, 0)), {"h": ("c1", 0.55)})
    r.on_game(4000, _g(score=(2, 0)), _g(score=(2, 2)), {"h": ("c1", 0.55)})
    rows = r.drenar()
    assert len(rows) == 1 and not rows[0]["reacciono"] and rows[0]["ts_evento"] == 1000
    assert len(r.pendientes) == 1 and r.pendientes[0].ts_evento == 4000


def test_estado_para_los_detectores_es_explicable():
    r = ReactionEngine(riesgo_recencia_ms=30_000, riesgo_puntos_60s=12)
    assert r.estado("g1", "nba", 0)["event_risk_score"] == 0.0
    r.on_game(1000, _g(), _g(score=(3, 0)), {"h": ("c1", 0.55)})
    e = r.estado("g1", "nba", 4000)
    assert e["ms_since_event"] == 3000 and e["market_pending"]
    assert e["event_risk_components"]["recencia"] == 0.9         # 3 s de 30
    assert e["event_risk_components"]["rafaga_puntos_60s"] == 0.25   # 3 puntos de 12
    assert e["event_risk_score"] == 0.9
    r.expirar(70_000)
    e2 = r.estado("g1", "nba", 70_000)
    assert e2["event_risk_score"] == 0.0 and not e2["market_pending"]


def test_partido_no_en_vivo_no_genera_eventos():
    r = ReactionEngine()
    assert r.on_game(1, None, _g(live=False), {"h": ("c1", 0.5)}) is None
    assert r.on_game(1, _g(), _g(ended=True), {"h": ("c1", 0.5)}) is None


def test_un_retraso_negativo_no_se_guarda_porque_significa_relojes_distintos():
    """El libro trae el reloj del exchange y el partido el nuestro: si sale negativo, no mide nada."""
    r = ReactionEngine(umbral_ticks=1)
    r.on_game(10_000, _g(), _g(score=(2, 0)), {"h": ("c1", 0.55)})
    r.on_book(9_000, "h", 0.58, 0.01)                    # observación anterior al evento
    assert r.drenar() == [] and r.descartadas_por_reloj == 1
    r.on_book(12_000, "h", 0.58, 0.01)
    filas = r.drenar()
    assert len(filas) == 1 and filas[0]["lag_ms"] == 2000
