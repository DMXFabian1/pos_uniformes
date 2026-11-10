"""E1-B (R1, R2): formulario de cliente y credenciales (T-B11, T-B13,
T-B22, T-B23, T-B24).

E1-C2 (C10): el bloqueo temporal de credenciales sin nivel se sustituye por
la credencial estándar; las pruebas de credencial se ajustaron a eso.
"""

from __future__ import annotations

import os
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QDoubleSpinBox, QWidget
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, NivelLealtad, RolUsuario, TipoCliente, Usuario
from pos_uniformes.services.clientes import identidad_service as ids
from pos_uniformes.services.settings_client_action_service import create_settings_client, update_settings_client
from pos_uniformes.ui.dialogs import settings_prompt_dialogs as prompts
from pos_uniformes.ui.main_window import MainWindow
from pos_uniformes.utils.config import settings

_CARD = "pos_uniformes.ui.main_window.CustomerCardService.render_for_client"
_ATTACH = "pos_uniformes.ui.main_window.CustomerCardService.render_and_attach"


def _cliente(nivel):
    return Cliente(id=5, codigo_cliente="CLI-000005", nombre="Ana", tipo_cliente=TipoCliente.GENERAL,
                   descuento_preferente=Decimal("0.00"), nivel_lealtad=nivel, telefono="6671234567", activo=True)


def _ctx_vacio():
    class _Ctx:
        def __enter__(self_inner):
            return SimpleNamespace()

        def __exit__(self_inner, *a):
            return False

    return _Ctx()


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class FormularioClienteTests(_Qt):
    """T-B11 y T-B13."""

    def _abrir(self, **kw):
        capturado = {}

        def ejecutar(dialog):
            spin = dialog.findChild(QDoubleSpinBox)
            capturado["habilitado"] = spin.isEnabled()
            capturado["valor"] = spin.value()
            spin.setValue(33.0)  # aunque alguien lo forzara, el servicio lo ignora
            return int(QDialog.DialogCode.Accepted)

        with patch.object(prompts.QDialog, "exec", ejecutar):
            datos = prompts.prompt_client_data(QWidget(), title="t", helper_text="h", **kw)
        return capturado, datos

    def test_tb11_alta_con_descuento_bloqueado_en_cero(self) -> None:
        cap, _ = self._abrir(descuento_bloqueado=True)
        self.assertFalse(cap["habilitado"])
        self.assertEqual(cap["valor"], 0.0)

    def test_tb13_edicion_sin_nivel_bloquea_y_muestra_el_valor_actual(self) -> None:
        actuales = {"nombre": "Ana", "tipo_cliente": "GENERAL", "descuento_preferente": "0.00", "telefono": "", "notas": ""}
        cap, _ = self._abrir(current_values=actuales, descuento_bloqueado=True)
        self.assertFalse(cap["habilitado"])
        self.assertEqual(cap["valor"], 0.0)

    def test_tb13_sin_el_parametro_el_formulario_es_el_de_hoy(self) -> None:
        cap, _ = self._abrir()
        self.assertTrue(cap["habilitado"])
        self.assertEqual(cap["valor"], 5.0)  # sugerencia de hoy para GENERAL
        actuales = {"nombre": "Ana", "tipo_cliente": "PROFESOR", "descuento_preferente": "15.00", "telefono": "", "notas": ""}
        cap, _ = self._abrir(current_values=actuales)
        self.assertTrue(cap["habilitado"])
        self.assertEqual(cap["valor"], 15.0)

    def test_tb11_main_window_pide_el_formulario_bloqueado_al_crear(self) -> None:
        # E1-C1 (C10): Configuración ya no abre `prompt_client_data` sino la ficha
        # nueva, que no tiene campo de descuento. Se conserva la intención: el alta
        # del ADMIN no captura descuento.
        falso = SimpleNamespace(current_role=RolUsuario.ADMIN)
        with patch("pos_uniformes.ui.main_window.get_session", return_value=_ctx_vacio()), patch(
            "pos_uniformes.ui.main_window.tipos_para_combo", return_value=[("GENERAL", "General")]
        ), patch("pos_uniformes.ui.main_window.prompt_cliente_ficha", return_value=None) as prompt:
            MainWindow._handle_create_client(falso)
        prompt.assert_called_once()
        self.assertNotIn("descuento_bloqueado", prompt.call_args.kwargs)
        self.assertIsNone(prompt.call_args.kwargs.get("current_values"))


class EdicionDesdeMainWindowTests(_Qt):
    """T-B13: al editar, el formulario se bloquea solo si el cliente no tiene nivel."""

    # E1-C1 (C10): la edición abre la ficha nueva (identidad y tipo). Con o sin
    # nivel, el formulario ya no ofrece descuento: los niveles quedan congelados
    # (D5) y la edición no los toca. Antes, con nivel, el descuento era editable.

    def _editar(self, nivel):
        cliente = _cliente(nivel)
        falso = SimpleNamespace(current_role=RolUsuario.ADMIN, _selected_settings_client_id=lambda: 5)
        ficha = {"nombre": "Ana", "telefono": "6671234567", "tipo_clave": "", "notas": "", "activo": "1", "archivado": "0"}
        with patch("pos_uniformes.ui.main_window.get_session", return_value=_ctx_vacio()), patch(
            "pos_uniformes.ui.main_window.cargar_ficha", return_value=ficha
        ), patch("pos_uniformes.ui.main_window.tipos_para_combo", return_value=[("GENERAL", "General")]), patch(
            "pos_uniformes.ui.main_window.prompt_cliente_ficha", return_value=None
        ) as prompt:
            MainWindow._handle_update_client(falso)
        self.assertEqual(cliente.nivel_lealtad, nivel)
        return prompt.call_args.kwargs

    def test_sin_nivel_bloquea(self) -> None:
        kwargs = self._editar(None)
        self.assertNotIn("descuento_bloqueado", kwargs)
        self.assertNotIn("descuento_preferente", kwargs["current_values"])

    def test_con_nivel_no_cambia(self) -> None:
        kwargs = self._editar(NivelLealtad.BASICO)
        self.assertNotIn("descuento_bloqueado", kwargs)
        self.assertNotIn("descuento_preferente", kwargs["current_values"])


class CredencialesTests(_Qt):
    """T-B22 y T-B23, ajustadas en E1-C2: credencial estándar para todos."""

    def test_tb22_render_bloqueado_sin_nivel(self) -> None:
        # Antes: bloqueada con «Disponible en E1-C». Ahora: credencial estándar.
        cliente = _cliente(None)
        with patch(_CARD, return_value=Path("credencial.png")) as render, patch(_ATTACH) as adjuntar:
            ruta, error = MainWindow._render_client_card_safe(SimpleNamespace(), cliente)
        self.assertEqual(ruta, Path("credencial.png"))
        self.assertIsNone(error)
        render.assert_called_once_with(cliente)
        adjuntar.assert_not_called()
        self.assertIsNone(cliente.card_image_path)
        self.assertIsNone(cliente.nivel_lealtad)

    def test_tb22_con_nivel_se_genera_como_hoy(self) -> None:
        # Con nivel viejo se genera la MISMA credencial estándar (D5).
        with patch(_CARD, return_value=Path("credencial.png")) as render, patch(_ATTACH) as adjuntar:
            ruta, error = MainWindow._render_client_card_safe(SimpleNamespace(), _cliente(NivelLealtad.LEAL))
        self.assertEqual(ruta, Path("credencial.png"))
        self.assertIsNone(error)
        render.assert_called_once()
        adjuntar.assert_not_called()

    def test_tb23_whatsapp_de_credencial_bloqueado(self) -> None:
        # Antes: WhatsApp de credencial bloqueado sin nivel. Ahora se prepara
        # con la credencial estándar y el mensaje lleva el código, sin nivel.
        cliente = _cliente(None)
        falso = SimpleNamespace(
            _selected_settings_client_id=lambda: 5,
            _normalize_whatsapp_phone=lambda t: t,
            _get_whatsapp_templates=lambda: {"client_promotion": "", "client_greeting": "", "client_followup": "Hola"},
            _reveal_path=lambda p: None,
        )
        falso._prepare_client_qr_delivery = lambda c: MainWindow._prepare_client_qr_delivery(falso, c)
        falso._prepare_client_card_delivery = lambda c: MainWindow._prepare_client_card_delivery(falso, c)
        sesion = SimpleNamespace(get=lambda _m, _i: cliente, commit=lambda: None)

        class _Ctx:
            def __enter__(self_inner):
                return sesion

            def __exit__(self_inner, *a):
                return False

        with patch("pos_uniformes.ui.main_window.get_session", return_value=_Ctx()), patch(
            _CARD, return_value=Path("credencial.png")
        ) as render, patch("pos_uniformes.ui.main_window.QrGenerator.path_for_client", return_value=Path(__file__)), patch(
            "pos_uniformes.ui.main_window.prompt_client_whatsapp_data", return_value=("followup", "")
        ), patch("pos_uniformes.ui.main_window.QMessageBox.information"), patch(
            "pos_uniformes.ui.main_window.QMessageBox.warning"
        ) as aviso, patch("pos_uniformes.ui.main_window.webbrowser.open", return_value=True) as navegador:
            MainWindow._handle_open_client_whatsapp(falso)
        aviso.assert_not_called()
        render.assert_called_once_with(cliente)
        url = navegador.call_args.args[0]
        self.assertIn("CLI-000005", url)
        self.assertNotIn("Nivel", url)
        self.assertNotIn("Descuento", url)


class AccionesDeConfiguracionTests(_Qt):
    """T-B24: crear y editar en Configuración no generan credencial sin nivel."""

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
        admin = Usuario(username=f"e1b_admin_{uuid.uuid4().hex[:6]}", nombre_completo="Admin E1-B", password_hash="x",
                        rol=RolUsuario.ADMIN, activo=True)
        self.s.add(admin)
        self.s.flush()
        self.admin_id = admin.id
        self.render = lambda c: MainWindow._render_client_card_safe(SimpleNamespace(), c)

    def test_crear_y_editar(self) -> None:
        payload = {"nombre": "Cliente E1-B", "tipo_cliente": "GENERAL", "descuento_preferente": "0.00",
                   "telefono": "9988776655", "notas": ""}
        with patch(_CARD) as card:
            creado = create_settings_client(self.s, admin_user_id=self.admin_id, payload=payload, render_card=self.render)
            cliente = self.s.query(Cliente).filter_by(codigo_cliente=creado.client_code).one()
            editado = update_settings_client(self.s, admin_user_id=self.admin_id, client_id=cliente.id,
                                             payload={**payload, "nombre": "Cliente E1-B editado", "descuento_preferente": "10.00"},
                                             render_card=self.render)
        # E1-C2 (C10): estas funciones viejas siguen intactas; con el render de
        # la pantalla ahora generan la credencial estándar (aquí simulada).
        self.assertEqual(card.call_count, 2)
        self.assertIsNotNone(creado.card_path)
        self.assertIsNone(creado.card_error)
        self.assertIsNone(editado.card_error)
        self.s.refresh(cliente)
        self.assertIsNone(cliente.nivel_lealtad)
        self.assertEqual(Decimal(cliente.descuento_preferente), Decimal("0.00"))
        self.assertEqual(cliente.origen_alta, ids.ORIGEN_POS_ADMIN)


if __name__ == "__main__":
    unittest.main()
