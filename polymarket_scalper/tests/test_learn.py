import json
import random

from scalper.learn.features import FeatureSchema, build_features, features_from_ledger_row
from scalper.learn.model import WinModel, brier
from scalper.learn.registry import ModelBundle, ModelStore
from scalper.learn.scorer import Scorer
from scalper.learn.train import train_kind
from scalper.signals.base import Leg, Signal
from scalper.sim.engine import Engine
from scalper.storage import ParquetWriter
from conftest import make_book, make_market


def _signal(kind="spread_capture", conf=0.5, **meta):
    return Signal(1_000_000, kind, "0xabc", "e1", [Leg("0xabc-0", "BUY", 0.41, 50, "maker"), Leg("0xabc-0", "SELL", 0.44, 50, "maker")],
                  50, 0.015, 0.0, 0.01, conf, "mean_revert", meta=dict(meta))


def test_features_are_signal_time_only_and_roundtrip():
    m = make_market(fee=0.05)
    b = make_book("0xabc-0", [(0.40, 100)], [(0.45, 100)])
    s = _signal(spread_ticks=5, tpm=1.2, mid_vol=0.003, imbalance=0.1, sport="tennis", league="atp", side="home")
    f = build_features(s, m, 1_000_000, b)
    assert f["conf_heuristic"] == 0.5 and f["spread_ticks"] == 5 and f["is_maker"] == 1.0 and f["fee_rate"] == 0.05
    assert f["sport"] == "tennis" and f["category"] == "sports"
    assert not any(k in f for k in ("realized_pnl", "error", "fills", "payout"))
    row = {"meta": json.dumps({"features": f})}
    assert features_from_ledger_row(row) == f
    assert features_from_ledger_row({"meta": "{}"}) is None
    schema = FeatureSchema.from_rows([f])
    v = schema.vector(f)
    assert len(v) == len(schema.names) and v[schema.names.index("sport=tennis")] == 1.0
    assert schema.vector({**f, "sport": "cricket"})[schema.names.index("sport=tennis")] == 0.0   # fuera de vocabulario


def _synthetic_rows(n, seed=1, informative=True):
    """Filas de ledger sintéticas: gana con prob. sigmoide(6·(mid_vol_norm)) si informative, si no al azar."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        vol = rng.random()
        spread = rng.choice([3, 4, 5, 6])
        p_true = 1 / (1 + 2.718 ** (-6 * (0.5 - vol))) if informative else 0.5
        y = 1 if rng.random() < p_true else 0
        f = {"edge_net": 0.01 + 0.002 * spread, "edge_gross": 0.02, "fee_est": 0.0, "size": 50, "conf_heuristic": 0.5,
             "entry_price": 0.4, "n_legs": 2, "spread_ticks": spread, "tpm": rng.random() * 3, "mid_vol": vol * 0.01,
             "imbalance": rng.uniform(-1, 1), "bid_depth": 5, "ask_depth": 5, "fee_rate": 0.05, "tick_size": 0.01,
             "volume_24h_log": 10, "hour_utc": i % 24, "dow": i % 7, "is_maker": 1, "category": "sports",
             "sport": rng.choice(["tennis", "soccer"]), "league": "x", "side": "", "sports_market_type": "moneyline",
             "horizon": "mean_revert"}
        rows.append({"run_id": "r", "mode": "replay", "signal_id": f"s{i}", "kind": "spread_capture", "condition_id": "c",
                     "event_id": "e", "ts_signal": 1_000_000 + i * 1000, "ts_fill": 0, "ts_exit": 0, "status": "closed",
                     "exit_reason": "both_filled" if y else "expired", "size_target": 50.0, "size_filled": 50.0,
                     "cost": 20.0, "fees": 0.0, "payout": 21.0 if y else 19.0, "predicted_edge": 0.01, "predicted_pnl": 0.5,
                     "realized_pnl": 1.0 if y else -1.0, "error": 0.0, "confidence": 0.5,
                     "meta": json.dumps({"features": f}), "conf_heuristic": 0.5, "p_win_model": None, "model_version": None})
    return rows


def _write_ledger(tmp_path, rows):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    for r in rows:
        w.append("ledger", r)
    w.close()


def test_train_promotes_when_model_beats_heuristic(tmp_path):
    _write_ledger(tmp_path, _synthetic_rows(300))
    rep = train_kind(tmp_path, "spread_capture", min_examples=40, backend="logistic")
    assert rep.n_train > 0 and rep.brier_val < rep.brier_heuristic_val and rep.promoted and rep.version == 1
    assert rep.top_features and rep.top_features[0][0] == "mid_vol"        # la feature que manda
    store = ModelStore(tmp_path)
    assert store.current_version("spread_capture") == 1
    # segunda versión: campeón/retador sobre la misma validación; igual receta -> no mejora al campeón
    rep2 = train_kind(tmp_path, "spread_capture", min_examples=40, backend="logistic")
    assert rep2.version == 2 and not rep2.promoted and "campeón" in rep2.reason
    assert store.current_version("spread_capture") == 1
    assert [h["version"] for h in store.history("spread_capture")] == [1, 2]


def test_train_does_not_promote_noise(tmp_path):
    _write_ledger(tmp_path, _synthetic_rows(300, seed=3, informative=False))
    rep = train_kind(tmp_path, "spread_capture", min_examples=40, backend="logistic")
    assert rep.n_train > 0 and not rep.promoted
    assert ModelStore(tmp_path).current_version("spread_capture") is None


def test_train_needs_enough_examples(tmp_path):
    _write_ledger(tmp_path, _synthetic_rows(20))
    rep = train_kind(tmp_path, "spread_capture", min_examples=40)
    assert rep.n_train == 0 and "pocos" in rep.reason


def test_scorer_blends_gates_and_sizes(tmp_path):
    rows = _synthetic_rows(300)
    _write_ledger(tmp_path, rows)
    train_kind(tmp_path, "spread_capture", min_examples=40, backend="logistic")
    store = ModelStore(tmp_path)
    m = make_market(fee=0.05)
    b = make_book("0xabc-0", [(0.40, 100)], [(0.45, 100)])
    sc = Scorer(store, shrink_n=50, min_train=30, min_p_win=0.5)
    good = sc.score(_signal(spread_ticks=5, tpm=1, mid_vol=0.0005), m, 1_000_000, b)     # vol baja -> gana
    bad = sc.score(_signal(spread_ticks=5, tpm=1, mid_vol=0.0095), m, 1_000_000, b)      # vol alta -> pierde
    assert good.trusted and good.p_model > 0.7 and bad.p_model < 0.3
    assert good.p_blend > bad.p_blend and not good.gate and bad.gate
    assert good.size_mult == 1.0 and bad.size_mult == 0.2
    w = 300 / 350
    assert abs(good.p_blend - (w * good.p_model + (1 - w) * 0.5)) < 1e-9
    # sin modelo para ese tipo: heurística intacta
    other = sc.score(_signal(kind="complement_buy", conf=0.7), m, 1_000_000, b)
    assert other.p_model is None and other.p_blend == 0.7 and not other.gate and other.size_mult == 1.0
    # poco entrenado: informa pero no filtra
    small = ModelBundle("complement_buy", 0, FeatureSchema.from_rows([]), WinModel("logistic").fit([[0.0], [1.0]], [0, 1]), 5)
    small.schema.numeric, small.schema.categorical = ["edge_net"], []
    store.save(small)
    store.promote("complement_buy", 1)
    sc.reload()
    r = sc.score(_signal(kind="complement_buy", conf=0.7), m, 1_000_000, b)
    assert r.p_model is not None and not r.trusted and not r.gate and r.size_mult == 1.0
    assert abs(r.p_blend - (5 / 55 * r.p_model + 50 / 55 * 0.7)) < 1e-9


def test_engine_stores_features_and_heuristic_confidence(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    m = make_market(fee=0.0)
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng = Engine(cfg, "t", "replay", w)
    eng.set_markets([m])
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[y].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.books[n].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.on_book(1000, y, eng.books[y])
    eng.tick(1200)
    w.close()
    from scalper.storage import scan
    df = scan(tmp_path, "ledger").collect()
    row = df.to_dicts()[0]
    assert row["conf_heuristic"] == row["confidence"] and row["p_win_model"] is None
    f = features_from_ledger_row(row)
    assert f is not None and f["n_legs"] == 2 and f["fee_rate"] == 0.0 and f["category"] == "sports"


def test_hgb_backend_if_available(tmp_path):
    import pytest
    from scalper.learn.model import has_sklearn
    if not has_sklearn():
        pytest.skip("scikit-learn no instalado")
    _write_ledger(tmp_path, _synthetic_rows(300, seed=5))
    rep = train_kind(tmp_path, "spread_capture", min_examples=40, backend="hgb")
    assert rep.promoted and rep.brier_val < rep.brier_heuristic_val
    b = ModelStore(tmp_path).load_current("spread_capture")
    assert b is not None and b.model.backend == "hgb"
    # serialización ida y vuelta: mismas predicciones
    rows = _synthetic_rows(5, seed=9)
    X = [b.schema.vector(json.loads(r["meta"])["features"]) for r in rows]
    again = ModelBundle.from_dict(b.to_dict())
    assert all(abs(p - q) < 1e-9 for p, q in zip(b.model.predict_proba(X), again.model.predict_proba(X)))
