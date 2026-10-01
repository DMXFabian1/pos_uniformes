"""Los últimos cortes, con lo que faltó o sobró.

Un corte con $300 de diferencia no enteraba a nadie hasta que alguien lo
buscaba en la PC (Daniel, 2026-09-25). Al estrenarlo salió que 9 de 10 cortes
quedaban cortos... y resultó que eran los ajustes del propio Daniel con
«Ajustar la venta», no dinero perdido (2026-10-01). Por eso el ajuste se
nombra ajuste y no enciende la alarma.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from pos_uniformes.services import telegram_cortes_service as ct


def _fila(dia=18, contado="16082", esperado="17082", quien="Daniel", ops=11, ajustado=False):
    return ct.CorteFila(
        fecha=date(2026, 9, dia), hora="17:49", quien=quien,
        contado=Decimal(contado), esperado=Decimal(esperado), operaciones=ops,
        ajustado=ajustado,
    )


class LaCuentaTest(unittest.TestCase):
    def test_la_diferencia_es_contado_menos_esperado(self):
        self.assertEqual(_fila(contado="900", esperado="1000").diferencia, Decimal("-100.00"))
        self.assertEqual(_fila(contado="1100", esperado="1000").diferencia, Decimal("100.00"))

    def test_lo_chico_no_llama_la_atencion(self):
        self.assertFalse(_fila(contado="999", esperado="1000").llama_la_atencion)
        self.assertTrue(_fila(contado="900", esperado="1000").llama_la_atencion)


class ComoSeLeeTest(unittest.TestCase):
    def test_sin_cortes_lo_dice(self):
        self.assertIn("No hay cortes", ct.texto([], dias=14))

    def test_dice_si_falto_o_sobro_y_cuanto(self):
        r = ct.texto([_fila(contado="900", esperado="1000")])
        self.assertIn("faltó $100.00", r)
        r = ct.texto([_fila(contado="1100", esperado="1000")])
        self.assertIn("sobró $100.00", r)

    def test_el_que_cuadra_se_celebra(self):
        r = ct.texto([_fila(contado="1000", esperado="1000")])
        self.assertIn("✅ cuadró", r)
        self.assertIn("ninguno se pasa", r)

    def test_dice_quien_y_cuantas_operaciones(self):
        r = ct.texto([_fila(quien="Fanny Ortiz", ops=32)])
        self.assertIn("Fanny Ortiz", r)
        self.assertIn("32 ops", r)

    def test_señala_el_peor(self):
        filas = [_fila(contado="900", esperado="1000"), _fila(dia=19, contado="0", esperado="2149")]
        self.assertIn("$2,149.00", ct.texto(filas))


class ElAjusteNoEsUnDescuadreTest(unittest.TestCase):
    """Daniel bajaba la cifra del corte a mano con «Ajustar la venta», y el
    bot lo contaba como «faltó $2,000» — dinero perdido donde no lo había
    (2026-10-01). Un ajuste lo decidió él; un descuadre, nadie."""

    def test_el_ajuste_se_dice_ajuste(self):
        r = ct.texto([_fila(contado="16082", esperado="17082", ajustado=True)])
        self.assertIn("✏️ ajustado −$1,000.00", r)
        self.assertNotIn("faltó", r)

    def test_el_ajuste_no_enciende_la_alarma(self):
        self.assertFalse(_fila(contado="900", esperado="1000", ajustado=True).llama_la_atencion)
        self.assertTrue(_fila(contado="900", esperado="1000").llama_la_atencion)

    def test_sin_ajuste_sigue_diciendo_falto(self):
        self.assertIn("faltó", ct.texto([_fila(contado="900", esperado="1000")]))

    def test_dice_cuanto_sumaron_los_ajustes(self):
        filas = [
            _fila(dia=18, contado="16082", esperado="17082", ajustado=True),
            _fila(dia=19, contado="20548", esperado="22548", ajustado=True),
        ]
        r = ct.texto(filas)
        self.assertIn("2 con ajuste tuyo, −$3,000.00", r)

    def test_sin_ajustes_no_menciona_el_tema(self):
        self.assertNotIn("ajuste tuyo", ct.texto([_fila(contado="1000", esperado="1000")]))


class ElBotLoConoceTest(unittest.TestCase):
    def test_esta_en_la_ayuda_el_despachador_y_el_menu(self):
        from pathlib import Path

        from pos_uniformes.services.telegram_bot_service import AYUDA

        self.assertIn("/cortes", AYUDA)
        base = Path(__file__).resolve().parent.parent / "services"
        self.assertIn('cmd.nombre == "cortes"', (base / "telegram_bot_service.py").read_text(encoding="utf-8"))
        menu = (base / "telegram_menu_service.py").read_text(encoding="utf-8")
        self.assertIn('"m:cortes"', menu)


if __name__ == "__main__":
    unittest.main()
