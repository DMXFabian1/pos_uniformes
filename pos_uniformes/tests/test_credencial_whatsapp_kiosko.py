"""Credencial de bienvenida por WhatsApp al registrar un cliente en el kiosko.

Sin base de datos: sesión, render y apertura de URL son falsos.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QGuiApplication, QImage
from PyQt6.QtWidgets import QApplication, QDialog

from pos_uniformes.services.clientes import credencial_whatsapp_service as cws
from pos_uniformes.services.clientes.identidad_service import ClienteEncontrado
from pos_uniformes.ui.dialogs import credencial_whatsapp_dialog as cwd
from pos_uniformes.ui.dialogs.cliente_rapido_dialog import ClienteRapidoDialog
from pos_uniformes.ui.helpers import quick_sale_cliente_helper as kiosko
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

ANA = ClienteEncontrado(id=7, codigo="CLI-000007", nombre="Ana López", telefono_enmascarado="•••• ••45 21")


class _Sesion:
    def __init__(self, cliente):
        self._cliente = cliente

    def get(self, _modelo, cliente_id):
        return self._cliente if self._cliente and self._cliente.id == cliente_id else None


def _cliente(telefono="667 123 4521"):
    return SimpleNamespace(id=7, nombre="Ana López Hernández", telefono=telefono, codigo_cliente="CLI-000007")


class ServicioTests(unittest.TestCase):
    def test_telefono_como_lo_pide_whatsapp(self) -> None:
        for entrada, esperado in (
            ("667 123 4521", "526671234521"),
            ("(667) 123-4521", "526671234521"),
            ("5216671234521", "526671234521"),
            ("526671234521", "526671234521"),
            ("123", ""),
            ("", ""),
            (None, ""),
        ):
            with self.subTest(entrada=entrada):
                self.assertEqual(cws.normalizar_telefono(entrada), esperado)

    def test_mensaje_de_bienvenida_sin_promesas(self) -> None:
        texto = cws.mensaje_bienvenida("Ana López Hernández", "CLI-000007", "Maximoda")
        self.assertIn("¡Hola Ana!", texto)
        self.assertIn("Maximoda", texto)
        self.assertIn("CLI-000007", texto)
        for prohibido in ("%", "descuento", "Descuento", "gratis"):
            self.assertNotIn(prohibido, texto)

    def test_enlace_de_whatsapp_web_con_el_chat_y_el_texto(self) -> None:
        url = cws.enlace_web("526671234521", "Hola Ana & cía")
        self.assertTrue(url.startswith("https://web.whatsapp.com/send?phone=526671234521&text="))
        self.assertEqual(unquote(url.split("text=", 1)[1]), "Hola Ana & cía")
        self.assertNotIn("whatsapp://", url, "nada de la app de escritorio")

    def test_preparar_genera_la_credencial_y_arma_todo(self) -> None:
        render = MagicMock(return_value="/tmp/credencial.png")
        envio = cws.preparar(_Sesion(_cliente()), 7, render=render, negocio="Maximoda")
        render.assert_called_once()
        self.assertEqual((envio.telefono_wa, envio.codigo, envio.imagen), ("526671234521", "CLI-000007", Path("/tmp/credencial.png")))
        self.assertIn("Maximoda", envio.mensaje)
        self.assertIn("web.whatsapp.com/send?phone=526671234521", envio.url_web)

    def test_sin_telefono_no_genera_nada(self) -> None:
        render = MagicMock()
        with self.assertRaises(cws.SinTelefonoParaWhatsappError):
            cws.preparar(_Sesion(_cliente(telefono="")), 7, render=render, negocio="Maximoda")
        render.assert_not_called()

    def test_cliente_que_no_existe(self) -> None:
        with self.assertRaises(ValueError):
            cws.preparar(_Sesion(None), 7, render=MagicMock(), negocio="Maximoda")


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class DialogoTests(_Qt):
    def _envio(self) -> cws.EnvioCredencial:
        carpeta = Path(tempfile.mkdtemp())
        imagen = QImage(320, 200, QImage.Format.Format_RGB32)
        imagen.fill(QColor("#a84f2d"))
        ruta = carpeta / "CLI-000007.png"
        imagen.save(str(ruta))
        return cws.EnvioCredencial(7, "Ana López", "CLI-000007", "526671234521", "Hola", ruta,
                                   cws.enlace_web("526671234521", "Hola"))

    def test_un_clic_copia_abre_whatsapp_web_y_cierra(self) -> None:
        envio = self._envio()
        abrir = MagicMock(return_value=True)
        QGuiApplication.clipboard().clear()
        d = cwd.CredencialWhatsappDialog(None, envio, abrir=abrir)
        d.enviar_button.click()
        abrir.assert_called_once()
        self.assertEqual(abrir.call_args.args[0], envio.url_web)
        self.assertFalse(QGuiApplication.clipboard().image().isNull())
        self.assertTrue(d.enviado)
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))

    def test_sin_whatsapp_lo_dice_y_no_cierra(self) -> None:
        d = cwd.CredencialWhatsappDialog(None, self._envio(), abrir=MagicMock(return_value=False))
        d.enviar_button.click()
        self.assertFalse(d.enviado)
        self.assertEqual(d.paso_label.text(), cwd.SIN_WHATSAPP)
        self.assertNotEqual(d.result(), int(QDialog.DialogCode.Accepted))


class AbrirWhatsappWebTests(_Qt):
    URL = "https://web.whatsapp.com/send?phone=526671234521&text=Hola"

    def test_con_motor_web_en_una_ventana_del_programa(self) -> None:
        from pos_uniformes.ui.dialogs import visor_consulta_dialog as visor
        from pos_uniformes.ui.helpers import abrir_consultas as ac

        with patch.object(ac, "_hay_motor_web", return_value=True), \
                patch.object(visor, "mostrar_whatsapp") as ventana, \
                patch.object(ac, "_abrir_como_ventana") as edge:
            self.assertTrue(ac.abrir_whatsapp_web(self.URL))
        ventana.assert_called_once_with(self.URL, None)
        edge.assert_not_called()

    def test_sin_motor_web_en_edge_modo_aplicacion_como_el_mapa(self) -> None:
        from pos_uniformes.ui.helpers import abrir_consultas as ac

        with patch.object(ac, "_hay_motor_web", return_value=False), \
                patch.object(ac, "ruta_edge", return_value=Path("C:/Edge/msedge.exe")), \
                patch.object(ac.subprocess, "Popen") as popen, \
                patch.object(ac.QDesktopServices, "openUrl") as navegador:
            self.assertTrue(ac.abrir_whatsapp_web(self.URL))
        self.assertIn(f"--app={self.URL}", popen.call_args.args[0])
        navegador.assert_not_called()

    def test_sin_edge_en_el_navegador(self) -> None:
        from pos_uniformes.ui.helpers import abrir_consultas as ac

        with patch.object(ac, "_hay_motor_web", return_value=False), \
                patch.object(ac, "ruta_edge", return_value=None), \
                patch.object(ac.QDesktopServices, "openUrl", return_value=True) as navegador:
            self.assertTrue(ac.abrir_whatsapp_web(self.URL))
        self.assertEqual(navegador.call_args.args[0].toString(), self.URL)

    def test_se_presenta_como_chrome(self) -> None:
        from pos_uniformes.ui.dialogs.visor_consulta_dialog import agente_chrome

        qt = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "QtWebEngine/6.10.0 Chrome/134.0.6998.208 Safari/537.36")
        self.assertEqual(
            agente_chrome(qt),
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.6998.208 Safari/537.36",
        )


class SoloConClientesNuevosTests(_Qt):
    def _widget(self):
        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-2"
        return w

    def _dialogo(self, es_nuevo):
        class _D:
            def __init__(self_inner, *a, **k):
                self_inner.elegido = ANA
                self_inner.es_nuevo = es_nuevo

            def exec(self_inner):
                return int(QDialog.DialogCode.Accepted)

        return patch.object(kiosko, "ClienteRapidoDialog", _D)

    def test_registrado_aqui_ofrece_la_credencial(self) -> None:
        w = self._widget()
        with self._dialogo(True), patch.object(w, "_identificar_cliente"), \
                patch.object(w, "_ofrecer_credencial_whatsapp") as ofrecer:
            w._btn_cliente.click()
        ofrecer.assert_called_once_with(7)

    def test_elegido_de_la_lista_no(self) -> None:
        w = self._widget()
        with self._dialogo(False), patch.object(w, "_identificar_cliente"), \
                patch.object(w, "_ofrecer_credencial_whatsapp") as ofrecer:
            w._btn_cliente.click()
        ofrecer.assert_not_called()

    def test_el_dialogo_marca_si_es_nuevo(self) -> None:
        d = ClienteRapidoDialog(None, buscar=lambda t: [ANA], registrar=lambda *a: ANA)
        d.nombre_input.setText("Ana López")
        d.telefono_input.setText("6671234521")
        d.registrar_button.click()
        self.assertTrue(d.es_nuevo)
        e = ClienteRapidoDialog(None, buscar=lambda t: [ANA], registrar=lambda *a: ANA)
        e.busqueda_input.setText("ana")
        e._on_buscar()
        e.elegir_button.click()
        self.assertFalse(e.es_nuevo)

    def test_sin_telefono_avisa_y_no_abre_nada(self) -> None:
        w = self._widget()

        class _Ctx:
            def __enter__(self_inner):
                return _Sesion(_cliente(telefono=""))

            def __exit__(self_inner, *a):
                return False

        with patch("pos_uniformes.database.connection.get_session", return_value=_Ctx()), \
                patch.object(kiosko.QMessageBox, "information") as aviso, \
                patch.object(cwd, "CredencialWhatsappDialog") as dialogo:
            w._ofrecer_credencial_whatsapp(7)
        aviso.assert_called_once()
        dialogo.assert_not_called()



class ArranqueDelKioskoTests(unittest.TestCase):
    """Sin AA_ShareOpenGLContexts antes de crear la app, el motor web no carga
    después y WhatsApp Web abre en el navegador, fuera del programa (Mac,
    2026-11-10)."""

    def test_el_kiosko_deja_listo_el_motor_web_antes_de_crear_la_app(self) -> None:
        import inspect

        from pos_uniformes import presupuestos_satelite_main as kiosko_main

        fuente = inspect.getsource(kiosko_main.main)
        atributo = fuente.find("AA_ShareOpenGLContexts")
        self.assertNotEqual(atributo, -1)
        self.assertLess(atributo, fuente.find("QApplication(sys.argv)"))

    def test_whatsapp_se_puede_usar_con_avisos_abiertos(self) -> None:
        import inspect

        from pos_uniformes.ui.dialogs.visor_consulta_dialog import VisorWhatsapp

        self.assertIn("ApplicationModal", inspect.getsource(VisorWhatsapp.__init__))


if __name__ == "__main__":
    unittest.main()
