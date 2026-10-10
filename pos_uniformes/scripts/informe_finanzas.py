"""Informe general de las finanzas de la tienda, en texto plano.

Corre en la PC principal (la unica que alcanza la base) y deja el
informe en `reportes\\finanzas.txt` para mandarlo por git. Es de SOLO
LECTURA: no escribe nada en la base.

Regla que ordena el informe: aqui solo hay DINERO REAL. Lo que entro al
cajon, lo que entro por terminal, los abonos. Nunca "vendido en total"
ni el valor de los apartados, que es dinero que todavia no existe.

Uso (en la PC principal):
    python -m pos_uniformes.scripts.informe_finanzas [dias]
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

DIAS_POR_OMISION = 90
_CERO = Decimal("0.00")


def _pesos(monto: Decimal | None) -> str:
    return f"${(monto or _CERO):,.2f}"


def _titulo(texto: str) -> list[str]:
    return ["", texto.upper(), "=" * len(texto)]


def _sub(texto: str) -> list[str]:
    return ["", texto, "-" * len(texto)]


def _entradas(session, desde: datetime) -> list[str]:
    """Lo que entro, separado por donde cayo el dinero."""
    from sqlalchemy import func, literal_column, select

    from pos_uniformes.database import models as m

    lv = m.LibretaVenta
    lineas = _titulo("lo que entro")

    fila = session.execute(
        select(
            func.coalesce(func.sum(lv.monto_total), 0),
            func.coalesce(func.sum(lv.monto_neto), 0),
            func.count(),
            func.coalesce(func.sum(lv.piezas), 0),
        ).where(lv.created_at >= desde)
    ).one()
    total, neto, operaciones, piezas = fila
    lineas.append(f"Operaciones cobradas : {operaciones:,} ({piezas:,} piezas)")
    lineas.append(f"Cobrado              : {_pesos(total)}")
    lineas.append(f"Recibido de verdad   : {_pesos(neto)}")
    if total and total != neto:
        lineas.append(f"Se quedo la terminal : {_pesos(total - neto)}")

    lineas += _sub("por donde entro")
    for etiqueta, condicion in (
        ("Efectivo", lv.pago_tarjeta.is_(False)),
        ("Tarjeta", lv.pago_tarjeta.is_(True)),
    ):
        t, n, c = session.execute(
            select(
                func.coalesce(func.sum(lv.monto_total), 0),
                func.coalesce(func.sum(lv.monto_neto), 0),
                func.count(),
            ).where(lv.created_at >= desde, condicion)
        ).one()
        parte = f" ({t / total * 100:.0f}%)" if total else ""
        lineas.append(f"{etiqueta:<9} {_pesos(t):>14}{parte:<7} neto {_pesos(n):>14}  {c:,} ops")

    lineas += _sub("por tipo de operacion")
    for tipo, t, n, c in session.execute(
        select(
            lv.tipo,
            func.coalesce(func.sum(lv.monto_total), 0),
            func.coalesce(func.sum(lv.monto_neto), 0),
            func.count(),
        )
        .where(lv.created_at >= desde)
        .group_by(lv.tipo)
        .order_by(func.sum(lv.monto_total).desc())
    ):
        lineas.append(f"{(tipo or '?'):<9} {_pesos(t):>14}        neto {_pesos(n):>14}  {c:,} ops")

    lineas += _sub("mes por mes")
    # Una sola expresion reusada en select/group_by/order_by. Construirla
    # tres veces manda tres parametros distintos y Postgres ya no reconoce
    # que la columna del SELECT es la del GROUP BY ("must appear in the
    # GROUP BY clause"). El literal lo deja explicito en el SQL.
    mes_col = func.date_trunc(literal_column("'month'"), lv.created_at)
    for mes, t, n, c, p in session.execute(
        select(
            mes_col,
            func.coalesce(func.sum(lv.monto_total), 0),
            func.coalesce(func.sum(lv.monto_neto), 0),
            func.count(),
            func.coalesce(func.sum(lv.piezas), 0),
        )
        .where(lv.created_at >= desde)
        .group_by(mes_col)
        .order_by(mes_col)
    ):
        lineas.append(
            f"{mes:%Y-%m}  cobrado {_pesos(t):>14}  neto {_pesos(n):>14}  {c:>5,} ops  {p:>6,} pz"
        )

    lineas += _sub("quien cobro")
    for codigo, nombre, t, c, com in session.execute(
        select(
            lv.employee_code,
            func.max(lv.employee_name),
            func.coalesce(func.sum(lv.monto_total), 0),
            func.count(),
            func.coalesce(func.sum(lv.comisiones), 0),
        )
        .where(lv.created_at >= desde)
        .group_by(lv.employee_code)
        .order_by(func.sum(lv.monto_total).desc())
    ):
        parte = f"{t / total * 100:5.1f}%" if total else "    - "
        lineas.append(
            f"{(nombre or codigo)[:22]:<22} {codigo:<8} {_pesos(t):>14} {parte}  {c:>4,} ops  {com:>4,} com"
        )
    return lineas


def _salidas(session, desde: datetime) -> tuple[list[str], Decimal, Decimal]:
    """Lo unico que el sistema sabe que SALIO: nomina y retiros."""
    from sqlalchemy import func, select

    from pos_uniformes.database import models as m

    lineas = _titulo("lo que salio")

    pago = m.EmpleadaPago
    total_nomina = _CERO
    lineas += _sub("nomina pagada")
    filas = list(
        session.execute(
            select(
                pago.employee_code,
                func.max(pago.employee_name),
                func.count(),
                func.coalesce(func.sum(pago.sueldo_base), 0),
                func.coalesce(func.sum(pago.monto_comisiones), 0),
                func.coalesce(func.sum(pago.descuento_faltas), 0),
                func.coalesce(func.sum(pago.descuento_prestamos), 0),
                func.coalesce(func.sum(pago.total), 0),
            )
            .where(pago.created_at >= desde)
            .group_by(pago.employee_code)
            .order_by(func.sum(pago.total).desc())
        )
    )
    if not filas:
        lineas.append("(sin pagos registrados en el periodo)")
    for codigo, nombre, cuantos, base, comis, faltas, prestamos, total in filas:
        total_nomina += total
        lineas.append(
            f"{(nombre or codigo)[:22]:<22} {cuantos:>2} pagos  base {_pesos(base):>12}"
            f"  comis {_pesos(comis):>10}  faltas -{_pesos(faltas):>10}"
            f"  prest -{_pesos(prestamos):>10}  = {_pesos(total):>12}"
        )
    lineas.append(f"{'TOTAL NOMINA':<22} {_pesos(total_nomina):>58}")

    retiro = m.CajaRetiro
    total_retiros = _CERO
    lineas += _sub("retiros del cajon (gastos descontados)")
    filas = list(
        session.execute(
            select(
                retiro.motivo,
                func.count(),
                func.coalesce(func.sum(retiro.monto), 0),
            )
            .where(retiro.created_at >= desde)
            .group_by(retiro.motivo)
            .order_by(func.sum(retiro.monto).desc())
        )
    )
    if not filas:
        lineas.append("(sin retiros registrados en el periodo)")
    for motivo, cuantos, monto in filas:
        total_retiros += monto
        lineas.append(f"{(motivo or '(sin motivo)')[:40]:<40} {cuantos:>3}  {_pesos(monto):>14}")
    lineas.append(f"{'TOTAL RETIROS':<40} {'':>3}  {_pesos(total_retiros):>14}")

    lineas += _sub("ultimos retiros, uno por uno")
    for cuando, monto, motivo, quien, en_cajon in session.execute(
        select(retiro.created_at, retiro.monto, retiro.motivo, retiro.creado_por, retiro.en_cajon)
        .where(retiro.created_at >= desde)
        .order_by(retiro.created_at.desc())
        .limit(25)
    ):
        marca = "" if en_cajon else "  (no salio del cajon)"
        lineas.append(
            f"{cuando:%Y-%m-%d %H:%M}  {_pesos(monto):>12}  {(motivo or '-')[:34]:<34} {quien or '-'}{marca}"
        )
    return lineas, total_nomina, total_retiros


def _cortes(session, desde: datetime) -> list[str]:
    """Esperado contra contado: aqui se ve si el cajon cierra."""
    from sqlalchemy import func, select

    from pos_uniformes.database import models as m

    corte = m.LibretaCorte
    lineas = _titulo("los cortes")
    filas = list(
        session.execute(
            select(
                corte.id,
                corte.fecha,
                corte.periodo_label,
                corte.monto_esperado,
                corte.monto_final,
                corte.retiros_pagos,
                corte.otros_retiros,
                corte.reactivo_final,
                corte.nota,
            )
            .where(corte.created_at >= desde)
            .order_by(corte.fecha.desc(), corte.id.desc())
        )
    )
    if not filas:
        return lineas + ["(sin cortes en el periodo)"]

    faltante_total = _CERO
    cortos = 0
    lineas.append(
        f"{'id':>5} {'fecha':<11} {'esperado':>13} {'contado':>13} {'dif':>12}  nota"
    )
    for id_, fecha, _label, esperado, final, _pagos, _otros, _fondo, nota in filas:
        diferencia = (final or _CERO) - (esperado or _CERO)
        if esperado and diferencia < 0:
            faltante_total += -diferencia
            cortos += 1
        lineas.append(
            f"{id_:>5} {fecha!s:<11} {_pesos(esperado):>13} {_pesos(final):>13}"
            f" {_pesos(diferencia):>12}  {(nota or '')[:30]}"
        )
    lineas.append("")
    lineas.append(f"Cortes en el periodo : {len(filas)}")
    lineas.append(f"Cerraron cortos      : {cortos}")
    lineas.append(f"Faltante acumulado   : {_pesos(faltante_total)}")
    return lineas


def _pendientes(session) -> list[str]:
    """Dinero que todavia no es dinero, y el fondo del cajon."""
    from sqlalchemy import func, select

    from pos_uniformes.database import models as m

    lineas = _titulo("al dia de hoy")

    parametros = session.execute(select(m.CajaParametros)).scalars().first()
    if parametros:
        lineas.append(f"Fondo del cajon      : {_pesos(parametros.reactivo_actual)}")
        lineas.append(f"Sueldo base por ciclo: {_pesos(parametros.sueldo_base)}")
        lineas.append(f"Pesos por comision   : {_pesos(parametros.tarifa_comision)}")
        lineas.append(f"Descuento por falta  : {_pesos(parametros.descuento_falta)}")

    ap = m.Apartado
    cuantos, abonado, pendiente = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(ap.total_abonado), 0),
            func.coalesce(func.sum(ap.saldo_pendiente), 0),
        ).where(ap.estado == m.EstadoApartado.ACTIVO)
    ).one()
    lineas += _sub("apartados vivos (dinero por cobrar, NO vendido)")
    lineas.append(f"Apartados activos    : {cuantos:,}")
    lineas.append(f"Ya abonaron          : {_pesos(abonado)}")
    lineas.append(f"Falta que paguen     : {_pesos(pendiente)}")

    pr = m.PrestamoEmpleada
    lineas += _sub("prestamos a empleadas")
    filas = list(
        session.execute(
            select(
                pr.estado,
                func.count(),
                func.coalesce(func.sum(pr.monto), 0),
            )
            .group_by(pr.estado)
            .order_by(pr.estado)
        )
    )
    if not filas:
        lineas.append("(ninguno)")
    for estado, cuantos, monto in filas:
        lineas.append(f"{estado:<12} {cuantos:>3}  {_pesos(monto):>14}")
    vivo = session.execute(
        select(func.coalesce(func.sum(pr.monto), 0)).where(
            pr.estado == "aprobado", pr.cobrado_at.is_(None)
        )
    ).scalar_one()
    lineas.append(f"Prestado sin cobrar  : {_pesos(vivo)}")
    return lineas


def _lo_que_no_sabemos(session) -> list[str]:
    """Lo que el informe NO puede decir, y por que. Va al final a proposito."""
    from sqlalchemy import func, select

    from pos_uniformes.database import models as m

    compras = session.execute(select(func.count()).select_from(m.Compra)).scalar_one()
    lineas = _titulo("lo que esta cuenta no sabe")
    lineas.append(
        "Esto NO es una utilidad. El sistema no guarda lo que costo la"
    )
    lineas.append("mercancia, ni la renta, ni la luz, ni los pedidos a proveedor:")
    lineas.append(f"la tabla de compras tiene {compras} renglones.")
    lineas.append("")
    lineas.append("Lo unico que el sistema sabe que salio son los retiros del")
    lineas.append("cajon y la nomina. Todo lo demas se paga por fuera y no deja")
    lineas.append("rastro aqui.")
    return lineas


def construir(session, dias: int) -> str:
    from sqlalchemy import func, select

    from pos_uniformes.database import models as m

    desde = datetime.now().astimezone() - timedelta(days=dias)
    primera, ultima = session.execute(
        select(func.min(m.LibretaVenta.created_at), func.max(m.LibretaVenta.created_at))
    ).one()

    cabeza = [
        "INFORME DE FINANZAS - MAXIMODA",
        "=" * 31,
        f"Hecho el          : {datetime.now():%Y-%m-%d %H:%M}",
        f"Periodo del informe: ultimos {dias} dias (desde {desde:%Y-%m-%d})",
        f"Hay datos desde   : {primera:%Y-%m-%d %H:%M}" if primera else "Hay datos desde   : (nada)",
        f"Ultimo movimiento : {ultima:%Y-%m-%d %H:%M}" if ultima else "Ultimo movimiento : (nada)",
    ]

    entradas = _entradas(session, desde)
    salidas, nomina, retiros = _salidas(session, desde)

    from sqlalchemy import func as f2

    neto = session.execute(
        select(f2.coalesce(f2.sum(m.LibretaVenta.monto_neto), 0)).where(
            m.LibretaVenta.created_at >= desde
        )
    ).scalar_one()

    resumen = _titulo("en una linea")
    resumen.append(f"Entro (neto)         : {_pesos(neto)}")
    resumen.append(f"Nomina               : -{_pesos(nomina)}")
    resumen.append(f"Retiros del cajon    : -{_pesos(retiros)}")
    resumen.append(f"{'QUEDA':<21}: {_pesos(neto - nomina - retiros)}")
    resumen.append("")
    resumen.append("Ojo: 'queda' no es ganancia. Falta todo lo que no se")
    resumen.append("registra (mercancia, renta, servicios). Ver el final.")

    partes = (
        cabeza
        + resumen
        + entradas
        + salidas
        + _cortes(session, desde)
        + _pendientes(session)
        + _lo_que_no_sabemos(session)
    )
    return "\n".join(partes) + "\n"


def main(argv: list[str]) -> int:
    dias = DIAS_POR_OMISION
    if len(argv) > 1:
        try:
            dias = int(argv[1])
        except ValueError:
            print(f"'{argv[1]}' no es un numero de dias.")
            return 2

    from pos_uniformes.database.connection import get_session

    session = get_session()
    try:
        informe = construir(session, dias)
    finally:
        session.close()

    destino = Path(__file__).resolve().parent.parent / "reportes" / "finanzas.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(informe, encoding="utf-8")
    print(informe)
    print(f"\nGuardado en {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
