"""Pedir el préstamo en la Libreta y aprobarlo desde el celular.

La parte que se ve. Lo que se cuida: que el botón no se le ofrezca a quien no
debe, que aprobar mueva el dinero una sola vez, y que la solicitud no se
pierda si el celular no tiene señal en ese momento.
"""

from __future__ import annotations

import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaRetiro, Empleada, PrestamoEmpleada
from pos_uniformes.services import prestamos_service as pr
from pos_uniformes.services import telegram_prestamos_service as prs

_VENTANA = Path(__file__).resolve().parent.parent / "ui" / "quote_satellite_window.py"


class _Sesion:
    def __init__(self, s): self.s = s
    def __call__(self): return self
    def __enter__(self): return self.s
    def __exit__(self, *a): return False


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-5", nombre_completo="Fanny Ortiz", activo=True))
        self.s.flush()
        # Aquí se prueban el aviso y los botones, no el tope del 70%: ese
        # tiene sus propios tests en test_prestamos_service.
        margen = patch.object(pr, "ganado_hasta_hoy", return_value=Decimal("10000"))
        margen.start()
        self.addCleanup(margen.stop)

    def _pedir(self, monto="1500", motivo="para la renta"):
        p = pr.pedir(self.s, employee_code="VEND-5", nombre="Fanny Ortiz", monto=monto, motivo=motivo)
        self.s.flush()
        return p


class ElAvisoTest(_Base):
    def test_dice_quien_cuanto_y_para_que(self):
        texto = prs.aviso_de_solicitud(self._pedir())
        self.assertIn("Fanny Ortiz", texto)
        self.assertIn("$1,500.00", texto)
        self.assertIn("para la renta", texto)
        self.assertIn("/prestamos", texto)


class LaPantallaDelCelularTest(_Base):
    def _botones(self, botones):
        return [b["text"] for f in json.loads(botones)["inline_keyboard"] for b in f]

    def test_sin_nada_pendiente_lo_dice(self):
        texto, botones = prs.texto_y_botones(self.s)
        self.assertIn("No hay préstamos esperando", texto)
        self.assertEqual(self._botones(botones), ["‹ Menú"])

    def test_cada_solicitud_trae_su_boton_de_aprobar_y_de_rechazar(self):
        self._pedir()
        texto, botones = prs.texto_y_botones(self.s)
        self.assertIn("Fanny Ortiz — $1,500.00", texto)
        etiquetas = self._botones(botones)
        self.assertIn("✅ Fanny Ortiz $1,500", etiquetas)
        self.assertIn("✖️", etiquetas)

    def test_aprobar_saca_el_dinero_del_cajon_una_sola_vez(self):
        p = self._pedir()
        aviso, texto, _b = prs.atender(f"pr:ok:{p.id}", session_factory=_Sesion(self.s), quien="VEND-1")
        self.assertEqual(aviso, "Aprobado")
        self.assertIn("retiro del cajón", texto)
        self.assertEqual(len(self.s.scalars(select(CajaRetiro)).all()), 1)

        # El mismo botón otra vez (dedo doble): no vuelve a sacar dinero.
        aviso2, _t, _b = prs.atender(f"pr:ok:{p.id}", session_factory=_Sesion(self.s), quien="VEND-1")
        self.assertIn("aprobado", aviso2)
        self.assertEqual(len(self.s.scalars(select(CajaRetiro)).all()), 1)

    def test_rechazar_no_saca_dinero(self):
        p = self._pedir()
        aviso, texto, _b = prs.atender(f"pr:no:{p.id}", session_factory=_Sesion(self.s), quien="VEND-1")
        self.assertEqual(aviso, "Rechazado")
        self.assertEqual(self.s.scalars(select(CajaRetiro)).all(), [])

    def test_un_boton_inventado_no_truena(self):
        aviso, texto, botones = prs.atender("pr:loquesea", session_factory=_Sesion(self.s), quien="VEND-1")
        self.assertIn("No conozco", aviso)

    def test_el_bot_distingue_sus_botones(self):
        self.assertTrue(prs.es_de_prestamos("pr:ok:1"))
        self.assertFalse(prs.es_de_prestamos("m:pagos"))


class ElBotonDeLaLibretaTest(unittest.TestCase):
    """Se revisa el guion: armar la ventana entera pide base y gafete."""

    def setUp(self) -> None:
        self.fuente = _VENTANA.read_text(encoding="utf-8")

    def test_el_dueño_no_se_pide_prestamos_a_si_mismo(self):
        self.assertIn('es_dueno = str(code or "").upper() == "VEND-1"', self.fuente)

    def test_sin_gafete_no_se_ofrece(self):
        self.assertIn("if not code or es_dueno:", self.fuente)

    def test_si_ya_pidio_uno_no_se_le_ofrece_otro(self):
        self.assertIn("pendiente_de(session, code)", self.fuente)
        self.assertIn("Daniel todavía no responde", self.fuente)

    def test_si_le_van_a_descontar_se_lo_dice(self):
        self.assertIn("Se te descontarán", self.fuente)

    def test_el_formulario_trae_cantidades_de_un_toque(self):
        self.assertIn("(200, 500, 1000, 1500, 2000)", self.fuente)

    def test_no_le_ofrece_cantidades_que_no_caben_en_su_tope(self):
        self.assertIn("if Decimal(c) <= tope", self.fuente)

    def test_le_dice_de_frente_cuanto_puede_pedir(self):
        self.assertIn("Puedes pedir hasta", self.fuente)
        self.assertIn("el 70% de lo que llevas ganado", self.fuente)

    def test_recien_pagada_ni_siquiera_abre_el_formulario(self):
        # Sin nada ganado no hay de dónde descontarlo: se le dice y ya.
        self.assertIn("if tope <= 0:", self.fuente)
        self.assertIn("no llevas nada ganado", self.fuente)

    def test_si_el_celular_falla_la_solicitud_no_se_pierde(self):
        # Queda en la cola de alertas en vez de perderse.
        self.assertIn("from pos_uniformes.services.alertas_service import encolar", self.fuente)

    def test_el_boton_se_refresca_al_pintar_la_libreta(self):
        # Va donde se pinta, no en el control del gafete: ahí es parte de lo
        # que ella ve, y así se actualiza también al refrescar.
        import re

        cuerpo = re.search(
            r"def _refresh_libreta_view.*?\n    def ", self.fuente, re.S
        ).group(0)
        self.assertIn("self._libreta_prestamo_refrescar()", cuerpo)


if __name__ == "__main__":
    unittest.main()
