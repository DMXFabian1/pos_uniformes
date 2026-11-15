"""«Escuela igual a otra» (tanda 5 del alta, 2026-11-15).

Sobre la caja en miniatura: «Ignacio Allende (Jaral)» es la copia de Ignacio
Allende en Gris a la que le faltan el Pants Suelto, el suéter y el chaleco
(como el 10-nov). Cada prenda sale NUEVA, YA ESTÁ o CAMBIA COLOR; las nuevas
copian los precios del origen con existencia 0, todo junto o nada.
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
    Marca,
    MovimientoInventario,
    Producto,
    TipoPieza,
    Uniforme,
    UniformePieza,
    Variante,
)
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import copiar_escuela_service as ce
from pos_uniformes.services.catalog_service import CatalogService
from tests._ayuda_mini_caja import ESCALERAS, MiniCaja

D = Decimal
ORIGEN = "Ignacio Allende"
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
        return {m.__name__: self.contar(m) for m in (Escuela, Producto, Variante, UniformePieza, ConjuntoComponente,
                                                       CambioCatalogo, MovimientoInventario)}

    def producto(self, nombre: str) -> Producto | None:
        return self.s.scalar(select(Producto).where(Producto.nombre == nombre))

    def pieza(self, plan: ce.PlanCopia, tipo: str) -> ce.PiezaACopiar:
        return next(p for p in plan.piezas if p.origen.tipo_pieza == tipo)

    def precios(self, nombre: str) -> dict[str, Decimal]:
        p = self.producto(nombre)
        return {v.talla: v.precio_venta for v in self.s.scalars(select(Variante).where(Variante.producto_id == p.id))}

    def falda_general(self) -> Producto:
        """Una pieza general (sin escuela) en el uniforme de Ignacio Allende."""
        pieza = TipoPieza(nombre="Falda")
        self.s.add(pieza)
        self.s.flush()
        falda = Producto(nombre="Falda Escocés", nombre_base="Falda Escocés",
                         categoria_id=self.caja.cat["Oficial"].id, marca_id=self.caja.marca.id,
                         tipo_pieza_id=pieza.id, tipo_prenda_id=self.caja.prenda["Oficial"].id)
        self.s.add(falda)
        self.s.flush()
        self.s.add(Variante(producto_id=falda.id, sku="SKU999001", talla="10", color="Azul Marino",
                            precio_venta=D(320), stock_actual=0))
        uni = self.s.scalar(select(Uniforme).where(Uniforme.escuela_id == self.caja.escuelas[ORIGEN].id))
        self.s.add(UniformePieza(uniforme_id=uni.id, producto_id=falda.id, grupo="Diario", orden=9,
                                 obligatoria=False))
        self.s.commit()
        return falda


class EstadosTests(_Base):
    def test_jaral_cada_prenda_con_su_estado(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        estados = {p.origen.tipo_pieza: p.estado for p in plan.piezas}
        self.assertEqual(estados, {
            "Pants 2pz": ce.ESTADO_YA_ESTA, "Pants 3pz": ce.ESTADO_YA_ESTA, "Playera": ce.ESTADO_YA_ESTA,
            "Chamarra": ce.ESTADO_YA_ESTA, "Pants Suelto": ce.ESTADO_NUEVA, "Suéter": ce.ESTADO_NUEVA,
            "Chaleco": ce.ESTADO_NUEVA,
        })
        self.assertEqual(plan.todos_los_errores, [])
        self.assertTrue(plan.puede_aplicar)
        # El color cambia también en el nombre; el Pants Suelto toma el Gris que ya usa Jaral.
        self.assertEqual(self.pieza(plan, "Suéter").nombre, f"Suéter Botones M Azul {JARAL}")
        self.assertEqual(self.pieza(plan, "Chaleco").nombre, f"Chaleco Azul {JARAL}")
        self.assertEqual(self.pieza(plan, "Pants Suelto").color, "Gris")
        self.assertEqual(plan.color_para_todas("Sin color"), "Gris")
        self.assertEqual(plan.color_para_todas("Rojo"), "Azul")
        self.assertEqual(plan.texto_boton(), "Copiar 3 prendas (24 tallas)")
        self.assertEqual(
            plan.resumen(),
            f"{JARAL} queda igual que {ORIGEN}: se crean 3 prendas (24 tallas, de $245 a $315). "
            f"Mismos precios que {ORIGEN}, sin existencia.",
        )

    def test_el_plan_no_escribe_nada(self) -> None:
        antes = self.foto()
        ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        self.assertEqual(self.foto(), antes)
        self.assertFalse(self.s.new)

    def test_prenda_por_prenda_gana_sobre_para_todas(self) -> None:
        chaleco = self.caja.productos[(ORIGEN, "Chaleco")].id
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"}, color_de={chaleco: "Blanca"})
        self.assertEqual(self.pieza(plan, "Suéter").color, "Azul")
        self.assertEqual(self.pieza(plan, "Chaleco").color, "Blanco")  # una sola forma
        self.assertEqual(self.pieza(plan, "Chaleco").nombre, f"Chaleco Blanco {JARAL}")

    def test_cambia_color_de_lo_que_ya_esta(self) -> None:
        playera = self.caja.productos[(ORIGEN, "Playera")].id
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, color_de={playera: "Azul"})
        p = self.pieza(plan, "Playera")
        self.assertEqual(p.estado, ce.ESTADO_CAMBIA_COLOR)
        self.assertEqual(p.texto_estado, "CAMBIA COLOR: Gris → Azul")
        self.assertEqual(p.todos_los_errores, [])
        self.assertIn("1 cambia de color", plan.resumen())
        precios_antes = self.precios(f"Playera Deportiva {JARAL}")
        resultado = ce.aplicar_copia(self.s, plan, self.admin, commit=True)
        self.assertEqual(len(resultado.cambiados), 1)
        v = self.s.scalars(select(Variante).where(Variante.producto_id == p.destino_id)).all()
        self.assertEqual({x.color for x in v}, {"Azul"})
        # El precio no se toca (nunca baja) y los SKU tampoco.
        self.assertEqual(self.precios(f"Playera Deportiva {JARAL}"), precios_antes)
        self.assertEqual(set(resultado.variantes_cambiadas), {x.id for x in v})
        nota = self.s.scalars(select(CambioCatalogo.observacion).where(
            CambioCatalogo.entidad_id.in_([x.id for x in v]))).all()
        self.assertTrue(any(n and n.startswith("Copia de escuela: Ignacio Allende") for n in nota))

    def test_un_color_que_no_existe_pregunta(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Grisz"})
        self.assertFalse(plan.puede_aplicar)
        self.assertIn("se parece a «Gris»", plan.nota_bloqueo())
        plan = ce.replanear(self.s, plan, confirmados=("Grisz",))
        self.assertTrue(plan.puede_aplicar)

    def test_desmarcar_no_la_lleva(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        plan = ce.marcar(self.s, plan, self.caja.productos[(ORIGEN, "Suéter")].id, False)
        self.assertEqual(sorted(p.origen.tipo_pieza for p in plan.nuevas), ["Chaleco", "Pants Suelto"])
        self.assertFalse(self.pieza(plan, "Suéter").marcada)
        self.assertEqual(plan.texto_boton(), "Copiar 2 prendas (17 tallas)")
        for tipo in ("Pants Suelto", "Chaleco", "Pants 2pz", "Pants 3pz", "Playera", "Chamarra"):
            plan = ce.marcar(self.s, plan, self.caja.productos[(ORIGEN, tipo)].id, False)
        self.assertEqual(plan.nota_bloqueo(), "Marca al menos una prenda.")

    def test_ya_tiene_todo(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL)
        for tipo in ("Pants Suelto", "Suéter", "Chaleco"):
            plan = ce.marcar(self.s, plan, self.caja.productos[(ORIGEN, tipo)].id, False)
        self.assertFalse(plan.puede_aplicar)
        self.assertEqual(plan.nota_bloqueo(), "El destino ya tiene todo lo marcado.")
        with self.assertRaises(ce.CopiaNoValida):
            ce.aplicar_copia(self.s, plan, self.admin)

    def test_la_misma_escuela_no(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, ORIGEN)
        self.assertIn("es la misma", plan.nota_bloqueo())

    def test_pieza_general_del_uniforme_se_liga(self) -> None:
        falda = self.falda_general()
        plan = ce.planear_copia(self.s, ORIGEN, JARAL)
        p = next(p for p in plan.piezas if p.origen.producto_id == falda.id)
        self.assertEqual(p.estado, ce.ESTADO_SE_LIGA)
        self.assertIn("1 pieza que ya existe se liga a su uniforme", plan.resumen())
        ce.aplicar_copia(self.s, plan, self.admin, commit=True)
        uni = self.s.scalar(select(Uniforme).where(Uniforme.escuela_id == self.caja.escuelas[JARAL].id))
        liga = self.s.scalar(select(UniformePieza).where(UniformePieza.uniforme_id == uni.id,
                                                         UniformePieza.producto_id == falda.id))
        self.assertEqual((liga.grupo, liga.orden, liga.obligatoria), ("Diario", 9, False))
        # La segunda vez ya está.
        plan = ce.planear_copia(self.s, ORIGEN, JARAL)
        self.assertEqual(next(p for p in plan.piezas if p.origen.producto_id == falda.id).estado,
                         ce.ESTADO_YA_ESTA)


class AplicarTests(_Base):
    def test_copia_a_jaral_mismos_precios_existencia_0_uniforme_y_receta(self) -> None:
        # El origen tiene un precio distinto al que más se repite: se copia el del origen.
        gd = self.s.scalar(select(Variante).where(
            Variante.producto_id == self.caja.productos[(ORIGEN, "Pants Suelto")].id, Variante.talla == "GD"))
        gd.precio_venta = D(299)
        self.s.commit()
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        resultado = ce.aplicar_copia(self.s, plan, self.admin, commit=True)
        self.assertEqual(len(resultado.productos), 3)
        self.assertEqual(self.precios(f"Pants Suelto {JARAL}"),
                         {**{t: D(p) for t, p in ESCALERAS["Pants Suelto"].items()}, "GD": D(299)})
        self.assertEqual(self.precios(f"Suéter Botones M Azul {JARAL}"),
                         self.precios(f"Suéter Botones M Rojo {ORIGEN}"))
        nuevos = [self.producto(p.nombre) for p in resultado.productos]
        variantes = self.s.scalars(select(Variante).where(Variante.producto_id.in_([p.id for p in nuevos]))).all()
        self.assertEqual({v.stock_actual for v in variantes}, {0})
        self.assertEqual(self.contar(MovimientoInventario), 0)
        # Mismo lugar en el uniforme que en el origen.
        uni = self.s.scalar(select(Uniforme).where(Uniforme.escuela_id == self.caja.escuelas[JARAL].id))
        grupos = {self.s.get(Producto, l.producto_id).nombre: l.grupo for l in self.s.scalars(
            select(UniformePieza).where(UniformePieza.uniforme_id == uni.id))}
        self.assertEqual(grupos[f"Pants Suelto {JARAL}"], "Deportivo")
        self.assertEqual(grupos[f"Chaleco Azul {JARAL}"], "Diario")
        # La Chamarra de Jaral (sin receta) se completa con el Pants Suelto nuevo.
        chamarra = self.caja.productos[(JARAL, "Chamarra")]
        self.assertEqual(self.contar_receta(chamarra.id), 2)
        # Bitácora con el origen.
        nota = self.s.scalar(select(CambioCatalogo.observacion).where(
            CambioCatalogo.entidad_id == self.producto(f"Chaleco Azul {JARAL}").id))
        self.assertEqual(nota, f"Copia de escuela: {ORIGEN} → {JARAL} · modelo: Chaleco Rojo {ORIGEN}")
        # Volver a planear da 0 cambios.
        otra = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        self.assertEqual(otra.nuevas, [])
        self.assertFalse(otra.hay_cambios)

    def contar_receta(self, conjunto_id: int) -> int:
        return int(self.s.scalar(select(func.count()).select_from(ConjuntoComponente).where(
            ConjuntoComponente.conjunto_id == conjunto_id)))

    def test_ensayo_da_los_sku_reales_y_no_guarda(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        antes = self.foto()
        ensayo = ce.ensayar_copia(self.s, plan, self.admin)
        self.assertTrue(ensayo.ok, ensayo.error)
        self.assertEqual([t.sku for p in ensayo.productos for t in p.tallas],
                         [t.sku for p in plan.planes for t in p.tallas])
        self.s.rollback()
        self.assertEqual(self.foto(), antes)

    def test_todo_o_nada(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        antes = self.foto()
        original = alta.uniforme_service.agregar_pieza
        llamadas = []

        def falla_a_la_tercera(*a, **kw):
            llamadas.append(1)
            if len(llamadas) == 3:
                raise ValueError("se cayó la luz")
            return original(*a, **kw)

        with patch.object(alta.uniforme_service, "agregar_pieza", side_effect=falla_a_la_tercera):
            with self.assertRaises(ValueError):
                ce.aplicar_copia(self.s, plan, self.admin)
        self.s.rollback()
        self.assertEqual(self.foto(), antes)

    def test_una_cajera_no_puede(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        antes = self.foto()
        with self.assertRaises(PermissionError):
            ce.aplicar_copia(self.s, plan, self.caja.cajera)
        self.s.rollback()
        self.assertEqual(self.foto(), antes)

    def test_nunca_baja_un_precio_de_lo_que_ya_esta(self) -> None:
        # Jaral vende su Playera más cara que el origen: copiar no la toca.
        playera = self.caja.productos[(JARAL, "Playera")]
        for v in self.s.scalars(select(Variante).where(Variante.producto_id == playera.id)):
            v.precio_venta = v.precio_venta + 10
        self.s.commit()
        antes = self.precios(playera.nombre)
        origen = self.caja.productos[(ORIGEN, "Playera")].id
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"}, color_de={origen: "Azul"})
        self.assertEqual(self.pieza(plan, "Playera").estado, ce.ESTADO_CAMBIA_COLOR)
        ce.aplicar_copia(self.s, plan, self.admin, commit=True)
        self.assertEqual(self.precios(playera.nombre), antes)


class EscuelaNuevaTests(_Base):
    NUEVA = "Ignacio Allende (Rancho Nuevo)"

    def test_pregunta_si_es_la_misma(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, self.NUEVA)
        self.assertTrue(plan.es_nueva)
        # La de origen no se ofrece (de ella se copia).
        self.assertEqual([p.valor for p in plan.parecidas], [JARAL])
        self.assertFalse(plan.puede_aplicar)
        self.assertIn(f"es la misma que «{JARAL}»", plan.nota_bloqueo())
        # Sin la de origen fuera, también sale (mismo nombre, otro lugar).
        self.assertEqual({p.valor for p in ce.escuelas_parecidas(self.s, "Ignacio Allende Rancho Nuevo")},
                         {JARAL, ORIGEN})
        self.assertEqual(ce.escuelas_parecidas(self.s, JARAL), ())
        # Mientras no se conteste no hay planes, pero sí la lista.
        self.assertEqual(len(plan.piezas), 7)
        self.assertEqual({p.estado for p in plan.piezas}, {ce.ESTADO_NUEVA})
        self.assertEqual(plan.planes, [])
        # El resumen ya cuenta las tallas del origen (no «0 tallas»).
        self.assertIn("se crean 7 prendas (64 tallas", plan.resumen())
        self.assertEqual(plan.texto_boton(), "Copiar 7 prendas (64 tallas)")

    def test_sin_acentos_es_la_que_ya_existe(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, "ignacio allende (JARAL)")
        self.assertFalse(plan.es_nueva)
        self.assertEqual(plan.destino, JARAL)

    def test_crear_escuela_nueva_con_todo(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, self.NUEVA, escuela_nueva=True)
        self.assertEqual(plan.todos_los_errores, [])
        self.assertEqual(plan.texto_boton(), "Copiar 7 prendas (64 tallas)")
        self.assertTrue(plan.resumen().startswith(f"Se crea la escuela {self.NUEVA}, igual que {ORIGEN}"))
        # Los SKU previstos van seguidos y los conjuntos al final.
        skus = [t.sku for p in plan.planes for t in p.tallas]
        self.assertEqual(len(skus), len(set(skus)))
        self.assertEqual([p.tipo_pieza for p in plan.planes][-2:], ["Pants 3pz", "Chamarra"])
        resultado = ce.aplicar_copia(self.s, plan, self.admin, commit=True)
        self.assertTrue(resultado.escuela_creada)
        escuela = self.s.scalar(select(Escuela).where(Escuela.nombre == self.NUEVA))
        self.assertIsNotNone(escuela)
        self.assertEqual(sorted(t.sku for p in resultado.productos for t in p.tallas), sorted(skus))
        pants3 = self.producto(f"Pants 3pz Deportivo {self.NUEVA}")
        self.assertEqual(int(self.s.scalar(select(func.count()).select_from(ConjuntoComponente).where(
            ConjuntoComponente.conjunto_id == pants3.id))), 2)
        self.assertIn("Se creó la escuela", plan.texto_listo())

    def test_solo_admin_crea_la_escuela(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, self.NUEVA, escuela_nueva=True)
        antes = self.foto()
        with self.assertRaises(PermissionError):
            ce.aplicar_copia(self.s, plan, self.caja.cajera)
        self.s.rollback()
        self.assertEqual(self.foto(), antes)


class DosColoresTests(_Base):
    """Dos prendas del origen que solo difieren en el color no caen en la
    misma del destino (hallazgo de la revisión de la tanda 5)."""

    def setUp(self) -> None:
        super().setUp()
        calceta = TipoPieza(nombre="Calceta")
        self.s.add(calceta)
        self.s.flush()
        self.caja.pieza["Calceta"] = calceta
        tallas = {t: 45 for t in ("4", "6", "8")}
        self.blanca = self.caja.prod(ORIGEN, "Calceta", nombre="Calceta Blanca", prenda="Oficial",
                                     color="Blanco", precios=tallas)
        self.azul = self.caja.prod(ORIGEN, "Calceta", nombre="Calceta Azul Marino", prenda="Oficial",
                                   color="Azul Marino", precios=tallas)
        self.destino = self.caja.prod(JARAL, "Calceta", nombre="Calceta Blanca", prenda="Oficial",
                                      color="Blanco", precios=tallas)
        self.s.commit()

    def de(self, plan: ce.PlanCopia, producto: Producto) -> ce.PiezaACopiar:
        return next(p for p in plan.piezas if p.origen.producto_id == producto.id)

    def test_la_del_otro_color_sale_nueva(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL)
        self.assertEqual(self.de(plan, self.blanca).estado, ce.ESTADO_YA_ESTA)
        self.assertEqual(self.de(plan, self.blanca).destino_id, self.destino.id)
        azul = self.de(plan, self.azul)
        self.assertEqual(azul.estado, ce.ESTADO_NUEVA)
        self.assertIsNone(azul.destino_id)
        self.assertEqual(azul.nombre, f"Calceta Azul Marino {JARAL}")

    def test_dos_colores_elegidos_no_pisan_la_misma(self) -> None:
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Blanco": "Gris", "Azul Marino": "Verde"})
        destinos = [p.destino_id for p in plan.cambian]
        self.assertEqual(destinos, [self.destino.id])
        self.assertEqual(self.de(plan, self.azul).estado, ce.ESTADO_NUEVA)

    def test_cambia_color_avisa_la_existencia(self) -> None:
        for v in self.destino.variantes:
            v.stock_actual = 4
        self.s.commit()
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, color_de={self.blanca.id: "Gris"})
        p = self.de(plan, self.blanca)
        self.assertEqual(p.estado, ce.ESTADO_CAMBIA_COLOR)
        self.assertEqual(p.existencia, 12)
        self.assertIn("Tiene 12 piezas en existencia: también quedan como Gris.", p.avisos)
        self.assertIn("con 12 piezas en existencia, que también cambian", plan.resumen())


class PrendaSinTallasTests(_Base):
    def test_la_del_destino_sin_tallas_se_llena(self) -> None:
        c = self.caja
        vacia = Producto(nombre=f"Pants Suelto {JARAL}", nombre_base=f"Pants Suelto {JARAL}",
                         categoria_id=c.cat["Deportivo"].id, marca_id=c.marca.id,
                         escuela_id=c.escuelas[JARAL].id, tipo_pieza_id=c.pieza["Pants Suelto"].id)
        self.s.add(vacia)
        self.s.commit()
        plan = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"})
        p = self.pieza(plan, "Pants Suelto")
        self.assertEqual(p.estado, ce.ESTADO_NUEVA)
        self.assertEqual(p.plan.reusar_id, vacia.id)
        self.assertTrue(plan.puede_aplicar, plan.todos_los_errores)
        ce.aplicar_copia(self.s, plan, self.admin, commit=True)
        self.s.expire_all()
        self.assertEqual(len(self.s.get(Producto, vacia.id).variantes), len(p.origen.tallas))


class PurasTests(unittest.TestCase):
    def test_nombre_sin_color(self) -> None:
        colores = [["azul", "marino"], ["azul"], ["rojo"], ["blanco"], ["gris"]]
        self.assertEqual(ce.nombre_sin_color("Suéter Botones M Rojo", colores), "sueter botones m")
        self.assertEqual(ce.nombre_sin_color("Chaleco Azul Marino", colores), "chaleco")
        self.assertEqual(ce.nombre_sin_color("Blusa Blanca Manga Corta", colores), "blusa manga corta")
        self.assertEqual(ce.clave_pieza("Suéter", "Suéter Botones M Gris", colores),
                         ce.clave_pieza("Suéter", "Suéter Botones M Rojo", colores))

    def test_filtrar_escuelas(self) -> None:
        escuelas = [ce.EscuelaParaCopiar(1, "Ignacio Allende", ("Primaria",), 7),
                    ce.EscuelaParaCopiar(2, "Técnica 18", ("Secundaria",), 1)]
        self.assertEqual([e.nombre for e in ce.filtrar_escuelas(escuelas, "tecnica")], ["Técnica 18"])
        self.assertEqual(escuelas[0].detalle, "Primaria · 7 prendas")


if __name__ == "__main__":
    unittest.main()
