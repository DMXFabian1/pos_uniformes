"""El aviso de descanso: se decide desde el mensaje, viendo cómo queda la semana.

Daniel pidió poder ver el calendario para saber si conviene (2026-10-05), así
que lo que se cuida aquí es que el panorama VAYA en el mensaje —no en otro
comando— y que lo que falta se note en vez de pasar por bueno.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from pos_uniformes.services import descansos_service as ds
from pos_uniformes.services import telegram_descansos_service as dsc

MIERCOLES = date(2026, 10, 7)


def _ctx(**kw):
    base = dict(
        fecha=MIERCOLES, nombre_dia="miércoles",
        quien_mas_descansa=[], trabajan_ese_dia=["Evelyn", "Stayce"],
        semana=[], venta_tipica=None, venta_tipica_de_cuantos=0,
        es_el_dia_mas_movido=False, tiene_pago=False, tiene_conteo=[],
    )
    base.update(kw)
    return ds.Contexto(**base)


class ElPanoramaTests(unittest.TestCase):
    def test_dice_quien_mas_descansa_y_quien_queda(self) -> None:
        texto = "\n".join(dsc.texto_de_contexto(_ctx(quien_mas_descansa=["Naye"])))
        self.assertIn("ya descansa: Naye", texto)
        self.assertIn("Quedarían trabajando: Evelyn, Stayce", texto)

    def test_cuando_no_descansa_nadie_mas_tambien_lo_dice(self) -> None:
        """El silencio no sirve: hay que poder leer que ese día está libre."""
        self.assertIn("no descansa nadie más", "\n".join(dsc.texto_de_contexto(_ctx())))

    def test_grita_cuando_no_quedaria_nadie(self) -> None:
        texto = "\n".join(dsc.texto_de_contexto(_ctx(trabajan_ese_dia=[])))
        self.assertIn("⚠️", texto)
        self.assertIn("NADIE", texto)

    def test_marca_cuando_quedaria_corta(self) -> None:
        texto = "\n".join(dsc.texto_de_contexto(
            _ctx(quien_mas_descansa=["Naye", "Fanny"])
        ))
        self.assertIn("⚠️", texto)

    def test_dice_que_tan_movido_es_ese_dia(self) -> None:
        texto = "\n".join(dsc.texto_de_contexto(
            _ctx(venta_tipica=Decimal("18450"), venta_tipica_de_cuantos=4,
                 es_el_dia_mas_movido=True)
        ))
        self.assertIn("Los miércoles se vende $18,450", texto)
        self.assertIn("4 de referencia", texto)
        self.assertIn("el día más movido", texto)

    def test_los_sabados_no_los_sabado(self) -> None:
        texto = "\n".join(dsc.texto_de_contexto(
            _ctx(nombre_dia="sábado", venta_tipica=Decimal("22000"),
                 venta_tipica_de_cuantos=4)
        ))
        self.assertIn("Los sábados se vende", texto)
        texto_mie = "\n".join(dsc.texto_de_contexto(
            _ctx(venta_tipica=Decimal("14000"), venta_tipica_de_cuantos=4)
        ))
        self.assertIn("Los miércoles se vende", texto_mie)

    def test_sin_dato_de_venta_no_inventa_el_renglon(self) -> None:
        self.assertNotIn("se vende", "\n".join(dsc.texto_de_contexto(_ctx())))

    def test_avisa_del_pago_y_del_conteo(self) -> None:
        texto = "\n".join(dsc.texto_de_contexto(
            _ctx(tiene_pago=True, tiene_conteo=["Justo Sierra", "Conalep"])
        ))
        self.assertIn("le toca cobrar", texto)
        self.assertIn("Justo Sierra, Conalep", texto)

    def test_la_semana_se_puede_leer_de_un_golpe(self) -> None:
        semana = [
            ds.DiaDeLaSemana(fecha=date(2026, 10, 5), nombre="lunes", trabajan=["A", "B"]),
            ds.DiaDeLaSemana(fecha=MIERCOLES, nombre="miércoles", trabajan=["A"],
                             descansan=["B"], es_el_pedido=True),
        ]
        texto = "\n".join(dsc.texto_de_contexto(_ctx(semana=semana)))
        self.assertIn("lun 05/10", texto)
        self.assertIn("mié 07/10", texto)
        self.assertIn("←", texto)   # el día que se está decidiendo


class ElAvisoTests(unittest.TestCase):
    def _solicitud(self):
        return SimpleNamespace(
            id=7, employee_code="VEND-5", employee_name="Cristal Torres",
            fecha=MIERCOLES, motivo="Escuela", estado=ds.PEDIDO,
        )

    def test_el_aviso_sale_aunque_no_haya_panorama(self) -> None:
        """Un dato que falta no puede impedir que Daniel conteste."""
        texto = dsc.aviso_de_solicitud(self._solicitud(), session=None, hoy=date(2026, 10, 5))
        self.assertIn("Cristal", texto)
        self.assertIn("miércoles 07/10", texto)
        self.assertIn("en 2 días", texto)
        self.assertIn("Escuela", texto)

    def test_los_botones_van_colgados_del_aviso(self) -> None:
        botones = dsc.botones_de(self._solicitud())
        self.assertIn("dc:ok:7", botones)
        self.assertIn("dc:no:7", botones)

    def test_lo_de_hoy_y_lo_de_mañana_se_dicen_asi(self) -> None:
        s = self._solicitud()
        s.fecha = date(2026, 10, 5)
        self.assertIn("HOY", dsc.aviso_de_solicitud(s, hoy=date(2026, 10, 5)))
        s.fecha = date(2026, 10, 6)
        self.assertIn("mañana", dsc.aviso_de_solicitud(s, hoy=date(2026, 10, 5)))

    def test_reconoce_sus_propios_botones(self) -> None:
        self.assertTrue(dsc.es_de_descansos("dc:ok:7"))
        self.assertFalse(dsc.es_de_descansos("pr:ok:7"))


if __name__ == "__main__":
    unittest.main()
