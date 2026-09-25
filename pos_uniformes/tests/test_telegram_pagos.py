"""Pagos desde el celular.

El corte ya se hacía desde lejos; los pagos no (Daniel, 2026-09-25). Lo que se
cuida aquí es el candado: un dedo en el celular resbala más fácil que un clic
en la caja, así que lo que saca dinero no pasa con una sola palabra.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from pos_uniformes.services import telegram_pagos_service as pg


class _Det:
    """Lo mínimo que el texto le pide a un DetallePago."""

    def __init__(self, total="1412.00", comisiones=56, faltas=0):
        self.desde, self.hasta = date(2026, 9, 18), date(2026, 9, 25)
        self.sueldo_base = Decimal("1300.00")
        self.comisiones = comisiones
        self.tarifa_comision = Decimal("2.00")
        self.faltas = faltas
        self.descuento_falta = Decimal("100.00")
        self.dias_trabajados = None
        self.tarifa_dia = None
        self.total = Decimal(total)

    por_dia = False
    monto_comisiones = Decimal("112.00")
    descuento_faltas = Decimal("0.00")


class PagarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registrados = []

    def _correr(self, argumento, *, det=None, code="VEND-5"):
        from pos_uniformes.services import asistencia_service as asis
        from pos_uniformes.services import nomina_service as nom

        sesion = object()
        with patch.object(asis, "buscar_code", return_value=code), \
             patch.object(nom, "pago_pendiente", return_value=det or _Det()), \
             patch.object(nom, "registrar_pago_con_monto",
                          side_effect=lambda *a, **k: self.registrados.append(a)), \
             patch.object(pg, "_nombre", return_value="Evelyn Ortiz"), \
             patch.object(pg, "_detalle_texto", wraps=pg._detalle_texto):
            with patch("pos_uniformes.services.telegram_pagos_service.Session"):
                sesion = type("S", (), {"commit": lambda self_: None})()
                return pg.pagar(sesion, argumento, quien="VEND-1")

    def test_sin_confirmar_enseña_el_desglose_y_no_paga(self):
        r = self._correr("Evelyn")
        self.assertIn("TOTAL: $1,412.00", r)
        self.assertIn("/pagar Evelyn si", r)
        self.assertEqual(self.registrados, [], "el dinero no se mueve con una sola palabra")

    def test_con_la_confirmacion_si_paga(self):
        r = self._correr("Evelyn si")
        self.assertIn("✅ Pagado", r)
        self.assertIn("$1,412.00", r)
        self.assertEqual(len(self.registrados), 1)

    def test_otras_palabras_tambien_confirman(self):
        for palabra in ("sí", "ok", "dale", "confirmar"):
            self.registrados.clear()
            self._correr(f"Evelyn {palabra}")
            self.assertEqual(len(self.registrados), 1, palabra)

    def test_si_no_debe_nada_no_ofrece_pagar(self):
        r = self._correr("Evelyn", det=_Det(total="0.00"))
        self.assertIn("no tiene nada pendiente", r)
        self.assertNotIn("/pagar", r)

    def test_a_quien_no_existe_lo_dice(self):
        r = self._correr("Menganita", code=None)
        self.assertIn("¿Quién es", r)
        self.assertEqual(self.registrados, [])

    def test_sin_nombre_explica_como_se_usa(self):
        self.assertIn("/pagar Fanny", pg.pagar(None, "", quien="VEND-1"))


class RetiroTest(unittest.TestCase):
    def setUp(self) -> None:
        self.hechos = []

    def _correr(self, argumento):
        from pos_uniformes.services import retiros_service

        sesion = type("S", (), {"commit": lambda self_: None})()
        with patch.object(retiros_service, "registrar_retiro",
                          side_effect=lambda *a, **k: self.hechos.append(k)):
            return pg.retiro(sesion, argumento, quien="VEND-1")

    def test_pide_el_motivo(self):
        """Sin motivo, el corte de la noche es un misterio."""
        r = self._correr("500")
        self.assertIn("¿Para qué", r)
        self.assertEqual(self.hechos, [])

    def test_con_monto_y_motivo_lo_anota(self):
        r = self._correr("500 gasolina")
        self.assertIn("✅", r)
        self.assertEqual(self.hechos[0]["monto"], Decimal("500"))
        self.assertEqual(self.hechos[0]["motivo"], "gasolina")

    def test_acepta_el_signo_y_las_comas(self):
        self._correr("$1,500 proveedor")
        self.assertEqual(self.hechos[0]["monto"], Decimal("1500"))

    def test_lo_que_no_es_cantidad_no_pasa(self):
        self.assertIn("No entendí", self._correr("abc gasolina"))
        self.assertEqual(self.hechos, [])

    def test_cero_o_negativo_no_pasa(self):
        for malo in ("0 gasolina", "-50 gasolina"):
            self.hechos.clear()
            r = self._correr(malo)
            self.assertEqual(self.hechos, [], malo)
            self.assertTrue("mayor a cero" in r or "No entendí" in r)


class ElBotLosConoceTest(unittest.TestCase):
    def test_estan_en_la_ayuda_y_en_el_despachador(self):
        from pathlib import Path

        from pos_uniformes.services.telegram_bot_service import AYUDA

        for c in ("/pagos", "/pagar", "/retiro", "/deshacerpago"):
            self.assertIn(c, AYUDA, f"{c} no sale en /ayuda")
        fuente = (
            Path(__file__).resolve().parent.parent / "services" / "telegram_bot_service.py"
        ).read_text(encoding="utf-8")
        for c in ("pagos", "pagar", "retiro"):
            self.assertIn(f'cmd.nombre == "{c}"', fuente)


if __name__ == "__main__":
    unittest.main()
