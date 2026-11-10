"""E1-C3 (T-N11): ficha de solo lectura y lista del ADMIN.

Las pruebas con base corren en una transacción que se revierte.
"""

from __future__ import annotations

import os
import unittest
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QPushButton, QTabWidget, QTableWidget
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pos_uniformes.database.models import ClienteEvento, LibretaVenta, RolUsuario, Usuario
from pos_uniformes.services.clientes import admin_service as adm
from pos_uniformes.services.clientes import ficha_service
from pos_uniformes.services.clientes import identidad_service as ids
from pos_uniformes.ui.dialogs.cliente_ficha_dialog import PROGRAMAS_PENDIENTES, construir_ficha_dialog
from pos_uniformes.ui.helpers.settings_clients_helper import CLIENTES_ADMIN_COLUMNAS
from pos_uniformes.ui.main_window import MainWindow
from pos_uniformes.utils.config import settings


class FichaServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        url = make_url(settings.database_url)
        if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "pos_uniformes_test":
            self.skipTest("Solo corre contra la base local de prueba.")
        self.engine = create_engine(url)
        self.addCleanup(self.engine.dispose)
        self.conn = self.engine.connect()
        self.addCleanup(self.conn.close)
        self.tx = self.conn.begin()
        self.addCleanup(self.tx.rollback)
        self.s = Session(bind=self.conn, join_transaction_mode="create_savepoint")
        self.addCleanup(self.s.close)
        self.admin = Usuario(username=f"e1c3_{uuid.uuid4().hex[:6]}", nombre_completo="Admin", password_hash="x",
                             rol=RolUsuario.ADMIN, activo=True)
        self.cajero = Usuario(username=f"e1c3c_{uuid.uuid4().hex[:6]}", nombre_completo="Cajero", password_hash="x",
                              rol=RolUsuario.CAJERO, activo=True)
        self.s.add_all([self.admin, self.cajero])
        self.s.flush()
        self.cliente = ids.dar_de_alta(self.s, nombre="Ficha E1C3", telefono=f"66{uuid.uuid4().int % 10**8:08d}",
                                       origen=ids.ORIGEN_VENTA_RAPIDA, tipo_clave="DOCENTE", usuario_id=self.admin.id)
        for i, privado in enumerate((False, False, True)):
            self.s.add(LibretaVenta(employee_code="E01", employee_name="Lupita", tipo="venta", piezas=i + 1,
                                    monto_total=Decimal("100.00") * (i + 1), monto_neto=Decimal("100.00"),
                                    privado=privado, detalle=[], cliente_id=self.cliente.id))
        self.s.flush()

    def _conteos(self):
        return (
            self.s.scalar(select(func.count(LibretaVenta.id)).where(LibretaVenta.cliente_id == self.cliente.id)),
            self.s.scalar(select(func.count(ClienteEvento.id)).where(ClienteEvento.cliente_id == self.cliente.id)),
        )

    def test_ficha_junta_historial_sin_privadas_y_sin_escribir(self) -> None:
        antes = self._conteos()
        ficha = ficha_service.cargar_ficha(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id)
        self.assertEqual(self._conteos(), antes, "la ficha no debe escribir nada")
        self.assertEqual((ficha.tipo, ficha.origen), ("Docente", ids.ORIGEN_VENTA_RAPIDA))
        self.assertEqual(len(ficha.libreta), 2)
        self.assertEqual(ficha.libreta_privadas, 1)
        self.assertNotIn("$300.00", [f.columnas[3] for f in ficha.libreta])
        self.assertEqual(ficha.ventas, [])
        self.assertEqual(ficha.apartados, [])
        self.assertEqual(ficha.eventos[0].columnas[0], ids.EVENTO_ALTA)
        self.assertEqual(ficha.eventos[0].columnas[2], self.admin.username)

    def test_ficha_muestra_archivado_y_eventos_recientes_primero(self) -> None:
        adm.archivar(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id, motivo="Ficha de prueba")
        ficha = ficha_service.cargar_ficha(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id)
        self.assertIsNotNone(ficha.archivado_en)
        self.assertEqual(ficha.archivado_motivo, "Ficha de prueba")
        self.assertEqual([e.columnas[0] for e in ficha.eventos], [adm.EVENTO_ARCHIVADO, ids.EVENTO_ALTA])
        self.assertIn("motivo: Ficha de prueba", ficha.eventos[0].columnas[3])

    def test_solo_admin(self) -> None:
        with self.assertRaises(PermissionError):
            ficha_service.cargar_ficha(self.s, cliente_id=self.cliente.id, usuario_id=self.cajero.id)

    def test_dialogo_de_solo_lectura(self) -> None:
        self.app = QApplication.instance() or QApplication([])  # guardada: sin referencia, Qt la destruye
        ficha = ficha_service.cargar_ficha(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id)
        dialogo = construir_ficha_dialog(None, ficha)
        pestanas = dialogo.findChild(QTabWidget)
        self.assertEqual([pestanas.tabText(i) for i in range(pestanas.count())],
                         ["Datos", "Fidelizacion", "Compras", "Apartados", "Eventos"])
        textos = [l.text() for l in dialogo.findChildren(QLabel)]
        self.assertIn(PROGRAMAS_PENDIENTES, textos)
        self.assertTrue(any("1 registro(s) privado(s)" in t for t in textos))
        self.assertEqual([b.text() for b in dialogo.findChildren(QPushButton)], ["Cerrar"])


class ListaAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self):
        estado = QComboBox()
        for etiqueta, valor in (("Activos", adm.ESTADO_ACTIVOS), ("Archivados", adm.ESTADO_ARCHIVADOS)):
            estado.addItem(etiqueta, valor)
        tipo = QComboBox()
        tipo.addItem("Todos los tipos", None)
        origen = QComboBox()
        origen.addItem("Todos los origenes", None)
        return SimpleNamespace(
            user_id=1,
            settings_clients_search_input=QLineEdit(),
            settings_clients_status_label=QLabel(),
            settings_clients_table=QTableWidget(0, 11),
            settings_clients_estado_combo=estado,
            settings_clients_tipo_combo=tipo,
            settings_clients_origen_combo=origen,
        )

    def test_columnas_sin_nivel_ni_descuento_y_filtros(self) -> None:
        falso = self._ventana()
        filas = [adm.FilaClienteAdmin(id=7, codigo="CLI-000007", nombre="Ana", telefono="6671234567", tipo="Docente",
                                      origen="", alta=None, activo=True, archivado=False, notas="")]
        with patch("pos_uniformes.ui.main_window.admin_service.listar_para_admin", return_value=filas) as listar, patch(
            "pos_uniformes.ui.main_window.tipos_para_combo", return_value=[("DOCENTE", "Docente")]
        ), patch("pos_uniformes.ui.main_window.QrGenerator.exists_for_client", return_value=False), patch(
            "pos_uniformes.ui.main_window.CustomerCardService.exists_for_client", return_value=True
        ):
            falso.settings_clients_estado_combo.setCurrentIndex(1)
            MainWindow._refresh_settings_clients(falso, session=object())
        tabla = falso.settings_clients_table
        encabezados = [tabla.horizontalHeaderItem(i).text() for i in range(tabla.columnCount())]
        self.assertEqual(encabezados, list(CLIENTES_ADMIN_COLUMNAS))
        self.assertNotIn("Nivel", encabezados)
        self.assertNotIn("Desc.", encabezados)
        self.assertEqual(tabla.item(0, 2).text(), "Docente")
        self.assertEqual(tabla.item(0, 4).text(), "Anterior")
        self.assertEqual(tabla.item(0, 7).text(), "Lista")
        self.assertEqual(listar.call_args.kwargs["estado"], adm.ESTADO_ARCHIVADOS)
        self.assertEqual(falso.settings_clients_tipo_combo.count(), 2)


if __name__ == "__main__":
    unittest.main()
