from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from pos_uniformes.database.models import TipoMovimientoInventario
from pos_uniformes.services.inventario_service import InventarioService


def _make_variante(stock_actual: int = 10, variante_id: int = 1) -> SimpleNamespace:
    """Crea un stub de Variante con los atributos mínimos requeridos."""
    return SimpleNamespace(id=variante_id, stock_actual=stock_actual)


class _SessionStub:
    """Stub mínimo de SQLAlchemy Session para tests unitarios."""

    def __init__(self, variante_to_lock: object | None = None) -> None:
        self.added: list[object] = []
        self._variante_to_lock = variante_to_lock
        # Rastrear si se llamó scalar con with_for_update
        self.scalar_called = False

    def add(self, value: object) -> None:
        self.added.append(value)

    def scalar(self, stmt: object) -> object | None:
        """Simula SELECT ... FOR UPDATE devolviendo la variante bloqueada."""
        self.scalar_called = True
        return self._variante_to_lock


class InventarioServiceTests(unittest.TestCase):
    def test_registrar_movimiento_still_blocks_negative_stock_by_default(self) -> None:
        variante = _make_variante(stock_actual=1)
        session = _SessionStub(variante_to_lock=variante)

        with self.assertRaisesRegex(ValueError, "stock negativo"):
            InventarioService.registrar_movimiento(
                session=session,
                variante=variante,
                tipo_movimiento=TipoMovimientoInventario.SALIDA_VENTA,
                cantidad=-2,
            )

    def test_registrar_salida_venta_allows_negative_stock_when_policy_is_disabled(self) -> None:
        variante = _make_variante(stock_actual=1)
        session = _SessionStub(variante_to_lock=variante)

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

    def test_registrar_movimiento_adquiere_lock_antes_de_modificar_stock(self) -> None:
        """registrar_movimiento debe emitir SELECT FOR UPDATE antes de leer stock_actual."""
        variante = _make_variante(stock_actual=5)
        session = _SessionStub(variante_to_lock=variante)

        with patch(
            "pos_uniformes.services.inventario_service.MovimientoInventario",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ):
            InventarioService.registrar_movimiento(
                session=session,
                variante=variante,
                tipo_movimiento=TipoMovimientoInventario.ENTRADA_COMPRA,
                cantidad=3,
            )

        self.assertTrue(
            session.scalar_called,
            "Se esperaba que scalar() fuera llamado para adquirir el row-level lock.",
        )

    def test_registrar_movimiento_lanza_si_variante_desaparece_entre_lock_y_escritura(self) -> None:
        """Si la variante fue eliminada justo antes del lock, se lanza ValueError."""
        variante = _make_variante(stock_actual=5)
        # scalar() devuelve None → la variante ya no existe
        session = _SessionStub(variante_to_lock=None)

        with self.assertRaisesRegex(ValueError, "ya no existe"):
            InventarioService.registrar_movimiento(
                session=session,
                variante=variante,
                tipo_movimiento=TipoMovimientoInventario.ENTRADA_COMPRA,
                cantidad=3,
            )


if __name__ == "__main__":
    unittest.main()
