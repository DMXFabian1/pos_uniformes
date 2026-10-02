"""Temporadas: el detalle del calendario en el ticket y en la pantalla.

Idea de Daniel (02/10). Lo que se cuida: que el dibujo no se desarme al
centrarlo, que quepa en el papel, que la mayor parte del año no salga nada, y
que un adorno jamás detenga un ticket.
"""

from __future__ import annotations

import unittest
from datetime import date

from pos_uniformes.services import temporada_service as t


class CalendarioTests(unittest.TestCase):
    def test_las_fechas_que_pidio(self) -> None:
        self.assertEqual(t.actual(date(2026, 10, 31)).nombre, "Halloween")
        self.assertEqual(t.actual(date(2026, 11, 2)).nombre, "Día de Muertos")
        self.assertEqual(t.actual(date(2026, 12, 24)).nombre, "Navidad")

    def test_el_regreso_a_clases_tambien(self) -> None:
        # Para una tienda de uniformes es LA temporada, no una fiesta más.
        self.assertEqual(t.actual(date(2026, 8, 1)).nombre, "Regreso a clases")

    def test_casi_todo_el_año_no_hay_nada(self) -> None:
        # Un adorno que sale siempre deja de notarse, y entonces no adorna.
        sin_temporada = sum(
            1 for d in _todos_los_dias(2026) if t.actual(d) is None
        )
        self.assertGreater(sin_temporada, 200, "hay temporada demasiados días")

    def test_navidad_cruza_el_año(self) -> None:
        self.assertEqual(t.actual(date(2026, 12, 31)).nombre, "Año nuevo y Reyes")
        self.assertEqual(t.actual(date(2027, 1, 5)).nombre, "Año nuevo y Reyes")
        self.assertIsNone(t.actual(date(2027, 1, 20)))

    def test_ningun_dia_cae_en_dos(self) -> None:
        for d in _todos_los_dias(2026):
            coinciden = [x.nombre for x in t.TEMPORADAS if x.incluye(d)]
            self.assertLessEqual(len(coinciden), 1, f"{d}: {coinciden}")


def _todos_los_dias(anio: int):
    from datetime import timedelta

    d = date(anio, 1, 1)
    while d.year == anio:
        yield d
        d += timedelta(days=1)


class ElDibujoDelTicketTests(unittest.TestCase):
    def test_todos_los_renglones_del_dibujo_miden_igual(self) -> None:
        # Si no, al centrarlos uno por uno cada uno agarra un margen distinto
        # y el dibujo queda hecho un reguero de símbolos.
        for temporada in t.TEMPORADAS:
            renglones = t.renglones_de_ticket(_un_dia_de(temporada))
            arte = renglones[:-1]            # el último es el saludo
            anchos = {len(a) for a in arte}
            self.assertEqual(len(anchos), 1, f"{temporada.nombre}: {anchos}")

    def test_centrado_conserva_la_forma(self) -> None:
        # Las sangrías internas del dibujo SON el dibujo (el arbolito es ancho
        # abajo y angosto arriba): lo que tiene que ser igual para todos es el
        # margen que les agrega el centrado, no dónde empieza la tinta.
        arte = t.renglones_de_ticket(date(2026, 12, 10))[:-1]
        margen = (t.ANCHO_TICKET - len(arte[0])) // 2
        for linea in arte:
            centrado = linea.center(t.ANCHO_TICKET)
            self.assertTrue(centrado.startswith(" " * margen))
            self.assertEqual(centrado[margen:margen + len(linea)], linea)

    def test_cabe_en_el_papel(self) -> None:
        for temporada in t.TEMPORADAS:
            for renglon in t.renglones_de_ticket(_un_dia_de(temporada)):
                self.assertLessEqual(
                    len(renglon), t.ANCHO_TICKET, f"{temporada.nombre}: «{renglon}»"
                )

    def test_no_se_come_el_ticket(self) -> None:
        # El papel cuesta y el ticket se guarda.
        for temporada in t.TEMPORADAS:
            self.assertLessEqual(
                len(t.renglones_de_ticket(_un_dia_de(temporada))), t.MAX_RENGLONES + 1
            )

    def test_el_dibujo_es_ASCII_sin_emoji(self) -> None:
        # La térmica dibuja texto con una fuente monoespaciada: los emoji no
        # salen, y cuando no salen salen como cuadritos.
        for temporada in t.TEMPORADAS:
            for renglon in temporada.arte:
                self.assertTrue(renglon.isascii(), f"{temporada.nombre}: «{renglon}»")

    def test_un_dia_cualquiera_no_agrega_nada(self) -> None:
        self.assertEqual(t.renglones_de_ticket(date(2026, 3, 18)), [])

    def test_siempre_termina_con_el_saludo(self) -> None:
        # El saludo pesa más que el dibujo: es lo que la señora lee.
        for temporada in t.TEMPORADAS:
            self.assertEqual(
                t.renglones_de_ticket(_un_dia_de(temporada))[-1], temporada.saludo
            )


def _un_dia_de(temporada: t.Temporada) -> date:
    mes, dia = temporada.desde
    anio = 2026 if mes >= 2 else 2027
    return date(anio, mes, dia)


class EnLaPantallaTests(unittest.TestCase):
    def test_el_saludo_trae_su_emoji(self) -> None:
        texto = t.saludo_de_pantalla(date(2026, 10, 31))
        self.assertIn("🎃", texto)
        self.assertIn("Halloween", texto)

    def test_un_dia_cualquiera_no_dice_nada(self) -> None:
        self.assertEqual(t.saludo_de_pantalla(date(2026, 3, 18)), "")

    def test_cada_temporada_trae_color_propio(self) -> None:
        for temporada in t.TEMPORADAS:
            self.assertRegex(temporada.color, r"^#[0-9a-fA-F]{6}$")


class NuncaDetieneUnTicketTests(unittest.TestCase):
    def test_si_el_adorno_truena_el_ticket_sale_igual(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        lineas = ["TOTAL", "Gracias por su compra."]
        with patch.object(t, "renglones_de_ticket", side_effect=RuntimeError("boom")):
            QuickSaleWidget._append_temporada(lineas)
        self.assertEqual(lineas, ["TOTAL", "Gracias por su compra."])

    def test_va_despues_del_gracias(self) -> None:
        # Ahora se emite el marcador del PNG; el saludo va debajo.
        from unittest.mock import patch

        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        lineas = ["Gracias por su compra."]
        with patch.object(t, "actual", return_value=t.TEMPORADAS[2]):
            QuickSaleWidget._append_temporada(lineas)
        self.assertEqual(lineas[0], "Gracias por su compra.")
        self.assertTrue(any(t.MARCADOR_INICIO in l for l in lineas))
        self.assertIn(t.TEMPORADAS[2].saludo, lineas[-1])

    def test_sin_png_cae_al_dibujo_de_ascii(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        lineas: list[str] = []
        with patch.object(t, "actual", return_value=t.TEMPORADAS[2]), \
                patch.object(t, "imagen_para_marcador", return_value=None):
            QuickSaleWidget._append_temporada(lineas)
        self.assertFalse(any(t.MARCADOR_INICIO in l for l in lineas))
        self.assertTrue(any('.-"""-.' in l for l in lineas))

    def test_solo_en_la_copia_del_cliente(self) -> None:
        # La de la tienda se archiva; no necesita adornos.
        from pathlib import Path

        codigo = (
            Path(__file__).resolve().parents[1] / "ui" / "views" / "quick_sale_view.py"
        ).read_text(encoding="utf-8")
        trozo = codigo[codigo.index("if not store_copy:"):]
        self.assertIn("_append_temporada(lines)", trozo[:600])


if __name__ == "__main__":
    unittest.main()


class ElTicketSeLeeTests(unittest.TestCase):
    """Lo que el cliente se lleva a su casa (Daniel, 02/10: hay que mejorarlo)."""

    def test_las_cantidades_llevan_coma_de_millares(self) -> None:
        # En una tienda de uniformes se pasa de mil sin querer, y «$1395.00» se
        # lee de dos veces.
        from pos_uniformes.ui.helpers.ticket_print_layout_helper import tk_fmt

        self.assertEqual(tk_fmt("1395"), "1,395.00")
        self.assertEqual(tk_fmt("12850.5"), "12,850.50")
        self.assertEqual(tk_fmt("750"), "750.00")

    def test_una_cantidad_rara_no_detiene_el_ticket(self) -> None:
        from pos_uniformes.ui.helpers.ticket_print_layout_helper import tk_fmt

        self.assertEqual(tk_fmt("no soy un numero"), "no soy un numero")

    def test_el_ticket_lleva_acentos(self) -> None:
        # El pipeline imprime ┌─┐╞═╡, que es más exótico que una tilde: que
        # fuera sin acentos era costumbre, no limitación. Y un ticket sin
        # acentos se lee como hecho a las carreras.
        from pathlib import Path

        codigo = (
            Path(__file__).resolve().parents[1] / "ui" / "views" / "quick_sale_view.py"
        ).read_text(encoding="utf-8")
        for malo in ("Atendio:", "ARTICULOS", "Terminos y Condiciones", "REIMPRESION"):
            self.assertNotIn(malo, codigo, malo)
