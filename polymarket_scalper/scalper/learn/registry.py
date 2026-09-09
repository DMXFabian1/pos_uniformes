"""Versiones de modelos por tipo de señal: `data/models/<kind>/v<N>.json` y `current` -> versión promovida."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .features import FeatureSchema
from .model import WinModel


@dataclass
class ModelBundle:
    kind: str
    version: int
    schema: FeatureSchema
    model: WinModel
    n_train: int
    metrics: dict[str, Any] = field(default_factory=dict)
    trained_at: int = 0
    train_range: tuple[int, int] = (0, 0)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "version": self.version, "schema": self.schema.to_dict(), "model": self.model.to_dict(),
                "n_train": self.n_train, "metrics": self.metrics, "trained_at": self.trained_at,
                "train_range": list(self.train_range)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ModelBundle":
        return cls(d["kind"], int(d["version"]), FeatureSchema.from_dict(d["schema"]), WinModel.from_dict(d["model"]),
                   int(d["n_train"]), d.get("metrics", {}), int(d.get("trained_at", 0)),
                   tuple(d.get("train_range", (0, 0))))


class ModelStore:
    def __init__(self, data_dir: str | Path):
        self.root = Path(data_dir) / "models"

    def _dir(self, kind: str) -> Path:
        return self.root / kind

    def versions(self, kind: str) -> list[int]:
        d = self._dir(kind)
        if not d.exists():
            return []
        return sorted(int(p.stem[1:]) for p in d.glob("v*.json"))

    def save(self, bundle: ModelBundle) -> int:
        d = self._dir(bundle.kind)
        d.mkdir(parents=True, exist_ok=True)
        ver = (self.versions(bundle.kind) or [0])[-1] + 1
        bundle.version = ver
        bundle.trained_at = bundle.trained_at or int(time.time() * 1000)
        (d / f"v{ver}.json").write_text(json.dumps(bundle.to_dict()), encoding="utf-8")
        return ver

    def load(self, kind: str, version: int) -> ModelBundle | None:
        p = self._dir(kind) / f"v{version}.json"
        if not p.exists():
            return None
        return ModelBundle.from_dict(json.loads(p.read_text(encoding="utf-8")))

    def current_version(self, kind: str) -> int | None:
        p = self._dir(kind) / "current"
        if not p.exists():
            return None
        try:
            return int(p.read_text().strip())
        except ValueError:
            return None

    def load_current(self, kind: str) -> ModelBundle | None:
        v = self.current_version(kind)
        return self.load(kind, v) if v is not None else None

    def promote(self, kind: str, version: int) -> None:
        (self._dir(kind) / "current").write_text(str(version))

    def kinds(self) -> list[str]:
        return sorted(p.name for p in self.root.glob("*") if p.is_dir()) if self.root.exists() else []

    def history(self, kind: str) -> list[dict[str, Any]]:
        cur = self.current_version(kind)
        out = []
        for v in self.versions(kind):
            b = self.load(kind, v)
            if b is None:
                continue
            out.append({"version": v, "current": v == cur, "n_train": b.n_train, "trained_at": b.trained_at,
                        "backend": b.model.backend, **{k: b.metrics.get(k) for k in ("brier_val", "brier_heuristic_val",
                                                                                   "n_val", "promoted", "reason")}})
        return out
