"""La Libreta del dueño, rediseñada (2026-11-05).

Daniel: «¿cómo puedo ver días anteriores en libreta?». Había que abrir "Más
opciones", poner dos fechas y tocar "Ver rango". Ahora la fecha es lo primero:
◀ día ▶, Hoy / Semana / Mes / Su ciclo. Los movimientos van a la izquierda, lo
que se hace con ellos a la derecha, y lo de caja en un menú. La empleada ve lo
mismo de siempre.
"""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QInputDialog

HOY = datetime.now().date()


def _fila(i: int, *, tarjeta: bool = False, nombre: str = "Stayce Chavarria", code: str = "VEND-4"):
    return SimpleNamespace(
        id=i, tipo="venta", piezas=3, comisiones=3, monto_total=Decimal("657.00"), monto_neto=Decimal("657.00"),
        pago_tarjeta=tarjeta, employee_code=code, employee_name=nombre, created_at=datetime.now(), cliente=None,
        descuento_empleada=False, privado=False, detalle=[{"nombre": "Sueter", "cantidad": 3}],
    )


class LibretaDelDuenoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self, code: str | None = None):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        win = QuoteSatelliteWindow(user_id=1, offline_mode=True)
        win._gafete_libreta_valido = lambda c: True
        self.refrescos = []
        win._refresh_libreta_view = lambda: self.refrescos.append(win._libreta_periodo)
        win.libreta_gate_input.setText(code or QuickSaleWidget._OWNER_CODE)
        win._on_libreta_gate_scan()
        self.addCleanup(win.close)
        return win

    # ── la fecha ─────────────────────────────────────────────────────────
    def test_arranca_en_hoy_y_no_deja_ir_al_futuro(self) -> None:
        win = self._ventana()
        self.assertTrue(win.libreta_dia_label.text().startswith("Hoy · "))
        self.assertTrue(win.libreta_dia_prev.isEnabled())
        self.assertFalse(win.libreta_dia_next.isEnabled())

    def test_la_flecha_va_a_ayer_y_vuelve_a_hoy(self) -> None:
        win = self._ventana()
        win.libreta_dia_prev.click()
        ayer = HOY - timedelta(days=1)
        self.assertEqual(win._libreta_periodo, "rango")
        self.assertEqual(win.libreta_rango_desde.date().toPyDate(), ayer)
        self.assertEqual(win.libreta_rango_hasta.date().toPyDate(), ayer)
        self.assertTrue(win.libreta_dia_label.text().startswith("Ayer · "))
        # Un solo día no abre el panel de fechas: se entiende con el título.
        self.assertTrue(win.libreta_opciones_panel.isHidden())
        self.assertTrue(win.libreta_table.isColumnHidden(0))      # la Fecha sobra
        self.assertTrue(win.libreta_dia_next.isEnabled())
        win.libreta_dia_next.click()
        # De vuelta a hoy es «Hoy» de verdad (desde el último corte), no un rango.
        self.assertEqual(win._libreta_periodo, "hoy")
        self.assertEqual(self.refrescos[-2:], ["rango", "hoy"])

    def test_mes_y_sus_flechas_van_de_mes_en_mes(self) -> None:
        win = self._ventana()
        win.libreta_mes_button.click()
        self.assertEqual(win.libreta_rango_desde.date().toPyDate(), HOY.replace(day=1))
        self.assertEqual(win.libreta_rango_hasta.date().toPyDate(), HOY)
        self.assertTrue(win.libreta_mes_button.isChecked())
        self.assertFalse(win.libreta_dia_next.isEnabled())
        self.assertFalse(win.libreta_table.isColumnHidden(0))
        win.libreta_dia_prev.click()
        fin_anterior = HOY.replace(day=1) - timedelta(days=1)
        self.assertEqual(win.libreta_rango_desde.date().toPyDate(), fin_anterior.replace(day=1))
        self.assertEqual(win.libreta_rango_hasta.date().toPyDate(), fin_anterior)
        self.assertTrue(win.libreta_mes_button.isChecked())
        win.libreta_dia_next.click()
        self.assertEqual(win.libreta_rango_hasta.date().toPyDate(), HOY)

    def test_semana_y_la_flecha_va_a_la_anterior(self) -> None:
        win = self._ventana()
        win.libreta_semana_button.click()
        lunes = HOY - timedelta(days=HOY.weekday())
        self.assertEqual(win._libreta_fechas_mostradas(), (lunes, lunes + timedelta(days=6)))
        win.libreta_dia_prev.click()
        self.assertEqual(win.libreta_rango_desde.date().toPyDate(), lunes - timedelta(days=7))
        self.assertEqual(win.libreta_rango_hasta.date().toPyDate(), lunes - timedelta(days=1))

    def test_elegir_un_dia_en_el_calendario(self) -> None:
        from PyQt6.QtCore import QDate
        from PyQt6.QtWidgets import QDialog

        win = self._ventana()
        dia = HOY - timedelta(days=9)

        def exec_falso(dlg):
            win._libreta_dia_calendario.clicked.emit(QDate(dia.year, dia.month, dia.day))
            return QDialog.DialogCode.Accepted

        with patch.object(QDialog, "exec", exec_falso):
            win.libreta_dia_label.click()
        self.assertEqual(win.libreta_rango_desde.date().toPyDate(), dia)
        self.assertEqual(win.libreta_rango_hasta.date().toPyDate(), dia)

    # ── acomodo ──────────────────────────────────────────────────────────
    def test_lo_de_caja_va_en_un_menu_y_dispara_lo_de_siempre(self) -> None:
        win = self._ventana()
        textos = [a.text() for a in win.libreta_caja_menu.actions() if a.text()]
        self.assertEqual(len(textos), 6)
        for palabra in ("retiro", "Cortes", "Pagos", "Equipo", "Caja y nómina", "Meta semanal"):
            self.assertTrue(any(palabra in t for t in textos), palabra)
        self.assertFalse(win.libreta_caja_menu_button.isHidden())
        self.assertFalse(win.libreta_print_button.isHidden())
        with patch.object(type(win), "_abrir_equipo") as abrir:
            # el botón viejo se conectó al método original: se prueba el camino del menú
            accion = next(a for a in win.libreta_caja_menu.actions() if "Equipo" in a.text())
            with patch.object(win.libreta_equipo_button, "click") as clic:
                accion.trigger()
            clic.assert_called_once()
        del abrir

    def test_la_meta_se_cambia_desde_el_menu(self) -> None:
        win = self._ventana()
        with patch.object(QInputDialog, "getInt", return_value=(120, True)), patch.object(
            win, "_guardar_meta_libreta"
        ) as guardar:
            win._libreta_pedir_meta()
        self.assertEqual(win.libreta_meta_spin.value(), 120)
        guardar.assert_called_once()

    def test_el_movimiento_elegido_se_dice_con_sus_letras(self) -> None:
        win = self._ventana()
        win.show()
        win._set_page("libreta")
        win._pintar_libreta([_fila(1), _fila(2, tarjeta=True, nombre="Cristal", code="VEND-5")])
        self.assertFalse(win.libreta_mov_vacio.isHidden())
        self.assertTrue(win.libreta_acciones_bar.isHidden())
        win.libreta_table.selectRow(0)
        self.assertTrue(win.libreta_mov_vacio.isHidden())
        self.assertFalse(win.libreta_acciones_bar.isHidden())
        texto = win.libreta_mov_detalle.text()
        self.assertIn("Venta de", texto)
        self.assertIn("3 piezas", texto)
        self.assertIn("$657.00", texto)

    # ── la empleada ──────────────────────────────────────────────────────
    def test_la_empleada_ve_lo_de_siempre(self) -> None:
        win = self._ventana("VEND-4")
        self.assertTrue(win.libreta_owner_bar.isHidden())
        self.assertTrue(win.libreta_caja_menu_button.isHidden())
        self.assertTrue(win.libreta_print_button.isHidden())
        self.assertTrue(win.libreta_semana_button.isHidden())
        # Sus dos botones siguen en la cabecera, no en la barra del dueño.
        for boton in (win.libreta_hoy_button, win.libreta_ciclo_button):
            self.assertGreaterEqual(win._libreta_header_ly.indexOf(boton), 0)
            self.assertFalse(boton.isHidden())

    def test_entra_el_dueno_despues_de_una_empleada_y_al_reves(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        win = self._ventana("VEND-4")
        win._libreta_logout()
        win.libreta_gate_input.setText(QuickSaleWidget._OWNER_CODE)
        win._on_libreta_gate_scan()
        self.assertGreaterEqual(win._libreta_fecha_ly.indexOf(win.libreta_hoy_button), 0)
        self.assertFalse(win.libreta_caja_menu_button.isHidden())
        win._libreta_logout()
        win.libreta_gate_input.setText("VEND-4")
        win._on_libreta_gate_scan()
        self.assertGreaterEqual(win._libreta_header_ly.indexOf(win.libreta_hoy_button), 0)
        self.assertTrue(win.libreta_caja_menu_button.isHidden())


if __name__ == "__main__":
    unittest.main()
