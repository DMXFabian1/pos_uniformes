"""T-A5 (E1-A): un cliente SIN nivel no rompe la lista de Clientes, el resumen
de Marketing, la API `by-qr` ni el texto de la credencial.

La API se prueba con SQLite en memoria; el listado real con la base local de
prueba (127.0.0.1/pos_uniformes_test) dentro de una transacción que se
deshace al final.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QTableWidget
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.main import app
from pos_uniformes.database.models import Cliente, NivelLealtad, TipoCliente, Usuario
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.ui.helpers.settings_marketing_helper import build_settings_marketing_summary_label
from pos_uniformes.ui.main_window import MainWindow
from pos_uniformes.utils.config import settings


def _cliente(codigo: str, nivel: NivelLealtad | None) -> Cliente:
    return Cliente(
        id=abs(hash(codigo)) % 100000,
        codigo_cliente=codigo,
        nombre=f"Cliente {codigo}",
        tipo_cliente=TipoCliente.GENERAL,
        descuento_preferente=Decimal("0.00"),
        nivel_lealtad=nivel,
        telefono="6671234567",
        activo=True,
        updated_at=datetime.now(timezone.utc),
    )


class ResumenMarketingTests(unittest.TestCase):
    def test_cuenta_sin_nivel_aparte(self) -> None:
        texto = build_settings_marketing_summary_label([NivelLealtad.BASICO, None, NivelLealtad.LEAL, None])
        self.assertIn("Clientes registrados: 4", texto)
        self.assertIn("BASICO: 1", texto)
        self.assertIn("Sin nivel: 2", texto)
        self.assertNotIn("None", texto)

    def test_sin_clientes_sin_nivel_el_texto_no_cambia(self) -> None:
        texto = build_settings_marketing_summary_label([NivelLealtad.BASICO])
        self.assertEqual(
            texto, "Clientes registrados: 1\nBASICO: 1 | LEAL: 0 | PROFESOR: 0 | MAYORISTA: 0"
        )

    def test_refresh_de_main_window(self) -> None:
        app = QApplication.instance() or QApplication([])  # noqa: F841
        falso = SimpleNamespace(settings_marketing_summary_label=QLabel())
        sesion = SimpleNamespace(scalars=lambda _q: SimpleNamespace(all=lambda: [None, NivelLealtad.PROFESOR]))
        MainWindow._refresh_marketing_summary(falso, sesion)
        self.assertIn("Sin nivel: 1", falso.settings_marketing_summary_label.text())


class ListaYCredencialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_lista_de_clientes_carga_con_un_cliente_sin_nivel(self) -> None:
        # E1-C3 (C10): la lista ya no tiene columna Nivel (D5) y se arma con
        # `admin_service.listar_para_admin`. Se conserva la intención: la lista
        # carga sin fallar con clientes con y sin nivel, y ninguno muestra nivel.
        from PyQt6.QtWidgets import QComboBox

        from pos_uniformes.services.clientes import admin_service

        estado = QComboBox()
        estado.addItem("Activos", admin_service.ESTADO_ACTIVOS)
        falso = SimpleNamespace(
            user_id=1,
            settings_clients_search_input=QLineEdit(),
            settings_clients_status_label=QLabel(),
            settings_clients_table=QTableWidget(0, 11),
            settings_clients_estado_combo=estado,
            settings_clients_tipo_combo=QComboBox(),
            settings_clients_origen_combo=QComboBox(),
        )
        filas = [
            admin_service.FilaClienteAdmin(id=i, codigo=codigo, nombre="Ana", telefono="", tipo="", origen="",
                                           alta=None, activo=True, archivado=False, notas="")
            for i, codigo in ((1, "CLI-SN1"), (2, "CLI-B1"))
        ]
        with patch("pos_uniformes.ui.main_window.admin_service.listar_para_admin", return_value=filas), patch(
            "pos_uniformes.ui.main_window.tipos_para_combo", return_value=[]
        ), patch("pos_uniformes.ui.main_window.QrGenerator.exists_for_client", return_value=False):
            MainWindow._refresh_settings_clients(falso, session=object())
        tabla = falso.settings_clients_table
        self.assertEqual(tabla.rowCount(), 2)
        celdas = {tabla.item(r, c).text() for r in range(2) for c in range(tabla.columnCount())}
        self.assertFalse(celdas & {"Sin nivel", "BASICO"})

    def test_texto_de_credencial_no_falla(self) -> None:
        # E1-C2 (C10): el bloqueo temporal de E1-B («Disponible en E1-C») se
        # sustituye por la credencial estándar. Un cliente sin nivel recibe la
        # misma credencial que todos, con su código y sin línea de nivel; el
        # render no escribe en la ficha y el nivel sigue vacío.
        qr = MagicMock(return_value=("6671234567", Path("qr.png"), ""))
        falso = SimpleNamespace(_prepare_client_qr_delivery=qr)
        cliente = _cliente("CLI-SN2", None)
        with patch("pos_uniformes.ui.main_window.CustomerCardService") as tarjeta:
            tarjeta.render_for_client.return_value = Path("CLI-SN2_card.png")
            telefono, ruta_entrega, nota = MainWindow._prepare_client_card_delivery(falso, cliente)
            ruta, mensaje = MainWindow._render_client_card_safe(falso, cliente)
        self.assertEqual((telefono, ruta_entrega), ("6671234567", Path("CLI-SN2_card.png")))
        self.assertIn("CLI-SN2", nota)
        self.assertNotIn("Nivel", nota)
        self.assertEqual((ruta, mensaje), (Path("CLI-SN2_card.png"), None))
        self.assertEqual(tarjeta.render_for_client.call_count, 2)
        tarjeta.render_and_attach.assert_not_called()
        qr.assert_called_once()
        self.assertIsNone(cliente.nivel_lealtad)
        self.assertIsNone(getattr(cliente, "card_image_path", None))


class ApiByQrTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Usuario.__table__.create(engine)
        Cliente.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        self.session.add_all([_cliente("CLI-SN3", None), _cliente("CLI-L3", NivelLealtad.LEAL)])
        self.session.commit()
        app.dependency_overrides[get_db] = lambda: self.session
        app.dependency_overrides[get_current_employee] = lambda: (SimpleNamespace(codigo="VEND-1"), None)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()

    # E1-C4 (C10): la respuesta ya no lleva `nivel_lealtad`, `descuento_preferente`,
    # `tipo_cliente` ni el telefono completo (D5, P2). Se conserva la intención:
    # el endpoint responde bien con fichas con y sin nivel, y ambas igual.

    def test_cliente_sin_nivel_responde_null(self) -> None:
        r = self.client.get("/api/v1/clients/by-qr/CLI-SN3")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("nivel_lealtad", r.json())
        self.assertEqual(r.json()["codigo_cliente"], "CLI-SN3")

    def test_cliente_con_nivel_no_cambia(self) -> None:
        r = self.client.get("/api/v1/clients/by-qr/CLI-L3")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(set(r.json()), {"id", "codigo_cliente", "nombre", "tipo", "telefono_enmascarado"})


class ListadoEnPostgresTests(unittest.TestCase):
    """El listado real (`ClientService.list_clients`) con un cliente sin nivel."""

    def setUp(self) -> None:
        url = make_url(settings.database_url)
        if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "pos_uniformes_test":
            self.skipTest("Solo corre contra la base local de prueba.")
        self.engine = create_engine(url)
        self.addCleanup(self.engine.dispose)
        self.conn = self.engine.connect()
        self.addCleanup(self.conn.close)
        self.tx = self.conn.begin()
        self.addCleanup(self.tx.rollback)  # nada queda escrito
        self.session = Session(bind=self.conn)
        self.addCleanup(self.session.close)

    def test_cliente_sin_nivel_aparece_y_conserva_vacio(self) -> None:
        cliente = Cliente(
            codigo_cliente="CLI-E1A-SN",
            nombre="Prueba E1A sin nivel",
            tipo_cliente=TipoCliente.GENERAL,
            descuento_preferente=Decimal("0.00"),
            activo=True,
        )
        self.session.add(cliente)
        self.session.flush()
        self.session.refresh(cliente)
        self.assertIsNone(cliente.nivel_lealtad, "se asignó un nivel por omisión")
        encontrados = ClientService.list_clients(self.session, "Prueba E1A sin nivel")
        self.assertIn(cliente.id, [c.id for c in encontrados])


if __name__ == "__main__":
    unittest.main()
