"""Tests para trabajo_dispatcher y los emisores de trabajos_service (Fase 1).

Todo sin Qt: la Session y los handlers se inyectan. Un engine SQLite en memoria
compartido simula la Postgres (las sesiones que abre/cierra el despachador ven
los mismos datos porque el pool singleton reusa la conexión).
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.services.trabajo_dispatcher import TrabajoDispatcher


class EmisorTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = Session(engine)

    def tearDown(self) -> None:
        self.session.close()

    def test_enviar_ticket(self) -> None:
        t = svc.enviar_ticket(self.session, "TICKET\nDEMO", origen="kiosko")
        self.assertEqual(t.tipo, TipoTrabajo.TICKET)
        self.assertEqual(t.estado, EstadoTrabajo.PENDIENTE)
        self.assertEqual(t.origen, "kiosko")
        self.assertEqual(t.contenido, {"texto": "TICKET\nDEMO"})

    def test_enviar_ticket_vacio_falla(self) -> None:
        with self.assertRaises(ValueError):
            svc.enviar_ticket(self.session, "   ")

    def test_enviar_tickets_ignora_vacios(self) -> None:
        creados = svc.enviar_tickets(self.session, ["A", "", "  ", "B"])
        self.assertEqual(len(creados), 2)
        self.assertEqual([t.contenido["texto"] for t in creados], ["A", "B"])

    def test_texto_de_ticket(self) -> None:
        t = svc.enviar_ticket(self.session, "HOLA")
        self.assertEqual(svc.texto_de_ticket(t), "HOLA")

    def test_texto_de_ticket_tipo_incorrecto(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.ETIQUETA, {"sku": "X"})
        with self.assertRaises(ValueError):
            svc.texto_de_ticket(t)


class DispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = lambda: Session(self.engine)
        self.impresos: list[str] = []
        self.eventos: list[tuple[int, EstadoTrabajo, str | None]] = []

    def _ticket_handler(self, trabajo) -> None:
        self.impresos.append(svc.texto_de_ticket(trabajo))

    def _dispatcher(self, handlers=None, **kw) -> TrabajoDispatcher:
        if handlers is None:
            handlers = {TipoTrabajo.TICKET: self._ticket_handler}
        return TrabajoDispatcher(
            self.session_factory,
            handlers,
            on_event=lambda tid, estado, err: self.eventos.append((tid, estado, err)),
            **kw,
        )

    def _seed(self, texto: str) -> int:
        s = self.session_factory()
        t = svc.enviar_ticket(s, texto)
        s.commit()
        tid = t.id
        s.close()
        return tid

    def test_poll_once_imprime_y_marca_hecho(self) -> None:
        tid = self._seed("TICKET 1")
        disp = self._dispatcher()
        resultado = disp.poll_once()
        self.assertEqual(resultado, EstadoTrabajo.HECHO)
        self.assertEqual(self.impresos, ["TICKET 1"])
        # Estado persistido
        s = self.session_factory()
        self.assertEqual(svc.obtener(s, tid).estado, EstadoTrabajo.HECHO)
        s.close()

    def test_poll_once_cola_vacia_devuelve_none(self) -> None:
        self.assertIsNone(self._dispatcher().poll_once())

    def test_handler_reclama_en_proceso_antes_de_imprimir(self) -> None:
        self._seed("X")
        visto = {}

        def handler(trabajo):
            visto["estado"] = trabajo.estado

        self._dispatcher({TipoTrabajo.TICKET: handler}).poll_once()
        # Al momento de imprimir, el trabajo ya estaba reclamado (EN_PROCESO).
        self.assertEqual(visto["estado"], EstadoTrabajo.EN_PROCESO)

    def test_handler_que_falla_marca_error(self) -> None:
        tid = self._seed("ROMPE")

        def handler(trabajo):
            raise RuntimeError("impresora sin papel")

        # max_intentos=1 => un solo fallo va directo a ERROR (sin reintento).
        disp = self._dispatcher({TipoTrabajo.TICKET: handler}, max_intentos=1)
        resultado = disp.poll_once()
        self.assertEqual(resultado, EstadoTrabajo.ERROR)
        s = self.session_factory()
        t = svc.obtener(s, tid)
        self.assertEqual(t.estado, EstadoTrabajo.ERROR)
        self.assertEqual(t.error_msg, "impresora sin papel")
        s.close()

    def test_sin_handler_para_tipo_marca_error(self) -> None:
        # Dispatcher que dice atender TICKET pero sin función handler real.
        s = self.session_factory()
        t = svc.enviar_ticket(s, "X")
        s.commit()
        tid = t.id
        s.close()
        disp = TrabajoDispatcher(
            self.session_factory, {}, tipos=[TipoTrabajo.TICKET], max_intentos=1
        )
        self.assertEqual(disp.poll_once(), EstadoTrabajo.ERROR)
        s = self.session_factory()
        self.assertEqual(svc.obtener(s, tid).estado, EstadoTrabajo.ERROR)
        s.close()

    def test_drain_procesa_todos(self) -> None:
        for i in range(4):
            self._seed(f"T{i}")
        disp = self._dispatcher()
        n = disp.drain()
        self.assertEqual(n, 4)
        self.assertEqual(self.impresos, ["T0", "T1", "T2", "T3"])
        self.assertIsNone(disp.poll_once())

    def test_solo_atiende_tipos_configurados(self) -> None:
        # Un despachador de solo TICKET no toca una ETIQUETA pendiente.
        s = self.session_factory()
        etq = svc.encolar(s, TipoTrabajo.ETIQUETA, {"sku": "X"})
        s.commit()
        etq_id = etq.id
        s.close()
        disp = self._dispatcher()  # solo TICKET
        self.assertIsNone(disp.poll_once())
        s = self.session_factory()
        self.assertEqual(svc.obtener(s, etq_id).estado, EstadoTrabajo.PENDIENTE)
        s.close()

    def test_on_event_se_dispara(self) -> None:
        tid = self._seed("X")
        self._dispatcher().poll_once()
        self.assertEqual(self.eventos, [(tid, EstadoTrabajo.HECHO, None)])


class DispatcherLoopTests(unittest.TestCase):
    """El loop start/stop con un `schedule` falso (sin Qt)."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = lambda: Session(self.engine)
        self.impresos: list[str] = []

    def test_start_requiere_schedule(self) -> None:
        disp = TrabajoDispatcher(self.session_factory, {})
        with self.assertRaises(RuntimeError):
            disp.start()

    def test_loop_drena_y_luego_idlea(self) -> None:
        # schedule síncrono controlado: ejecutamos ticks a mano.
        pendientes: list = []

        def schedule(delay_ms, cb):
            pendientes.append((delay_ms, cb))

        for i in range(2):
            s = self.session_factory()
            svc.enviar_ticket(s, f"T{i}")
            s.commit()
            s.close()

        disp = TrabajoDispatcher(
            self.session_factory,
            {TipoTrabajo.TICKET: lambda t: self.impresos.append(svc.texto_de_ticket(t))},
            schedule=schedule,
        )
        disp.start()
        # Ejecutar ticks encolados hasta que el loop empiece a idlear (delay > 0).
        delays = []
        for _ in range(10):
            if not pendientes:
                break
            delay, cb = pendientes.pop(0)
            delays.append(delay)
            if delay > 0:  # ya llegó al idle: la cola está vacía
                disp.stop()
                break
            cb()
        self.assertEqual(self.impresos, ["T0", "T1"])
        self.assertIn(0, delays)  # drenó de inmediato
        self.assertTrue(any(d > 0 for d in delays))  # luego idleó


if __name__ == "__main__":
    unittest.main()
