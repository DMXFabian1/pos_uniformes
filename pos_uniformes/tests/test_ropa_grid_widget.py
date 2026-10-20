"""La cuadrícula de Ropa del kiosko: fichas que filtran, tarjetas con foto, páginas."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

from pos_uniformes.services import foto_local_cache_service as cache  # noqa: E402
from pos_uniformes.ui.helpers import ropa_grid_widget as rg  # noqa: E402
from pos_uniformes.ui.helpers.quote_guided_catalog_helper import (  # noqa: E402
    GuidedCatalogOption,
    GuidedCatalogProductCard,
    GuidedCatalogView,
)

_app = QApplication.instance() or QApplication([])


def _card(i: int, foto_hash: str = "") -> GuidedCatalogProductCard:
    return GuidedCatalogProductCard(
        key=f"Sudadera||Modelo {i}", sku=f"SKU{i:06d}", title=f"Modelo {i}", subtitle="Yamo · Surtido",
        meta_label="", price_label="$139.00", gender_key="NINA", tipo_pieza="Sudadera",
        producto_id=i, foto_hash=foto_hash, marca="Yamo",
    )


def _view(cards, *, elegida: str = "") -> GuidedCatalogView:
    return GuidedCatalogView(
        level_options=(), school_options=(),
        gender_options=(GuidedCatalogOption("MUJER", "Mujer", 3, True), GuidedCatalogOption("TODOS", "Todos", 3, True)),
        profile_options=(),
        bucket_options=(GuidedCatalogOption("Ropa casual", "Ropa casual", 3, True), GuidedCatalogOption("TODOS", "Todas", 3, True)),
        piece_options=(GuidedCatalogOption("Sudadera", "Sudadera", 3, True),),
        product_cards=tuple(cards), variant_options=(), selected_product_key=elegida, selected_sku="",
        status_label="", path_label="Ropa > Ropa casual", empty_label="",
    )


class RopaGridTests(unittest.TestCase):
    def setUp(self) -> None:
        self.w = rg.RopaGridWidget()
        self.addCleanup(self.w.deleteLater)

    def _fichas(self, clave: str) -> list[QPushButton]:
        fila = self.w._filas[clave]
        return [fila.itemAt(i).widget() for i in range(fila.count()) if fila.itemAt(i).widget() is not None]

    def test_pinta_fichas_y_tarjetas(self) -> None:
        self.w.aplicar(_view([_card(1), _card(2)]), genero="TODOS", seccion="TODOS", prenda="")
        self.assertEqual([b.text() for b in self._fichas("genero")], ["Mujer (3)", "Todos (3)"])
        self.assertTrue(self._fichas("genero")[1].isChecked())
        self.assertEqual([b.text() for b in self._fichas("prenda")], ["Todas (3)", "Sudadera (3)"])
        self.assertEqual(len(self.w.tarjetas), 2)
        self.assertIn("2 modelos", self.w.resumen.text())

    def test_las_fichas_avisan_que_se_toco(self) -> None:
        recibido = []
        self.w.genero_elegido.connect(recibido.append)
        self.w.prenda_elegida.connect(recibido.append)
        self.w.aplicar(_view([_card(1)]), genero="TODOS", seccion="TODOS", prenda="")
        self._fichas("genero")[0].click()
        self._fichas("prenda")[1].click()
        self.assertEqual(recibido, ["MUJER", "Sudadera"])

    def test_tocar_una_tarjeta_avisa_el_modelo(self) -> None:
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QMouseEvent

        recibido = []
        self.w.modelo_elegido.connect(recibido.append)
        self.w.aplicar(_view([_card(7)]), genero="TODOS", seccion="TODOS", prenda="")
        tarjeta = self.w.tarjetas["Sudadera||Modelo 7"]
        tarjeta.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
                                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(recibido, ["Sudadera||Modelo 7"])

    def test_por_paginas(self) -> None:
        self.w.aplicar(_view([_card(i) for i in range(30)]), genero="TODOS", seccion="TODOS", prenda="")
        self.assertEqual(len(self.w.tarjetas), rg.POR_PAGINA)
        self.assertFalse(self.w._pager.isHidden())
        self.w._cambiar_pagina(1)
        self.assertEqual(len(self.w.tarjetas), 6)
        self.assertIn("Página 2 de 2", self.w.pagina_label.text())

    def test_la_foto_sale_del_disco_del_kiosko_y_sin_foto_la_inicial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(cache, "satellite_data_dir", return_value=Path(tmp)):
            (Path(tmp) / "data" / "fotos").mkdir(parents=True)
            Image.new("RGB", (300, 400), (90, 20, 20)).save(Path(tmp) / "data" / "fotos" / "abc123.jpg")
            self.w.aplicar(_view([_card(1, "abc123"), _card(2)]), genero="TODOS", seccion="TODOS", prenda="")
            con_foto = self.w.tarjetas["Sudadera||Modelo 1"].findChild(type(self.w.resumen), "ropaFoto")
            sin_foto = self.w.tarjetas["Sudadera||Modelo 2"].findChild(type(self.w.resumen), "ropaFoto")
            self.assertIsNotNone(con_foto.pixmap())
            self.assertFalse(con_foto.pixmap().isNull())
            self.assertEqual(sin_foto.text(), "M")

    def test_la_elegida_se_marca(self) -> None:
        self.w.aplicar(_view([_card(1), _card(2)], elegida="Sudadera||Modelo 2"), genero="TODOS", seccion="TODOS", prenda="")
        self.assertEqual(self.w.tarjetas["Sudadera||Modelo 2"].property("elegida"), "true")
        self.assertEqual(self.w.tarjetas["Sudadera||Modelo 1"].property("elegida"), "false")


if __name__ == "__main__":
    unittest.main()
