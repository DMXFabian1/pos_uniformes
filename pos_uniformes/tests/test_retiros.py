"""Retiros del cajón con motivo: se descuentan en el corte y salen en los tickets."""

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

from pos_uniformes.database.models import CajaRetiro
from pos_uniformes.services.corte_caja_service import EstadoCaja, ResumenPeriodo
from pos_uniformes.services.retiros_service import eliminar_retiro, registrar_retiro, retiros_del_periodo, total_retiros
from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_previa_corte_encargado, texto_ticket_corte, texto_ticket_corte_encargado


class RetirosServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        CajaRetiro.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()

    def test_registrar_y_sumar(self) -> None:
        registrar_retiro(self.session, monto="500", motivo=" Proveedor ", creado_por="enc-1")
        registrar_retiro(self.session, monto=Decimal("120.50"), motivo="Cambio", creado_por="VEND-1")
        ahora = datetime.now().astimezone()
        lista = retiros_del_periodo(self.session, None, ahora)
        self.assertEqual([(r.motivo, r.monto, r.creado_por) for r in lista], [("Proveedor", Decimal("500.00"), "ENC-1"), ("Cambio", Decimal("120.50"), "VEND-1")])
        self.assertEqual(total_retiros(self.session, None, ahora), Decimal("620.50"))

    def test_validaciones(self) -> None:
        with self.assertRaises(PermissionError):
            registrar_retiro(self.session, monto=10, motivo="x", creado_por="VEND-2")
        with self.assertRaises(ValueError):
            registrar_retiro(self.session, monto=0, motivo="x", creado_por="VEND-1")
        with self.assertRaises(ValueError):
            registrar_retiro(self.session, monto=10, motivo="   ", creado_por="VEND-1")

    def test_eliminar(self) -> None:
        r = registrar_retiro(self.session, monto=10, motivo="Comida", creado_por="ENC-1")
        self.assertTrue(eliminar_retiro(self.session, r.id, creado_por="ENC-1"))
        self.assertFalse(eliminar_retiro(self.session, 999, creado_por="ENC-1"))


class EstadoConRetirosTests(unittest.TestCase):
    def test_esperado_descuenta_retiros_apuntados(self) -> None:
        estado = EstadoCaja(
            desde=None, hasta=datetime(2026, 9, 9, 20, tzinfo=timezone.utc), reactivo=Decimal("11160.00"),
            resumen=ResumenPeriodo(10, 12, Decimal("6660"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("6660.00")),
            pagos=Decimal("1191.33"), otros_retiros=Decimal("100.00"), retiros=Decimal("500.00"),
        )
        self.assertEqual(estado.total_retiros, Decimal("600.00"))
        self.assertEqual(estado.esperado, Decimal("16028.67"))
        previa = texto_previa_corte_encargado(estado, [])
        self.assertIn("Ya salió del cajón: -$600.00", previa)
        self.assertIn("SE RETIRA: $4,868.67", previa)  # 6660 - 1191.33 - 600


class TicketsConRetirosTests(unittest.TestCase):
    def _corte(self):
        return SimpleNamespace(periodo_label="p", creado_por="ENC-1", operaciones=10, reactivo_inicial=Decimal("11160"),
                               retiros_pagos=Decimal("0"), otros_retiros=Decimal("500"), monto_final=Decimal("17320"),
                               reactivo_final=Decimal("11160"), nota="")

    def test_ticket_dueno_lista_retiros(self) -> None:
        retiros = [SimpleNamespace(motivo="Proveedor de playeras", monto=Decimal("400")), SimpleNamespace(motivo="Cambio", monto=Decimal("100"))]
        texto = texto_ticket_corte(self._corte(), retiros=retiros)
        self.assertIn("Gasto (Proveedor", texto)
        self.assertIn("-$400.00", texto)
        self.assertIn("Gasto (Cambio):", texto)
        self.assertIn("-$100.00", texto)
        self.assertIn("$6,160.00", texto)  # SACAR = 17320 - 11160

    def test_ticket_encargado_muestra_lo_que_ya_salio(self) -> None:
        retiros = [SimpleNamespace(motivo="Proveedor", monto=Decimal("500"))]
        texto = texto_ticket_corte_encargado(self._corte(), Decimal("6660"), [], retiros=retiros)
        self.assertIn("Gasto (Proveedor):", texto)
        self.assertIn("$500.00", texto)
        self.assertIn("SACAR DE LA VENTA:", texto)
        self.assertIn("$6,160.00", texto)  # 17320 - 11160


if __name__ == "__main__":
    unittest.main()
