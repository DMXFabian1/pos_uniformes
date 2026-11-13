from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.inventory_snapshot_service import (
    invalidate_inventory_qr_exists_cache,
    load_inventory_snapshot_rows,
    ordenar_filas_inventario,
)
from pos_uniformes.services.search_filter_service import (
    SEARCH_ALIAS_BLOBS_KEY,
    SEARCH_GENERAL_BLOB_KEY,
)


class InventorySnapshotServiceTests(unittest.TestCase):
    def tearDown(self) -> None:
        invalidate_inventory_qr_exists_cache()

    def test_load_inventory_snapshot_rows_builds_snapshot_from_query_rows(self) -> None:
        raw_rows = [
            (
                8,
                "SKU-008",
                "Uniforme",
                "Marca Norte",
                "Pants Deportivo | Morelos | Pants #4",
                "Pants Deportivo",
                None,
                "Deportivo",
                None,
                "Pants legacy",
                True,
                "16",
                "Azul Marino",
                Decimal("219"),
                Decimal("140"),
                6,
                4,
                1,
                2,
                False,
                True,
                None,
                None,
            )
        ]
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.inventory_snapshot_service._execute_inventory_snapshot_query",
            return_value=raw_rows,
        ), patch(
            "pos_uniformes.services.inventory_snapshot_service._inventory_qr_exists",
            return_value=True,
        ):
            snapshot_rows = load_inventory_snapshot_rows(session)

        self.assertEqual(len(snapshot_rows), 1)
        row = snapshot_rows[0]
        self.assertEqual(row["sku"], "SKU-008")
        self.assertEqual(row["producto_nombre"], "Pants Deportivo | Morelos | Pants")
        self.assertEqual(row["escuela_nombre"], "General")
        self.assertEqual(row["tipo_pieza_nombre"], "-")
        self.assertEqual(row["precio_venta"], Decimal("219.00"))
        self.assertEqual(row["stock_actual"], 6)
        self.assertEqual(row["stock_bodega"], 4)
        self.assertEqual(row["stock_piso"], 1)
        self.assertEqual(row["apartado_cantidad"], 2)
        self.assertIsNone(row["stock_minimo"])
        self.assertTrue(row["qr_exists"])
        self.assertEqual(row["fallback_text"], "fallback")
        self.assertIn("pants deportivo", row[SEARCH_GENERAL_BLOB_KEY])
        self.assertIn("pants legacy", row[SEARCH_ALIAS_BLOBS_KEY]["legacy"])

    def test_inventory_qr_exists_is_reused_for_repeated_sku_until_invalidated(self) -> None:
        raw_rows = [
            (
                8,
                "SKU-008",
                "Uniforme",
                "Marca Norte",
                "Pants Deportivo | Morelos | Pants #4",
                "Pants Deportivo",
                None,
                "Deportivo",
                None,
                "Pants legacy",
                True,
                "16",
                "Azul Marino",
                Decimal("219"),
                Decimal("140"),
                6,
                4,
                1,
                2,
                False,
                True,
                None,
                None,
            )
        ]
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.inventory_snapshot_service._execute_inventory_snapshot_query",
            return_value=raw_rows,
        ), patch(
            "pathlib.Path.exists",
            side_effect=[True, False],
        ) as exists_mock:
            first_rows = load_inventory_snapshot_rows(session)
            second_rows = load_inventory_snapshot_rows(session)
            invalidate_inventory_qr_exists_cache(sku="SKU-008")
            reloaded_rows = load_inventory_snapshot_rows(session)

        self.assertTrue(first_rows[0]["qr_exists"])
        self.assertTrue(second_rows[0]["qr_exists"])
        self.assertFalse(reloaded_rows[0]["qr_exists"])
        self.assertEqual(exists_mock.call_count, 2)


class OrdenFilasInventarioTests(unittest.TestCase):
    def _fila(self, sku: str, producto: str, talla: str, *, pid: int = 1, color: str = "Azul") -> dict[str, object]:
        return {"sku": sku, "producto_nombre": producto, "producto_id": pid, "talla": talla, "color": color}

    def test_tallas_en_orden_de_talla_no_de_sku(self) -> None:
        filas = [
            self._fila("SKU-1", "Pants Gales", "EXG"),
            self._fila("SKU-2", "Pants Gales", "10"),
            self._fila("SKU-3", "Pants Gales", "CH"),
            self._fila("SKU-4", "Pants Gales", "2"),
            self._fila("SKU-5", "Pants Gales", "GD"),
            self._fila("SKU-6", "Pants Gales", "MD"),
            self._fila("SKU-7", "Pants Gales", "16"),
        ]
        orden = [f["talla"] for f in ordenar_filas_inventario(filas)]
        self.assertEqual(orden, ["2", "10", "16", "CH", "MD", "GD", "EXG"])

    def test_agrupa_por_producto_y_uni_al_final(self) -> None:
        filas = [
            self._fila("SKU-9", "Suéter Morelos", "UNI", pid=2),
            self._fila("SKU-1", "Calceta", "UNI", pid=3),
            self._fila("SKU-8", "Suéter Morelos", "8", pid=2),
            self._fila("SKU-7", "Calceta", "13-18", pid=3),
            self._fila("SKU-6", "Calceta", "9-12", pid=3),
        ]
        orden = [(f["producto_nombre"], f["talla"]) for f in ordenar_filas_inventario(filas)]
        self.assertEqual(
            orden,
            [
                ("Calceta", "9-12"),
                ("Calceta", "13-18"),
                ("Calceta", "UNI"),
                ("Suéter Morelos", "8"),
                ("Suéter Morelos", "UNI"),
            ],
        )

    def test_mismo_nombre_distinto_producto_no_se_mezcla(self) -> None:
        filas = [
            self._fila("A", "Playera", "8", pid=2),
            self._fila("B", "Playera", "6", pid=1),
            self._fila("C", "Playera", "10", pid=2),
            self._fila("D", "Playera", "12", pid=1),
        ]
        self.assertEqual([f["sku"] for f in ordenar_filas_inventario(filas)], ["B", "D", "A", "C"])


if __name__ == "__main__":
    unittest.main()
