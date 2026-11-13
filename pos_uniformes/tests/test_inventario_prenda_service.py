"""Vista «Por prenda» de Inventario (tanda 4): agrupar, escalera, totales,
precio, contada, orden y páginas. Puro: sin Qt ni base."""

from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pos_uniformes.services.inventario_prenda_service import (
    agrupar_por_prenda,
    filas_en_orden,
    indice_de_variante,
    ordenar_grupos,
    paginar_prendas,
    resumen_prendas,
    siguiente_orden_prenda,
    texto_contada_grupo,
    texto_escalera,
    texto_paginacion_prendas,
    texto_rango_precio,
)

AHORA = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
_ids = iter(range(1, 1_000_000))


def _fila(talla, stock, *, producto_id=1, prenda="Pants 2pz Muestra", color="Azul marino", precio=289, dias=10, **extra):
    vid = next(_ids)
    fila = {
        "variante_id": vid, "sku": f"SKU{vid:06d}", "producto_id": producto_id, "producto_nombre": prenda,
        "producto_nombre_base": prenda, "talla": talla, "color": color, "precio_venta": Decimal(precio),
        "stock_actual": stock, "stock_bodega": 0, "stock_piso": 0, "variante_activa": True, "stock_minimo": None,
        "ultimo_conteo_at": None if dias is None else AHORA - timedelta(days=dias),
        "rebaja_tipo": None, "rebaja_precio": None, "rebaja_hasta": None,
    }
    fila.update(extra)
    return fila


class AgruparTests(unittest.TestCase):
    def test_una_fila_por_prenda_y_color_con_tallas_en_orden_de_talla(self) -> None:
        filas = [
            _fila("12", -1), _fila("4", 3), _fila("EXG", 1), _fila("10", 2), _fila("CH", 0), _fila("6", 0), _fila("8", 5),
            _fila("8", 4, color="Blanco"),
            _fila("UNI", 2, producto_id=2, prenda="Bata"),
        ]
        grupos = agrupar_por_prenda(filas)
        self.assertEqual([(g.prenda, g.color) for g in grupos],
                         [("Pants 2pz Muestra", "Azul marino"), ("Pants 2pz Muestra", "Blanco"), ("Bata", "Azul marino")])
        self.assertEqual(grupos[0].texto_escalera, "4·3  6·0  8·5  10·2  12·−1  CH·0  EXG·1")
        self.assertEqual(grupos[0].tallas, 7)

    def test_el_color_se_agrupa_sin_importar_mayusculas_ni_acentos(self) -> None:
        grupos = agrupar_por_prenda([_fila("4", 1, color="Azul Marino"), _fila("6", 1, color="azul marino ")])
        self.assertEqual(len(grupos), 1)

    def test_tonos_de_la_escalera_como_la_columna_hay(self) -> None:
        filas = [_fila("4", -2), _fila("6", 0), _fila("8", 2), _fila("10", 9), _fila("12", 5, stock_minimo=8),
                 _fila("14", 7, variante_activa=False)]
        tonos = [(t.talla, t.tono) for t in agrupar_por_prenda(filas)[0].escalera]
        self.assertEqual(tonos, [("4", "danger"), ("6", "muted"), ("8", "warning"), ("10", ""), ("12", "warning"), ("14", "muted")])

    def test_piezas_suman_lo_positivo_y_dicen_donde(self) -> None:
        filas = [_fila("4", 6, stock_bodega=4), _fila("6", -2), _fila("8", 3, stock_piso=1)]
        grupo = agrupar_por_prenda(filas)[0]
        self.assertEqual(grupo.piezas, 9)
        self.assertEqual(grupo.texto_hay, "9")
        self.assertEqual(grupo.texto_donde, "Bodega 4 · Piso 1")
        self.assertEqual(agrupar_por_prenda([_fila("4", 2)])[0].texto_donde, "Tienda")
        self.assertEqual(agrupar_por_prenda([_fila("4", 0)])[0].texto_donde, "—")

    def test_conjuntos_salen_en_la_escalera_pero_no_suman_piezas(self) -> None:
        filas = [_fila("8", 4, producto_id=3, prenda="Pants 3pz", es_conjunto=True),
                 _fila("10", 0, producto_id=3, prenda="Pants 3pz", es_conjunto=True),
                 _fila("8", 5)]
        conjunto, pants = agrupar_por_prenda(filas)
        self.assertTrue(conjunto.es_conjunto)
        self.assertEqual(conjunto.piezas, 0)
        self.assertEqual(conjunto.texto_hay, "4")  # lo que se puede armar
        self.assertEqual(conjunto.texto_donde, "—")
        self.assertEqual([(t.cifra, t.tono) for t in conjunto.escalera], [("4", ""), ("0", "muted")])
        self.assertEqual(resumen_prendas([conjunto, pants]), "2 prendas · 5 piezas")

    def test_rango_de_precio_y_oferta(self) -> None:
        self.assertEqual(agrupar_por_prenda([_fila("4", 1, precio=250), _fila("6", 1, precio=265)])[0].texto_precio, "$250–$265")
        self.assertEqual(agrupar_por_prenda([_fila("4", 1), _fila("6", 1)])[0].texto_precio, "$289")
        grupo = agrupar_por_prenda([_fila("4", 1, rebaja_tipo="oferta", rebaja_precio=Decimal(175)), _fila("6", 1)])[0]
        self.assertEqual(grupo.texto_precio, "Oferta $175–$289")
        self.assertEqual(grupo.aviso_precio, "Oferta en 1 de 2 tallas")
        self.assertEqual(texto_rango_precio(None, None), "—")
        self.assertEqual(texto_rango_precio(Decimal("99.5"), Decimal("120")), "$99.50–$120")

    def test_descuadre_de_una_talla_lleva_la_marca_como_en_por_talla(self) -> None:
        # Talla 10: total −2 y 3 en Bodega (descuadre 3); talla 12: 4 en tienda.
        grupo = agrupar_por_prenda([_fila("10", -2, stock_bodega=3), _fila("12", 4)])[0]
        self.assertEqual(grupo.descuadre, 3)
        self.assertEqual(grupo.tallas_descuadre, 1)
        self.assertEqual(grupo.texto_donde, "Bodega 3 ⚠")
        self.assertEqual(grupo.aviso_donde, "Tienda 4 · Bodega 3. Ojo: en 1 talla hay en cajas 3 de más contra su total")
        cuadra = agrupar_por_prenda([_fila("4", 6, stock_bodega=4), _fila("8", 3, stock_piso=1)])[0]
        self.assertEqual(cuadra.descuadre, 0)
        self.assertEqual(cuadra.texto_donde, "Bodega 4 · Piso 1")
        self.assertEqual(cuadra.aviso_donde, "Tienda 4 · Bodega 4 · Piso 1")

    def test_oferta_y_liquidacion_mezcladas_no_se_disfrazan_de_una_sola(self) -> None:
        grupo = agrupar_por_prenda([
            _fila("4", 1, rebaja_tipo="oferta", rebaja_precio=Decimal(175)),
            _fila("6", 1, rebaja_tipo="oferta", rebaja_precio=Decimal(180)),
            _fila("8", 1, rebaja_tipo="liquidacion", rebaja_precio=Decimal(150)),
        ])[0]
        self.assertEqual(grupo.rebaja, "Rebaja")
        self.assertEqual(grupo.texto_precio, "Rebaja $150–$180")
        self.assertEqual(grupo.aviso_precio, "Oferta en 2 · Liquidación en 1 de 3 tallas")
        sola = agrupar_por_prenda([
            _fila("4", 1, rebaja_tipo="liquidacion", rebaja_precio=Decimal(150)),
            _fila("6", 1, rebaja_tipo="liquidacion", rebaja_precio=Decimal(150)),
        ])[0]
        self.assertEqual(sola.rebaja, "Liquidación")
        self.assertEqual(sola.aviso_precio, "Liquidación en todas sus tallas")

    def test_contada_dice_la_mas_vieja_o_nunca(self) -> None:
        grupo = agrupar_por_prenda([_fila("4", 1, dias=3), _fila("6", 1, dias=52), _fila("8", 1, dias=0)])[0]
        self.assertEqual(texto_contada_grupo(grupo, ahora=AHORA), "Hace 52d")
        grupo = agrupar_por_prenda([_fila("4", 1, dias=3), _fila("6", 1, dias=None)])[0]
        self.assertEqual(texto_contada_grupo(grupo, ahora=AHORA), "Nunca")
        self.assertEqual(texto_contada_grupo(agrupar_por_prenda([_fila("4", 1, dias=1)])[0], ahora=AHORA), "Ayer")

    def test_solo_agrupa_lo_que_paso_los_filtros(self) -> None:
        filas = [_fila("4", -1), _fila("6", 3), _fila("8", -2, producto_id=2, prenda="Bata"), _fila("10", 4, producto_id=2, prenda="Bata")]
        negativos = [f for f in filas if f["stock_actual"] < 0]
        grupos = agrupar_por_prenda(negativos)
        self.assertEqual([g.texto_escalera for g in grupos], ["4·−1", "8·−2"])
        self.assertEqual(resumen_prendas(grupos), "2 prendas")  # sin «0 piezas»
        self.assertEqual(filas_en_orden(grupos), negativos)

    def test_texto_escalera(self) -> None:
        self.assertEqual(texto_escalera(agrupar_por_prenda([_fila("", 2)])[0].escalera), "—·2")


class OrdenYPaginasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grupos = agrupar_por_prenda([
            _fila("4", 1, producto_id=1, prenda="Pants", precio=300, dias=5),
            _fila("4", 9, producto_id=2, prenda="Bata", precio=200, dias=None),
            _fila("4", 5, producto_id=3, prenda="Chamarra", precio=500, dias=60),
        ])

    def test_ordenar_por_columna(self) -> None:
        nombres = lambda gs: [g.prenda for g in gs]  # noqa: E731
        self.assertEqual(nombres(ordenar_grupos(self.grupos, "Prenda")), ["Bata", "Chamarra", "Pants"])
        self.assertEqual(nombres(ordenar_grupos(self.grupos, "Hay", descendente=True)), ["Bata", "Chamarra", "Pants"])
        self.assertEqual(nombres(ordenar_grupos(self.grupos, "Precio")), ["Bata", "Pants", "Chamarra"])
        self.assertEqual(nombres(ordenar_grupos(self.grupos, "Contada")), ["Bata", "Chamarra", "Pants"])
        self.assertEqual(nombres(ordenar_grupos(self.grupos, "Tallas")), ["Pants", "Bata", "Chamarra"])
        self.assertEqual(nombres(ordenar_grupos(self.grupos, None)), ["Pants", "Bata", "Chamarra"])

    def test_siguiente_orden(self) -> None:
        self.assertEqual(siguiente_orden_prenda((None, False), "Hay"), ("Hay", False))
        self.assertEqual(siguiente_orden_prenda(("Hay", False), "Hay"), ("Hay", True))
        self.assertEqual(siguiente_orden_prenda(("Hay", True), "Hay"), (None, False))
        self.assertEqual(siguiente_orden_prenda(("Hay", True), "Tallas"), ("Hay", True))

    def test_paginas_cuentan_prendas_y_saltan_a_la_de_la_talla(self) -> None:
        pagina = paginar_prendas(self.grupos, 0, 2)
        self.assertEqual((pagina.paginas, pagina.total, pagina.inicio, pagina.fin), (2, 3, 1, 2))
        self.assertEqual(texto_paginacion_prendas(pagina), "Mostrando 1–2 de 3 prendas")
        tercera = self.grupos[2].variante_ids[0]
        self.assertEqual(indice_de_variante(self.grupos, tercera), 2)
        pagina = paginar_prendas(self.grupos, 0, 2, variante_id=tercera)
        self.assertEqual((pagina.pagina, [g.prenda for g in pagina.grupos]), (1, ["Chamarra"]))
        self.assertEqual(paginar_prendas(self.grupos, 9, 2).pagina, 1)  # se acomoda a la última
        self.assertEqual(texto_paginacion_prendas(paginar_prendas(self.grupos, 0, 10)), "Mostrando 3 prendas")
        self.assertEqual(texto_paginacion_prendas(paginar_prendas([], 0, 10)), "Sin prendas con estos filtros")


class RendimientoTests(unittest.TestCase):
    def test_agrupar_5200_tallas_es_rapido(self) -> None:
        tallas = ("4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD", "EXG", "UNI")
        filas = []
        for producto in range(600):
            for color in ("Azul marino", "Blanco") if producto % 3 == 0 else ("Azul marino",):
                for talla in tallas[: 4 + producto % 8]:
                    filas.append(_fila(talla, (producto * 7 + len(talla)) % 9 - 2, producto_id=producto,
                                       prenda=f"Prenda {producto}", color=color, dias=None if producto % 5 == 0 else producto % 90))
        filas = filas[:5200]
        self.assertEqual(len(filas), 5200)
        inicio = time.perf_counter()
        grupos = agrupar_por_prenda(filas)
        ordenar_grupos(grupos, "Hay")
        paginar_prendas(grupos, 0, 100)
        transcurrido = time.perf_counter() - inicio
        self.assertGreater(len(grupos), 500)
        self.assertLess(transcurrido, 0.1, f"agrupar tardó {transcurrido * 1000:.0f} ms")


if __name__ == "__main__":
    unittest.main()
