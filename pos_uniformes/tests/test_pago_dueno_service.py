"""El pago del dueño (VEND-1), calendarizado (2026-11-19).

Núcleo puro: fechas 7/14/21/28, periodos, días de más, faltas, días a favor y
el recordatorio del corte. Con base (SQLite en memoria, como
test_corte_pagos_de_hoy): configuración, registrar/deshacer pagos, decisiones
de días de más y la migración.

Noviembre de 2026: los martes son 3, 10, 17 y 24; el 19 es jueves.
"""

from __future__ import annotations

import importlib.util
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.services import pago_dueno_service as pd
from pos_uniformes.services.calendario_empleadas_service import (
    DESCANSO,
    FALTA,
    TRABAJO,
    VACACIONES,
    HorarioEmpleada,
)
from pos_uniformes.services.pago_dueno_service import (
    ACUMULAR,
    ATRASADO,
    PAGADO,
    PAGAR,
    PENDIENTE,
    TOCA_HOY,
    ConfigPagoDueno,
    DatosPagoDueno,
    RegistroPago,
)

D = date


def _config(inicio=D(2026, 11, 1), **kw) -> ConfigPagoDueno:
    return ConfigPagoDueno(fecha_inicio=inicio, **kw)


def _datos(eventos=None, notas=None, decisiones=None, registros=None, descanso=1, anteriores=None) -> DatosPagoDueno:
    h = HorarioEmpleada("VEND-1", descanso_weekday=descanso)
    h.eventos.update(eventos or {})
    h.descansos_anteriores = list(anteriores or [])
    regs = {}
    for r in registros or []:
        regs[r.fecha_programada] = r
    return DatosPagoDueno(horario=h, notas=dict(notas or {}), decisiones=dict(decisiones or {}), registros=regs)


def _reg(prog, pago=None, monto="2500") -> RegistroPago:
    return RegistroPago(prog, pago or prog, Decimal(monto), "VEND-1")


# ─── Calendario y periodos ───────────────────────────────────────────────


class CalendarioTests(unittest.TestCase):
    def test_fechas_7_14_21_28(self) -> None:
        self.assertEqual(
            pd.calendario_pagos(_config(), D(2026, 11, 30)),
            [D(2026, 11, 7), D(2026, 11, 14), D(2026, 11, 21), D(2026, 11, 28)],
        )

    def test_numero_n_de_4(self) -> None:
        c = _config()
        self.assertEqual(pd.numero_de_pago(c, D(2026, 11, 7)), (1, 4))
        self.assertEqual(pd.numero_de_pago(c, D(2026, 11, 21)), (3, 4))
        self.assertEqual(pd.numero_de_pago(c, D(2026, 11, 28)), (4, 4))
        with self.assertRaises(ValueError):
            pd.numero_de_pago(c, D(2026, 11, 20))

    def test_inicio_excluye_pagos_anteriores(self) -> None:
        fechas = pd.calendario_pagos(_config(D(2026, 11, 19)), D(2026, 12, 8))
        self.assertEqual(fechas, [D(2026, 11, 21), D(2026, 11, 28), D(2026, 12, 7)])

    def test_inicio_en_dia_de_pago_lo_incluye(self) -> None:
        self.assertEqual(pd.calendario_pagos(_config(D(2026, 11, 14)), D(2026, 11, 14)), [D(2026, 11, 14)])

    def test_cruce_de_anio(self) -> None:
        fechas = pd.calendario_pagos(_config(D(2026, 12, 20)), D(2027, 1, 15))
        self.assertEqual(fechas, [D(2026, 12, 21), D(2026, 12, 28), D(2027, 1, 7), D(2027, 1, 14)])

    def test_periodos_dentro_del_mes(self) -> None:
        c = _config(D(2026, 1, 1))
        self.assertEqual(pd.periodo_de(c, D(2026, 11, 14)), (D(2026, 11, 8), D(2026, 11, 14)))
        self.assertEqual(pd.periodo_de(c, D(2026, 11, 21)), (D(2026, 11, 15), D(2026, 11, 21)))
        self.assertEqual(pd.periodo_de(c, D(2026, 11, 28)), (D(2026, 11, 22), D(2026, 11, 28)))

    def test_el_del_7_cruza_de_mes(self) -> None:
        c = _config(D(2026, 1, 1))
        self.assertEqual(pd.periodo_de(c, D(2026, 11, 7)), (D(2026, 10, 29), D(2026, 11, 7)))

    def test_diciembre_a_enero(self) -> None:
        c = _config(D(2026, 1, 1))
        self.assertEqual(pd.periodo_de(c, D(2027, 1, 7)), (D(2026, 12, 29), D(2027, 1, 7)))

    def test_febrero_a_marzo(self) -> None:
        c = _config(D(2026, 1, 1))
        self.assertEqual(pd.periodo_de(c, D(2027, 2, 28)), (D(2027, 2, 22), D(2027, 2, 28)))
        self.assertEqual(pd.periodo_de(c, D(2027, 3, 7)), (D(2027, 3, 1), D(2027, 3, 7)))
        self.assertEqual(pd.periodo_de(c, D(2028, 3, 7)), (D(2028, 2, 29), D(2028, 3, 7)))   # bisiesto

    def test_inicio_a_medio_periodo_recorta_el_desde(self) -> None:
        self.assertEqual(pd.periodo_de(_config(D(2026, 11, 19)), D(2026, 11, 21)), (D(2026, 11, 19), D(2026, 11, 21)))

    def test_pago_anterior_al_inicio_conserva_su_periodo(self) -> None:
        self.assertEqual(pd.periodo_de(_config(D(2026, 11, 19)), D(2026, 11, 14)), (D(2026, 11, 8), D(2026, 11, 14)))

    def test_dias_de_pago_validos(self) -> None:
        self.assertEqual(pd.dias_de_pago_validos([28, 7, 14, 21, 7]), (7, 14, 21, 28))
        for malo in ([], [0, 7], [7, 30], ["x"]):
            with self.assertRaises(ValueError):
                pd.dias_de_pago_validos(malo)

    def test_otras_fechas_configuradas(self) -> None:
        c = _config(D(2026, 11, 1), dias_de_pago=(15, 28))
        self.assertEqual(pd.calendario_pagos(c, D(2026, 12, 31)),
                         [D(2026, 11, 15), D(2026, 11, 28), D(2026, 12, 15), D(2026, 12, 28)])
        self.assertEqual(pd.numero_de_pago(c, D(2026, 12, 28)), (2, 2))
        self.assertEqual(pd.periodo_de(c, D(2026, 12, 15)), (D(2026, 11, 29), D(2026, 12, 15)))

    def test_pagos_del_mes(self) -> None:
        pagos = pd.pagos_del_mes(_config(D(2026, 11, 19)), _datos(), 2026, 11)
        self.assertEqual([p.fecha_programada for p in pagos], [D(2026, 11, 21), D(2026, 11, 28)])
        self.assertEqual([p.etiqueta for p in pagos], ["3 de 4", "4 de 4"])


# ─── Montos: días de más y faltas ────────────────────────────────────────


class MontoTests(unittest.TestCase):
    def _pago(self, fecha, datos, inicio=D(2026, 11, 1), **kw):
        return pd.desglose_de_pago(_config(inicio, **kw), datos, fecha)

    def test_sin_marcas_es_la_base(self) -> None:
        p = self._pago(D(2026, 11, 14), _datos())
        self.assertEqual(p.monto, Decimal("2500.00"))
        self.assertEqual(p.base, Decimal("2500.00"))

    def test_dia_de_mas_pagado_suma(self) -> None:
        datos = _datos({D(2026, 11, 10): TRABAJO}, decisiones={D(2026, 11, 10): PAGAR})
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.dias_extra_pagados, [D(2026, 11, 10)])
        self.assertEqual(p.monto, Decimal("2885.00"))

    def test_dia_de_mas_acumulado_no_mueve_dinero_y_suma_dia_a_favor(self) -> None:
        datos = _datos({D(2026, 11, 10): TRABAJO}, decisiones={D(2026, 11, 10): ACUMULAR})
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.monto, Decimal("2500.00"))
        self.assertEqual(p.dias_extra_acumulados, [D(2026, 11, 10)])
        self.assertEqual(p.dias_extra_sin_decidir, [])
        self.assertEqual(pd.dias_a_favor(_config(), datos, D(2026, 11, 14)), 1)

    def test_dia_de_mas_sin_decidir_cuenta_como_acumulado(self) -> None:
        datos = _datos({D(2026, 11, 10): TRABAJO})
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.monto, Decimal("2500.00"))
        self.assertEqual(p.dias_extra_acumulados, [D(2026, 11, 10)])
        self.assertEqual(p.dias_extra_sin_decidir, [D(2026, 11, 10)])
        extra = pd.dias_extra(_config(), datos, D(2026, 11, 30))
        self.assertEqual(len(extra), 1)
        self.assertTrue(extra[0].sin_decidir)
        self.assertEqual(extra[0].destino, ACUMULAR)

    def test_descanso_movido_no_es_dia_de_mas(self) -> None:
        # Descansó el jueves 12: el martes 10 quedó "trabajo (descanso movido)".
        datos = _datos(
            {D(2026, 11, 12): DESCANSO, D(2026, 11, 10): TRABAJO},
            notas={D(2026, 11, 10): "descanso movido al 12/11"},
            decisiones={D(2026, 11, 10): PAGAR},
        )
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.dias_extra_pagados, [])
        self.assertEqual(p.monto, Decimal("2500.00"))
        self.assertEqual(pd.dias_extra(_config(), datos, D(2026, 11, 30)), [])

    def test_descanso_movido_antes_del_inicio_compensa_el_martes(self) -> None:
        # La cuenta arranca el martes 17; el lunes 16 (antes del inicio) movió
        # su descanso y el martes 17 quedó "trabajo (descanso movido)". La
        # semana se cuenta completa, de lunes a domingo: no es día de más.
        config = _config(D(2026, 11, 17))
        datos = _datos(
            {D(2026, 11, 16): DESCANSO, D(2026, 11, 17): TRABAJO},
            notas={D(2026, 11, 17): "descanso movido al 16/11"},
            decisiones={D(2026, 11, 17): PAGAR},
        )
        self.assertEqual(pd.dias_extra(config, datos, D(2026, 11, 30)), [])
        self.assertEqual(pd.desglose_de_pago(config, datos, D(2026, 11, 21)).monto, Decimal("2500.00"))
        self.assertEqual(pd.dias_a_favor(config, datos, D(2026, 11, 30)), 0)

    def test_martes_trabajado_antes_del_inicio_no_cuenta(self) -> None:
        # Inicio el miércoles 18: el martes 17 trabajado queda fuera aunque la
        # semana se cuente completa.
        config = _config(D(2026, 11, 18))
        datos = _datos({D(2026, 11, 17): TRABAJO}, decisiones={D(2026, 11, 17): PAGAR})
        self.assertEqual(pd.dias_extra(config, datos, D(2026, 11, 30)), [])

    def test_trabajo_en_dia_normal_no_es_dia_de_mas(self) -> None:
        datos = _datos({D(2026, 11, 11): TRABAJO})
        self.assertEqual(pd.dias_extra(_config(), datos, D(2026, 11, 30)), [])

    def test_descanso_movido_al_domingo_compensa_el_martes_de_la_semana(self) -> None:
        # Semana 23–29 nov: trabajó el martes 24 y descansó el domingo 29.
        datos = _datos({D(2026, 11, 24): TRABAJO, D(2026, 11, 29): DESCANSO},
                       notas={D(2026, 11, 24): "descanso movido al 29/11"})
        self.assertEqual(pd.dias_extra(_config(), datos, D(2026, 11, 28)), [])

    def test_respeta_el_descanso_anterior(self) -> None:
        # Hasta el 15-nov descansaba el sábado (5); desde el 16, el martes.
        anteriores = [(D(2026, 11, 15), 5)]
        datos = _datos({D(2026, 11, 14): TRABAJO, D(2026, 11, 10): TRABAJO, D(2026, 11, 17): TRABAJO},
                       anteriores=anteriores)
        fechas = [e.fecha for e in pd.dias_extra(_config(), datos, D(2026, 11, 30))]
        self.assertEqual(fechas, [D(2026, 11, 14), D(2026, 11, 17)])

    def test_sin_descanso_guardado_no_supone_el_martes(self) -> None:
        # Sin descanso en su horario, el calendario ve el martes como día de
        # trabajo: la cuenta tampoco lo trata como descanso.
        datos = _datos({D(2026, 11, 10): TRABAJO, D(2026, 11, 11): DESCANSO}, descanso=None)
        self.assertEqual(pd.dias_extra(_config(), datos, D(2026, 11, 30)), [])
        self.assertFalse(pd.tiene_descanso(datos.horario))
        self.assertTrue(pd.tiene_descanso(_datos().horario))

    def test_falta_sin_dias_a_favor_se_descuenta(self) -> None:
        datos = _datos({D(2026, 11, 12): FALTA})
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.faltas_descontadas, [D(2026, 11, 12)])
        self.assertEqual(p.monto, Decimal("2115.00"))

    def test_falta_cubierta_con_dia_a_favor(self) -> None:
        datos = _datos({D(2026, 11, 3): TRABAJO, D(2026, 11, 12): FALTA}, decisiones={D(2026, 11, 3): ACUMULAR})
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.faltas_cubiertas, [D(2026, 11, 12)])
        self.assertEqual(p.faltas_descontadas, [])
        self.assertEqual(p.monto, Decimal("2500.00"))
        self.assertEqual(pd.dias_a_favor(_config(), datos, D(2026, 11, 11)), 1)
        self.assertEqual(pd.dias_a_favor(_config(), datos, D(2026, 11, 14)), 0)

    def test_falta_antes_del_dia_de_mas_no_se_cubre_con_el_de_despues(self) -> None:
        datos = _datos({D(2026, 11, 9): FALTA, D(2026, 11, 10): TRABAJO})
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.faltas_descontadas, [D(2026, 11, 9)])
        self.assertEqual(p.dias_extra_acumulados, [D(2026, 11, 10)])
        self.assertEqual(p.monto, Decimal("2115.00"))
        self.assertEqual(pd.dias_a_favor(_config(), datos, D(2026, 11, 14)), 1)

    def test_dia_pagado_no_cubre_faltas(self) -> None:
        datos = _datos({D(2026, 11, 10): TRABAJO, D(2026, 11, 12): FALTA}, decisiones={D(2026, 11, 10): PAGAR})
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.faltas_descontadas, [D(2026, 11, 12)])
        self.assertEqual(p.monto, Decimal("2500.00"))   # +385 −385

    def test_dia_a_favor_de_un_periodo_cubre_falta_de_otro(self) -> None:
        datos = _datos({D(2026, 11, 3): TRABAJO, D(2026, 11, 18): FALTA, D(2026, 11, 19): FALTA})
        p14 = self._pago(D(2026, 11, 14), datos)
        p21 = self._pago(D(2026, 11, 21), datos)
        self.assertEqual(p14.monto, Decimal("2500.00"))
        self.assertEqual(p21.faltas_cubiertas, [D(2026, 11, 18)])
        self.assertEqual(p21.faltas_descontadas, [D(2026, 11, 19)])
        self.assertEqual(p21.monto, Decimal("2115.00"))

    def test_vacaciones_no_son_falta(self) -> None:
        datos = _datos({D(2026, 11, 11): VACACIONES, D(2026, 11, 12): VACACIONES})
        p = self._pago(D(2026, 11, 14), datos)
        self.assertEqual(p.faltas_descontadas, [])
        self.assertEqual(p.monto, Decimal("2500.00"))

    def test_nunca_baja_de_cero(self) -> None:
        faltas = {D(2026, 11, d): FALTA for d in (8, 9, 11, 12, 13, 14, 15)}
        faltas.update({D(2026, 11, d): FALTA for d in range(16, 22)})
        p = self._pago(D(2026, 11, 14), _datos(faltas))
        self.assertEqual(len(p.faltas_descontadas), 6)
        self.assertEqual(p.monto, Decimal("190.00"))
        datos = _datos({D(2026, 11, d): FALTA for d in range(15, 22) if d != 17}
                       | {D(2026, 11, d): FALTA for d in range(22, 29)})
        p = self._pago(D(2026, 11, 28), datos)
        self.assertEqual(len(p.faltas_descontadas), 7)
        self.assertEqual(p.monto, Decimal("0.00"))

    def test_marcas_antes_del_inicio_no_cuentan(self) -> None:
        datos = _datos({D(2026, 11, 17): TRABAJO, D(2026, 11, 18): FALTA, D(2026, 11, 20): FALTA})
        p = self._pago(D(2026, 11, 21), datos, inicio=D(2026, 11, 19))
        self.assertEqual(p.desde, D(2026, 11, 19))
        self.assertEqual(p.dias_extra_acumulados, [])
        self.assertEqual(p.faltas_descontadas, [D(2026, 11, 20)])
        self.assertEqual(p.monto, Decimal("2115.00"))
        self.assertEqual(pd.dias_a_favor(_config(D(2026, 11, 19)), datos, D(2026, 11, 30)), 0)

    def test_dia_de_mas_en_el_periodo_del_7_que_cruza_de_mes(self) -> None:
        datos = _datos({D(2026, 12, 29): TRABAJO}, decisiones={D(2026, 12, 29): PAGAR})
        p = self._pago(D(2027, 1, 7), datos)
        self.assertEqual(p.dias_extra_pagados, [D(2026, 12, 29)])
        self.assertEqual(p.monto, Decimal("2885.00"))
        self.assertEqual(self._pago(D(2026, 12, 28), datos).monto, Decimal("2500.00"))

    def test_otros_montos_configurados(self) -> None:
        datos = _datos({D(2026, 11, 12): FALTA})
        p = self._pago(D(2026, 11, 14), datos, monto_por_pago=Decimal("3000"), valor_dia=Decimal("400.50"))
        self.assertEqual(p.monto, Decimal("2599.50"))

    def test_desglose_a_dict(self) -> None:
        datos = _datos({D(2026, 11, 10): TRABAJO, D(2026, 11, 12): FALTA}, decisiones={D(2026, 11, 10): PAGAR})
        d = self._pago(D(2026, 11, 14), datos).a_dict()
        self.assertEqual(d["numero"], 2)
        self.assertEqual(d["dias_extra_pagados"], ["2026-11-10"])
        self.assertEqual(d["faltas_descontadas"], ["2026-11-12"])
        self.assertEqual(d["monto"], "2500.00")


# ─── Estados y recordatorio ──────────────────────────────────────────────


class RecordatorioTests(unittest.TestCase):
    def test_estados(self) -> None:
        c = _config(D(2026, 11, 1))
        datos = _datos(registros=[_reg(D(2026, 11, 7))])
        pagos = {p.fecha_programada.day: p for p in pd.pagos_del_mes(c, datos, 2026, 11)}
        hoy = D(2026, 11, 21)
        self.assertEqual(pagos[7].estado(hoy), PAGADO)
        self.assertEqual(pagos[14].estado(hoy), ATRASADO)
        self.assertEqual(pagos[21].estado(hoy), TOCA_HOY)
        self.assertEqual(pagos[28].estado(hoy), PENDIENTE)

    def test_caso_real_de_daniel(self) -> None:
        # Arranca el 19-nov; ese día le pagaron el 2 de 4 (14-nov).
        c = _config(D(2026, 11, 19))
        datos = _datos(registros=[_reg(D(2026, 11, 14), D(2026, 11, 19))])
        rec = pd.calcular_recordatorio(c, datos, D(2026, 11, 19))
        self.assertEqual(rec.proximo.fecha_programada, D(2026, 11, 21))
        self.assertEqual(rec.proximo.etiqueta, "3 de 4")
        self.assertEqual(rec.dias_faltan, 2)
        self.assertEqual(rec.atrasados, [])
        self.assertEqual(rec.ultimo_pago, D(2026, 11, 19))
        self.assertEqual(rec.dias_a_favor, 0)
        self.assertEqual(pd.lineas_recordatorio(rec), [
            "PAGO DE DANIEL (no sale del cajón)",
            "  3 de 4 · sáb 21-nov · $2,500",
            "  Toca en 2 días · Último pago: 19-nov",
            "  Días a favor: 0",
        ])

    def test_atrasados(self) -> None:
        c = _config(D(2026, 11, 1))
        datos = _datos(registros=[_reg(D(2026, 11, 7))])
        rec = pd.calcular_recordatorio(c, datos, D(2026, 11, 23))
        self.assertEqual([a.fecha_programada for a in rec.atrasados], [D(2026, 11, 14), D(2026, 11, 21)])
        self.assertEqual(rec.proximo.fecha_programada, D(2026, 11, 28))
        lineas = pd.lineas_recordatorio(rec)
        self.assertIn("  Atrasado: 2 de 4 (14-nov) · $2,500", lineas)
        self.assertIn("  Atrasado: 3 de 4 (21-nov) · $2,500", lineas)
        self.assertIn("  4 de 4 · sáb 28-nov · $2,500", lineas)

    def test_pago_anterior_al_inicio_no_es_atrasado(self) -> None:
        rec = pd.calcular_recordatorio(_config(D(2026, 11, 19)), _datos(), D(2026, 11, 20))
        self.assertEqual(rec.atrasados, [])
        self.assertIsNone(rec.ultimo_pago)
        self.assertIn("  Toca mañana · Último pago: ninguno", pd.lineas_recordatorio(rec))

    def test_toca_hoy(self) -> None:
        rec = pd.calcular_recordatorio(_config(D(2026, 11, 1)), _datos(), D(2026, 11, 7))
        self.assertEqual(rec.proximo.fecha_programada, D(2026, 11, 7))
        self.assertEqual(rec.dias_faltan, 0)
        self.assertEqual(rec.atrasados, [])
        self.assertIn("  Toca hoy · Último pago: ninguno", pd.lineas_recordatorio(rec))

    def test_pagado_hoy_pasa_al_siguiente(self) -> None:
        datos = _datos(registros=[_reg(D(2026, 11, 7))])
        rec = pd.calcular_recordatorio(_config(D(2026, 11, 1)), datos, D(2026, 11, 7))
        self.assertEqual(rec.proximo.fecha_programada, D(2026, 11, 14))
        self.assertEqual(rec.ultimo_pago, D(2026, 11, 7))

    def test_pago_adelantado_salta_al_siguiente(self) -> None:
        datos = _datos(registros=[_reg(D(2026, 11, 28), D(2026, 11, 27)), _reg(D(2026, 11, 21))])
        rec = pd.calcular_recordatorio(_config(D(2026, 11, 19)), datos, D(2026, 11, 27))
        self.assertEqual(rec.proximo.fecha_programada, D(2026, 12, 7))
        self.assertEqual(rec.proximo.etiqueta, "1 de 4")
        self.assertEqual(rec.ultimo_pago, D(2026, 11, 27))

    def test_ultimo_pago_es_la_fecha_real_mas_reciente(self) -> None:
        datos = _datos(registros=[_reg(D(2026, 11, 7), D(2026, 11, 9)), _reg(D(2026, 11, 14), D(2026, 11, 14))])
        self.assertEqual(pd.ultimo_pago(datos), D(2026, 11, 14))

    def test_cruce_de_anio_en_el_recordatorio(self) -> None:
        rec = pd.calcular_recordatorio(_config(D(2026, 12, 1)), _datos(
            registros=[_reg(D(2026, 12, d)) for d in (7, 14, 21, 28)]), D(2026, 12, 30))
        self.assertEqual(rec.proximo.fecha_programada, D(2027, 1, 7))
        self.assertEqual(rec.dias_faltan, 8)
        self.assertIn("  1 de 4 · jue 07-ene · $2,500", pd.lineas_recordatorio(rec))

    def test_inicio_en_el_futuro(self) -> None:
        rec = pd.calcular_recordatorio(_config(D(2026, 12, 1)), _datos(), D(2026, 11, 19))
        self.assertEqual(rec.proximo.fecha_programada, D(2026, 12, 7))
        self.assertEqual(rec.atrasados, [])

    def test_dias_a_favor_y_monto_en_el_texto(self) -> None:
        datos = _datos({D(2026, 11, 3): TRABAJO, D(2026, 11, 10): TRABAJO},
                       decisiones={D(2026, 11, 10): PAGAR})
        rec = pd.calcular_recordatorio(_config(D(2026, 11, 1)), datos, D(2026, 11, 12))
        lineas = pd.lineas_recordatorio(rec)
        self.assertIn("  2 de 4 · sáb 14-nov · $2,885", lineas)
        self.assertEqual(lineas[-1], "  Días a favor: 1")

    def test_sin_config_vigente_no_hay_recordatorio(self) -> None:
        self.assertIsNone(pd.calcular_recordatorio(_config(activo=False), _datos(), D(2026, 11, 19)))
        self.assertIsNone(pd.calcular_recordatorio(_config(inicio=None), _datos(), D(2026, 11, 19)))

    def test_textos(self) -> None:
        self.assertEqual(pd.dinero_texto(Decimal("2115.5")), "$2,115.50")
        self.assertEqual(pd.dinero_texto(Decimal("10000")), "$10,000")
        self.assertEqual(pd.fecha_corta(D(2026, 11, 21), con_dia=True), "sáb 21-nov")
        self.assertEqual(pd.cuando_toca(3), "Toca en 3 días")


# ─── Con base (SQLite en memoria) ────────────────────────────────────────


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import EmpleadaHorario

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.addCleanup(engine.dispose)
        self.s = Session(engine)
        self.addCleanup(self.s.close)
        self.s.add(EmpleadaHorario(employee_code="VEND-1", descanso_weekday=1))
        self.s.commit()

    def _configurar(self, inicio=D(2026, 11, 19), **kw):
        return pd.guardar_config(self.s, fecha_inicio=inicio, **kw)

    def _marcar(self, fecha, tipo, nota=None):
        from pos_uniformes.database.models import EmpleadaEvento

        self.s.add(EmpleadaEvento(employee_code="VEND-1", fecha=fecha, tipo=tipo, nota=nota))
        self.s.commit()


class ConfigDbTests(_ConBase):
    def test_sin_config_no_hay_nada(self) -> None:
        self.assertIsNone(pd.cargar_config(self.s))
        self.assertIsNone(pd.recordatorio(self.s, D(2026, 11, 19)))
        self.assertEqual(pd.lineas_recordatorio_corte(self.s, D(2026, 11, 19)), [])
        self.assertEqual(pd.dias_extra_sin_decidir(self.s, D(2026, 11, 30)), [])
        self.assertFalse(pd.es_dia_extra(self.s, D(2026, 11, 24)))

    def test_config_inactiva_no_hay_recordatorio(self) -> None:
        self._configurar(activo=False)
        self.assertIsNotNone(pd.cargar_config(self.s))
        self.assertIsNone(pd.recordatorio(self.s, D(2026, 11, 19)))

    def test_guardar_y_cargar(self) -> None:
        self._configurar(monto_por_pago="2600", valor_dia=400, dias_de_pago=[28, 14])
        c = pd.cargar_config(self.s)
        self.assertEqual(c.monto_por_pago, Decimal("2600.00"))
        self.assertEqual(c.valor_dia, Decimal("400.00"))
        self.assertEqual(c.dias_de_pago, (14, 28))
        self.assertEqual(c.fecha_inicio, D(2026, 11, 19))
        self.assertTrue(c.vigente)
        self._configurar(inicio=D(2026, 11, 20))
        from pos_uniformes.database.models import PagoDuenoConfig

        self.assertEqual(self.s.query(PagoDuenoConfig).count(), 1)

    def test_config_invalida(self) -> None:
        with self.assertRaises(ValueError):
            self._configurar(dias_de_pago=[7, 31])
        with self.assertRaises(ValueError):
            pd.guardar_config(self.s, fecha_inicio=None)

    def test_sin_tablas_el_recordatorio_es_none(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with Session(engine) as s:
            self.assertIsNone(pd.recordatorio(s, D(2026, 11, 19)))


class PagosDbTests(_ConBase):
    def test_registrar_el_2_de_4_pagado_el_19_y_recordatorio(self) -> None:
        self._configurar()
        d = pd.registrar_pago(self.s, D(2026, 11, 14), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))
        self.assertEqual(d.monto, Decimal("2500.00"))
        self.assertEqual(d.etiqueta, "2 de 4")
        rec = pd.recordatorio(self.s, D(2026, 11, 19))
        self.assertEqual(rec.proximo.etiqueta, "3 de 4")
        self.assertEqual(rec.ultimo_pago, D(2026, 11, 19))
        self.assertEqual(pd.lineas_recordatorio_corte(self.s, D(2026, 11, 19))[2],
                         "  Toca en 2 días · Último pago: 19-nov")
        from pos_uniformes.database.models import PagoDuenoRegistro

        fila = self.s.query(PagoDuenoRegistro).one()
        self.assertEqual(fila.desglose["numero"], 2)
        self.assertEqual(fila.creado_por, "VEND-1")

    def test_monto_editado(self) -> None:
        self._configurar()
        d = pd.registrar_pago(self.s, D(2026, 11, 14), D(2026, 11, 19), "2000", "vend-1", hoy=D(2026, 11, 19))
        self.assertEqual(d.registro.monto, Decimal("2000.00"))

    def test_rechaza_duplicado_futuro_otra_persona_y_fecha_que_no_es_de_pago(self) -> None:
        self._configurar()
        pd.registrar_pago(self.s, D(2026, 11, 14), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))
        with self.assertRaises(ValueError):
            pd.registrar_pago(self.s, D(2026, 11, 14), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))
        with self.assertRaises(ValueError):
            pd.registrar_pago(self.s, D(2026, 11, 21), D(2026, 11, 20), None, "VEND-1", hoy=D(2026, 11, 19))
        with self.assertRaises(PermissionError):
            pd.registrar_pago(self.s, D(2026, 11, 21), D(2026, 11, 19), None, "VEND-4", hoy=D(2026, 11, 19))
        with self.assertRaises(ValueError):
            pd.registrar_pago(self.s, D(2026, 11, 20), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))

    def test_sin_config_no_registra(self) -> None:
        with self.assertRaises(ValueError):
            pd.registrar_pago(self.s, D(2026, 11, 14), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))

    def test_deshacer(self) -> None:
        self._configurar(inicio=D(2026, 11, 1))
        pd.registrar_pago(self.s, D(2026, 11, 14), D(2026, 11, 14), None, "VEND-1", hoy=D(2026, 11, 19))
        with self.assertRaises(PermissionError):
            pd.deshacer_pago(self.s, D(2026, 11, 14), "ENC-1")
        self.assertTrue(pd.deshacer_pago(self.s, D(2026, 11, 14), "VEND-1"))
        self.assertFalse(pd.deshacer_pago(self.s, D(2026, 11, 14), "VEND-1"))
        rec = pd.recordatorio(self.s, D(2026, 11, 19))
        self.assertEqual([a.fecha_programada for a in rec.atrasados], [D(2026, 11, 7), D(2026, 11, 14)])

    def test_pagos_del_mes_db(self) -> None:
        self._configurar()
        pd.registrar_pago(self.s, D(2026, 11, 21), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))
        pagos = pd.pagos_del_mes_db(self.s, 2026, 11)
        self.assertEqual([p.fecha_programada for p in pagos], [D(2026, 11, 21), D(2026, 11, 28)])
        self.assertTrue(pagos[0].pagado)
        self.assertFalse(pagos[1].pagado)


class DiasExtraDbTests(_ConBase):
    def test_marcar_trabajo_en_martes_y_decidir(self) -> None:
        self._configurar()
        from pos_uniformes.services.calendario_empleadas_service import marcar_dia

        marcar_dia(self.s, "VEND-1", D(2026, 11, 24), TRABAJO, actor="VEND-1")
        self.assertTrue(pd.es_dia_extra(self.s, D(2026, 11, 24)))
        self.assertEqual(pd.dias_extra_sin_decidir(self.s, D(2026, 11, 30)), [D(2026, 11, 24)])
        pd.decidir_dia_extra(self.s, D(2026, 11, 24), PAGAR)
        self.assertEqual(pd.dias_extra_sin_decidir(self.s, D(2026, 11, 30)), [])
        self.assertEqual(pd.recordatorio(self.s, D(2026, 11, 25)).proximo.monto, Decimal("2885.00"))
        pd.decidir_dia_extra(self.s, D(2026, 11, 24), ACUMULAR)
        rec = pd.recordatorio(self.s, D(2026, 11, 25))
        self.assertEqual(rec.proximo.monto, Decimal("2500.00"))
        self.assertEqual(rec.dias_a_favor, 1)

    def test_descanso_movido_con_marcar_dia_no_es_dia_extra(self) -> None:
        self._configurar()
        from pos_uniformes.services.calendario_empleadas_service import marcar_dia

        marcar_dia(self.s, "VEND-1", D(2026, 11, 26), DESCANSO, actor="VEND-1")   # jueves
        self.assertFalse(pd.es_dia_extra(self.s, D(2026, 11, 24)))                 # el martes quedó "trabajo"
        with self.assertRaises(ValueError):
            pd.decidir_dia_extra(self.s, D(2026, 11, 24), PAGAR)

    def test_sin_descanso_guardado_la_cuenta_y_el_calendario_coinciden(self) -> None:
        from pos_uniformes.database.models import EmpleadaHorario
        from pos_uniformes.services.calendario_empleadas_service import (
            cargar_horario, estado_del_dia, marcar_dia,
        )

        self.s.get(EmpleadaHorario, "VEND-1").descanso_weekday = None
        self.s.commit()
        self._configurar(inicio=D(2026, 11, 17))
        self.assertTrue(pd.falta_descanso(self.s))
        marcar_dia(self.s, "VEND-1", D(2026, 11, 24), TRABAJO, actor="VEND-1")
        self.assertEqual(estado_del_dia(cargar_horario(self.s, "VEND-1"), D(2026, 11, 24)), TRABAJO)
        self.assertFalse(pd.es_dia_extra(self.s, D(2026, 11, 24)))
        self.assertEqual(pd.lista_dias_extra(self.s, D(2026, 11, 30)), [])
        # Con el descanso guardado, el aviso se va y el martes trabajado sí es de más.
        self.s.get(EmpleadaHorario, "VEND-1").descanso_weekday = 1
        self.s.commit()
        self.assertFalse(pd.falta_descanso(self.s))
        self.assertTrue(pd.es_dia_extra(self.s, D(2026, 11, 24)))

    def test_falta_descanso_sin_cuenta_es_false(self) -> None:
        self.assertFalse(pd.falta_descanso(self.s))

    def test_destino_invalido(self) -> None:
        self._configurar()
        self._marcar(D(2026, 11, 24), TRABAJO)
        with self.assertRaises(ValueError):
            pd.decidir_dia_extra(self.s, D(2026, 11, 24), "regalar")

    def test_falta_cubierta_desde_la_base(self) -> None:
        self._configurar()
        self._marcar(D(2026, 11, 24), TRABAJO)
        self._marcar(D(2026, 11, 27), FALTA)
        p = pd.pagos_del_mes_db(self.s, 2026, 11)[-1]
        self.assertEqual(p.faltas_cubiertas, [D(2026, 11, 27)])
        self.assertEqual(p.monto, Decimal("2500.00"))

    def test_quitar_la_marca_no_deja_basura(self) -> None:
        """Se quita «Sí trabajó» y luego se vuelve a marcar desde otra pantalla:
        el «págamelo» viejo no revive (no mueve el monto sin que nadie lo decida)."""
        self._configurar()
        from pos_uniformes.services.calendario_empleadas_service import marcar_dia, quitar_marca

        marcar_dia(self.s, "VEND-1", D(2026, 11, 24), TRABAJO, actor="VEND-1")
        pd.decidir_dia_extra(self.s, D(2026, 11, 24), PAGAR)
        self.assertEqual(pd.decision_dia_extra(self.s, D(2026, 11, 24)), PAGAR)
        quitar_marca(self.s, "VEND-1", D(2026, 11, 24), actor="VEND-1")
        self.assertEqual(pd.limpiar_decisiones_huerfanas(self.s), 1)
        self.assertIsNone(pd.decision_dia_extra(self.s, D(2026, 11, 24)))
        self.assertEqual(pd.pagos_del_mes_db(self.s, 2026, 11)[-1].monto, Decimal("2500.00"))
        marcar_dia(self.s, "VEND-1", D(2026, 11, 24), TRABAJO, actor="ENC-1")
        p = pd.pagos_del_mes_db(self.s, 2026, 11)[-1]
        self.assertEqual(p.monto, Decimal("2500.00"))
        self.assertEqual(p.dias_extra_sin_decidir, [D(2026, 11, 24)])

    def test_limpiar_respeta_las_decisiones_vigentes(self) -> None:
        self._configurar()
        self._marcar(D(2026, 11, 24), TRABAJO)
        pd.decidir_dia_extra(self.s, D(2026, 11, 24), ACUMULAR)
        self.assertEqual(pd.limpiar_decisiones_huerfanas(self.s), 0)
        self.assertEqual(pd.decision_dia_extra(self.s, D(2026, 11, 24)), ACUMULAR)

    def test_descanso_movido_despues_borra_la_decision(self) -> None:
        self._configurar()
        from pos_uniformes.services.calendario_empleadas_service import marcar_dia

        marcar_dia(self.s, "VEND-1", D(2026, 11, 24), TRABAJO, actor="VEND-1")
        pd.decidir_dia_extra(self.s, D(2026, 11, 24), PAGAR)
        marcar_dia(self.s, "VEND-1", D(2026, 11, 26), DESCANSO, actor="VEND-1")   # descansó el jueves
        self.assertEqual(pd.limpiar_decisiones_huerfanas(self.s), 1)
        self.assertEqual(pd.pagos_del_mes_db(self.s, 2026, 11)[-1].monto, Decimal("2500.00"))

    def test_limpiar_sin_cuenta_no_toca_nada(self) -> None:
        self.assertEqual(pd.limpiar_decisiones_huerfanas(self.s), 0)

    def test_las_empleadas_no_cambian(self) -> None:
        self._configurar()
        from pos_uniformes.database.models import EmpleadaPago

        pd.registrar_pago(self.s, D(2026, 11, 14), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))
        self.assertEqual(self.s.query(EmpleadaPago).count(), 0)


# ─── Migración ───────────────────────────────────────────────────────────


_VERSIONES = Path(__file__).resolve().parents[1] / "migrations" / "versions"
REV = "a7d3e9f1c2b4"
TABLAS = {"pago_dueno_config", "pago_dueno_registro", "pago_dueno_dia_extra"}


def _migracion():
    ruta = next(_VERSIONES.glob(f"{REV}_*.py"))
    spec = importlib.util.spec_from_file_location("mig_pago_dueno", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MigracionTests(unittest.TestCase):
    def _correr(self, engine, accion: str) -> None:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        mod = _migracion()
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(mod, accion)()

    def test_sigue_a_la_cabeza_anterior(self) -> None:
        self.assertEqual(_migracion().down_revision, "d1e2f3a4b5c6")

    def test_upgrade_crea_y_downgrade_quita(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        self._correr(engine, "upgrade")
        self.assertTrue(TABLAS <= set(inspect(engine).get_table_names()))
        cols = {c["name"] for c in inspect(engine).get_columns("pago_dueno_config")}
        self.assertTrue({"monto_por_pago", "valor_dia", "dias_de_pago", "fecha_inicio", "activo"} <= cols)
        self._correr(engine, "downgrade")
        self.assertFalse(TABLAS & set(inspect(engine).get_table_names()))


if __name__ == "__main__":
    unittest.main()
