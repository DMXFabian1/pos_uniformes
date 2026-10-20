"""Entradas al cajón que no son venta (el fondo de papá para la nómina, 2026-10-20)."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.models import CajaEntrada
from pos_uniformes.services import telegram_pagos_service as pg
from pos_uniformes.services.corte_caja_service import EstadoCaja, ResumenPeriodo
from pos_uniformes.services.entradas_service import (
    eliminar_entrada,
    entradas_del_periodo,
    registrar_entrada,
    total_entradas,
)
from pos_uniformes.ui.dialogs.corte_caja_dialog import (
    contado_desde_venta,
    texto_estado_caja,
    texto_previa_corte_encargado,
    texto_ticket_corte_encargado,
)


class EntradasServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        CajaEntrada.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()

    def test_registrar_y_sumar(self) -> None:
        with patch("pos_uniformes.services.alertas_service.encolar") as encolar:
            registrar_entrada(self.session, monto="1750", motivo="", creado_por="vend-1")
        self.assertIn("➕ Entró al cajón (no venta): $1,750.00 — Fondo de papá", encolar.call_args.args[1])
        registrar_entrada(self.session, monto=Decimal("200"), motivo=" Cambio del banco ", creado_por="ENC-1")
        ahora = datetime.now().astimezone()
        lista = entradas_del_periodo(self.session, None, ahora)
        self.assertEqual([(e.motivo, e.monto, e.creado_por) for e in lista],
                         [("Fondo de papá", Decimal("1750.00"), "VEND-1"), ("Cambio del banco", Decimal("200.00"), "ENC-1")])
        self.assertEqual(total_entradas(self.session, None, ahora), Decimal("1950.00"))

    def test_validaciones_y_doble_envio(self) -> None:
        with self.assertRaises(PermissionError):
            registrar_entrada(self.session, monto=10, motivo="x", creado_por="VEND-2")
        with self.assertRaises(ValueError):
            registrar_entrada(self.session, monto=0, motivo="x", creado_por="VEND-1")
        registrar_entrada(self.session, monto=1750, motivo="papá", creado_por="VEND-1")
        with self.assertRaisesRegex(ValueError, "ya quedó apuntada"):
            registrar_entrada(self.session, monto=1750, motivo="papá", creado_por="VEND-1")

    def test_eliminar(self) -> None:
        e = registrar_entrada(self.session, monto=10, motivo="x", creado_por="ENC-1")
        self.assertTrue(eliminar_entrada(self.session, e.id, creado_por="ENC-1"))
        self.assertFalse(eliminar_entrada(self.session, 999, creado_por="ENC-1"))


def _estado(entradas="1750.00", pagos="2736.00"):
    return EstadoCaja(
        desde=None, hasta=datetime(2026, 10, 18, 18, tzinfo=timezone.utc), reactivo=Decimal("11160.00"),
        resumen=ResumenPeriodo(10, 12, Decimal("6660"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("6660.00")),
        pagos=Decimal(pagos), retiros=Decimal("100.00"), entradas=Decimal(entradas),
    )


class EstadoConEntradasTests(unittest.TestCase):
    def test_el_esperado_suma_lo_que_entro(self) -> None:
        # 11160 + 6660 + 1750 − 2736 − 100
        self.assertEqual(_estado().esperado, Decimal("16734.00"))
        self.assertEqual(contado_desde_venta(_estado(), Decimal("6660"), Decimal("0")), Decimal("16734.00"))
        self.assertIn("Entró al cajón sin ser venta (fondo de papá...): +$1,750.00", texto_estado_caja(_estado()))

    def test_si_papa_deja_de_mas_el_sobrante_se_queda_en_el_cajon(self) -> None:
        # Pagos 1436, entró 1750: sobran 314 y se ven en el esperado, sin más.
        e = _estado(pagos="1436.00")
        self.assertEqual(e.esperado, Decimal("11160") + Decimal("6660") + Decimal("314") - Decimal("100"))

    def test_la_previa_del_encargado_lo_dice(self) -> None:
        texto = texto_previa_corte_encargado(_estado(), [])
        self.assertIn("Entró sin ser venta: +$1,750.00", texto)
        # 6660 + 1750 − 2736 − 100
        self.assertIn("SE RETIRA: $5,574.00", texto)


class TicketConEntradasTests(unittest.TestCase):
    def test_el_ticket_lista_lo_que_entro_y_de_donde_salieron_los_pagos(self) -> None:
        corte = SimpleNamespace(
            periodo_label="dom 18/10", creado_por="VEND-1", nota=None, created_at=None,
            reactivo_inicial=Decimal("11160.00"), reactivo_final=Decimal("11160.00"),
            monto_final=Decimal("16734.00"), retiros_pagos=Decimal("2736.00"), otros_retiros=Decimal("100.00"),
        )
        pagos = [SimpleNamespace(employee_name="Stayce Chavarria", employee_code="VEND-4", total=Decimal("1436.00"), created_at=None),
                 SimpleNamespace(employee_name="Cristal Torres", employee_code="VEND-3", total=Decimal("1300.00"), created_at=None)]
        entradas = [SimpleNamespace(motivo="Fondo de papá", monto=Decimal("1750.00"))]
        retiros = [SimpleNamespace(motivo="Comida", monto=Decimal("100.00"))]
        with patch("pos_uniformes.ui.dialogs.corte_caja_dialog._desglose_pago"):
            texto = texto_ticket_corte_encargado(corte, Decimal("6660.00"), [], [], retiros=retiros,
                                                 ya_pagados=pagos, entradas=entradas)
        self.assertIn("Entro (Fondo de papa", texto.replace("á", "a"))
        self.assertIn("+$1,750.00", texto)
        self.assertIn("-$1,436.00", texto)                          # el pago sale completo
        self.assertIn("de los pagos, $1,750.00 salio", texto)
        self.assertIn("SACAR DE LA VENTA:", texto)
        self.assertIn("$5,574.00", texto)                           # 16734 − 11160


class BotEntradaTests(unittest.TestCase):
    def _correr(self, argumento, registrar=None):
        from pos_uniformes.services import entradas_service

        with patch.object(entradas_service, "registrar_entrada", side_effect=registrar) as reg:
            texto = pg.entrada(MagicMock(), argumento, quien="VEND-1")
        return texto, reg

    def test_entrada_de_papa(self) -> None:
        texto, reg = self._correr("1750 papá")
        self.assertEqual(reg.call_args.kwargs["monto"], Decimal("1750"))
        self.assertEqual(reg.call_args.kwargs["motivo"], "Fondo de papá")
        self.assertIn("✅ Entró al cajón: $1,750.00 (Fondo de papá)", texto)

    def test_sin_motivo_es_el_fondo_de_papa_y_sin_monto_explica(self) -> None:
        _, reg = self._correr("1,750")
        self.assertEqual(reg.call_args.kwargs["motivo"], "Fondo de papá")
        self.assertIn("Por ejemplo", self._correr("")[0])
        self.assertIn("No entendí", self._correr("mil papá")[0])

    def test_lo_que_el_servicio_rechaza_se_dice(self) -> None:
        texto, _ = self._correr("1750 papá", registrar=ValueError("ya quedó apuntada"))
        self.assertIn("No lo apunté: ya quedó apuntada", texto)


if __name__ == "__main__":
    unittest.main()
