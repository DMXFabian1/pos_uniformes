"""Ajustar un corte exige decir por qué.

En septiembre salieron $16,349 por ajustes y no había una sola palabra de a
dónde fueron (Daniel, 2026-10-01). La cifra estaba; la explicación, no.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaCorte
from pos_uniformes.services.historial_cortes_service import (
    SinPermiso,
    ajustar_corte,
    quitar_ajuste,
    venta_real,
)

_DIALOGO = Path(__file__).resolve().parent.parent / "ui" / "dialogs" / "historial_cortes_dialog.py"


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        from datetime import date, datetime

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.corte = LibretaCorte(
            fecha=date(2026, 9, 20), periodo_label="19/09 → 20/09",
            monto_final=Decimal("22548"), monto_esperado=Decimal("22548"),
            reactivo_inicial=Decimal("11160"), reactivo_final=Decimal("11160"),
            retiros_pagos=Decimal("0"), otros_retiros=Decimal("0"),
            operaciones=32, creado_por="VEND-1",
            desde=datetime(2026, 9, 19, 17, 58), hasta=datetime(2026, 9, 20, 16, 34),
        )
        self.s.add(self.corte)
        self.s.commit()
        self.real = venta_real(self.corte)   # 11,388

    def _ajustar(self, menos="2000", nota=""):
        return ajustar_corte(
            self.s, self.corte.id, venta=self.real - Decimal(menos),
            creado_por="VEND-1", nota=nota,
        )


class LaNotaTest(_Base):
    def test_sin_decir_por_que_no_se_ajusta(self):
        with self.assertRaises(ValueError) as caso:
            self._ajustar()
        self.assertIn("sin eso, ese dinero queda sin explicación", str(caso.exception))
        self.assertEqual(Decimal(str(self.corte.monto_final)), Decimal("22548"), "no se tocó")

    def test_con_el_porque_si(self):
        r = self._ajustar(nota="Depósito al banco")
        self.assertEqual(r["nota"], "Depósito al banco")
        self.assertEqual(self.corte.nota, "Depósito al banco")

    def test_los_espacios_no_cuentan_como_explicacion(self):
        with self.assertRaises(ValueError):
            self._ajustar(nota="   ")

    def test_dejar_la_cifra_real_no_pide_nota(self):
        # Sin ajuste no hay nada que explicar.
        r = ajustar_corte(self.s, self.corte.id, venta=self.real, creado_por="VEND-1")
        self.assertEqual(r["nota"], "")

    def test_al_quitar_el_ajuste_la_nota_se_va_con_el(self):
        self._ajustar(nota="Depósito al banco")
        quitar_ajuste(self.s, self.corte.id, creado_por="VEND-1")
        self.assertIsNone(self.corte.nota)

    def test_la_nota_larga_no_rompe_la_columna(self):
        r = self._ajustar(nota="x" * 500)
        self.assertLessEqual(len(r["nota"]), 200)

    def test_solo_el_dueño_ajusta(self):
        with self.assertRaises(SinPermiso):
            ajustar_corte(self.s, self.corte.id, venta=self.real, creado_por="VEND-5", nota="x")


class ElDialogoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fuente = _DIALOGO.read_text(encoding="utf-8")

    def test_pregunta_el_porque(self):
        self.assertIn('QLabel("¿Por qué?")', self.fuente)
        self.assertIn("nota=nota_input.text()", self.fuente)

    def test_trae_los_motivos_de_siempre(self):
        for motivo in ("Depósito al banco", "Proveedor", "Me lo llevé"):
            self.assertIn(motivo, self.fuente)

    def test_no_deja_guardar_sin_el(self):
        self.assertIn("Falta el porqué", self.fuente)

    def test_si_no_hay_ajuste_no_estorba_con_la_pregunta(self):
        self.assertIn("w.setVisible(bool(fuera))", self.fuente)


class EnElCelularTest(unittest.TestCase):
    def test_cortes_enseña_la_nota_y_cuenta_los_que_no_la_tienen(self):
        from datetime import date

        from pos_uniformes.services import telegram_cortes_service as ct

        con = ct.CorteFila(
            fecha=date(2026, 9, 20), hora="16:34", quien="Daniel",
            contado=Decimal("20548"), esperado=Decimal("22548"), operaciones=32,
            ajustado=True, nota="Depósito al banco",
        )
        sin = ct.CorteFila(
            fecha=date(2026, 9, 19), hora="17:58", quien="Daniel",
            contado=Decimal("16627"), esperado=Decimal("17627"), operaciones=19,
            ajustado=True,
        )
        texto = ct.texto([con, sin])
        self.assertIn("lo bajaste tú $2,000 (Depósito al banco)", texto)
        # «de ellos» no decía de quiénes: ¿de los dos de arriba, o de los 13
        # del periodo? Ahora lo dice (07/10).
        self.assertIn("1 de los de arriba sin anotar por qué", texto)


if __name__ == "__main__":
    unittest.main()
