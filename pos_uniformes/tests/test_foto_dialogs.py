"""La foto del modelo desde el POS: la ventana de captura y su botón en «Por nombrar»."""

from __future__ import annotations

import io
import os
import unittest
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from pos_uniformes.database.connection import Base  # noqa: E402
from pos_uniformes.database.models import Categoria, Marca, Producto, RolUsuario, Usuario, Variante  # noqa: E402
from pos_uniformes.services import producto_foto_service as fotos  # noqa: E402
from pos_uniformes.ui.dialogs.foto_producto_dialog import FotoProductoDialog  # noqa: E402
from pos_uniformes.ui.dialogs.por_nombrar_dialog import PorNombrarDialog  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _jpeg(ancho=900, alto=1200) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), (120, 40, 40)).save(salida, format="JPEG")
    return salida.getvalue()


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        with self._sesion() as s:
            cat, marca = Categoria(nombre="Ropa casual"), Marca(nombre="Darong")
            admin = Usuario(username="admin", nombre_completo="Admin", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
            s.add_all([cat, marca, admin])
            s.flush()
            p = Producto(nombre="YT0572", nombre_base="YT0572", categoria=cat, marca=marca, genero="Mujer", por_identificar=True)
            s.add(p)
            s.flush()
            s.add(Variante(producto_id=p.id, sku="SKU005647", talla="Unitalla", color="Surtido", precio_venta=Decimal("99.00"), stock_actual=30))
            s.commit()
            self.pid, self.admin_id = p.id, admin.id
        self._quieto = patch.object(fotos, "_avisar_catalogo")
        self._quieto.start()

    def tearDown(self) -> None:
        self._quieto.stop()

    @contextmanager
    def _sesion(self):
        s = Session(self.engine)
        try:
            yield s
        finally:
            s.close()


class FotoProductoDialogTests(_ConBase):
    def _ventana(self) -> FotoProductoDialog:
        d = FotoProductoDialog(producto_id=self.pid, titulo="YT0572", session_factory=self._sesion, con_camara=False)
        self.addCleanup(d.deleteLater)
        return d

    def test_sin_camara_se_puede_subir_archivo_y_quitar(self) -> None:
        d = self._ventana()
        self.assertFalse(d.tomar_btn.isEnabled())
        self.assertEqual(d.actual.text(), "Sin foto")
        d.guardar(_jpeg())
        self.assertTrue(d.cambio)
        self.assertEqual(d.actual.text(), "")                      # ya enseña la foto
        with self._sesion() as s:
            self.assertTrue(fotos.hash_de(s, self.pid))
        d._quitar()
        self.assertEqual(d.actual.text(), "Sin foto")

    def test_un_archivo_que_no_es_foto_lo_dice(self) -> None:
        d = self._ventana()
        d.guardar(b"no es una foto")
        self.assertIn("imagen", d.estado.text())
        self.assertFalse(d.cambio)

    def test_si_la_camara_falla_al_abrir_queda_el_archivo(self) -> None:
        def _sin_camara(_video):
            raise RuntimeError("Esta PC no tiene cámara.")

        d = FotoProductoDialog(producto_id=self.pid, session_factory=self._sesion, camara_factory=_sin_camara,
                               video_factory=lambda: __import__("PyQt6.QtWidgets", fromlist=["QWidget"]).QWidget())
        self.addCleanup(d.deleteLater)
        self.assertFalse(d.tomar_btn.isEnabled())
        self.assertTrue(d.archivo_btn.isEnabled())

    def test_con_camara_tomar_foto_guarda(self) -> None:
        from PyQt6.QtGui import QColor, QImage
        from PyQt6.QtWidgets import QWidget

        class _CamaraFalsa:
            nombre = "Webcam de prueba"

            def __init__(self, _video):
                pass

            def iniciar(self):
                pass

            def detener(self):
                pass

            def tomar(self, al_capturar):
                img = QImage(640, 480, QImage.Format.Format_RGB32)
                img.fill(QColor(90, 20, 20))
                al_capturar(img)

        d = FotoProductoDialog(producto_id=self.pid, session_factory=self._sesion,
                               camara_factory=_CamaraFalsa, video_factory=QWidget)
        self.addCleanup(d.deleteLater)
        self.assertTrue(d.tomar_btn.isEnabled())
        d._tomar()
        self.assertTrue(d.cambio)
        with self._sesion() as s:
            self.assertTrue(fotos.miniatura(s, self.pid))


class PorNombrarConFotoTests(_ConBase):
    def test_la_bandeja_ensena_la_foto_si_hay(self) -> None:
        d = PorNombrarDialog(session_factory=self._sesion, user_id=self.admin_id, on_print_labels=None)
        self.addCleanup(d.deleteLater)
        self.assertEqual(d.foto.text(), "Sin foto")
        with self._sesion() as s:
            fotos.guardar(s, self.pid, _jpeg())
            s.commit()
        d._pintar_foto()
        self.assertEqual(d.foto.text(), "")
        self.assertIsNotNone(d.foto.pixmap())


if __name__ == "__main__":
    unittest.main()
