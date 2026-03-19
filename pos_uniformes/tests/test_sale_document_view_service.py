from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sale_document_view_service import (
    PrintableDocumentSettings,
    build_layaway_receipt_document_view,
    build_layaway_sale_ticket_document_view,
    build_sale_ticket_document_view,
)


class SaleDocumentViewServiceTests(unittest.TestCase):
    def test_build_sale_ticket_document_view_uses_loaded_sale_and_print_settings(self) -> None:
        session = object()
        sale = SimpleNamespace(folio="VTA-001")
        settings = PrintableDocumentSettings(
            business_name="POS Uniformes",
            business_phone="555-0000",
            business_address="Centro",
            ticket_footer="Gracias por tu compra.",
            preferred_printer="Brother",
            ticket_copies=2,
        )

        with (
            patch(
                "pos_uniformes.services.sale_document_view_service._resolve_sale_document_view_dependencies",
                return_value=(
                    lambda current_session, sale_id: sale,
                    lambda current_session, layaway_id: None,
                    lambda current_session, layaway_id: None,
                    lambda current_session, **kwargs: settings,
                ),
            ),
            patch(
                "pos_uniformes.services.sale_document_view_service.build_sale_ticket_text",
                return_value="ticket renderizado",
            ) as build_text,
        ):
            view = build_sale_ticket_document_view(session, sale_id=15)

        self.assertEqual(view.title, "Ticket 15")
        self.assertEqual(view.content, "ticket renderizado")
        build_text.assert_called_once_with(
            sale=sale,
            business_name="POS Uniformes",
            business_phone="555-0000",
            business_address="Centro",
            ticket_footer="Gracias por tu compra.",
            preferred_printer="Brother",
            ticket_copies=2,
        )

    def test_build_sale_ticket_document_view_falls_back_when_print_settings_fail(self) -> None:
        sale = SimpleNamespace(folio="VTA-002")

        with (
            patch(
                "pos_uniformes.services.sale_document_view_service._resolve_sale_document_view_dependencies",
                return_value=(
                    lambda current_session, sale_id: sale,
                    lambda current_session, layaway_id: None,
                    lambda current_session, layaway_id: None,
                    lambda current_session, **kwargs: (_ for _ in ()).throw(RuntimeError("sin config")),
                ),
            ),
            patch(
                "pos_uniformes.services.sale_document_view_service.build_sale_ticket_text",
                return_value="ticket fallback",
            ) as build_text,
        ):
            view = build_sale_ticket_document_view(object(), sale_id=22)

        self.assertEqual(view.title, "Ticket 22")
        self.assertEqual(view.content, "ticket fallback")
        self.assertEqual(build_text.call_args.kwargs["business_name"], "POS Uniformes")
        self.assertEqual(build_text.call_args.kwargs["ticket_footer"], "Gracias por tu compra.")
        self.assertEqual(build_text.call_args.kwargs["ticket_copies"], 1)

    def test_build_layaway_receipt_document_view_uses_receipt_defaults(self) -> None:
        session = object()
        layaway = SimpleNamespace(folio="APA-001")
        settings = PrintableDocumentSettings(
            business_name="POS Uniformes",
            business_phone="555-0000",
            business_address="Centro",
            ticket_footer="Gracias por tu preferencia.",
            preferred_printer="Brother",
            ticket_copies=3,
        )

        with (
            patch(
                "pos_uniformes.services.sale_document_view_service._resolve_sale_document_view_dependencies",
                return_value=(
                    lambda current_session, sale_id: None,
                    lambda current_session, layaway_id: layaway,
                    lambda current_session, layaway_id: None,
                    lambda current_session, **kwargs: settings,
                ),
            ),
            patch(
                "pos_uniformes.services.sale_document_view_service.build_layaway_receipt_text",
                return_value="comprobante renderizado",
            ) as build_text,
        ):
            view = build_layaway_receipt_document_view(session, layaway_id=7)

        self.assertEqual(view.title, "Apartado 7")
        self.assertEqual(view.content, "comprobante renderizado")
        build_text.assert_called_once_with(
            layaway=layaway,
            business_name="POS Uniformes",
            business_phone="555-0000",
            business_address="Centro",
            ticket_footer="Gracias por tu preferencia.",
            preferred_printer="Brother",
            ticket_copies=3,
        )

    def test_build_layaway_sale_ticket_document_view_uses_generated_sale(self) -> None:
        session = object()
        sale = SimpleNamespace(folio="ENT-APA-001")
        settings = PrintableDocumentSettings(
            business_name="POS Uniformes",
            business_phone="",
            business_address="",
            ticket_footer="Gracias por tu compra.",
            preferred_printer="",
            ticket_copies=1,
        )

        with (
            patch(
                "pos_uniformes.services.sale_document_view_service._resolve_sale_document_view_dependencies",
                return_value=(
                    lambda current_session, sale_id: None,
                    lambda current_session, layaway_id: None,
                    lambda current_session, layaway_id: sale,
                    lambda current_session, **kwargs: settings,
                ),
            ),
            patch(
                "pos_uniformes.services.sale_document_view_service.build_sale_ticket_text",
                return_value="ticket de entrega",
            ) as build_text,
        ):
            view = build_layaway_sale_ticket_document_view(session, layaway_id=9)

        self.assertEqual(view.title, "Ticket de entrega 9")
        self.assertEqual(view.content, "ticket de entrega")
        self.assertEqual(build_text.call_args.kwargs["sale"], sale)


if __name__ == "__main__":
    unittest.main()
