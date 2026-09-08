"""Corte de caja: ticket y texto de estado (funciones puras del diálogo)."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services.corte_caja_service import EstadoCaja, ResumenPeriodo
from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_estado_caja, texto_ticket_corte


def _corte(**extra):
    base = dict(
        periodo_label="07/09 20:30 → 08/09 21:00",
        creado_por="ENC-1",
        operaciones=12,
        reactivo_inicial=Decimal("11160.00"),
        retiros_pagos=Decimal("1390.00"),
        otros_retiros=Decimal("0.00"),
        monto_final=Decimal("13000.00"),
        reactivo_final=Decimal("11160.00"),
        nota="",
    )
    base.update(extra)
    return SimpleNamespace(**base)


class TicketCorteTests(unittest.TestCase):
    def test_ticket_trae_fondo_pagos_y_retiro(self) -> None:
        texto = texto_ticket_corte(_corte(), [SimpleNamespace(employee_name="Ana", employee_code="VEND-2", operaciones=7, comisiones=30)])
        self.assertIn("CORTE DE CAJA", texto)
        self.assertIn("$11,160.00", texto)       # fondo inicial y final
        self.assertIn("-$1,390.00", texto)       # pagos
        self.assertIn("$13,000.00", texto)       # en caja
        self.assertIn("$1,840.00", texto)        # se retira = 13000 - 11160
        self.assertIn("Ana", texto)
        self.assertIn("30 com.", texto)
        self.assertNotIn("esperado", texto.lower())  # nunca imprime esperado/diferencia

    def test_sin_pagos_no_imprime_la_linea(self) -> None:
        texto = texto_ticket_corte(_corte(retiros_pagos=Decimal("0.00")))
        self.assertNotIn("Pagos empleadas", texto)


class TextoEstadoTests(unittest.TestCase):
    def test_texto_estado(self) -> None:
        estado = EstadoCaja(
            desde=datetime(2026, 9, 7, 20, 30),
            hasta=datetime(2026, 9, 8, 21, 0),
            reactivo=Decimal("11160.00"),
            resumen=ResumenPeriodo(12, 20, Decimal("3000"), Decimal("500"), Decimal("0"), Decimal("700.00"), Decimal("2800.00")),
            pagos=Decimal("1390.00"),
        )
        texto = texto_estado_caja(estado)
        self.assertIn("del 07/09 20:30 al 08/09 21:00", texto)
        self.assertIn("$11,160.00", texto)
        self.assertIn("$2,800.00", texto)
        self.assertIn("tarjeta", texto.lower())
        self.assertIn("-$1,390.00", texto)
        self.assertIn("DEBE HABER EN EL CAJÓN: $12,570.00", texto)


if __name__ == "__main__":
    unittest.main()
