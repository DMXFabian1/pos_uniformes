"""Modelo P(ganancia | señal). Backend `hgb` (scikit-learn, gradient boosting) o `logistic` (Python puro)."""
from __future__ import annotations

import base64
import math
import pickle
from typing import Any

try:  # scikit-learn es opcional
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore
    _HAS_SK = True
except Exception:  # noqa: BLE001
    _HAS_SK = False


def has_sklearn() -> bool:
    return _HAS_SK


class _Logistic:
    """Regresión logística L2 con descenso de gradiente sobre features estandarizadas."""

    def __init__(self, l2: float = 1.0, epochs: int = 400, lr: float = 0.1):
        self.l2, self.epochs, self.lr = l2, epochs, lr
        self.w: list[float] = []
        self.b = 0.0
        self.mu: list[float] = []
        self.sd: list[float] = []

    def _std(self, X: list[list[float]]) -> list[list[float]]:
        return [[(x - m) / s for x, m, s in zip(row, self.mu, self.sd)] for row in X]

    def fit(self, X: list[list[float]], y: list[int]) -> None:
        n, d = len(X), len(X[0])
        self.mu = [sum(r[j] for r in X) / n for j in range(d)]
        self.sd = [max(math.sqrt(sum((r[j] - self.mu[j]) ** 2 for r in X) / n), 1e-6) for j in range(d)]
        Z = self._std(X)
        self.w, self.b = [0.0] * d, 0.0
        for _ in range(self.epochs):
            gw, gb = [0.0] * d, 0.0
            for z, t in zip(Z, y):
                p = _sigmoid(sum(wi * zi for wi, zi in zip(self.w, z)) + self.b)
                err = p - t
                for j in range(d):
                    gw[j] += err * z[j]
                gb += err
            for j in range(d):
                self.w[j] -= self.lr * (gw[j] / n + self.l2 * self.w[j] / n)
            self.b -= self.lr * gb / n

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        return [_sigmoid(sum(wi * zi for wi, zi in zip(self.w, z)) + self.b) for z in self._std(X)]

    def to_dict(self) -> dict[str, Any]:
        return {"w": self.w, "b": self.b, "mu": self.mu, "sd": self.sd}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "_Logistic":
        m = cls()
        m.w, m.b, m.mu, m.sd = d["w"], d["b"], d["mu"], d["sd"]
        return m


def _sigmoid(x: float) -> float:
    x = max(min(x, 30.0), -30.0)
    return 1.0 / (1.0 + math.exp(-x))


class WinModel:
    def __init__(self, backend: str = "auto"):
        if backend == "auto":
            backend = "hgb" if _HAS_SK else "logistic"
        if backend == "hgb" and not _HAS_SK:
            raise RuntimeError("scikit-learn no está instalado; usa backend='logistic'")
        self.backend = backend
        self._m: Any = None

    def fit(self, X: list[list[float]], y: list[int]) -> "WinModel":
        if self.backend == "hgb":
            self._m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3, min_samples_leaf=10,
                                                     l2_regularization=1.0, early_stopping=False, random_state=7)
            self._m.fit(X, y)
        else:
            self._m = _Logistic()
            self._m.fit(X, y)
        return self

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        if not X:
            return []
        if self.backend == "hgb":
            return [float(p) for p in self._m.predict_proba(X)[:, 1]]
        return self._m.predict_proba(X)

    def to_dict(self) -> dict[str, Any]:
        if self.backend == "hgb":
            return {"backend": "hgb", "pickle_b64": base64.b64encode(pickle.dumps(self._m)).decode("ascii")}
        return {"backend": "logistic", "params": self._m.to_dict()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WinModel":
        m = cls(d["backend"])
        if d["backend"] == "hgb":
            m._m = pickle.loads(base64.b64decode(d["pickle_b64"]))
        else:
            m._m = _Logistic.from_dict(d["params"])
        return m


def brier(p: list[float], y: list[int]) -> float:
    return sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / len(y) if y else float("nan")


def logloss(p: list[float], y: list[int]) -> float:
    eps = 1e-6
    return -sum(yi * math.log(max(pi, eps)) + (1 - yi) * math.log(max(1 - pi, eps)) for pi, yi in zip(p, y)) / len(y) \
        if y else float("nan")
