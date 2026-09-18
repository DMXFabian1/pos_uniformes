"""Bodega desde el celular: llegó mercancía (entra al inventario y a una caja) y pasar al piso."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    BodegaUbicacion,
    ConteoInventario,
    MovimientoInventario,
    Variante,
)
from pos_uniformes.services import bodega_movil_service as bm
from pos_uniformes.tests.test_conteo_jornada_service import _seed


class BodegaMovilTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.escuela = _seed(self.s, "Uno", stock=10)   # 2 prendas × tallas 6 y 8, stock 10
        self.s.add(BodegaUbicacion(codigo="ALMACEN-N1", rack="ALMACEN", nivel=1))
        self.s.add(BodegaUbicacion(codigo="PISO-N1", rack="PISO", nivel=1))
        self.s.commit()
        self.v = list(self.s.scalars(select(Variante).order_by(Variante.id)).all())

    def tearDown(self) -> None:
        self.s.close()

    def _contenido(self, vid: int) -> int:
        return sum(c.cantidad for c in self.s.scalars(select(BodegaContenido).where(BodegaContenido.variante_id == vid)).all())

    # --- llegó mercancía ---------------------------------------------------------
    def test_llego_al_piso_sube_el_inventario_y_no_abre_caja(self) -> None:
        # Lo normal: llega y se queda a la mano. Ninguna caja se toca.
        v0, v1 = self.v[0], self.v[1]
        r = bm.llego_mercancia(
            self.s, items=[{"variante_id": v0.id, "cantidad": 12}, {"variante_id": v1.id, "cantidad": 0}],
            quien_code="VEND-1", quien="Daniel", referencia="Maquilador 13/09",
        )
        self.s.commit()
        self.assertEqual((r["piezas"], r["tallas"], r["al_piso"], r["en_caja"]), (12, 1, 12, 0))
        self.assertIsNone(r["caja_id"])
        self.s.refresh(v0)
        self.assertEqual(v0.stock_actual, 22)            # 10 + 12
        self.assertEqual(self._contenido(v0.id), 0)
        self.assertEqual(v1.stock_actual, 10)             # la de 0 no se tocó
        self.assertEqual(self.s.scalars(select(BodegaCaja)).all(), [])
        mov = self.s.scalars(select(MovimientoInventario)).one()
        self.assertEqual((mov.tipo_movimiento.value, mov.cantidad, mov.stock_posterior), ("ENTRADA_COMPRA", 12, 22))
        self.assertIn("VEND-1", mov.creado_por)
        self.assertIn("12 al piso", mov.observacion)

    def test_parte_a_una_caja_nueva(self) -> None:
        v0, v1 = self.v[0], self.v[1]
        r = bm.llego_mercancia(
            self.s, items=[{"variante_id": v0.id, "cantidad": 12, "a_caja": 8}, {"variante_id": v1.id, "cantidad": 4}],
            quien_code="VEND-1", caja_nueva=True, referencia="Maquilador 13/09",
        )
        self.assertEqual((r["piezas"], r["al_piso"], r["en_caja"]), (16, 8, 8))
        self.assertTrue(r["caja_codigo"].startswith("A-"))
        self.assertEqual(self._contenido(v0.id), 8)
        self.assertEqual(self._contenido(v1.id), 0)
        self.s.refresh(v0)
        self.assertEqual(v0.stock_actual, 22)
        caja = self.s.get(BodegaCaja, r["caja_id"])
        self.assertEqual(caja.ubicacion.rack, "ALMACEN")   # la caja nueva nace en el almacén
        self.assertEqual(caja.notas, "Maquilador 13/09")

    def test_a_una_caja_que_ya_existe(self) -> None:
        v0 = self.v[0]
        r1 = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 5, "a_caja": 5}], quien_code="VEND-1", caja_nueva=True)
        r2 = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 3, "a_caja": 3}], quien_code="VEND-1", caja_id=r1["caja_id"])
        self.assertEqual(r1["caja_id"], r2["caja_id"])
        self.assertEqual(self._contenido(v0.id), 8)
        self.assertEqual(len(self.s.scalars(select(BodegaCaja)).all()), 1)

    def test_no_se_guarda_mas_de_lo_que_llego(self) -> None:
        with self.assertRaises(ValueError):
            bm.llego_mercancia(self.s, items=[{"variante_id": self.v[0].id, "cantidad": 2, "a_caja": 5}], quien_code="VEND-1", caja_nueva=True)

    def test_solo_el_dueno(self) -> None:
        with self.assertRaises(bm.SoloElDueno):
            bm.llego_mercancia(self.s, items=[{"variante_id": self.v[0].id, "cantidad": 1}], quien_code="VEND-4", caja_nueva=True)
        with self.assertRaises(bm.SoloElDueno):
            bm.pasar_al_piso(self.s, caja_id=1, items=[], quien_code="ENC-1")

    def test_sin_piezas_no_abre_caja(self) -> None:
        with self.assertRaises(ValueError):
            bm.llego_mercancia(self.s, items=[{"variante_id": self.v[0].id, "cantidad": 0}], quien_code="VEND-1", caja_nueva=True)
        self.assertEqual(self.s.scalars(select(BodegaCaja)).all(), [])

    # --- pasar al piso -----------------------------------------------------------
    def test_pasar_al_piso_baja_la_caja_y_no_el_total(self) -> None:
        v0 = self.v[0]
        r = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 12, "a_caja": 12}], quien_code="VEND-1", caja_nueva=True)
        out = bm.pasar_al_piso(self.s, caja_id=r["caja_id"], items=[{"variante_id": v0.id, "cantidad": 5}], quien_code="VEND-1")
        self.s.commit()
        self.s.refresh(v0)
        self.assertEqual((out["piezas"], out["quedan"]), (5, 7))
        self.assertEqual(v0.stock_actual, 22)          # el total no cambia
        self.assertEqual(self._contenido(v0.id), 7)
        self.assertEqual(self.s.get(BodegaCaja, r["caja_id"]).estado, "ACTIVA")

    def test_vaciar_la_caja_la_marca_vacia(self) -> None:
        v0 = self.v[0]
        r = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 4, "a_caja": 4}], quien_code="VEND-1", caja_nueva=True)
        out = bm.pasar_al_piso(self.s, caja_id=r["caja_id"], items=[{"variante_id": v0.id, "cantidad": 4}], quien_code="VEND-1")
        self.assertEqual(out["quedan"], 0)
        self.assertEqual(self.s.get(BodegaCaja, r["caja_id"]).estado, "VACIA")
        self.assertEqual([c["id"] for c in bm.cajas_activas(self.s)], [])

    def test_no_se_puede_sacar_mas_de_lo_que_hay(self) -> None:
        v0 = self.v[0]
        r = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 4, "a_caja": 4}], quien_code="VEND-1", caja_nueva=True)
        with self.assertRaises(ValueError):
            bm.pasar_al_piso(self.s, caja_id=r["caja_id"], items=[{"variante_id": v0.id, "cantidad": 9}], quien_code="VEND-1")

    # --- lecturas ----------------------------------------------------------------
    def test_cajas_y_contenido(self) -> None:
        v0, v1 = self.v[0], self.v[1]
        r = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 4, "a_caja": 4}, {"variante_id": v1.id, "cantidad": 2, "a_caja": 2}], quien_code="VEND-1", caja_nueva=True)
        cajas = bm.cajas_activas(self.s)
        self.assertEqual(len(cajas), 1)
        self.assertEqual((cajas[0]["codigo"], cajas[0]["ubicacion"], cajas[0]["piezas"], cajas[0]["tallas"]), (r["caja_codigo"], "ALMACEN-N1", 6, 2))
        contenido = bm.contenido_de_caja(self.s, r["caja_id"])
        self.assertEqual([(c["talla"], c["cantidad"]) for c in contenido], [("6", 4), ("8", 2)])
        self.assertIn("Prenda 0", contenido[0]["producto"])

    def test_buscar_prendas_trae_tallas_y_lo_que_pediste(self) -> None:
        v0 = self.v[0]
        bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 3, "a_caja": 3}], quien_code="VEND-1", caja_nueva=True)
        self.s.add(ConteoInventario(
            variante_id=v0.id, escuela_id=self.escuela.id, stock_sistema=0, stock_fisico=1, diferencia=1,
            contado_por="x", contado_at=datetime.now() - timedelta(days=3), pedido=12, pedido_sugerido=10,
            pedido_decidido_at=datetime.now() - timedelta(days=3),
        ))
        self.s.commit()
        prendas = bm.buscar_prendas(self.s, "prenda 0")
        self.assertEqual(len(prendas), 1)
        p = prendas[0]
        self.assertEqual(p["escuela"], "Uno")
        t6 = next(t for t in p["tallas"] if t["talla"] == "6")
        self.assertEqual((t6["a_la_mano"], t6["en_cajas"], t6["pedido"]), (10, 3, 12))
        t8 = next(t for t in p["tallas"] if t["talla"] == "8")
        self.assertEqual((t8["en_cajas"], t8["pedido"]), (0, None))
        self.assertEqual(bm.buscar_prendas(self.s, "x"), [])          # muy corto
        self.assertEqual(bm.buscar_prendas(self.s, "prenda zzz"), [])  # varias palabras, todas deben estar
        self.assertEqual(len(bm.buscar_prendas(self.s, "prenda")), 2)

    def test_buscar_prendas_sigue_las_reglas_de_la_hoja(self) -> None:
        # Sin Pants 3pz ni Chamarra (se arman, no llegan), orden por tipo de pieza y tallas de chica a grande.
        from pos_uniformes.database.models import Categoria, Marca, Producto, TipoPieza

        cat = self.s.scalar(select(Categoria)); marca = self.s.scalar(select(Marca))
        tipos = {n: TipoPieza(nombre=n) for n in ("Pants 3pz", "Chamarra", "Playera", "Pants 2pz")}
        self.s.add_all(tipos.values()); self.s.flush()
        for n, tallas in (("Pants 3pz", ["6"]), ("Chamarra", ["6"]), ("Playera", ["12", "4", "CH"]), ("Pants 2pz", ["8"])):
            prod = Producto(nombre=f"{n} Conalep", nombre_base=n, categoria_id=cat.id, marca_id=marca.id,
                            escuela_id=self.escuela.id, tipo_pieza_id=tipos[n].id)
            self.s.add(prod); self.s.flush()
            for i, t in enumerate(tallas):
                self.s.add(Variante(producto_id=prod.id, sku=f"C-{n[:3]}-{t}", talla=t, color="", precio_venta=100, stock_actual=1))
        self.s.commit()
        prendas = bm.buscar_prendas(self.s, "conalep")
        self.assertEqual([p["tipo_pieza"] for p in prendas], ["Pants 2pz", "Playera"])   # 3pz y Chamarra fuera; orden de la hoja
        playera = next(p for p in prendas if p["tipo_pieza"] == "Playera")
        self.assertEqual([t["talla"] for t in playera["tallas"]], ["4", "12", "CH"])

    # --- corregir caja -----------------------------------------------------------
    def test_corregir_caja_cambia_solo_la_caja(self) -> None:
        from pos_uniformes.database.models import BodegaMovimiento

        v0, v1 = self.v[0], self.v[1]
        r = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 8, "a_caja": 8}, {"variante_id": v1.id, "cantidad": 3, "a_caja": 3}], quien_code="VEND-1", caja_nueva=True)
        out = bm.corregir_caja(self.s, caja_id=r["caja_id"], items=[
            {"variante_id": v0.id, "cantidad": 5},      # había 8, hay 5
            {"variante_id": v1.id, "cantidad": 3},      # igual: no es cambio
        ], quien_code="VEND-1", quien="Daniel")
        self.s.commit()
        self.assertEqual((out["cambios"], out["quedan"]), (1, 8))
        self.assertEqual(self._contenido(v0.id), 5)
        self.s.refresh(v0)
        self.assertEqual(v0.stock_actual, 18)   # el total no se toca (10 + 8 que llegaron)
        ajustes = [m for m in self.s.scalars(select(BodegaMovimiento)).all() if m.tipo == "AJUSTE"]
        self.assertEqual(len(ajustes), 1)
        self.assertEqual((ajustes[0].cantidad, ajustes[0].observacion), (-3, "Recuento: de 8 a 5"))
        self.assertIn("VEND-1", ajustes[0].creado_por)

    def test_corregir_a_cero_vacia_la_caja_y_en_blanco_no_toca(self) -> None:
        v0, v1 = self.v[0], self.v[1]
        r = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 4, "a_caja": 4}, {"variante_id": v1.id, "cantidad": 2, "a_caja": 2}], quien_code="VEND-1", caja_nueva=True)
        out = bm.corregir_caja(self.s, caja_id=r["caja_id"], items=[{"variante_id": v0.id, "cantidad": 0}, {"variante_id": v1.id, "cantidad": ""}], quien_code="VEND-1")
        self.assertEqual((out["cambios"], out["quedan"]), (1, 2))
        self.assertEqual(self._contenido(v1.id), 2)   # en blanco = no la revisé
        out = bm.corregir_caja(self.s, caja_id=r["caja_id"], items=[{"variante_id": v1.id, "cantidad": 0}], quien_code="VEND-1")
        self.assertEqual(out["quedan"], 0)
        self.assertEqual(self.s.get(BodegaCaja, r["caja_id"]).estado, "VACIA")

    def test_si_la_caja_tiene_mas_que_el_total_el_total_sube(self) -> None:
        from pos_uniformes.database.models import MovimientoInventario

        v0 = self.v[0]   # stock_actual 10, nada en cajas
        r = bm.llego_mercancia(self.s, items=[{"variante_id": v0.id, "cantidad": 1, "a_caja": 1}], quien_code="VEND-1", caja_nueva=True)
        bm.corregir_caja(self.s, caja_id=r["caja_id"], items=[{"variante_id": v0.id, "cantidad": 15}], quien_code="VEND-1")
        self.s.refresh(v0)
        self.assertEqual(self._contenido(v0.id), 15)
        self.assertEqual(v0.stock_actual, 15)   # 11 → 15 para no dejar "a la mano" negativo
        tipos = [m.tipo_movimiento.value for m in self.s.scalars(select(MovimientoInventario)).all()]
        self.assertIn("AJUSTE_ENTRADA", tipos)

    def test_corregir_solo_el_dueno(self) -> None:
        with self.assertRaises(bm.SoloElDueno):
            bm.corregir_caja(self.s, caja_id=1, items=[], quien_code="VEND-4")


if __name__ == "__main__":
    unittest.main()
