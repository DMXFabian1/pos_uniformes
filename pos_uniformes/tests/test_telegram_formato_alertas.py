"""Formato común del bot en las alertas y resúmenes (2026-11-20).

Daniel: «Sí, en todos». Cada mensaje empieza con «emoji TÍTULO · fecha» y la
cifra que importa va justo debajo. Nada de esto manda mensajes de verdad.
"""

from __future__ import annotations

import json
import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.services import alertas_service as al
from pos_uniformes.services import resumen_diario_service as rd
from pos_uniformes.services.telegram_formato import es_encabezado


def _primera(texto: str) -> str:
    return texto.splitlines()[0]


class AlertasTests(unittest.TestCase):
    def test_corte(self) -> None:
        corte = SimpleNamespace(
            creado_por="enc-1", hasta=datetime(2026, 11, 20, 18, 45), created_at=None,
            monto_final=Decimal("13000"), reactivo_final=Decimal("1500"), monto_esperado=Decimal("13000"),
            retiros_pagos=Decimal("800"), otros_retiros=Decimal("200"), nota=None,
        )
        t = al.texto_alerta_corte(corte, Decimal("12345"))
        self.assertTrue(es_encabezado(_primera(t)))
        self.assertEqual(_primera(t), "🧾 CORTE DE CAJA · vie 20 nov · 18:45")
        self.assertEqual(t.splitlines()[1], "💰 $12,345.00 de venta en efectivo")

    def test_retiro_sin_corte_y_fuera_de_horario(self) -> None:
        retiro = SimpleNamespace(monto=Decimal("500"), motivo="Gasolina", creado_por="enc-1",
                                 created_at=datetime(2026, 11, 20, 12, 5))
        fila = SimpleNamespace(created_at=datetime(2026, 11, 20, 22, 10), employee_name="Ana López",
                               employee_code="VEND-2", tipo="venta", monto_total=Decimal("350"))
        for texto in (
            al.texto_alerta_retiro(retiro),
            al.texto_sin_corte(date(2026, 11, 20), time(18, 0)),
            al.texto_fuera_de_horario(fila, time(10, 0), time(18, 0)),
        ):
            with self.subTest(texto=texto):
                self.assertTrue(es_encabezado(_primera(texto)), texto)
                self.assertNotIn("/corte", texto)

    def test_el_boton_del_corte_es_uno_que_ya_existe(self) -> None:
        """El «Manda /corte» se volvió el botón de la propuesta (`cc:volver`),
        que ya tiene su manejador en telegram_corte_botones_service."""
        teclado = json.loads(al.botones_ver_corte())
        datos = [b["callback_data"] for fila in teclado["inline_keyboard"] for b in fila]
        self.assertEqual(datos, ["cc:volver"])

    def test_la_base_caida_y_de_vuelta(self) -> None:
        mandados: list[str] = []
        t0 = datetime(2026, 11, 20, 12, 0)
        with patch.object(al, "_base_falla_desde", None), patch.object(al, "_base_falla_avisada", False):
            al._vuelta_sin_base(OSError("sin red"), mandados.append, t0)
            al._vuelta_sin_base(OSError("sin red"), mandados.append, t0 + timedelta(minutes=11))
            al._vuelta_con_base(mandados.append, t0 + timedelta(minutes=20))
        self.assertEqual(len(mandados), 2)
        for texto in mandados:
            self.assertTrue(es_encabezado(_primera(texto)), texto)

    def test_una_alerta_atrasada_conserva_el_encabezado_arriba(self) -> None:
        alerta = SimpleNamespace(
            texto=al.texto_sin_corte(date(2026, 11, 19), time(18, 0)),
            created_at=datetime(2026, 11, 19, 18, 10).astimezone(),
        )
        t = al._fechada(alerta, datetime(2026, 11, 20, 9, 0).astimezone())
        self.assertTrue(es_encabezado(_primera(t)), t)
        self.assertIn("🕒 Este aviso es de ayer 18:10; llegó tarde.", t)


class ResumenTests(unittest.TestCase):
    def _datos(self, **extra) -> rd.DatosResumen:
        base = dict(fecha=date(2026, 11, 20), operaciones=3, piezas=5, ventas=Decimal("900"),
                    efectivo=Decimal("700"), tarjeta=Decimal("200"))
        base.update(extra)
        return rd.DatosResumen(**base)

    def test_resumen_del_dia(self) -> None:
        t = rd.formatear(self._datos())
        self.assertTrue(es_encabezado(_primera(t)))
        self.assertEqual(_primera(t), "📒 RESUMEN DEL DÍA · vie 20 nov")
        self.assertEqual(t.splitlines()[1], "💵 $900.00 entró")

    def test_resumen_sin_movimiento_no_inventa_cifra(self) -> None:
        t = rd.formatear(rd.DatosResumen(fecha=date(2026, 11, 20)))
        self.assertTrue(es_encabezado(_primera(t)))
        self.assertEqual(t.splitlines()[1], "")

    def test_hoy(self) -> None:
        t = rd.texto_hoy(self._datos(), ahora=datetime(2026, 11, 20, 14, 30))
        self.assertEqual(_primera(t), "📅 HOY · vie 20 nov · 14:30")
        self.assertEqual(t.splitlines()[1], "💰 $900.00 entró hoy")

    def test_pendientes_de_mediodia(self) -> None:
        bloque = "📌 PENDIENTES\n💵 Hoy toca pagar a Ana"
        with patch("pos_uniformes.services.pendientes_service.pendientes_del_dia", return_value=[]), \
                patch("pos_uniformes.services.pendientes_service.texto_pendientes", return_value=bloque):
            t = rd.texto_solo_pendientes(None, date(2026, 11, 20))
        self.assertEqual(_primera(t), "📌 PENDIENTES · vie 20 nov")
        self.assertEqual(t.count("PENDIENTES"), 1)
        self.assertIn("💵 Hoy toca pagar a Ana", t)


if __name__ == "__main__":
    unittest.main()
