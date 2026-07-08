from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.quote_document_view_service import build_quote_document_view  # noqa: E402
from pos_uniformes.services.business_print_settings_service import BusinessPrintSettingsSnapshot  # noqa: E402


def _make_settings(**overrides) -> BusinessPrintSettingsSnapshot:
    defaults = dict(
        business_name="POS Uniformes",
        business_phone="555-1234",
        business_address="Calle Principal 1",
        ticket_footer="",
        preferred_printer="Brother",
        ticket_printer="Brother",
        ticket_copies=1,
    )
    defaults.update(overrides)
    return BusinessPrintSettingsSnapshot(**defaults)


class QuoteDocumentViewServiceTests(unittest.TestCase):
    def _patch_deps(self, quote, settings):
        class FakePresupuestoService:
            @staticmethod
            def obtener_presupuesto(session, quote_id):
                return quote

        return patch(
            "pos_uniformes.services.quote_document_view_service._resolve_quote_document_view_dependencies",
            return_value=(FakePresupuestoService, lambda session, **kw: settings),
        )

    def test_returns_view_with_correct_title(self) -> None:
        quote = SimpleNamespace(folio="PRE-001")
        settings = _make_settings()

        with (
            self._patch_deps(quote, settings),
            patch(
                "pos_uniformes.services.quote_document_view_service.build_quote_text",
                return_value="contenido presupuesto",
            ),
        ):
            view = build_quote_document_view(object(), quote_id=1)

        self.assertEqual(view.title, "Presupuesto PRE-001")

    def test_returns_view_with_content_from_build_quote_text(self) -> None:
        quote = SimpleNamespace(folio="PRE-002")
        settings = _make_settings()

        with (
            self._patch_deps(quote, settings),
            patch(
                "pos_uniformes.services.quote_document_view_service.build_quote_text",
                return_value="texto generado",
            ),
        ):
            view = build_quote_document_view(object(), quote_id=2)

        self.assertEqual(view.content, "texto generado")

    def test_passes_business_settings_to_build_quote_text(self) -> None:
        quote = SimpleNamespace(folio="PRE-003")
        settings = _make_settings(
            business_name="Uniformes ABC",
            business_phone="555-9999",
            business_address="Av. Central 5",
        )

        with (
            self._patch_deps(quote, settings),
            patch(
                "pos_uniformes.services.quote_document_view_service.build_quote_text",
                return_value="ok",
            ) as build_text,
        ):
            build_quote_document_view(object(), quote_id=3)

        call_kwargs = build_text.call_args.kwargs
        self.assertEqual(call_kwargs["business_name"], "Uniformes ABC")
        self.assertEqual(call_kwargs["business_phone"], "555-9999")
        self.assertEqual(call_kwargs["business_address"], "Av. Central 5")
        self.assertEqual(call_kwargs["quote"], quote)

    def test_ticket_footer_is_always_empty_string(self) -> None:
        """El presupuesto nunca lleva pie de ticket — se fuerza a ''."""
        quote = SimpleNamespace(folio="PRE-004")
        settings = _make_settings(ticket_footer="Este footer no debe aparecer")

        with (
            self._patch_deps(quote, settings),
            patch(
                "pos_uniformes.services.quote_document_view_service.build_quote_text",
                return_value="ok",
            ) as build_text,
        ):
            build_quote_document_view(object(), quote_id=4)

        self.assertEqual(build_text.call_args.kwargs["ticket_footer"], "")

    def test_raises_when_quote_not_found(self) -> None:
        with (
            self._patch_deps(None, _make_settings()),
            patch(
                "pos_uniformes.services.quote_document_view_service.build_quote_text",
                return_value="",
            ),
        ):
            with self.assertRaises(ValueError):
                build_quote_document_view(object(), quote_id=99)


if __name__ == "__main__":
    unittest.main()
