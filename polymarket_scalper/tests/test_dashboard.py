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
