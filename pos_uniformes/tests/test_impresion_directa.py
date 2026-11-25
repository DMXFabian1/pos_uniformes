"""Cobro en un paso (2026-11-24): el ticket de venta sale sin vista previa.

Las empleadas pedían menos toques. `route_tickets(..., directo=True)` imprime
aquí sin abrir la ventana, anota (on_printed) igual que el botón «Imprimir» y,
si algo no sale, abre la ventana de siempre solo con eso y SIN volver a anotar.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from pos_uniformes.ui.helpers import ticket_routing_helper as trh

_CACHE = "pos_uniformes.services.print_routing_cache_service"
_DLG = "pos_uniformes.ui.dialogs.printable_text_dialog.open_tickets_print_dialog"


def _inmediato(_ms, fn):
    fn()


def _sin_exec(_dlg):
    return 0


class ImpresionDirectaTests(unittest.TestCase):
    """Imprime, anota UNA vez y la ventana «✓ Cobrado» se queda abierta
    (Daniel, 2026-11-24: «por si se atora el papel o algo»)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.parent = QWidget()
        for p in (
            patch.object(QTimer, "singleShot", staticmethod(_inmediato)),
            patch.object(trh, "otras_impresoras_de_tickets", return_value=[]),
            patch.object(QDialog, "exec", _sin_exec),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_imprime_todo_anota_una_vez_y_queda_la_ventana(self) -> None:
        impresos, anotado = [], []
        with patch(_DLG) as dialogo:
            ventana = trh.imprimir_directo(
                self.parent, "Ticket de venta", ["cliente", "copia"],
                on_printed=lambda: anotado.append(1),
                print_fn=lambda t: impresos.append(t) or True,
            )
        self.assertEqual(impresos, ["cliente", "copia"])
        self.assertEqual(anotado, [1])
        dialogo.assert_not_called()
        self.assertIn("Ticket impreso", ventana.estado.text())
        self.assertTrue(ventana.otra_vez.isEnabled())

    def test_imprimir_otra_vez_no_vuelve_a_anotar(self) -> None:
        impresos, anotado = [], []
        ventana = trh.imprimir_directo(
            self.parent, "Ticket de venta", ["cliente", "copia"],
            on_printed=lambda: anotado.append(1),
            print_fn=lambda t: impresos.append(t) or True,
        )
        ventana.otra_vez.click()
        # Salió todo: «otra vez» es solo el del cliente.
        self.assertEqual(impresos, ["cliente", "copia", "cliente"])
        self.assertEqual(anotado, [1])

    def test_lo_que_no_sale_se_avisa_y_se_reimprime_eso(self) -> None:
        anotado, intentos = [], []

        def _imprime(t):
            intentos.append(t)
            return t == "cliente" or len(intentos) > 2   # la copia sale al segundo intento

        visto = {}

        def _exec(dlg):
            # Con la ventana abierta: lee el aviso y toca «Imprimir otra vez».
            from PyQt6.QtWidgets import QLabel, QPushButton

            estado = [l for l in dlg.findChildren(QLabel) if l.objectName() == "cobradoEstado"][0]
            visto["antes"] = estado.text()
            [b for b in dlg.findChildren(QPushButton) if b.objectName() == "otraVez"][0].click()
            visto["despues"] = estado.text()
            return 0

        with patch.object(QDialog, "exec", _exec):
            trh.imprimir_directo(
                self.parent, "Ticket de venta", ["cliente", "copia"],
                on_printed=lambda: anotado.append(1), print_fn=_imprime,
            )
        self.assertIn("No salió", visto["antes"])
        self.assertIn("ya quedó anotada", visto["antes"])
        # Reimprime solo lo que no salió: la copia.
        self.assertEqual(intentos, ["cliente", "copia", "copia"])
        self.assertIn("Ticket impreso", visto["despues"])
        self.assertEqual(anotado, [1])

    def test_una_excepcion_de_la_impresora_cuenta_como_no_salio(self) -> None:
        def _truena(_t):
            raise OSError("sin papel")

        ventana = trh.imprimir_directo(self.parent, "Ticket de venta", ["cliente"], print_fn=_truena)
        self.assertEqual(ventana.textos_para_reimprimir(), ["cliente"])
        self.assertIn("No salió", ventana.estado.text())

    def test_si_falla_anotar_no_se_cae_la_impresion(self) -> None:
        impresos = []

        def _falla():
            raise RuntimeError("sin base")

        trh.imprimir_directo(
            self.parent, "Ticket de venta", ["cliente"],
            on_printed=_falla, print_fn=lambda t: impresos.append(t) or True,
        )
        self.assertEqual(impresos, ["cliente"])

    def test_listo_es_el_boton_del_enter(self) -> None:
        ventana = trh.imprimir_directo(self.parent, "Ticket de venta", ["cliente"], print_fn=lambda t: True)
        self.assertTrue(ventana.listo.isDefault())

    def test_si_se_cierra_antes_y_algo_falla_se_ofrece_la_ventana_de_siempre(self) -> None:
        from pos_uniformes.ui.dialogs.cobro_listo_dialog import VentanaCobrado

        avisos = []
        ventana = VentanaCobrado(
            self.parent, ["cliente"], total_txt=None, destinos=[],
            reimprimir=lambda textos, fin: None, mandar=lambda d, t: True,
            al_cerrar_con_fallas=avisos.append,
        )
        ventana.imprimiendo()
        ventana.exec()                 # «Listo» antes de que acabe
        ventana.termino(["cliente"])
        self.assertEqual(avisos, [["cliente"]])

    def test_mandar_desde_la_ventana_a_otra_pc(self) -> None:
        pc = {"identificador": "PC-1", "nombre": "PC principal", "online": True}
        with patch.object(trh, "otras_impresoras_de_tickets", return_value=[pc]), \
                patch.object(trh, "encolar_para_ids", return_value=[3]) as encolar, \
                patch.object(trh, "vigilar_envio"):
            ventana = trh.imprimir_directo(self.parent, "Ticket de venta", ["cliente"], print_fn=lambda t: True)
            ventana.mandar_botones[0].click()
        self.assertEqual(encolar.call_args.args[:2], ("PC-1", ["cliente"]))
        self.assertIn("Mandado a PC principal", ventana.estado.text())


class RouteTicketsDirectoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_directo_con_impresora_aqui_no_abre_la_ventana(self) -> None:
        anotar = MagicMock()
        with patch(f"{_CACHE}.puede_imprimir", return_value=True), \
                patch(f"{_CACHE}.load_print_routing", return_value=("local", "principal")), \
                patch.object(trh, "imprimir_directo") as directo, \
                patch(_DLG) as dialogo:
            trh.route_tickets(QWidget(), "Ticket de venta", ["t"], on_printed=anotar, directo=True)
        directo.assert_called_once()
        self.assertIs(directo.call_args.kwargs["on_printed"], anotar)
        dialogo.assert_not_called()

    def test_sin_directo_sigue_la_ventana_de_siempre(self) -> None:
        with patch(f"{_CACHE}.puede_imprimir", return_value=True), \
                patch(f"{_CACHE}.load_print_routing", return_value=("local", "principal")), \
                patch.object(trh, "otras_impresoras_de_tickets", return_value=[]), \
                patch.object(trh, "imprimir_directo") as directo, \
                patch(_DLG) as dialogo:
            trh.route_tickets(QWidget(), "Corte", ["t"])
        directo.assert_not_called()
        dialogo.assert_called_once()

    def test_directo_sin_impresora_aqui_se_encola_como_antes(self) -> None:
        with patch(f"{_CACHE}.puede_imprimir", return_value=False), \
                patch(f"{_CACHE}.load_print_routing", return_value=("satelite", "caja")), \
                patch(f"{_CACHE}.imprimir_aqui_de_respaldo", return_value=False), \
                patch.object(trh, "_enviar_al_satelite", return_value=True) as encolar, \
                patch.object(trh, "imprimir_directo") as directo:
            trh.route_tickets(QWidget(), "Ticket de venta", ["t"], directo=True)
        directo.assert_not_called()
        encolar.assert_called_once()


class MandarAOtraPcTests(unittest.TestCase):
    """«Mandar a PC principal» desde la ventana de cobro (2026-11-24)."""

    PC = {"identificador": "PC-1", "nombre": "PC principal"}

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_route_con_destino_manda_y_no_imprime_aqui(self) -> None:
        anotar = MagicMock()
        with patch(f"{_CACHE}.puede_imprimir", return_value=True), \
                patch(f"{_CACHE}.load_print_routing", return_value=("local", "caja")), \
                patch.object(trh, "mandar_directo") as mandar, \
                patch.object(trh, "imprimir_directo") as aqui:
            trh.route_tickets(QWidget(), "Ticket de venta", ["t"], on_printed=anotar, directo=True, destino=self.PC)
        aqui.assert_not_called()
        self.assertEqual(mandar.call_args.args[3], self.PC)
        self.assertIs(mandar.call_args.kwargs["on_printed"], anotar)

    def test_encola_vigila_anota_y_queda_la_ventana(self) -> None:
        anotado = []
        with patch.object(trh, "encolar_para_ids", return_value=[7, 8]) as encolar, \
                patch.object(trh, "vigilar_envio") as vigilar, \
                patch.object(trh, "otras_impresoras_de_tickets", return_value=[]), \
                patch.object(QDialog, "exec", _sin_exec), \
                patch(_DLG) as dialogo:
            ok = trh.mandar_directo(
                QWidget(), "Ticket de venta", ["cliente"], self.PC,
                on_printed=lambda: anotado.append(1), origen="caja",
            )
        self.assertTrue(ok)
        self.assertEqual(encolar.call_args.args[:3], ("PC-1", ["cliente"], "caja"))
        self.assertEqual(vigilar.call_args.args[1:], ([7, 8], "PC principal"))
        self.assertEqual(anotado, [1])
        dialogo.assert_not_called()

    def test_si_no_se_puede_mandar_no_anota_y_ofrece_imprimir_aqui(self) -> None:
        anotar = MagicMock()
        with patch.object(trh, "encolar_para_ids", side_effect=OSError("sin red")), \
                patch.object(trh, "otras_impresoras_de_tickets", return_value=[]), \
                patch(_DLG) as dialogo:
            ok = trh.mandar_directo(QWidget(), "Ticket de venta", ["cliente"], self.PC, on_printed=anotar)
        self.assertFalse(ok)
        anotar.assert_not_called()
        # La ventana de siempre lleva on_printed: anota cuando sí se imprima.
        self.assertIs(dialogo.call_args.kwargs["on_printed"], anotar)
        self.assertIn("PC principal", dialogo.call_args.args[1])

    def test_destinos_solo_si_esta_pc_imprime_tickets(self) -> None:
        otras = [{"identificador": "PC-1", "nombre": "PC principal", "online": True}]
        with patch(f"{_CACHE}.puede_imprimir", return_value=False), \
                patch.object(trh, "otras_impresoras_de_tickets", return_value=otras):
            self.assertEqual(trh.destinos_para_cobro(), [])
        with patch(f"{_CACHE}.puede_imprimir", return_value=True), \
                patch.object(trh, "otras_impresoras_de_tickets", return_value=otras):
            self.assertEqual(trh.destinos_para_cobro(), otras)


if __name__ == "__main__":
    unittest.main()
