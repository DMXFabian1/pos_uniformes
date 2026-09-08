"""Corte de caja: ticket y texto de estado (funciones puras del diálogo)."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services.corte_caja_service import EstadoCaja, ResumenPeriodo
from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_estado_caja, texto_previa_corte_encargado, texto_ticket_corte, texto_ticket_corte_encargado


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


class TicketPagarHoyTests(unittest.TestCase):
    def test_seccion_pagar_hoy_y_venta(self) -> None:
        pagos = [
            SimpleNamespace(employee_name="Evelyn Ramírez", employee_code="VEND-2", total=Decimal("1191.33"), comisiones=54, faltas=1),
            SimpleNamespace(employee_name="Cristal", employee_code="VEND-3", total=Decimal("1320.00"), comisiones=10, faltas=0),
        ]
        texto = texto_ticket_corte(_corte(retiros_pagos=Decimal("2511.33")), pagos=pagos, venta_efectivo=Decimal("6660.00"))
        self.assertIn("VENTA (efectivo):", texto)
        self.assertIn("$6,660.00", texto)
        self.assertIn("PAGAR HOY", texto)
        self.assertIn("Evelyn Ramírez:", texto)
        self.assertIn("$1,191.33", texto)
        self.assertIn("54 com. - 1 falta(s)", texto)
        self.assertIn("TOTAL PAGOS:", texto)
        self.assertIn("$2,511.33", texto)

    def test_previa_encargado(self) -> None:
        estado = EstadoCaja(
            desde=None, hasta=datetime(2026, 9, 9, 20, 20), reactivo=Decimal("11160.00"),
            resumen=ResumenPeriodo(19, 27, Decimal("6660"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("6660.00")),
            pagos=Decimal("0.00"),
        )
        avisos = [SimpleNamespace(employee_name="Evelyn Ramírez", total_estimado=Decimal("1191.33"))]
        texto = texto_previa_corte_encargado(estado, avisos)
        self.assertEqual(texto.split("\n")[0], "VENTA: $6,660.00")
        self.assertIn("Evelyn  $1,191.33", texto)
        self.assertIn("SE RETIRA: $5,468.67", texto)
        self.assertIn("Se queda de fondo: $11,160.00", texto)


class TicketEncargadoTests(unittest.TestCase):
    def test_solo_vendido_pagar_y_sacar(self) -> None:
        corte = _corte(monto_final=Decimal("16628.67"), retiros_pagos=Decimal("1191.33"))
        pagos = [SimpleNamespace(employee_name="Evelyn Ramírez", employee_code="VEND-2", total=Decimal("1191.33"))]
        texto = texto_ticket_corte_encargado(corte, Decimal("6660.00"), pagos)
        self.assertIn("SE VENDIO:", texto)
        self.assertIn("$6,660.00", texto)
        self.assertIn("PAGAR A EVELYN:", texto)
        self.assertIn("$1,191.33", texto)
        self.assertIn("SACAR DE LA VENTA:", texto)
        self.assertIn("$5,468.67", texto)
        self.assertIn("El fondo del cajon se queda igual.", texto)
        for prohibido in ("EN CAJA", "Fondo inicial", "Operaciones", "11,160"):
            self.assertNotIn(prohibido, texto)

    def test_sin_pagos_y_fondo_que_baja(self) -> None:
        corte = _corte(monto_final=Decimal("10356.00"), reactivo_final=Decimal("10356.00"))
        texto = texto_ticket_corte_encargado(corte, Decimal("500.00"), [])
        self.assertIn("Hoy no se paga a nadie.", texto)
        self.assertIn("SACAR DE LA VENTA:", texto)
        self.assertIn("$0.00", texto)
        self.assertIn("Se tomo del fondo.", texto)
        self.assertIn("Fondo que queda:", texto)
