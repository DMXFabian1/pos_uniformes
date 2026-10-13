"""Informe de discrepancias de descansos — SOLO LECTURA.

Corre antes y después de la migración d9e0f1a2b3c4 y no corrige nada: dice qué
hay que revisar para que Daniel decida. La transacción se abre READ ONLY.

    python -m pos_uniformes.scripts.reporte_discrepancias_descansos [--semanas 8]

Revisa:
1. Semanas con un número de descansos distinto de uno (empleadas de descanso
   fijo, activas): el doble descanso de Cristal sale aquí.
2. Días con dos marcas incompatibles (p. ej. descanso y pago el mismo día).
3. Eventos del autoservicio viejo (aprobados solos, sin solicitud).
4. Solicitudes aprobadas sin eventos y eventos ligados a solicitudes no
   aprobadas (solo si la migración ya corrió).
5. Solicitudes pendientes cuyo día ya pasó (las cerrará la tarea del bot).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta


def _hay_columna(s, tabla: str, columna: str) -> bool:
    from sqlalchemy import text

    return bool(s.execute(text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"
    ), {"t": tabla, "c": columna}).first())


def reporte(session, *, hoy: date, semanas: int = 8) -> list[str]:
    from sqlalchemy import text

    from pos_uniformes.services.calendario_empleadas_service import (
        HorarioEmpleada, es_descanso_efectivo,
    )
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR

    salida: list[str] = []
    empleadas = {
        c: n for c, n in session.execute(text(
            "SELECT codigo, split_part(nombre_completo, ' ', 1) FROM empleada WHERE activo"
        )).all() if c.upper() not in QUIEN_PUEDE_PAGAR
    }
    horarios = {
        c: HorarioEmpleada(employee_code=c, descanso_weekday=w, modo_pago=m or "semana",
                           dias_trabajo=list(d or []))
        for c, w, m, d in session.execute(text(
            "SELECT employee_code, descanso_weekday, modo_pago, dias_trabajo FROM empleada_horario"
        )).all()
    }
    por_dia: dict[tuple[str, date], list[tuple[str, str | None]]] = defaultdict(list)
    for c, f, t, nota in session.execute(text(
        "SELECT employee_code, fecha, tipo, nota FROM empleada_evento"
    )).all():
        por_dia[(c, f)].append((t, nota))
        h = horarios.get(c)
        if h is None:
            continue
        if t == "pago":
            h.pagos.add(f)
            h.eventos.setdefault(f, t)
        else:
            h.eventos[f] = t

    salida.append(f"== 1. Semanas con ≠1 descanso (±{semanas} semanas desde {hoy}) ==")
    salida.append("   (un pago registrado en su día fijo cuenta como descanso: si ese día vino "
                  "a trabajar, la semana sale con uno de más y hay que verla a mano)")
    lunes0 = hoy - timedelta(days=hoy.weekday())
    hallados = 0
    for c, nombre in sorted(empleadas.items()):
        h = horarios.get(c)
        if h is None or h.por_dia or h.descanso_weekday is None:
            continue
        for k in range(-semanas, semanas + 1):
            lunes = lunes0 + timedelta(weeks=k)
            dias = [lunes + timedelta(days=i) for i in range(7)]
            libres = [d for d in dias if es_descanso_efectivo(h, d)]
            if len(libres) != 1:
                hallados += 1
                notas = "; ".join(
                    f"{d:%d/%m} {t} ({n or 'sin nota'})"
                    for d in dias for (t, n) in por_dia.get((c, d), [])
                )
                salida.append(
                    f"- {nombre} ({c}) semana del {lunes:%d/%m}: {len(libres)} descansos "
                    f"[{', '.join(f'{d:%a %d/%m}' for d in libres) or '—'}] · marcas: {notas or '—'}"
                )
    if not hallados:
        salida.append("(ninguna)")

    salida.append("== 2. Días con varias marcas ==")
    varios = [(k, v) for k, v in sorted(por_dia.items()) if len(v) > 1]
    salida += [f"- {c} {f:%d/%m/%Y}: {', '.join(t for t, _n in v)}" for (c, f), v in varios] or ["(ninguno)"]

    salida.append("== 3. Eventos del autoservicio viejo (sin aprobación de Daniel) ==")
    viejos = [
        (c, f, t, n) for (c, f), v in sorted(por_dia.items()) for (t, n) in v
        if n and (n == "pedido desde la Libreta" or n.startswith("intercambio con ")
                  or n == "movió su descanso")
    ]
    salida += [f"- {c} {f:%d/%m/%Y} {t} ({n})" for c, f, t, n in viejos] or ["(ninguno)"]

    if _hay_columna(session, "empleada_evento", "solicitud_id"):
        salida.append("== 4. Solicitudes y eventos desligados ==")
        sin_evento = session.execute(text(
            "SELECT s.id, s.employee_code, s.fecha FROM solicitud_descanso s "
            "WHERE s.estado = 'aprobado' AND NOT EXISTS "
            "(SELECT 1 FROM empleada_evento e WHERE e.solicitud_id = s.id)"
        )).all()
        huerfanos = session.execute(text(
            "SELECT e.id, e.employee_code, e.fecha, s.estado FROM empleada_evento e "
            "JOIN solicitud_descanso s ON s.id = e.solicitud_id WHERE s.estado <> 'aprobado'"
        )).all()
        salida += [f"- aprobada sin evento: #{i} {c} {f}" for i, c, f in sin_evento]
        salida += [f"- evento #{i} {c} {f} de solicitud {e}" for i, c, f, e in huerfanos]
        if not (sin_evento or huerfanos):
            salida.append("(nada)")
    else:
        salida.append("== 4. (migración d9e0f1a2b3c4 sin correr: no hay ligas que revisar) ==")

    salida.append("== 5. Pendientes cuyo día ya pasó ==")
    viejas = session.execute(text(
        "SELECT id, employee_code, fecha FROM solicitud_descanso WHERE estado = 'pedido' AND fecha < :h"
    ), {"h": hoy}).all()
    salida += [f"- #{i} {c} {f}" for i, c, f in viejas] or ["(ninguna)"]
    return salida


def main() -> None:
    from sqlalchemy import text

    from pos_uniformes.database.connection import get_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--semanas", type=int, default=8)
    args = parser.parse_args()
    with get_session() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        for linea in reporte(s, hoy=date.today(), semanas=args.semanas):
            print(linea)
        s.rollback()


if __name__ == "__main__":
    main()
