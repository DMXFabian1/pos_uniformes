"""Avisar cuando lo mandado a otra PC no salió.

Daniel, 2026-11-12: «quise imprimir un corte en el pc principal y no me
aparece». El corte #190 se fue al Kiosko Principal minuto y medio después de
que se apagó (la ventana lo daba por encendido 2.5 min) y nadie avisó.
"""

from __future__ import annotations

import os
import time
import unittest
from contextlib import contextmanager
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.ui.helpers import ticket_routing_helper as rt


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


class SinSalirTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = _session()

    def tearDown(self) -> None:
        self.s.close()

    def _trabajo(self, estado, tipo=TipoTrabajo.CORTE):
        t = svc.encolar(self.s, tipo, {"texto": "x"}, destino="kiosko")
        t.estado = estado
        self.s.flush()
        return t

    def test_solo_los_pendientes_y_los_que_fallaron(self) -> None:
        pend = self._trabajo(EstadoTrabajo.PENDIENTE)
        err = self._trabajo(EstadoTrabajo.ERROR)
        hecho = self._trabajo(EstadoTrabajo.HECHO)
        imprimiendo = self._trabajo(EstadoTrabajo.EN_PROCESO)
        ids = [pend.id, err.id, hecho.id, imprimiendo.id]
        self.assertEqual([t.id for t in svc.sin_salir(self.s, ids)], [pend.id, err.id])

    def test_sin_ids_no_consulta(self) -> None:
        self.assertEqual(svc.sin_salir(self.s, []), [])

    def test_si_todo_salio_no_hay_aviso(self) -> None:
        self.assertIsNone(svc.aviso_no_ha_salido([], "Kiosko Principal"))

    def test_el_corte_sin_tomar_dice_donde_y_que_no_se_repita(self) -> None:
        texto = svc.aviso_no_ha_salido([self._trabajo(EstadoTrabajo.PENDIENTE)], "Kiosko Principal")
        self.assertIn("El corte todavía no sale", texto)
        self.assertIn("Kiosko Principal no lo ha tomado", texto)
        self.assertIn("sale solo en cuanto Kiosko Principal se prenda", texto)
        self.assertIn("no lo vuelvas a hacer", texto)

    def test_un_ticket_no_habla_de_rehacer_el_corte(self) -> None:
        texto = svc.aviso_no_ha_salido([self._trabajo(EstadoTrabajo.PENDIENTE, TipoTrabajo.TICKET)], "Kiosko 2")
        self.assertIn("El ticket todavía no sale", texto)
        self.assertNotIn("corte", texto)

    def test_si_fallo_la_impresora_lo_dice(self) -> None:
        texto = svc.aviso_no_ha_salido([self._trabajo(EstadoTrabajo.ERROR)], "Kiosko Principal")
        self.assertIn("su impresora dio error", texto)


class CancelarLosQueNoSalieronTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = _session()

    def tearDown(self) -> None:
        self.s.close()

    def _trabajo(self, estado, texto):
        t = svc.encolar(self.s, TipoTrabajo.CORTE, {"texto": texto}, destino="kiosko")
        t.estado = estado
        self.s.flush()
        return t

    def test_cancela_lo_pendiente_y_devuelve_su_texto(self) -> None:
        pend = self._trabajo(EstadoTrabajo.PENDIENTE, "CORTE 190")
        imprimiendo = self._trabajo(EstadoTrabajo.EN_PROCESO, "OTRO")
        hecho = self._trabajo(EstadoTrabajo.HECHO, "VIEJO")
        textos = svc.cancelar_los_que_no_salieron(self.s, [pend.id, imprimiendo.id, hecho.id])
        self.assertEqual(textos, ["CORTE 190"])
        self.assertEqual(pend.estado, EstadoTrabajo.CANCELADO)
        self.assertEqual(imprimiendo.estado, EstadoTrabajo.EN_PROCESO)   # ya se está imprimiendo
        self.assertEqual(hecho.estado, EstadoTrabajo.HECHO)

    def test_una_etiqueta_se_llama_etiqueta(self) -> None:
        t = svc.encolar(self.s, TipoTrabajo.ETIQUETA, {"sku": "X"})
        self.assertIn("La etiqueta todavía no sale", svc.aviso_no_ha_salido([t], "la PC de etiquetas"))


class VigilarEnvioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.s = _session()
        self.ventana = QWidget()

    def tearDown(self) -> None:
        self.ventana.deleteLater()
        self.s.close()

    def _esperar(self, avisos: list, segundos: float = 2.0) -> None:
        fin = time.monotonic() + segundos
        while time.monotonic() < fin and not avisos:
            self.app.processEvents()
            time.sleep(0.01)

    def _correr(self) -> list:
        @contextmanager
        def _sesion():
            yield self.s

        avisos: list = []
        with patch("pos_uniformes.database.connection.get_session", _sesion), \
                patch.object(rt, "_imprimir_aqui_si_se_puede", lambda parent: None), \
                patch("PyQt6.QtWidgets.QMessageBox.warning", lambda p, titulo, texto: avisos.append((titulo, texto))):
            enviar = rt._enviar_y_vigilar(
                self.ventana, [{"identificador": "bfaf", "nombre": "Kiosko Principal", "online": True}],
                "principal", TipoTrabajo.CORTE,
            )
            with patch.object(svc, "SEGUNDOS_PARA_REVISAR", 0):
                self.assertEqual(enviar("bfaf", ["CORTE DE CAJA"]), 1)
            self._esperar(avisos)
        return avisos

    def test_si_la_otra_pc_no_lo_toma_avisa_con_su_nombre(self) -> None:
        avisos = self._correr()
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0][0], "Todavía no sale")
        self.assertIn("Kiosko Principal", avisos[0][1])

    def test_si_ya_salio_no_avisa(self) -> None:
        from sqlalchemy import update

        from pos_uniformes.database.models import Trabajo

        @contextmanager
        def _sesion():
            yield self.s

        avisos: list = []
        with patch("pos_uniformes.database.connection.get_session", _sesion), \
                patch("PyQt6.QtWidgets.QMessageBox.warning", lambda p, titulo, texto: avisos.append(texto)), \
                patch.object(svc, "SEGUNDOS_PARA_REVISAR", 0):
            ids = rt.encolar_para_ids("bfaf", ["CORTE"], "principal", tipo=TipoTrabajo.CORTE)
            self.s.execute(update(Trabajo).values(estado=EstadoTrabajo.HECHO))
            self.s.flush()
            rt.vigilar_envio(self.ventana, ids, "Kiosko Principal")
            self._esperar(avisos, 0.3)
        self.assertEqual(avisos, [])

    def test_imprimir_aqui_cancela_alla_y_lo_imprime(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        @contextmanager
        def _sesion():
            yield self.s

        impresos: list = []
        with patch("pos_uniformes.database.connection.get_session", _sesion), \
                patch.object(QMessageBox, "exec", lambda caja: 0), \
                patch.object(QMessageBox, "clickedButton",
                             lambda caja: next(b for b in caja.buttons() if "Imprimir aquí" in b.text())):
            ids = rt.encolar_para_ids("bfaf", ["CORTE 190"], "principal", tipo=TipoTrabajo.CORTE)
            rt.vigilar_envio(self.ventana, ids, "Kiosko Principal", segundos=0, imprimir_aqui=impresos.extend)
            self._esperar(impresos)
        self.assertEqual(impresos, ["CORTE 190"])
        self.assertEqual(svc.sin_salir(self.s, ids), [])   # el de allá quedó cancelado

    def test_sin_ventana_no_hace_nada(self) -> None:
        rt.vigilar_envio(None, [1], "Kiosko")  # no truena


if __name__ == "__main__":
    unittest.main()
