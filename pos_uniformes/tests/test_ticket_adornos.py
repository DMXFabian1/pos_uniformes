"""Los adornos festivos del ticket dibujado.

Lo que se cuida: que el texto del ticket no cambie ni un carácter con el tema,
que los renglones de datos salgan iguales con o sin adorno, que no haya
manchas negras que coman papel, y que apagarlos devuelva el ticket de antes.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services import temporada_service as temp
from pos_uniformes.services import ticket_adornos_service as ad
from pos_uniformes.services import ticket_imagen_service as ti

TEMAS = tuple(ad.ADORNOS)


def _ticket(items, *, terminos=6, marcador="dia_de_muertos"):
    """Un ticket de venta con la misma forma que arma Venta Rápida."""
    lineas = [
        f"{temp.MARCADOR_INICIO}logo|MAXIMODA{temp.MARCADOR_FIN}",
        "           Ticket de venta            ",
        "┌────────────────────────────────────┐",
        "│ Fecha:            10/10/2026 13:43 │",
        "│ Atendió:            Nayeli Herrera │",
        "├────────────────────────────────────┤",
        "│             ARTÍCULOS              │",
        "├────────────────────────────────────┤",
    ]
    total = 0
    for nombre, talla, cant, precio in items:
        importe = cant * precio
        total += importe
        lineas.append(f"│ {nombre[:34]:<34} │")
        izq = f"T.{talla}  {cant} x ${precio:,.2f}"
        der = f"${importe:,.2f}"
        lineas.append(f"│ {izq:<{34 - len(der)}}{der} │")
        lineas.append("├────────────────────────────────────┤")
    lineas[-1] = "├────────────────────────────────────┤"
    lineas.append(f"│ {len(items)} artículos{'':<24}│")
    lineas.append(f"│ Subtotal:{'':>{24 - len(f'${total:,.2f}')}}${total:,.2f} │")
    lineas.append("└────────────────────────────────────┘")
    lineas.append("╔════════════════════════════════════╗")
    tot = f"${total:,.2f}"
    lineas.append(f"║ TOTAL A PAGAR:{'':>{20 - len(tot)}}{tot} ║")
    lineas.append("╚════════════════════════════════════╝")
    lineas.append("")
    lineas.append("        Términos y Condiciones        ")
    for i in range(terminos):
        lineas.append(f"{i + 1}. Condición número {i + 1} del ticket de")
        lineas.append("   prueba, con su renglón de más.")
    lineas.append("")
    lineas.append("        Gracias por su compra.        ")
    if marcador:
        lineas.append(f"{temp.MARCADOR_INICIO}{marcador}{temp.MARCADOR_FIN}")
        lineas.append("         Feliz Día de Muertos         ")
    return "\n".join(lineas)


UNO = [("Playera Polo Blanca", "10", 1, 185.0)]
VARIOS = [
    ("Playera Polo Blanca", "10", 2, 185.0),
    ("Pants Suelto Punto Azul Marino", "12", 1, 309.0),
    ("Suéter Escolar Vino con Escudo Bordado", "8", 3, 420.5),
    ("Falda Tableada Gris Oxford", "14", 1, 265.75),
]
MUCHOS = [(f"Prenda número {i} de nombre largo", str(6 + i), i % 3 + 1, 99.99 + i) for i in range(1, 19)]


def _tinta(imagen, x0=0, y0=0, x1=None, y1=None) -> int:
    """Pixeles negros en el rectángulo (x0, y0)-(x1, y1)."""
    x1 = imagen.width() if x1 is None else x1
    y1 = imagen.height() if y1 is None else y1
    negros = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if imagen.pixelColor(x, y).red() < 128:
                negros += 1
    return negros


def _filas_distintas(a, b) -> list[int]:
    assert a.size() == b.size()
    return [
        y for y in range(a.height())
        if any(a.pixelColor(x, y) != b.pixelColor(x, y) for x in range(0, a.width(), 2))
    ]


class _ConApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class ElTemaSaleDelTicketTests(unittest.TestCase):
    def test_se_lee_del_marcador_de_temporada(self) -> None:
        self.assertEqual(ad.tema_del_ticket(_ticket(UNO, marcador="halloween")), "halloween")

    def test_el_logo_no_es_un_tema(self) -> None:
        self.assertIsNone(ad.tema_del_ticket(_ticket(UNO, marcador="")))

    def test_hay_un_adorno_por_temporada(self) -> None:
        self.assertEqual(set(TEMAS), set(temp.ARCHIVOS.values()))

    def test_los_aliases_en_ingles_llegan_al_mismo_adorno(self) -> None:
        self.assertIs(ad.adorno_de("valentines_day"), ad.ADORNOS["san_valentin"])
        self.assertIsNone(ad.adorno_de("pascua"))

    def test_los_puntos_de_adorno_son_los_del_aire(self) -> None:
        self.assertEqual(ad.punto_de_adorno("│             ARTÍCULOS              │", None), ad.FLANCOS)
        self.assertEqual(ad.punto_de_adorno("        Términos y Condiciones        ", None), ad.TERMINOS)
        self.assertEqual(ad.punto_de_adorno("           Ticket de venta            ", None), ad.CABECERA)
        self.assertEqual(ad.punto_de_adorno("│ 3 artículos · 4 piezas             │", None), ad.RESUMEN)
        self.assertEqual(ad.punto_de_adorno("", "        Términos y Condiciones        "), ad.DIVISOR)
        self.assertEqual(ad.punto_de_adorno("", "        Gracias por su compra.        "), ad.GRECA)
        self.assertIsNone(ad.punto_de_adorno("│ Playera Polo Blanca                │", None))
        self.assertIsNone(ad.punto_de_adorno("", "1. Revise su mercancía"))


class LosDatosNoCambianTests(_ConApp):
    def test_el_texto_del_ticket_es_el_mismo_para_los_ocho(self) -> None:
        """Los adornos viven en el dibujo: el texto que ve la pantalla, el
        camino de QPrinter y ESC/POS en texto no se toca."""
        def cuerpo(texto: str) -> str:
            # Todo lo que va ANTES del dibujo del pie: el pie (dibujo y saludo)
            # ya cambiaba por temporada desde antes y queda fuera de esto.
            lineas = texto.split("\n")
            corte = next(i for i, l in enumerate(lineas) if l.strip().startswith(temp.MARCADOR_INICIO) and "logo" not in l)
            return "\n".join(lineas[:corte])

        base = cuerpo(_ticket(VARIOS, marcador="halloween"))
        for tema in TEMAS:
            with self.subTest(tema=tema):
                self.assertEqual(cuerpo(_ticket(VARIOS, marcador=tema)), base)

    def test_los_renglones_de_articulos_salen_identicos_con_y_sin_adorno(self) -> None:
        """Solo artículos, sin encabezado ni términos: no hay motivo que poner
        en los renglones de texto. Con adorno la caja gana 9 puntos de aire
        arriba y abajo (para las esquinas), así que los renglones de texto se
        comparan desplazados y sin los 40 puntos de cada orilla, que es donde
        viven las esquinas."""
        solo_items = "\n".join([
            "┌────────────────────────────────────┐",
            "│ Playera Polo Blanca                │",
            "│ T.10  2 x $185.00          $370.00 │",
            "├────────────────────────────────────┤",
            "│ Subtotal:                  $370.00 │",
            "└────────────────────────────────────┘",
        ])
        plano = ti.render_ticket(solo_items, adornos=False)
        alto_linea = (plano.height() - ti.MARGEN * 2) // 6
        for tema in TEMAS:
            with self.subTest(tema=tema):
                con = ti.render_ticket(solo_items, adornos=True, tema=tema)
                self.assertEqual(con.height(), plano.height() + 18)
                for y in range(ti.MARGEN + alto_linea, ti.MARGEN + alto_linea * 5):
                    for x in range(40, 536, 2):
                        self.assertEqual(
                            plano.pixelColor(x, y), con.pixelColor(x, y + 9), f"{tema} ({x},{y})"
                        )

    def test_apagados_el_ticket_es_el_de_antes(self) -> None:
        texto = _ticket(VARIOS)
        sin = ti.render_ticket(texto, adornos=False)
        self.assertEqual(_filas_distintas(sin, ti.render_ticket(texto, adornos=False, tema="halloween")), [])

    def test_el_ajuste_de_la_maquina_los_apaga(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import escpos_settings_cache_service as esc

        texto = _ticket(VARIOS)
        apagado = esc.EscPosSettings(adornos_de_temporada=False)
        with patch.object(esc, "load_escpos_settings", return_value=apagado):
            self.assertEqual(_filas_distintas(ti.render_ticket(texto, adornos=False), ti.render_ticket(texto)), [])


class LosOchoImprimenLoMismoTests(_ConApp):
    def test_mismo_ancho_mismo_alto_para_la_misma_venta(self) -> None:
        texto = _ticket(VARIOS)
        altos = {tema: ti.render_ticket(texto, adornos=True, tema=tema).height() for tema in TEMAS}
        self.assertEqual(len(set(altos.values())), 1, altos)
        self.assertTrue(all(ti.render_ticket(texto, adornos=True, tema=t).width() == 576 for t in TEMAS))

    def test_con_adorno_el_ticket_crece_solo_en_los_renglones_adornados(self) -> None:
        """Los renglones con motivo grande crecen, las cajas ganan aire para
        las esquinas y la greca cierra el marco: unos 20 cm de papel menos
        de un cuarto más alto, nunca el doble."""
        texto = _ticket(VARIOS)
        sin = ti.render_ticket(texto, adornos=False)
        con = ti.render_ticket(texto, adornos=True, tema="halloween")
        self.assertGreater(con.height(), sin.height())
        self.assertLess(con.height() - sin.height(), 240)

    def test_datos_dificiles_no_rompen_ninguna_variante(self) -> None:
        casos = {
            "uno": _ticket(UNO),
            "varios_con_decimales": _ticket(VARIOS),
            "muchos_renglones": _ticket(MUCHOS, terminos=12),
            "terminos_largos": _ticket(UNO, terminos=20),
        }
        for nombre, texto in casos.items():
            for tema in TEMAS:
                with self.subTest(caso=nombre, tema=tema):
                    img = ti.render_ticket(texto, adornos=True, tema=tema)
                    self.assertEqual(img.width(), 576)
                    self.assertGreater(img.height(), 300)


class NadaDeManchasNegrasTests(_ConApp):
    def test_los_adornos_no_gastan_papel(self) -> None:
        """Lo que agregan los adornos es poca tinta: trazos, no masas."""
        texto = _ticket(VARIOS)
        sin = ti.render_ticket(texto, adornos=False)
        base = _tinta(sin)
        for tema in TEMAS:
            with self.subTest(tema=tema):
                con = ti.render_ticket(texto, adornos=True, tema=tema)
                extra = _tinta(con) - base
                self.assertGreater(extra, 0, "no se dibujó nada")
                self.assertLess(extra, con.width() * con.height() * 0.035)

    def test_ninguna_franja_es_mas_negra_que_blanca(self) -> None:
        texto = _ticket(VARIOS)
        for tema in TEMAS:
            with self.subTest(tema=tema):
                img = ti.render_ticket(texto, adornos=True, tema=tema)
                for y0 in range(0, img.height() - 24, 24):
                    franja = _tinta(img, 0, y0, img.width(), y0 + 24)
                    self.assertLess(franja, img.width() * 24 * 0.5, f"franja y={y0}")

    def test_el_total_sigue_siendo_una_caja_doble_dibujada(self) -> None:
        self.assertTrue(ti._es_regla("╔════════════════════════════════════╗"))
        self.assertTrue(ti._es_regla("╚════════════════════════════════════╝"))


class LosMotivosSePuedenDibujarTests(_ConApp):
    def test_cada_motivo_deja_tinta_dentro_de_su_caja(self) -> None:
        from PyQt6.QtGui import QColor, QImage, QPainter

        motivos = {}
        for adorno in ad.ADORNOS.values():
            for d in (adorno.flanco, adorno.esquina, adorno.mini, adorno.cabecera, *adorno.greca):
                motivos[d.__name__] = d
        for nombre, dibujo in motivos.items():
            with self.subTest(motivo=nombre):
                lienzo = QImage(60, 60, QImage.Format.Format_RGB32)
                lienzo.fill(QColor("white"))
                p = QPainter(lienzo)
                dibujo(p, 10, 10, 40)
                p.end()
                self.assertGreater(_tinta(lienzo, 10, 10, 50, 50), 20)
                # No se sale de su caja más que el trazo (3 puntos de tolerancia).
                self.assertEqual(_tinta(lienzo, 0, 0, 60, 6) + _tinta(lienzo, 0, 54, 60, 60)
                                 + _tinta(lienzo, 0, 0, 6, 60) + _tinta(lienzo, 54, 0, 60, 60), 0)


if __name__ == "__main__":
    unittest.main()
