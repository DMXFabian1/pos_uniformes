"""Tests de la Fase 4: emisor de conteo, handler y ruteo por máquina."""

from __future__ import annotations

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


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class EnviarConteoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def test_enviar_conteo_encola_hojas(self) -> None:
        t = svc.enviar_conteo(
            self.session, ["hoja 1", "hoja 2"], titulo="Conteo Primaria", origen="principal"
        )
        self.assertIsNotNone(t)
        self.assertEqual(t.tipo, TipoTrabajo.CONTEO)
        self.assertEqual(t.contenido["hojas"], ["hoja 1", "hoja 2"])
        self.assertEqual(t.contenido["titulo"], "Conteo Primaria")

    def test_enviar_conteo_ignora_vacias(self) -> None:
        t = svc.enviar_conteo(self.session, ["", "  ", "real"])
        self.assertEqual(t.contenido["hojas"], ["real"])

    def test_enviar_conteo_sin_hojas_devuelve_none(self) -> None:
        self.assertIsNone(svc.enviar_conteo(self.session, ["", "   "]))

    def test_hojas_de_conteo_roundtrip(self) -> None:
        t = svc.enviar_conteo(self.session, ["a", "b", "c"])
        self.assertEqual(svc.hojas_de_conteo(t), ["a", "b", "c"])

    def test_hojas_de_conteo_tipo_incorrecto(self) -> None:
        t = svc.enviar_ticket(self.session, "X")
        with self.assertRaises(ValueError):
            svc.hojas_de_conteo(t)


class ConteoHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def test_dispatcher_imprime_todas_las_hojas(self) -> None:
        from pos_uniformes.ui.helpers.trabajo_print_handlers import build_handlers

        s = self.factory()
        t = svc.enviar_conteo(s, ["A", "B", "C"], titulo="Conteo")
        s.commit()
        tid = t.id
        s.close()

        impresas = []
        with patch(
            "pos_uniformes.ui.dialogs.printable_text_dialog.print_conteo_sheet",
            side_effect=lambda hoja: impresas.append(hoja) or True,
        ), patch(
            "pos_uniformes.ui.helpers.trabajo_print_handlers._qt_sleep"
        ) as sleep_mock:
            disp = TrabajoDispatcher(self.factory, build_handlers())
            resultado = disp.poll_once()

        self.assertEqual(resultado, EstadoTrabajo.HECHO)
        self.assertEqual(impresas, ["A", "B", "C"])
        # Pausó entre las 3 hojas (2 pausas), no después de la última.
        self.assertEqual(sleep_mock.call_count, 2)
        s = self.factory()
        self.assertEqual(svc.obtener(s, tid).estado, EstadoTrabajo.HECHO)
        s.close()

    def test_dispatcher_marca_error_si_falla_una_hoja(self) -> None:
        from pos_uniformes.ui.helpers.trabajo_print_handlers import build_handlers

        s = self.factory()
        t = svc.enviar_conteo(s, ["A", "B"])
        s.commit()
        tid = t.id
        s.close()

        # La segunda hoja falla (print_conteo_sheet devuelve False).
        def flaky(hoja):
            return hoja != "B"

        with patch(
            "pos_uniformes.ui.dialogs.printable_text_dialog.print_conteo_sheet",
            side_effect=flaky,
        ), patch("pos_uniformes.ui.helpers.trabajo_print_handlers._qt_sleep"):
            # max_intentos=1 => el fallo va directo a ERROR (sin reintento).
            disp = TrabajoDispatcher(self.factory, build_handlers(), max_intentos=1)
            resultado = disp.poll_once()

        self.assertEqual(resultado, EstadoTrabajo.ERROR)
        s = self.factory()
        t = svc.obtener(s, tid)
        self.assertEqual(t.estado, EstadoTrabajo.ERROR)
        self.assertIn("1 de 2", t.error_msg)
        s.close()


class PacingTests(unittest.TestCase):
    """imprimir_hojas_paced: pausa entre hojas como el apartado, sin Qt."""

    def test_pausa_entre_hojas_no_despues_de_la_ultima(self) -> None:
        from pos_uniformes.ui.helpers.trabajo_print_handlers import imprimir_hojas_paced

        impresas, pausas = [], []
        errores = imprimir_hojas_paced(
            ["A", "B", "C"],
            print_fn=lambda h: impresas.append(h) or True,
            sleep_fn=lambda s: pausas.append(s),
        )
        self.assertEqual(errores, 0)
        self.assertEqual(impresas, ["A", "B", "C"])
        self.assertEqual(len(pausas), 2)  # 3 hojas -> 2 pausas

    def test_una_hoja_no_pausa(self) -> None:
        from pos_uniformes.ui.helpers.trabajo_print_handlers import imprimir_hojas_paced

        pausas = []
        imprimir_hojas_paced(
            ["sola"], print_fn=lambda h: True, sleep_fn=lambda s: pausas.append(s)
        )
        self.assertEqual(pausas, [])

    def test_cuenta_errores(self) -> None:
        from pos_uniformes.ui.helpers.trabajo_print_handlers import imprimir_hojas_paced

        errores = imprimir_hojas_paced(
            ["A", "B", "C"],
            print_fn=lambda h: h != "B",  # B falla
            sleep_fn=lambda s: None,
        )
        self.assertEqual(errores, 1)


class ConteoRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_modo_local_devuelve_false(self) -> None:
        from pos_uniformes.ui.helpers.conteo_routing_helper import (
            maybe_route_conteo_to_satellite,
        )

        with patch(
            "pos_uniformes.services.print_routing_cache_service.satellite_data_dir",
            return_value=self.data_dir,
        ):
            resultado = maybe_route_conteo_to_satellite(
                ["hoja"], titulo="Conteo"
            )
        self.assertFalse(resultado)

    def test_modo_satelite_encola(self) -> None:
        from pos_uniformes.services.print_routing_cache_service import (
            MODO_SATELITE,
            save_print_routing,
        )
        from pos_uniformes.ui.helpers.conteo_routing_helper import (
            maybe_route_conteo_to_satellite,
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
                resultado = maybe_route_conteo_to_satellite(
                    ["h1", "h2"], titulo="Conteo Primaria"
                )

        self.assertTrue(resultado)
        session = Session(engine)
        conteos = svc.listar(session, tipos=[TipoTrabajo.CONTEO])
        self.assertEqual(len(conteos), 1)
        self.assertEqual(conteos[0].contenido["titulo"], "Conteo Primaria")
        self.assertEqual(conteos[0].origen, "principal")
        session.close()


if __name__ == "__main__":
    unittest.main()
