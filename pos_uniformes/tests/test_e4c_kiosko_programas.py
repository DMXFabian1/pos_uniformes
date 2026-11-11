"""E4-C: programa del cliente en Venta Rápida (kiosko) y aviso en la Libreta.

Lo puro va sin base. Lo de la franja y la Libreta corre contra la base local
de prueba con transacción revertida; Telegram va simulado.
"""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPushButton
from sqlalchemy import func, select

from pos_uniformes.database.models import Membresia, Venta
from pos_uniformes.services.fidelizacion import membresia_service as ms
from pos_uniformes.tests.test_e4a_membresias import _Base
from pos_uniformes.tests.test_e4b_telegram_membresias import _Fabrica
from pos_uniformes.ui.dialogs.proponer_programa_dialog import ProponerProgramaDialog
from pos_uniformes.ui.helpers import quick_sale_programa_helper as ph
from pos_uniformes.ui.helpers.quick_sale_programa_helper import estado_para_barra
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget
from tests.conftest import conservar_hasta_el_final

D = Decimal


def _app():
    return QApplication.instance() or QApplication([])


class EstadoBarraTests(unittest.TestCase):
    def test_sin_conexion_todo_deshabilitado(self) -> None:
        e = estado_para_barra(en_linea=False, activa=None, activa_clave=None, pendiente=None)
        self.assertEqual((e.puede_club, e.puede_proponer), (False, False))
        self.assertEqual(e.tooltip, "Sin conexión: inscríbelo después.")

    def test_sin_programa_puede_las_dos(self) -> None:
        e = estado_para_barra(en_linea=True, activa=None, activa_clave=None, pendiente=None)
        self.assertEqual((e.texto, e.puede_club, e.puede_proponer), ("★ Sin programa", True, True))

    def test_en_club_solo_puede_proponer(self) -> None:
        e = estado_para_barra(en_linea=True, activa="Maximoda Club", activa_clave="CLUB", pendiente=None)
        self.assertEqual((e.texto, e.puede_club, e.puede_proponer), ("★ Miembro Maximoda Club", False, True))

    def test_en_profesional_o_mayorista_se_cambia_en_el_pos(self) -> None:
        e = estado_para_barra(en_linea=True, activa="Maximoda Mayorista", activa_clave="MAYORISTA", pendiente=None)
        self.assertEqual((e.puede_club, e.puede_proponer), (False, False))
        self.assertIn("POS", e.tooltip)

    def test_con_propuesta_pendiente_espera(self) -> None:
        e = estado_para_barra(en_linea=True, activa="Maximoda Club", activa_clave="CLUB", pendiente="Maximoda Profesional")
        self.assertEqual(e.texto, "⏳ Propuesta a Profesional: esperando aprobación")
        self.assertEqual((e.puede_club, e.puede_proponer), (False, False))

    def test_sin_empleada_no_actua(self) -> None:
        e = estado_para_barra(en_linea=True, activa=None, activa_clave=None, pendiente=None, hay_empleada=False)
        self.assertEqual((e.puede_club, e.puede_proponer), (False, False))

    def test_nunca_promete_porcentajes(self) -> None:
        for kw in ({"activa": "Maximoda Club", "activa_clave": "CLUB", "pendiente": None},
                   {"activa": None, "activa_clave": None, "pendiente": "Maximoda Mayorista"}):
            self.assertNotIn("%", estado_para_barra(en_linea=True, **kw).texto)


class DialogoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _app()

    def test_pide_programa_y_motivo_de_10_caracteres(self) -> None:
        d = ProponerProgramaDialog(None, nombre_cliente="Ana")
        self.assertFalse(d.enviar_button.isEnabled())
        d.motivo_input.setPlainText("Maestra de la Benito Juárez")
        self.assertFalse(d.enviar_button.isEnabled(), "falta el programa")
        d.opciones["MAYORISTA"].setChecked(True)
        d.motivo_input.setPlainText("maestra")
        self.assertFalse(d.enviar_button.isEnabled())
        self.assertIn("faltan 3", d.aviso.text())
        d.motivo_input.setPlainText("  Compra para su grupo  ")
        d.enviar_button.click()
        self.assertEqual(d.result(), int(QDialog.DialogCode.Accepted))
        self.assertEqual(d.resultado, ("MAYORISTA", "Compra para su grupo"))
        self.assertEqual(set(d.opciones), {"PROFESIONAL", "MAYORISTA"}, "Club no se propone")


class _Kiosko(_Base):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _app()

    def setUp(self) -> None:
        super().setUp()
        self.f = _Fabrica(self.s)
        p = patch("pos_uniformes.database.connection.get_session", self.f)
        p.start()
        self.addCleanup(p.stop)

    def _widget(self, *, online=True, empleada=None):
        sat = SimpleNamespace(offline_mode=not online, _kiosk_lookup_from_cache=None, _db_online=online)
        w = QuickSaleWidget(sat)
        # No `deleteLater`: el aviso de 1.8 s de la barra de escaneo caía sobre
        # el widget ya borrado y tumbaba el proceso de la prueba siguiente.
        self.addCleanup(conservar_hasta_el_final, w)
        w._employee_code = empleada if empleada is not None else self.lupita.codigo
        w._items = [{"sku": "SKU1", "nombre": "Pants", "talla": "6", "color": "", "precio": D("450.00"), "cantidad": 2}]
        w._cliente = {"id": self.cliente.id, "codigo": self.cliente.codigo_cliente, "nombre": self.cliente.nombre,
                      "por_qr": False, "en_linea": online}
        w._pintar_programa_bar()
        return w

    def _membresias(self):
        return list(self.s.scalars(select(Membresia).where(Membresia.cliente_id == self.cliente.id)))


class FranjaTests(_Kiosko):
    def test_aparece_con_el_cliente_y_se_va_sin_el(self) -> None:
        w = self._widget()
        self.assertFalse(w._programa_bar.isHidden())
        self.assertEqual(w._programa_label.text(), "★ Sin programa")
        self.assertTrue(w._btn_inscribir_club.isEnabled() and w._btn_proponer_programa.isEnabled())
        w._cliente = None
        w._pintar_programa_bar()
        self.assertTrue(w._programa_bar.isHidden())

    def test_inscribir_al_club_sin_tocar_la_venta(self) -> None:
        w = self._widget()
        antes = w._compute_totals()
        ventas = self.s.scalar(select(func.count(Venta.id)).where(Venta.cliente_id == self.cliente.id))
        with patch.object(ph.QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as pregunta:
            w._btn_inscribir_club.click()
        self.assertIn("no cambia ningún precio", pregunta.call_args.args[2])
        self.assertEqual([(m.estado, m.programa.clave) for m in self._membresias()], [(ms.ACTIVA, "CLUB")])
        self.assertEqual(w._programa_label.text(), "★ Miembro Maximoda Club")
        self.assertFalse(w._btn_inscribir_club.isEnabled())
        self.assertTrue(w._btn_proponer_programa.isEnabled())
        self.assertEqual(w._compute_totals(), antes, "el total no cambia")
        self.assertEqual(self.s.scalar(select(func.count(Venta.id)).where(Venta.cliente_id == self.cliente.id)), ventas)

    def test_si_dice_que_no_no_inscribe(self) -> None:
        w = self._widget()
        with patch.object(ph.QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            w._btn_inscribir_club.click()
        self.assertEqual(self._membresias(), [])

    def test_proponer_queda_pendiente_y_avisa_al_dueno(self) -> None:
        w = self._widget()

        class _Dlg:
            def __init__(self_inner, *a, **k):
                self_inner.resultado = ("PROFESIONAL", "Maestra de la Benito Juárez")

            def exec(self_inner):
                return int(QDialog.DialogCode.Accepted)

        with patch("pos_uniformes.ui.dialogs.proponer_programa_dialog.ProponerProgramaDialog", _Dlg), \
                patch("pos_uniformes.services.telegram_service.enviar_mensaje") as enviar:
            w._btn_proponer_programa.click()
        [m] = self._membresias()
        self.assertEqual((m.estado, m.propuesta_por_employee_code), (ms.PENDIENTE, self.lupita.codigo))
        enviar.assert_called_once()
        self.assertIn(f"mb:ok:{m.id}", enviar.call_args.kwargs["botones"])
        self.assertEqual(w._programa_label.text(), "⏳ Propuesta a Profesional: esperando aprobación")
        self.assertFalse(w._btn_inscribir_club.isEnabled() or w._btn_proponer_programa.isEnabled())

    def test_sin_conexion_no_consulta_ni_guarda(self) -> None:
        w = self._widget(online=False)  # el constructor del widget sí lee (empleadas)
        with patch("pos_uniformes.database.connection.get_session") as sesion:
            w._pintar_programa_bar()
            self.assertEqual(w._programa_label.text(), "★ Programa: sin conexión")
            self.assertFalse(w._btn_inscribir_club.isEnabled() or w._btn_proponer_programa.isEnabled())
            self.assertEqual(w._btn_inscribir_club.toolTip(), "Sin conexión: inscríbelo después.")
            with patch.object(ph.QMessageBox, "information") as aviso:
                w._on_inscribir_club()
            sesion.assert_not_called()
        self.assertIn("Sin conexión", aviso.call_args.args[2])

    def test_empleada_dada_de_baja_ve_el_motivo_y_no_inscribe(self) -> None:
        w = self._widget(empleada=self.baja.codigo)
        with patch.object(ph.QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
                patch.object(ph.QMessageBox, "warning") as aviso:
            w._btn_inscribir_club.click()
        aviso.assert_called_once()
        self.assertEqual(self._membresias(), [])

    def test_consulta_una_vez_por_cliente_no_en_cada_repintado(self) -> None:
        w = self._widget()
        with patch.object(w, "_leer_programa", wraps=w._leer_programa) as leer:
            for _ in range(5):
                w._pintar_programa_bar()
        leer.assert_not_called()
        otro = self._cliente("Otro E4C")
        w._cliente = dict(w._cliente, id=otro.id)
        with patch.object(w, "_leer_programa", wraps=w._leer_programa) as leer:
            w._pintar_programa_bar()
            w._pintar_programa_bar()
        self.assertEqual(leer.call_count, 1)


class LibretaTests(_Kiosko):
    def _libreta(self):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        w = SimpleNamespace(
            _libreta_code=self.lupita.codigo,
            libreta_descanso_button=QPushButton(),
            libreta_descanso_aviso=QLabel(),
            libreta_descanso_respuesta=QLabel(),
            libreta_descanso_visto_button=QPushButton(),
        )
        for widget in vars(w).values():
            if hasattr(widget, "deleteLater"):
                self.addCleanup(widget.deleteLater)
        w._libreta_descanso_refrescar = lambda: QuoteSatelliteWindow._libreta_descanso_refrescar(w)
        p = patch("pos_uniformes.ui.quote_satellite_window.get_session", self.f)
        p.start()
        self.addCleanup(p.stop)
        return w, (lambda: QuoteSatelliteWindow._libreta_descanso_visto(w))

    def test_le_llega_la_respuesta_hasta_que_la_lee(self) -> None:
        m = self._proponer()
        ms.rechazar_por_dueno(self.s, m.id, motivo="Todavía no compra seguido")
        w, visto = self._libreta()
        w._libreta_descanso_refrescar()
        self.assertFalse(w.libreta_descanso_respuesta.isHidden())
        self.assertIn(f"Daniel no aprobó a {self.cliente.nombre} en Maximoda Profesional", w.libreta_descanso_respuesta.text())
        self.assertFalse(w.libreta_descanso_visto_button.isHidden())
        visto()
        self.assertTrue(w.libreta_descanso_respuesta.isHidden())
        self.s.refresh(m)
        self.assertIsNotNone(m.avisada_at)

    def test_si_falla_lo_de_programas_la_libreta_sigue(self) -> None:
        w, _visto = self._libreta()
        with patch.object(ms, "respuestas_sin_ver", side_effect=RuntimeError("sin tabla")):
            w._libreta_descanso_refrescar()
        self.assertFalse(w.libreta_descanso_button.isHidden(), "el botón de descanso sigue")
        self.assertTrue(w.libreta_descanso_respuesta.isHidden())


if __name__ == "__main__":
    unittest.main()
