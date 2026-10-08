"""Los botones de ayer siguen en el chat, y alguien los va a tocar.

Revisión del bot pedida por Daniel el 2026-10-08 («necesito que el bot quede
así redondo»). Se recorrieron los 43 botones de mirar —todos bien— y después
los que CAMBIAN cosas, con datos que ya no existen: ése es el caso real, no un
código inventado. Un mensaje de hace tres días con el botón de pagarle a
alguien que ya se dio de baja.
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.services import telegram_bot_service as bot


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        from pos_uniformes.database import models  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.engine = engine
        self.factory = lambda: Session(engine)


class PagarleAAlguienQueNoExisteTests(_Base):
    """`m:pagarok:NADIE` **registraba un pago de $1,300**.

    El cálculo da el sueldo base por omisión y nadie preguntaba si esa
    empleada existe. Es el botón de un mensaje viejo para quien ya no está.
    """

    def _pagos_registrados(self) -> int:
        from pos_uniformes.database.models import EmpleadaPago

        with self.factory() as s:
            return s.query(EmpleadaPago).count()

    def test_no_se_registra_el_pago(self) -> None:
        bot.atender_toque("m:pagarok:NADIE", session_factory=self.factory)
        self.assertEqual(self._pagos_registrados(), 0)

    def test_lo_dice_y_dice_por_qué(self) -> None:
        _, texto, _ = bot.atender_toque("m:pagarok:NADIE", session_factory=self.factory)
        self.assertIn("No tengo a nadie activo", texto)
        self.assertIn("/pagos", texto)

    def test_el_globito_no_miente(self) -> None:
        """Decía «Pagado» pasara lo que pasara."""
        aviso, _, _ = bot.atender_toque("m:pagarok:NADIE", session_factory=self.factory)
        self.assertNotEqual(aviso, "Pagado")

    def test_el_desglose_tampoco_se_inventa_a_nadie(self) -> None:
        _, texto, _ = bot.atender_toque("m:pagar:NADIE", session_factory=self.factory)
        self.assertIn("No tengo a nadie activo", texto)

    def test_una_empleada_dada_de_baja_cuenta_como_que_no_está(self) -> None:
        """El caso de verdad: el botón es de antes de la baja."""
        from pos_uniformes.database.models import Empleada
        from pos_uniformes.services import telegram_pagos_service as pg

        with self.factory() as s:
            s.add(Empleada(codigo="VEND-9", nombre_completo="Quien Se Fue", activo=False))
            s.commit()
            self.assertFalse(pg.existe_y_trabaja(s, "VEND-9"))

    def test_una_activa_sí_pasa_el_filtro(self) -> None:
        from pos_uniformes.database.models import Empleada
        from pos_uniformes.services import telegram_pagos_service as pg

        with self.factory() as s:
            s.add(Empleada(codigo="VEND-8", nombre_completo="Quien Trabaja", activo=True))
            s.commit()
            self.assertTrue(pg.existe_y_trabaja(s, "VEND-8"))
            self.assertTrue(pg.existe_y_trabaja(s, "vend-8"))   # sin importar mayúsculas


class BotonesViejosQueNoDebenHacerNadaTests(_Base):
    """Ninguno puede reventar ni quedarse callado: el botón se queda girando."""

    GASTADOS = [
        "co:ver:99999", "co:quitar:99999", "co:borrar:99999", "co:borrarok:99999",
        "pr:ok:99999", "pr:no:99999", "dc:ok:99999", "dc:no:99999",
        "av:quitar:99999", "av:mas:99999:3", "av:otra:99999",
        "cc:ret:abc", "cc:fnd:abc", "cc:baja:abc", "cc:nota:",
        "m:", "co:", "cc:", "pr:", "dc:", "av:", "cj:", "rs:",
    ]

    def test_ninguno_truena_ni_contesta_vacio(self) -> None:
        for dato in self.GASTADOS:
            with self.subTest(dato=dato):
                r = bot.atender_toque(
                    dato, session_factory=self.factory, enviar=lambda *a: None
                )
                self.assertIsNotNone(r, "nadie lo atiende")
                aviso, texto, _ = r
                self.assertTrue(
                    (aviso or "").strip() or (texto or "").strip(),
                    "contesta vacío: el botón se queda girando",
                )

    def test_un_corte_sin_nota_no_se_hace(self) -> None:
        """`cc:nota:` sin nota haría el corte igual, que es justo lo que ese
        botón existe para impedir."""
        aviso, _, _ = bot.atender_toque("cc:nota:", session_factory=self.factory)
        self.assertEqual(aviso, "No conozco ese botón")


if __name__ == "__main__":
    unittest.main()
