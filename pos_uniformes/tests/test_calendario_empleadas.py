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
        ciclo_dias_pago=7,  # semanal: cobran el mismo día cada semana
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
    """Regla de Daniel: pago cada 7 días de CALENDARIO — cobran siempre el
    mismo día de la semana; la falta NO mueve la fecha (se descuenta)."""

    def test_ciclo_semanal_mismo_dia_de_la_semana(self) -> None:
        # Último pago dom 6 → próximo dom 13, siempre domingo.
        h = _horario()
        self.assertEqual(fecha_proximo_pago(h, date(2026, 9, 7)), date(2026, 9, 13))
        self.assertEqual(fecha_proximo_pago(h, date(2026, 9, 7)).weekday(), 6)

    def test_falta_no_mueve_la_fecha_de_pago(self) -> None:
        h = _horario()
        h.eventos[date(2026, 9, 8)] = FALTA  # faltó el martes
        self.assertEqual(fecha_proximo_pago(h, date(2026, 9, 9)), date(2026, 9, 13))

    def test_descanso_extra_tampoco_mueve_la_fecha(self) -> None:
        h = _horario()
        h.eventos[date(2026, 9, 12)] = DESCANSO
        self.assertEqual(fecha_proximo_pago(h, date(2026, 9, 7)), date(2026, 9, 13))

    def test_sin_ultimo_pago_no_hay_fecha(self) -> None:
        h = _horario(fecha_ultimo_pago=None)
        self.assertIsNone(fecha_proximo_pago(h, date(2026, 9, 7)))
        self.assertIsNone(dias_para_pago(h, date(2026, 9, 7)))

    def test_dias_trabajados_para_control_del_dueno(self) -> None:
        # La falta sí cuenta para el CONTROL (cuántos días trabajó de
        # verdad), aunque no mueva la fecha del pago.
        h = _horario()
        h.eventos[date(2026, 9, 8)] = FALTA
        # Al miércoles 9: trabajó lun 7 y mié 9 (el martes faltó) = 2.
        self.assertEqual(dias_trabajados_desde_ultimo_pago(h, date(2026, 9, 9)), 2)
        # Días de calendario al pago: del mié 9 al dom 13 = 4.
        self.assertEqual(dias_para_pago(h, date(2026, 9, 9)), 4)

    def test_faltan_cero_cuando_ya_toca_o_esta_vencido(self) -> None:
        h = _horario()
        self.assertEqual(dias_para_pago(h, date(2026, 9, 13)), 0)
        self.assertEqual(dias_para_pago(h, date(2026, 9, 20)), 0)  # atrasado


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
        # Su jueves fijo más cercano es el 10 — con fecha concreta.
        self.assertIn("Tu siguiente descanso: jueves 10/Sep", texto)
        self.assertIn("Próximo pago", texto)
        self.assertIn("faltan 4 días", texto)  # del mié 9 al dom 13

    def test_resumen_respeta_descanso_movido(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import proximo_descanso

        h = _horario()
        # Movió su jueves 10 al sábado 12 (intercambio o solicitud).
        h.eventos[date(2026, 9, 10)] = TRABAJO
        h.eventos[date(2026, 9, 12)] = DESCANSO
        self.assertEqual(proximo_descanso(h, date(2026, 9, 9)), date(2026, 9, 12))
        self.assertIn("sábado 12/Sep", resumen_empleada(h, date(2026, 9, 9)))

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
        self.assertEqual(h.ciclo_dias_pago, 7)
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
            self.session, "VEND-2", descanso_weekday=_JUEVES, ciclo_dias_pago=7
        )
        registrar_pago(self.session, "VEND-2", date(2026, 9, 6))
        marcar_dia(self.session, "VEND-2", date(2026, 9, 8), FALTA)

        chips = chips_calendario_mes(self.session, 2026, 9, date(2026, 9, 7))

        # Descanso fijo (jueves 10) con el primer nombre de la empleada.
        self.assertIn(("descanso", "Ana"), chips[date(2026, 9, 10)])
        # Pago hecho (dom 6) y el próximo proyectado el MISMO día de la
        # semana (dom 13) — la falta del martes no lo mueve.
        self.assertIn(("pago", "Ana"), chips[date(2026, 9, 6)])
        self.assertIn(("pago", "Ana"), chips[date(2026, 9, 13)])
        # La falta del 8 NO aparece en el calendario compartido.
        self.assertNotIn(date(2026, 9, 8), chips)


class AutoservicioDescansosTests(unittest.TestCase):
    """Las reglas negocian por Daniel: cupo 1/día, 7 días de anticipación,
    intercambios directos entre compañeras."""

    def _horarios(self) -> dict:
        ana = _horario(employee_code="VEND-2", descanso_weekday=_JUEVES)
        bere = _horario(employee_code="VEND-3", descanso_weekday=_LUNES)
        return {"VEND-2": ana, "VEND-3": bere}

    def test_sin_anticipacion_se_rechaza(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import (
            validar_solicitud_descanso,
        )

        ok, motivo = validar_solicitud_descanso(
            self._horarios(), "VEND-2", date(2026, 9, 8), hoy=date(2026, 9, 4)
        )
        self.assertFalse(ok)
        self.assertIn("7 días", motivo)

    def test_cupo_ocupado_se_rechaza_y_sugiere(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import (
            dias_libres_cercanos,
            validar_solicitud_descanso,
        )

        horarios = self._horarios()
        # Pide el lunes 14... pero los lunes descansa VEND-3.
        ok, motivo = validar_solicitud_descanso(
            horarios, "VEND-2", date(2026, 9, 14), hoy=date(2026, 9, 4)
        )
        self.assertFalse(ok)
        self.assertIn("VEND-3", motivo)
        # Y hay sugerencias que sí cumplen todas las reglas.
        libres = dias_libres_cercanos(horarios, "VEND-2", date(2026, 9, 4))
        self.assertTrue(libres)
        for f in libres:
            self.assertTrue(
                validar_solicitud_descanso(horarios, "VEND-2", f, date(2026, 9, 4))[0]
            )

    def test_pedir_mueve_el_descanso_de_su_semana(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import EmpleadaEvento, EmpleadaHorario
        from pos_uniformes.services.calendario_empleadas_service import (
            aplicar_solicitud_descanso,
            cargar_horario,
        )

        engine = create_engine("sqlite://")
        for t in (EmpleadaHorario, EmpleadaEvento):
            t.__table__.create(engine)
        session = sessionmaker(bind=engine)()

        horarios = self._horarios()
        # Pide el martes 15 (semana lun 14 - dom 20; su jueves fijo es el 17).
        ok, msg = aplicar_solicitud_descanso(
            session, horarios, "VEND-2", date(2026, 9, 15), hoy=date(2026, 9, 4)
        )
        self.assertTrue(ok, msg)
        h = cargar_horario(session, "VEND-2")
        self.assertEqual(h.eventos[date(2026, 9, 15)], DESCANSO)
        self.assertEqual(h.eventos[date(2026, 9, 17)], TRABAJO)  # su jueves se movió
        session.close()

    def test_intercambio_valida_y_aplica(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import EmpleadaEvento, EmpleadaHorario
        from pos_uniformes.services.calendario_empleadas_service import (
            aplicar_intercambio,
            cargar_horario,
            validar_intercambio,
        )

        engine = create_engine("sqlite://")
        for t in (EmpleadaHorario, EmpleadaEvento):
            t.__table__.create(engine)
        session = sessionmaker(bind=engine)()

        horarios = self._horarios()
        hoy = date(2026, 9, 4)
        jueves_ana = date(2026, 9, 17)
        lunes_bere = date(2026, 9, 14)

        # Un día que no es descanso de Ana: rechazado.
        ok, motivo = validar_intercambio(
            horarios, "VEND-2", date(2026, 9, 16), "VEND-3", lunes_bere, hoy
        )
        self.assertFalse(ok)

        # Jueves de Ana por lunes de Bere: hecho, sin Daniel.
        ok, msg = aplicar_intercambio(
            session, horarios, "VEND-2", jueves_ana, "VEND-3", lunes_bere, hoy
        )
        self.assertTrue(ok, msg)
        ana = cargar_horario(session, "VEND-2")
        bere = cargar_horario(session, "VEND-3")
        self.assertEqual(ana.eventos[jueves_ana], TRABAJO)
        self.assertEqual(ana.eventos[lunes_bere], DESCANSO)
        self.assertEqual(bere.eventos[lunes_bere], TRABAJO)
        self.assertEqual(bere.eventos[jueves_ana], DESCANSO)
        session.close()

    def test_intercambio_sin_anticipacion_se_rechaza(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import (
            validar_intercambio,
        )

        ok, motivo = validar_intercambio(
            self._horarios(),
            "VEND-2",
            date(2026, 9, 10),  # su jueves, pero a 3 días
            "VEND-3",
            date(2026, 9, 14),
            hoy=date(2026, 9, 7),
        )
        self.assertFalse(ok)
        self.assertIn("7 días", motivo)


class LimiteMensualTests(unittest.TestCase):
    """2 movimientos al mes por empleada (pedidos + intercambios juntos)."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import EmpleadaEvento, EmpleadaHorario

        engine = create_engine("sqlite://")
        for t in (EmpleadaHorario, EmpleadaEvento):
            t.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()

    def tearDown(self) -> None:
        self.session.close()

    def test_tercer_movimiento_del_mes_se_rechaza(self) -> None:
        from datetime import timedelta

        from pos_uniformes.services.calendario_empleadas_service import (
            aplicar_solicitud_descanso,
            cambios_del_mes,
        )

        hoy = date.today()
        horarios = {"VEND-2": HorarioEmpleada(employee_code="VEND-2")}
        f1 = hoy + timedelta(days=8)
        f2 = hoy + timedelta(days=15)
        f3 = hoy + timedelta(days=22)

        ok1, _ = aplicar_solicitud_descanso(self.session, horarios, "VEND-2", f1, hoy)
        ok2, _ = aplicar_solicitud_descanso(self.session, horarios, "VEND-2", f2, hoy)
        self.assertTrue(ok1 and ok2)
        self.assertEqual(cambios_del_mes(self.session, "VEND-2", hoy), 2)

        ok3, motivo = aplicar_solicitud_descanso(self.session, horarios, "VEND-2", f3, hoy)
        self.assertFalse(ok3)
        self.assertIn("2 cambios", motivo)

    def test_intercambio_tambien_gasta_cuota(self) -> None:
        from datetime import timedelta

        from pos_uniformes.services.calendario_empleadas_service import (
            aplicar_intercambio,
            cambios_del_mes,
        )

        hoy = date.today()
        f_a = hoy + timedelta(days=10)
        f_b = hoy + timedelta(days=11)
        horarios = {
            "VEND-2": HorarioEmpleada(employee_code="VEND-2", eventos={f_a: DESCANSO}),
            "VEND-3": HorarioEmpleada(employee_code="VEND-3", eventos={f_b: DESCANSO}),
        }
        ok, msg = aplicar_intercambio(
            self.session, horarios, "VEND-2", f_a, "VEND-3", f_b, hoy
        )
        self.assertTrue(ok, msg)
        # A cada una le cuenta 1 de sus 2 del mes.
        self.assertEqual(cambios_del_mes(self.session, "VEND-2", hoy), 1)
        self.assertEqual(cambios_del_mes(self.session, "VEND-3", hoy), 1)

    def test_marcas_del_dueno_no_gastan_cuota(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import (
            cambios_del_mes,
            marcar_dia,
        )

        hoy = date.today()
        marcar_dia(self.session, "VEND-2", hoy, DESCANSO)  # sin nota de autoservicio
        marcar_dia(self.session, "VEND-2", hoy, FALTA)
        self.assertEqual(cambios_del_mes(self.session, "VEND-2", hoy), 0)


if __name__ == "__main__":
    unittest.main()
