"""El motor del alta: plan, ensayo y aplicar todo junto o nada (tanda 2, 2026-11-13).

Se prueba con una caja en miniatura donde «Ignacio Allende (Jaral)» está como
quedó el 14-sep (sin Pants Suelto, suéteres ni chaleco) y se completa
copiando de sus hermanas, como el 10-nov.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, func, select

from pos_uniformes.database.models import (
    CambioCatalogo,
    ConjuntoComponente,
    Escuela,
    MovimientoInventario,
    Producto,
    SkuSequence,
    TipoMovimientoInventario,
    UniformePieza,
    Variante,
)
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import conjunto_service
from pos_uniformes.services.catalog_service import CatalogService
from tests._ayuda_mini_caja import ESCALERAS, MiniCaja

D = Decimal
JARAL = "Ignacio Allende (Jaral)"


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.caja = MiniCaja(create_engine("sqlite://"))
        self.s = self.caja.s
        self.admin = self.caja.admin
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)

    def contar(self, modelo) -> int:
        return int(self.s.scalar(select(func.count()).select_from(modelo)))

    def foto(self) -> dict:
        return {m.__name__: self.contar(m) for m in (Producto, Variante, UniformePieza, ConjuntoComponente,
                                                       CambioCatalogo, MovimientoInventario)}

    def ultimo_sku(self) -> int:
        return int(self.s.scalar(select(SkuSequence.ultimo_numero)))

    def producto(self, nombre: str) -> Producto | None:
        return self.s.scalar(select(Producto).where(Producto.nombre == nombre))

    def pants_suelto_jaral(self, **kw) -> alta.PlanPrenda:
        return alta.planear_desde_modelo(self.s, JARAL, "Pants Suelto", **kw)


class PlanTests(_Base):
    def test_pants_suelto_para_jaral_copiado_de_sus_hermanas(self) -> None:
        plan = self.pants_suelto_jaral(color="Gris")
        self.assertEqual(plan.errores, [])
        self.assertEqual(plan.nombre, "Pants Suelto Ignacio Allende (Jaral)")
        self.assertEqual(plan.nivel, "Primaria")
        self.assertEqual(plan.color, "Gris")
        self.assertEqual({t.talla: t.precio for t in plan.tallas},
                         {t: D(p) for t, p in ESCALERAS["Pants Suelto"].items()})
        self.assertEqual({t.origen_precio for t in plan.tallas}, {"como las demás"})
        self.assertIn("igual en 3 escuelas de primaria", plan.modelo_texto)
        self.assertEqual(plan.grupo_previsto, "Deportivo")
        self.assertEqual(plan.receta_texto, "Receta Chamarra: se completa.")
        self.assertEqual(plan.texto_rango, "10 tallas · $245 a $295")
        self.assertEqual(
            plan.resumen,
            "Se crean 10 tallas de Pants Suelto Ignacio Allende (Jaral), de $245 a $295. "
            "Quedan en su uniforme Deportivo.",
        )
        n = self.ultimo_sku()
        self.assertEqual(plan.skus_previstos, [f"SKU{i:06d}" for i in range(n + 1, n + 11)])

    def test_el_plan_no_escribe_nada(self) -> None:
        antes = self.foto()
        self.pants_suelto_jaral()
        self.assertEqual(self.foto(), antes)
        self.assertFalse(self.s.new)

    def test_quitar_tallas_y_precio_a_mano(self) -> None:
        plan = self.pants_suelto_jaral(quitar_tallas=["4"], precios_a_mano={"GD": 290})
        self.assertNotIn("4", [t.talla for t in plan.tallas])
        gd = next(t for t in plan.tallas if t.talla == "GD")
        self.assertEqual((gd.precio, gd.origen_precio), (D(290), "a mano"))
        self.assertEqual(gd.aviso, "Queda más bajo que en las demás escuelas ($295).")
        self.assertEqual(gd.sugerencia_5_9, D(295))
        self.assertTrue(plan.puede_aplicar)  # avisa, no frena
        # Un solo aviso visible: en su talla, no repetido en los de la prenda.
        self.assertFalse(any("más bajo" in a for a in plan.avisos))
        self.assertEqual([a for a in plan.todos_los_avisos if "más bajo" in a],
                         ["Talla GD: queda más bajo que en las demás escuelas ($295)."])

    def test_editar_un_precio_y_volver_a_completar(self) -> None:
        plan = self.pants_suelto_jaral()
        gd = next(t for t in plan.tallas if t.talla == "GD")
        self.assertEqual((gd.origen_precio, gd.moda, gd.prendas_con_moda), ("como las demás", D(295), 4))
        gd.precio = D(290)
        alta.completar(self.s, plan)
        self.assertEqual(gd.origen_precio, "a mano")
        self.assertEqual(gd.aviso, "Queda más bajo que en las demás escuelas ($295).")
        gd.precio = gd.moda  # «volver al de las demás»
        alta.completar(self.s, plan)
        self.assertEqual((gd.origen_precio, gd.aviso), ("como las demás", ""))

    def test_sin_precio_un_solo_error_por_talla(self) -> None:
        plan = self.pants_suelto_jaral()
        plan.tallas[0].precio = None
        alta.completar(self.s, plan)
        self.assertEqual(plan.tallas[0].error, "Falta el precio.")
        self.assertEqual(plan.errores, [])
        self.assertEqual(plan.todos_los_errores, ["Talla 4: falta el precio."])
        self.assertFalse(plan.puede_aplicar)

    def test_el_aviso_sin_modelo_sobrevive_a_completar(self) -> None:
        plan = alta.planear_desde_modelo(self.s, JARAL, "Mochila", nombre="Mochila",
                                         confirmados=["Mochila"])
        self.assertTrue(plan.avisos and plan.avisos[0].startswith("No hay otra Mochila"), plan.avisos)
        alta.completar(self.s, plan)
        self.assertTrue(plan.avisos[0].startswith("No hay otra Mochila"))

    def test_precio_en_cero_frena(self) -> None:
        plan = self.pants_suelto_jaral(precios_a_mano={"4": 0})
        self.assertIn("Talla 4: el precio no puede quedar en $0.", plan.todos_los_errores)
        with self.assertRaises(alta.AltaNoValida):
            alta.aplicar(self.s, plan, self.admin)

    def test_el_color_cambia_tambien_en_el_nombre(self) -> None:
        plan = alta.planear_desde_modelo(self.s, JARAL, "Suéter", color="Azul")
        self.assertEqual(plan.nombre, "Suéter Botones M Azul Ignacio Allende (Jaral)")
        self.assertEqual(plan.color, "Azul")
        self.assertEqual(alta.cambiar_color_en_nombre("Camisa Manga Larga Blanca", "Blanco", "Azul"),
                         "Camisa Manga Larga Azul")
        self.assertEqual(alta.cambiar_color_en_nombre("Pants Suelto", "Sin color", "Gris"), "Pants Suelto")

    def test_una_sola_forma_para_tallas_y_colores(self) -> None:
        plan = alta.planear(self.s, {
            "producto": {"nombre": "Corbata", "categoria": "Oficial", "marca": "Sin marca"},
            "color": "Blanca",
            "variantes": [{"talla": "Uni", "precio": 70}],
        })
        self.assertEqual(plan.errores, [])
        self.assertEqual(plan.tallas[0].talla, "Unitalla")
        self.assertEqual(plan.color, "Blanco")
        # No hay otra corbata en esta base: el $70 se acepta y solo se sugiere $75.
        self.assertEqual(plan.tallas[0].precio, D(70))
        self.assertEqual(plan.tallas[0].sugerencia_5_9, D(75))
        self.assertTrue(any("«Uni» se guarda como «Unitalla»" in a for a in plan.avisos))

    def test_nada_se_crea_sin_confirmar(self) -> None:
        # Misma escuela escrita sin paréntesis: se usa la que existe.
        plan = alta.planear_desde_modelo(self.s, "ignacio allende jaral", "Pants Suelto", nivel="Primaria")
        self.assertEqual((plan.escuela, plan.errores), (JARAL, []))
        # Otra escritura: pregunta «¿Es la misma que…?» y no crea nada.
        plan = alta.planear_desde_modelo(self.s, "Ignacio Allende Jaral de Berrios", "Pants Suelto",
                                         nivel="Primaria")
        self.assertTrue(any("¿Es la misma que «Ignacio Allende" in e for e in plan.errores), plan.errores)
        plan = alta.planear(self.s, {
            "producto": {"nombre": "Short", "categoria": "Deportivo", "marca": "Sin marca", "tipo_pieza": "Shortt"},
            "variantes": [{"talla": "4", "precio": 150}],
        })
        self.assertTrue(any("Shortt" in e for e in plan.errores), plan.errores)

    def test_existencia_en_un_conjunto_frena(self) -> None:
        plan = alta.planear_desde_modelo(self.s, "Benito Juárez", "Pants 3pz", llegan={"4": 2})
        self.assertTrue(any("no tiene existencia propia" in e for e in plan.errores))

    def test_ya_existe(self) -> None:
        plan = alta.planear_desde_modelo(self.s, "Miguel Hidalgo", "Pants Suelto")
        self.assertIn("Ya existe «Pants Suelto Miguel Hidalgo».", plan.errores)


class EnsayoTests(_Base):
    def test_ensayo_dice_lo_que_se_crearia_y_no_deja_nada(self) -> None:
        plan = self.pants_suelto_jaral(color="Gris")
        antes, sku_antes = self.foto(), self.ultimo_sku()
        r = alta.ensayar(self.s, plan, self.admin)
        self.assertTrue(r.ok, r.error)
        self.assertTrue(r.ensayo)
        p = r.productos[0]
        self.assertEqual(p.nombre, "Pants Suelto Ignacio Allende (Jaral)")
        self.assertEqual(r.skus, plan.skus_previstos)
        self.assertEqual(p.uniforme, "Deportivo")
        self.assertEqual(len(p.recetas), 1)
        self.assertIn("Chamarra Deportiva Ignacio Allende (Jaral)", p.recetas[0])
        self.assertIn("(se completó)", p.recetas[0])
        self.assertEqual(p.bitacora, "Alta desde POS · modelo: " + plan.modelo_nombre)
        self.assertEqual(self.foto(), antes)
        self.assertEqual(self.ultimo_sku(), sku_antes)
        self.assertIn("SKU", r.texto())

    def test_ensayo_con_errores_no_lanza(self) -> None:
        plan = self.pants_suelto_jaral(precios_a_mano={"4": 0})
        r = alta.ensayar(self.s, plan, self.admin)
        self.assertFalse(r.ok)
        self.assertIn("$0", r.error)

    def test_jaral_completo_copiando_de_sus_hermanas(self) -> None:
        """El alta del 10-nov repetida sin guardar: pants suelto gris, suéter y chaleco azules."""
        planes = [
            alta.planear_desde_modelo(self.s, JARAL, "Pants Suelto", color="Gris"),
            alta.planear_desde_modelo(self.s, JARAL, "Suéter", color="Azul", saltar_skus=10),
            alta.planear_desde_modelo(self.s, JARAL, "Chaleco", color="Azul", saltar_skus=17),
        ]
        self.assertEqual([p.errores for p in planes], [[], [], []])
        antes = self.foto()
        r = alta.ensayar(self.s, planes, self.admin, alta.ORIGEN_CLAUDE)
        self.assertTrue(r.ok, r.error)
        self.assertEqual([p.nombre for p in r.productos], [
            "Pants Suelto Ignacio Allende (Jaral)",
            "Suéter Botones M Azul Ignacio Allende (Jaral)",
            "Chaleco Azul Ignacio Allende (Jaral)",
        ])
        self.assertEqual(r.skus, [s for p in planes for s in p.skus_previstos])
        self.assertEqual([p.uniforme for p in r.productos], ["Deportivo", "Diario", "Diario"])
        self.assertTrue(r.productos[1].bitacora.startswith("Claude (skill alta-productos) · modelo: Suéter"))
        self.assertEqual(self.foto(), antes)


class AplicarTests(_Base):
    def test_guarda_todo_junto(self) -> None:
        plan = self.pants_suelto_jaral(color="Gris")
        receta_3pz_antes = self._receta("Pants 3pz")
        r = alta.aplicar(self.s, plan, self.admin, commit=True)
        p = self.producto("Pants Suelto Ignacio Allende (Jaral)")
        self.assertIsNotNone(p)
        self.assertEqual(r.productos[0].producto_id, p.id)
        self.assertEqual(sorted(v.sku for v in p.variantes), plan.skus_previstos)
        self.assertEqual({v.color for v in p.variantes}, {"Gris"})
        pieza = self.s.scalar(select(UniformePieza).where(UniformePieza.producto_id == p.id))
        self.assertEqual(pieza.grupo, "Deportivo")
        # La Chamarra de Jaral ya tiene receta (sale del 2pz y deja este suelto).
        self.assertEqual(self._receta("Chamarra"), [
            (self.caja.productos[(JARAL, "Pants 2pz")].id, 1), (p.id, -1),
        ])
        # La receta del 3pz (ya armada) no se toca.
        self.assertEqual(self._receta("Pants 3pz"), receta_3pz_antes)
        # Bitácora con origen, en la prenda y en cada talla.
        obs = set(self.s.scalars(select(CambioCatalogo.observacion)).all())
        self.assertEqual(obs, {"Alta desde POS · modelo: " + plan.modelo_nombre})
        self.assertEqual(self.contar(CambioCatalogo), 11)

    def _receta(self, pieza: str) -> list[tuple[int, int]]:
        c = self.caja.productos[(JARAL, pieza)]
        return [(r.componente_id, r.cantidad) for r in conjunto_service.receta_de(self.s, c.id)]

    def test_si_falla_la_receta_no_queda_la_prenda(self) -> None:
        plan = self.pants_suelto_jaral()
        antes, sku_antes = self.foto(), self.ultimo_sku()
        with patch.object(conjunto_service, "definir_receta", side_effect=ValueError("receta rota")):
            with self.assertRaisesRegex(ValueError, "receta rota"):
                alta.aplicar(self.s, plan, self.admin)
        self.s.commit()
        self.assertIsNone(self.producto("Pants Suelto Ignacio Allende (Jaral)"))
        self.assertEqual(self.foto(), antes)
        self.assertEqual(self.ultimo_sku(), sku_antes)

    def test_existencia_inicial_como_entrada_normal_y_la_talla_se_puede_borrar(self) -> None:
        plan = self.pants_suelto_jaral(llegan={"4": 3, "6": 2})
        alta.aplicar(self.s, plan, self.admin, commit=True)
        p = self.producto("Pants Suelto Ignacio Allende (Jaral)")
        por_talla = {v.talla: v for v in p.variantes}
        self.assertEqual((por_talla["4"].stock_actual, por_talla["6"].stock_actual, por_talla["8"].stock_actual),
                         (3, 2, 0))
        movs = self.s.scalars(select(MovimientoInventario).where(
            MovimientoInventario.variante_id == por_talla["4"].id)).all()
        self.assertEqual([(m.tipo_movimiento, m.cantidad, m.referencia) for m in movs],
                         [(TipoMovimientoInventario.AJUSTE_ENTRADA, 3, "ALTA-ENTRADA")])
        self.assertIn("Llegaron al dar de alta", movs[0].observacion)
        # Se corrige como cualquier entrada y la talla se puede borrar.
        from pos_uniformes.services.inventario_service import InventarioService

        InventarioService.registrar_ajuste_manual(self.s, por_talla["4"], -3, self.admin, referencia="ADJ-1")
        CatalogService.eliminar_variante(self.s, self.admin, por_talla["4"])
        self.s.commit()
        self.assertIsNone(self.s.get(Variante, por_talla["4"].id))

    def test_conjunto_nuevo_propone_su_receta(self) -> None:
        plan = alta.planear_desde_modelo(self.s, "Benito Juárez", "Pants 3pz")
        self.assertEqual(plan.receta_texto, "Receta Pants 3pz: se propone con las piezas de la escuela.")
        r = alta.aplicar(self.s, plan, self.admin, commit=True)
        self.assertIn("(nueva)", r.productos[0].recetas[0])
        nuevo = self.producto("Pants 3pz Deportivo Benito Juárez")
        comp = {c.componente_id for c in conjunto_service.receta_de(self.s, nuevo.id)}
        self.assertEqual(comp, {self.caja.productos[("Benito Juárez", "Pants 2pz")].id,
                                self.caja.productos[("Benito Juárez", "Playera")].id})

    def test_conjunto_sin_piezas_avisa_y_no_frena(self) -> None:
        plan = alta.planear_desde_modelo(self.s, "Benito Juárez", "Chamarra")
        r = alta.aplicar(self.s, plan, self.admin)
        # Benito Juárez sí tiene Pants 2pz y Pants Suelto: se arma.
        self.assertEqual(len(r.productos[0].recetas), 1)
        self.s.rollback()
        # Una escuela sin piezas: la chamarra entra, la receta queda pendiente.
        plan = alta.planear_desde_modelo(self.s, "Técnica 18", "Chamarra", nivel="Secundaria")
        r = alta.aplicar(self.s, plan, self.admin)
        self.assertEqual(r.productos[0].recetas, ())
        self.assertTrue(any("falta Pants 2pz" in a for a in r.productos[0].avisos))

    def test_conjunto_con_existencia_propia_no_pierde_su_existencia(self) -> None:
        """Hallazgo de revisión: completar la receta sincroniza la existencia
        del conjunto con la de sus piezas; si tenía juegos contados propios
        se perdían. Ahora no se toca y se avisa."""
        from pos_uniformes.services.inventario_service import InventarioService

        chamarra = self.caja.productos[(JARAL, "Chamarra")]
        talla10 = next(v for v in chamarra.variantes if v.talla == "10")
        InventarioService.registrar_ajuste_manual(self.s, talla10, 12, self.admin, referencia="CONTEO")
        self.s.commit()
        plan = self.pants_suelto_jaral(color="Gris")
        self.assertEqual(plan.receta_texto, "")
        aviso = "«Chamarra Deportiva Ignacio Allende (Jaral)» tiene 12 en existencia propia"
        self.assertTrue(any(a.startswith(aviso) for a in plan.avisos), plan.avisos)
        r = alta.aplicar(self.s, plan, self.admin, commit=True)
        self.assertEqual(r.productos[0].recetas, ())
        self.assertTrue(any(a.startswith(aviso) for a in r.productos[0].avisos))
        self.assertEqual(self._receta("Chamarra"), [])
        self.s.refresh(talla10)
        self.assertEqual(talla10.stock_actual, 12)

    def test_el_plan_de_un_conjunto_dice_que_pieza_le_falta(self) -> None:
        plan = alta.planear_desde_modelo(self.s, "Técnica 18", "Chamarra", nivel="Secundaria")
        self.assertIn("falta Pants 2pz", plan.receta_texto)
        self.assertEqual(plan.errores, [])

    def test_nunca_baja_un_precio_que_ya_existe(self) -> None:
        precios_antes = dict(self.s.execute(select(Variante.id, Variante.precio_venta)).all())
        planes = alta.planear_varias_escuelas(self.s, ["Miguel Hidalgo", "Justo Sierra", "Benito Juárez"], "Suéter",
                                              color="Azul", precios_a_mano={"4": 199})
        alta.aplicar(self.s, planes, self.admin, commit=True)
        despues = dict(self.s.execute(select(Variante.id, Variante.precio_venta)).all())
        self.assertEqual({k: despues[k] for k in precios_antes}, precios_antes)

    def test_varias_escuelas_en_una_transaccion(self) -> None:
        planes = alta.planear_varias_escuelas(self.s, ["Miguel Hidalgo", "Justo Sierra"], "Chaleco", color="Azul")
        self.assertEqual([p.nombre for p in planes], ["Chaleco Azul Miguel Hidalgo", "Chaleco Azul Justo Sierra"])
        previstos = [s for p in planes for s in p.skus_previstos]
        self.assertEqual(len(set(previstos)), 14)
        r = alta.aplicar(self.s, planes, self.admin, commit=True)
        self.assertEqual(r.skus, previstos)

    def test_varias_escuelas_si_una_falla_no_queda_ninguna(self) -> None:
        planes = alta.planear_varias_escuelas(self.s, ["Miguel Hidalgo", "Justo Sierra"], "Chaleco", color="Azul")
        antes = self.foto()
        original = alta._crear
        llamadas = []

        def falla_la_segunda(session, plan, usuario, origen):
            llamadas.append(plan.nombre)
            if len(llamadas) == 2:
                raise ValueError("se cayó la segunda")
            return original(session, plan, usuario, origen)

        with patch.object(alta, "_crear", side_effect=falla_la_segunda):
            with self.assertRaisesRegex(ValueError, "segunda"):
                alta.aplicar(self.s, planes, self.admin)
        self.s.commit()
        self.assertEqual(self.foto(), antes)

    def test_solo_admin(self) -> None:
        plan = self.pants_suelto_jaral()
        with self.assertRaises(PermissionError):
            alta.aplicar(self.s, plan, self.caja.cajera)
        self.assertFalse(alta.ensayar(self.s, plan, self.caja.cajera).ok)

    def test_escuela_nueva_solo_admin_y_confirmada(self) -> None:
        spec = {
            "producto": {"nombre": "Pants Suelto", "categoria": "Deportivo", "marca": "Sin marca",
                         "escuela": "Escuela Rural Nueva", "tipo_pieza": "Pants Suelto",
                         "nivel_educativo": "Primaria", "tipo_prenda": "Deportivo"},
            "variantes": [{"talla": "4", "precio": 245}],
        }
        plan = alta.planear(self.s, spec)
        self.assertTrue(plan.errores)
        plan = alta.planear(self.s, spec, confirmados=["Escuela Rural Nueva"])
        self.assertEqual(plan.errores, [])
        with self.assertRaisesRegex(PermissionError, "Solo ADMIN"):
            alta.aplicar(self.s, plan, self.caja.cajera)
        r = alta.aplicar(self.s, plan, self.admin, commit=True)
        self.assertEqual(r.productos[0].escuela, "Escuela Rural Nueva")
        self.assertEqual(r.productos[0].uniforme, "Deportivo")
        self.assertIsNotNone(self.s.scalar(select(Escuela).where(Escuela.nombre == "Escuela Rural Nueva")))

    def test_spec_de_la_skill_sin_uniforme_y_con_origen(self) -> None:
        plan = alta.planear(self.s, {
            "producto": {"nombre": "Pants Suelto", "categoria": "Deportivo", "marca": "Sin marca",
                         "escuela": JARAL, "tipo_pieza": "Pants Suelto", "nivel_educativo": "Primaria",
                         "tipo_prenda": "Deportivo"},
            "color": "Gris",
            "variantes": [{"talla": t, "precio": p} for t, p in ESCALERAS["Pants Suelto"].items()],
            "uniforme": False,
            "modelo": "Pants Suelto Ignacio Allende",
            "origen": alta.origen_copia_escuela("Ignacio Allende", JARAL),
        })
        self.assertEqual(plan.errores, [])
        r = alta.aplicar(self.s, plan, self.admin, alta.ORIGEN_CLAUDE, commit=True)
        self.assertIsNone(r.productos[0].uniforme)
        self.assertEqual(
            r.productos[0].bitacora,
            "Copia de escuela: Ignacio Allende → Ignacio Allende (Jaral) · modelo: Pants Suelto Ignacio Allende",
        )


if __name__ == "__main__":
    unittest.main()
