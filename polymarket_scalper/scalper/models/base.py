"""Tipos comunes de los modelos de probabilidad de victoria en vivo."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class GameState:
    """Estado de un partido normalizado a partir de una fila de la tabla `games`."""
    game_id: str
    league: str
    sport: str              # basketball | tennis | soccer | esports | unknown
    home: str
    away: str
    live: bool
    ended: bool
    home_score: int = 0
    away_score: int = 0
    period: str = ""
    elapsed_s: float = 0.0  # segundos transcurridos en el período actual (si aplica)
    extra: dict[str, Any] = field(default_factory=dict)   # sets/juegos en tenis, etc.
    ts_ms: int = 0


@dataclass
class WinProb:
    home: float
    away: float
    draw: float = 0.0
    model: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def for_side(self, side: str) -> float:
        return {"home": self.home, "away": self.away, "draw": self.draw}[side]


class WinProbModel(Protocol):
    name: str

    def prob(self, g: GameState, pregame: WinProb | None) -> WinProb | None:
        """Probabilidad de victoria dado el estado. None si no se puede evaluar."""


_BASKET = {"nba", "wnba", "ncaab", "cbb", "euroleague", "basketball", "nbl", "acb", "cba", "bbl"}
_SOCCER = {"soccer", "epl", "laliga", "seriea", "bundesliga", "ligue1", "ucl", "uel", "mls", "fifa", "wc",
           "champions", "eredivisie", "liga", "premier", "football"}
_TENNIS = {"atp", "wta", "challenger", "wta challenger", "tennis", "itf"}
_ESPORTS = {"cs2", "csgo", "dota2", "lol", "mlbb", "r6siege", "valorant", "rl", "ow", "sc2"}


def sport_of(league: str, sport_hint: str = "") -> str:
    s = (sport_hint or "").lower()
    if s in ("basketball", "tennis", "soccer", "football"):
        return "soccer" if s == "football" else s
    lg = (league or "").lower()
    if lg in _BASKET or "basket" in lg or lg.startswith("nba"):
        return "basketball"
    if lg in _TENNIS or "atp" in lg or "wta" in lg or "tennis" in lg:
        return "tennis"
    if lg in _ESPORTS or lg.startswith("lol") or lg.startswith("cs"):
        return "esports"
    if lg in _SOCCER or "soccer" in lg or any(k in lg for k in ("liga", "league", "cup", "serie", "ucl", "uefa")):
        return "soccer"
    return "unknown"


_MMSS = re.compile(r"^(\d{1,3}):(\d{2})(?::(\d{2}))?$")


def parse_clock(elapsed: str) -> float:
    """'05:12' -> 312 s; '67' -> 67*60 s (minutos); vacío -> 0."""
    e = (elapsed or "").strip().strip("'")
    if not e:
        return 0.0
    m = _MMSS.match(e)
    if m:
        h_or_m, mm, ss = m.group(1), m.group(2), m.group(3)
        if ss is not None:
            return int(h_or_m) * 3600 + int(mm) * 60 + int(ss)
        return int(h_or_m) * 60 + int(mm)
    if e.replace("+", "").isdigit():
        return float(e.replace("+", "")) * 60
    return 0.0


def parse_game(row: dict[str, Any]) -> GameState:
    """Fila de `games` (o evento del recolector) -> GameState. Nunca lanza; lo que no entiende va a `extra`."""
    league = str(row.get("league") or "").lower()
    sport = sport_of(league, str(row.get("sport") or ""))
    score = str(row.get("score") or "")
    g = GameState(str(row.get("game_id") or ""), league, sport, str(row.get("home") or ""), str(row.get("away") or ""),
                  bool(row.get("live")), bool(row.get("ended")), period=str(row.get("period") or ""),
                  elapsed_s=parse_clock(str(row.get("elapsed") or "")), ts_ms=int(row.get("ts_ms") or 0))
    try:
        if sport == "tennis":
            g.extra = _parse_tennis(score, g.period)
            g.home_score, g.away_score = g.extra.get("sets_home", 0), g.extra.get("sets_away", 0)
        elif sport == "esports":
            parts = score.split("|")
            maps = parts[1] if len(parts) > 1 else parts[0]
            a, b = _pair(maps)
            g.home_score, g.away_score = a, b
            g.extra = {"best_of": int(re.sub(r"\D", "", parts[2]) or 0) if len(parts) > 2 else 0}
        else:
            g.home_score, g.away_score = _pair(score)
    except Exception:  # noqa: BLE001
        g.extra["parse_error"] = score
    return g


def _pair(s: str) -> tuple[int, int]:
    m = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _parse_tennis(score: str, period: str) -> dict[str, Any]:
    """'7-6(7-2), 4-1' + 'S2' -> sets terminados, juegos del set actual, tiebreak."""
    sets = [s.strip() for s in score.split(",") if s.strip()]
    sets_home = sets_away = 0
    games_home = games_away = 0
    tb_home = tb_away = 0
    in_tb = period.upper().startswith("TB")
    for i, st in enumerate(sets):
        base = re.sub(r"\(.*?\)", "", st)
        a, b = _pair(base)
        last = i == len(sets) - 1
        if last:
            games_home, games_away = a, b
            m = re.search(r"\((\d+)-(\d+)\)", st)
            if m and in_tb:
                tb_home, tb_away = int(m.group(1)), int(m.group(2))
            finished = _set_done(a, b)
            if finished:
                if a > b:
                    sets_home += 1
                else:
                    sets_away += 1
                games_home = games_away = 0
        else:
            if a > b:
                sets_home += 1
            elif b > a:
                sets_away += 1
    return {"sets_home": sets_home, "sets_away": sets_away, "games_home": games_home, "games_away": games_away,
            "tb_home": tb_home, "tb_away": tb_away, "in_tiebreak": in_tb, "n_sets": len(sets)}


def _set_done(a: int, b: int) -> bool:
    hi, lo = max(a, b), min(a, b)
    return (hi >= 6 and hi - lo >= 2) or (hi == 7 and lo == 6)


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def match_outcome(outcome: str, home: str, away: str, question: str = "") -> str | None:
    """A qué lado del partido corresponde un outcome de mercado: 'home' | 'away' | 'draw' | None.

    Outcomes 'Yes'/'No' se resuelven con la pregunta ('Will X win…', '…end in a draw?').
    """
    o = norm_name(outcome)
    if o in ("yes", "no"):
        q = norm_name(question)
        if "draw" in q or "tie" in q:
            side = "draw"
        else:
            side = _closest(q, home, away, min_ratio=0.0, contains=True)
        if side is None:
            return None
        if o == "yes":
            return side
        # 'No' en un mercado binario de 2 equipos es el otro lado; en 3 salidas no es un lado único
        return None
    if o in ("draw", "tie"):
        return "draw"
    return _closest(o, home, away)


def _closest(text: str, home: str, away: str, min_ratio: float = 0.6, contains: bool = False) -> str | None:
    h, a = norm_name(home), norm_name(away)
    if contains:
        hin, ain = h and h in text, a and a in text
        if hin and not ain:
            return "home"
        if ain and not hin:
            return "away"
        # nombres parciales: 'Barcelona' en 'will fc barcelona win'
        ht = [w for w in h.split() if len(w) > 3]
        at = [w for w in a.split() if len(w) > 3]
        hs = sum(1 for w in ht if w in text)
        as_ = sum(1 for w in at if w in text)
        if hs > as_:
            return "home"
        if as_ > hs:
            return "away"
        return None
    # 'Lakers' ⊂ 'Los Angeles Lakers': todas las palabras del outcome están en un solo equipo
    tw = {w for w in text.split() if len(w) > 2}
    if tw:
        hin = tw <= set(h.split())
        ain = tw <= set(a.split())
        if hin and not ain:
            return "home"
        if ain and not hin:
            return "away"
    rh = difflib.SequenceMatcher(None, text, h).ratio()
    ra = difflib.SequenceMatcher(None, text, a).ratio()
    if max(rh, ra) < min_ratio:
        return None
    return "home" if rh >= ra else "away"
