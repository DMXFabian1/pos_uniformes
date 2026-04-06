from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.database.models import EstadoApartado, TipoMovimientoCaja
from pos_uniformes.services.caja_service import CajaService


class _ScalarResult:
    def __init__(self, values):
        self._values = list(values)
        self.unique_called = False

    def all(self):
        return list(self._values)

    def unique(self):
        self.unique_called = True
        return self


class _SessionStub:
    def __init__(self, scalar_batches):
        self._batches = list(scalar_batches)

    def scalars(self, statement):
        del statement
        if not self._batches:
            raise AssertionError("No hay mas lotes configurados para scalars().")
        return _ScalarResult(self._batches.pop(0))


class CajaServiceTests(unittest.TestCase):
    def test_listar_sesiones_uses_unique_for_joined_movements(self) -> None:
        scalar_result = _ScalarResult([])
        session = SimpleNamespace(scalars=lambda statement: scalar_result)

        with patch("pos_uniformes.services.caja_service.select", side_effect=lambda *args, **kwargs: _QueryStub()):
            CajaService.listar_sesiones(session)

        self.assertTrue(scalar_result.unique_called)

    def test_resumir_sesion_excludes_canceled_layaway_payments_from_expected_cash(self) -> None:
        cash_session = SimpleNamespace(
            id=7,
            abierta_at=datetime(2026, 4, 6, 9, 0),
            cerrada_at=datetime(2026, 4, 6, 18, 0),
            monto_apertura=Decimal("500.00"),
        )
        sale = SimpleNamespace(
            observacion="Metodo de pago: Efectivo",
            total=Decimal("200.00"),
        )
        active_payment = SimpleNamespace(
            monto=Decimal("100.00"),
            monto_efectivo=Decimal("100.00"),
            apartado=SimpleNamespace(estado=EstadoApartado.ACTIVO),
        )
        canceled_payment = SimpleNamespace(
            monto=Decimal("150.00"),
            monto_efectivo=Decimal("150.00"),
            apartado=SimpleNamespace(estado=EstadoApartado.CANCELADO),
        )
        movement = SimpleNamespace(
            tipo=TipoMovimientoCaja.INGRESO,
            monto=Decimal("50.00"),
        )
        session = _SessionStub(
            [
                [sale],
                [active_payment, canceled_payment],
                [movement],
            ]
        )

        with patch("pos_uniformes.services.caja_service.select", side_effect=lambda *args, **kwargs: _QueryStub()):
            resumen = CajaService.resumir_sesion(session, cash_session)

        self.assertEqual(resumen.ventas_efectivo_count, 1)
        self.assertEqual(resumen.efectivo_ventas, Decimal("200.00"))
        self.assertEqual(resumen.abonos_efectivo_count, 1)
        self.assertEqual(resumen.efectivo_abonos, Decimal("100.00"))
        self.assertEqual(resumen.ingresos_total, Decimal("50.00"))
        self.assertEqual(resumen.esperado_en_caja, Decimal("850.00"))

    def test_resumir_sesion_uses_mixed_cash_component_for_layaway_payment(self) -> None:
        cash_session = SimpleNamespace(
            id=8,
            abierta_at=datetime(2026, 4, 6, 9, 0),
            cerrada_at=datetime(2026, 4, 6, 18, 0),
            monto_apertura=Decimal("300.00"),
        )
        payment = SimpleNamespace(
            monto=Decimal("200.00"),
            monto_efectivo=Decimal("80.00"),
            apartado=SimpleNamespace(estado=EstadoApartado.ACTIVO),
        )
        session = _SessionStub(
            [
                [],
                [payment],
                [],
            ]
        )

        with patch("pos_uniformes.services.caja_service.select", side_effect=lambda *args, **kwargs: _QueryStub()):
            resumen = CajaService.resumir_sesion(session, cash_session)

        self.assertEqual(resumen.abonos_efectivo_count, 1)
        self.assertEqual(resumen.efectivo_abonos, Decimal("80.00"))
        self.assertEqual(resumen.esperado_en_caja, Decimal("380.00"))


class _QueryStub:
    def options(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def where(self, *args, **kwargs):
        return self


if __name__ == "__main__":
    unittest.main()
