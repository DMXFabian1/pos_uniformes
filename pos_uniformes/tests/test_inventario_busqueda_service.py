"""Búsqueda de Inventario: Meili solo indexa activas; las inactivas no se pierden."""

from __future__ import annotations

import unittest

from pos_uniformes.services.inventario_busqueda_service import combinar_hits_meili


def _fila(sku: str, nombre: str, activa: bool = True) -> dict[str, object]:
    return {"sku": sku, "producto_nombre": nombre, "variante_activa": activa}


def _contiene(texto: str):
    return lambda fila: texto in str(fila["producto_nombre"]).lower()


class CombinarHitsMeiliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filas = [
            _fila("A", "Pants Gales"),
            _fila("B", "Pants Morelos", activa=False),
            _fila("C", "Playera Gales", activa=False),
            _fila("D", "Playera Morelos"),
        ]

    def test_inactivas_que_coinciden_se_conservan(self) -> None:
        resultado = combinar_hits_meili(self.filas, {"A"}, _contiene("pants"))
        self.assertEqual([f["sku"] for f in resultado], ["A", "B"])

    def test_inactivas_que_no_coinciden_no_entran(self) -> None:
        resultado = combinar_hits_meili(self.filas, {"D"}, _contiene("morelos playera"))
        self.assertEqual([f["sku"] for f in resultado], ["D"])

    def test_activas_solo_por_meili(self) -> None:
        # Una activa que no regresó Meili no se agrega aunque coincida local.
        resultado = combinar_hits_meili(self.filas, set(), _contiene("pants"))
        self.assertEqual([f["sku"] for f in resultado], ["B"])


if __name__ == "__main__":
    unittest.main()
