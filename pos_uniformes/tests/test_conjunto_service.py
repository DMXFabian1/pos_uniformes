"""Catálogo fase 3: Pants 3pz y Chamarra son artificiales — venderlos mueve
sus piezas y su stock se calcula."""

from __future__ import annotations

import io
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria, Escuela, LibretaVenta, Marca, MovimientoInventario, Producto,
    TipoMovimientoInventario, TipoPieza, TipoPrenda, Variante,
)
from pos_uniformes.scripts import armar_recetas
from pos_uniformes.services import conjunto_service as cs
from pos_uniformes.services import uniforme_service as us
from pos_uniformes.services.inventario_service import InventarioService


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        cat = Categoria(nombre="Uniformes"); marca = Marca(nombre="G"); self.s.add_all([cat, marca]); self.s.flush()
        self.cat, self.marca = cat, marca
        self.tp = {n: TipoPrenda(nombre=n) for n in ("Deportivo", "Básico")}
        self.tz = {n: TipoPieza(nombre=n) for n in ("Pants 3pz", "Pants 2pz", "Playera", "Chamarra", "Pants Suelto", "Camisa")}
        self.s.add_all([*self.tp.values(), *self.tz.values()]); self.s.flush()
        self.esc = Escuela(nombre="Justo Sierra"); self.s.add(self.esc); self.s.flush()
        self.p3 = self._prod("Pants 3pz Deportivo JS", "Pants 3pz", tallas={"10": 0, "12": 0})
        self.p2 = self._prod("Pants 2pz Deportivo JS", "Pants 2pz", tallas={"10": 5, "12": 2, "14": 1})
        self.play = self._prod("Playera Deportiva JS", "Playera", tallas={"10": 3, "12": 7})
        self.cham = self._prod("Chamarra Deportiva JS", "Chamarra", tallas={"10": 0, "12": 0})
        self.suelto = self._prod("Pants Suelto JS", "Pants Suelto", tallas={"10": 1, "12": 0})
        self.s.commit()

    def _prod(self, nombre, pieza, *, escuela=True, prenda="Deportivo", tallas):
        p = Producto(nombre=nombre, nombre_base=nombre, categoria_id=self.cat.id, marca_id=self.marca.id,
                     escuela_id=self.esc.id if escuela else None, tipo_prenda_id=self.tp[prenda].id, tipo_pieza_id=self.tz[pieza].id)
        self.s.add(p); self.s.flush()
        for t, st in tallas.items():
            self.s.add(Variante(producto_id=p.id, sku=f"{p.id}-{t}", talla=t, color="Rojo", precio_venta=100, stock_actual=st))
        self.s.flush()
        return p

    def _stock(self, prod, talla) -> int:
        return int(self.s.scalar(select(Variante.stock_actual).where(Variante.producto_id == prod.id, Variante.talla == talla)))

    def _var(self, prod, talla) -> Variante:
        return self.s.scalar(select(Variante).where(Variante.producto_id == prod.id, Variante.talla == talla))

    def _armar(self):
        for c in (self.p3, self.cham):
            prop = cs.proponer_receta(self.s, c)
            cs.definir_receta(self.s, c.id, prop["componentes"])
        self.s.commit()


class RecetaTests(_Base):
    def test_propone_por_tipo_de_pieza_dentro_de_la_escuela(self) -> None:
        prop = cs.proponer_receta(self.s, self.p3)
        self.assertEqual(prop["componentes"], [(self.p2.id, 1, 0), (self.play.id, 1, 1)])
        prop = cs.proponer_receta(self.s, self.cham)
        self.assertEqual(prop["componentes"], [(self.p2.id, 1, 0), (self.suelto.id, -1, 1)])

    def test_ambiguo_o_faltante_no_propone(self) -> None:
        # Polo vs Deportiva: la del 3pz es la deportiva (se desempata solo)
        self._prod("Playera Polo JS", "Playera", tallas={"10": 1})
        prop = cs.proponer_receta(self.s, self.p3)
        self.assertEqual(prop["componentes"], [(self.p2.id, 1, 0), (self.play.id, 1, 1)])
        # dos deportivas (H y M): eso sí lo decide Daniel
        self._prod("Playera Deportiva M JS", "Playera", tallas={"10": 1})
        prop = cs.proponer_receta(self.s, self.p3)
        self.assertEqual(prop["componentes"], []); self.assertIn("Playera", prop["ambiguas"])
        self.s.delete(self._var(self.suelto, "10")); self.s.delete(self._var(self.suelto, "12")); self.s.delete(self.suelto); self.s.flush()
        prop = cs.proponer_receta(self.s, self.cham)
        self.assertEqual(prop["faltan"], ["Pants Suelto"])

    def test_con_uniforme_las_candidatas_son_sus_piezas_incluida_la_polo_general(self) -> None:
        polo = self._prod("Playera Polo Blanca", "Playera", escuela=False, prenda="Básico", tallas={"10": 4})
        self.s.delete(self._var(self.play, "10")); self.s.delete(self._var(self.play, "12")); self.s.delete(self.play); self.s.flush()
        uni = us.armar(self.s, self.esc.id); us.agregar_pieza(self.s, uni.id, polo.id); self.s.commit()
        prop = cs.proponer_receta(self.s, self.p3)
        self.assertEqual(prop["componentes"], [(self.p2.id, 1, 0), (polo.id, 1, 1)])

    def test_definir_valida_y_recalcula_stock(self) -> None:
        with self.assertRaises(ValueError):
            cs.definir_receta(self.s, self.p2.id, [(self.play.id, 1)])   # un 2pz no es conjunto
        with self.assertRaises(ValueError):
            cs.definir_receta(self.s, self.p3.id, [(self.cham.id, 1)])   # una pieza no puede ser otro conjunto
        cs.definir_receta(self.s, self.p3.id, [(self.p2.id, 1), (self.play.id, 1)]); self.s.commit()
        self.assertEqual((self._stock(self.p3, "10"), self._stock(self.p3, "12")), (3, 2))   # min(5,3), min(2,7)
        self.assertEqual(cs.receta_texto(self.s, self.p3.id), "se arma de Pants 2pz Deportivo JS + Playera Deportiva JS")
        cs.definir_receta(self.s, self.cham.id, [(self.p2.id, 1), (self.suelto.id, -1)]); self.s.commit()
        self.assertEqual(self._stock(self.cham, "10"), 5)
        self.assertEqual(cs.receta_texto(self.s, self.cham.id), "sale de Pants 2pz Deportivo JS, deja Pants Suelto JS")
        movs = self.s.scalars(select(MovimientoInventario).where(MovimientoInventario.referencia == f"derivado:{self.p3.id}")).all()
        self.assertEqual(len(movs), 2)


class GeneralesTests(_Base):
    def test_un_conjunto_general_se_arma_de_generales_con_el_mismo_nombre(self) -> None:
        ch = self._prod("Chamarra Liso Azul Marino", "Chamarra", escuela=False, prenda="Básico", tallas={"10": 0})
        p2 = self._prod("Pants 2pz Liso Azul Marino", "Pants 2pz", escuela=False, prenda="Básico", tallas={"10": 3})
        su = self._prod("Pants Suelto Liso Azul Marino", "Pants Suelto", escuela=False, prenda="Básico", tallas={"10": 0})
        self._prod("Pants 2pz Punto Azul Marino", "Pants 2pz", escuela=False, prenda="Básico", tallas={"10": 3})
        self.s.commit()
        prop = cs.proponer_receta(self.s, ch)
        self.assertEqual(prop["componentes"], [(p2.id, 1, 0), (su.id, -1, 1)])


class VentaTests(_Base):
    def setUp(self) -> None:
        super().setUp(); self._armar()

    def test_vender_3pz_baja_2pz_y_playera_y_el_3pz_se_recalcula(self) -> None:
        InventarioService.registrar_movimiento(self.s, self._var(self.p3, "10"), TipoMovimientoInventario.SALIDA_VENTA, -1, referencia="libreta:1", creado_por="VEND-4")
        self.s.commit()
        self.assertEqual((self._stock(self.p2, "10"), self._stock(self.play, "10")), (4, 2))
        self.assertEqual(self._stock(self.p3, "10"), 2)          # min(4, 2)
        self.assertEqual(self._stock(self.cham, "10"), 4)        # la chamarra también depende del 2pz
        tipos = {(m.variante_id, m.tipo_movimiento) for m in self.s.scalars(select(MovimientoInventario).where(MovimientoInventario.referencia == "libreta:1")).all()}
        self.assertEqual(tipos, {(self._var(self.p2, "10").id, TipoMovimientoInventario.SALIDA_VENTA), (self._var(self.play, "10").id, TipoMovimientoInventario.SALIDA_VENTA)})

    def test_vender_chamarra_baja_2pz_y_deja_un_suelto(self) -> None:
        InventarioService.registrar_movimiento(self.s, self._var(self.cham, "10"), TipoMovimientoInventario.SALIDA_VENTA, -1, referencia="libreta:2", creado_por="VEND-4")
        self.s.commit()
        self.assertEqual((self._stock(self.p2, "10"), self._stock(self.suelto, "10"), self._stock(self.cham, "10")), (4, 2, 4))
        entrada = self.s.scalar(select(MovimientoInventario).where(MovimientoInventario.referencia == "libreta:2", MovimientoInventario.variante_id == self._var(self.suelto, "10").id))
        self.assertEqual((entrada.tipo_movimiento, entrada.cantidad), (TipoMovimientoInventario.AJUSTE_ENTRADA, 1))
        self.assertIn("por Chamarra Deportiva JS 10", entrada.observacion)

    def test_llega_mercancia_de_2pz_y_el_3pz_sube_solo(self) -> None:
        InventarioService.registrar_movimiento(self.s, self._var(self.play, "12"), TipoMovimientoInventario.ENTRADA_COMPRA, 10, creado_por="bodega")
        InventarioService.registrar_movimiento(self.s, self._var(self.p2, "12"), TipoMovimientoInventario.ENTRADA_COMPRA, 6, creado_por="bodega")
        self.s.commit()
        self.assertEqual((self._stock(self.p3, "12"), self._stock(self.cham, "12")), (8, 8))   # min(8, 17), 8

    def test_talla_sin_pieza_no_se_toca_y_se_reporta(self) -> None:
        # el 2pz tiene talla 14 pero el 3pz no la tiene: nada que calcular; y una
        # talla del conjunto sin pieza (16) se reporta
        self.s.add(Variante(producto_id=self.p3.id, sku="p3-16", talla="16", color="Rojo", precio_venta=100, stock_actual=9)); self.s.commit()
        self.assertEqual(cs.tallas_sin_pieza(self.s, self.p3.id), ["16"])
        cs.sincronizar_conjunto(self.s, self.p3.id); self.s.commit()
        self.assertEqual(self._stock(self.p3, "16"), 9)
        # y venderla no truena: mueve lo que puede (nada) y sigue
        InventarioService.registrar_movimiento(self.s, self._var(self.p3, "16"), TipoMovimientoInventario.SALIDA_VENTA, -1, referencia="libreta:3", creado_por="x")
        self.s.commit()
        self.assertEqual(self._stock(self.p3, "16"), 9)

    def test_libreta_descuenta_una_vez_y_devuelve_todo(self) -> None:
        from pos_uniformes.services import libreta_service as ls
        entry = LibretaVenta(employee_code="VEND-4", employee_name="Fanny", tipo="venta", piezas=2, comisiones=2, monto_total=900, monto_neto=900,
                             detalle=[{"sku": f"{self.cham.id}-10", "cantidad": 1}, {"sku": f"{self.p3.id}-12", "cantidad": 1}])
        self.s.add(entry); self.s.flush()
        self.assertEqual(ls.descontar_stock(self.s, entry), 2)
        self.assertEqual(ls.descontar_stock(self.s, entry), 0)  # segunda vez no repite
        self.s.commit()
        self.assertEqual((self._stock(self.p2, "10"), self._stock(self.suelto, "10")), (4, 2))
        self.assertEqual((self._stock(self.p2, "12"), self._stock(self.play, "12")), (1, 6))
        self.assertEqual((self._stock(self.p3, "12"), self._stock(self.cham, "12")), (1, 1))
        ls.devolver_stock(self.s, entry); self.s.commit()
        self.assertEqual((self._stock(self.p2, "10"), self._stock(self.suelto, "10")), (5, 1))
        self.assertEqual((self._stock(self.p2, "12"), self._stock(self.play, "12")), (2, 7))
        self.assertEqual((self._stock(self.p3, "12"), self._stock(self.cham, "10")), (2, 5))


class ScriptTests(_Base):
    def test_resumen_e_impresion(self) -> None:
        cs.definir_receta(self.s, self.cham.id, [(self.p2.id, 1), (self.suelto.id, -1)]); self.s.commit()
        filas = armar_recetas._con_texto(self.s, cs.resumen(self.s))
        out = io.StringIO()
        con, prop, pend = armar_recetas.imprimir(filas, salida=out)
        self.assertEqual((con, prop, pend), (1, 1, 0))
        texto = out.getvalue()
        self.assertIn("✓ Justo Sierra · Chamarra Deportiva JS: sale de Pants 2pz Deportivo JS, deja Pants Suelto JS", texto)
        self.assertIn("→ Justo Sierra · Pants 3pz Deportivo JS: Pants 2pz Deportivo JS + Playera Deportiva JS", texto)


class RevisarTests(_Base):
    def test_revisar_cuenta_el_3pz_vendido_como_2pz_y_playera(self) -> None:
        from datetime import date, timedelta
        from pos_uniformes.services.revision_service import _ventas_por_sku
        self._armar()
        self.s.add(LibretaVenta(employee_code="VEND-4", employee_name="Fanny", tipo="venta", piezas=1, comisiones=2, monto_total=500, monto_neto=500,
                                detalle=[{"sku": f"{self.p3.id}-10", "cantidad": 2}, {"sku": f"{self.play.id}-10", "cantidad": 1}]))
        self.s.commit()
        por_sku = _ventas_por_sku(self.s, date.today() - timedelta(days=7))
        piezas = {sku: sum(n for _f, n in filas) for sku, filas in por_sku.items()}
        self.assertEqual(piezas[f"{self.p3.id}-10"], 2)
        self.assertEqual(piezas[f"{self.p2.id}-10"], 2)      # salieron dentro del 3pz
        self.assertEqual(piezas[f"{self.play.id}-10"], 3)    # 1 sola + 2 dentro del 3pz
        self.assertNotIn(f"{self.suelto.id}-10", piezas)     # la chamarra no se vendió


class SueltoFaltanteTests(_Base):
    """Cuando la escuela vende chamarra pero no tiene su Pants Suelto, se le
    da de alta (Daniel, 2026-09-22) y la chamarra ya sabe dónde dejarlo."""

    def setUp(self) -> None:
        super().setUp()
        from pos_uniformes.database.models import RolUsuario, Usuario
        self.s.delete(self._var(self.suelto, "10")); self.s.delete(self._var(self.suelto, "12"))
        self.s.delete(self.suelto)
        self.s.add(Usuario(username="daniel", nombre_completo="Daniel", password_hash="x", rol=RolUsuario.ADMIN, activo=True))
        self.s.commit()

    def test_crea_solo_las_que_faltan_con_las_tallas_del_2pz_y_su_precio(self) -> None:
        from pos_uniformes.database.models import Usuario
        from pos_uniformes.scripts import crear_piezas_faltantes as csf
        filas = csf.planear(self.s)
        self.assertEqual([f["nombre"] for f in filas], ["Pants Suelto Justo Sierra"])
        self.assertEqual(sorted(t for t, _c in filas[0]["tallas"]), ["10", "12", "14"])
        productos, tallas = csf.aplicar(self.s, filas, self.s.scalars(select(Usuario)).first())
        self.s.commit()
        self.assertEqual((productos, tallas), (1, 3))
        nuevo = self.s.scalars(select(Producto).where(Producto.nombre.like("Pants Suelto%"))).first()
        vs = {v.talla: v for v in self.s.scalars(select(Variante).where(Variante.producto_id == nuevo.id))}
        self.assertEqual({t: int(v.stock_actual) for t, v in vs.items()}, {"10": 0, "12": 0, "14": 0})
        self.assertEqual(float(vs["10"].precio_venta), 259.0)
        self.assertTrue(all(v.sku for v in vs.values()))
        # y ahora la chamarra ya sabe de dónde sale y dónde deja el suelto
        prop = cs.proponer_receta(self.s, self.cham)
        self.assertEqual(prop["componentes"], [(self.p2.id, 1, 0), (nuevo.id, -1, 1)])
        # correrlo otra vez no duplica
        self.assertEqual(csf.planear(self.s), [])

    def test_no_toca_a_la_que_usa_un_suelto_general(self) -> None:
        from pos_uniformes.scripts import crear_piezas_faltantes as csf
        general = self._prod("Pants Suelto Punto Rojo", "Pants Suelto", escuela=False, prenda="Básico", tallas={"10": 2})
        uni = us.armar(self.s, self.esc.id); us.agregar_pieza(self.s, uni.id, general.id); self.s.commit()
        self.assertEqual(csf.planear(self.s), [])
        self.assertEqual(cs.proponer_receta(self.s, self.cham)["componentes"], [(self.p2.id, 1, 0), (general.id, -1, 1)])


class AlternativasTests(_Base):
    """Daniel (2026-09-22): "el SABES puede llevar de hombre o de mujer playera
    deportiva" → las dos playeras son una sola pieza del 3pz."""

    def setUp(self) -> None:
        super().setUp()
        self.s.delete(self._var(self.play, "10")); self.s.delete(self._var(self.play, "12")); self.s.delete(self.play)
        self.play_h = self._prod("Playera Deportiva H JS", "Playera", tallas={"10": 3, "12": 1})
        self.play_m = self._prod("Playera Deportiva M JS", "Playera", tallas={"10": 2, "12": 0})
        self.play_h.genero, self.play_m.genero = "Hombre", "Mujer"
        self.s.commit()

    def test_las_dos_playeras_son_la_misma_pieza_y_el_stock_las_suma(self) -> None:
        prop = cs.proponer_receta(self.s, self.p3)
        self.assertEqual(prop["componentes"], [(self.p2.id, 1, 0), (self.play_h.id, 1, 1), (self.play_m.id, 1, 1)])
        cs.definir_receta(self.s, self.p3.id, prop["componentes"]); self.s.commit()
        self.assertEqual(cs.receta_texto(self.s, self.p3.id), "se arma de Pants 2pz Deportivo JS + Playera Deportiva H JS o Playera Deportiva M JS")
        self.assertEqual(self._stock(self.p3, "10"), 5)   # min(2pz 5, playeras 3+2)
        self.assertEqual(self._stock(self.p3, "12"), 1)   # min(2pz 2, playeras 1+0)

    def test_al_vender_se_toma_la_que_mas_hay(self) -> None:
        cs.definir_receta(self.s, self.p3.id, cs.proponer_receta(self.s, self.p3)["componentes"]); self.s.commit()
        InventarioService.registrar_movimiento(self.s, self._var(self.p3, "10"), TipoMovimientoInventario.SALIDA_VENTA, -1, referencia="libreta:9", creado_por="VEND-4")
        self.s.commit()
        self.assertEqual((self._stock(self.play_h, "10"), self._stock(self.play_m, "10")), (2, 2))  # bajó la H (había 3)
        self.assertEqual(self._stock(self.p2, "10"), 4)
        self.assertEqual(self._stock(self.p3, "10"), 4)   # min(4, 2+2)

    def test_dos_del_mismo_genero_no_son_alternativas(self) -> None:
        self.play_m.genero = "Hombre"; self.s.commit()
        prop = cs.proponer_receta(self.s, self.p3)
        self.assertEqual(prop["componentes"], []); self.assertIn("Playera", prop["ambiguas"])


class PlayeraFaltanteTests(_Base):
    """Vicente Guerrero vende 3pz pero no tiene playera propia (Daniel,
    2026-09-22: "crea su propia deportiva")."""

    def setUp(self) -> None:
        super().setUp()
        from pos_uniformes.database.models import RolUsuario, Usuario
        self.s.delete(self._var(self.play, "10")); self.s.delete(self._var(self.play, "12")); self.s.delete(self.play)
        self.s.add(Usuario(username="daniel", nombre_completo="Daniel", password_hash="x", rol=RolUsuario.ADMIN, activo=True))
        self.s.commit()

    def test_le_crea_su_playera_deportiva_con_los_precios_de_las_demas(self) -> None:
        from pos_uniformes.database.models import Usuario
        from pos_uniformes.scripts import crear_piezas_faltantes as csf
        filas = [f for f in csf.planear(self.s) if f["tipo_pieza"] == "Playera"]
        self.assertEqual([f["nombre"] for f in filas], ["Playera Deportiva Justo Sierra"])
        csf.aplicar(self.s, filas, self.s.scalars(select(Usuario)).first()); self.s.commit()
        nueva = self.s.scalars(select(Producto).where(Producto.nombre.like("Playera Deportiva%"))).first()
        vs = {v.talla: float(v.precio_venta) for v in self.s.scalars(select(Variante).where(Variante.producto_id == nueva.id))}
        self.assertEqual(vs, {"10": 199.0, "12": 209.0, "14": 209.0})
        self.assertEqual(cs.proponer_receta(self.s, self.p3)["componentes"], [(self.p2.id, 1, 0), (nueva.id, 1, 1)])


class GrupoLegadoTests(_Base):
    """La columna `grupo` se agregó con 0 para todas, así que las recetas que
    ya existían se leían como "2pz **o** playera". La migración
    4f5a6b7c8d9e las reagrupa por tipo de pieza."""

    def test_reagrupar_por_tipo_de_pieza(self) -> None:
        from pos_uniformes.database.models import ConjuntoComponente
        self.s.add_all([
            ConjuntoComponente(conjunto_id=self.p3.id, componente_id=self.p2.id, cantidad=1, grupo=0),
            ConjuntoComponente(conjunto_id=self.p3.id, componente_id=self.play.id, cantidad=1, grupo=0),
            ConjuntoComponente(conjunto_id=self.cham.id, componente_id=self.p2.id, cantidad=1, grupo=0),
            ConjuntoComponente(conjunto_id=self.cham.id, componente_id=self.suelto.id, cantidad=-1, grupo=0),
        ])
        self.s.commit()
        self.assertIn(" o ", cs.receta_texto(self.s, self.p3.id))  # así se leía: mal
        cs.reagrupar_por_tipo_de_pieza(self.s); self.s.commit()
        self.assertEqual(cs.receta_texto(self.s, self.p3.id), "se arma de Pants 2pz Deportivo JS + Playera Deportiva JS")
        self.assertEqual(cs.receta_texto(self.s, self.cham.id), "sale de Pants 2pz Deportivo JS, deja Pants Suelto JS")

    def test_dos_piezas_del_mismo_tipo_siguen_siendo_alternativas(self) -> None:
        from pos_uniformes.database.models import ConjuntoComponente
        otra = self._prod("Playera Deportiva M JS", "Playera", tallas={"10": 1})
        self.s.add_all([
            ConjuntoComponente(conjunto_id=self.p3.id, componente_id=self.p2.id, cantidad=1, grupo=7),
            ConjuntoComponente(conjunto_id=self.p3.id, componente_id=self.play.id, cantidad=1, grupo=7),
            ConjuntoComponente(conjunto_id=self.p3.id, componente_id=otra.id, cantidad=1, grupo=7),
        ])
        self.s.commit()
        cs.reagrupar_por_tipo_de_pieza(self.s); self.s.commit()
        self.assertEqual(cs.receta_texto(self.s, self.p3.id), "se arma de Pants 2pz Deportivo JS + Playera Deportiva JS o Playera Deportiva M JS")


class TotalesTests(_Base):
    """Un 3pz con receta ES el pants 2pz y la playera que ya están contados:
    su existencia no se suma otra vez a los totales del inventario."""

    def test_el_filtro_deja_fuera_solo_a_los_conjuntos_con_receta(self) -> None:
        from sqlalchemy import func
        total = lambda: int(self.s.scalar(  # noqa: E731
            select(func.coalesce(func.sum(Variante.stock_actual), 0))
            .select_from(Variante).join(Variante.producto)
            .where(cs.filtro_sin_conjuntos())
        ))
        todo = int(self.s.scalar(select(func.coalesce(func.sum(Variante.stock_actual), 0))))
        self.assertEqual(total(), todo)          # sin recetas, nada se excluye
        self._armar()
        self.s.commit()
        derivado = sum(
            int(v.stock_actual)
            for p in (self.p3, self.cham)
            for v in self.s.scalars(select(Variante).where(Variante.producto_id == p.id)).all()
        )
        self.assertGreater(derivado, 0)
        self.assertEqual(total(), int(self.s.scalar(select(func.coalesce(func.sum(Variante.stock_actual), 0)))) - derivado)
        # y las prendas normales siguen contando
        self.assertIn(self.p2.id, [v.producto_id for v in self.s.scalars(
            select(Variante).join(Variante.producto).where(cs.filtro_sin_conjuntos())).all()])


class CandadoDeTallasTests(_Base):
    """Una pieza que no comparte ninguna talla con el conjunto no lo arma en
    ninguna: la receta nace muerta. Pasó con los Pants 3pz de Álvaro Obregón,
    a los que se les puso una playera unitalla (2026-09-22, nota 40)."""

    def test_no_propone_una_pieza_unitalla_para_un_conjunto_por_numero(self):
        unitalla = self._prod("Playera Deportiva", "Playera", escuela=False, tallas={"Uni": 5})
        # Se va la playera de la escuela: solo queda la genérica unitalla.
        for v in self.s.scalars(select(Variante).where(Variante.producto_id == self.play.id)).all():
            v.activo = False
        self.play.activo = False
        self.s.flush()

        propuesta = cs.proponer_receta(self.s, self.p3)
        self.assertEqual(propuesta["componentes"], [], "no se arma con lo que no empata")
        self.assertIn("Playera", propuesta["faltan"], "se dice que falta, no se inventa")
        self.assertTrue(unitalla.activo)

    def test_la_pieza_que_si_empata_se_sigue_proponiendo(self):
        propuesta = cs.proponer_receta(self.s, self.p3)
        ids = {pid for pid, _c, _g in propuesta["componentes"]}
        self.assertIn(self.play.id, ids)

    def test_empata_en_tallas_lo_dice_directo(self):
        unitalla = self._prod("Playera Uni", "Playera", escuela=False, tallas={"Uni": 1})
        self.assertFalse(cs.empata_en_tallas(self.s, self.p3, unitalla))
        self.assertTrue(cs.empata_en_tallas(self.s, self.p3, self.play))

