"""Tests de la capa de vista de la cola (Fase 2) y de reimprimir."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.services import trabajo_queue_view_service as view


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class EtiquetasTests(unittest.TestCase):
    def test_estado_label_depende_del_tipo(self) -> None:
        self.assertEqual(
            view.estado_label(EstadoTrabajo.EN_PROCESO, TipoTrabajo.TICKET), "Imprimiendo"
        )
        self.assertEqual(
            view.estado_label(EstadoTrabajo.EN_PROCESO, TipoTrabajo.PEDIDO), "Preparando"
        )
        self.assertEqual(
            view.estado_label(EstadoTrabajo.HECHO, TipoTrabajo.TICKET), "Impreso"
        )
        self.assertEqual(
            view.estado_label(EstadoTrabajo.HECHO, TipoTrabajo.PEDIDO), "Listo"
        )
        self.assertEqual(
            view.estado_label(EstadoTrabajo.PENDIENTE, TipoTrabajo.TICKET), "En espera"
        )

    def test_tipo_label(self) -> None:
        self.assertEqual(view.tipo_label(TipoTrabajo.ETIQUETA), "Etiqueta")


class ResumenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_resumen_ticket_es_primera_linea(self) -> None:
        t = svc.enviar_ticket(self.session, "\n  \nMAXIMODA\nProducto x1")
        self.assertEqual(view.resumen(t), "MAXIMODA")

    def test_resumen_etiqueta(self) -> None:
        t = svc.encolar(
            self.session,
            TipoTrabajo.ETIQUETA,
            {"sku": "SKU1", "copies": 3, "paper_mode": "standard"},
        )
        self.assertEqual(view.resumen(t), "SKU1 · 3 copia(s) · standard")

    def test_resumen_conteo(self) -> None:
        t = svc.encolar(
            self.session,
            TipoTrabajo.CONTEO,
            {"hojas": ["h1", "h2"], "titulo": "Conteo Primaria"},
        )
        self.assertEqual(view.resumen(t), "Conteo Primaria · 2 hoja(s)")

    def test_resumen_pedido_cuenta_items(self) -> None:
        t = svc.encolar(self.session, TipoTrabajo.PEDIDO, {"items": [1, 2, 3]})
        self.assertEqual(view.resumen(t), "3 artículo(s)")


class RowViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_acciones_pendiente(self) -> None:
        svc.enviar_ticket(self.session, "X")
        row = view.listar_para_vista(self.session)[0]
        self.assertTrue(row.puede_cancelar)
        self.assertFalse(row.puede_reintentar)
        self.assertFalse(row.puede_reimprimir)

    def test_acciones_hecho(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        svc.marcar_hecho(self.session, t.id)
        row = view.listar_para_vista(self.session)[0]
        self.assertFalse(row.puede_cancelar)
        self.assertTrue(row.puede_reimprimir)

    def test_acciones_error(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        svc.marcar_error(self.session, t.id, "sin papel")
        row = view.listar_para_vista(self.session)[0]
        self.assertTrue(row.puede_reintentar)
        self.assertEqual(row.error_msg, "sin papel")

    def test_orden_y_filtros(self) -> None:
        svc.enviar_ticket(self.session, "A", origen="principal")
        b = svc.encolar(self.session, TipoTrabajo.ETIQUETA, {"sku": "B"}, origen="kiosko")
        rows = view.listar_para_vista(self.session, tipos=[TipoTrabajo.ETIQUETA])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, b.id)
        self.assertEqual(rows[0].origen, "kiosko")

    def test_contar_por_estado(self) -> None:
        a = svc.enviar_ticket(self.session, "A")
        svc.enviar_ticket(self.session, "B")
        svc.marcar_hecho(self.session, a.id)
        conteo = view.contar_por_estado(self.session)
        self.assertEqual(conteo[EstadoTrabajo.PENDIENTE], 1)
        self.assertEqual(conteo[EstadoTrabajo.HECHO], 1)
        self.assertEqual(conteo[EstadoTrabajo.ERROR], 0)


class ReimprimirTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_reimprimir_clona_como_pendiente(self) -> None:
        t = svc.enviar_ticket(self.session, "TICKET", origen="kiosko")
        svc.marcar_hecho(self.session, t.id)
        copia = svc.reimprimir(self.session, t.id)
        # El original sigue HECHO; la copia es nueva y PENDIENTE.
        self.assertNotEqual(copia.id, t.id)
        self.assertEqual(copia.estado, EstadoTrabajo.PENDIENTE)
        self.assertEqual(copia.tipo, TipoTrabajo.TICKET)
        self.assertEqual(copia.contenido, {"texto": "TICKET"})
        self.assertEqual(copia.origen, "kiosko")
        self.assertEqual(svc.obtener(self.session, t.id).estado, EstadoTrabajo.HECHO)

    def test_reimprimir_id_inexistente(self) -> None:
        with self.assertRaises(ValueError):
            svc.reimprimir(self.session, 9999)


if __name__ == "__main__":
    unittest.main()
