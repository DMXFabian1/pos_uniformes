"""La ventana «Mercancía por nombrar» del POS: escoger, nombrar, imprimir etiquetas."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from pos_uniformes.database.connection import Base  # noqa: E402
from pos_uniformes.database.models import (  # noqa: E402
    Categoria,
    Marca,
    Producto,
    RolUsuario,
    TipoPieza,
    Usuario,
    Variante,
)
from pos_uniformes.ui.dialogs.por_nombrar_dialog import PorNombrarDialog  # noqa: E402

_app = QApplication.instance() or QApplication([])


class PorNombrarDialogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        with self._sesion() as s:
            cat, marca = Categoria(nombre="Ropa casual"), Marca(nombre="Darong")
            admin = Usuario(username="admin", nombre_completo="Admin", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
            s.add_all([cat, marca, admin, TipoPieza(nombre="Sudadera")])
            s.flush()
            self.admin_id = admin.id
            self.ids = []
            for nombre in ("YT0572", "MO194"):
                p = Producto(nombre=nombre, nombre_base=nombre, categoria=cat, marca=marca, genero="Mujer", por_identificar=True)
                s.add(p)
                s.flush()
                s.add(Variante(producto_id=p.id, sku=f"SKU{p.id:06d}", talla="Unitalla", color="Surtido",
                               precio_venta=Decimal("99.00"), stock_actual=30))
                self.ids.append(p.id)
            s.commit()
        self._quieto = patch("pos_uniformes.services.catalog_service.CatalogService._notify_meili")
        self._quieto.start()
        self.impresas: list[list[int]] = []
        self.refrescos = 0

    def tearDown(self) -> None:
        self._quieto.stop()

    @contextmanager
    def _sesion(self):
        s = Session(self.engine)
        try:
            yield s
        finally:
            s.close()

    def _ventana(self, **extra) -> PorNombrarDialog:
        d = PorNombrarDialog(
            session_factory=self._sesion, user_id=self.admin_id,
            on_print_labels=self.impresas.append,
            on_changed=lambda: setattr(self, "refrescos", self.refrescos + 1),
            **extra,
        )
        self.addCleanup(d.deleteLater)
        return d

    def test_lista_lo_pendiente_y_abre_el_primero(self) -> None:
        d = self._ventana()
        self.assertEqual(d.lista.count(), 2)
        self.assertEqual(d.nombre.text(), "YT0572")
        self.assertIn("2 productos", d.pista.text())

    def test_guardar_y_listo_lo_saca_y_pasa_al_siguiente(self) -> None:
        d = self._ventana()
        d.nombre.setText("Chamarra YT0572")
        d.pieza.setCurrentText("Chamarra")
        d.color.setText("Negro")
        d.guardar(listo=True)
        self.assertEqual(d.lista.count(), 1)
        self.assertEqual(d.nombre.text(), "MO194")
        self.assertEqual(self.refrescos, 1)
        with self._sesion() as s:
            p = s.get(Producto, self.ids[0])
            self.assertEqual((p.nombre, p.tipo_pieza.nombre, p.por_identificar), ("Chamarra YT0572", "Chamarra", False))

    def test_sin_pieza_lo_dice_y_no_lo_saca(self) -> None:
        d = self._ventana()
        d.nombre.setText("Algo YT0572")
        d.guardar(listo=True)
        self.assertIn("pieza", d.estado.text())
        self.assertEqual(d.lista.count(), 2)

    def test_a_medias_se_queda_en_la_lista_con_lo_que_lleva(self) -> None:
        d = self._ventana()
        d.nombre.setText("Chamarra YT0572")
        d.guardar(listo=False)
        self.assertEqual(d.lista.count(), 2)
        self.assertEqual(d.nombre.text(), "Chamarra YT0572")      # sigue en el mismo

    def test_imprimir_etiquetas_manda_las_tallas(self) -> None:
        d = self._ventana()
        d._imprimir_actual()
        d._imprimir_todo()
        self.assertEqual(len(self.impresas[0]), 1)
        self.assertEqual(len(self.impresas[1]), 2)

    def test_sin_nada_pendiente_lo_dice(self) -> None:
        with self._sesion() as s:
            for p in s.query(Producto).all():
                p.por_identificar = False
            s.commit()
        d = self._ventana()
        self.assertIn("No hay nada", d.pista.text())
        self.assertFalse(d.listo_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
