import json

from scalper.dashboard.data import build_payload, snapshot_html


def test_payload_on_empty_data_dir(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    p = build_payload(cfg)
    assert p["summary"]["positions_closed"] == 0 and p["summary"]["equity"] == cfg.sim.start_cash
    assert p["equity"] == [] and p["games"] == [] and p["wallets"] == [] and p["models"] == []
    assert all(t["rows"] == 0 for t in p["tables"])
    json.dumps(p, default=str)                       # serializable


def test_snapshot_embeds_payload(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    html = snapshot_html(cfg)
    assert "window.__SNAPSHOT__" in html and "<title>Scalper Polymarket</title>" in html
    assert "<!--SNAPSHOT-->" not in html


def test_el_panel_trae_la_ejecucion_las_decisiones_y_las_reacciones(cfg, tmp_path):
    """El panel lee las mismas métricas que el veredicto, no unas propias."""
    from scalper.storage import ParquetWriter
    from test_evaluacion import _fila

    cfg.data_dir = str(tmp_path)
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    for i in range(6):
        w.append("ledger", _fila(i, strategy="NBA_DIRECTIONAL", pnl=1.0, edge=0.02, edge_taker=0.01))
    for i in range(4):
        w.append("ledger", _fila(6 + i, strategy="NBA_DIRECTIONAL", filled=0.0, cons=0.0, opt=0.0,
                                 exit_reason="sin_llenar", pnl=0.0, edge=0.02, edge_taker=0.01))
    w.append("decisions", {"ts_ms": int(__import__("time").time() * 1000), "run_id": "r", "condition_id": "c",
                           "kind": "model_deviation", "strategy": "NBA_DIRECTIONAL", "decision": "no_trade",
                           "motivo": "edge_neto_insuficiente", "edge_net": 0.001, "detalle": "{}"})
    w.append("reactions", {"ts_ms": 2000, "game_id": "g1", "league": "nba", "condition_id": "c", "token_id": "t",
                           "evento": "marcador", "ts_evento": 1000, "mid_antes": 0.5, "mid_despues": 0.53,
                           "lag_ms": 1000, "movimiento": 0.03, "reacciono": True})
    w.close()

    p = build_payload(cfg)
    ejec = {e["strategy"]: e for e in p["ejecucion"]}
    assert ejec["NBA_DIRECTIONAL"]["ejecucion"]["tasa_llenado"] == 0.6
    assert ejec["NBA_DIRECTIONAL"]["ejecucion"]["break_even_llenado"] == 0.5
    assert ejec["NBA_DIRECTIONAL"]["ejecucion"]["tasa_baseline"] == cfg.sim.fill_baseline_prob
    assert p["summary"]["tasa_llenado_observada"] == 0.6
    assert p["summary"]["no_trade_24h"] == 1
    assert p["decisiones"]["motivos"][0]["motivo"] == "edge_neto_insuficiente"
    assert p["reacciones"]["por_liga"][0]["league"] == "nba"
    json.dumps(p, default=str)
