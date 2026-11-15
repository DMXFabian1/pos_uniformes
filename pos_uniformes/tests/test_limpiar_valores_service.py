"""Limpieza de valores del catálogo (tanda 5 del alta, 2026-11-15). Sobre la mini caja (SQLite)."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select

from pos_uniformes.database.models import (
    AtributoProducto,
    CambioCatalogo,
    Escuela,
    Producto,
    TipoPrenda,
    Variante,
)
from pos_uniformes.services import limpiar_valores_service as lv
from pos_uniformes.services.catalog_service import CatalogService
from tests._ayuda_mini_caja import MiniCaja

D = Decimal


class LimpiarValoresTests(unittest.TestCase):
    def setUp(self) -> None:
        self.caja = MiniCaja(create_engine("sqlite://"))
        self.s = self.caja.s
        self.admin = self.caja.admin
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)
        c = self.caja
        c.prenda["Basico"] = TipoPrenda(nombre="Basico")  # el duplicado muerto de «Básico»
        basico = AtributoProducto(nombre="Basico")
        acentuado = AtributoProducto(nombre="Básico")
        self.s.add_all([c.prenda["Basico"], basico, acentuado])
        self.s.flush()
        self.atributo_basico, self.atributo_acentuado = basico, acentuado
        self.sku = 900
        # Camisa con tallas sueltas: Ch, M, G, XL → CH, MD, GD, EXG.
        self.camisa = self._general("Camisa Manga Larga Blanca", [("Ch", "Blanca"), ("M", "Blanca"),
                                                                   ("G", "Blanca"), ("XL", "Blanca")])
        # Blusa con XL y EXG del mismo color: choque, no se toca. En otro color sí.
        self.blusa = self._general("Blusa de Dama III", [("XL", "Rosa"), ("EXG", "Rosa"), ("XL", "Azul")])
        # Boina «Uni» y moño «NT» → Unitalla; el moño con atributo «Basico».
        self.boina = self._general("Boina Escolta Roja", [("Uni", "Rojo")])
        self.mono = self._general("Moño Azul", [("NT", "Azul")], atributo=basico)
        # La de ESTV que repite la escuela (tanda 1).
        estv = Escuela(nombre="ESTV 154")
        self.s.add(estv)
        self.s.flush()
        self.estv = self._general("Pants 3pz Deportivo Estv 154 ESTV 154", [("CH", "Sin color")], escuela=estv)
        self.s.commit()

    def _general(self, nombre, tallas, *, atributo=None, escuela=None) -> Producto:
        c = self.caja
        p = Producto(nombre=nombre, nombre_base=nombre, categoria_id=c.cat["Oficial"].id, marca_id=c.marca.id,
                     tipo_prenda_id=c.prenda["Básico"].id, atributo_id=atributo.id if atributo else None,
                     escuela_id=escuela.id if escuela else None, genero="Unisex")
        self.s.add(p)
        self.s.flush()
        for talla, color in tallas:
            self.sku += 1
            self.s.add(Variante(producto_id=p.id, sku=f"SKU{self.sku:06d}", talla=talla, color=color,
                                precio_venta=D(150), stock_actual=5))
        self.s.flush()
        return p

    def foto(self) -> dict[int, tuple]:
        self.s.expire_all()
        return {v.id: (v.sku, v.talla, v.color, v.precio_venta, v.stock_actual, v.producto_id)
                for v in self.s.scalars(select(Variante)).all()}

    def tallas_de(self, producto: Producto) -> list[tuple[str, str]]:
        self.s.expire_all()
        return sorted((v.talla, v.color) for v in self.s.scalars(
            select(Variante).where(Variante.producto_id == producto.id)).all())

    # ── Plan ─────────────────────────────────────────────────────────────

    def test_el_plan_agrupa_lo_que_se_junta(self) -> None:
        plan = lv.planear_limpieza(self.s)
        cambios = {(c.antes, c.despues): (len(c.variantes), len(c.productos)) for c in plan.tallas}
        self.assertEqual(cambios, {
            ("Ch", "CH"): (1, 1), ("M", "MD"): (1, 1), ("G", "GD"): (1, 1),
            ("XL", "EXG"): (2, 2),  # la de la camisa y la azul de la blusa
            ("Uni", "Unitalla"): (1, 1), ("NT", "Unitalla"): (1, 1),
        })
        self.assertEqual([(f.campo, f.de_nombre, f.a_nombre, len(f.productos)) for f in plan.taxonomias],
                         [("tipo_prenda", "Basico", "Básico", 0), ("atributo", "Basico", "Básico", 1)])
        self.assertEqual([n.despues for n in plan.nombres], ["Pants 3pz Deportivo ESTV 154"])
        self.assertIn(("Blanca", "Blanco", 4), plan.colores)
        self.assertTrue(any("«Deportiva» / «Deportivo»" in p for p in plan.parecidos), plan.parecidos)
        self.assertFalse(any("Pants 2pz" in p for p in plan.parecidos), plan.parecidos)
        texto = plan.texto()
        for esperado in ("TALLAS A JUNTAR (7 tallas de 4 prendas)", "«Uni» → «Unitalla»: 1 talla de 1 prenda",
                         "CHOQUES: NO SE TOCAN (1;", "COLORES (INFORMATIVO, NO SE TOCAN",
                         "SKU, precios y existencias no cambian."):
            self.assertIn(esperado, texto)

    def test_el_choque_se_lista_y_no_se_toca(self) -> None:
        plan = lv.planear_limpieza(self.s)
        self.assertEqual(len(plan.choques), 1)
        choque = plan.choques[0]
        self.assertEqual((choque.producto_id, choque.color, choque.talla_final),
                         (self.blusa.id, "Rosa", "EXG"))
        self.assertEqual(sorted(t.talla for t in choque.tallas), ["EXG", "XL"])
        self.assertTrue(all(t.variante_id not in plan.variantes for t in choque.tallas))
        lv.aplicar_limpieza(self.s, plan, self.admin, commit=True)
        self.assertEqual(self.tallas_de(self.blusa), [("EXG", "Azul"), ("EXG", "Rosa"), ("XL", "Rosa")])

    def test_planear_no_escribe(self) -> None:
        antes = self.foto()
        lv.planear_limpieza(self.s)
        self.s.rollback()
        self.assertEqual(self.foto(), antes)
        self.assertEqual(self.s.scalars(select(CambioCatalogo)).all(), [])

    # ── Aplicar ──────────────────────────────────────────────────────────

    def test_aplicar_cambia_solo_lo_planeado_y_nada_de_sku_precio_ni_existencia(self) -> None:
        antes = self.foto()
        plan = lv.planear_limpieza(self.s)
        resultado = lv.aplicar_limpieza(self.s, plan, self.admin, commit=True)
        self.assertEqual((resultado.tallas, resultado.prendas_movidas, resultado.taxonomias_apagadas,
                          resultado.nombres), (7, 1, 2, 1))
        despues = self.foto()
        self.assertEqual(set(despues), set(antes))
        for vid, (sku, talla, color, precio, stock, pid) in antes.items():
            d_sku, d_talla, d_color, d_precio, d_stock, d_pid = despues[vid]
            self.assertEqual((d_sku, d_color, d_precio, d_stock, d_pid), (sku, color, precio, stock, pid))
            self.assertEqual(d_talla, plan.variantes.get(vid, talla))
        self.assertEqual(self.tallas_de(self.camisa),
                         [("CH", "Blanca"), ("EXG", "Blanca"), ("GD", "Blanca"), ("MD", "Blanca")])
        self.assertEqual(self.tallas_de(self.mono), [("Unitalla", "Azul")])
        self.s.expire_all()
        self.assertEqual(self.s.get(Producto, self.mono.id).atributo.nombre, "Básico")
        self.assertFalse(self.s.get(AtributoProducto, self.atributo_basico.id).activo)
        self.assertFalse(self.s.get(TipoPrenda, self.caja.prenda["Basico"].id).activo)
        self.assertEqual(self.s.get(Producto, self.estv.id).nombre, "Pants 3pz Deportivo ESTV 154")
        # Los colores no se tocan.
        self.assertEqual(self.tallas_de(self.boina), [("Unitalla", "Rojo")])
        self.assertIn(("CH", "Blanca"), self.tallas_de(self.camisa))
        # Bitácora con la referencia.
        notas = self.s.scalars(select(CambioCatalogo.observacion)).all()
        self.assertEqual(len([n for n in notas if "talla «" in n]), 7)
        self.assertTrue(all(n.startswith(lv.REFERENCIA) for n in notas), notas)

    def test_la_segunda_corrida_no_hace_nada(self) -> None:
        lv.aplicar_limpieza(self.s, lv.planear_limpieza(self.s), self.admin, commit=True)
        plan = lv.planear_limpieza(self.s)
        self.assertFalse(plan.hay_cambios)
        self.assertEqual((plan.variantes, plan.taxonomias, plan.nombres), ({}, [], []))
        self.assertEqual(len(plan.choques), 1)  # el choque sigue listado para arreglarlo a mano
        antes = len(self.s.scalars(select(CambioCatalogo)).all())
        lv.aplicar_limpieza(self.s, plan, self.admin, commit=True)
        self.assertEqual(len(self.s.scalars(select(CambioCatalogo)).all()), antes)

    def test_solo_admin(self) -> None:
        antes = self.foto()
        with self.assertRaises(PermissionError):
            lv.aplicar_limpieza(self.s, lv.planear_limpieza(self.s), self.caja.cajera)
        self.s.rollback()
        self.assertEqual(self.foto(), antes)

    def test_todo_o_nada(self) -> None:
        antes = self.foto()
        plan = lv.planear_limpieza(self.s)
        with patch.object(CatalogService, "actualizar_producto", side_effect=RuntimeError("falla")):
            with self.assertRaises(RuntimeError):
                lv.aplicar_limpieza(self.s, plan, self.admin)
        self.s.rollback()
        self.assertEqual(self.foto(), antes)
        self.s.expire_all()
        self.assertEqual(self.s.get(Producto, self.mono.id).atributo.nombre, "Basico")
        self.assertEqual(self.s.scalars(select(CambioCatalogo)).all(), [])

    def test_plan_viejo_se_detiene(self) -> None:
        plan = lv.planear_limpieza(self.s)
        vid = next(iter(plan.variantes))
        self.s.get(Variante, vid).talla = "Otra"
        self.s.commit()
        with self.assertRaises(lv.PlanDesactualizado):
            lv.aplicar_limpieza(self.s, plan, self.admin)

    # ── Recetas y forma acentuada inactiva (revisión de la tanda 5) ──────

    def _talla(self, producto: Producto, talla: str, *, activo: bool = True) -> Variante:
        self.sku += 1
        v = Variante(producto_id=producto.id, sku=f"SKU{self.sku:06d}", talla=talla, color="Sin color",
                     precio_venta=D(600), stock_actual=3, activo=activo)
        self.s.add(v)
        self.s.flush()
        return v

    def test_la_receta_no_se_rompe_si_la_pieza_queda_en_choque(self) -> None:
        tres = self.caja.productos[("Miguel Hidalgo", "Pants 3pz")]
        dos = self.caja.productos[("Miguel Hidalgo", "Pants 2pz")]
        conjunto_xl = self._talla(tres, "XL")
        pieza_xl = self._talla(dos, "XL")
        self._talla(dos, "EXG", activo=False)  # intento viejo: hace choque en el Pants 2pz
        self.s.commit()
        plan = lv.planear_limpieza(self.s)
        self.assertTrue(any(c.producto_id == dos.id for c in plan.choques))
        self.assertNotIn(conjunto_xl.id, plan.variantes)
        self.assertNotIn(pieza_xl.id, plan.variantes)
        self.assertEqual(len(plan.choques_receta), 1)
        self.assertIn("«XL» de Pants 3pz Deportivo Miguel Hidalgo", plan.choques_receta[0])
        self.assertIn("RECETAS: NO SE TOCAN (1;", plan.texto())
        # Lo demás sí se limpia.
        self.assertIn(self.camisa.id, {pid for c in plan.tallas for pid in c.productos})

    def test_la_receta_no_se_rompe_si_el_conjunto_queda_en_choque(self) -> None:
        tres = self.caja.productos[("Miguel Hidalgo", "Pants 3pz")]
        dos = self.caja.productos[("Miguel Hidalgo", "Pants 2pz")]
        self._talla(tres, "XL")
        self._talla(tres, "EXG", activo=False)
        pieza_xl = self._talla(dos, "XL")
        self.s.commit()
        plan = lv.planear_limpieza(self.s)
        self.assertNotIn(pieza_xl.id, plan.variantes)
        lv.aplicar_limpieza(self.s, plan, self.admin, commit=True)
        self.s.expire_all()
        self.assertEqual(self.s.get(Variante, pieza_xl.id).talla, "XL")

    def test_la_receta_que_cambia_de_los_dos_lados_si_se_limpia(self) -> None:
        tres = self.caja.productos[("Miguel Hidalgo", "Pants 3pz")]
        dos = self.caja.productos[("Miguel Hidalgo", "Pants 2pz")]
        conjunto_xl, pieza_xl = self._talla(tres, "XL"), self._talla(dos, "XL")
        self.s.commit()
        plan = lv.planear_limpieza(self.s)
        self.assertEqual((plan.variantes.get(conjunto_xl.id), plan.variantes.get(pieza_xl.id)), ("EXG", "EXG"))
        self.assertEqual(plan.choques_receta, [])

    def test_la_forma_con_acento_inactiva_se_reactiva(self) -> None:
        self.atributo_acentuado.activo = False
        otra = self._general("Corbata Azul", [("Unitalla", "Azul")], atributo=self.atributo_acentuado)
        self.s.commit()
        plan = lv.planear_limpieza(self.s)
        fusion = next(f for f in plan.taxonomias if f.campo == "atributo")
        self.assertEqual((fusion.de_nombre, fusion.a_nombre, fusion.reactiva), ("Basico", "Básico", True))
        self.assertIn("«Básico» vuelve a quedar activo", fusion.texto)
        lv.aplicar_limpieza(self.s, plan, self.admin, commit=True)
        self.s.expire_all()
        self.assertTrue(self.s.get(AtributoProducto, self.atributo_acentuado.id).activo)
        self.assertFalse(self.s.get(AtributoProducto, self.atributo_basico.id).activo)
        self.assertEqual({self.s.get(Producto, i).atributo.nombre for i in (self.mono.id, otra.id)}, {"Básico"})


if __name__ == "__main__":
    unittest.main()
