"""Mandar un ticket a la impresora de OTRA PC desde la ventana de imprimir.

Daniel, 2026-11-05: «¿hay una forma de enviar un ticket a la otra impresora,
por si algo llegara a fallar?» — y que se elija ahí mismo, como el tamaño de
la etiqueta. Antes había que entrar al menú admin y desmarcar una casilla.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, Satelite, TipoTrabajo
from pos_uniformes.services import satelite_registry_service as registro
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.ui.dialogs import printable_text_dialog as ventana

AHORA = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class LaColaRespetaElDestinoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = _session()

    def tearDown(self) -> None:
        self.s.close()

    def test_el_kiosko_no_se_queda_con_el_ticket_que_mando_a_la_principal(self) -> None:
        t = svc.enviar_ticket(self.s, "TICKET", origen="kiosko", destino="pc-principal")
        self.assertIsNone(svc.reclamar_siguiente(self.s, para="kiosko-1"))
        self.assertEqual(t.estado, EstadoTrabajo.PENDIENTE)
        tomado = svc.reclamar_siguiente(self.s, para="pc-principal")
        self.assertEqual(tomado.id, t.id)
        self.assertEqual(tomado.estado, EstadoTrabajo.EN_PROCESO)

    def test_lo_que_no_va_dirigido_lo_toma_cualquiera(self) -> None:
        t = svc.enviar_ticket(self.s, "TICKET")
        self.assertIsNone(t.destino)
        self.assertEqual(svc.reclamar_siguiente(self.s, para="kiosko-1").id, t.id)

    def test_un_ticket_dirigido_a_otra_no_tapa_los_que_siguen(self) -> None:
        svc.enviar_ticket(self.s, "PARA LA PRINCIPAL", destino="pc-principal")
        mio = svc.enviar_ticket(self.s, "DE CUALQUIERA")
        self.assertEqual(svc.reclamar_siguiente(self.s, para="kiosko-1").id, mio.id)
        self.assertEqual(svc.siguiente_pendiente(self.s, para="pc-principal").contenido["texto"], "PARA LA PRINCIPAL")

    def test_sin_identificador_se_porta_como_siempre(self) -> None:
        t = svc.enviar_ticket(self.s, "TICKET", destino="pc-principal")
        self.assertEqual(svc.reclamar_siguiente(self.s).id, t.id)


class OtrasImpresorasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = _session()
        self.s.add_all([
            Satelite(identificador="kiosko-1", nombre="Kiosko Principal", ultimo_visto=AHORA, imprime="TICKET,ETIQUETA"),
            Satelite(identificador="pc-principal", nombre="PC principal", ultimo_visto=AHORA, imprime="TICKET,CORTE"),
            Satelite(identificador="kiosko-2", nombre="Kiosko 2", ultimo_visto=AHORA - timedelta(hours=3), imprime="TICKET"),
            Satelite(identificador="etiquetas", nombre="Solo etiquetas", ultimo_visto=AHORA, imprime="ETIQUETA"),
            Satelite(identificador="retirada", nombre="Retirada", ultimo_visto=AHORA - timedelta(days=20), imprime="TICKET"),
            Satelite(identificador="vieja", nombre="Build viejo", ultimo_visto=AHORA, imprime=None),
        ])
        self.s.flush()

    def tearDown(self) -> None:
        self.s.close()

    def test_lista_las_otras_que_imprimen_tickets_primero_las_encendidas(self) -> None:
        otras = registro.otras_impresoras(self.s, "TICKET", "kiosko-1", ahora=AHORA)
        self.assertEqual(
            [(d["nombre"], d["online"]) for d in otras],
            [("PC principal", True), ("Kiosko 2", False)],
        )

    def test_el_latido_publica_lo_que_imprime_esta_pc(self) -> None:
        with patch.object(registro, "_lo_que_imprime_esta_pc", return_value="TICKET,CORTE"), patch.object(
            registro, "es_de_desarrollo", return_value=False
        ):
            nueva = registro.registrar(self.s, "nueva", "Nueva", ahora=AHORA)
            vieja = registro.registrar(self.s, "vieja", "Build viejo", ahora=AHORA)
        self.assertEqual(nueva.imprime, "TICKET,CORTE")
        self.assertEqual(vieja.imprime, "TICKET,CORTE")


class ElServidorDeImpresionLateTests(unittest.TestCase):
    """Con el kiosko cerrado, la PC que imprime tiene que seguir saliendo encendida."""

    def test_late_y_publica_lo_que_imprime(self) -> None:
        from contextlib import contextmanager

        from pos_uniformes.ui.helpers import servidor_impresion_runner as runner

        s = _session()

        @contextmanager
        def fabrica():
            yield s

        with patch("pos_uniformes.services.satellite_identity_service.get_satellite_id", return_value="pc-principal"), patch(
            "pos_uniformes.services.satellite_identity_service.get_satellite_name", return_value="PC principal"
        ), patch.object(registro, "_lo_que_imprime_esta_pc", return_value="TICKET"), patch.object(
            registro, "es_de_desarrollo", return_value=False
        ):
            self.assertTrue(runner.latir(fabrica))
        otras = registro.otras_impresoras(s, "TICKET", "kiosko-1")
        self.assertEqual([(d["nombre"], d["online"]) for d in otras], [("PC principal", True)])
        s.close()

    def test_sin_base_no_truena(self) -> None:
        from pos_uniformes.ui.helpers import servidor_impresion_runner as runner

        def fabrica():
            raise RuntimeError("sin conexión")

        self.assertFalse(runner.latir(fabrica))


class LaVentanaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _abrir(self, accion, **kw):
        """Abre la ventana sin bloquear: `accion(dialog)` hace de la empleada."""
        impresos, enviados, avisos = [], [], []

        def exec_falso(dlg):
            accion(dlg)
            return 0

        with patch.object(QDialog, "exec", exec_falso), patch.object(
            QMessageBox, "information", lambda *a, **k: avisos.append(a[2])
        ), patch.object(QMessageBox, "warning", lambda *a, **k: avisos.append(a[2])):
            ventana.open_tickets_print_dialog(
                None, "Venta", ["TICKET 1"],
                print_fn=lambda texto: impresos.append(texto) or True,
                on_printed=lambda: impresos.append("ANOTADA"),
                enviar_a=kw.pop("enviar_a", lambda d, textos: enviados.append((d, list(textos))) or len(textos)),
                **kw,
            )
        return impresos, enviados, avisos

    DESTINOS = [
        {"identificador": "pc-principal", "nombre": "PC principal", "online": True},
        {"identificador": "kiosko-2", "nombre": "Kiosko 2", "online": False},
    ]

    @staticmethod
    def _boton_imprimir(dlg) -> QPushButton:
        return next(b for b in dlg.findChildren(QPushButton) if b.objectName() == "ticketImprimir")

    def test_sin_otras_impresoras_la_ventana_queda_como_siempre(self) -> None:
        vistos = {}
        self._abrir(lambda dlg: vistos.update(fichas=getattr(dlg, "destino_botones", None)), destinos=[])
        self.assertIsNone(vistos["fichas"])

    def test_arranca_en_esta_pc_y_la_apagada_no_se_puede_elegir(self) -> None:
        vistos = {}

        def accion(dlg):
            b = dlg.destino_botones
            vistos.update(aqui=b[""].isChecked(), principal=b["pc-principal"].isEnabled(),
                          apagada=b["kiosko-2"].isEnabled(), texto=b["kiosko-2"].text(),
                          boton=self._boton_imprimir(dlg).text())

        self._abrir(accion, destinos=self.DESTINOS)
        self.assertTrue(vistos["aqui"] and vistos["principal"])
        self.assertFalse(vistos["apagada"])
        self.assertIn("apagada", vistos["texto"])
        self.assertIn("Imprimir", vistos["boton"])

    def test_eligiendo_otra_el_ticket_se_manda_y_no_se_imprime_aqui(self) -> None:
        vistos = {}

        def accion(dlg):
            dlg.destino_botones["pc-principal"].click()
            vistos["boton"] = self._boton_imprimir(dlg).text()
            self._boton_imprimir(dlg).click()

        impresos, enviados, avisos = self._abrir(accion, destinos=self.DESTINOS)
        self.assertIn("Mandar a PC principal", vistos["boton"])
        self.assertEqual(enviados, [("pc-principal", ["TICKET 1"])])
        self.assertEqual(impresos, ["ANOTADA"])          # la venta sí se anota; aquí no salió papel
        self.assertIn("en camino a PC principal", avisos[0])

    def test_si_no_se_pudo_mandar_lo_dice_y_la_venta_no_se_anota(self) -> None:
        def falla(_d, _t):
            raise RuntimeError("sin conexión")

        def accion(dlg):
            dlg.destino_botones["pc-principal"].click()
            self._boton_imprimir(dlg).click()

        impresos, _enviados, avisos = self._abrir(accion, destinos=self.DESTINOS, enviar_a=falla)
        self.assertEqual(impresos, [])
        self.assertIn("No se pudo mandar a PC principal", avisos[0])

    def test_volver_a_aqui_regresa_el_boton_de_imprimir(self) -> None:
        vistos = {}

        def accion(dlg):
            dlg.destino_botones["pc-principal"].click()
            dlg.destino_botones[""].click()
            vistos["boton"] = self._boton_imprimir(dlg).text()
            vistos["aqui"] = dlg.destino_botones[""].isChecked()

        self._abrir(accion, destinos=self.DESTINOS)
        self.assertIn("Imprimir", vistos["boton"])
        self.assertTrue(vistos["aqui"])


if __name__ == "__main__":
    unittest.main()
