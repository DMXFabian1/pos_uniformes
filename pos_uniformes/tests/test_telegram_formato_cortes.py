"""Los mensajes del corte en el formato común del bot (Daniel, 2026-11-20).

Encabezado (emoji, TÍTULO, fecha) en la primera línea, la cifra principal
justo debajo, y nunca un encabezado debajo de otro. Nada se manda a Telegram.
"""

from __future__ import annotations

import json
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import tests.test_corte_remoto as tcr
from pos_uniformes.scripts import corte_automatico as script
from pos_uniformes.services import corte_remoto_service as crs
from pos_uniformes.services import telegram_cajon_service as cj
from pos_uniformes.services import telegram_corte_botones_service as cb
from pos_uniformes.services import telegram_cortes_service as ct
from pos_uniformes.services.telegram_formato import es_encabezado


def _primera(texto: str) -> str:
    return texto.splitlines()[0]


def _encabezados(texto: str) -> int:
    return sum(1 for linea in texto.splitlines() if es_encabezado(linea))


class PropuestaYCorteTests(unittest.TestCase):
    def test_la_propuesta_empieza_con_encabezado_y_la_venta(self) -> None:
        with patch("pos_uniformes.services.corte_caja_service.estado_caja", return_value=tcr._estado()), \
             patch("pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy", return_value=[]):
            texto = crs.texto_propuesta_corte(MagicMock(), tcr._HASTA)
        lineas = texto.splitlines()
        self.assertTrue(es_encabezado(lineas[0]))
        self.assertIn("¿HACEMOS EL CORTE?", lineas[0])
        self.assertTrue(lineas[1].startswith("💰 $7,480.00 de venta en efectivo"))
        self.assertNotIn("\n\n\n", texto)
        self.assertIn("Si lo hago ahora:", texto)

    def test_el_corte_hecho_empieza_con_encabezado(self) -> None:
        caso = tcr.TicketConRetiroTests("test_sin_modificaciones_el_papel_lleva_la_venta_real")
        resultado, *_ = caso._correr()
        lineas = resultado.mensaje.splitlines()
        self.assertTrue(es_encabezado(lineas[0]))
        self.assertIn("CORTE HECHO", lineas[0])
        self.assertTrue(lineas[1].startswith("💰 $7,480.00"))
        self.assertEqual(_encabezados(resultado.mensaje), 1)


class BotonesDelCorteTests(unittest.TestCase):
    def test_las_pantallas_de_cantidades_llevan_encabezado(self) -> None:
        with patch("pos_uniformes.services.telegram_service.teclado", return_value="{}"):
            textos = [
                cb.pantalla_bajar(Decimal("5000"), Decimal("700"))[0],
                cb.pantalla_cantidades("retirar", Decimal("3000"), Decimal("5000"))[0],
                cb.pantalla_cantidades("fondo", Decimal("500"), Decimal("5000"))[0],
                cb.preguntar_por_la_nota("abc", Decimal("460"))[0],
            ]
        for texto in textos:
            with self.subTest(texto=_primera(texto)):
                self.assertTrue(es_encabezado(_primera(texto)))

    def test_la_lista_del_cajon_lleva_encabezado_y_boton_de_corte(self) -> None:
        filas = [cj.Fila("pago", 1, "Evelyn", Decimal("500"), "20/11 12:00", False)]
        with patch.object(cj, "filas_del_periodo", return_value=filas):
            texto, botones = cj.texto_y_botones(MagicMock())
        self.assertTrue(es_encabezado(_primera(texto)))
        self.assertNotIn("/corte", texto)
        datos = [b["callback_data"] for f in json.loads(botones)["inline_keyboard"] for b in f]
        self.assertIn("co:nuevo", datos)

    def test_el_cajon_desde_la_propuesta_vuelve_a_ella(self) -> None:
        filas = [cj.Fila("pago", 1, "Evelyn", Decimal("500"), "20/11 12:00", True)]
        with patch.object(cj, "filas_del_periodo", return_value=filas):
            _, texto, botones = cb.atender("cc:cajon", session_factory=MagicMock(), quien="VEND-1")
        datos = [b["callback_data"] for f in json.loads(botones)["inline_keyboard"] for b in f]
        self.assertIn("cc:volver", datos)
        self.assertNotIn("co:nuevo", datos)            # uno solo para seguir
        self.assertIn("Volver a la propuesta", texto)
        self.assertEqual(_encabezados(texto), 1)


class ListaDeCortesTests(unittest.TestCase):
    def test_la_lista_y_la_vacia_llevan_encabezado(self) -> None:
        fila = ct.CorteFila(fecha=date(2026, 11, 20), hora="18:45", quien="Daniel",
                            contado=Decimal("1000"), esperado=Decimal("1000"), operaciones=3)
        for texto in (ct.texto([fila], dias=14), ct.texto([], dias=14), ct.texto([], dias=1)):
            with self.subTest(texto=texto[:30]):
                self.assertTrue(es_encabezado(_primera(texto)))
                self.assertIn("CORTES", _primera(texto))


class CorteAutomaticoTests(unittest.TestCase):
    def test_el_recordatorio_no_deja_dos_encabezados(self) -> None:
        propuesta = "🧾 ¿HACEMOS EL CORTE? · vie 20 nov · 17:00\n💰 $100.00 de venta en efectivo"
        texto = script._con_encabezado("⏰ SIGUE PENDIENTE EL CORTE · vie 20 nov · 17:20", propuesta)
        self.assertEqual(_encabezados(texto), 1)
        self.assertTrue(texto.startswith("⏰ SIGUE PENDIENTE"))
        self.assertEqual(texto.splitlines()[1], "💰 $100.00 de venta en efectivo")

    def test_el_cierre_fallido_lleva_encabezado_y_no_repite_el_del_motivo(self) -> None:
        texto = script._texto_cierre_fallido("🧾 CORTE HECHO · vie 20 nov\nalgo raro")
        self.assertTrue(es_encabezado(_primera(texto)))
        self.assertEqual(_encabezados(texto), 1)
        self.assertIn("Quise cerrar el día por ti y no pude", texto)
        self.assertIn("algo raro", texto)


if __name__ == "__main__":
    unittest.main()
