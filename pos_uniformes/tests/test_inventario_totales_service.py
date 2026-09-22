"""Los totales del inventario tienen una sola definición.

Cada test fija una de las reglas que antes vivían sueltas en el SQL del
generador del panel: qué es tienda, qué es de escuela, qué es bajo mínimo y
qué no se suma por venir contado en otra pieza.
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    BodegaUbicacion,
    Categoria,
    CatalogSchoolProductLink,
    ConjuntoComponente,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    TipoPieza,
    TipoPrenda,
    Variante,
)
from pos_uniformes.services import inventario_totales_service as its


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="G")
        self.prenda = TipoPrenda(nombre="Deportivo")
        self.s.add_all([self.cat, self.marca, self.prenda])
        self.nivel = NivelEducativo(nombre="Primaria")
        self.nivel2 = NivelEducativo(nombre="Secundaria")
        self.esc = Escuela(nombre="Justo Sierra")
        self.s.add_all([self.nivel, self.nivel2, self.esc])
        self.piezas = {n: TipoPieza(nombre=n) for n in ("Pants 2pz", "Pants 3pz", "Playera")}
        self.s.add_all(list(self.piezas.values()))
        self.s.flush()

    def _prod(self, nombre, pieza="Pants 2pz", *, escuela=True, nivel=None, activo=True):
        p = Producto(
            nombre=nombre,
            nombre_base=nombre,
            categoria_id=self.cat.id,
            marca_id=self.marca.id,
            escuela_id=self.esc.id if escuela else None,
            nivel_educativo_id=(nivel or self.nivel).id,
            tipo_prenda_id=self.prenda.id,
            tipo_pieza_id=self.piezas[pieza].id,
            activo=activo,
        )
        self.s.add(p)
        self.s.flush()
        return p

    def _var(self, producto, talla="10", *, stock=0, precio=100, minimo=None, activo=True):
        v = Variante(
            producto_id=producto.id,
            sku=f"{producto.id}-{talla}",
            talla=talla,
            color="Rojo",
            precio_venta=precio,
            stock_actual=stock,
            stock_minimo=minimo,
            activo=activo,
        )
        self.s.add(v)
        self.s.flush()
        return v

    def _guardar(self, variante, cantidad, *, rack="A"):
        """Mete `cantidad` de esa talla en una caja del rack dado."""
        ubi = BodegaUbicacion(codigo=f"{rack}-1-{variante.id}", rack=rack, nivel=1)
        self.s.add(ubi)
        self.s.flush()
        caja = BodegaCaja(codigo=f"C{variante.id}-{rack}", ubicacion_id=ubi.id)
        self.s.add(caja)
        self.s.flush()
        self.s.add(BodegaContenido(caja_id=caja.id, variante_id=variante.id, cantidad=cantidad))
        self.s.flush()

    def totales(self):
        return its.totales_inventario(self.s)


class TotalesInventarioTest(_Base):
    def test_sin_bodega_todo_es_tienda(self):
        self._var(self._prod("Pants JS"), stock=7)
        t = self.totales()
        self.assertEqual(t.stock_total, 7)
        self.assertEqual(t.stock_tienda, 7)
        self.assertEqual(t.stock_bodega, 0)
        self.assertEqual(t.stock_piso, 0)

    def test_lo_guardado_se_resta_de_la_tienda(self):
        v = self._var(self._prod("Pants JS"), stock=10)
        self._guardar(v, 3, rack="A")      # en caja, bodega
        self._guardar(v, 2, rack="piso")   # a la mano, piso (y en minúsculas)
        t = self.totales()
        self.assertEqual(t.stock_total, 10)
        self.assertEqual(t.stock_bodega, 3)
        self.assertEqual(t.stock_piso, 2)
        self.assertEqual(t.stock_tienda, 5)

    def test_el_conjunto_no_se_suma_dos_veces(self):
        p2 = self._prod("Pants 2pz JS", "Pants 2pz")
        play = self._prod("Playera JS", "Playera")
        p3 = self._prod("Pants 3pz JS", "Pants 3pz")
        self._var(p2, stock=5, precio=200)
        self._var(play, stock=5, precio=100)
        self._var(p3, stock=5, precio=300)
        sin_receta = self.totales()
        self.assertEqual(sin_receta.stock_total, 15)

        self.s.add_all([
            ConjuntoComponente(conjunto_id=p3.id, componente_id=p2.id, cantidad=1, grupo=0),
            ConjuntoComponente(conjunto_id=p3.id, componente_id=play.id, cantidad=1, grupo=1),
        ])
        self.s.flush()
        con_receta = self.totales()
        self.assertEqual(con_receta.stock_total, 10, "el 3pz ya está contado en sus piezas")
        self.assertEqual(con_receta.valor_inventario, 1500.0)

    def test_basico_ligado_cuenta_como_de_escuela(self):
        general = self._prod("Pants Liso Rojo", escuela=False)
        self._var(general, stock=4)
        self.assertEqual(self.totales().variantes_con_escuela, 0)

        self.s.add(CatalogSchoolProductLink(escuela_id=self.esc.id, producto_id=general.id))
        self.s.flush()
        self.assertEqual(self.totales().variantes_con_escuela, 1)

    def test_liga_apagada_no_cuenta(self):
        general = self._prod("Pants Liso Rojo", escuela=False)
        self._var(general, stock=4)
        self.s.add(
            CatalogSchoolProductLink(escuela_id=self.esc.id, producto_id=general.id, activo=False)
        )
        self.s.flush()
        self.assertEqual(self.totales().variantes_con_escuela, 0)

    def test_agotada_se_mide_contra_tienda_no_contra_el_total(self):
        v = self._var(self._prod("Pants JS"), stock=6)
        self._guardar(v, 6, rack="A")  # todo en cajas: en el mostrador no hay nada
        t = self.totales()
        self.assertEqual(t.stock_total, 6)
        self.assertEqual(t.variantes_sin_stock, 1, "tener cajas no es tener en tienda")

    def test_bajo_minimo_usa_el_minimo_de_la_talla_o_el_default(self):
        p = self._prod("Pants JS")
        self._var(p, "10", stock=1)              # sin mínimo → default 2 → bajo
        self._var(p, "12", stock=3, minimo=5)    # su mínimo es 5 → bajo
        self._var(p, "14", stock=3)              # default 2 → sano
        self._var(p, "16", stock=0)              # agotada, no "bajo"
        t = self.totales()
        self.assertEqual(t.variantes_bajo_minimo, 2)
        self.assertEqual(t.variantes_sin_stock, 1)

    def test_inactivos_fuera(self):
        p = self._prod("Pants JS")
        self._var(p, "10", stock=5)
        self._var(p, "12", stock=5, activo=False)
        muerto = self._prod("Pants Viejo", activo=False)
        self._var(muerto, "10", stock=99)
        self.assertEqual(self.totales().stock_total, 5)

    def test_valor_inventario_usa_el_total_no_solo_la_tienda(self):
        v = self._var(self._prod("Pants JS"), stock=10, precio=250)
        self._guardar(v, 4, rack="A")
        self.assertEqual(self.totales().valor_inventario, 2500.0)


class ValorPorNivelTest(_Base):
    def test_agrupa_por_nivel_y_excluye_conjuntos_y_generales(self):
        p2 = self._prod("Pants 2pz JS", "Pants 2pz")
        p3 = self._prod("Pants 3pz JS", "Pants 3pz")
        sec = self._prod("Playera Sec", "Playera", nivel=self.nivel2)
        general = self._prod("Pants Liso", escuela=False)
        self._var(p2, stock=2, precio=100)
        self._var(p3, stock=2, precio=300)
        self._var(sec, stock=1, precio=50)
        self._var(general, stock=9, precio=999)
        self.s.add(ConjuntoComponente(conjunto_id=p3.id, componente_id=p2.id, cantidad=1, grupo=0))
        self.s.flush()

        valores = its.valor_por_nivel(self.s)
        self.assertEqual(valores, {"Primaria": 200.0, "Secundaria": 50.0})


class GeneradorNoEscribeSQLTest(unittest.TestCase):
    """El panel pregunta, no calcula.

    Si alguien vuelve a pegar estas reglas a mano en el generador, el desfase
    regresa en silencio: el POS cambia su definición y el panel se queda con la
    vieja. Que truene aquí es más barato que descubrirlo en la tienda."""

    def setUp(self) -> None:
        from pathlib import Path

        ruta = Path(__file__).resolve().parent.parent / "scripts" / "generar_panel_uniformes.py"
        self.fuente = ruta.read_text(encoding="utf-8")

    def test_no_repite_la_regla_de_los_conjuntos(self):
        self.assertNotIn(
            "conjunto_componente",
            self.fuente,
            "la regla vive en conjunto_service.filtro_sin_conjuntos",
        )

    def test_no_repite_la_suma_de_piso_y_bodega(self):
        # Ojo: el generador todavía trae piso y bodega **por talla** para
        # Tarifarios y Disponibilidad; eso se resuelve cuando les toque su paso.
        # Lo que aquí se cuida es la **suma** de los totales, que ya tiene dueño.
        self.assertNotIn(
            "bodega_stock",
            self.fuente,
            "la suma vive en inventario_totales_service.subconsulta_bodega",
        )

    def test_pide_los_totales_al_servicio(self):
        self.assertIn("inventario_totales_service.totales_inventario", self.fuente)
        self.assertIn("inventario_totales_service.valor_por_nivel", self.fuente)


if __name__ == "__main__":
    unittest.main()
