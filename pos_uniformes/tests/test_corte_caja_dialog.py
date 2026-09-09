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

    def test_con_ajuste_no_delata_la_suma(self) -> None:
        # Cifra del dueño ≠ real: fuera VENTA, reactivo inicial y pagos (la suma delataría el ajuste).
        from datetime import datetime as _dt

        corte = _corte(creado_por="VEND-1", monto_final=Decimal("19311.00"), monto_esperado=Decimal("20311.00"), hasta=_dt(2026, 9, 9, 14, 22), desde=_dt(2026, 9, 8, 18, 15))
        pago = SimpleNamespace(employee_name="Fanny Ortiz", employee_code="VEND-7", total=Decimal("1590.00"), sueldo_base=Decimal("1300.00"), comisiones=145, tarifa_comision=Decimal("2.00"), monto_comisiones=Decimal("290.00"), faltas=0, descuento_faltas=Decimal("0"), dias_trabajados=None)
        texto = texto_ticket_corte(corte, pagos=[pago], venta_efectivo=Decimal("10741.00"))
        self.assertIn("EN CAJA:", texto)
        self.assertIn("$19,311.00", texto)
        self.assertIn("Se queda (reactivo):", texto)
        self.assertIn("Fanny Ortiz:", texto)  # la sección de pagos sí (es lo que se le paga)
        for delator in ("VENTA (efectivo):", "Reactivo inicial:", "Pagos empleadas:", "10,741", "20,311"):
            self.assertNotIn(delator, texto)
        # Sin ajuste: ticket completo.
        completo = texto_ticket_corte(_corte(creado_por="VEND-1", monto_final=Decimal("20311.00"), monto_esperado=Decimal("20311.00"), hasta=_dt(2026, 9, 9, 14, 22), desde=_dt(2026, 9, 8, 18, 15)), venta_efectivo=Decimal("10741.00"))
        self.assertIn("VENTA (efectivo):", completo)
        self.assertIn("Reactivo inicial:", completo)

    def test_tarjeta_informativa_en_ticket_del_dueno(self) -> None:
        texto = texto_ticket_corte(_corte(), venta_efectivo=Decimal("10741.00"), tarjeta=Decimal("705.00"), tarjeta_ops=2)
        self.assertIn("VENTA (efectivo):", texto)
        self.assertIn("Con tarjeta (2):", texto)
        self.assertIn("$705.00", texto)
        self.assertNotIn("Con tarjeta", texto_ticket_corte(_corte(), venta_efectivo=Decimal("1"), tarjeta=Decimal("0")))

    def test_sin_pagos_no_imprime_la_linea(self) -> None:
        texto = texto_ticket_corte(_corte(retiros_pagos=Decimal("0.00")))
        self.assertNotIn("Pagos empleadas", texto)


class TicketLegacyTests(unittest.TestCase):
    def test_sin_reactivo_no_imprime_esos_renglones(self) -> None:
        texto = texto_ticket_corte(_corte(reactivo_inicial=Decimal("0"), reactivo_final=Decimal("0"), retiros_pagos=Decimal("0"), monto_final=Decimal("22300.00")))
        self.assertIn("$22,300.00", texto)
        self.assertNotIn("Reactivo inicial", texto)
        self.assertNotIn("Se queda", texto)
        self.assertNotIn("Se retira", texto)


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
            SimpleNamespace(employee_name="Evelyn Ramírez", employee_code="VEND-2", total=Decimal("1191.33"), comisiones=54, faltas=1,
                            sueldo_base=Decimal("1300.00"), tarifa_comision=Decimal("2.00"), monto_comisiones=Decimal("108.00"), descuento_faltas=Decimal("216.67")),
            SimpleNamespace(employee_name="Cristal", employee_code="VEND-3", total=Decimal("1320.00"), comisiones=10, faltas=0,
                            sueldo_base=Decimal("1300.00"), tarifa_comision=Decimal("2.00"), monto_comisiones=Decimal("20.00"), descuento_faltas=Decimal("0.00")),
        ]
        texto = texto_ticket_corte(_corte(retiros_pagos=Decimal("2511.33")), pagos=pagos, venta_efectivo=Decimal("6660.00"))
        self.assertIn("VENTA (efectivo):", texto)
        self.assertIn("$6,660.00", texto)
        self.assertIn("PAGOS A EMPLEADAS", texto)
        self.assertIn("Evelyn Ramírez:", texto)
        self.assertIn("$1,191.33", texto)
        self.assertIn("54 comisiones x $2:", texto)
        self.assertIn("1 falta(s):", texto)
        self.assertIn("-$216.67", texto)
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
        pagos = [SimpleNamespace(
            employee_name="Evelyn Ramírez", employee_code="VEND-2", total=Decimal("1191.33"),
            sueldo_base=Decimal("1300.00"), comisiones=54, tarifa_comision=Decimal("2.00"),
            monto_comisiones=Decimal("108.00"), faltas=1, descuento_faltas=Decimal("216.67"),
        )]
        texto = texto_ticket_corte_encargado(corte, Decimal("6660.00"), pagos)
        self.assertIn("Sueldo:", texto)
        self.assertIn("$1,300.00", texto)
        self.assertIn("54 comisiones x $2:", texto)
        self.assertIn("+$108.00", texto)
        self.assertIn("1 falta(s):", texto)
        self.assertIn("-$216.67", texto)
        self.assertIn("VENTA EN EFECTIVO:", texto)
        self.assertIn("$6,660.00", texto)
        self.assertIn("PAGAR A EVELYN:", texto)
        self.assertIn("$1,191.33", texto)
        # La cuenta se ve: venta − pago = sacar
        self.assertIn("Pago a Evelyn:", texto)
        self.assertIn("-$1,191.33", texto)
        self.assertIn("SACAR DE LA VENTA:", texto)
        self.assertIn("$5,468.67", texto)
        self.assertIn("El reactivo de la caja se queda igual.", texto)
        self.assertNotIn("tarjeta", texto)  # sin tarjeta no se menciona
        for prohibido in ("EN CAJA", "Fondo inicial", "Operaciones", "11,160"):
            self.assertNotIn(prohibido, texto)

    def test_ya_pagado_en_el_periodo_se_ve_y_se_resta(self) -> None:
        # Caso real 2026-09-09: Fanny cobró a las 14:22 y el corte de las 14:45 decía
        # "no se paga a nadie" pero restaba $1,590 en silencio.
        from datetime import datetime as _dt

        corte = _corte(monto_final=Decimal("20596.00"), retiros_pagos=Decimal("1590"))
        fanny = SimpleNamespace(employee_name="Fanny Ortiz", employee_code="VEND-7", total=Decimal("1590.00"), sueldo_base=Decimal("1300.00"),
                                comisiones=145, tarifa_comision=Decimal("2.00"), monto_comisiones=Decimal("290.00"), faltas=0,
                                descuento_faltas=Decimal("0"), dias_trabajados=None, created_at=_dt(2026, 9, 9, 14, 22))
        texto = texto_ticket_corte_encargado(corte, Decimal("11026.00"), [], ya_pagados=[fanny])
        self.assertNotIn("Hoy no se paga a nadie.", texto)
        self.assertIn("YA PAGADO A FANNY:", texto)
        self.assertIn("(se le pago a las 14:22)", texto)
        self.assertIn("Pago a Fanny:", texto)
        self.assertIn("-$1,590.00", texto)
        self.assertIn("$9,436.00", texto)

    def test_con_tarjeta_va_aparte(self) -> None:
        corte = _corte(monto_final=Decimal("21901.00"), retiros_pagos=Decimal("0"))
        texto = texto_ticket_corte_encargado(corte, Decimal("10741.00"), [], tarjeta=Decimal("705.00"), tarjeta_ops=2)
        self.assertIn("VENTA EN EFECTIVO:", texto)
        self.assertIn("$10,741.00", texto)
        self.assertIn("Con tarjeta (2):", texto)
        self.assertIn("$705.00", texto)
        self.assertIn("no esta en el cajon", texto)
        self.assertIn("Hoy no se paga a nadie.", texto)
        self.assertIn("SACAR DE LA VENTA:", texto)
        self.assertNotIn("$11,446", texto)  # nunca se suman efectivo + tarjeta

    def test_sin_pagos_y_fondo_que_baja(self) -> None:
        corte = _corte(monto_final=Decimal("10356.00"), reactivo_final=Decimal("10356.00"))
        texto = texto_ticket_corte_encargado(corte, Decimal("500.00"), [])
        self.assertIn("Hoy no se paga a nadie.", texto)
        self.assertIn("SACAR DE LA VENTA:", texto)
        self.assertIn("$0.00", texto)
        self.assertIn("Se tomo del reactivo.", texto)
        self.assertIn("Reactivo que queda:", texto)
