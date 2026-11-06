"""¿El contador de personas cuenta, y lo que cuenta tiene sentido?

Daniel, 2026-11-06: antes de mejorar las cámaras había que comprobar lo que
nunca se comprobó. `/camaras` lo dice con sus razones.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import AfluenciaHora, LibretaVenta
from pos_uniformes.services import camaras_revision_service as rev

HOY = date(2026, 11, 6)          # viernes
AHORA = datetime(2026, 11, 6, 12, 0)


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)

    def _cuenta(self, dias_atras: int, hora: int, *, entran=0, salen=0, pasan=0, camara="ENTRADA1.1") -> None:
        momento = datetime.combine(HOY - timedelta(days=dias_atras), time(hora, 0))
        self.s.add(AfluenciaHora(camara=camara, hora=momento, entradas=entran, salidas=salen,
                                 pasan=pasan, updated_at=momento + timedelta(minutes=59)))
        self.s.commit()

    def _ventas(self, dias_atras: int, cuantas: int, hora: int = 11) -> None:
        momento = datetime.combine(HOY - timedelta(days=dias_atras), time(hora, 15))
        for _ in range(cuantas):
            self.s.add(LibretaVenta(employee_code="VEND-4", employee_name="Fanny", tipo="venta",
                                    piezas=1, created_at=momento))
        self.s.commit()

    def _revisar(self) -> rev.Revision:
        return rev.revisar(self.s, hoy=HOY, ahora=AHORA)


class RevisionTests(_ConBase):
    def test_un_contador_sano_no_trae_hallazgos_pero_no_presume_exactitud(self) -> None:
        for d in (1, 2, 3):
            self._cuenta(d, 11, entran=30, salen=28)
            self._cuenta(d, 11, pasan=120, camara="ENTRADA1")
            self._ventas(d, 9)
        r = self._revisar()
        self.assertTrue(r.sano, r.hallazgos)
        self.assertEqual([(d.entradas, d.salidas, d.pasan, d.ventas) for d in r.dias], [(30, 28, 120, 9)] * 3)
        self.assertEqual(r.dias[0].conversion, 30.0)
        t = rev.texto(r)
        self.assertIn("✅ No se ve nada raro", t)
        self.assertIn("NO prueba que el número sea exacto", t)
        self.assertIn("jue 5/11 · 30 / 28 · 120 · 9 · 30%", t)

    def test_nunca_ha_contado(self) -> None:
        self._ventas(1, 8)
        r = self._revisar()
        self.assertIsNone(r.ultimo_dato)
        self.assertIn("NUNCA ha escrito nada", r.hallazgos[0])
        self.assertIn("⚠️ Lo que se ve mal", rev.texto(r))

    def test_dejo_de_contar_y_despues_hubo_ventas(self) -> None:
        self._cuenta(5, 11, entran=30, salen=30)
        self._ventas(5, 9)
        self._ventas(2, 9)
        self._ventas(1, 9)
        r = self._revisar()
        self.assertTrue(any("se detuvo" in h and "dom 1/11" in h for h in r.hallazgos), r.hallazgos)
        self.assertTrue(any("sin nadie entrando" in h and "jue 5/11 (9 ventas)" in h for h in r.hallazgos))

    def test_mas_ventas_que_gente_es_contar_de_menos(self) -> None:
        self._cuenta(1, 11, entran=4, salen=4)
        self._ventas(1, 9)
        r = self._revisar()
        self.assertTrue(any("contando de menos" in h and "9 ventas, 4 entran" in h for h in r.hallazgos), r.hallazgos)

    def test_entran_muchos_y_no_sale_nadie_es_la_linea(self) -> None:
        for d in (1, 2):
            self._cuenta(d, 11, entran=60, salen=5)
            self._ventas(d, 9)
        r = self._revisar()
        self.assertTrue(any("Entraron 120 y salieron 10" in h for h in r.hallazgos), r.hallazgos)

    def test_con_pocos_cruces_no_se_acusa_a_la_linea(self) -> None:
        self._cuenta(1, 11, entran=6, salen=1)
        self._ventas(1, 2)
        self.assertTrue(self._revisar().sano)

    def test_una_camara_que_no_conto_nada_se_nombra(self) -> None:
        self._cuenta(1, 11, entran=30, salen=29)
        self._cuenta(1, 11, camara="ENTRADA2.2")           # existe, en ceros
        self._ventas(1, 9)
        r = self._revisar()
        self.assertTrue(any("ENTRADA2.2" in h for h in r.hallazgos), r.hallazgos)

    def test_hoy_no_se_juzga_porque_va_a_medias(self) -> None:
        self._cuenta(1, 11, entran=30, salen=30)
        self._ventas(1, 9)
        self._ventas(0, 9, hora=9)                         # hoy: ventas y todavía sin conteo
        r = self._revisar()
        self.assertTrue(r.sano, r.hallazgos)
        self.assertNotIn(HOY, [d.dia for d in r.dias])

    def test_un_dia_flojo_sin_gente_no_prueba_nada(self) -> None:
        self._cuenta(2, 11, entran=30, salen=30)
        self._ventas(2, 9)
        self._ventas(1, 2)                                 # 2 ventas y nadie contado: poco para juzgar
        self.assertTrue(self._revisar().sano)


class ComandoTests(_ConBase):
    def test_el_bot_contesta_camaras(self) -> None:
        from contextlib import contextmanager

        from pos_uniformes.services import telegram_bot_service as bot

        self._cuenta(1, 11, entran=30, salen=28)
        self._ventas(1, 9)

        @contextmanager
        def fabrica():
            yield self.s

        texto = bot.atender_texto("/camaras", session_factory=fabrica, hoy=HOY)
        self.assertIn("Revisión del contador de personas", texto)
        self.assertIn("/camaras", bot.AYUDA)


if __name__ == "__main__":
    unittest.main()
