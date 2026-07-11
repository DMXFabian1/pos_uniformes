"""Tests de la Fase 6: reintentos con backoff, limpieza y resiliencia."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.services.trabajo_dispatcher import TrabajoDispatcher


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class RegistrarFalloTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_reprograma_antes_del_tope(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        futuro = datetime(2999, 1, 1)
        r = svc.registrar_fallo(self.session, t.id, "falló", max_intentos=3, disponible_en=futuro)
        self.assertEqual(r.estado, EstadoTrabajo.PENDIENTE)
        self.assertEqual(r.intentos, 1)
        self.assertEqual(r.error_msg, "falló")
        self.assertIsNone(r.procesado_en)
        self.assertEqual(r.disponible_en, futuro)

    def test_error_al_alcanzar_el_tope(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        svc.registrar_fallo(self.session, t.id, "1", max_intentos=2, disponible_en=datetime(2999, 1, 1))
        r = svc.registrar_fallo(self.session, t.id, "2", max_intentos=2, disponible_en=datetime(2999, 1, 1))
        self.assertEqual(r.estado, EstadoTrabajo.ERROR)
        self.assertEqual(r.intentos, 2)
        self.assertIsNone(r.disponible_en)
        self.assertIsNotNone(r.procesado_en)


class DisponibleEnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_no_reclama_si_disponible_en_futuro(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        t.disponible_en = datetime(2999, 1, 1)
        self.session.flush()
        self.assertIsNone(svc.reclamar_siguiente(self.session))
        self.assertIsNone(svc.siguiente_pendiente(self.session))

    def test_reclama_si_disponible_en_pasado(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        t.disponible_en = datetime(2000, 1, 1)
        self.session.flush()
        reclamado = svc.reclamar_siguiente(self.session)
        self.assertIsNotNone(reclamado)
        self.assertEqual(reclamado.id, t.id)


class LimpiezaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def _con_fecha(self, trabajo_id: int, fecha: datetime) -> None:
        t = svc.obtener(self.session, trabajo_id)
        t.created_at = fecha
        self.session.flush()

    def test_borra_hechos_viejos_conserva_recientes_y_pendientes(self) -> None:
        ahora = datetime(2026, 1, 30)
        viejo = svc.enviar_ticket(self.session, "viejo")
        svc.marcar_hecho(self.session, viejo.id)
        self._con_fecha(viejo.id, datetime(2026, 1, 1))  # 29 días atrás

        reciente = svc.enviar_ticket(self.session, "reciente")
        svc.marcar_hecho(self.session, reciente.id)
        self._con_fecha(reciente.id, datetime(2026, 1, 29))  # ayer

        pendiente_viejo = svc.enviar_ticket(self.session, "pendiente")
        self._con_fecha(pendiente_viejo.id, datetime(2025, 1, 1))  # viejísimo pero PENDIENTE

        borrados = svc.limpiar_trabajos_viejos(self.session, dias=7, ahora=ahora)
        self.assertEqual(borrados, 1)
        self.assertIsNone(svc.obtener(self.session, viejo.id))
        self.assertIsNotNone(svc.obtener(self.session, reciente.id))
        self.assertIsNotNone(svc.obtener(self.session, pendiente_viejo.id))


class DispatcherReintentoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def _seed(self) -> int:
        s = self.factory()
        t = svc.enviar_ticket(s, "X")
        s.commit()
        tid = t.id
        s.close()
        return tid

    def test_reintenta_hasta_error(self) -> None:
        tid = self._seed()
        intentos = {"n": 0}

        def handler(_t):
            intentos["n"] += 1
            raise RuntimeError("siempre falla")

        # Reloj en el pasado => el backoff queda disponible de inmediato,
        # así drain() reintenta sin esperar de verdad.
        disp = TrabajoDispatcher(
            self.factory,
            {TipoTrabajo.TICKET: handler},
            max_intentos=3,
            now_fn=lambda: datetime(2000, 1, 1),
        )
        disp.drain()
        self.assertEqual(intentos["n"], 3)  # 3 intentos y a ERROR
        s = self.factory()
        t = svc.obtener(s, tid)
        self.assertEqual(t.estado, EstadoTrabajo.ERROR)
        self.assertEqual(t.intentos, 3)
        s.close()

    def test_backoff_no_reintenta_de_inmediato(self) -> None:
        tid = self._seed()

        def handler(_t):
            raise RuntimeError("falla")

        # Reloj en el futuro => disponible_en queda en el futuro => no se
        # vuelve a reclamar en el mismo drain.
        disp = TrabajoDispatcher(
            self.factory,
            {TipoTrabajo.TICKET: handler},
            max_intentos=3,
            now_fn=lambda: datetime(2999, 1, 1),
        )
        resultado = disp.poll_once()
        self.assertEqual(resultado, EstadoTrabajo.PENDIENTE)  # reprogramado, no ERROR
        self.assertIsNone(disp.poll_once())  # aún no disponible
        s = self.factory()
        t = svc.obtener(s, tid)
        self.assertEqual(t.estado, EstadoTrabajo.PENDIENTE)
        self.assertEqual(t.intentos, 1)
        s.close()


class ResilienciaTests(unittest.TestCase):
    def test_poll_once_none_si_falla_la_sesion(self) -> None:
        def factory_rota():
            raise ConnectionError("DB caída")

        disp = TrabajoDispatcher(factory_rota, {})
        self.assertIsNone(disp.poll_once())  # no lanza; el loop reintentará

    def test_drain_no_muere_si_falla_la_sesion(self) -> None:
        def factory_rota():
            raise ConnectionError("DB caída")

        disp = TrabajoDispatcher(factory_rota, {})
        self.assertEqual(disp.drain(), 0)


if __name__ == "__main__":
    unittest.main()
