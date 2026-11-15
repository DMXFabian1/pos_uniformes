"""El motor para la prenda general o de temporada (tanda 4 del alta, 2026-11-15)."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, func, select

from pos_uniformes.database.models import (
    Categoria,
    Marca,
    MovimientoInventario,
    Producto,
    TipoPrenda,
    UniformePieza,
    Variante,
)
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services.catalog_service import CatalogService
from tests._ayuda_mini_caja import MiniCaja

D = Decimal


def temporada(caja: MiniCaja) -> Producto:
    """Agrega a la mini caja la ropa de temporada del 20-oct: un chaleco Ykan, Surtido."""
    s = caja.s
    prenda = TipoPrenda(nombre="Temporada")
    categoria = Categoria(nombre="Temporada")
    marca = Marca(nombre="Ykan")
    s.add_all([prenda, categoria, marca])
    s.flush()
    p = Producto(nombre="Chaleco Mujer KY17002", nombre_base="Chaleco Mujer KY17002", categoria_id=categoria.id,
                 marca_id=marca.id, tipo_prenda_id=prenda.id, tipo_pieza_id=caja.pieza["Chaleco"].id, genero="Mujer")
    s.add(p)
    s.flush()
    for i, talla in enumerate(("Infantil", "Adulto"), start=900):
        s.add(Variante(producto_id=p.id, sku=f"SKU{i:06d}", talla=talla, color="Surtido",
                       precio_venta=D(389), stock_actual=0))
    s.commit()
    return p


class GeneralTests(unittest.TestCase):
    def setUp(self) -> None:
        self.caja = MiniCaja(create_engine("sqlite://"))
        self.s = self.caja.s
        self.chaleco = temporada(self.caja)
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)

    def contar(self, modelo) -> int:
        return int(self.s.scalar(select(func.count()).select_from(modelo)))

    def plan(self, **kw) -> alta.PlanPrenda:
        datos = dict(tallas=valores.JUEGOS_TALLAS["Infantil · Adulto"], marca="Ykan", color="Surtido",
                     tipo_prenda="Temporada", tipo_pieza="Chaleco", precio=389)
        datos.update(kw)
        return alta.planear_general(self.s, "Chaleco Mujer KY18005", **datos)

    def test_juegos_de_tallas(self) -> None:
        self.assertEqual(list(valores.JUEGOS_TALLAS),
                         ["Unitalla", "Infantil · Adulto", "Infantil · Juvenil · Adulto", "CH · MD · GD · EXG"])
        self.assertEqual(valores.JUEGOS_TALLAS["CH · MD · GD · EXG"], ("CH", "MD", "GD", "EXG"))

    def test_parecida_ofrece_igual_que_esta(self) -> None:
        parecidas = alta.parecidas_generales(self.s, "chaleco mujer ky18005")
        self.assertEqual([p.nombre for p in parecidas], ["Chaleco Mujer KY17002"])
        p = parecidas[0]
        self.assertEqual((p.marca, p.tipo_prenda, p.tipo_pieza, p.categoria), ("Ykan", "Temporada", "Chaleco", "Temporada"))
        self.assertEqual(p.tallas, (("Infantil", D(389)), ("Adulto", D(389))))
        self.assertEqual(p.texto, "2 tallas · $389 · Ykan")
        self.assertEqual(alta.parecidas_generales(self.s, "Sudadera MO194"), [])
        # Las prendas de escuela no cuentan.
        self.assertEqual(alta.parecidas_generales(self.s, "Pants Suelto Nuevo"), [])

    def test_plan_completo_y_aplicar(self) -> None:
        plan = self.plan(llegan={"Infantil": 70}, costo=130)
        self.assertTrue(plan.puede_aplicar, plan.todos_los_errores)
        self.assertEqual(plan.nombre, "Chaleco Mujer KY18005")
        self.assertEqual(plan.categoria, "Temporada")  # se llena sola
        self.assertEqual([t.talla for t in plan.tallas], ["Infantil", "Adulto"])
        self.assertEqual(plan.resumen, "Se crean 2 tallas de Chaleco Mujer KY18005, a $389.")
        self.assertFalse(plan.ligar)
        uniformes = self.contar(UniformePieza)
        resultado = alta.aplicar(self.s, plan, self.caja.admin, plan.origen, commit=True)
        creado = resultado.productos[0]
        self.assertIsNone(creado.escuela)
        self.assertIsNone(creado.uniforme)
        self.assertEqual(self.contar(UniformePieza), uniformes)
        variantes = self.s.scalars(select(Variante).where(Variante.producto_id == creado.producto_id)).all()
        self.assertEqual({(v.talla, v.color, v.precio_venta, v.costo_referencia) for v in variantes},
                         {("Infantil", "Surtido", D(389), D(130)), ("Adulto", "Surtido", D(389), D(130))})
        self.assertEqual(sum(v.stock_actual for v in variantes), 70)
        self.assertEqual(self.contar(MovimientoInventario), 1)
        self.assertTrue(creado.bitacora.startswith(alta.ORIGEN_GENERAL))

    def test_precio_por_talla_gana_al_unico(self) -> None:
        plan = self.plan(precio=389, precios_por_talla={"Adulto": 419})
        self.assertEqual({t.talla: t.precio for t in plan.tallas}, {"Infantil": D(389), "Adulto": D(419)})

    def test_marca_color_y_tipo_se_eligen_siempre(self) -> None:
        plan = self.plan(marca="", color="", tipo_prenda="", tipo_pieza="")
        self.assertFalse(plan.puede_aplicar)
        for e in ("Elige el color.", "Elige el tipo de prenda.", "Elige la pieza.", "Falta la marca."):
            self.assertIn(e, plan.errores)

    def test_sin_precio_o_en_cero_frena(self) -> None:
        plan = self.plan(precio=None)
        self.assertEqual({t.error for t in plan.tallas}, {"Falta el precio."})
        plan = self.plan(precio=0)
        self.assertEqual({t.error for t in plan.tallas}, {"El precio no puede quedar en $0."})

    def test_no_compara_con_las_demas_escuelas(self) -> None:
        plan = self.plan(precio=99)
        self.assertEqual({t.aviso for t in plan.tallas}, {""})
        self.assertEqual({t.sugerencia_5_9 for t in plan.tallas}, {None})  # 99 ya termina en 9

    def test_marca_nueva_pregunta(self) -> None:
        plan = self.plan(marca="Fertoni")
        self.assertIn("«Fertoni» no existe como marca. Elígela de la lista o confirma que es nueva.", plan.errores)
        plan = self.plan(marca="Fertoni", confirmados=["Fertoni"])
        self.assertTrue(plan.puede_aplicar, plan.todos_los_errores)

    def test_nombre_repetido_frena(self) -> None:
        plan = alta.planear_general(self.s, "Chaleco Mujer KY17002", tallas=["Unitalla"], marca="Ykan",
                                    color="Surtido", tipo_prenda="Temporada", tipo_pieza="Chaleco", precio=389)
        self.assertIn("Ya existe «Chaleco Mujer KY17002».", plan.errores)

    def test_igual_que_esta_otro_modelo(self) -> None:
        m = alta.datos_de_modelo(self.s, self.chaleco.id)
        plan = alta.planear_general(
            self.s, "Chaleco Mujer KY18005", tallas=[t for t, _p in m.tallas], precios_por_talla=m.precios,
            marca=m.marca, color="Negro", tipo_prenda=m.tipo_prenda, tipo_pieza=m.tipo_pieza, categoria=m.categoria,
            genero=m.genero, modelo_id=m.producto_id, modelo_nombre=m.nombre)
        self.assertTrue(plan.puede_aplicar, plan.todos_los_errores)
        self.assertEqual(alta.origen_bitacora(plan), f"{alta.ORIGEN_GENERAL} · modelo: Chaleco Mujer KY17002")

    def test_opciones_traen_tipos_y_categorias(self) -> None:
        from pos_uniformes.services import nueva_prenda_service as nps

        ops = nps.opciones(self.s)
        self.assertIn("Temporada", ops.tipos_prenda)
        self.assertIn("Temporada", ops.categorias)
        self.assertEqual(list(ops.tipos_prenda), sorted(ops.tipos_prenda, key=valores.normalizar))

    def test_el_plan_no_escribe(self) -> None:
        antes = (self.contar(Producto), self.contar(Variante))
        self.plan()
        self.assertEqual((self.contar(Producto), self.contar(Variante)), antes)


    # ── Revisión 2026-11-15: lo que ya dice el nombre ─────────────────────

    def test_sugerir_pieza_y_genero_del_nombre(self) -> None:
        piezas, generos = ("Chaleco", "Pants", "Pants Suelto", "Suéter"), ("Mujer", "Unisex", "Niña")
        self.assertEqual(alta.sugerir_de_nombre("Chaleco Mujer KY18005", piezas, generos), ("Chaleco", "Mujer"))
        self.assertEqual(alta.sugerir_de_nombre("pants suelto niña", piezas, generos), ("Pants Suelto", "Niña"))
        self.assertEqual(alta.sugerir_de_nombre("Sueter Gris", piezas, generos), ("Suéter", None))
        self.assertEqual(alta.sugerir_de_nombre("Calceta Blanca", piezas, generos), (None, None))
        self.assertEqual(alta.sugerir_de_nombre("", piezas, generos), (None, None))
        # Una palabra suelta no es la pieza de dos («Suelto» no es «Pants Suelto»).
        self.assertEqual(alta.sugerir_de_nombre("Short Suelto", piezas, generos), (None, None))

    def test_tipo_de_prenda_sale_de_la_pieza_y_prefiere_las_generales(self) -> None:
        self.assertEqual(alta.tipo_prenda_para(self.s, "Chaleco"), "Temporada")
        self.assertIsNone(alta.tipo_prenda_para(self.s, None))
        self.assertIsNone(alta.tipo_prenda_para(self.s, "Pieza que no existe"))


if __name__ == "__main__":
    unittest.main()
