"""Cambiar el precio de una prenda desde la consola.

Lo delicado es lo que NO debe pasar: tocar otra prenda parecida, mover tallas
que no se pidieron, o cambiar algo en seco.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria, Escuela, Marca, Producto, TipoPieza, TipoPrenda, Variante,
)
from pos_uniformes.scripts import cambiar_precio as cp


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="G")
        self.prenda = TipoPrenda(nombre="Deportivo")
        self.pieza = TipoPieza(nombre="Pants 3pz")
        self.esc = Escuela(nombre="UVEG")
        self.s.add_all([self.cat, self.marca, self.prenda, self.pieza, self.esc])
        self.s.flush()

    def _prod(self, nombre, tallas=("CH", "MD"), precio=790, activo=True):
        p = Producto(
            nombre=nombre, nombre_base=nombre, categoria_id=self.cat.id, marca_id=self.marca.id,
            escuela_id=self.esc.id, tipo_prenda_id=self.prenda.id, tipo_pieza_id=self.pieza.id,
            activo=activo,
        )
        self.s.add(p)
        self.s.flush()
        for t in tallas:
            self.s.add(Variante(producto_id=p.id, sku=f"{p.id}-{t}", talla=t, color="AM",
                                precio_venta=precio, stock_actual=0))
        self.s.flush()
        return p

    def _precios(self, p):
        return {v.talla: Decimal(str(v.precio_venta)) for v in
                self.s.scalars(select(Variante).where(Variante.producto_id == p.id)).all()}


class BuscarTest(_Base):
    def test_encuentra_por_un_pedazo_del_nombre(self):
        self._prod("Pants 3pz Deportivo UVEG")
        self.assertEqual(len(cp.buscar_prendas(self.s, "3pz Deportivo UVEG")), 1)

    def test_no_trae_las_dadas_de_baja(self):
        self._prod("Pants 3pz Deportivo UVEG", activo=False)
        self.assertEqual(cp.buscar_prendas(self.s, "UVEG"), [])


class TallasTest(_Base):
    def test_sin_filtro_trae_todas(self):
        p = self._prod("Pants 3pz Deportivo UVEG", tallas=("CH", "MD", "GD"))
        self.assertEqual(len(cp.tallas_de(self.s, p, None)), 3)

    def test_con_filtro_solo_esas_y_sin_importar_mayusculas(self):
        p = self._prod("Pants 3pz Deportivo UVEG", tallas=("CH", "MD", "GD"))
        vs = cp.tallas_de(self.s, p, {"ch", "gd"})
        self.assertEqual([v.talla for v in vs], ["CH", "GD"])


class MainTest(_Base):
    def _correr(self, *argv):
        from unittest.mock import patch

        class _Ctx:
            def __init__(self, s): self.s = s
            def __enter__(self): return self.s
            def __exit__(self, *a): return False

        with patch.object(cp, "get_session", lambda: _Ctx(self.s)):
            return cp.main(list(argv))

    def test_en_seco_no_cambia_nada(self):
        p = self._prod("Pants 3pz Deportivo UVEG")
        self.assertEqual(self._correr("--prenda", "UVEG", "--precio", "750"), 0)
        self.assertEqual(set(self._precios(p).values()), {Decimal("790")})

    def test_aplicar_cambia_todas_sus_tallas(self):
        p = self._prod("Pants 3pz Deportivo UVEG", tallas=("CH", "MD", "GD"))
        self._correr("--prenda", "UVEG", "--precio", "750", "--aplicar")
        self.assertEqual(set(self._precios(p).values()), {Decimal("750")})

    def test_con_varias_que_empatan_no_toca_nada(self):
        """Mejor quedarse quieto que adivinar cuál era."""
        a = self._prod("Pants 3pz Deportivo UVEG")
        b = self._prod("Pants 2pz Deportivo UVEG")
        self.assertEqual(self._correr("--prenda", "UVEG", "--precio", "750", "--aplicar"), 1)
        for p in (a, b):
            self.assertEqual(set(self._precios(p).values()), {Decimal("790")})

    def test_solo_las_tallas_pedidas(self):
        p = self._prod("Pants 3pz Deportivo UVEG", tallas=("CH", "MD", "GD"))
        self._correr("--prenda", "3pz", "--precio", "750", "--tallas", "CH,GD", "--aplicar")
        self.assertEqual(self._precios(p), {"CH": Decimal("750"), "MD": Decimal("790"), "GD": Decimal("750")})

    def test_un_precio_que_no_es_numero_no_pasa(self):
        p = self._prod("Pants 3pz Deportivo UVEG")
        self.assertEqual(self._correr("--prenda", "UVEG", "--precio", "setecientos", "--aplicar"), 1)
        self.assertEqual(set(self._precios(p).values()), {Decimal("790")})

    def test_negativo_tampoco(self):
        self._prod("Pants 3pz Deportivo UVEG")
        self.assertEqual(self._correr("--prenda", "UVEG", "--precio", "-10", "--aplicar"), 1)


if __name__ == "__main__":
    unittest.main()
