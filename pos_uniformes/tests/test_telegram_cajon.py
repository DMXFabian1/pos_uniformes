"""`/cajon`: corregir desde el celular lo que NO salió del cajón.

Era la opción del corte que más pesaba de las que faltaban (Daniel, 2026-10-04):
sin ella el corte se cuadra contra dinero que nunca salió y la diferencia
aparece como faltante — de lejos, como si la caja no cuadrara.
"""

from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaRetiro, Empleada, EmpleadaPago
from pos_uniformes.services import telegram_cajon_service as cj


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.addCleanup(self.s.close)
        self.factory = sessionmaker(self.engine)
        self.s.add(Empleada(codigo="VEND-3", nombre_completo="Evelyn Ortiz", activo=True))
        self.s.flush()

    def pago(self, total="1300", en_cajon=True) -> EmpleadaPago:
        # Hora LOCAL con zona, como la guarda el programa. Con UTC, SQLite
        # —que compara fechas como texto— deja la fila fuera del periodo.
        ahora = datetime.now().astimezone()
        p = EmpleadaPago(
            employee_code="VEND-3", employee_name="Evelyn Ortiz",
            fecha=ahora.date(), desde=ahora, hasta=ahora,
            total=Decimal(total), en_cajon=en_cajon,
            created_at=ahora, creado_por="VEND-1",
        )
        self.s.add(p); self.s.flush(); return p

    def _refrescar(self) -> None:
        """`atender` escribe en OTRA sesión; sin esto se lee lo de antes."""
        self.s.expire_all()

    def retiro(self, monto="350", motivo="gasolina", en_cajon=True) -> CajaRetiro:
        r = CajaRetiro(
            monto=Decimal(monto), motivo=motivo, en_cajon=en_cajon,
            created_at=datetime.now().astimezone(), creado_por="VEND-1",
        )
        self.s.add(r); self.s.flush(); return r


class LaListaTests(_Base):
    def test_sin_nada_lo_dice_y_explica_para_que_sirve(self) -> None:
        texto, _ = cj.texto_y_botones(self.s)
        self.assertIn("No hay pagos ni retiros", texto)
        self.assertIn("transferencia", texto)

    def test_salen_pagos_y_retiros_juntos(self) -> None:
        self.pago(); self.retiro()
        texto, botones = cj.texto_y_botones(self.s)
        self.assertIn("Evelyn", texto)
        self.assertIn("gasolina", texto)
        self.assertIn("cj:pago:", botones)
        self.assertIn("cj:retiro:", botones)

    def test_se_ve_cual_salio_y_cual_no(self) -> None:
        self.pago(en_cajon=True)
        self.retiro(en_cajon=False)
        texto, _ = cj.texto_y_botones(self.s)
        self.assertIn("✅ Evelyn", texto)
        self.assertIn("⬜ gasolina", texto)

    def test_suma_lo_que_quedo_fuera(self) -> None:
        self.retiro(monto="350", en_cajon=False)
        self.retiro(monto="150", motivo="agua", en_cajon=False)
        texto, _ = cj.texto_y_botones(self.s)
        self.assertIn("Fuera del cajón: $500.00", texto)

    def test_si_no_hay_nada_fuera_no_se_dice(self) -> None:
        self.pago(en_cajon=True)
        texto, _ = cj.texto_y_botones(self.s)
        self.assertNotIn("Fuera del cajón", texto)


class TocarUnoTests(_Base):
    def test_desmarcar_un_pago(self) -> None:
        p = self.pago(en_cajon=True)
        self.s.commit()
        aviso, texto, _ = cj.atender(f"cj:pago:{p.id}", session_factory=self.factory)
        self.assertEqual(aviso, "No salió del cajón")
        self._refrescar()
        self.assertFalse(self.s.get(EmpleadaPago, p.id).en_cajon)

    def test_volver_a_marcarlo(self) -> None:
        # El mismo botón sirve de ida y de vuelta: si no, un dedazo no se
        # podría deshacer desde el celular.
        p = self.pago(en_cajon=False)
        self.s.commit()
        aviso, _, _ = cj.atender(f"cj:pago:{p.id}", session_factory=self.factory)
        self.assertEqual(aviso, "Sí salió del cajón")
        self._refrescar()
        self.assertTrue(self.s.get(EmpleadaPago, p.id).en_cajon)

    def test_desmarcar_un_retiro(self) -> None:
        r = self.retiro(en_cajon=True)
        self.s.commit()
        cj.atender(f"cj:retiro:{r.id}", session_factory=self.factory)
        self._refrescar()
        self.assertFalse(self.s.get(CajaRetiro, r.id).en_cajon)

    def test_desmarcar_cambia_lo_que_debe_quedar_en_el_cajon(self) -> None:
        # Esto es lo que de verdad arregla: el esperado sube porque ese dinero
        # nunca salió, y la diferencia deja de verse como faltante.
        from pos_uniformes.services.corte_caja_service import estado_caja

        r = self.retiro(monto="350", en_cajon=True)
        self.s.commit()
        antes = estado_caja(self.s).esperado
        cj.atender(f"cj:retiro:{r.id}", session_factory=self.factory)
        self._refrescar()
        self.assertEqual(estado_caja(self.s).esperado - antes, Decimal("350.00"))

    def test_un_boton_mal_formado_no_revienta(self) -> None:
        for malo in ("cj:", "cj:pago", "cj:pago:abc", "cj:otracosa:1"):
            aviso, _, _ = cj.atender(malo, session_factory=self.factory)
            self.assertEqual(aviso, "No conozco ese botón")

    def test_uno_que_ya_no_esta_en_el_periodo(self) -> None:
        aviso, texto, _ = cj.atender("cj:pago:99999", session_factory=self.factory)
        self.assertIn("ya no está", aviso)
        self.assertTrue(texto)

    def test_es_del_cajon(self) -> None:
        self.assertTrue(cj.es_del_cajon("cj:pago:1"))
        self.assertFalse(cj.es_del_cajon("m:raiz"))
        self.assertFalse(cj.es_del_cajon("av:ver:1"))


class EnganchadoAlBotTests(_Base):
    def test_el_comando_contesta_con_botones(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        self.pago(); self.s.commit()
        texto, botones = bot.responder("/cajon", session_factory=self.factory)
        self.assertIn("Evelyn", texto)
        self.assertIn("cj:pago:", botones)

    def test_el_toque_llega_por_el_bot(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        p = self.pago(en_cajon=True); self.s.commit()
        aviso, _, _ = bot.atender_toque(f"cj:pago:{p.id}", session_factory=self.factory)
        self.assertEqual(aviso, "No salió del cajón")

    def test_esta_en_la_ayuda_y_en_el_menu(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_menu_service as menu

        self.assertIn("/cajon", bot.AYUDA)
        self.assertIn("m:cajon", {d for fila in menu._RAIZ for _, d in fila})


if __name__ == "__main__":
    unittest.main()
