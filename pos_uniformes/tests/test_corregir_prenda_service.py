"""«✏️ Corregir prenda»: nombre y color de toda la prenda a la vez (tanda 4, 2026-11-15)."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select

from pos_uniformes.database.models import CambioCatalogo, TipoTrabajo, Trabajo, Variante
from pos_uniformes.services import corregir_prenda_service as cp
from pos_uniformes.services.catalog_service import CatalogService
from tests._ayuda_mini_caja import MiniCaja

D = Decimal


class CorregirTests(unittest.TestCase):
    def setUp(self) -> None:
        self.caja = MiniCaja(create_engine("sqlite://"))
        self.s = self.caja.s
        self.admin = self.caja.admin
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)
        self.sueter = self.caja.productos[("Ignacio Allende", "Suéter")]

    def variantes(self, producto_id: int) -> list[tuple]:
        self.s.expire_all()
        return [(v.id, v.sku, v.talla, v.color, v.precio_venta)
                for v in self.s.scalars(select(Variante).where(Variante.producto_id == producto_id)
                                        .order_by(Variante.id)).all()]

    def test_el_plan_quita_la_escuela_y_arma_el_nombre(self) -> None:
        plan = cp.planear_correccion(self.s, self.sueter.id)
        self.assertEqual(plan.nombre_sin_escuela_antes, "Suéter Botones M Rojo")
        self.assertFalse(plan.hay_cambios)
        self.assertEqual(plan.resumen, "Sin cambios todavía.")
        plan = cp.planear_correccion(self.s, self.sueter.id, nombre_sin_escuela="sueter botones m rojo ignacio allende")
        self.assertEqual(plan.nombre, CatalogService.armar_nombre("sueter botones m rojo", "Ignacio Allende"))
        self.assertNotIn("Ignacio Allende Ignacio Allende", plan.nombre)

    def test_cambia_nombre_y_color_sin_perder_sku_ni_precio(self) -> None:
        antes = self.variantes(self.sueter.id)
        base = cp.nombre_con_color_nuevo("Suéter Botones M Rojo", "Rojo", "Azul")
        self.assertEqual(base, "Suéter Botones M Azul")
        plan = cp.planear_correccion(self.s, self.sueter.id, nombre_sin_escuela=base, color="Azul")
        self.assertTrue(plan.puede_aplicar, plan.errores)
        self.assertEqual(plan.texto_etiquetas, cp.AVISO_ETIQUETAS)
        self.assertIn("Pasa a llamarse «Suéter Botones M Azul Ignacio Allende» (con sus 7 tallas).", plan.resumen)
        self.assertIn("pasan de Rojo a Azul", plan.resumen)
        resultado = cp.aplicar_correccion(self.s, plan, self.admin, commit=True)
        self.assertEqual(resultado.nombre, "Suéter Botones M Azul Ignacio Allende")
        self.assertEqual(resultado.tallas_cambiadas, 7)
        despues = self.variantes(self.sueter.id)
        self.assertEqual([(i, s, t, p) for i, s, t, _c, p in despues], [(i, s, t, p) for i, s, t, _c, p in antes])
        self.assertEqual({c for *_x, c, _p in despues}, {"Azul"})
        notas = set(self.s.scalars(select(CambioCatalogo.observacion)
                                   .where(CambioCatalogo.observacion == cp.ORIGEN_CORREGIR)).all())
        self.assertEqual(notas, {cp.ORIGEN_CORREGIR})

    def test_un_precio_que_baja_no_se_aplica_sin_confirmar(self) -> None:
        vid = self.variantes(self.sueter.id)[0][0]
        plan = cp.planear_correccion(self.s, self.sueter.id, precios_nuevos={vid: 289})
        self.assertEqual(len(plan.bajas), 1)
        self.assertEqual(plan.bajas[0].antes, D(299))
        with self.assertRaises(cp.HayPreciosQueBajan):
            cp.aplicar_correccion(self.s, plan, self.admin)
        self.assertEqual(self.variantes(self.sueter.id)[0][4], D(299))
        cp.aplicar_correccion(self.s, plan, self.admin, permitir_bajar=True, commit=True)
        self.assertEqual(self.variantes(self.sueter.id)[0][4], D(289))

    def test_subir_no_pide_confirmar_y_cero_frena(self) -> None:
        vid = self.variantes(self.sueter.id)[0][0]
        plan = cp.planear_correccion(self.s, self.sueter.id, precios_nuevos={vid: 305})
        self.assertEqual(plan.bajas, [])
        self.assertEqual(plan.texto_etiquetas, "")  # el precio no va en la etiqueta de uniforme
        self.assertIn("Cambia 1 precio.", plan.resumen)
        plan = cp.planear_correccion(self.s, self.sueter.id, precios_nuevos={vid: 0})
        self.assertIn("Talla 4: el precio no puede quedar en $0.", plan.errores)

    def test_nombre_que_ya_existe_frena(self) -> None:
        chaleco = self.caja.productos[("Ignacio Allende", "Chaleco")]
        plan = cp.planear_correccion(self.s, chaleco.id, nombre_sin_escuela="Suéter Botones M Rojo")
        self.assertFalse(plan.puede_aplicar)
        self.assertTrue(plan.errores[0].startswith("Ya existe otra prenda"))

    def test_color_parecido_pregunta(self) -> None:
        plan = cp.planear_correccion(self.s, self.sueter.id, color="Azulito")
        self.assertFalse(plan.puede_aplicar)
        plan = cp.planear_correccion(self.s, self.sueter.id, color="Azulito", confirmados=["Azulito"])
        self.assertTrue(plan.puede_aplicar, plan.errores)

    def test_solo_admin(self) -> None:
        plan = cp.planear_correccion(self.s, self.sueter.id, nombre_sin_escuela="Suéter Botones Mujer Rojo")
        with self.assertRaises(PermissionError):
            cp.aplicar_correccion(self.s, plan, self.caja.cajera)
        self.s.rollback()
        self.s.expire_all()
        self.assertEqual(self.s.get(type(self.sueter), self.sueter.id).nombre, "Suéter Botones M Rojo Ignacio Allende")

    def test_cuenta_las_etiquetas_mandadas_al_satelite(self) -> None:
        sku = self.variantes(self.sueter.id)[0][1]
        self.s.add(Trabajo(tipo=TipoTrabajo.ETIQUETA, contenido={"sku": sku, "copies": 1}, origen="principal",
                           creado_por="SYSTEM"))
        self.s.add(Trabajo(tipo=TipoTrabajo.ETIQUETA, contenido={"sku": "OTRO", "copies": 1}, origen="principal",
                           creado_por="SYSTEM"))
        self.s.commit()
        plan = cp.planear_correccion(self.s, self.sueter.id, nombre_sin_escuela="Suéter Botones Mujer Rojo")
        self.assertEqual(plan.etiquetas_enviadas, 1)
        self.assertTrue(plan.texto_etiquetas.startswith("Se han mandado a imprimir 1 etiqueta de esta prenda."))


if __name__ == "__main__":
    unittest.main()
