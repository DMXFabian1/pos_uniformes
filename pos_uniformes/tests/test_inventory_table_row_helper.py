from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_table_row_helper import (
    build_inventory_table_row_view,
    build_inventory_table_row_views,
)


class InventoryTableRowHelperTests(unittest.TestCase):
    def test_build_inventory_table_row_view_for_low_stock_sin_columna_qr(self) -> None:
        view = build_inventory_table_row_view(
            {
                "variante_id": 8,
                "sku": "SKU-008",
                "producto_nombre_base": "Pants Deportivo",
                "talla": "16",
                "color": "Azul Marino",
                "stock_actual": 2,
                "apartado_cantidad": 1,
                "variante_activa": False,
                "ultimo_conteo_at": None,
                "stock_minimo": None,
            }
        )

        self.assertEqual(view.variant_id, 8)
        self.assertEqual(
            view.values,
            ("SKU-008", "Pants Deportivo", "16", "Azul Marino", "2 Bajo", "Tienda", "—", "Nunca"),
        )
        # Desactivada: toda la fila en gris (también la cifra) y lo dice al pasar el mouse.
        self.assertEqual(view.row_tone, "muted")
        self.assertEqual(view.stock_tone, "muted")
        self.assertIn("Desactivada", view.tooltip)
        self.assertFalse(view.stock_con_fondo)
        self.assertFalse(hasattr(view, "qr_tone"))

    def test_sin_columnas_apartado_ni_estado(self) -> None:
        from pos_uniformes.ui.helpers.inventory_table_row_helper import INVENTORY_TABLE_HEADERS

        self.assertNotIn("Apartado", INVENTORY_TABLE_HEADERS)
        self.assertNotIn("Estado", INVENTORY_TABLE_HEADERS)
        self.assertNotIn("QR", INVENTORY_TABLE_HEADERS)
        self.assertIn("Dónde", INVENTORY_TABLE_HEADERS)
        self.assertNotIn("Piso", INVENTORY_TABLE_HEADERS)
        self.assertNotIn("Almacén", INVENTORY_TABLE_HEADERS)

    def test_activa_no_lleva_aviso(self) -> None:
        view = build_inventory_table_row_view(
            {
                "variante_id": 9, "sku": "S", "producto_nombre_base": "P", "talla": "8", "color": "Azul",
                "stock_actual": 5, "variante_activa": True, "ultimo_conteo_at": None, "stock_minimo": None,
            }
        )
        self.assertIsNone(view.tooltip)
        self.assertEqual(len(view.values), 8)

    def test_build_inventory_table_row_views_for_multiple_rows(self) -> None:
        views = build_inventory_table_row_views(
            [
                {
                    "variante_id": 1,
                    "sku": "SKU-001",
                    "producto_nombre_base": "Camisa Oficial",
                    "talla": "12",
                    "color": "Blanco",
                    "stock_actual": 0,
                    "apartado_cantidad": 0,
                    "variante_activa": True,
                    "ultimo_conteo_at": None,
                    "stock_minimo": None,
                },
                {
                    "variante_id": 2,
                    "sku": "SKU-002",
                    "producto_nombre_base": "Pants Deportivo",
                    "talla": "14",
                    "color": "Azul",
                    "stock_actual": 6,
                    "apartado_cantidad": 0,
                    "variante_activa": True,
                    "ultimo_conteo_at": None,
                    "stock_minimo": None,
                },
            ]
        )

        self.assertEqual(len(views), 2)
        self.assertEqual(views[0].values[4], "0 Agotado")
        self.assertEqual(views[0].row_tone, "danger")
        self.assertEqual(views[0].stock_tone, "danger")
        self.assertEqual(views[1].values[4], "6 OK")
        self.assertIsNone(views[1].row_tone)
        self.assertEqual(views[1].stock_tone, "positive")

    def test_stock_muestra_el_total_aunque_este_en_bodega_y_piso(self) -> None:
        # 10 en total, 7 en bodega y 3 en piso: antes salía «0 Agotado».
        view = build_inventory_table_row_view(
            {
                "variante_id": 3,
                "sku": "SKU-003",
                "producto_nombre_base": "Playera Deportiva",
                "talla": "10",
                "color": "Blanco",
                "stock_actual": 10,
                "stock_bodega": 7,
                "stock_piso": 3,
                "apartado_cantidad": 0,
                "variante_activa": True,
                "ultimo_conteo_at": None,
                "stock_minimo": None,
            }
        )
        self.assertEqual(view.values[4], "10 OK")
        # Piso y Almacén se juntan en «Dónde»; el reparto completo va en el aviso.
        self.assertEqual(view.values[5], "Bodega 7 · Piso 3")
        self.assertEqual(dict(view.cell_tooltips)[5], "Bodega 7 · Piso 3")
        self.assertEqual(view.stock_tone, "positive")
        self.assertIsNone(view.row_tone)

    def test_precio_normal_y_con_oferta(self) -> None:
        from decimal import Decimal

        base = {
            "variante_id": 7, "sku": "SKU-7", "producto_nombre_base": "Pants 2pz", "talla": "10",
            "color": "Marino", "stock_actual": 3, "variante_activa": True, "ultimo_conteo_at": None,
            "stock_minimo": None, "precio_venta": Decimal("250.00"),
        }
        normal = build_inventory_table_row_view(base)
        self.assertEqual(normal.values[6], "$250")
        self.assertNotIn(6, dict(normal.cell_tooltips))
        oferta = build_inventory_table_row_view({**base, "rebaja_tipo": "oferta", "rebaja_precio": Decimal("175")})
        self.assertEqual(oferta.values[6], "Oferta $175")
        self.assertEqual(dict(oferta.cell_tooltips)[6], "Precio normal $250")

    def test_negativo_en_rojo(self) -> None:
        view = build_inventory_table_row_view(
            {
                "variante_id": 4,
                "sku": "SKU-004",
                "producto_nombre_base": "Pants",
                "talla": "8",
                "color": "Azul",
                "stock_actual": -2,
                "apartado_cantidad": 0,
                "variante_activa": True,
                "ultimo_conteo_at": None,
                "stock_minimo": None,
            }
        )
        self.assertEqual(view.values[4], "\u22122 Negativo")
        self.assertEqual(view.stock_tone, "danger")
        self.assertEqual(view.row_tone, "danger")


    def test_pants_3pz_con_receta_en_cero_y_con_existencia(self) -> None:
        base = {
            "variante_id": 5, "sku": "SKU-005", "producto_nombre_base": "Pants 3pz Gales",
            "talla": "8", "color": "Azul", "apartado_cantidad": 0, "variante_activa": True, "ultimo_conteo_at": None, "stock_minimo": None,
            "tipo_pieza_nombre": "Pants 3pz", "es_conjunto": True,
        }
        cero = build_inventory_table_row_view({**base, "stock_actual": 0})
        self.assertEqual((cero.values[4], cero.stock_tone, cero.row_tone), ("0 Agotado", "danger", "danger"))
        dos = build_inventory_table_row_view({**base, "stock_actual": 2})
        self.assertEqual((dos.values[4], dos.stock_tone), ("2 Conjunto", "neutral"))
        self.assertEqual(dos.values[5], "—")  # se arma con piezas: no tiene lugar propio

if __name__ == "__main__":
    unittest.main()
