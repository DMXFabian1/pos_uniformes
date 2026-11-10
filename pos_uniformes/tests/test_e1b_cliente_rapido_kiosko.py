"""E1-B: buscador y alta rápida en Venta Rápida (T-B5, T-B6, T-B7).

Sin base de datos: el diálogo recibe funciones falsas de búsqueda y registro.
"""

from __future__ import annotations

import os
import unittest
import unittest.mock
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from pos_uniformes.services.clientes.identidad_service import (
    ClienteEncontrado,
    CoincidenciasPorConfirmarError,
    TelefonoInvalidoError,
)
from pos_uniformes.ui.dialogs.cliente_rapido_dialog import ClienteRapidoDialog
from pos_uniformes.ui.helpers import quick_sale_cliente_helper as kiosko
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

D = Decimal
ANA = ClienteEncontrado(id=7, codigo="CLI-000007", nombre="Ana López", telefono_enmascarado="•••• ••45 21")


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class DialogoTests(_Qt):
    """T-B5."""

    def test_busqueda_muestra_telefono_enmascarado_y_es_esta_persona_elige(self) -> None:
        d = ClienteRapidoDialog(None, buscar=lambda t: [ANA], registrar=lambda *a: self.fail("no registra"))
        d.busqueda_input.setText("4521")
        d._on_buscar()
        texto = d.resultados.item(0).text()
        self.assertIn("•••• ••45 21", texto)
        self.assertNotIn("667", texto)
        d.elegir_button.click()
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))
        self.assertEqual(d.elegido, ANA)

    def test_alta_en_tres_pasos(self) -> None:
        llamadas = []

        def registrar(nombre, tel, confirmar):
            llamadas.append((nombre, tel, confirmar))
            return ClienteEncontrado(id=9, codigo="CLI-000009", nombre=nombre, telefono_enmascarado="•••• ••00 11")

        d = ClienteRapidoDialog(None, buscar=lambda t: [], registrar=registrar)
        d.busqueda_input.setText("Pedro")
        d._on_buscar()  # 1. buscar
        self.assertEqual(d.resultados.count(), 0)
        d.nombre_input.setText("Pedro Ruiz")  # 2. capturar
        d.telefono_input.setText("6671110011")
        d.registrar_button.click()  # 3. registrar
        self.assertEqual(llamadas, [("Pedro Ruiz", "6671110011", False)])
        self.assertEqual(d.elegido.codigo, "CLI-000009")

    def test_telefono_ya_registrado_da_error_y_no_crea(self) -> None:
        # Daniel, 2026-11-10: en el kiosko no se acepta un teléfono repetido;
        # ya no existe «Es otra persona con el mismo teléfono».
        llamadas = []

        def registrar(nombre, tel, confirmar):
            llamadas.append(confirmar)
            raise CoincidenciasPorConfirmarError([ANA])

        d = ClienteRapidoDialog(None, buscar=lambda t: [], registrar=registrar)
        d.nombre_input.setText("Hija de Ana")
        d.telefono_input.setText("6671234521")
        with patch("pos_uniformes.ui.dialogs.cliente_rapido_dialog.QMessageBox.warning") as aviso:
            d.registrar_button.click()
        aviso.assert_called_once()
        self.assertIn("Ana López", aviso.call_args.args[2])
        self.assertIsNone(d.elegido, "no debe crear")
        self.assertFalse(hasattr(d, "otra_persona_button"))
        self.assertEqual(llamadas, [False], "nunca pide confirmar un teléfono compartido")
        self.assertTrue(d.elegir_button.isEnabled())
        self.assertIn("Ana López", d.resultados.item(0).text())

    def test_telefono_obligatorio_de_10_digitos_sin_llamar_a_la_base(self) -> None:
        registrar = unittest.mock.MagicMock()
        for malo in ("", "123", "66712345", "0000000000"):
            with self.subTest(telefono=malo):
                d = ClienteRapidoDialog(None, buscar=lambda t: [], registrar=registrar)
                d.nombre_input.setText("Luis")
                d.telefono_input.setText(malo)
                with patch("pos_uniformes.ui.dialogs.cliente_rapido_dialog.QMessageBox.warning") as aviso:
                    d.registrar_button.click()
                aviso.assert_called_once()
                self.assertIsNone(d.elegido)
        registrar.assert_not_called()

    def test_telefono_invalido_avisa_y_no_registra(self) -> None:
        def registrar(*a):
            raise TelefonoInvalidoError("El teléfono debe tener 10 dígitos válidos.")

        d = ClienteRapidoDialog(None, buscar=lambda t: [], registrar=registrar)
        d.nombre_input.setText("X")
        d.telefono_input.setText("123")
        with patch("pos_uniformes.ui.dialogs.cliente_rapido_dialog.QMessageBox.warning") as aviso:
            d.registrar_button.click()
        aviso.assert_called_once()
        self.assertIsNone(d.elegido)


class _Kiosko(_Qt):
    def _widget(self, online=True):
        sat = SimpleNamespace(offline_mode=not online, _kiosk_lookup_from_cache=None, _db_online=online)
        w = QuickSaleWidget(sat)
        w._employee_code = "VEND-2"
        w._employee_name = "Fanny"
        w._items = [{"sku": "SKU1", "nombre": "Pants", "talla": "6", "color": "", "precio": D("450.00"), "cantidad": 2}]
        return w

    def _dialogo_que_elige(self, elegido):
        class _D:
            def __init__(self_inner, *a, **k):
                self_inner.elegido = elegido

            def exec(self_inner):
                return int(QDialog.DialogCode.Accepted)

        return patch.object(kiosko, "ClienteRapidoDialog", _D)


class BotonClienteTests(_Kiosko):
    def test_tb5_el_boton_abre_el_buscador_y_liga_con_identificar_cliente(self) -> None:
        w = self._widget()
        with self._dialogo_que_elige(ANA), patch.object(w, "_identificar_cliente") as ident:
            w._btn_cliente.click()
        ident.assert_called_once_with("CLI-000007", por_qr=False, cliente_id=7)

    def test_tb6_el_total_no_cambia_al_ligar_o_registrar(self) -> None:
        for descuento in (False, True):
            with self.subTest(descuento_empleada=descuento):
                w = self._widget()
                w._discount_active = descuento
                antes = w._compute_totals()
                resumen = SimpleNamespace(cliente_id=7, codigo="CLI-000007", nombre="Ana López", tiene_monedero=False,
                                          estado="sin_monedero", disponible=D("0"), tasa=None,
                                          proximo_vencimiento=None, monto_proximo_vencimiento=D("0"))

                class _Ctx:
                    def __enter__(self_inner):
                        return SimpleNamespace(get=lambda _m, _i: SimpleNamespace(id=7, activo=True))

                    def __exit__(self_inner, *a):
                        return False

                with self._dialogo_que_elige(ANA), patch(
                    "pos_uniformes.database.connection.get_session", return_value=_Ctx()
                ), patch("pos_uniformes.services.monedero_service.resumen_cliente", return_value=resumen):
                    w._btn_cliente.click()
                self.assertEqual(w._cliente["codigo"], "CLI-000007")
                self.assertEqual(w._compute_totals(), antes)

    def test_tb7_sin_conexion_no_busca_ni_registra(self) -> None:
        w = self._widget(online=False)
        with patch.object(kiosko, "ClienteRapidoDialog") as dialogo, patch(
            "pos_uniformes.database.connection.get_session"
        ) as sesion, patch("pos_uniformes.ui.helpers.quick_sale_cliente_helper.QMessageBox.information") as aviso:
            w._btn_cliente.click()
        dialogo.assert_not_called()
        sesion.assert_not_called()
        self.assertIn("Sin conexión", aviso.call_args.args[2])

    def test_registrar_desde_el_kiosko_usa_la_regla_de_venta_rapida(self) -> None:
        w = self._widget()
        capturado = {}

        def alta(session, **kw):
            capturado.update(kw)
            return SimpleNamespace(id=11, codigo_cliente="CLI-000011", nombre=kw["nombre"], telefono=kw["telefono"])

        class _Ctx:
            def __enter__(self_inner):
                return SimpleNamespace(commit=lambda: capturado.setdefault("commit", True))

            def __exit__(self_inner, *a):
                return False

        with patch("pos_uniformes.database.connection.get_session", return_value=_Ctx()), patch.object(
            kiosko.identidad_service, "dar_de_alta", side_effect=alta
        ):
            nuevo = w._registrar_cliente_identidad("Luis", "6670001122", False)
        self.assertEqual(nuevo.codigo, "CLI-000011")
        self.assertEqual(capturado["origen"], "venta_rapida")
        self.assertTrue(capturado["exigir_telefono_valido"])
        self.assertTrue(capturado["revisar_duplicados"])
        self.assertFalse(capturado["confirmar_telefono_compartido"])
        self.assertEqual(capturado["employee_code"], "VEND-2")
        self.assertTrue(capturado["commit"])


if __name__ == "__main__":
    unittest.main()
