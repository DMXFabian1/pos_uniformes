"""Formato común de los mensajes del bot, grupo «pagos» (Daniel, 2026-11-20).

Pagos, Mi pago, préstamos, descansos, vacaciones y programas: la primera
línea de cada mensaje principal es el encabezado («💰 PAGOS PENDIENTES · vie
20 nov») y, cuando hay una cifra que importa, va justo debajo. Nada de esto
manda mensajes de verdad a Telegram.
"""

from __future__ import annotations

import json
import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pos_uniformes.services import telegram_descansos_service as dsc
from pos_uniformes.services import telegram_membresias_service as tm
from pos_uniformes.services import telegram_pagos_service as pg
from pos_uniformes.services import telegram_prestamos_service as prs
from pos_uniformes.services import telegram_vacaciones_service as tv
from pos_uniformes.services.telegram_formato import es_encabezado
from tests.test_telegram_mi_pago import JUE_19, _ConBase

HOY = date(2026, 11, 20)


def _primera(texto: str) -> str:
    return texto.splitlines()[0]


class _Det:
    desde, hasta = date(2026, 11, 13), date(2026, 11, 20)
    por_dia = False
    sueldo_base = Decimal("1300.00")
    comisiones = 56
    tarifa_comision = Decimal("2.00")
    monto_comisiones = Decimal("112.00")
    faltas = 0
    total = Decimal("1412.00")


class PagosTests(unittest.TestCase):
    def test_pagos_pendientes_lleva_encabezado_y_el_total_debajo(self) -> None:
        from pos_uniformes.services import nomina_service as nom

        aviso = SimpleNamespace(employee_code="VEND-5")
        with patch.object(nom, "avisos_de_pago", return_value=[aviso, aviso]), \
             patch.object(nom, "pago_pendiente", return_value=_Det()), \
             patch.object(nom, "cuando_pago", return_value="hoy"), \
             patch.object(pg, "_nombre", return_value="Fanny"):
            texto = pg.pagos(object(), hoy=HOY)
        self.assertTrue(es_encabezado(_primera(texto)))
        self.assertEqual(_primera(texto), "💰 PAGOS PENDIENTES · vie 20 nov")
        self.assertEqual(texto.splitlines()[1], "💰 $2,824.00 en total")

    def test_el_desglose_lleva_el_nombre_arriba_y_su_total(self) -> None:
        from pos_uniformes.services import nomina_service as nom

        with patch.object(pg, "existe_y_trabaja", return_value=True), \
             patch.object(nom, "pago_pendiente", return_value=_Det()), \
             patch.object(pg, "_nombre", return_value="Fanny"):
            texto = pg.desglose_por_code(object(), "VEND-5", hoy=HOY)
        self.assertEqual(_primera(texto), "💵 PAGO A FANNY · vie 20 nov")
        self.assertIn("$1,412.00 a pagar", texto.splitlines()[1])
        self.assertIn("TOTAL: $1,412.00", texto)

    def test_el_retiro_hecho_lleva_encabezado_con_hora(self) -> None:
        from pos_uniformes.services import retiros_service

        with patch.object(retiros_service, "registrar_retiro"), \
             patch.object(pg, "_en_cajon", return_value=None):
            texto = pg.retiro(MagicMock(), "500 gasolina", quien="VEND-1")
        self.assertTrue(es_encabezado(_primera(texto)))
        self.assertIn("$500.00 para gasolina", texto.splitlines()[1])


class PrestamosTests(unittest.TestCase):
    def _prestamo(self):
        return SimpleNamespace(
            id=3, employee_code="VEND-5", employee_name="Fanny Ortiz", monto=Decimal("500.00"),
            tipo="prestamo", motivo="Doctor", created_at=datetime(2026, 11, 20, 12, 30),
        )

    def test_el_aviso_de_prestamo_empieza_con_encabezado(self) -> None:
        texto = prs.aviso_de_solicitud(self._prestamo())
        self.assertEqual(_primera(texto), "💵 PRÉSTAMO · vie 20 nov · 12:30")
        self.assertIn("$500.00 · Fanny Ortiz pide prestado", texto.splitlines()[1])

    def test_lo_que_se_decide_tambien(self) -> None:
        for aprobado in (True, False):
            with self.subTest(aprobado=aprobado):
                self.assertTrue(es_encabezado(_primera(prs.texto_al_decidir(self._prestamo(), aprobado))))


class DescansosVacacionesTests(unittest.TestCase):
    def test_el_aviso_de_descanso_lleva_el_dia_pedido(self) -> None:
        s = SimpleNamespace(id=7, employee_code="VEND-5", employee_name="Cristal Torres",
                            fecha=date(2026, 11, 21), motivo="Escuela", estado="pedido")
        texto = dsc.aviso_de_solicitud(s, session=None, hoy=HOY)
        self.assertEqual(_primera(texto), "🛌 PIDE DESCANSO · sáb 21 nov")
        self.assertIn("Cristal Torres pide descansar", texto)

    def test_el_aviso_de_vacaciones_sin_panorama(self) -> None:
        s = SimpleNamespace(id=12, employee_code="VEND-4", employee_name="Stayce",
                            desde=date(2026, 12, 1), hasta=date(2026, 12, 6), dias=5)
        texto = tv.aviso_de_solicitud(s)
        self.assertEqual(_primera(texto), "🏖️ VACACIONES #12 · mar 1 dic")
        # El aviso ya trae el botón «🏖️ Ver todas»: sin «/vacaciones» escrito.
        self.assertNotIn("/vacaciones", texto)


class ProgramasTests(unittest.TestCase):
    def test_las_caducadas_llevan_encabezado(self) -> None:
        m = SimpleNamespace(cliente_id=1, programa=SimpleNamespace(nombre="Maximoda Profesional"))
        with patch.object(tm, "_cliente", return_value=SimpleNamespace(nombre="Lupita")):
            texto = tm.aviso_de_caducadas(object(), [m])
        self.assertTrue(es_encabezado(_primera(texto)))
        self.assertIn("Lupita → Maximoda Profesional", texto)


class MiPagoTests(_ConBase):
    def test_mipago_lleva_encabezado_lo_que_toca_y_el_boton_de_dias(self) -> None:
        self._configurar(JUE_19)
        texto, botones = self._responder("/mipago")
        self.assertEqual(_primera(texto), "💼 MI PAGO · jue 19 nov")
        self.assertIn("toca el sáb 21 nov", texto.splitlines()[1])
        datos = [b["callback_data"] for fila in json.loads(botones)["inline_keyboard"] for b in fila]
        self.assertIn("mp:dias", datos)
        self.assertNotIn("/diasdemas", texto)

    def test_mepagaron_y_diasdemas_tambien(self) -> None:
        self._configurar(JUE_19)
        for comando in ("/mepagaron", "/diasdemas"):
            with self.subTest(comando=comando):
                self.assertTrue(es_encabezado(_primera(self._responder(comando)[0])))


if __name__ == "__main__":
    unittest.main()
