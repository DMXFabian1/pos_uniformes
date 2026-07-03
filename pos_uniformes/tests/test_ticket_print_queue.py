"""Tests de la cola de impresion de tickets (TicketPrintQueue).

Cubren los dos sintomas reportados en venta rapida:
- Un solo "Imprimir" manda TODOS los tickets (antes pedia dos clics).
- Cerrar el dialogo mientras hay timers pendientes no toca widgets muertos
  (antes tumbaba el proceso con un RuntimeError no capturado).
"""

from __future__ import annotations

import unittest
from typing import Callable

from pos_uniformes.ui.helpers.ticket_print_queue import TicketPrintQueue


class ImmediateScheduler:
    """Ejecuta cada callback al instante: drena toda la cola en start()."""

    def __call__(self, _ms: int, fn: Callable[[], None]) -> None:
        fn()


class ManualScheduler:
    """Acumula los callbacks; se disparan a mano con run_next()."""

    def __init__(self) -> None:
        self.pending: list[Callable[[], None]] = []

    def __call__(self, _ms: int, fn: Callable[[], None]) -> None:
        self.pending.append(fn)

    def run_next(self) -> bool:
        if not self.pending:
            return False
        self.pending.pop(0)()
        return True


class TicketPrintQueueTests(unittest.TestCase):
    def test_one_start_prints_every_ticket(self) -> None:
        printed: list[str] = []
        queue = TicketPrintQueue(
            ["TICKET A", "TICKET B"],
            print_fn=lambda t: (printed.append(t), True)[1],
            schedule=ImmediateScheduler(),
        )
        queue.start()
        # Un solo start() imprimio los dos tickets, en orden.
        self.assertEqual(printed, ["TICKET A", "TICKET B"])

    def test_blank_tickets_are_dropped(self) -> None:
        printed: list[str] = []
        queue = TicketPrintQueue(
            ["", "  ", "REAL"],
            print_fn=lambda t: (printed.append(t), True)[1],
            schedule=ImmediateScheduler(),
        )
        self.assertEqual(queue.ticket_count, 1)
        queue.start()
        self.assertEqual(printed, ["REAL"])

    def test_status_sequence_for_two_tickets(self) -> None:
        statuses: list[str] = []
        queue = TicketPrintQueue(
            ["A", "B"],
            print_fn=lambda _t: True,
            schedule=ImmediateScheduler(),
            on_status=statuses.append,
            idle_label="Imprimir 2 tickets",
        )
        queue.start()
        self.assertIn("Imprimiendo 1/2…", statuses)
        self.assertIn("Imprimiendo 2/2…", statuses)
        self.assertIn("✓ 2 impresos", statuses)
        # El reset (cooldown) vuelve al estado idle.
        self.assertEqual(statuses[-1], "Imprimir 2 tickets")

    def test_failed_job_counts_as_error(self) -> None:
        done: list[tuple[int, int]] = []
        queue = TicketPrintQueue(
            ["A", "B"],
            print_fn=lambda t: t != "B",  # B falla
            schedule=ImmediateScheduler(),
            on_done=lambda ok, errors: done.append((ok, errors)),
        )
        queue.start()
        self.assertEqual(done, [(1, 1)])

    def test_raising_job_does_not_abort_queue(self) -> None:
        printed: list[str] = []

        def _print(t: str) -> bool:
            if t == "A":
                raise RuntimeError("impresora desconectada")
            printed.append(t)
            return True

        done: list[tuple[int, int]] = []
        queue = TicketPrintQueue(
            ["A", "B"],
            print_fn=_print,
            schedule=ImmediateScheduler(),
            on_done=lambda ok, errors: done.append((ok, errors)),
        )
        queue.start()  # no debe propagar la excepcion
        self.assertEqual(printed, ["B"])      # B sigue imprimiendose
        self.assertEqual(done, [(1, 1)])

    def test_close_mid_queue_stops_further_prints(self) -> None:
        printed: list[str] = []
        sched = ManualScheduler()
        queue = TicketPrintQueue(
            ["A", "B", "C"],
            print_fn=lambda t: (printed.append(t), True)[1],
            schedule=sched,
        )
        queue.start()                 # imprime A, agenda el siguiente
        self.assertEqual(printed, ["A"])
        queue.close()                 # el dialogo se cerro
        # El timer pendiente dispara, pero la cola ya no hace nada.
        while sched.run_next():
            pass
        self.assertEqual(printed, ["A"])  # B y C nunca se imprimieron

    def test_no_status_after_close(self) -> None:
        statuses: list[str] = []
        sched = ManualScheduler()
        queue = TicketPrintQueue(
            ["A"],
            print_fn=lambda _t: True,
            schedule=sched,
            on_status=statuses.append,
        )
        queue.start()
        before = len(statuses)
        queue.close()
        while sched.run_next():       # dispara el reset de cooldown pendiente
            pass
        self.assertEqual(len(statuses), before)  # ningun status tras cerrar

    def test_runtime_error_in_status_is_swallowed(self) -> None:
        """Simula acceder a un QPushButton ya destruido."""

        def _boom(_text: str) -> None:
            raise RuntimeError("wrapped C/C++ object has been deleted")

        queue = TicketPrintQueue(
            ["A", "B"],
            print_fn=lambda _t: True,
            schedule=ImmediateScheduler(),
            on_status=_boom,
        )
        # No debe propagar: el guard convierte el error en cierre silencioso.
        queue.start()

    def test_start_is_not_reentrant(self) -> None:
        printed: list[str] = []
        sched = ManualScheduler()
        queue = TicketPrintQueue(
            ["A", "B"],
            print_fn=lambda t: (printed.append(t), True)[1],
            schedule=sched,
        )
        queue.start()
        queue.start()                 # segundo clic mientras imprime: ignorado
        while sched.run_next():
            pass
        self.assertEqual(printed, ["A", "B"])  # cada ticket una sola vez


if __name__ == "__main__":
    unittest.main()
