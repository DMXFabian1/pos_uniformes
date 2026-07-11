"""Tests de la Fase 3: emisor de etiquetas, handler y ruteo por máquina."""

from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.services.trabajo_dispatcher import TrabajoDispatcher

_PNG = b"\x89PNG\r\n\x1a\n_fake_label_bytes"


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class EnviarEtiquetaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_enviar_etiqueta_encola_con_imagen(self) -> None:
        t = svc.enviar_etiqueta(
            self.session, _PNG, sku="SKU1", copies=2, paper_mode="split", origen="principal"
        )
        self.assertEqual(t.tipo, TipoTrabajo.ETIQUETA)
        self.assertEqual(t.estado, EstadoTrabajo.PENDIENTE)
        self.assertEqual(t.contenido["sku"], "SKU1")
        self.assertEqual(t.contenido["copies"], 2)
        self.assertEqual(t.contenido["paper_mode"], "split")
        # La imagen viaja en base64.
        self.assertEqual(base64.b64decode(t.contenido["image_b64"]), _PNG)

    def test_enviar_etiqueta_imagen_vacia_falla(self) -> None:
        with self.assertRaises(ValueError):
            svc.enviar_etiqueta(self.session, b"", sku="SKU1")

    def test_datos_de_etiqueta_roundtrip(self) -> None:
        t = svc.enviar_etiqueta(self.session, _PNG, sku="SKU9", copies=4, paper_mode="dk1221")
        imagen, sku, copies, paper_mode = svc.datos_de_etiqueta(t)
        self.assertEqual(imagen, _PNG)
        self.assertEqual(sku, "SKU9")
        self.assertEqual(copies, 4)
        self.assertEqual(paper_mode, "dk1221")

    def test_datos_de_etiqueta_tipo_incorrecto(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        with self.assertRaises(ValueError):
            svc.datos_de_etiqueta(t)


class EtiquetaHandlerTests(unittest.TestCase):
    """El despachador procesa una ETIQUETA llamando al print headless."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def test_dispatcher_imprime_etiqueta(self) -> None:
        from pos_uniformes.ui.helpers.trabajo_print_handlers import build_handlers

        s = self.factory()
        t = svc.enviar_etiqueta(s, _PNG, sku="SKU1", copies=2, paper_mode="standard")
        s.commit()
        tid = t.id
        s.close()

        llamadas = []

        def fake_print(image_path, *, sku, copies, paper_mode):
            # El handler escribió la imagen a un archivo real antes de imprimir.
            llamadas.append((Path(image_path).read_bytes(), sku, copies, paper_mode))

        with patch(
            "pos_uniformes.ui.helpers.satellite_label_print_helper.print_label_image_headless",
            side_effect=fake_print,
        ):
            disp = TrabajoDispatcher(self.factory, build_handlers())
            resultado = disp.poll_once()

        self.assertEqual(resultado, EstadoTrabajo.HECHO)
        self.assertEqual(len(llamadas), 1)
        imagen, sku, copies, paper_mode = llamadas[0]
        self.assertEqual(imagen, _PNG)
        self.assertEqual((sku, copies, paper_mode), ("SKU1", 2, "standard"))
        s = self.factory()
        self.assertEqual(svc.obtener(s, tid).estado, EstadoTrabajo.HECHO)
        s.close()


class LabelRoutingTests(unittest.TestCase):
    """El guard maybe_route_label_to_satellite según el modo por máquina."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.img = self.data_dir / "label.png"
        self.img.write_bytes(_PNG)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_modo_local_devuelve_false(self) -> None:
        from pos_uniformes.ui.helpers.label_routing_helper import maybe_route_label_to_satellite

        # Sin cache => default LOCAL => no rutea.
        with patch(
            "pos_uniformes.services.print_routing_cache_service.satellite_data_dir",
            return_value=self.data_dir,
        ):
            resultado = maybe_route_label_to_satellite(
                self.img, sku="SKU1", copies=1, paper_mode="standard"
            )
        self.assertFalse(resultado)

    def test_modo_satelite_encola_y_devuelve_true(self) -> None:
        from pos_uniformes.services.print_routing_cache_service import (
            MODO_SATELITE,
            save_print_routing,
        )
        from pos_uniformes.ui.helpers.label_routing_helper import (
            maybe_route_label_to_satellite,
        )

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with patch(
            "pos_uniformes.services.print_routing_cache_service.satellite_data_dir",
            return_value=self.data_dir,
        ):
            save_print_routing(MODO_SATELITE, "principal")
            with patch(
                "pos_uniformes.database.connection.get_session",
                side_effect=lambda: Session(engine),
            ), patch("PyQt6.QtWidgets.QMessageBox.information"):
                resultado = maybe_route_label_to_satellite(
                    self.img, sku="SKU1", copies=2, paper_mode="split"
                )

        self.assertTrue(resultado)
        # Sesión fresca sobre el mismo engine para verificar lo persistido.
        session = Session(engine)
        etiquetas = svc.listar(session, tipos=[TipoTrabajo.ETIQUETA])
        self.assertEqual(len(etiquetas), 1)
        self.assertEqual(etiquetas[0].contenido["sku"], "SKU1")
        self.assertEqual(etiquetas[0].origen, "principal")
        session.close()


if __name__ == "__main__":
    unittest.main()
