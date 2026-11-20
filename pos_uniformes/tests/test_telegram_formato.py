"""El formato común de los mensajes del bot (2026-11-20)."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal

from pos_uniformes.services import telegram_formato as f


class FormatoTests(unittest.TestCase):
    def test_encabezado_con_fecha_y_hora(self) -> None:
        self.assertEqual(
            f.encabezado("🧾", "Corte de caja", datetime(2026, 11, 20, 18, 45), hora=True),
            "🧾 CORTE DE CAJA · vie 20 nov · 18:45",
        )

    def test_encabezado_sin_fecha(self) -> None:
        self.assertEqual(f.encabezado("📋", "Menú"), "📋 MENÚ")

    def test_la_hora_solo_con_datetime(self) -> None:
        self.assertEqual(f.encabezado("📊", "Hoy", date(2026, 11, 22), hora=True), "📊 HOY · dom 22 nov")

    def test_dinero(self) -> None:
        self.assertEqual(f.dinero(Decimal("12345.5")), "$12,345.50")
        self.assertEqual(f.dinero(-80), "−$80.00")
        self.assertEqual(f.dinero(None), "$0.00")

    def test_cifra(self) -> None:
        self.assertEqual(f.cifra(Decimal("1500"), "en efectivo"), "💰 $1,500.00 en efectivo")
        self.assertEqual(f.cifra(5, emoji="💵"), "💵 $5.00")

    def test_mensaje_completo(self) -> None:
        texto = f.mensaje(
            "🧾", "Corte de caja", cuando=datetime(2026, 11, 20, 18, 45), hora=True,
            principal=f.cifra(12345, "en efectivo"),
            detalle=["Pagos $800.00", "", "Reactivo queda $1,500.00"],
            pie="Si algo no cuadra, avísame.",
        )
        self.assertEqual(texto, (
            "🧾 CORTE DE CAJA · vie 20 nov · 18:45\n💰 $12,345.00 en efectivo\n\n"
            "Pagos $800.00\nReactivo queda $1,500.00\n\nSi algo no cuadra, avísame."
        ))

    def test_mensaje_sin_detalle(self) -> None:
        self.assertEqual(f.mensaje("✅", "Listo"), "✅ LISTO")

    def test_es_encabezado(self) -> None:
        self.assertTrue(f.es_encabezado("🧾 CORTE DE CAJA · vie 20 nov"))
        self.assertTrue(f.es_encabezado(f.encabezado("💵", "Pagos")))
        self.assertFalse(f.es_encabezado("Corte hecho por VEND-1"))
        self.assertFalse(f.es_encabezado("🧾 Corte hecho por VEND-1"))




class AnioTests(unittest.TestCase):
    def test_otro_anio_lleva_el_anio(self) -> None:
        self.assertEqual(f.fecha_corta(date(2025, 9, 9)), "mar 9 sep 2025")
        self.assertEqual(f.fecha_corta(date(2026, 9, 9)), "mié 9 sep")


if __name__ == "__main__":
    unittest.main()
