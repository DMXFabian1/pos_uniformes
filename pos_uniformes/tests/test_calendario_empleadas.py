"""Tests del calendario de empleadas: descansos fijos, faltas que recorren
el pago (regla: pago cada N días TRABAJADOS) y el pintado del mes.

Lógica pura — sin base de datos ni Qt.
"""

from __future__ import annotations

import unittest
from datetime import date

from pos_uniformes.services.calendario_empleadas_service import (
    DESCANSO,
    FALTA,
    PAGO,
    TRABAJO,
    HorarioEmpleada,
    dias_para_pago,
    dias_trabajados_desde_ultimo_pago,
    estado_del_dia,
    faltas_en_rango,
    fecha_proximo_pago,
    pintar_mes,
    resumen_empleada,
)

# Septiembre 2026: el día 1 es martes; los jueves caen 3, 10, 17, 24.
_LUNES = 0
_JUEVES = 3


def _horario(**kwargs) -> HorarioEmpleada:
    base = dict(
        employee_code="VEND-2",
        descanso_weekday=_JUEVES,
        ciclo_dias_pago=6,
        fecha_ultimo_pago=date(2026, 9, 6),  # domingo
    )
    base.update(kwargs)
    return HorarioEmpleada(**base)


class EstadoDelDiaTests(unittest.TestCase):
    def test_descanso_fijo_semanal(self) -> None:
        h = _horario()
        self.assertEqual(estado_del_dia(h, date(2026, 9, 10)), DESCANSO)  # jueves
        self.assertEqual(estado_del_dia(h, date(2026, 9, 11)), TRABAJO)  # viernes

    def test_evento_le_gana_al_patron(self) -> None:
        h = _horario()
        h.eventos[date(2026, 9, 10)] = TRABAJO  # trabajó en su jueves
        h.eventos[date(2026, 9, 11)] = FALTA
        h.eventos[date(2026, 9, 12)] = DESCANSO  # descanso movido
        self.assertEqual(estado_del_dia(h, date(2026, 9, 10)), TRABAJO)
        self.assertEqual(estado_del_dia(h, date(2026, 9, 11)), FALTA)
        self.assertEqual(estado_del_dia(h, date(2026, 9, 12)), DESCANSO)

    def test_sin_descanso_configurado_todo_es_trabajo(self) -> None:
        h = _horario(descanso_weekday=None)
        self.assertEqual(estado_del_dia(h, date(2026, 9, 10)), TRABAJO)


class ProximoPagoTests(unittest.TestCase):
    def test_ciclo_normal_brinca_el_descanso(self) -> None:
        # Último pago dom 6; trabaja lun 7, mar 8, mié 9, (jue 10 descansa),
        # vie 11, sáb 12, dom 13 → el 6º día trabajado es el domingo 13.
        h = _horario()
        self.assertEqual(fecha_proximo_pago(h, date(2026, 9, 7)), date(2026, 9, 13))

    def test_falta_recorre_el_pago_un_dia(self) -> None:
        # La regla que pidió Daniel: la falta no cuenta como trabajado,
        # así que el pago se recorre solo — del dom 13 al lun 14.
        h = _horario()
        h.eventos[date(2026, 9, 8)] = FALTA  # faltó el martes
        self.assertEqual(fecha_proximo_pago(h, date(2026, 9, 9)), date(2026, 9, 14))

    def test_descanso_extra_tambien_recorre(self) -> None:
        h = _horario()
        h.eventos[date(2026, 9, 12)] = DESCANSO  # descanso extra el sábado
        self.assertEqual(fecha_proximo_pago(h, date(2026, 9, 7)), date(2026, 9, 14))

    def test_trabajar_su_descanso_adelanta_el_pago(self) -> None:
        h = _horario()
        h.eventos[date(2026, 9, 10)] = TRABAJO  # trabajó su jueves
        self.assertEqual(fecha_proximo_pago(h, date(2026, 9, 7)), date(2026, 9, 12))

    def test_sin_ultimo_pago_no_hay_fecha(self) -> None:
        h = _horario(fecha_ultimo_pago=None)
        self.assertIsNone(fecha_proximo_pago(h, date(2026, 9, 7)))
        self.assertIsNone(dias_para_pago(h, date(2026, 9, 7)))

    def test_dias_trabajados_y_faltantes(self) -> None:
        h = _horario()
        h.eventos[date(2026, 9, 8)] = FALTA
        # Al miércoles 9: trabajó lun 7 y mié 9 (el martes faltó) = 2.
        self.assertEqual(dias_trabajados_desde_ultimo_pago(h, date(2026, 9, 9)), 2)
        self.assertEqual(dias_para_pago(h, date(2026, 9, 9)), 4)

    def test_faltan_cero_cuando_ya_toca(self) -> None:
        h = _horario()
        self.assertEqual(dias_para_pago(h, date(2026, 9, 13)), 0)


class PintarMesTests(unittest.TestCase):
    def test_mes_completo_con_estados(self) -> None:
        h = _horario()
        h.eventos[date(2026, 9, 8)] = FALTA
        h.eventos[date(2026, 9, 6)] = PAGO
        mes = pintar_mes(h, 2026, 9)
        self.assertEqual(len(mes), 30)
        self.assertEqual(mes[date(2026, 9, 3)], DESCANSO)  # jueves fijo
        self.assertEqual(mes[date(2026, 9, 8)], FALTA)
        self.assertEqual(mes[date(2026, 9, 6)], PAGO)
        self.assertEqual(mes[date(2026, 9, 7)], TRABAJO)

    def test_faltas_en_rango(self) -> None:
        h = _horario()
        h.eventos[date(2026, 9, 8)] = FALTA
        h.eventos[date(2026, 9, 20)] = FALTA
        h.eventos[date(2026, 10, 2)] = FALTA
        self.assertEqual(
            faltas_en_rango(h, date(2026, 9, 1), date(2026, 9, 30)), 2
        )


class ResumenTests(unittest.TestCase):
    def test_resumen_con_todo(self) -> None:
        h = _horario()
        texto = resumen_empleada(h, date(2026, 9, 9))
        self.assertIn("jueves", texto)
        self.assertIn("Próximo pago", texto)
        self.assertIn("faltan 3 días", texto)  # trabajó 3 de 6 al mié 9

    def test_resumen_hoy_toca_pago(self) -> None:
        h = _horario()
        self.assertIn("¡hoy!", resumen_empleada(h, date(2026, 9, 13)))

    def test_resumen_sin_configurar(self) -> None:
        h = _horario(descanso_weekday=None, fecha_ultimo_pago=None)
        self.assertIn("Sin horario", resumen_empleada(h, date(2026, 9, 9)))


class AccesoDatosTests(unittest.TestCase):
    """Round-trip real de horario/eventos/pagos contra SQLite en memoria."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import (
            EmpleadaEvento,
            EmpleadaHorario,
            LibretaVenta,
        )

        engine = create_engine("sqlite://")
        for tabla in (EmpleadaHorario, EmpleadaEvento, LibretaVenta):
            tabla.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()

    def tearDown(self) -> None:
        self.session.close()

    def test_horario_nuevo_tiene_defaults(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import cargar_horario

        h = cargar_horario(self.session, "vend-2")
        self.assertEqual(h.employee_code, "VEND-2")
        self.assertIsNone(h.descanso_weekday)
        self.assertEqual(h.ciclo_dias_pago, 6)
        self.assertEqual(h.eventos, {})

    def test_guardar_marcar_y_pagar(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import (
            cargar_horario,
            guardar_horario,
            marcar_dia,
            quitar_marca,
            registrar_pago,
        )

        guardar_horario(
            self.session, "VEND-2", descanso_weekday=_JUEVES, ciclo_dias_pago=6
        )
        marcar_dia(self.session, "VEND-2", date(2026, 9, 8), FALTA)
        # Re-marcar el mismo día reemplaza la marca (no duplica).
        marcar_dia(self.session, "VEND-2", date(2026, 9, 8), DESCANSO)
        registrar_pago(self.session, "VEND-2", date(2026, 9, 13))

        h = cargar_horario(self.session, "VEND-2")
        self.assertEqual(h.descanso_weekday, _JUEVES)
        self.assertEqual(h.fecha_ultimo_pago, date(2026, 9, 13))
        self.assertEqual(h.eventos[date(2026, 9, 8)], DESCANSO)
        self.assertEqual(h.eventos[date(2026, 9, 13)], PAGO)

        # Quitar marca borra la excepción pero respeta el historial de pagos.
        quitar_marca(self.session, "VEND-2", date(2026, 9, 8))
        quitar_marca(self.session, "VEND-2", date(2026, 9, 13))
        h = cargar_horario(self.session, "VEND-2")
        self.assertNotIn(date(2026, 9, 8), h.eventos)
        self.assertEqual(h.eventos[date(2026, 9, 13)], PAGO)

    def test_comisiones_desde_ultimo_pago(self) -> None:
        from datetime import datetime, timedelta, timezone

        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.calendario_empleadas_service import (
            comisiones_desde_ultimo_pago,
        )

        def _venta(dias_atras: int, comisiones: int) -> LibretaVenta:
            momento = datetime.now(timezone.utc) - timedelta(days=dias_atras)
            return LibretaVenta(
                employee_code="VEND-2",
                employee_name="Ana",
                tipo="venta",
                piezas=comisiones,
                comisiones=comisiones,
                detalle=[],
                created_at=momento,
            )

        self.session.add_all([_venta(10, 5), _venta(2, 3), _venta(0, 4)])
        self.session.commit()

        # Pagada hace 5 días: solo cuentan las ventas de después (3 + 4).
        h = _horario(fecha_ultimo_pago=date.today() - timedelta(days=5))
        self.assertEqual(comisiones_desde_ultimo_pago(self.session, "VEND-2", h), 7)

        # Sin pago registrado: cuenta todo (5 + 3 + 4).
        h_sin = _horario(fecha_ultimo_pago=None)
        self.assertEqual(
            comisiones_desde_ultimo_pago(self.session, "VEND-2", h_sin), 12
        )


class ChipsCalendarioCompartidoTests(unittest.TestCase):
    """Sincronía con la página Calendario del kiosko: descansos y pagos de
    empleadas salen como chips; las faltas NO (privadas de la Libreta)."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import (
            Empleada,
            EmpleadaEvento,
            EmpleadaHorario,
        )

        engine = create_engine("sqlite://")
        for tabla in (Empleada, EmpleadaHorario, EmpleadaEvento):
            tabla.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        self.session.add(
            Empleada(codigo="VEND-2", nombre_completo="Ana López", activo=True)
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()

    def test_descansos_y_pagos_si_faltas_no(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import (
            chips_calendario_mes,
            guardar_horario,
            marcar_dia,
            registrar_pago,
        )

        guardar_horario(
            self.session, "VEND-2", descanso_weekday=_JUEVES, ciclo_dias_pago=6
        )
        registrar_pago(self.session, "VEND-2", date(2026, 9, 6))
        marcar_dia(self.session, "VEND-2", date(2026, 9, 8), FALTA)

        chips = chips_calendario_mes(self.session, 2026, 9, date(2026, 9, 7))

        # Descanso fijo (jueves 10) con el primer nombre de la empleada.
        self.assertIn(("descanso", "Ana"), chips[date(2026, 9, 10)])
        # Pago hecho (dom 6) y próximo pago proyectado: la falta del martes
        # lo recorre del dom 13 al lun 14 — también sincronizado.
        self.assertIn(("pago", "Ana"), chips[date(2026, 9, 6)])
        self.assertIn(("pago", "Ana"), chips[date(2026, 9, 14)])
        self.assertNotIn(date(2026, 9, 13), chips)
        # La falta del 8 NO aparece en el calendario compartido.
        self.assertNotIn(date(2026, 9, 8), chips)


if __name__ == "__main__":
    unittest.main()
