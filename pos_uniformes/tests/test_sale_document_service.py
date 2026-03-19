from __future__ import annotations

from enum import Enum
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sale_document_service import (
    load_layaway_for_receipt,
    load_sale_for_layaway_ticket,
    load_sale_for_ticket,
)


class FakeEstadoApartado(Enum):
    ACTIVO = "activo"
    ENTREGADO = "entregado"


def _build_sale() -> SimpleNamespace:
    producto = SimpleNamespace(nombre="Playera")
    variante = SimpleNamespace(sku="SKU-001", producto=producto)
    detalle = SimpleNamespace(variante=variante)
    cliente = SimpleNamespace(codigo_cliente="CLI-001")
    return SimpleNamespace(detalles=[detalle], cliente=cliente)


def _build_layaway(*, delivered: bool) -> SimpleNamespace:
    producto = SimpleNamespace(nombre="Playera")
    variante = SimpleNamespace(sku="SKU-001", producto=producto)
    detalle = SimpleNamespace(variante=variante)
    abono = SimpleNamespace(usuario=SimpleNamespace(username="cajero"))
    return SimpleNamespace(
        folio="APA-001",
        estado=FakeEstadoApartado.ENTREGADO if delivered else FakeEstadoApartado.ACTIVO,
        detalles=[detalle],
        abonos=[abono],
    )


class SaleDocumentServiceTests(unittest.TestCase):
    def test_load_sale_for_ticket_returns_sale_when_found(self) -> None:
        sale = _build_sale()
        session = SimpleNamespace(get=lambda _model, _id: sale)

        with patch(
            "pos_uniformes.services.sale_document_service._resolve_sale_document_dependencies",
            return_value=(object(), object(), FakeEstadoApartado, lambda model: None),
        ):
            result = load_sale_for_ticket(session, 10)

        self.assertIs(result, sale)

    def test_load_sale_for_ticket_raises_when_sale_is_missing(self) -> None:
        session = SimpleNamespace(get=lambda _model, _id: None)

        with patch(
            "pos_uniformes.services.sale_document_service._resolve_sale_document_dependencies",
            return_value=(object(), object(), FakeEstadoApartado, lambda model: None),
        ):
            with self.assertRaisesRegex(ValueError, "Venta no encontrada"):
                load_sale_for_ticket(session, 10)

    def test_load_layaway_for_receipt_returns_layaway_when_found(self) -> None:
        layaway = _build_layaway(delivered=False)
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.sale_document_service._resolve_sale_document_dependencies",
            return_value=(
                object(),
                SimpleNamespace(obtener_apartado=lambda current_session, layaway_id: layaway),
                FakeEstadoApartado,
                lambda model: None,
            ),
        ):
            result = load_layaway_for_receipt(session, 5)

        self.assertIs(result, layaway)

    def test_load_sale_for_layaway_ticket_raises_when_layaway_not_delivered(self) -> None:
        layaway = _build_layaway(delivered=False)
        session = SimpleNamespace(scalar=lambda _stmt: _build_sale())

        with patch(
            "pos_uniformes.services.sale_document_service._resolve_sale_document_dependencies",
            return_value=(
                SimpleNamespace(folio=""),
                SimpleNamespace(obtener_apartado=lambda current_session, layaway_id: layaway),
                FakeEstadoApartado,
                lambda model: None,
            ),
        ):
            with self.assertRaisesRegex(ValueError, "solo esta disponible para apartados entregados"):
                load_sale_for_layaway_ticket(session, 5)

    def test_load_sale_for_layaway_ticket_returns_sale_when_generated_sale_exists(self) -> None:
        layaway = _build_layaway(delivered=True)
        sale = _build_sale()
        venta_model = SimpleNamespace(folio="")

        class _SelectStub:
            def where(self, _condition):
                return "stmt"

        session = SimpleNamespace(scalar=lambda _stmt: sale)

        with patch(
            "pos_uniformes.services.sale_document_service._resolve_sale_document_dependencies",
            return_value=(
                venta_model,
                SimpleNamespace(obtener_apartado=lambda current_session, layaway_id: layaway),
                FakeEstadoApartado,
                lambda model: _SelectStub(),
            ),
        ):
            result = load_sale_for_layaway_ticket(session, 5)

        self.assertIs(result, sale)


if __name__ == "__main__":
    unittest.main()
