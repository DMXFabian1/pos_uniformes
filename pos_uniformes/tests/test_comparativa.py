"""¿$4,200 es bueno? Comparar contra los mismos días de antes.

El bot daba cifras y ninguna manera de juzgarlas. Lo que se cuida aquí son las
dos decisiones que hacen que la comparación valga: mismo día de la semana, y
hasta la misma hora.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import comparativa_service as comp


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.addCleanup(self.s.close)
        self.viernes = date(2026, 10, 2)

    def vender(self, dia: date, monto: str, hora: int = 10) -> None:
        self.s.add(
            LibretaVenta(
                employee_code="VEND-3", employee_name="Evelyn", tipo="venta",
                piezas=1, monto_total=Decimal(monto),
                created_at=datetime.combine(dia, datetime.min.time()).replace(hour=hora).astimezone(),
            )
        )
        self.s.flush()


class ContraElMismoDiaTests(_Base):
    def test_compara_contra_los_mismos_dias_de_la_semana(self) -> None:
        # Una tienda de uniformes no vende igual lunes que sábado: comparar
        # contra "ayer" habla del calendario, no del negocio.
        for semanas in range(1, 5):
            self.vender(self.viernes - timedelta(weeks=semanas), "1000")
        self.vender(self.viernes - timedelta(days=1), "99999")   # jueves: no cuenta
        self.vender(self.viernes, "1500")
        c = comp.comparar(self.s, self.viernes, ahora=self._fin_del_dia())
        self.assertEqual(c.referencia, Decimal("1000.00"))
        self.assertEqual(c.pct, 50)

    def _fin_del_dia(self) -> datetime:
        return datetime.combine(self.viernes, datetime.min.time()).replace(hour=23).astimezone()

    def test_un_dia_cerrado_no_arrastra_el_promedio(self) -> None:
        # Promediar un cero convierte un día bueno en uno malo.
        self.vender(self.viernes - timedelta(weeks=1), "2000")
        # las otras tres semanas: sin ventas (cerrado, festivo)
        self.vender(self.viernes, "2000")
        c = comp.comparar(self.s, self.viernes, ahora=self._fin_del_dia())
        self.assertEqual(c.referencia, Decimal("2000.00"))
        self.assertEqual(c.pct, 0)

    def test_sin_historia_no_se_inventa_nada(self) -> None:
        self.vender(self.viernes, "1500")
        c = comp.comparar(self.s, self.viernes, ahora=self._fin_del_dia())
        self.assertIsNone(c.referencia)
        self.assertIsNone(c.pct)
        self.assertEqual(comp.texto(c), "")

    def test_el_mejor_del_mes_se_nota(self) -> None:
        for semanas, monto in ((1, "1000"), (2, "1200"), (3, "900"), (4, "1100")):
            self.vender(self.viernes - timedelta(weeks=semanas), monto)
        self.vender(self.viernes, "5000")
        c = comp.comparar(self.s, self.viernes, ahora=self._fin_del_dia())
        self.assertTrue(c.mejor_de_los_mismos)
        self.assertIn("mejor viernes", comp.texto(c))


class HastaLaMismaHoraTests(_Base):
    def test_a_media_mañana_no_compara_contra_el_dia_completo(self) -> None:
        # Este es el corazón del asunto: a las 11 llevas dos horas de venta.
        # Compararlas contra un día entero diría que vas hundido SIEMPRE, y un
        # bot que siempre da malas noticias se ignora.
        pasado = self.viernes - timedelta(weeks=1)
        self.vender(pasado, "500", hora=10)     # mañana
        self.vender(pasado, "4500", hora=17)    # tarde
        self.vender(self.viernes, "500", hora=10)
        once = datetime.combine(self.viernes, datetime.min.time()).replace(hour=11).astimezone()
        c = comp.comparar(self.s, self.viernes, ahora=once)
        self.assertEqual(c.hoy, Decimal("500.00"))
        self.assertEqual(c.referencia, Decimal("500.00"))   # solo la mañana del otro
        self.assertEqual(c.pct, 0)

    def test_el_dia_completo_cuando_ya_cerro(self) -> None:
        pasado = self.viernes - timedelta(weeks=1)
        self.vender(pasado, "500", hora=10)
        self.vender(pasado, "4500", hora=17)
        self.vender(self.viernes, "500", hora=10)
        tarde = datetime.combine(self.viernes, datetime.min.time()).replace(hour=23).astimezone()
        c = comp.comparar(self.s, self.viernes, ahora=tarde)
        self.assertEqual(c.referencia, Decimal("5000.00"))

    def test_mirar_un_dia_pasado_lo_toma_completo(self) -> None:
        # Si se pregunta por el martes de la semana pasada, no tiene sentido
        # cortarlo a la hora que es hoy.
        c = comp.comparar(self.s, self.viernes - timedelta(days=7), ahora=self._ahora())
        self.assertIsNone(c.hasta_hora)

    def _ahora(self) -> datetime:
        return datetime.combine(self.viernes, datetime.min.time()).replace(hour=11).astimezone()


class ComoSeLeeTests(_Base):
    def _con(self, hoy: str, antes: list[str]) -> comp.Comparativa:
        for i, monto in enumerate(antes, start=1):
            self.vender(self.viernes - timedelta(weeks=i), monto)
        self.vender(self.viernes, hoy)
        fin = datetime.combine(self.viernes, datetime.min.time()).replace(hour=23).astimezone()
        return comp.comparar(self.s, self.viernes, ahora=fin)

    def test_una_diferencia_chica_es_un_dia_normal(self) -> None:
        # Fingir precisión en el ±3% es inventar una señal donde hay ruido.
        texto = comp.texto(self._con("1030", ["1000", "1000"]))
        self.assertIn("Como un viernes normal", texto)

    def test_arriba_y_abajo_se_dicen_distinto(self) -> None:
        self.assertIn("arriba", comp.texto(self._con("2000", ["1000"])))

    def test_abajo(self) -> None:
        self.assertIn("abajo", comp.texto(self._con("400", ["1000"])))

    def test_dice_el_dia_de_la_semana(self) -> None:
        self.assertIn("viernes", comp.texto(self._con("2000", ["1000"])))


if __name__ == "__main__":
    unittest.main()
