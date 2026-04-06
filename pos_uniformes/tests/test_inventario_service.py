from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.database.models import TipoMovimientoInventario
from pos_uniformes.services.inventario_service import InventarioService


class _SessionStub:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


class InventarioServiceTests(unittest.TestCase):
    def test_registrar_movimiento_still_blocks_negative_stock_by_default(self) -> None:
        session = _SessionStub()
        variante = SimpleNamespace(stock_actual=1)

        with self.assertRaisesRegex(ValueError, "stock negativo"):
            InventarioService.registrar_movimiento(
                session=session,
                variante=variante,
                tipo_movimiento=TipoMovimientoInventario.SALIDA_VENTA,
                cantidad=-2,
            )

    def test_registrar_salida_venta_allows_negative_stock_when_policy_is_disabled(self) -> None:
        session = _SessionStub()
        variante = SimpleNamespace(stock_actual=1)

        with patch(
            "pos_uniformes.services.inventario_service.allow_negative_sale_stock",
            return_value=True,
        ), patch(
            "pos_uniformes.services.inventario_service.MovimientoInventario",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ):
            movimiento = InventarioService.registrar_salida_venta(
                session=session,
                variante=variante,
                cantidad=2,
                referencia="VTA-001",
                creado_por="caja",
            )

        self.assertEqual(variante.stock_actual, -1)
        self.assertEqual(movimiento.stock_anterior, 1)
        self.assertEqual(movimiento.stock_posterior, -1)
        self.assertEqual(movimiento.cantidad, -2)


if __name__ == "__main__":
    unittest.main()
