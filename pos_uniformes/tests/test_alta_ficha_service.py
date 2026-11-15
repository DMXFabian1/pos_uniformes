"""Tallas y colores que faltan, desde la ficha de la prenda (tanda 4, 2026-11-15).

Sobre la caja en miniatura: el Pants Suelto de Miguel Hidalgo no tiene EXG y
el de Benito Juárez sí ($305); el Suéter de Ignacio Allende lleva su color en
el nombre («Suéter Botones M Rojo»), el Pants Suelto no.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, func, select

from pos_uniformes.database.models import (
    CambioCatalogo,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    UniformePieza,
    Variante,
)
from pos_uniformes.services import alta_ficha_service as af
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services.catalog_service import CatalogService
from tests._ayuda_mini_caja import ESCALERAS, MiniCaja

D = Decimal


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.caja = MiniCaja(create_engine("sqlite://"))
        self.s = self.caja.s
        self.admin = self.caja.admin
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)

    def prod(self, escuela: str, pieza: str) -> Producto:
        return self.caja.productos[(escuela, pieza)]

    def contar(self, modelo) -> int:
        return int(self.s.scalar(select(func.count()).select_from(modelo)))

    def tallas_de(self, producto_id: int, color: str | None = None) -> dict[str, Decimal]:
        filtro = [Variante.producto_id == producto_id]
        if color:
            filtro.append(Variante.color == color)
        return {v.talla: v.precio_venta for v in self.s.scalars(select(Variante).where(*filtro)).all()}


class PurasTests(unittest.TestCase):
    def test_piso_es_la_talla_mas_cara_de_las_mas_chicas(self) -> None:
        propias = {"14": D(255), "16": D(255), "CH": D(285), "GD": D(295)}
        self.assertEqual(af.piso_de("EXG", propias), ("GD", D(295)))
        self.assertEqual(af.piso_de("18", propias), ("16", D(255)))
        self.assertIsNone(af.piso_de("4", propias))

    def test_precio_nunca_baja_de_la_talla_anterior(self) -> None:
        propias = {"GD": D(295)}
        self.assertEqual(af.precio_para("EXG", D(305), propias), (D(305), "como las demás"))
        self.assertEqual(af.precio_para("EXG", D(289), propias), (D(295), af.ORIGEN_COMO_TALLA_ANTERIOR))
        self.assertEqual(af.precio_para("EXG", None, propias), (D(295), af.ORIGEN_COMO_TALLA_ANTERIOR))
        self.assertEqual(af.precio_para("4", None, propias), (None, "falta precio"))

    def test_infantil_juvenil_adulto_en_su_orden(self) -> None:
        self.assertEqual(sorted(["Adulto", "Infantil", "Juvenil"], key=af.clave), ["Infantil", "Juvenil", "Adulto"])

    def test_color_en_nombre(self) -> None:
        self.assertTrue(af.color_en_nombre("Suéter Botones M Rojo", "Rojo"))
        self.assertTrue(af.color_en_nombre("Camisa Manga Larga Blanca", "Blanco"))
        self.assertFalse(af.color_en_nombre("Pants Suelto", "Gris"))
        self.assertFalse(af.color_en_nombre("Pants Suelto", "Sin color"))

    def test_chip_y_cobertura(self) -> None:
        t = af.TallaQueFalta("EXG", D(305), "como las demás", 1, 4)
        self.assertEqual(t.texto_chip, "EXG ＋ $305")
        self.assertEqual(t.texto_cobertura("Pants Suelto"), "la tienen 1 de las 4 prendas de Pants Suelto")
        self.assertEqual(af.TallaQueFalta("18", None, "falta precio").texto_chip, "18 ＋")


class FichaTests(_Base):
    def test_la_ficha_ensena_en_gris_la_exg_de_sus_hermanas(self) -> None:
        ficha = af.leer_ficha(self.s, self.prod("Miguel Hidalgo", "Pants Suelto").id)
        self.assertEqual([t.talla for t in ficha.tallas], list(ESCALERAS["Pants Suelto"]))
        self.assertEqual([(t.talla, t.precio) for t in ficha.faltan], [("EXG", D(305))])
        exg = ficha.faltan[0]
        self.assertEqual((exg.tienen, exg.total), (1, 3))  # Justo Sierra, Ignacio Allende, Benito Juárez
        self.assertEqual(ficha.colores, ("Sin color",))
        self.assertIn("En gris", ficha.texto_hermanas)
        self.assertNotIn("EXG", ficha.otras_tallas)
        self.assertNotIn("GD", ficha.otras_tallas)
        self.assertIn("18", ficha.otras_tallas)

    def test_sin_hermanas_no_hay_gris_pero_si_otra_talla(self) -> None:
        ficha = af.leer_ficha(self.s, self.prod("Técnica 18", "Pants Suelto").id)
        self.assertEqual(ficha.faltan, ())
        self.assertEqual(ficha.texto_hermanas, "")
        self.assertIn("EXG", ficha.otras_tallas)

    def test_no_existe(self) -> None:
        self.assertIsNone(af.leer_ficha(self.s, 99999))

    def test_leer_no_escribe(self) -> None:
        antes = (self.contar(Variante), self.contar(CambioCatalogo))
        af.leer_ficha(self.s, self.prod("Miguel Hidalgo", "Pants Suelto").id)
        self.assertEqual((self.contar(Variante), self.contar(CambioCatalogo)), antes)


class TallaNuevaTests(_Base):
    def test_crea_exactamente_esa_talla_con_su_precio(self) -> None:
        p = self.prod("Miguel Hidalgo", "Pants Suelto")
        plan = af.planear_tallas_nuevas(self.s, p.id, ["EXG"])
        self.assertTrue(plan.puede_aplicar, plan.todos_los_errores)
        self.assertEqual(plan.resumen, "Se crea la talla EXG de Pants Suelto Miguel Hidalgo, a $305.")
        n = self.contar(Variante)
        bitacora = self.contar(CambioCatalogo)
        resultado = af.aplicar_tallas_nuevas(self.s, plan, self.admin, commit=True)
        self.assertEqual(self.contar(Variante), n + 1)
        self.assertEqual(self.tallas_de(p.id)["EXG"], D(305))
        creada = resultado.productos[0].tallas[0]
        self.assertEqual((creada.talla, creada.color, creada.precio), ("EXG", "Sin color", D(305)))
        self.assertEqual(creada.sku, plan.skus[0])
        nota = self.s.scalar(select(CambioCatalogo.observacion).order_by(CambioCatalogo.id.desc()))
        self.assertEqual(nota, af.ORIGEN_TALLA)
        self.assertEqual(self.contar(CambioCatalogo), bitacora + 1)

    def test_ya_la_tiene(self) -> None:
        p = self.prod("Miguel Hidalgo", "Pants Suelto")
        plan = af.planear_tallas_nuevas(self.s, p.id, ["GD"])
        self.assertFalse(plan.puede_aplicar)
        self.assertEqual(plan.tallas[0].error, "Ya la tiene.")
        with self.assertRaises(alta.AltaNoValida):
            af.aplicar_tallas_nuevas(self.s, plan, self.admin)

    def test_precio_mas_bajo_que_la_talla_anterior_avisa_sin_frenar(self) -> None:
        p = self.prod("Miguel Hidalgo", "Pants Suelto")
        plan = af.planear_tallas_nuevas(self.s, p.id, {"EXG": 289})
        self.assertTrue(plan.puede_aplicar)
        self.assertEqual(plan.tallas[0].aviso, "Queda más barata que la talla GD ($295).")
        self.assertEqual(plan.tallas[0].sugerencia_5_9, None)  # 289 ya termina en 9

    def test_cero_y_vacio_frenan(self) -> None:
        p = self.prod("Técnica 18", "Pants Suelto")
        plan = af.planear_tallas_nuevas(self.s, p.id, {"10": None})
        self.assertEqual(plan.tallas[0].error, "Falta el precio.")
        plan = af.planear_tallas_nuevas(self.s, p.id, {"10": 0})
        self.assertEqual(plan.tallas[0].error, "El precio no puede quedar en $0.")

    def test_otra_talla_de_la_lista_toma_el_precio_de_la_anterior(self) -> None:
        p = self.prod("Técnica 18", "Pants Suelto")
        plan = af.planear_tallas_nuevas(self.s, p.id, ["EXG"])
        self.assertEqual((plan.tallas[0].precio, plan.tallas[0].origen_precio),
                         (D(305), af.ORIGEN_COMO_TALLA_ANTERIOR))

    def test_solo_admin(self) -> None:
        p = self.prod("Miguel Hidalgo", "Pants Suelto")
        plan = af.planear_tallas_nuevas(self.s, p.id, ["EXG"])
        n = self.contar(Variante)
        with self.assertRaises(PermissionError):
            af.aplicar_tallas_nuevas(self.s, plan, self.caja.cajera)
        self.assertEqual(self.contar(Variante), n)

    def test_llegan_entra_como_entrada_normal(self) -> None:
        p = self.prod("Miguel Hidalgo", "Pants Suelto")
        plan = af.planear_tallas_nuevas(self.s, p.id, ["EXG"], llegan={"EXG": 3})
        resultado = af.aplicar_tallas_nuevas(self.s, plan, self.admin, commit=True)
        v = self.s.get(Variante, resultado.productos[0].tallas[0].variante_id)
        self.assertEqual(v.stock_actual, 3)
        mov = self.s.scalar(select(MovimientoInventario).where(MovimientoInventario.variante_id == v.id))
        self.assertEqual((mov.tipo_movimiento, mov.referencia), (TipoMovimientoInventario.AJUSTE_ENTRADA, "ALTA-ENTRADA"))

    def test_la_receta_que_usa_la_pieza_avisa_si_no_arma_la_talla(self) -> None:
        # La Chamarra de Miguel Hidalgo usa su Pants Suelto; agregar EXG al Pants
        # Suelto no le crea EXG a la Chamarra (no la tiene): no hay nada que avisar.
        p = self.prod("Miguel Hidalgo", "Pants Suelto")
        plan = af.planear_tallas_nuevas(self.s, p.id, ["EXG"])
        resultado = af.aplicar_tallas_nuevas(self.s, plan, self.admin, commit=True)
        self.assertEqual(resultado.productos[0].avisos, ())
        # Al revés: EXG a la Chamarra (conjunto) sin que sus piezas la tengan.
        chamarra = self.prod("Justo Sierra", "Chamarra")
        plan = af.planear_tallas_nuevas(self.s, chamarra.id, {"EXG": 345})
        resultado = af.aplicar_tallas_nuevas(self.s, plan, self.admin, commit=True)
        self.assertTrue(any("no arma la talla EXG" in a for a in resultado.productos[0].avisos),
                        resultado.productos[0].avisos)


class OtroColorTests(_Base):
    def test_el_nombre_lleva_el_color_es_otra_prenda(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        plan = af.planear_otro_color(self.s, sueter.id, "Azul")
        self.assertEqual(plan.modo, af.MODO_PRENDA)
        self.assertTrue(plan.puede_aplicar, plan.todos_los_errores)
        self.assertEqual(plan.nombre, "Suéter Botones M Azul Ignacio Allende")
        self.assertEqual(
            plan.resumen,
            "Se crea «Suéter Botones M Azul Ignacio Allende» con 7 tallas, de $299 a $315. "
            "«Suéter Botones M Rojo Ignacio Allende» se queda igual.",
        )
        antes = self.tallas_de(sueter.id)
        resultado = af.aplicar_otro_color(self.s, plan, self.admin, commit=True)
        nuevo = resultado.productos[0]
        self.assertEqual(self.tallas_de(nuevo.producto_id, "Azul"), antes)  # todas, con sus precios
        self.assertEqual(self.tallas_de(sueter.id), antes)  # la original no cambia
        self.assertEqual(nuevo.uniforme, "Diario")  # en el mismo grupo del uniforme
        nota = self.s.scalar(
            select(CambioCatalogo.observacion).where(CambioCatalogo.entidad_id == nuevo.producto_id)
            .order_by(CambioCatalogo.id)
        )
        self.assertEqual(nota, f"{af.ORIGEN_COLOR} · modelo: Suéter Botones M Rojo Ignacio Allende")

    def test_el_nombre_no_lleva_el_color_son_tallas_de_la_misma_prenda(self) -> None:
        pants = self.prod("Ignacio Allende (Jaral)", "Pants 2pz")
        plan = af.planear_otro_color(self.s, pants.id, "Azul Marino")
        self.assertEqual(plan.modo, af.MODO_TALLAS)
        self.assertEqual(plan.color_antes, "Gris")
        self.assertTrue(plan.puede_aplicar, plan.todos_los_errores)
        productos = self.contar(Producto)
        af.aplicar_otro_color(self.s, plan, self.admin, commit=True)
        self.assertEqual(self.contar(Producto), productos)
        self.assertEqual(self.tallas_de(pants.id, "Azul Marino"), self.tallas_de(pants.id, "Gris"))

    def test_quisiste_decir_y_mismo_color(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        plan = af.planear_otro_color(self.s, sueter.id, "Roja")  # «Roja» → «Rojo»: el mismo
        self.assertFalse(plan.puede_aplicar)
        self.assertIn("La prenda ya está en Rojo.", plan.todos_los_errores)
        plan = af.planear_otro_color(self.s, sueter.id, "Azulito")
        self.assertFalse(plan.puede_aplicar)
        plan = af.planear_otro_color(self.s, sueter.id, "Azulito", confirmados=["Azulito"])
        self.assertTrue(plan.puede_aplicar, plan.todos_los_errores)

    def test_sin_color_avisa_que_mejor_se_corrija(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        plan = af.planear_otro_color(self.s, pants.id, "Gris")
        self.assertEqual(plan.modo, af.MODO_TALLAS)
        self.assertTrue(any("Sin color" in a for a in plan.todos_los_avisos))

    def test_cancelar_no_crea_nada(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        antes = (self.contar(Producto), self.contar(Variante), self.contar(UniformePieza))
        af.planear_otro_color(self.s, sueter.id, "Azul")
        self.s.rollback()
        self.assertEqual((self.contar(Producto), self.contar(Variante), self.contar(UniformePieza)), antes)


if __name__ == "__main__":
    unittest.main()
