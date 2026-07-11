"""Tests de la Fase 5: pedidos (tablero), transiciones y que el despachador los ignore."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo
from pos_uniformes.services import trabajo_queue_view_service as view
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.services.trabajo_dispatcher import TrabajoDispatcher


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class EnviarPedidoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_enviar_pedido(self) -> None:
        t = svc.enviar_pedido(
            self.session,
            [{"sku": "SKU1", "cantidad": 2}],
            cliente="Ana",
            nota="urge",
            origen="kiosko",
        )
        self.assertEqual(t.tipo, TipoTrabajo.PEDIDO)
        self.assertEqual(t.estado, EstadoTrabajo.PENDIENTE)
        d = svc.datos_de_pedido(t)
        self.assertEqual(d["cliente"], "Ana")
        self.assertEqual(d["nota"], "urge")
        self.assertEqual(len(d["items"]), 1)

    def test_enviar_pedido_vacio_falla(self) -> None:
        with self.assertRaises(ValueError):
            svc.enviar_pedido(self.session, [], cliente="", nota="")

    def test_enviar_pedido_solo_nota(self) -> None:
        t = svc.enviar_pedido(self.session, [], nota="traer cajas")
        self.assertEqual(svc.datos_de_pedido(t)["nota"], "traer cajas")


class TransicionesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_tomar_y_marcar_listo(self) -> None:
        t = svc.enviar_pedido(self.session, [{"sku": "X"}])
        svc.tomar_pedido(self.session, t.id)
        self.assertEqual(svc.obtener(self.session, t.id).estado, EstadoTrabajo.EN_PROCESO)
        svc.marcar_pedido_listo(self.session, t.id)
        listo = svc.obtener(self.session, t.id)
        self.assertEqual(listo.estado, EstadoTrabajo.HECHO)
        self.assertIsNotNone(listo.procesado_en)

    def test_no_tomar_dos_veces(self) -> None:
        t = svc.enviar_pedido(self.session, [{"sku": "X"}])
        svc.tomar_pedido(self.session, t.id)
        with self.assertRaises(ValueError):
            svc.tomar_pedido(self.session, t.id)

    def test_no_marcar_listo_sin_tomar(self) -> None:
        t = svc.enviar_pedido(self.session, [{"sku": "X"}])
        with self.assertRaises(ValueError):
            svc.marcar_pedido_listo(self.session, t.id)

    def test_tomar_no_pedido_falla(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        with self.assertRaises(ValueError):
            svc.tomar_pedido(self.session, t.id)


class DispatcherIgnoraPedidoTests(unittest.TestCase):
    def test_despachador_no_toca_pedidos(self) -> None:
        from pos_uniformes.ui.helpers.trabajo_print_handlers import build_handlers

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        factory = lambda: Session(engine)
        s = factory()
        p = svc.enviar_pedido(s, [{"sku": "X"}])
        s.commit()
        pid = p.id
        s.close()

        disp = TrabajoDispatcher(factory, build_handlers())
        self.assertIsNone(disp.poll_once())  # no hay handler PEDIDO -> no lo reclama
        s = factory()
        self.assertEqual(svc.obtener(s, pid).estado, EstadoTrabajo.PENDIENTE)
        s.close()


class ColumnasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_pedidos_por_columna(self) -> None:
        a = svc.enviar_pedido(self.session, [{"sku": "A"}])
        b = svc.enviar_pedido(self.session, [{"sku": "B"}])
        c = svc.enviar_pedido(self.session, [{"sku": "C"}])
        svc.tomar_pedido(self.session, b.id)
        svc.tomar_pedido(self.session, c.id)
        svc.marcar_pedido_listo(self.session, c.id)
        cols = view.pedidos_por_columna(self.session)
        self.assertEqual([r.id for r in cols["pendiente"]], [a.id])
        self.assertEqual([r.id for r in cols["preparando"]], [b.id])
        self.assertEqual([r.id for r in cols["listo"]], [c.id])

    def test_resumen_pedido_con_cliente(self) -> None:
        t = svc.enviar_pedido(self.session, [{"sku": "A"}, {"sku": "B"}], cliente="Ana")
        self.assertEqual(view.resumen(t), "Ana · 2 artículo(s)")


class BoardDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def _seed(self, **kw) -> int:
        s = self.factory()
        t = svc.enviar_pedido(s, [{"sku": "X"}], **kw)
        s.commit()
        tid = t.id
        s.close()
        return tid

    def _board(self):
        from pos_uniformes.ui.dialogs.pedido_board_dialog import PedidoBoardDialog

        return PedidoBoardDialog(session_factory=self.factory, auto_refresh_ms=0)

    def test_pedido_aparece_en_por_preparar(self) -> None:
        self._seed(cliente="Ana")
        board = self._board()
        self.assertEqual(board._listas["pendiente"].count(), 1)
        self.assertEqual(board._listas["preparando"].count(), 0)

    def test_tomar_mueve_a_preparando(self) -> None:
        tid = self._seed()
        board = self._board()
        board._selected_id = tid
        board._tomar()
        self.assertEqual(board._listas["pendiente"].count(), 0)
        self.assertEqual(board._listas["preparando"].count(), 1)

    def test_flujo_completo_a_listo(self) -> None:
        tid = self._seed()
        board = self._board()
        board._selected_id = tid
        board._tomar()
        board._selected_id = tid
        board._marcar_listo()
        self.assertEqual(board._listas["listo"].count(), 1)
        s = self.factory()
        self.assertEqual(svc.obtener(s, tid).estado, EstadoTrabajo.HECHO)
        s.close()

    def test_cancelar_pedido(self) -> None:
        tid = self._seed()
        board = self._board()
        board._selected_id = tid
        with patch(
            "pos_uniformes.ui.dialogs.pedido_board_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            board._cancelar()
        s = self.factory()
        self.assertEqual(svc.obtener(s, tid).estado, EstadoTrabajo.CANCELADO)
        s.close()


if __name__ == "__main__":
    unittest.main()
