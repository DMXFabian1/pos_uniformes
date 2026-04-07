from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.ui.helpers.sale_sports_uniform_helper import (
    SaleSportsUniformResolution,
    attach_sports_uniform_trace_to_cart_lines,
    belongs_to_same_school,
    build_sports_uniform_prototype_note,
    collect_internal_sale_cart_notes,
    is_deportivo_playera_variant,
    is_deportivo_two_piece_variant,
    resolve_sale_scan_variants,
    restore_sports_uniform_playera_price_if_needed,
    validate_sports_playera_match,
)


def _build_variant(
    *,
    sku: str,
    product_name: str,
    school_id: int = 1,
    school_name: str = "Patria",
    garment_type: str = "Deportivo",
    piece_type: str = "Pants 2pz",
    talla: str = "14",
    color: str = "Azul Marino",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        sku=sku,
        talla=talla,
        color=color,
        precio_venta="199.00",
        producto=SimpleNamespace(
            nombre=product_name,
            nombre_base=product_name,
            descripcion=product_name,
            escuela_id=school_id,
            escuela=SimpleNamespace(nombre=school_name),
            tipo_prenda=SimpleNamespace(nombre=garment_type),
            tipo_pieza=SimpleNamespace(nombre=piece_type),
        ),
    )


class SaleSportsUniformHelperTests(unittest.TestCase):
    def test_detects_deportivo_two_piece_variant(self) -> None:
        scanned_variant = _build_variant(
            sku="P2-001",
            product_name="Pants 2pz Deportivo",
        )

        self.assertTrue(is_deportivo_two_piece_variant(scanned_variant))

    def test_detects_deportivo_playera_variant(self) -> None:
        playera_variant = _build_variant(
            sku="PLY-001",
            product_name="Playera Deportiva Escolar",
            piece_type="Playera",
            talla="CH",
        )

        self.assertTrue(is_deportivo_playera_variant(playera_variant))

    @patch("pos_uniformes.ui.helpers.sale_sports_uniform_helper.QMessageBox.question")
    def test_returns_original_variant_when_operator_declines_playera(self, question_mock) -> None:
        scanned_variant = _build_variant(
            sku="P2-001",
            product_name="Pants 2pz Deportivo",
        )
        question_mock.return_value = 65536  # QMessageBox.StandardButton.No

        resolution = resolve_sale_scan_variants(None, SimpleNamespace(), scanned_variant)

        self.assertEqual(
            resolution,
            SaleSportsUniformResolution(variants=(scanned_variant,)),
        )

    @patch("pos_uniformes.ui.helpers.sale_sports_uniform_helper.QInputDialog.getText")
    @patch("pos_uniformes.ui.helpers.sale_sports_uniform_helper.QMessageBox.question")
    def test_adds_scanned_playera_when_same_school(self, question_mock, get_text_mock) -> None:
        scanned_variant = _build_variant(
            sku="P2-001",
            product_name="Pants 2pz Deportivo",
        )
        playera_variant = _build_variant(
            sku="PLY-001",
            product_name="Playera Deportiva Escolar",
            piece_type="Playera",
            talla="CH",
        )
        question_mock.return_value = 16384  # QMessageBox.StandardButton.Yes
        get_text_mock.return_value = ("ply-001", True)

        resolution = resolve_sale_scan_variants(
            None,
            SimpleNamespace(),
            scanned_variant,
            variant_loader=lambda session, sku: playera_variant if sku == "PLY-001" else None,
        )

        self.assertEqual(resolution.variants, (scanned_variant, playera_variant))
        self.assertTrue(resolution.composed_as_three_pieces)
        self.assertEqual(resolution.selected_playera_sku, "PLY-001")
        self.assertIn("atipica", resolution.size_hint)

    @patch("pos_uniformes.ui.helpers.sale_sports_uniform_helper.QInputDialog.getText")
    @patch("pos_uniformes.ui.helpers.sale_sports_uniform_helper.QMessageBox.question")
    def test_rejects_playera_from_another_school(self, question_mock, get_text_mock) -> None:
        scanned_variant = _build_variant(
            sku="P2-001",
            product_name="Pants 2pz Deportivo",
            school_id=1,
            school_name="Patria",
        )
        foreign_playera = _build_variant(
            sku="PLY-999",
            product_name="Playera Deportiva Escolar",
            school_id=2,
            school_name="Juarez",
            piece_type="Playera",
        )
        question_mock.return_value = 16384
        get_text_mock.return_value = ("PLY-999", True)

        with self.assertRaisesRegex(ValueError, "misma escuela"):
            resolve_sale_scan_variants(
                None,
                SimpleNamespace(),
                scanned_variant,
                variant_loader=lambda session, sku: foreign_playera if sku == "PLY-999" else None,
            )

    @patch("pos_uniformes.ui.helpers.sale_sports_uniform_helper.QInputDialog.getItem")
    @patch("pos_uniformes.ui.helpers.sale_sports_uniform_helper.QInputDialog.getText")
    @patch("pos_uniformes.ui.helpers.sale_sports_uniform_helper.QMessageBox.question")
    def test_opens_filtered_list_when_no_playera_sku_is_typed(
        self,
        question_mock,
        get_text_mock,
        get_item_mock,
    ) -> None:
        scanned_variant = _build_variant(
            sku="P2-001",
            product_name="Pants 2pz Deportivo",
        )
        playera_variant = _build_variant(
            sku="PLY-001",
            product_name="Playera Deportiva Escolar",
            piece_type="Playera",
            talla="GD",
        )
        question_mock.return_value = 16384
        get_text_mock.return_value = ("", True)
        get_item_mock.return_value = ("PLY-001 | GD | Azul Marino | Playera Deportiva Escolar | Patria [Atipica]", True)

        resolution = resolve_sale_scan_variants(
            None,
            SimpleNamespace(),
            scanned_variant,
            playera_candidates_loader=lambda session, variant: [playera_variant],
        )

        self.assertEqual(resolution.variants, (scanned_variant, playera_variant))
        self.assertIn("atipica", resolution.size_hint)

    def test_validate_sports_playera_match_accepts_different_size_same_school(self) -> None:
        scanned_variant = _build_variant(
            sku="P2-001",
            product_name="Pants 2pz Deportivo",
            talla="14",
        )
        playera_variant = _build_variant(
            sku="PLY-001",
            product_name="Playera Deportiva Escolar",
            piece_type="Playera",
            talla="CH",
        )

        validate_sports_playera_match(scanned_variant, playera_variant)
        self.assertTrue(belongs_to_same_school(scanned_variant, playera_variant))

    def test_collects_unique_internal_prototype_notes_from_cart(self) -> None:
        scanned_variant = _build_variant(sku="P2-001", product_name="Pants 2pz Deportivo")
        playera_variant = _build_variant(
            sku="PLY-001",
            product_name="Playera Deportiva Escolar",
            piece_type="Playera",
        )
        note = build_sports_uniform_prototype_note(scanned_variant, playera_variant)
        sale_cart = [
            {"sku": "P2-001", "cantidad": 1},
            {"sku": "PLY-001", "cantidad": 1},
        ]

        attach_sports_uniform_trace_to_cart_lines(sale_cart, trace_note=note)

        self.assertEqual(
            collect_internal_sale_cart_notes(sale_cart, scope="SPORTS_UNIFORM_PROTOTYPE"),
            [note],
        )
        self.assertIn("100.00", note)

    def test_restore_playera_price_when_two_piece_base_line_is_removed(self) -> None:
        scanned_variant = _build_variant(sku="P2-001", product_name="Pants 2pz Deportivo")
        playera_variant = _build_variant(
            sku="PLY-001",
            product_name="Playera Deportiva Escolar",
            piece_type="Playera",
        )
        note = build_sports_uniform_prototype_note(scanned_variant, playera_variant)
        sale_cart = [
            {"sku": "P2-001", "cantidad": 1},
            {
                "sku": "PLY-001",
                "cantidad": 1,
                "precio_unitario": 100,
                "precio_base": 189,
                "pricing_rule_key": "SPORTS_UNIFORM_3PZ_PLAYERA",
                "pricing_rule_label": "Conjunto deportivo 3pz",
            },
        ]

        attach_sports_uniform_trace_to_cart_lines(
            sale_cart,
            trace_note=note,
            base_sku="P2-001",
            playera_sku="PLY-001",
        )
        removed_line = dict(sale_cart[0])
        remaining_cart = [sale_cart[1]]

        message = restore_sports_uniform_playera_price_if_needed(
            remaining_cart,
            removed_line_item=removed_line,
        )

        self.assertIn("precio original", message)
        self.assertEqual(remaining_cart[0]["precio_unitario"], 189)
        self.assertEqual(remaining_cart[0]["pricing_rule_key"], "")
        self.assertNotIn("internal_trace_note", remaining_cart[0])


if __name__ == "__main__":
    unittest.main()
