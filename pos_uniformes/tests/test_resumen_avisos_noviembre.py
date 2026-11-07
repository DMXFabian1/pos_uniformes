"""El resumen de la noche, sin avisos que mienten (auditoría 2026-11-07)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from pos_uniformes.services.resumen_diario_service import DatosResumen, formatear, texto_hoy


class SinCorteNoEsAlarmaTests(unittest.TestCase):
    """«❗ SIN CORTE HOY» salía casi a diario: el resumen sale a las 17:45,
    antes del corte de la tarde."""

    def test_con_corte_ayer_es_lo_normal(self) -> None:
        t = formatear(DatosResumen(fecha=date(2026, 11, 7), operaciones=12, horas_sin_corte=24.2,
                                   ultimo_corte_fecha=date(2026, 11, 6)))
        self.assertNotIn("❗", t)
        self.assertIn("Todavía no hay corte de hoy", t)

    def test_si_ayer_no_hubo_corte_si_se_dice(self) -> None:
        t = formatear(DatosResumen(fecha=date(2026, 11, 7), operaciones=12, horas_sin_corte=48.0,
                                   ultimo_corte_fecha=date(2026, 11, 5)))
        self.assertIn("❗ AYER NO HUBO CORTE. El último fue el 05/11", t)

    def test_sin_ventas_no_hay_alarma(self) -> None:
        t = formatear(DatosResumen(fecha=date(2026, 11, 7), operaciones=0, horas_sin_corte=48.0,
                                   ultimo_corte_fecha=date(2026, 11, 5)))
        self.assertNotIn("❗", t)


class ApartadosSinMontoTests(unittest.TestCase):
    """Regla «solo dinero real»: el apartado no se cobró."""

    def test_se_dice_cuantos_no_cuanto(self) -> None:
        d = DatosResumen(fecha=date(2026, 11, 7), operaciones=5, apartados=Decimal("3450"), apartados_n=2)
        for texto in (formatear(d), texto_hoy(d, ahora=datetime(2026, 11, 7, 13, 0))):
            with self.subTest(texto=texto[:20]):
                self.assertIn("2 apartados nuevos (no es dinero cobrado)", texto)
                self.assertNotIn("3,450", texto)


class ElResumenCuentaElDiaCompletoTests(unittest.TestCase):
    """Si Daniel contestaba la propuesta de las 17:30 antes de las 17:45, el
    resumen salía «Sin operaciones desde el corte de hoy a las 17:3x»."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import LibretaCorte, LibretaVenta

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.hoy = date.today()
        tz = datetime.now().astimezone().tzinfo
        en = lambda d, h, m: datetime.combine(d, time(h, m), tzinfo=tz)  # noqa: E731
        ayer = self.hoy - timedelta(days=1)
        self.s.add(LibretaCorte(fecha=ayer, monto_final=Decimal("1000"), creado_por="VEND-1",
                                desde=en(ayer - timedelta(days=1), 18, 0), hasta=en(ayer, 18, 45),
                                created_at=en(ayer, 18, 45)))
        self.s.add(LibretaCorte(fecha=self.hoy, monto_final=Decimal("3000"), creado_por="VEND-1",
                                desde=en(ayer, 18, 45), hasta=en(self.hoy, 0, 3), created_at=en(self.hoy, 0, 3)))
        for h, monto in ((0, "100"), (0, "250")):
            self.s.add(LibretaVenta(employee_code="VEND-2", employee_name="Ana", tipo="venta", piezas=1,
                                    monto_total=Decimal(monto), monto_neto=Decimal(monto),
                                    created_at=en(self.hoy, h, 1)))
        self.s.add(LibretaVenta(employee_code="VEND-2", employee_name="Ana", tipo="venta", piezas=1,
                                monto_total=Decimal("40"), monto_neto=Decimal("40"),
                                created_at=en(self.hoy, 0, 4)))
        self.s.commit()

    def test_el_resumen_cuenta_desde_el_primer_corte_de_hoy(self) -> None:
        from pos_uniformes.services.resumen_diario_service import recolectar

        # Corte de hoy a las 00:03: antes, el resumen solo veía la venta de las 00:04.
        self.assertEqual(recolectar(self.s, self.hoy).operaciones, 1)
        d = recolectar(self.s, self.hoy, todo_el_dia=True)
        self.assertEqual(d.operaciones, 3)
        self.assertEqual(d.ventas, Decimal("390.00"))

    def test_el_bot_y_la_tarea_piden_el_dia_completo(self) -> None:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[1]
        # /resumen ayer: el día cambia, el «día completo» no (sección 5).
        self.assertIn("formatear(recolectar(session, dia, todo_el_dia=True))",
                      (raiz / "services" / "telegram_bot_service.py").read_text(encoding="utf-8"))
        self.assertIn("formatear(recolectar(session, hoy, todo_el_dia=True))",
                      (raiz / "scripts" / "resumen_diario_telegram.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
