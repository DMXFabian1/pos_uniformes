from __future__ import annotations

import unittest

from pos_uniformes.database.models import Venta


class SaleModelFieldsTests(unittest.TestCase):
    def test_venta_declares_discount_fields(self) -> None:
        column_names = set(Venta.__table__.columns.keys())

        self.assertIn("descuento_porcentaje", column_names)
        self.assertIn("descuento_monto", column_names)
