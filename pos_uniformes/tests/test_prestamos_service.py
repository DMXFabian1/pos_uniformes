"""Préstamos a empleadas: lo pide ella, lo apruebas tú, se descuenta del sueldo.

Lo delicado es que toca nómina y caja a la vez: aprobar un préstamo saca
dinero del cajón, y pagarlo cambia lo que ella cobra. Casi todos los tests son
sobre lo que NO debe pasar.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaRetiro, Empleada, PrestamoEmpleada
from pos_uniformes.services import prestamos_service as pr


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-5", nombre_completo="Fanny Ortiz", activo=True))
        self.s.flush()

    def _pedir(self, monto="1000", motivo="para la renta", code="VEND-5"):
        return pr.pedir(self.s, employee_code=code, nombre="Fanny Ortiz", monto=monto, motivo=motivo)

    def _ganado(self, cuanto):
        """Finge lo que lleva ganado: el cálculo real es de nómina y ya tiene
        sus propios tests."""
        from unittest.mock import patch

        return patch.object(pr, "ganado_hasta_hoy", return_value=Decimal(cuanto))

    def setUpGanado(self):  # noqa: N802 — ayuda para los tests que no lo fijan
        return self._ganado("10000")


class PedirTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        # Con margen de sobra, salvo donde el test lo fije a propósito.
        self._margen = self._ganado("10000")
        self._margen.start()
        self.addCleanup(self._margen.stop)

    def test_queda_esperando_respuesta(self):
        p = self._pedir()
        self.assertEqual(p.estado, pr.PEDIDO)
        self.assertEqual(pr.pendientes(self.s), [p])

    def test_sin_motivo_no_se_puede_autorizar(self):
        with self.assertRaises(pr.NoSePuede):
            self._pedir(motivo="  ")

    def test_ni_cero_ni_negativo(self):
        for malo in ("0", "-100"):
            with self.assertRaises(pr.NoSePuede):
                self._pedir(monto=malo)

    def test_no_mas_del_70_por_ciento_de_lo_ganado(self):
        """Daniel, 2026-10-01: el préstamo tiene que caber en lo que ya se ganó."""
        with self._ganado("1000"):
            self._pedir(monto="700")          # justo el tope: pasa
        with self._ganado("1000"), self.assertRaises(pr.NoSePuede) as caso:
            self._pedir(monto="701")
        self.assertIn("$700.00", str(caso.exception))

    def test_recien_pagada_no_puede_pedir(self):
        # Su ciclo empieza en cero: no hay de dónde descontarlo.
        with self._ganado("0"), self.assertRaises(pr.NoSePuede) as caso:
            self._pedir(monto="100")
        self.assertIn("no llevas nada ganado", str(caso.exception))

    def test_no_se_amontonan_las_solicitudes(self):
        self._pedir()
        with self.assertRaises(pr.NoSePuede):
            self._pedir()

    def test_no_pide_otro_si_todavia_le_deben_descontar_uno(self):
        p = self._pedir()
        pr.aprobar(self.s, p.id, quien="VEND-1")
        with self.assertRaises(pr.NoSePuede):
            self._pedir()


class AprobarTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        m = self._ganado("10000")
        m.start()
        self.addCleanup(m.stop)

    def test_al_aprobar_el_dinero_sale_del_cajon(self):
        """Sin el retiro, el corte de esa noche saldría corto justo por el
        préstamo y parecería un descuadre."""
        p = self._pedir(monto="1500")
        pr.aprobar(self.s, p.id, quien="VEND-1")
        retiros = self.s.scalars(select(CajaRetiro)).all()
        self.assertEqual(len(retiros), 1)
        self.assertEqual(Decimal(str(retiros[0].monto)), Decimal("1500"))
        self.assertIn("Fanny", retiros[0].motivo)

    def test_queda_el_rastro_de_quien_y_cuando(self):
        p = self._pedir()
        pr.aprobar(self.s, p.id, quien="VEND-1")
        self.assertEqual(p.estado, pr.APROBADO)
        self.assertEqual(p.resuelto_por, "VEND-1")
        self.assertIsNotNone(p.resuelto_at)

    def test_rechazar_no_saca_dinero(self):
        p = self._pedir()
        pr.rechazar(self.s, p.id, quien="VEND-1")
        self.assertEqual(p.estado, pr.RECHAZADO)
        self.assertEqual(self.s.scalars(select(CajaRetiro)).all(), [])

    def test_no_se_aprueba_dos_veces(self):
        p = self._pedir()
        pr.aprobar(self.s, p.id, quien="VEND-1")
        with self.assertRaises(pr.NoSePuede):
            pr.aprobar(self.s, p.id, quien="VEND-1")
        self.assertEqual(len(self.s.scalars(select(CajaRetiro)).all()), 1, "ni sale el dinero dos veces")

    def test_el_que_no_existe_lo_dice(self):
        with self.assertRaises(pr.NoSePuede):
            pr.aprobar(self.s, 999, quien="VEND-1")


class CobrarTest(_Base):
    def setUp(self) -> None:
        super().setUp()
        m = self._ganado("10000")
        m.start()
        self.addCleanup(m.stop)

    def test_lo_aprobado_cuenta_para_el_siguiente_pago(self):
        p = self._pedir(monto="800")
        pr.aprobar(self.s, p.id, quien="VEND-1")
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-5"), Decimal("800"))

    def test_lo_pedido_pero_no_aprobado_no_cuenta(self):
        self._pedir(monto="800")
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-5"), Decimal("0.00"))

    def test_al_cobrarlo_queda_saldado_y_con_su_rastro(self):
        p = self._pedir(monto="800")
        pr.aprobar(self.s, p.id, quien="VEND-1")
        cobrado = pr.marcar_cobrados(self.s, "VEND-5", pago_id=77)
        self.assertEqual(cobrado, Decimal("800"))
        self.assertEqual(p.estado, pr.COBRADO)
        self.assertEqual(p.pago_id, 77)
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-5"), Decimal("0.00"))

    def test_el_prestamo_de_otra_no_se_le_descuenta_a_ella(self):
        self.s.add(Empleada(codigo="VEND-4", nombre_completo="Stayce", activo=True))
        self.s.flush()
        p = pr.pedir(self.s, employee_code="VEND-4", nombre="Stayce", monto="500", motivo="x")
        pr.aprobar(self.s, p.id, quien="VEND-1")
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-5"), Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()


class CobroParcial(_Base):
    """Un préstamo más grande que el pago no se perdona: se parte y el resto
    sigue debiéndose (bug 2026-10-04)."""

    def _aprobado(self, monto):
        with self.setUpGanado():
            p = self._pedir(monto=monto)
            return pr.aprobar(self.s, p.id, quien="VEND-1")

    def test_lo_que_no_alcanzo_sigue_por_cobrar(self):
        self._aprobado("2000")
        cobrado = pr.marcar_cobrados(self.s, "VEND-5", pago_id=None, cubierto=Decimal("1300"))
        self.assertEqual(cobrado, Decimal("1300.00"))
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-5"), Decimal("700.00"))

    def test_la_parte_cobrada_queda_de_rastro(self):
        self._aprobado("2000")
        pr.marcar_cobrados(self.s, "VEND-5", pago_id=None, cubierto=Decimal("1300"))
        saldados = self.s.scalars(
            select(PrestamoEmpleada).where(PrestamoEmpleada.estado == pr.COBRADO)
        ).all()
        self.assertEqual([Decimal(str(p.monto)) for p in saldados], [Decimal("1300.00")])

    def test_la_suma_no_cambia(self):
        self._aprobado("2000")
        pr.marcar_cobrados(self.s, "VEND-5", pago_id=None, cubierto=Decimal("1300"))
        total = sum(
            (Decimal(str(p.monto)) for p in self.s.scalars(select(PrestamoEmpleada)).all()),
            Decimal("0.00"),
        )
        self.assertEqual(total, Decimal("2000.00"))

    def test_el_viejo_se_salda_primero(self):
        # Por la puerta normal no se puede deber dos a la vez (`pedir` lo
        # impide), así que se arman a mano: lo que importa es que si alguna vez
        # hay dos, el pago se come el más viejo y no uno al azar.
        viejo, nuevo = (
            PrestamoEmpleada(employee_code="VEND-5", employee_name="Fanny Ortiz",
                             monto=Decimal(m), motivo="x", estado=pr.APROBADO)
            for m in ("500", "800")
        )
        self.s.add_all([viejo, nuevo])
        self.s.flush()
        pr.marcar_cobrados(self.s, "VEND-5", pago_id=None, cubierto=Decimal("500"))
        self.assertEqual(self.s.get(PrestamoEmpleada, viejo.id).estado, pr.COBRADO)
        self.assertEqual(self.s.get(PrestamoEmpleada, nuevo.id).estado, pr.APROBADO)

    def test_sin_cubierto_se_cobra_todo_como_antes(self):
        self._aprobado("2000")
        self.assertEqual(pr.marcar_cobrados(self.s, "VEND-5"), Decimal("2000.00"))
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-5"), Decimal("0.00"))

    def test_un_pago_de_cero_no_salda_nada(self):
        self._aprobado("2000")
        self.assertEqual(
            pr.marcar_cobrados(self.s, "VEND-5", pago_id=None, cubierto=Decimal("0")),
            Decimal("0.00"),
        )
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-5"), Decimal("2000.00"))
