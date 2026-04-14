"""Helpers para decidir cierres seguros de ventanas principales."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowCloseDecision:
    should_block: bool
    title: str
    message: str


def build_main_window_close_decision(*, is_busy: bool) -> WindowCloseDecision:
    if is_busy:
        return WindowCloseDecision(
            should_block=True,
            title="Operacion en progreso",
            message=(
                "Hay un proceso en curso. Espera a que termine antes de cerrar la aplicacion."
            ),
        )
    return WindowCloseDecision(
        should_block=False,
        title="Cerrar POS Uniformes",
        message="Se cerrara la aplicacion actual. Quieres continuar?",
    )
