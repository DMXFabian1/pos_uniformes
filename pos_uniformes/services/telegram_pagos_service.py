"""Las respuestas de pagos del bot: a quién le toca, pagarle y retirar.

El corte ya se podía hacer desde lejos; los pagos no (Daniel, 2026-09-25).
Faltaba poder ver cuánto se le debe a cada quien y cerrarlo sin estar en la
tienda.

Aquí no se calcula nada: `nomina_service` dice cuánto y `retiros_service`
anota el retiro. Lo que sí vive aquí es el **candado**: lo que saca dinero no
pasa con una sola palabra, porque un dedo en el celular es más fácil de
resbalar que un clic en la caja.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

#: La segunda palabra que hace falta para que el dinero se mueva de verdad.
CONFIRMAR = {"si", "sí", "ok", "confirmar", "dale", "va"}


def _nombre(session, code: str) -> str:
    from pos_uniformes.services.nombres_empleadas_service import mostrar

    return mostrar(code)


def _detalle_texto(det, nombre: str) -> list[str]:
    """El desglose, como lo diría alguien: de dónde sale cada peso."""
    lineas = [f"{nombre}"]
    if det.desde:
        lineas.append(f"Del {det.desde.strftime('%d/%m')} al {det.hasta.strftime('%d/%m')}")
    if det.por_dia:
        lineas.append(f"Días: {det.dias_trabajados} × ${det.tarifa_dia:,.2f} = ${det.sueldo_base:,.2f}")
    else:
        lineas.append(f"Sueldo: ${det.sueldo_base:,.2f}")
    if det.comisiones:
        lineas.append(f"Comisiones: {det.comisiones} × ${det.tarifa_comision:,.2f} = ${det.monto_comisiones:,.2f}")
    if det.faltas:
        lineas.append(f"Faltas: {det.faltas} × ${det.descuento_falta:,.2f} = −${det.descuento_faltas:,.2f}")
    lineas.append("")
    lineas.append(f"TOTAL: ${det.total:,.2f}")
    return lineas


# ------------------------------------------------------------------- /pagos

def pagos(session: Session, *, hoy: date | None = None) -> str:
    """A quién le toca cobrar y cuánto, sin mover nada."""
    from pos_uniformes.services import nomina_service as nom

    avisos = nom.avisos_de_pago(session, hoy)
    if not avisos:
        return "No hay pagos pendientes. ✅"

    lineas = ["Pagos pendientes:", ""]
    total = Decimal("0")
    for a in avisos:
        nombre = _nombre(session, a.employee_code)
        det = nom.pago_pendiente(session, a.employee_code, hoy)
        total += det.total
        cuando = nom.cuando_pago(a)
        lineas.append(f"· {nombre} — ${det.total:,.2f}  ({cuando})")
    lineas.append("")
    lineas.append(f"En total: ${total:,.2f}")
    lineas.append("")
    lineas.append("Para pagarle a alguien: /pagar Fanny")
    return "\n".join(lineas)


# ------------------------------------------------------------------- /pagar

def pagar(session: Session, argumento: str, *, quien: str, hoy: date | None = None) -> str:
    """Enseña el desglose; solo paga si viene la confirmación.

    `/pagar Fanny` dice cuánto y de qué. `/pagar Fanny si` lo registra."""
    from pos_uniformes.services import asistencia_service as asis
    from pos_uniformes.services import nomina_service as nom

    partes = (argumento or "").split()
    if not partes:
        return "¿A quién? Por ejemplo:\n/pagar Fanny"

    confirmado = partes[-1].strip().lower() in CONFIRMAR
    nombre_buscado = " ".join(partes[:-1] if confirmado else partes).strip()
    if not nombre_buscado:
        return "¿A quién? Por ejemplo:\n/pagar Fanny"

    code = asis.buscar_code(session, nombre_buscado)
    if code is None:
        return f"¿Quién es «{nombre_buscado}»? Escríbelo como aparece en /asistencia."

    nombre = _nombre(session, code)
    det = nom.pago_pendiente(session, code, hoy)
    if det.total <= 0:
        return f"{nombre} no tiene nada pendiente ahora mismo."

    if not confirmado:
        # El dinero no se mueve con una sola palabra.
        return "\n".join(
            _detalle_texto(det, nombre)
            + ["", f"Si está bien: /pagar {nombre_buscado} si"]
        )

    try:
        nom.registrar_pago_con_monto(session, code, creado_por=quien, fecha=hoy)
    except PermissionError as exc:
        return f"No se pudo: {exc}"
    session.commit()
    return "\n".join([f"✅ Pagado a {nombre}: ${det.total:,.2f}"] + ["", "Si fue un error, /deshacerpago"])


# ------------------------------------------------------------------ /retiro

def retiro(session: Session, argumento: str, *, quien: str) -> str:
    """Saca dinero del cajón dejando dicho para qué: `/retiro 500 gasolina`."""
    from pos_uniformes.services import retiros_service

    partes = (argumento or "").split()
    if not partes:
        return "¿Cuánto y para qué? Por ejemplo:\n/retiro 500 gasolina"

    crudo = partes[0].replace("$", "").replace(",", "")
    try:
        monto = Decimal(crudo)
    except InvalidOperation:
        return f"No entendí «{partes[0]}» como cantidad. Por ejemplo:\n/retiro 500 gasolina"
    if monto <= 0:
        return "El retiro tiene que ser mayor a cero."

    motivo = " ".join(partes[1:]).strip()
    if not motivo:
        # Sin motivo, el corte de la noche es un misterio.
        return f"¿Para qué son los ${monto:,.2f}? Por ejemplo:\n/retiro {crudo} gasolina"

    retiros_service.registrar_retiro(session, monto=monto, motivo=motivo, creado_por=quien)
    session.commit()
    return f"✅ Retirado del cajón: ${monto:,.2f} para {motivo}.\n\nEl corte de hoy ya lo toma en cuenta."


# ------------------------------------------------------------ /deshacerpago

def deshacer_pago(session: Session, *, quien: str) -> str:
    """Deshace el último pago registrado. La red debajo de /pagar."""
    from pos_uniformes.database.models import EmpleadaPago
    from pos_uniformes.services import nomina_service as nom
    from sqlalchemy import select

    ultimo = session.scalars(
        select(EmpleadaPago).order_by(EmpleadaPago.id.desc()).limit(1)
    ).first()
    if ultimo is None:
        return "No hay ningún pago que deshacer."

    nombre = _nombre(session, str(ultimo.employee_code))
    monto = Decimal(str(ultimo.total or 0))
    try:
        nom.deshacer_pago(session, int(ultimo.id), creado_por=quien)
    except PermissionError as exc:
        return f"No se pudo: {exc}"
    session.commit()
    return f"↩️ Deshecho el pago a {nombre} de ${monto:,.2f}."
