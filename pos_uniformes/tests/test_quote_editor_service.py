from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.quote_editor_service import QuoteSavePayload, load_quote_editor_snapshot, save_quote_from_editor


class QuoteEditorServiceTests(unittest.TestCase):
    def test_load_quote_editor_snapshot_requires_draft(self) -> None:
        quote = SimpleNamespace(
            id=5,
            folio="PRE-001",
            cliente_id=8,
            cliente_nombre="Maria",
            cliente_telefono="5551234567",
            cliente=None,
            vigencia_hasta=datetime(2026, 3, 31, 0, 0),
            observacion="Seguimiento por WhatsApp.",
            estado=SimpleNamespace(value="BORRADOR"),
            detalles=[
                SimpleNamespace(
                    sku_snapshot="SKU-001",
                    descripcion_snapshot="Playera",
                    cantidad=2,
                    precio_unitario="199.00",
                )
            ],
        )
        fake_service = SimpleNamespace(obtener_presupuesto=lambda session, quote_id: quote)

        with patch(
            "pos_uniformes.services.quote_editor_service._resolve_quote_editor_dependencies",
            return_value=(object(), object(), fake_service),
        ):
            snapshot = load_quote_editor_snapshot(SimpleNamespace(), quote_id=5)

        self.assertEqual(snapshot.quote_id, 5)
        self.assertEqual(snapshot.folio, "PRE-001")
        self.assertEqual(snapshot.customer_id, 8)
        self.assertEqual(snapshot.customer_name, "Maria")
        self.assertEqual(snapshot.customer_phone, "5551234567")
        self.assertEqual(snapshot.notes_text, "Seguimiento por WhatsApp.")
        self.assertEqual(snapshot.status_label, "BORRADOR")
        self.assertEqual(len(snapshot.detail_rows), 1)
        self.assertEqual(snapshot.detail_rows[0].sku, "SKU-001")
        self.assertEqual(snapshot.detail_rows[0].description, "Playera")

    def test_save_quote_from_editor_creates_draft(self) -> None:
        user = object()
        client = SimpleNamespace(nombre="Maria", telefono="5551234567")
        created_quote = SimpleNamespace(id=5, folio="PRE-001", estado=SimpleNamespace(value="BORRADOR"))
        fake_service = SimpleNamespace(
            crear_presupuesto=lambda **kwargs: created_quote,
            obtener_presupuesto=lambda *args, **kwargs: None,
            actualizar_presupuesto=lambda **kwargs: None,
        )
        session = SimpleNamespace(
            get=lambda model, item_id: user if item_id == 7 else client,
            flush=lambda: None,
        )

        payload = QuoteSavePayload(
            quote_id=None,
            folio="PRE-001",
            customer_id=10,
            validity_at=datetime(2026, 3, 31, 0, 0),
            notes_text="Seguimiento",
            items=(SimpleNamespace(sku="SKU-1", cantidad=2),),
            target_state="BORRADOR",
        )

        with patch(
            "pos_uniformes.services.quote_editor_service._resolve_quote_editor_dependencies",
            return_value=(object(), object(), fake_service),
        ):
            result = save_quote_from_editor(session, user_id=7, payload=payload)

        self.assertEqual(result.quote_id, 5)
        self.assertEqual(result.folio, "PRE-001")
        self.assertEqual(result.status_label, "BORRADOR")
        self.assertEqual(result.action_key, "save_quote_draft")


if __name__ == "__main__":
    unittest.main()
