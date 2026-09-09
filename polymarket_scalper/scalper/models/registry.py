from __future__ import annotations

from .base import GameState, WinProb, WinProbModel, sport_of
from .basketball import BasketballModel
from .soccer import SoccerModel
from .tennis import TennisModel


class ModelRegistry:
    def __init__(self, sigma_basketball: float = 12.0, sigma_by_league: dict[str, float] | None = None,
                 soccer_total_goals: float = 2.7):
        self.models: dict[str, WinProbModel] = {
            "basketball": BasketballModel(sigma_basketball, sigma_by_league),
            "tennis": TennisModel(),
            "soccer": SoccerModel(soccer_total_goals),
        }

    def get(self, sport: str) -> WinProbModel | None:
        return self.models.get(sport)

    def prob(self, g: GameState, pregame: WinProb | None) -> WinProb | None:
        m = self.models.get(g.sport)
        return m.prob(g, pregame) if m is not None else None


def model_for_league(league: str, registry: ModelRegistry | None = None) -> WinProbModel | None:
    reg = registry or ModelRegistry()
    return reg.get(sport_of(league))
