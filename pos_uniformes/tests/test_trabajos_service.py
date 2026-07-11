"""Tests para trabajos_service — la cola de trabajos hacia el satélite (Fase 0).

Cubren el ciclo de vida completo: encolar -> reclamar (EN_PROCESO) ->
hecho/error, más cancelar, reintentar, reordenar, listar y filtros.
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo, Trabajo
from pos_uniformes.services import trabajos_service as svc


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class EncolarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_encolar_crea_pendiente_con_id(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"texto": "hola"})
        self.assertIsNotNone(t.id)
        self.assertEqual(t.estado, EstadoTrabajo.PENDIENTE)
        self.assertEqual(t.tipo, TipoTrabajo.TICKET)
        self.assertEqual(t.contenido, {"texto": "hola"})

    def test_encolar_defaults(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.ETIQUETA, {"sku": "X"})
        self.assertEqual(t.origen, "principal")
        self.assertEqual(t.creado_por, "SYSTEM")
        self.assertEqual(t.prioridad, 0)

    def test_encolar_origen_y_creado_por(self) -> None:
        t = svc.encolar(
            self.session,
            TipoTrabajo.PEDIDO,
            {"items": []},
            origen="kiosko",
            creado_por="ana",
        )
        self.assertEqual(t.origen, "kiosko")
        self.assertEqual(t.creado_por, "ana")

    def test_encolar_origen_vacio_cae_a_principal(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"x": 1}, origen="   ")
        self.assertEqual(t.origen, "principal")

    def test_encolar_rechaza_contenido_no_dict(self) -> None:
        with self.assertRaises(TypeError):
            svc.encolar(self.session, TipoTrabajo.TICKET, "no soy dict")  # type: ignore[arg-type]

    def test_encolar_rechaza_tipo_invalido(self) -> None:
        with self.assertRaises(TypeError):
            svc.encolar(self.session, "TICKET", {"x": 1})  # type: ignore[arg-type]


class ListarYOrdenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_orden_por_prioridad_luego_insercion(self) -> None:
        a = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1}, prioridad=5)
        b = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 2}, prioridad=1)
        c = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 3}, prioridad=1)
        ids = [t.id for t in svc.listar(self.session)]
        # b y c tienen prioridad 1 (b antes por id); a última por prioridad 5.
        self.assertEqual(ids, [b.id, c.id, a.id])

    def test_filtra_por_estado(self) -> None:
        p = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 2})
        svc.marcar_hecho(self.session, p.id)
        pendientes = svc.listar(self.session, estados=[EstadoTrabajo.PENDIENTE])
        self.assertEqual([t.contenido["n"] for t in pendientes], [2])

    def test_filtra_por_tipo_y_origen(self) -> None:
        svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1}, origen="principal")
        svc.encolar(self.session, TipoTrabajo.ETIQUETA, {"n": 2}, origen="kiosko")
        solo_etiq = svc.listar(self.session, tipos=[TipoTrabajo.ETIQUETA])
        self.assertEqual(len(solo_etiq), 1)
        solo_kiosko = svc.listar(self.session, origenes=["kiosko"])
        self.assertEqual(len(solo_kiosko), 1)

    def test_estados_vacio_devuelve_cero(self) -> None:
        svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        self.assertEqual(svc.listar(self.session, estados=[]), [])

    def test_limite(self) -> None:
        for i in range(5):
            svc.encolar(self.session, TipoTrabajo.TICKET, {"n": i})
        self.assertEqual(len(svc.listar(self.session, limite=2)), 2)


class ReclamarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_siguiente_pendiente_peek_no_cambia_estado(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        peek = svc.siguiente_pendiente(self.session)
        self.assertEqual(peek.id, t.id)
        self.assertEqual(peek.estado, EstadoTrabajo.PENDIENTE)

    def test_siguiente_pendiente_none_si_vacio(self) -> None:
        self.assertIsNone(svc.siguiente_pendiente(self.session))

    def test_reclamar_pasa_a_en_proceso(self) -> None:
        svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1}, prioridad=2)
        segundo = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 2}, prioridad=1)
        reclamado = svc.reclamar_siguiente(self.session)
        # El de menor prioridad se reclama primero.
        self.assertEqual(reclamado.id, segundo.id)
        self.assertEqual(reclamado.estado, EstadoTrabajo.EN_PROCESO)

    def test_reclamar_no_toma_dos_veces_el_mismo(self) -> None:
        svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        primero = svc.reclamar_siguiente(self.session)
        segundo = svc.reclamar_siguiente(self.session)
        self.assertIsNotNone(primero)
        self.assertIsNone(segundo)  # ya no hay PENDIENTE

    def test_reclamar_respeta_filtro_tipo(self) -> None:
        svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        etiq = svc.encolar(self.session, TipoTrabajo.ETIQUETA, {"n": 2})
        reclamado = svc.reclamar_siguiente(self.session, tipos=[TipoTrabajo.ETIQUETA])
        self.assertEqual(reclamado.id, etiq.id)

    def test_reclamar_none_si_vacio(self) -> None:
        self.assertIsNone(svc.reclamar_siguiente(self.session))


class FinalizarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_marcar_hecho(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        svc.reclamar_siguiente(self.session)
        hecho = svc.marcar_hecho(self.session, t.id)
        self.assertEqual(hecho.estado, EstadoTrabajo.HECHO)
        self.assertIsNotNone(hecho.procesado_en)
        self.assertIsNone(hecho.error_msg)

    def test_marcar_error_guarda_mensaje(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        err = svc.marcar_error(self.session, t.id, "impresora sin papel")
        self.assertEqual(err.estado, EstadoTrabajo.ERROR)
        self.assertEqual(err.error_msg, "impresora sin papel")
        self.assertIsNotNone(err.procesado_en)

    def test_marcar_hecho_id_inexistente(self) -> None:
        with self.assertRaises(ValueError):
            svc.marcar_hecho(self.session, 9999)


class CancelarReintentarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_cancelar_pendiente(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        cancelado = svc.cancelar(self.session, t.id)
        self.assertEqual(cancelado.estado, EstadoTrabajo.CANCELADO)

    def test_no_cancelar_hecho(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        svc.marcar_hecho(self.session, t.id)
        with self.assertRaises(ValueError):
            svc.cancelar(self.session, t.id)

    def test_reintentar_desde_error(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        svc.marcar_error(self.session, t.id, "falló")
        reintentado = svc.reintentar(self.session, t.id)
        self.assertEqual(reintentado.estado, EstadoTrabajo.PENDIENTE)
        self.assertIsNone(reintentado.error_msg)
        self.assertIsNone(reintentado.procesado_en)

    def test_reintentar_desde_cancelado(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        svc.cancelar(self.session, t.id)
        reintentado = svc.reintentar(self.session, t.id)
        self.assertEqual(reintentado.estado, EstadoTrabajo.PENDIENTE)

    def test_no_reintentar_pendiente(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        with self.assertRaises(ValueError):
            svc.reintentar(self.session, t.id)


class ReordenarYObtenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_reordenar_asigna_prioridad_por_posicion(self) -> None:
        a = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        b = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 2})
        c = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 3})
        svc.reordenar(self.session, [c.id, a.id, b.id])
        ids = [t.id for t in svc.listar(self.session)]
        self.assertEqual(ids, [c.id, a.id, b.id])
        self.assertEqual([c.prioridad, a.prioridad, b.prioridad], [0, 1, 2])

    def test_reordenar_id_inexistente(self) -> None:
        a = svc.encolar(self.session, TipoTrabajo.TICKET, {"n": 1})
        with self.assertRaises(ValueError):
            svc.reordenar(self.session, [a.id, 9999])

    def test_obtener_none_si_no_existe(self) -> None:
        self.assertIsNone(svc.obtener(self.session, 12345))


if __name__ == "__main__":
    unittest.main()
