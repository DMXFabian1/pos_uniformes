"""«Editar datos» de la prenda: el reemplazo del editor viejo (tanda 5, 2026-11-15)."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select

from pos_uniformes.database.models import (
    AtributoProducto,
    CambioCatalogo,
    Marca,
    Producto,
    Uniforme,
    UniformePieza,
    Variante,
)
from pos_uniformes.services import datos_prenda_service as dp
from pos_uniformes.services.catalog_service import CatalogService
from tests._ayuda_mini_caja import MiniCaja

D = Decimal


class DatosPrendaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.caja = MiniCaja(create_engine("sqlite://"))
        self.s = self.caja.s
        self.admin = self.caja.admin
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)
        self.s.add_all([Marca(nombre="Claudia"), AtributoProducto(nombre="Básico")])
        self.s.commit()
        self.sueter = self.caja.productos[("Ignacio Allende", "Suéter")]
        self.chamarra = self.caja.productos[("Ignacio Allende", "Chamarra")]
        self.suelto_bj = self.caja.productos[("Benito Juárez", "Pants Suelto")]

    def variantes(self, producto_id: int) -> list[tuple]:
        self.s.expire_all()
        return [(v.sku, v.talla, v.color, v.precio_venta, v.stock_actual)
                for v in self.s.scalars(select(Variante).where(Variante.producto_id == producto_id)
                                        .order_by(Variante.id)).all()]

    def test_opciones_son_listas_cerradas_sin_repetidos(self) -> None:
        self.s.add(AtributoProducto(nombre="Basico"))
        self.s.commit()
        ops = dp.opciones_datos(self.s)
        self.assertIn("Claudia", ops.listas["marca"])
        self.assertIn("Básico", ops.listas["atributo"])
        self.assertNotIn("Basico", ops.listas["atributo"])
        self.assertEqual(ops.generos, ("Unisex", "Mujer", "Hombre"))
        self.assertIn("Con Escudo", ops.escudos)

    def test_sin_cambios_no_deja_guardar(self) -> None:
        plan = dp.planear_datos(self.s, self.sueter.id)
        self.assertFalse(plan.puede_aplicar)
        self.assertEqual(plan.resumen, "Sin cambios todavía.")
        with self.assertRaises(dp.DatosNoValidos):
            dp.aplicar_datos(self.s, plan, self.admin)

    def test_cambia_marca_genero_y_mas_sin_tocar_tallas(self) -> None:
        antes = self.variantes(self.sueter.id)
        plan = dp.planear_datos(self.s, self.sueter.id, cambios={
            "marca": "claudia", "genero": "mujer", "atributo": "basico", "escudo": "Sin escudo",
            "descripcion": "Suéter de botones", "ubicacion": "Anaquel 3",
        })
        self.assertTrue(plan.puede_aplicar, plan.errores)
        self.assertEqual(plan.datos["marca"], "Claudia")
        self.assertEqual(plan.datos["atributo"], "Básico")
        self.assertEqual(plan.datos["genero"], "Mujer")
        self.assertEqual(plan.nombre, plan.nombre_antes)  # el nombre no cambia
        self.assertIn("Corregir prenda", " ".join(plan.avisos))  # cambió el atributo
        dp.aplicar_datos(self.s, plan, self.admin, commit=True)
        self.s.expire_all()
        p = self.s.get(Producto, self.sueter.id)
        self.assertEqual((p.marca.nombre, p.genero, p.atributo.nombre, p.escudo, p.descripcion, p.ubicacion),
                         ("Claudia", "Mujer", "Básico", "Sin escudo", "Suéter de botones", "Anaquel 3"))
        self.assertEqual(p.nombre, "Suéter Botones M Rojo Ignacio Allende")
        self.assertEqual(self.variantes(self.sueter.id), antes)
        campos = set(self.s.scalars(select(CambioCatalogo.campo)
                                    .where(CambioCatalogo.observacion == dp.ORIGEN_DATOS)).all())
        self.assertEqual(campos, {"marca", "genero", "atributo", "escudo", "descripcion", "ubicacion"})

    def test_valor_que_no_existe_no_se_crea(self) -> None:
        plan = dp.planear_datos(self.s, self.sueter.id, cambios={"marca": "Marca Inventada", "genero": "Niño"})
        self.assertFalse(plan.puede_aplicar)
        self.assertEqual(len(plan.errores), 2)
        self.assertIn("no está en la lista de marca", plan.errores[0])
        self.assertIsNone(self.s.scalar(select(Marca).where(Marca.nombre == "Marca Inventada")))

    def test_marca_y_categoria_son_obligatorias(self) -> None:
        plan = dp.planear_datos(self.s, self.sueter.id, cambios={"marca": "", "atributo": ""})
        self.assertIn("Falta marca.", plan.errores)
        self.assertNotIn("Falta atributo.", plan.errores)

    def test_costo_para_todas_las_tallas(self) -> None:
        plan = dp.planear_datos(self.s, self.sueter.id, costo="180")
        self.assertTrue(plan.puede_aplicar, plan.errores)
        self.assertIn("Costo: sin costo → $180 en 7 tallas", plan.resumen)
        dp.aplicar_datos(self.s, plan, self.admin, commit=True)
        self.s.expire_all()
        costos = {v.costo_referencia for v in self.s.get(Producto, self.sueter.id).variantes}
        self.assertEqual(costos, {D("180.00")})
        self.assertEqual(dp.planear_datos(self.s, self.sueter.id, costo="-5").errores,
                         ["El costo no puede ser negativo."])
        self.assertFalse(dp.planear_datos(self.s, self.sueter.id, costo="180").hay_cambios)

    def test_cambiar_escuela_arma_el_nombre_y_mueve_el_uniforme(self) -> None:
        antes = self.variantes(self.sueter.id)
        plan = dp.planear_datos(self.s, self.sueter.id, cambios={"escuela": "justo sierra"})
        self.assertTrue(plan.puede_aplicar, plan.errores)
        self.assertEqual(plan.nombre, "Suéter Botones M Rojo Justo Sierra")
        self.assertEqual(len(plan.piezas_a_mover), 1)
        dp.aplicar_datos(self.s, plan, self.admin, commit=True)
        self.s.expire_all()
        p = self.s.get(Producto, self.sueter.id)
        self.assertEqual((p.nombre, p.escuela.nombre), ("Suéter Botones M Rojo Justo Sierra", "Justo Sierra"))
        self.assertEqual(self.variantes(self.sueter.id), antes)
        activas = self.s.execute(
            select(Uniforme.escuela_id, UniformePieza.grupo)
            .join(Uniforme, UniformePieza.uniforme_id == Uniforme.id)
            .where(UniformePieza.producto_id == p.id, UniformePieza.activo.is_(True))
        ).all()
        self.assertEqual(activas, [(self.caja.escuelas["Justo Sierra"].id, "Diario")])

    def test_escuela_de_una_prenda_con_receta_se_detiene(self) -> None:
        plan = dp.planear_datos(self.s, self.chamarra.id, cambios={"escuela": "Justo Sierra"})
        self.assertFalse(plan.puede_aplicar)
        self.assertIn("receta", plan.errores[0])
        plan = dp.planear_datos(self.s, self.sueter.id, cambios={"escuela": ""})
        self.assertIn("general", plan.errores[0])

    def test_nombre_que_ya_existe_frena(self) -> None:
        # El Pants Suelto de Benito Juárez a Miguel Hidalgo choca con el que ya tiene.
        plan = dp.planear_datos(self.s, self.suelto_bj.id, cambios={"escuela": "Miguel Hidalgo"})
        self.assertFalse(plan.puede_aplicar)
        self.assertTrue(any(e.startswith("Ya existe otra prenda") for e in plan.errores), plan.errores)

    def test_solo_admin_y_todo_o_nada(self) -> None:
        plan = dp.planear_datos(self.s, self.sueter.id, cambios={"marca": "Claudia"})
        with self.assertRaises(PermissionError):
            dp.aplicar_datos(self.s, plan, self.caja.cajera)
        self.s.rollback()
        plan = dp.planear_datos(self.s, self.sueter.id, cambios={"escuela": "Justo Sierra"}, costo="150")
        with patch.object(dp.us, "agregar_pieza", side_effect=RuntimeError("falla")):
            with self.assertRaises(RuntimeError):
                dp.aplicar_datos(self.s, plan, self.admin)
        self.s.rollback()
        self.s.expire_all()
        p = self.s.get(Producto, self.sueter.id)
        self.assertEqual((p.marca.nombre, p.escuela.nombre), ("Sin marca", "Ignacio Allende"))
        self.assertEqual({v.costo_referencia for v in p.variantes}, {None})

    def test_si_la_prenda_cambio_mientras_se_editaba_se_detiene(self) -> None:
        plan = dp.planear_datos(self.s, self.sueter.id, cambios={"genero": "Mujer"})
        self.s.get(Producto, self.sueter.id).escudo = "Bordado"
        self.s.commit()
        with self.assertRaises(dp.DatosNoValidos):
            dp.aplicar_datos(self.s, plan, self.admin)


if __name__ == "__main__":
    unittest.main()
