"""Las empleadas apuntan gastos de la tienda.

Daniel, 2026-10-01: *"un gasto relacionado a la tienda, no de ellas"*. Es el
mismo retiro del cajón de siempre — el corte lo cuenta en «Gastos» — pero lo
apunta quien esté atendiendo: el dinero YA salió, y lo que importa es que
quede escrito en el momento, no que alguien lo autorice después.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaRetiro, Empleada
from pos_uniformes.services.retiros_service import registrar_gasto, registrar_retiro

_VISTA = Path(__file__).resolve().parent.parent / "ui" / "views" / "quick_sale_view.py"


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-5", nombre_completo="Fanny Ortiz", activo=True))
        self.s.commit()

    def _gastos(self):
        return self.s.scalars(select(CajaRetiro)).all()


class ApuntarTest(_Base):
    def test_una_empleada_si_puede_apuntar_un_gasto(self):
        """El retiro del dueño exige ser dueño; el gasto no, y esa es la idea."""
        with self.assertRaises(PermissionError):
            registrar_retiro(self.s, monto="85", motivo="bolsas", creado_por="VEND-5")
        g = registrar_gasto(self.s, monto="85", motivo="bolsas", employee_code="VEND-5")
        self.assertEqual(Decimal(str(g.monto)), Decimal("85.00"))
        self.assertEqual(g.creado_por, "VEND-5")

    def test_queda_como_retiro_para_que_el_corte_cuadre(self):
        registrar_gasto(self.s, monto="85", motivo="bolsas", employee_code="VEND-5")
        self.assertEqual(len(self._gastos()), 1)

    def test_sin_gafete_no_se_apunta(self):
        with self.assertRaises(PermissionError):
            registrar_gasto(self.s, monto="85", motivo="bolsas", employee_code="")
        self.assertEqual(self._gastos(), [])

    def test_sin_decir_en_que_no_se_apunta(self):
        # Sin motivo, el corte de la noche es un misterio.
        with self.assertRaises(ValueError):
            registrar_gasto(self.s, monto="85", motivo="   ", employee_code="VEND-5")
        self.assertEqual(self._gastos(), [])

    def test_ni_cero_ni_negativo(self):
        for malo in ("0", "-50"):
            with self.assertRaises(ValueError):
                registrar_gasto(self.s, monto=malo, motivo="bolsas", employee_code="VEND-5")
        self.assertEqual(self._gastos(), [])

    def test_el_motivo_largo_no_rompe_la_columna(self):
        g = registrar_gasto(self.s, monto="85", motivo="x" * 400, employee_code="VEND-5")
        self.assertLessEqual(len(g.motivo), 120)


class ElBotonTest(unittest.TestCase):
    """Se revisa el guion: armar venta rápida pide base y gafete."""

    def setUp(self) -> None:
        self.fuente = _VISTA.read_text(encoding="utf-8")

    def test_el_boton_vive_junto_a_sin_codigo(self):
        self.assertIn('QPushButton("🧾  Gasto")', self.fuente)
        self.assertIn("_on_gasto_tienda", self.fuente)

    def test_sin_gafete_se_le_dice(self):
        self.assertIn("Entra con tu gafete para apuntar un gasto", self.fuente)

    def test_trae_los_gastos_de_siempre_de_un_toque(self):
        self.assertIn('GASTOS_RAPIDOS = ("Bolsas", "Agua", "Papelería", "Limpieza", "Mandado", "Otro")', self.fuente)

    def test_una_cifra_grande_se_confirma(self):
        # $1,000 en bolsas casi siempre es un dedazo.
        self.assertIn('if monto >= Decimal("1000")', self.fuente)
        self.assertIn("¿Seguro que fueron", self.fuente)

    def test_le_dice_que_ya_le_llego_a_daniel(self):
        self.assertIn("Ya le llegó a Daniel", self.fuente)


if __name__ == "__main__":
    unittest.main()
