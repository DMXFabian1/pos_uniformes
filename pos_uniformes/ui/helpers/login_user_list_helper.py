"""Opciones visibles de usuario para el login."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class LoginUserOption:
    user_id: int
    username: str
    display_label: str


def _normalize_login_display_name(full_name: str) -> str:
    suffix = " pos uniformes"
    normalized = full_name.strip()
    if normalized.lower().endswith(suffix):
        normalized = normalized[: -len(suffix)].rstrip(" -|/")
    return normalized or full_name.strip()


def build_login_user_options(users: Iterable[object]) -> list[LoginUserOption]:
    options: list[LoginUserOption] = []
    for user in users:
        if not bool(getattr(user, "activo", False)):
            continue
        username = str(getattr(user, "username", "") or "").strip()
        if not username:
            continue
        full_name = str(getattr(user, "nombre_completo", "") or username).strip()
        options.append(
            LoginUserOption(
                user_id=int(getattr(user, "id")),
                username=username,
                display_label=_normalize_login_display_name(full_name),
            )
        )
    return options
