from scalper.models import ModelRegistry, WinProb, match_outcome, parse_game
from scalper.models.basketball import BasketballModel, phi_inv
from scalper.models.soccer import infer_rates, outcome_probs
from scalper.models.tennis import infer_point_probs, p_game, p_match, p_set, p_tiebreak


def test_parse_game_formats():
    g = parse_game({"game_id": 1, "league": "NBA", "home": "LAL", "away": "BOS", "live": True, "ended": False,
                    "score": "98-94", "period": "Q4", "elapsed": "05:12"})
    assert g.sport == "basketball" and (g.home_score, g.away_score) == (98, 94) and g.elapsed_s == 312
    t = parse_game({"game_id": 2, "league": "wta challenger", "sport": "tennis", "home": "A", "away": "B", "live": True,
                    "ended": False, "score": "7-6(7-2), 4-1", "period": "S2"})
    assert t.sport == "tennis" and t.extra["sets_home"] == 1 and t.extra["games_home"] == 4 and t.extra["games_away"] == 1
    tb = parse_game({"game_id": 3, "league": "challenger", "sport": "tennis", "home": "A", "away": "B", "live": True,
                     "ended": False, "score": "6-6(3-5)", "period": "TB1"})
    assert tb.extra["in_tiebreak"] and (tb.extra["tb_home"], tb.extra["tb_away"]) == (3, 5)
    e = parse_game({"game_id": 4, "league": "cs2", "home": "X", "away": "Y", "live": True, "ended": False,
                    "score": "7-6|1-1|Bo3", "period": "3/3"})
    assert e.sport == "esports" and (e.home_score, e.away_score) == (1, 1) and e.extra["best_of"] == 3
    s = parse_game({"game_id": 5, "league": "soccer", "home": "H", "away": "A", "live": True, "ended": False,
                    "score": "1-0", "period": "2H", "elapsed": "67"})
    assert s.sport == "soccer" and s.elapsed_s == 67 * 60


def test_basketball_stern_behaviour():
    m = BasketballModel(sigma=12.0)
    base = {"game_id": 1, "league": "nba", "home": "H", "away": "A", "live": True, "ended": False}
    even = m.prob(parse_game({**base, "score": "50-50", "period": "Q3", "elapsed": "00:00"}), WinProb(0.5, 0.5))
    assert abs(even.home - 0.5) < 1e-9
    pre = m.prob(parse_game({**base, "live": False, "score": "0-0", "period": ""}), WinProb(0.65, 0.35))
    assert abs(pre.home - 0.65) < 0.01                      # antes del partido reproduce el precio previo
    late = m.prob(parse_game({**base, "score": "110-98", "period": "Q4", "elapsed": "10:00"}), WinProb(0.4, 0.6))
    assert late.home > 0.97
    end = m.prob(parse_game({**base, "score": "100-101", "period": "Q4", "elapsed": "12:00"}), None)
    assert end.home == 0.0
    ot = m.prob(parse_game({**base, "score": "100-100", "period": "OT1", "elapsed": "02:30"}), None)
    assert abs(ot.home - 0.5) < 1e-9 and ot.detail["tau"] < 0.06
    assert abs(phi_inv(0.975) - 1.96) < 0.01


def test_tennis_markov_consistency():
    assert abs(p_game(0.5) - 0.5) < 1e-12 and p_game(0.62) > 0.77
    assert abs(p_tiebreak(0.62, 0.38) - 0.5) < 1e-9
    assert p_set(0.62, 0.38, 5, 0, True) > 0.99 and abs(p_set(0.62, 0.38, 0, 0, True) - 0.5) < 1e-9
    ph, pa = infer_point_probs(0.70, 0.62, 3)
    assert ph > pa and abs(p_match(ph, round(1 - pa, 4), 0, 0, 3, 0, 0, None) - 0.70) < 0.01
    up = p_match(ph, round(1 - pa, 4), 1, 0, 3, 4, 1, None)
    assert up > 0.95
    reg = ModelRegistry()
    g = parse_game({"game_id": 2, "league": "challenger", "sport": "tennis", "home": "A", "away": "B", "live": True,
                    "ended": False, "score": "7-6(7-2), 4-1", "period": "S2"})
    assert reg.prob(g, WinProb(0.6, 0.4)).home > 0.95


def test_soccer_poisson():
    lh, la = infer_rates(0.60, 0.25, 2.7)
    ph, pd, pa = outcome_probs(lh, la)
    assert abs(ph - 0.60) < 0.01 and abs(pd - 0.25) < 0.02
    reg = ModelRegistry()
    g = parse_game({"game_id": 5, "league": "soccer", "home": "H", "away": "A", "live": True, "ended": False,
                    "score": "1-0", "period": "2H", "elapsed": "80"})
    wp = reg.prob(g, WinProb(0.5, 0.25, 0.25))
    assert wp.home > 0.85 and wp.draw > wp.away
    ft = reg.prob(parse_game({"game_id": 5, "league": "soccer", "home": "H", "away": "A", "live": False, "ended": True,
                              "score": "2-2", "period": "FT"}), None)
    assert ft.draw == 1.0


def test_match_outcome_mapping():
    assert match_outcome("FC Barcelona", "FC Barcelona", "Feyenoord Rotterdam") == "home"
    assert match_outcome("Feyenoord", "FC Barcelona", "Feyenoord Rotterdam") == "away"
    assert match_outcome("Yes", "FC Barcelona", "Feyenoord Rotterdam", "Will FC Barcelona win on 2026-09-09?") == "home"
    assert match_outcome("Yes", "FC Barcelona", "Feyenoord Rotterdam", "Will Feyenoord Rotterdam win on 2026-09-09?") == "away"
    assert match_outcome("Yes", "FC Barcelona", "Feyenoord Rotterdam", "Will FC Barcelona vs. Feyenoord end in a draw?") == "draw"
    assert match_outcome("Draw", "H", "A") == "draw"
    assert match_outcome("Lakers", "Los Angeles Lakers", "Boston Celtics") == "home"
