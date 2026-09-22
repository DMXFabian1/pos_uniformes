"""El arreglo de catálogo de las dos Álvaro Obregón (nota 40).

Lo delicado no es mover datos, es **cuándo no moverlos**: desactivar una prenda
que sí se vendió, o fundir dos fichas y quedarse con un número inventado.
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConjuntoComponente,
    Escuela,
    Marca,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    TipoPieza,
    TipoPrenda,
    Variante,
)
from pos_uniformes.scripts import arreglar_alvaro_obregon as arr


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="G")
        self.prenda = TipoPrenda(nombre="Deportivo")
        self.esc = Escuela(nombre="Álvaro Obregón")
        self.s.add_all([self.cat, self.marca, self.prenda, self.esc])
        self.piezas = {n: TipoPieza(nombre=n) for n in ("Pants 2pz", "Pants 3pz", "Playera", "Chamarra", "Pants Suelto")}
        self.s.add_all(list(self.piezas.values()))
        self.s.flush()

    def _prod(self, nombre, pieza, tallas):
        p = Producto(
            nombre=nombre, nombre_base=nombre,
            categoria_id=self.cat.id, marca_id=self.marca.id,
            escuela_id=self.esc.id, tipo_prenda_id=self.prenda.id,
            tipo_pieza_id=self.piezas[pieza].id,
        )
        self.s.add(p)
        self.s.flush()
        for t, stock in tallas.items():
            self.s.add(Variante(producto_id=p.id, sku=f"{p.id}-{t}", talla=t, color="AM",
                                precio_venta=100, stock_actual=stock))
        self.s.flush()
        return p


class PreescolarTest(_Base):
    def _armar(self, *, ventas: int, existencia: int):
        pants = self._prod("Pants 2pz Deportivo Álvaro Obregón", "Pants 2pz", {"4": 3})
        tres = self._prod(arr.TRES_PZ_PREESCOLAR, "Pants 3pz", {"4": existencia})
        self.s.add(ConjuntoComponente(conjunto_id=tres.id, componente_id=pants.id, cantidad=1, grupo=0))
        self.s.flush()
        if ventas:
            v = self.s.scalars(select(Variante).where(Variante.producto_id == tres.id)).first()
            for _ in range(ventas):
                self.s.add(MovimientoInventario(
                    variante_id=v.id, tipo_movimiento=TipoMovimientoInventario.SALIDA_VENTA,
                    cantidad=-1, stock_anterior=0, stock_posterior=0, creado_por="TEST",
                ))
            self.s.flush()
        return tres

    def test_sin_ventas_ni_existencia_se_desactiva(self):
        tres = self._armar(ventas=0, existencia=0)
        arr.paso_preescolar(self.s, aplicar=True)
        self.assertFalse(tres.activo)
        self.assertEqual(arr.conjunto_service.receta_de(self.s, tres.id), [])

    def test_si_alguna_vez_se_vendio_NO_se_desactiva(self):
        """Borrar del catálogo algo que tuvo historia es lo caro de deshacer."""
        tres = self._armar(ventas=2, existencia=0)
        arr.paso_preescolar(self.s, aplicar=True)
        self.assertTrue(tres.activo, "tiene historia: se queda")
        self.assertEqual(arr.conjunto_service.receta_de(self.s, tres.id), [], "pero sin receta muerta")

    def test_si_tiene_existencia_NO_se_desactiva(self):
        tres = self._armar(ventas=0, existencia=5)
        arr.paso_preescolar(self.s, aplicar=True)
        self.assertTrue(tres.activo)

    def test_en_seco_no_toca_nada(self):
        tres = self._armar(ventas=0, existencia=0)
        arr.paso_preescolar(self.s, aplicar=False)
        self.assertTrue(tres.activo)
        self.assertNotEqual(arr.conjunto_service.receta_de(self.s, tres.id), [])


class ChamarrasTest(_Base):
    def test_al_fundir_las_tallas_quedan_como_nunca_contadas(self):
        """Sumar dos fichas duplicadas puede contar dos veces lo mismo: que el
        número se marque para contar en vez de darse por bueno."""
        from datetime import datetime, timezone

        queda = self._prod(arr.CHAMARRA_QUE_SE_QUEDA, "Chamarra", {"4": 10})
        self._prod(arr.CHAMARRA_QUE_SE_VA, "Chamarra", {"4": 10})
        v = self.s.scalars(select(Variante).where(Variante.producto_id == queda.id)).one()
        v.ultimo_conteo_at = datetime.now(timezone.utc)
        self.s.flush()

        arr.paso_chamarras(self.s, aplicar=True)
        self.assertEqual(v.stock_actual, 20, "las dos existencias se juntan")
        self.assertIsNone(v.ultimo_conteo_at, "y queda pidiendo que la cuenten")

    def test_si_ya_no_estan_las_dos_no_hace_nada(self):
        self._prod(arr.CHAMARRA_QUE_SE_QUEDA, "Chamarra", {"4": 10})
        lineas = arr.paso_chamarras(self.s, aplicar=True)
        self.assertIn("nada que fundir", " ".join(lineas))


if __name__ == "__main__":
    unittest.main()
