"""Demanda no atendida por SKU para la ficha de Inventario (tanda 5)."""

from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.exc import OperationalError, ProgrammingError

from pos_uniformes.services import demanda_service as dm


def _senal(tipo, sku=""):
    return SimpleNamespace(tipo=tipo, sku=sku, texto="", producto="", talla="", piezas=1, created_at=datetime(2026, 11, 1))


class PedidasPorSkuTests(unittest.TestCase):
    def test_solo_cuenta_tallas_agotadas_con_codigo(self) -> None:
        filas = [
            _senal(dm.TALLA_AGOTADA, "SKU1"),
            _senal(dm.TALLA_AGOTADA, "SKU1"),
            _senal(dm.TALLA_AGOTADA, "SKU2"),
            _senal(dm.TALLA_AGOTADA, ""),
            _senal(dm.BUSQUEDA_VACIA, "SKU1"),
            _senal(dm.CARRITO_VACIO, "SKU1"),
        ]
        self.assertEqual(dm.pedidas_por_sku(filas), {"SKU1": 2, "SKU2": 1})

    def test_texto(self) -> None:
        self.assertEqual(dm.texto_pedidas(0), "")
        self.assertEqual(dm.texto_pedidas(1), "La pidieron 1 vez en 30 días")
        self.assertEqual(dm.texto_pedidas(4), "La pidieron 4 veces en 30 días")


class CargarPedidasTests(unittest.TestCase):
    def test_una_sola_consulta_agrupada(self) -> None:
        session = Mock()
        session.execute.return_value = [("SKU1", 3), ("SKU9", 1)]
        self.assertEqual(dm.cargar_pedidas_por_sku(session, ahora=datetime(2026, 11, 13)), {"SKU1": 3, "SKU9": 1})
        self.assertEqual(session.execute.call_count, 1)
        sql = str(session.execute.call_args[0][0])
        self.assertIn("GROUP BY", sql)
        self.assertIn("demanda_no_atendida", sql)

    def test_sin_la_tabla_no_truena(self) -> None:
        session = Mock()
        session.execute.side_effect = ProgrammingError("SELECT", {}, Exception('relation "demanda_no_atendida" does not exist'))
        self.assertEqual(dm.cargar_pedidas_por_sku(session), {})
        session.rollback.assert_called_once_with()

    def test_otro_error_sube_para_que_la_cache_lo_maneje(self) -> None:
        session = Mock()
        session.execute.side_effect = OperationalError("SELECT", {}, Exception("sin red"))
        with self.assertRaises(OperationalError):
            dm.cargar_pedidas_por_sku(session)


if __name__ == "__main__":
    unittest.main()
