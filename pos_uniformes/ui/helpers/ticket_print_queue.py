"""Cola de impresion de tickets.

Imprime cada ticket como un job independiente (el autocutter corta entre
cada uno) con una pausa entre jobs para que el spooler procese el anterior.

Disenada para dos cosas:

1. Un solo "Imprimir" envia TODOS los tickets (ticket + copia, cliente +
   copia tienda). Antes cada copia abria su propio dialogo y obligaba a
   hacer clic en Imprimir dos veces.
2. Segura ante el cierre del dialogo: si el QDialog se destruye
   (WA_DeleteOnClose) mientras hay un QTimer pendiente, la cola no toca
   widgets ya muertos -> evita el RuntimeError que tumbaba el proceso.

No depende de Qt: el scheduler (timer) y el actualizador de estado se
inyectan, de modo que la logica se puede testear sin un event loop real.
"""

from __future__ import annotations

from typing import Callable

DEFAULT_INTER_TICKET_DELAY_MS = 1500  # pausa entre jobs (spooler/autocutter)
DEFAULT_COOLDOWN_MS = 3000            # antes de re-habilitar el boton


class TicketPrintQueue:
    """Imprime una lista de tickets como jobs separados, uno tras otro."""

    def __init__(
        self,
        tickets: list[str],
        *,
        print_fn: Callable[[str], bool],
        schedule: Callable[[int, Callable[[], None]], None],
        on_status: Callable[[str], None] | None = None,
        on_done: Callable[[int, int], None] | None = None,
        idle_label: str = "Imprimir",
        inter_ticket_delay_ms: int = DEFAULT_INTER_TICKET_DELAY_MS,
        cooldown_ms: int = DEFAULT_COOLDOWN_MS,
    ) -> None:
        self._tickets = [t for t in tickets if t and t.strip()]
        self._print_fn = print_fn
        self._schedule = schedule
        self._on_status = on_status
        self._on_done = on_done
        self._idle_label = idle_label
        self._inter_ticket_delay_ms = inter_ticket_delay_ms
        self._cooldown_ms = cooldown_ms

        self._n = len(self._tickets)
        self._idx = 0
        self._errors = 0
        self._printing = False
        self._closed = False

    # ── API ────────────────────────────────────────────────────────────────

    @property
    def ticket_count(self) -> int:
        return self._n

    def is_printing(self) -> bool:
        return self._printing

    def close(self) -> None:
        """El dialogo se cerro: no volver a tocar sus widgets."""
        self._closed = True

    def start(self) -> None:
        """Arranca la impresion de todos los tickets (idempotente)."""
        if self._printing or self._closed or self._n == 0:
            return
        self._printing = True
        self._idx = 0
        self._errors = 0
        self._print_next()

    # ── Interno ──────────────────────────────────────────────────────────────

    def _safe_status(self, text: str) -> None:
        if self._closed or self._on_status is None:
            return
        try:
            self._on_status(text)
        except RuntimeError:
            # El widget ya fue destruido por WA_DeleteOnClose.
            self._closed = True

    def _print_next(self) -> None:
        if self._closed:
            return

        if self._idx >= self._n:
            ok = self._n - self._errors
            self._safe_status(self._done_label(ok))
            self._printing = False
            if self._on_done is not None and not self._closed:
                try:
                    self._on_done(ok, self._errors)
                except RuntimeError:
                    self._closed = True
            self._schedule(self._cooldown_ms, self._reset)
            return

        self._safe_status(self._progress_label(self._idx))
        try:
            if not self._print_fn(self._tickets[self._idx]):
                self._errors += 1
        except Exception:  # noqa: BLE001 — un ticket que falla no debe abortar la cola
            self._errors += 1

        self._idx += 1
        # El ultimo ticket no necesita esperar al siguiente.
        delay = self._inter_ticket_delay_ms if self._idx < self._n else 0
        self._schedule(delay, self._print_next)

    def _reset(self) -> None:
        self._safe_status(self._idle_label)

    def _progress_label(self, idx: int) -> str:
        if self._n <= 1:
            return "Imprimiendo…"
        return f"Imprimiendo {idx + 1}/{self._n}…"

    def _done_label(self, ok: int) -> str:
        if self._n <= 1:
            return "✓ Impreso"
        return f"✓ {ok} impresos"
