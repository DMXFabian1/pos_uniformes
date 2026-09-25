"""Los últimos cortes, con lo que faltó o sobró.

Un corte con $300 de diferencia no enteraba a nadie hasta que alguien lo
buscaba en la PC (Daniel, 2026-09-25). Al estrenarlo con datos reales salió
que 9 de 10 cortes quedaban cortos en cifras redondas que no coinciden con
los retiros anotados — por eso el texto sugiere /retiro cuando ve ese patrón.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from pos_uniformes.services import telegram_cortes_service as ct


def _fila(dia=18, contado="16082", esperado="17082", quien="Daniel", ops=11):
    return ct.CorteFila(
        fecha=date(2026, 9, dia), hora="17:49", quien=quien,
        contado=Decimal(contado), esperado=Decimal(esperado), operaciones=ops,
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


class LaPistaDelRetiroTest(unittest.TestCase):
    """Cuando falta casi siempre y en cifras redondas, lo más probable no es un
    descuadre: es dinero que salió sin quedar apuntado."""

    def _muchas_redondas(self):
        return [
            _fila(dia=18, contado="16082", esperado="17082"),   # 1,000
            _fila(dia=19, contado="16627", esperado="17627"),   # 1,000
            _fila(dia=20, contado="20548", esperado="22548"),   # 2,000
        ]

    def test_con_varias_redondas_sugiere_anotar_el_retiro(self):
        r = ct.texto(self._muchas_redondas())
        self.assertIn("no quedó apuntado", r)
        self.assertIn("/retiro", r)

    def test_una_sola_no_dispara_la_sospecha(self):
        r = ct.texto([_fila(contado="16082", esperado="17082")])
        self.assertNotIn("no quedó apuntado", r)

    def test_si_lo_que_falta_no_es_redondo_no_la_sugiere(self):
        filas = [
            _fila(dia=d, contado=str(1000 - n), esperado="1000")
            for d, n in ((18, 137), (19, 241), (20, 89))
        ]
        self.assertNotIn("no quedó apuntado", ct.texto(filas))

    def test_lo_que_SOBRA_no_cuenta_como_retiro(self):
        filas = [_fila(dia=d, contado="2000", esperado="1000") for d in (18, 19, 20)]
        self.assertNotIn("no quedó apuntado", ct.texto(filas))


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
