"""Equivalencias provisionales de tallas para el subflujo deportivo."""

from __future__ import annotations

from dataclasses import dataclass
import re

_NUMERIC_SIZE_RE = re.compile(r"^\d+$")
_RANGE_SIZE_RE = re.compile(r"^\d+\s*-\s*\d+$")
_ALPHA_SIZE_ORDER = ("CH", "CH-MD", "MD", "GD", "GD-EXG", "EXG")
_RANGE_SIZE_ORDER = ("0-0", "0-2", "3-5", "6-8", "9-12", "13-18")
_NUMERIC_SIZE_ORDER = ("2", "4", "6", "8", "10", "12", "14", "16")


@dataclass(frozen=True)
class SportsUniformSizeGuidance:
    pants_size: str
    recommended_sizes: tuple[str, ...]
    selected_playera_size: str = ""
    match_level: str = "sin_referencia"


def build_sports_uniform_size_guidance(
    pants_size: object,
    playera_size: object | None = None,
) -> SportsUniformSizeGuidance:
    normalized_pants_size = normalize_sports_uniform_size(pants_size)
    normalized_playera_size = normalize_sports_uniform_size(playera_size)
    recommended_sizes = recommend_playera_sizes_for_pants(normalized_pants_size)
    match_level = classify_playera_size_match(
        normalized_pants_size,
        normalized_playera_size,
        recommended_sizes=recommended_sizes,
    )
    return SportsUniformSizeGuidance(
        pants_size=normalized_pants_size,
        recommended_sizes=recommended_sizes,
        selected_playera_size=normalized_playera_size,
        match_level=match_level,
    )


def recommend_playera_sizes_for_pants(pants_size: object) -> tuple[str, ...]:
    normalized_size = normalize_sports_uniform_size(pants_size)
    if not normalized_size:
        return ()

    if normalized_size in _ALPHA_SIZE_ORDER:
        return _neighboring_sizes(_ALPHA_SIZE_ORDER, normalized_size)
    if normalized_size in _RANGE_SIZE_ORDER:
        return _neighboring_sizes(_RANGE_SIZE_ORDER, normalized_size)
    if normalized_size in _NUMERIC_SIZE_ORDER:
        return _neighboring_sizes(_NUMERIC_SIZE_ORDER, normalized_size)
    if _NUMERIC_SIZE_RE.match(normalized_size):
        return (normalized_size,)
    if _RANGE_SIZE_RE.match(normalized_size):
        return (normalized_size,)
    return (normalized_size,)


def classify_playera_size_match(
    pants_size: object,
    playera_size: object,
    *,
    recommended_sizes: tuple[str, ...] | None = None,
) -> str:
    normalized_pants_size = normalize_sports_uniform_size(pants_size)
    normalized_playera_size = normalize_sports_uniform_size(playera_size)
    if not normalized_pants_size or not normalized_playera_size:
        return "sin_referencia"

    suggested_sizes = recommended_sizes or recommend_playera_sizes_for_pants(normalized_pants_size)
    if normalized_playera_size == normalized_pants_size:
        return "exacta"
    if normalized_playera_size in suggested_sizes:
        return "sugerida"
    if not suggested_sizes:
        return "sin_referencia"
    return "atipica"


def build_sports_uniform_size_hint(
    pants_size: object,
    playera_size: object | None = None,
) -> str:
    guidance = build_sports_uniform_size_guidance(pants_size, playera_size)
    if not guidance.pants_size:
        return "Sin referencia de talla para esta maqueta."

    suggested_text = ", ".join(guidance.recommended_sizes) if guidance.recommended_sizes else "sin referencia"
    if not guidance.selected_playera_size:
        return f"Maqueta talla: pants {guidance.pants_size}; playeras sugeridas {suggested_text}."
    if guidance.match_level == "exacta":
        return f"Maqueta talla: pants {guidance.pants_size} con playera {guidance.selected_playera_size} (exacta)."
    if guidance.match_level == "sugerida":
        return f"Maqueta talla: pants {guidance.pants_size} con playera {guidance.selected_playera_size} (sugerida)."
    if guidance.match_level == "atipica":
        return (
            f"Maqueta talla: pants {guidance.pants_size} con playera {guidance.selected_playera_size} "
            f"(atipica; sugeridas {suggested_text})."
        )
    return f"Maqueta talla: pants {guidance.pants_size}; playeras sugeridas {suggested_text}."


def normalize_sports_uniform_size(value: object) -> str:
    normalized = " ".join(str(value or "").strip().upper().split())
    return normalized.replace(" - ", "-")


def _neighboring_sizes(ordered_sizes: tuple[str, ...], selected_size: str) -> tuple[str, ...]:
    try:
        index = ordered_sizes.index(selected_size)
    except ValueError:
        return (selected_size,)

    candidates = [ordered_sizes[index]]
    if index + 1 < len(ordered_sizes):
        candidates.append(ordered_sizes[index + 1])
    if index - 1 >= 0:
        candidates.append(ordered_sizes[index - 1])
    return tuple(candidates)
