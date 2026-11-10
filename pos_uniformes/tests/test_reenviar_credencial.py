"""Reenviar la credencial desde la búsqueda de clientes del kiosko, por si al
cliente se le borró (Daniel, 2026-11-10). Sin base de datos.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services.clientes import credencial_whatsapp_service as cws
from pos_uniformes.services.clientes.identidad_service import ClienteEncontrado
from pos_uniformes.ui.dialogs import credencial_whatsapp_dialog as cwd
from pos_uniformes.ui.dialogs.cliente_rapido_dialog import ClienteRapidoDialog
from pos_uniformes.ui.helpers import quick_sale_cliente_helper as kiosko
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

ANA = ClienteEncontrado(id=7, codigo="CLI-000007", nombre="Ana López", telefono_enmascarado="•••• ••45 21")
LUIS = ClienteEncontrado(id=9, codigo="CLI-000009", nombre="Luis Ruiz", telefono_enmascarado="•••• ••00 11")


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class BotonTests(_Qt):
    def test_reenvia_al_seleccionado_sin_elegirlo_ni_cerrar(self) -> None:
        reenviar = MagicMock()
        d = ClienteRapidoDialog(None, buscar=lambda t: [ANA, LUIS], registrar=MagicMock(), reenviar=reenviar)
        self.assertFalse(d.reenviar_button.isHidden())
        self.assertFalse(d.reenviar_button.isEnabled(), "sin resultados no hay a quién")
        d.busqueda_input.setText("a")
        d._on_buscar()
        d.resultados.setCurrentRow(1)
        d.reenviar_button.click()
        reenviar.assert_called_once_with(LUIS)
        self.assertIsNone(d.elegido)
        self.assertFalse(d.es_nuevo)
        self.assertEqual(d.result(), 0, "la búsqueda sigue abierta")

    def test_sin_quien_reenvie_no_hay_boton(self) -> None:
        d = ClienteRapidoDialog(None, buscar=lambda t: [ANA], registrar=MagicMock())
        self.assertTrue(d.reenviar_button.isHidden())


class KioskoTests(_Qt):
    def _widget(self):
        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-2"
        return w

    def test_el_kiosko_conecta_el_reenvio(self) -> None:
        w = self._widget()
        capturado = {}

        class _D:
            def __init__(self_inner, *a, **k):
                capturado.update(k)
                self_inner.elegido = None

            def exec(self_inner):
                capturado["reenviar"](ANA)
                return 0

        with patch.object(kiosko, "ClienteRapidoDialog", _D), \
                patch.object(w, "_ofrecer_credencial_whatsapp") as ofrecer:
            w._btn_cliente.click()
        self.assertEqual(ofrecer.call_args.args, (7,))
        self.assertTrue(ofrecer.call_args.kwargs["reenvio"])
        self.assertIsInstance(ofrecer.call_args.kwargs["encima"], _D)

    def test_reenvio_con_mensaje_de_reenvio_y_sin_proponer(self) -> None:
        w = self._widget()
        envio = SimpleNamespace()
        with patch("pos_uniformes.database.connection.get_session", MagicMock()), \
                patch.object(cws, "preparar", return_value=envio) as preparar, \
                patch.object(cwd, "CredencialWhatsappDialog") as dialogo:
            w._ofrecer_credencial_whatsapp(7, reenvio=True)
        self.assertTrue(preparar.call_args.kwargs["reenvio"])
        self.assertTrue(dialogo.call_args.kwargs["reenvio"])
        self.assertNotIn("proponer", dialogo.call_args.kwargs)

    def test_whatsapp_cuelga_del_kiosko_no_de_la_busqueda(self) -> None:
        w = self._widget()
        encima = MagicMock()
        with patch("pos_uniformes.database.connection.get_session", MagicMock()), \
                patch.object(cws, "preparar", return_value=SimpleNamespace()), \
                patch.object(cwd, "CredencialWhatsappDialog") as dialogo, \
                patch("pos_uniformes.ui.helpers.abrir_consultas.abrir_whatsapp_web", return_value=True) as abrir:
            w._ofrecer_credencial_whatsapp(7, reenvio=True, encima=encima)
            self.assertIs(dialogo.call_args.args[0], encima)
            dialogo.call_args.kwargs["abrir"]("https://web.whatsapp.com/send?phone=1", encima)
        abrir.assert_called_once_with("https://web.whatsapp.com/send?phone=1", w)


class MensajeTests(unittest.TestCase):
    def test_mensaje_de_reenvio(self) -> None:
        texto = cws.mensaje_reenvio("Ana López", "CLI-000007", "Maximoda", "Maximoda Club")
        self.assertIn("¡Hola Ana!", texto)
        self.assertIn("Te reenviamos tu credencial", texto)
        self.assertIn("CLI-000007", texto)
        self.assertIn("Maximoda Club", texto)
        self.assertNotIn("registrarte", texto)
        for prohibido in ("%", "descuento", "Descuento", "gratis"):
            self.assertNotIn(prohibido, texto)

    def test_preparar_con_reenvio(self) -> None:
        cliente = SimpleNamespace(id=7, nombre="Ana López", telefono="6671234521", codigo_cliente="CLI-000007")
        sesion = SimpleNamespace(get=lambda _m, _i: cliente)
        envio = cws.preparar(sesion, 7, render=lambda c: "/tmp/c.png", negocio="Maximoda", reenvio=True)
        self.assertIn("Te reenviamos", envio.mensaje)


if __name__ == "__main__":
    unittest.main()
