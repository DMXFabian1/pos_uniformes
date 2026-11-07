"""Lo de hoy en la pantalla de gafete: operaciones por empleada desde que
abrió la tienda y quién vendió al último (las empleadas, 2026-11-07)."""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import gafete_hoy_service as gh

HOY = date(2026, 11, 7)


class ResumenDeHoyTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)

    def _mov(self, code, nombre, hora, *, tipo="venta", privado=False, dia=HOY):
        self.s.add(LibretaVenta(employee_code=code, employee_name=nombre, tipo=tipo, piezas=1,
                                monto_total=Decimal("100"), privado=privado,
                                created_at=datetime.combine(dia, hora)))
        self.s.commit()

    def test_cuenta_desde_la_apertura_y_dice_quien_fue_la_ultima(self) -> None:
        self._mov("VEND-4", "Fanny Ortiz", time(9, 10))
        self._mov("VEND-4", "Fanny Ortiz", time(11, 0), tipo="apartado")
        self._mov("VEND-5", "Stayce Chavarria", time(12, 30), tipo="abono")
        self._mov("VEND-4", "Fanny Ortiz", time(16, 42))
        r = gh.resumen_de_hoy(self.s, hoy=HOY)
        self.assertEqual(r.por_empleada, (("Fanny", 3), ("Stayce", 1)))
        self.assertEqual(r.ultima, ("Fanny", "16:42"))
        self.assertEqual(r.desde, datetime.combine(HOY, time(9, 0)))

    def test_lo_de_ayer_y_lo_de_antes_de_abrir_no_cuentan(self) -> None:
        self._mov("VEND-4", "Fanny Ortiz", time(17, 0), dia=HOY - timedelta(days=1))   # ayer, después del corte
        self._mov("VEND-4", "Fanny Ortiz", time(8, 30))                                  # hoy, antes de abrir
        self._mov("VEND-5", "Stayce Chavarria", time(10, 0))
        r = gh.resumen_de_hoy(self.s, hoy=HOY)
        self.assertEqual(r.por_empleada, (("Stayce", 1),))

    def test_lo_privado_del_dueno_y_los_retiros_no_son_operaciones(self) -> None:
        self._mov("VEND-1", "Daniel", time(10, 0), privado=True)
        self._mov("VEND-4", "Fanny Ortiz", time(10, 5), tipo="retiro")
        self._mov("VEND-4", "Fanny Ortiz", time(10, 6))
        r = gh.resumen_de_hoy(self.s, hoy=HOY)
        self.assertEqual(r.por_empleada, (("Fanny", 1),))

    def test_sin_nada_el_texto_va_vacio(self) -> None:
        r = gh.resumen_de_hoy(self.s, hoy=HOY)
        self.assertTrue(r.vacio)
        self.assertEqual(gh.texto(r), "")

    def test_el_texto_es_una_linea_sin_montos(self) -> None:
        r = gh.ResumenHoy(por_empleada=(("Fanny", 6), ("Stayce", 4)), ultima=("Stayce", "16:42"))
        t = gh.texto(r)
        self.assertEqual(t, "Hoy  ·  Fanny 6  ·  Stayce 4\nÚltima venta: Stayce, 16:42")
        self.assertNotIn("$", t)


class PieEnLaTarjetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_la_tarjeta_trae_el_pie_solo_si_se_pide_y_oculto_hasta_tener_texto(self) -> None:
        from pos_uniformes.ui.helpers.pantalla_de_gafete import construir_gate

        sin = construir_gate(emoji="📒", titulo="x", ayuda="y", hoja="")
        self.assertIsNone(sin.pie)
        con = construir_gate(emoji="📒", titulo="x", ayuda="y", hoja="", con_pie=True)
        self.assertIsNotNone(con.pie)
        self.assertEqual(con.pie.objectName(), "gatePie")
        self.assertFalse(con.pie.isVisibleTo(con.raiz))

    def test_venta_rapida_lo_pinta_y_lo_esconde_si_queda_vacio(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import patch

        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        satellite = SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None)
        with patch.object(QuickSaleWidget, "refrescar_pie_gafete", lambda self: None):
            w = QuickSaleWidget(satellite)
        w._pintar_pie_gafete("Hoy  ·  Fanny 6")
        self.assertTrue(w._gate_pie.isVisibleTo(w))
        self.assertEqual(w._gate_pie.text(), "Hoy  ·  Fanny 6")
        w._pintar_pie_gafete("")
        self.assertFalse(w._gate_pie.isVisibleTo(w))
        w.deleteLater()


if __name__ == "__main__":
    unittest.main()
