"""«Cómo va el día» — el vistazo de tres veces al día.

El resumen de la noche es para cerrar; este es para asomarse (Daniel,
2026-09-25). Lo que se cuida: que solo hable de **dinero real** y que los
apartados no se cuelen en el total, porque son dinero comprometido, no
cobrado.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal

from pos_uniformes.services.resumen_diario_service import DatosResumen, texto_hoy

_AHORA = datetime(2026, 9, 25, 14, 30)


def _datos(**kw) -> DatosResumen:
    base = dict(
        fecha=date(2026, 9, 25), operaciones=10, piezas=17,
        efectivo=Decimal("5000.00"), tarjeta=Decimal("1200.00"),
        abonos=Decimal("0.00"), apartados=Decimal("0.00"),
        ventas=Decimal("6200.00"),
    )
    base.update(kw)
    return DatosResumen(**base)


class LoQueEntroTest(unittest.TestCase):
    def test_suma_efectivo_tarjeta_y_abonos(self):
        r = texto_hoy(_datos(abonos=Decimal("300.00")), ahora=_AHORA)
        self.assertIn("Entró: $6,500.00", r)      # 5000 + 1200 + 300
        self.assertIn("efectivo $5,000.00", r)
        self.assertIn("tarjeta $1,200.00", r)
        self.assertIn("abonos $300.00", r)

    def test_sin_abonos_no_ensucia_la_linea(self):
        self.assertNotIn("abonos", texto_hoy(_datos(), ahora=_AHORA))

    def test_los_apartados_no_entran_al_total(self):
        """Dinero comprometido, no cobrado. La regla de la Libreta."""
        r = texto_hoy(_datos(apartados=Decimal("4000.00")), ahora=_AHORA)
        self.assertIn("Entró: $6,200.00", r)      # sin los 4,000
        self.assertIn("comprometido, no cobrado", r)

    def test_dice_operaciones_y_piezas(self):
        self.assertIn("10 operaciones · 17 piezas", texto_hoy(_datos(), ahora=_AHORA))

    def test_sin_ventas_lo_dice_sin_inventar_ceros(self):
        r = texto_hoy(_datos(operaciones=0, piezas=0), ahora=_AHORA)
        self.assertIn("Todavía no se registra ninguna venta", r)
        self.assertNotIn("Entró", r)


class QuienEstaTest(unittest.TestCase):
    def test_los_nombra(self):
        r = texto_hoy(_datos(), quien_esta=["Evelyn", "Stayce"], ahora=_AHORA)
        self.assertIn("Evelyn, Stayce", r)

    def test_si_no_hay_nadie_no_pone_la_linea_vacia(self):
        self.assertNotIn("👥", texto_hoy(_datos(), quien_esta=[], ahora=_AHORA))


class ElCorteTest(unittest.TestCase):
    def test_avisa_cuantas_horas_lleva_sin_corte(self):
        self.assertIn("5 horas", texto_hoy(_datos(horas_sin_corte=5.4), ahora=_AHORA))

    def test_una_hora_se_dice_en_singular(self):
        self.assertIn("una hora", texto_hoy(_datos(horas_sin_corte=1.2), ahora=_AHORA))

    def test_recien_cortado_no_molesta(self):
        r = texto_hoy(_datos(horas_sin_corte=0.3, cortes=[object()]), ahora=_AHORA)
        self.assertNotIn("Sin corte", r)

    def test_si_no_hubo_corte_en_todo_el_dia_lo_dice(self):
        r = texto_hoy(_datos(horas_sin_corte=None), ahora=_AHORA)
        self.assertIn("Todavía no hay corte hoy", r)


class ElBotLoConoceTest(unittest.TestCase):
    def test_esta_en_la_ayuda_el_despachador_y_el_menu(self):
        from pathlib import Path

        from pos_uniformes.services.telegram_bot_service import AYUDA

        self.assertIn("/hoy", AYUDA)
        base = Path(__file__).resolve().parent.parent / "services"
        bot = (base / "telegram_bot_service.py").read_text(encoding="utf-8")
        self.assertIn('cmd.nombre == "hoy"', bot)
        menu = (base / "telegram_menu_service.py").read_text(encoding="utf-8")
        self.assertIn('"m:hoy"', menu)
        self.assertIn('"hoy": "/hoy"', menu)


if __name__ == "__main__":
    unittest.main()
