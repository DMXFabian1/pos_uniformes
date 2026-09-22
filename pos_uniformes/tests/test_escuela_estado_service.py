"""Todo de una escuela en una sola pregunta.

Este servicio no calcula: junta lo que ya saben el mapa de conteos, los
pedidos decididos, los movimientos y la demanda no atendida. Los tests cuidan
que junte **lo de esa escuela** y que lo más urgente se diga primero.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    CatalogSchoolProductLink,
    ConteoInventario,
    DemandaNoAtendida,
    Escuela,
    Marca,
    MovimientoInventario,
    NivelEducativo,
    Producto,
    TipoMovimientoInventario,
    TipoPieza,
    TipoPrenda,
    Variante,
)
from pos_uniformes.services import escuela_estado_service as ee


def _hace(dias: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=dias)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="G")
        self.prenda = TipoPrenda(nombre="Deportivo")
        self.primaria = NivelEducativo(nombre="Primaria")
        self.s.add_all([self.cat, self.marca, self.prenda, self.primaria])
        self.piezas = {n: TipoPieza(nombre=n) for n in ("Playera", "Pants 2pz", "Calceta")}
        self.s.add_all(list(self.piezas.values()))
        self.esc = Escuela(nombre="Justo Sierra")
        self.otra = Escuela(nombre="Frida Kahlo")
        self.s.add_all([self.esc, self.otra])
        self.s.flush()

    def _prod(self, nombre, pieza="Playera", *, escuela=None):
        p = Producto(
            nombre=nombre, nombre_base=nombre,
            categoria_id=self.cat.id, marca_id=self.marca.id,
            escuela_id=escuela.id if escuela else None,
            nivel_educativo_id=self.primaria.id,
            tipo_prenda_id=self.prenda.id, tipo_pieza_id=self.piezas[pieza].id,
        )
        self.s.add(p)
        self.s.flush()
        return p

    def _var(self, producto, talla, stock=0):
        v = Variante(
            producto_id=producto.id, sku=f"SKU{producto.id}{talla}", talla=talla,
            color="Rojo", precio_venta=100, stock_actual=stock,
        )
        self.s.add(v)
        self.s.flush()
        return v

    def _vender(self, variante, piezas, *, hace_dias=1):
        self.s.add(MovimientoInventario(
            variante_id=variante.id,
            tipo_movimiento=TipoMovimientoInventario.SALIDA_VENTA,
            cantidad=-piezas, stock_anterior=0, stock_posterior=-piezas,
            created_at=_hace(hace_dias), creado_por="TEST",
        ))
        self.s.flush()

    def estado(self, escuela=None, **kw):
        return ee.estado_de(self.s, (escuela or self.esc).id, **kw)


class QueSeVendioTest(_Base):
    def test_suma_solo_las_salidas_por_venta_de_esta_escuela(self):
        mia = self._var(self._prod("Playera JS", escuela=self.esc), "10")
        ajena = self._var(self._prod("Playera FK", escuela=self.otra), "10")
        self._vender(mia, 3)
        self._vender(mia, 2)
        self._vender(ajena, 9)
        self.assertEqual(self.estado().vendido_piezas, 5)

    def test_lo_viejo_queda_fuera_de_la_ventana(self):
        v = self._var(self._prod("Playera JS", escuela=self.esc), "10")
        self._vender(v, 4, hace_dias=2)
        self._vender(v, 7, hace_dias=90)
        self.assertEqual(self.estado().vendido_piezas, 4)
        self.assertEqual(self.estado(dias=365).vendido_piezas, 11)

    def test_la_general_ligada_cuenta_como_de_la_escuela(self):
        # La escuela tiene lo suyo (de ahí sale su nivel) y además lleva una
        # prenda general: un básico liso que le sirve igual.
        propia = self._var(self._prod("Playera JS", escuela=self.esc), "10")
        self._vender(propia, 2)
        general = self._prod("Calceta Blanca", "Calceta")
        v = self._var(general, "6-8")
        self._vender(v, 6)
        self.assertEqual(self.estado().vendido_piezas, 2, "todavía no la lleva")

        self.s.add(CatalogSchoolProductLink(escuela_id=self.esc.id, producto_id=general.id))
        self.s.flush()
        self.assertEqual(self.estado().vendido_piezas, 8)

    def test_una_escuela_sin_prendas_propias_no_hereda_generales(self):
        """Límite heredado del reparto: los niveles de una escuela salen de sus
        propias prendas, así que una que solo llevara generales no tendría de
        dónde colgarlas. En la tienda no pasa — toda escuela tiene lo suyo —
        pero queda escrito para que no sorprenda."""
        general = self._prod("Calceta Blanca", "Calceta")
        self._vender(self._var(general, "6-8"), 6)
        self.s.add(CatalogSchoolProductLink(escuela_id=self.esc.id, producto_id=general.id))
        self.s.flush()
        self.assertEqual(self.estado().vendido_piezas, 0)


class QueSePidioTest(_Base):
    def _conteo(self, variante, *, pedido, hace_dias=1):
        self.s.add(ConteoInventario(
            variante_id=variante.id, escuela_id=self.esc.id,
            stock_sistema=0, stock_fisico=0, diferencia=0,
            pedido=pedido, pedido_decidido_at=_hace(hace_dias), contado_por="TEST",
        ))
        self.s.flush()

    def test_trae_lo_que_se_decidio_pedir(self):
        v = self._var(self._prod("Pants JS", "Pants 2pz", escuela=self.esc), "14")
        self._conteo(v, pedido=6)
        pedido = self.estado().pedido
        self.assertEqual(len(pedido), 1)
        self.assertEqual((pedido[0].prenda, pedido[0].talla, pedido[0].cuantas), ("Pants JS", "14", 6))

    def test_decidir_no_pedir_nada_no_es_un_pedido(self):
        v = self._var(self._prod("Pants JS", "Pants 2pz", escuela=self.esc), "14")
        self._conteo(v, pedido=0)
        self.assertEqual(self.estado().pedido, [], "cero es una decisión, no un pedido")


class LoQuePidieronYNoHabiaTest(_Base):
    def test_se_amarra_por_sku_y_solo_el_de_esta_escuela(self):
        mia = self._var(self._prod("Playera JS", escuela=self.esc), "10")
        ajena = self._var(self._prod("Playera FK", escuela=self.otra), "10")
        for sku, veces in ((mia.sku, 3), (ajena.sku, 5)):
            for _ in range(veces):
                self.s.add(DemandaNoAtendida(
                    tipo="TALLA_AGOTADA", sku=sku, producto="Playera", talla="10",
                    piezas=1, created_at=_hace(2),
                ))
        self.s.flush()
        faltas = self.estado().faltas_sentidas
        self.assertEqual(len(faltas), 1)
        self.assertEqual(faltas[0].veces, 3)


class TitularTest(_Base):
    def test_lo_rojo_se_dice_antes_que_nada(self):
        p = self._prod("Calceta Blanca", "Calceta", escuela=self.esc)
        self._var(p, "6-8", stock=-2)
        self.assertEqual(self.estado().titular, "una talla en rojo: se vendió sin contar")

    def test_sin_contar_lo_dice(self):
        p = self._prod("Playera JS", escuela=self.esc)
        self._var(p, "10", stock=4)
        self.assertEqual(self.estado().titular, "nunca se ha contado")


class EscuelaQueNoExisteTest(_Base):
    def test_avisa_en_vez_de_devolver_vacio(self):
        with self.assertRaises(ValueError):
            ee.estado_de(self.s, 9999)


if __name__ == "__main__":
    unittest.main()
