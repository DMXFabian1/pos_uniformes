"""Los mensajes de inventario, pulso, respaldo, avisos y actualizar abren con
el encabezado común del bot (Daniel, 2026-11-20: «Sí, en todos»).

No se manda nada a Telegram: son funciones que devuelven texto.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.services import telegram_actualizar_service as tact
from pos_uniformes.services import telegram_avisos_service as av
from pos_uniformes.services import telegram_inventario_service as inv
from pos_uniformes.services import telegram_pulso_service as pul
from pos_uniformes.services import telegram_respaldo_service as rs
from pos_uniformes.services.telegram_formato import es_encabezado


def _abre_con_encabezado(caso: unittest.TestCase, texto: str) -> None:
    primera = texto.splitlines()[0]
    caso.assertTrue(es_encabezado(primera), f"sin encabezado: {primera!r}")


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.s.close)


class InventarioTests(_ConBase):
    def test_contar_sin_pendientes(self) -> None:
        with patch("pos_uniformes.services.conteo_jornada_service.lo_que_toca", return_value=[]):
            _abre_con_encabezado(self, inv.contar(self.s))

    def test_faltas_lleva_la_fecha(self) -> None:
        texto = inv.faltas(self.s, 7, hoy=date(2026, 11, 20))
        _abre_con_encabezado(self, texto)
        self.assertIn("vie 20 nov", texto.splitlines()[0])


class PulsoTests(_ConBase):
    def test_encabezado_con_hora_y_la_cifra_debajo(self) -> None:
        ahora = datetime(2026, 11, 20, 12, 30).astimezone()
        with patch.object(pul, "_respaldo", return_value=["✅ Respaldo: hoy"]):
            texto = pul.pulso(self.s, hoy=ahora.date(), ahora=ahora)
        _abre_con_encabezado(self, texto)
        self.assertIn("12:30", texto.splitlines()[0])
        self.assertTrue(texto.splitlines()[1].startswith("💰 $"))


class RespaldoTests(unittest.TestCase):
    def test_el_toque_contesta_con_encabezado(self) -> None:
        with patch.object(rs, "_correr_respaldo", return_value=(True, "✅ listo")), \
             patch("threading.Thread") as hilo:
            _aviso, texto, _botones = rs.atender("rs:ahora", enviar=MagicMock())
        hilo.assert_called_once()
        rs._EN_CURSO.release()  # el hilo no corrió: se suelta a mano
        _abre_con_encabezado(self, texto)


class AvisosTests(unittest.TestCase):
    def test_acuse_con_encabezado(self) -> None:
        texto = av.aviso_de_acuse(etiqueta="Junta a las 6", empleada="Evelyn",
                                  pantalla="Entrada", faltan=1)
        _abre_con_encabezado(self, texto)
        self.assertIn("Evelyn vio el aviso en Entrada", texto)

    def test_la_ayuda_con_encabezado(self) -> None:
        _abre_con_encabezado(self, av.AYUDA_CORTA)


class ActualizarTests(unittest.TestCase):
    def test_como_esta_con_encabezado(self) -> None:
        texto = tact.atender_actualizar("", es_windows=True, arrancar=MagicMock(),
                                        estado=lambda: "PC principal: 6 nov · abc")
        _abre_con_encabezado(self, texto)
        self.assertIn("/actualizar si", texto)

    def test_version_y_volver(self) -> None:
        _abre_con_encabezado(self, tact.atender_version(estado=lambda: "PC principal: x"))
        _abre_con_encabezado(self, tact.atender_volver(""))


if __name__ == "__main__":
    unittest.main()
