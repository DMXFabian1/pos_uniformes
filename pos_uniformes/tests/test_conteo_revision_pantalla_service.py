"""La pantalla nueva de «Revisar conteo» (tanda 3): chips, orden, grupos y botones."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from pos_uniformes.services import conteo_revision_pantalla_service as p
from pos_uniformes.services.conteo_resumen_service import TallaResumen, resumir
from pos_uniformes.services.revision_service import BIEN, NO_SE_MUEVE, PEDIR, SURTIR, URGENTE

M = "−"


def _l(cid, talla, *, producto="Playera Chazarilla Azul Marino", color="AZUL MARINO", estado=NO_SE_MUEVE,
       conto=5, sugerido=0, surtir=0, en_cajas=0, cajas=()):
    return SimpleNamespace(
        conteo_id=cid, talla=talla, producto=producto, color=color, estado=estado, conto=conto,
        sugerido=sugerido, surtir=surtir, en_cajas=en_cajas, cajas=cajas,
        vendidas=0, dias_observados=41, ritmo_semana=0.0, semanas_cubiertas=None, pidieron=0,
        ellas_sugieren=None, pedido_anterior=None, pedido_anterior_at=None, vendidas_desde_pedido=None,
        anterior=None, anterior_at=None,
    )


def _t(cid, *, sistema=5, conto=5, vendidas=0, tienda=None, precio="185", ajustado=False, posterior=None, producto="P"):
    dif = conto - sistema
    tienda = sistema - vendidas if tienda is None else tienda
    return TallaResumen(
        conteo_id=cid, variante_id=cid, producto=producto, talla=str(cid), stock_sistema=sistema, conto=conto,
        diferencia=dif, ajustado=ajustado, vendidas_desde=vendidas, tienda_hoy=tienda,
        queda_hoy=tienda if ajustado else tienda + dif, precio_venta=Decimal(precio) if precio else None,
        ajuste_posterior=posterior,
    )


def _caso_86():
    """La 86: 15 tallas, 4 con diferencia (8 −1, 32 −4, 34 −1, 36 −1)."""
    tallas = ("4", "6", "8", "10", "12", "14", "16", "18", "20", "32", "34", "36", "38", "40", "42")
    dif = {"8": (7, 6, "185"), "32": (10, 6, "199"), "34": (9, 8, "199"), "36": (19, 18, "205")}
    vend = {"16": 5, "32": 2, "34": 2, "38": 1, "40": 3}
    lineas, resumen = [], []
    for i, t in enumerate(tallas, start=1):
        sistema, conto, precio = dif.get(t, (6, 6, "185"))
        lineas.append(_l(i, t, conto=conto, estado=BIEN if t in ("16", "32", "34") else NO_SE_MUEVE,
                         en_cajas=12 if t == "32" else 0, cajas=(("A-12", 12),) if t == "32" else ()))
        resumen.append(_t(i, sistema=sistema, conto=conto, vendidas=vend.get(t, 0), precio=precio))
    return lineas, resumir(resumen, jornada_id=86)


class ChipsTests(unittest.TestCase):
    def test_la_86_corrige_4_tallas_y_lo_demas_en_cero(self) -> None:
        lineas, ajuste = _caso_86()
        chips = p.chips(lineas, ajuste)
        self.assertEqual([c.clave for c in chips], ["AJUSTE", URGENTE, PEDIR, SURTIR])
        self.assertEqual(chips[0].texto, f"Corrige 4 tallas · faltan 7 · sobran 0 · {M}$1,385")
        self.assertEqual((chips[0].n, chips[0].tono, chips[0].tocable), (4, p.TONO_AJUSTE, True))
        for c in chips[1:]:
            self.assertEqual((c.n, c.tono, c.tocable), (0, p.TONO_CERO, False))
        self.assertEqual([c.texto for c in chips[1:]], ["Urgente 0", "Pedir 0", "Surtir 0"])

    def test_sin_diferencias_todo_cuadra_y_en_gris(self) -> None:
        lineas = [_l(1, "6"), _l(2, "8")]
        ajuste = resumir([_t(1), _t(2)])
        chip = p.chips(lineas, ajuste)[0]
        self.assertEqual((chip.texto, chip.tono, chip.tocable), ("Todo cuadra", p.TONO_CERO, False))

    def test_surtir_va_en_gris_con_la_nota_de_las_cajas(self) -> None:
        lineas = [_l(1, "6", estado=SURTIR, surtir=4, en_cajas=12), _l(2, "8", estado=URGENTE, sugerido=3),
                  _l(3, "10", estado=PEDIR, sugerido=6), _l(4, "12", estado=PEDIR, sugerido=2)]
        chips = {c.clave: c for c in p.chips(lineas, resumir([_t(i) for i in range(1, 5)]))}
        self.assertEqual((chips[SURTIR].texto, chips[SURTIR].tono, chips[SURTIR].nota),
                         ("Surtir 1", p.TONO_NEUTRO, "cajas sin recontar desde el 16-jul"))
        self.assertTrue(chips[SURTIR].tocable)
        self.assertEqual((chips[URGENTE].texto, chips[URGENTE].tono), ("Urgente 1", p.TONO_PELIGRO))
        self.assertEqual((chips[PEDIR].texto, chips[PEDIR].tono), ("Pedir 2", p.TONO_ADVERTENCIA))

    def test_tocar_un_chip_filtra_y_otra_vez_lo_quita(self) -> None:
        self.assertEqual(p.tocar_chip(None, PEDIR), PEDIR)
        self.assertIsNone(p.tocar_chip(PEDIR, PEDIR))
        self.assertEqual(p.tocar_chip(PEDIR, "AJUSTE"), "AJUSTE")

    def test_ya_revisada_dice_lo_que_se_corrigio_o_que_no_se_uso(self) -> None:
        resumen = resumir([_t(1, sistema=10, conto=6, ajustado=True), _t(2, sistema=3, conto=4, ajustado=True), _t(3)])
        self.assertEqual(p.texto_chip_ajuste(resumen, ya_revisada=True),
                         "Corrigió 2 tallas · faltaban 4 · sobraban 1")
        no_usada = resumir([_t(1, sistema=10, conto=6), _t(2)])
        self.assertEqual(p.texto_chip_ajuste(no_usada, ya_revisada=True, aplicada=False),
                         "1 talla con diferencia · no se usó")


class EncabezadoTests(unittest.TestCase):
    def test_una_prenda_dice_la_prenda_con_su_color_una_vez(self) -> None:
        lineas = [_l(1, "4", producto="Playera Chazarilla", color="AZUL MARINO")]
        self.assertEqual(p.titulo_encabezado(lineas, "Básicos · Playera Chazarilla"),
                         "Playera Chazarilla · Azul Marino · Básicos")
        # El color ya en el nombre no se repite.
        lineas = [_l(1, "4", producto="Playera Chazarilla Azul Marino", color="AZUL MARINO")]
        self.assertEqual(p.titulo_encabezado(lineas, "Básicos · Playera Chazarilla"),
                         "Playera Chazarilla Azul Marino · Básicos")

    def test_varias_prendas_dice_la_escuela(self) -> None:
        lineas = [_l(1, "4", producto="Playera Uno"), _l(2, "6", producto="Pants Uno")]
        self.assertEqual(p.titulo_encabezado(lineas, "Uno"), "Uno")

    def test_subtitulo_quien_cuando_y_cuantas(self) -> None:
        lineas, _ = _caso_86()
        texto = p.subtitulo_encabezado(quien="Stayce Chavarria", contado=date(2026, 10, 5), lineas=lineas,
                                       hoy=date(2026, 11, 15))
        self.assertEqual(texto, "Contó Stayce Chavarria · lun 5 oct · hace 41 días · 15 tallas")
        varias = [_l(1, "4", producto="A"), _l(2, "4", producto="B")]
        self.assertTrue(p.subtitulo_encabezado(quien="X", contado=None, lineas=varias).endswith("2 tallas · 2 prendas"))

    def test_el_pedido_solo_si_hay(self) -> None:
        self.assertEqual(p.texto_pedido({1: None, 2: 0}), "")
        self.assertEqual(p.texto_pedido({1: 21, 2: None}), "Tu pedido: <b>21</b> piezas en 1 talla")


class TablaTests(unittest.TestCase):
    def test_la_86_las_de_diferencia_primero_y_el_separador(self) -> None:
        lineas, ajuste = _caso_86()
        filas = p.filas_tabla(lineas, ajuste, {}, titulo="Básicos · Playera Chazarilla")
        self.assertEqual([f.tipo for f in filas[:5]], ["talla"] * 4 + ["separador"])
        self.assertEqual([f.celdas[p.COL_TALLA] for f in filas[:4]], ["8", "32", "34", "36"])
        self.assertEqual(filas[4].texto, "sin diferencia (11)")
        self.assertEqual(len(filas), 16)                    # sin fila de prenda: es una sola
        t32 = filas[1]
        self.assertEqual(t32.celdas[:6], ("32", "10", "6", f"{M}4", "2", "4"))   # 10 − 2 vendidas − 4
        self.assertEqual(t32.tono_dif, p.DIF_FALTAN)
        self.assertIn("A-12 ×12", t32.ayuda_que)
        self.assertIn("16-jul", t32.ayuda_que)
        sin_dif = next(f for f in filas if f.tipo == "talla" and f.celdas[0] == "16")
        self.assertEqual((sin_dif.celdas[p.COL_DIF], sin_dif.tono_dif), ("·", p.DIF_CUADRA))

    def test_en_su_orden_sin_separador(self) -> None:
        lineas, ajuste = _caso_86()
        filas = p.filas_tabla(lineas, ajuste, {}, en_su_orden=True)
        self.assertEqual([f.celdas[0] for f in filas], [l.talla for l in lineas])
        self.assertNotIn("separador", {f.tipo for f in filas})

    def test_el_filtro_deja_solo_su_grupo(self) -> None:
        lineas, ajuste = _caso_86()
        filas = p.filas_tabla(lineas, ajuste, {}, filtro="AJUSTE")
        self.assertEqual([f.celdas[0] for f in filas], ["8", "32", "34", "36"])
        self.assertEqual(p.filas_tabla(lineas, ajuste, {}, filtro=PEDIR), [])

    def test_varias_prendas_con_fila_de_grupo_y_sin_columna_prenda(self) -> None:
        lineas = [
            _l(1, "6", producto="Playera Uno", color="BLANCO"), _l(2, "8", producto="Playera Uno", color="BLANCO"),
            _l(3, "10", producto="Pants Uno", color="GRIS", estado=PEDIR, sugerido=6),
        ]
        ajuste = resumir([_t(1), _t(2, sistema=5, conto=3), _t(3)])
        filas = p.filas_tabla(lineas, ajuste, {3: 6}, titulo="Uno")
        self.assertEqual([f.tipo for f in filas], ["prenda", "talla", "separador", "talla", "prenda", "talla"])
        self.assertEqual(filas[0].texto, "Playera · Blanco   —   1 con diferencia")
        self.assertEqual(filas[1].celdas[0], "8")         # la talla sin el color
        self.assertEqual(filas[2].texto, "sin diferencia (1)")
        self.assertEqual(filas[4].texto, "Pants · Gris   —   pedir 6")
        self.assertEqual(filas[5].celdas[p.COL_PEDIDO], "6")

    def test_una_prenda_de_varios_colores_si_dice_el_color(self) -> None:
        lineas = [_l(1, "6", producto="Playera", color="BLANCO"), _l(2, "6", producto="Playera", color="AZUL")]
        filas = p.filas_tabla(lineas, resumir([_t(1), _t(2)]), {})
        self.assertEqual([f.celdas[0] for f in filas], ["6 Blanco", "6 Azul"])

    def test_queda_hoy_negativo_dice_recontar(self) -> None:
        linea = _l(1, "10", conto=0)
        fila = p.fila_talla(linea, _t(1, sistema=2, conto=0, vendidas=1), None)
        self.assertEqual(fila.celdas[p.COL_QUEDA], f"{M}1 · recontar")
        self.assertEqual(fila.tono_queda, "recontar")
        self.assertEqual(fila.celdas[p.COL_QUE], "se acabó")
        self.assertEqual(fila.tono_conto, "cero")

    def test_otro_ajuste_despues_lleva_el_ojo(self) -> None:
        fila = p.fila_talla(_l(1, "36"), _t(1, sistema=19, conto=18, posterior=datetime(2026, 10, 20, 18)), None)
        self.assertTrue(fila.celdas[p.COL_QUE].startswith("⚠ otro ajuste el 20 oct · "))
        self.assertEqual(fila.tono_que, p.QUE_OJO)

    def test_ya_revisada_queda_lo_de_hoy(self) -> None:
        t = _t(1, sistema=10, conto=6, vendidas=2)          # sin aplicar: 8 − 4 = 4
        self.assertEqual(p.fila_talla(_l(1, "32"), t, None).celdas[p.COL_QUEDA], "4")
        self.assertEqual(p.fila_talla(_l(1, "32"), t, None, ya_revisada=True).celdas[p.COL_QUEDA], "8")

    def test_surtir_dice_de_cajas_con_asterisco(self) -> None:
        fila = p.fila_talla(_l(1, "6", estado=SURTIR, surtir=4, en_cajas=12), _t(1), None)
        self.assertEqual(fila.celdas[p.COL_QUE], "surtir 4 de cajas*")
        self.assertEqual(fila.tono_que, p.QUE_GRIS)

    def test_sin_resumen_no_revienta(self) -> None:
        fila = p.fila_talla(_l(1, "6"), None, 3)
        self.assertEqual(fila.celdas[1:6], ("—", "5", "—", "—", "—"))
        self.assertEqual(fila.celdas[p.COL_PEDIDO], "3")

    def test_todas_las_columnas(self) -> None:
        lineas, ajuste = _caso_86()
        fila = p.fila_todas(lineas[9], p.tallas_por_id(ajuste)[10], 5, titulo="Básicos · Playera Chazarilla")
        self.assertEqual(len(fila), len(p.COLUMNAS_TODAS))
        self.assertEqual(fila[:8], ("Playera Chazarilla Azul Marino", "32 Azul Marino", "10", "6", f"{M}4", "2", "4", "12"))
        self.assertEqual(fila[p.COLUMNAS_TODAS.index("Pedido")], "5")
        self.assertEqual(fila[-1], "primer conteo")


class BotonesTests(unittest.TestCase):
    def test_corregir_con_la_cifra_dentro(self) -> None:
        _, ajuste = _caso_86()
        self.assertEqual(p.texto_boton_corregir(ajuste), f"Corregir inventario (4 tallas, {M}7 pz)")
        self.assertEqual(p.texto_boton_corregir(resumir([_t(1, sistema=3, conto=4)])), "Corregir inventario (1 talla, +1 pz)")
        self.assertEqual(p.texto_boton_corregir(resumir([_t(1)])), "Marcar como revisado")
        self.assertEqual(p.texto_boton_corregir(None), "Marcar como revisado")

    def test_que_se_ve_segun_el_estado(self) -> None:
        self.assertEqual(p.acciones(ya_revisada=False, pedidos={1: None}), p.Acciones(True, True, False))
        self.assertEqual(p.acciones(ya_revisada=True, pedidos={1: 4}), p.Acciones(False, False, True))

    def test_listo_y_siguiente(self) -> None:
        _, ajuste = _caso_86()
        self.assertEqual(p.texto_listo("aplicada", ajuste),
                         f"Se corrigieron 4 tallas: faltaban 7, sobraban 0 ({M}$1,385 a precio de venta).")
        self.assertEqual(p.texto_listo("aplicada", resumir([_t(1)])), "Quedó revisado: ninguna talla cambió.")
        self.assertIn("No se usó", p.texto_listo("descartada", ajuste))
        self.assertEqual(p.siguiente_por_revisar([9, 86, 4], 86), 9)
        self.assertEqual(p.siguiente_por_revisar([86], 86), None)
        self.assertEqual(p.texto_quedan(0), "No queda ningún conteo por revisar.")
        self.assertEqual(p.texto_quedan(1), "Queda 1 conteo por revisar.")
        self.assertEqual(p.texto_orden(False), "↕ En su orden")


if __name__ == "__main__":
    unittest.main()
