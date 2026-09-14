"""La venta del kiosko descuenta stock (2026-09-14): amarrada al id de la
Libreta, puede dejar negativo, nunca tumba la venta, y borrar la regresa."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta, MovimientoInventario, Variante
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.tests.test_conteo_jornada_service import _seed


class DescuentaStockTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        _seed(self.s, "Uno", stock=3)   # 2 prendas × tallas 6 y 8, stock 3
        self.s.commit()
        self.v = list(self.s.scalars(select(Variante).order_by(Variante.id)).all())

    def tearDown(self) -> None:
        self.s.close()

    def _venta(self, items, tipo="venta"):
        e = lib.registrar_operacion(
            self.s, employee_code="VEND-4", employee_name="Stayce", tipo=tipo, items=items,
            monto_total=Decimal("100.00"),
        )
        self.s.commit()
        return e

    def _stock(self, v) -> int:
        self.s.refresh(v)
        return v.stock_actual

    def test_la_venta_baja_el_stock_de_cada_talla(self) -> None:
        v0, v1 = self.v[0], self.v[1]
        e = self._venta([
            {"sku": v0.sku, "nombre": "x", "talla": "6", "cantidad": 2, "precio": "50"},
            {"sku": v1.sku, "nombre": "x", "talla": "8", "cantidad": 1, "precio": "50"},
        ])
        self.assertEqual((self._stock(v0), self._stock(v1)), (1, 2))
        movs = list(self.s.scalars(select(MovimientoInventario).order_by(MovimientoInventario.id)).all())
        self.assertEqual([(m.tipo_movimiento.value, m.cantidad, m.referencia) for m in movs],
                         [("SALIDA_VENTA", -2, f"libreta:{e.id}"), ("SALIDA_VENTA", -1, f"libreta:{e.id}")])
        self.assertEqual(movs[0].creado_por, "VEND-4")

    def test_puede_quedar_negativo(self) -> None:
        v0 = self.v[0]
        self._venta([{"sku": v0.sku, "cantidad": 5, "precio": "50"}])
        self.assertEqual(self._stock(v0), -2)   # la lista de qué recontar

    def test_no_descuenta_dos_veces(self) -> None:
        v0 = self.v[0]
        e = self._venta([{"sku": v0.sku, "cantidad": 1, "precio": "50"}])
        self.assertEqual(lib.descontar_stock(self.s, e), 0)   # ya estaba
        self.assertEqual(self._stock(v0), 2)

    def test_apartado_descuenta_y_abono_no(self) -> None:
        v0 = self.v[0]
        self._venta([{"sku": v0.sku, "cantidad": 1, "precio": "50"}], tipo="apartado")
        self.assertEqual(self._stock(v0), 2)
        self.assertEqual(self.s.scalars(select(MovimientoInventario)).one().tipo_movimiento.value, "APARTADO_RESERVA")
        lib.registrar_operacion(self.s, employee_code="VEND-4", employee_name="", tipo="abono",
                                items=[{"sku": v0.sku, "cantidad": 1, "precio": "50"}], monto_total=Decimal("50"), comisiones=0)
        self.s.commit()
        self.assertEqual(self._stock(v0), 2)

    def test_sku_desconocido_o_sin_codigo_se_ignora(self) -> None:
        e = self._venta([{"sku": "NOEXISTE", "cantidad": 1, "precio": "50"}, {"sku": "", "nombre": "Sin código", "cantidad": 1, "precio": "50"}])
        self.assertIsNotNone(e.id)
        self.assertEqual(self.s.scalars(select(MovimientoInventario)).all(), [])

    def test_si_el_descuento_falla_la_venta_se_guarda_igual(self) -> None:
        v0 = self.v[0]
        with patch("pos_uniformes.services.inventario_service.InventarioService.registrar_movimiento", side_effect=RuntimeError("base rara")):
            e = self._venta([{"sku": v0.sku, "cantidad": 1, "precio": "50"}])
        self.assertIsNotNone(self.s.get(LibretaVenta, e.id))
        self.assertEqual(self._stock(v0), 3)

    def test_borrar_la_operacion_regresa_el_stock(self) -> None:
        v0 = self.v[0]
        e = self._venta([{"sku": v0.sku, "cantidad": 2, "precio": "50"}])
        self.assertEqual(self._stock(v0), 1)
        self.assertTrue(lib.eliminar_operacion(self.s, e.id))
        self.s.commit()
        self.assertEqual(self._stock(v0), 3)
        tipos = [m.tipo_movimiento.value for m in self.s.scalars(select(MovimientoInventario)).all()]
        self.assertEqual(tipos, ["SALIDA_VENTA", "CANCELACION_VENTA"])


if __name__ == "__main__":
    unittest.main()
