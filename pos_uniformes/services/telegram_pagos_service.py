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

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

#: La segunda palabra que hace falta para que el dinero se mueva de verdad.
CONFIRMAR = {"si", "sí", "ok", "confirmar", "dale", "va"}


def _nombre(session, code: str) -> str:
    from pos_uniformes.services.nombres_empleadas_service import mostrar

    return mostrar(code)


def existe_y_trabaja(session, code: str) -> bool:
    """¿Ese código es de alguien del equipo, y sigue activa?

    Hace falta porque nada más lo comprobaba: `m:pagarok:NADIE` registraba un
    pago de $1,300 a una empleada inventada — el cálculo le daba el sueldo
    base por omisión y nadie preguntaba si existía (encontrado el 2026-10-08
    probando botones viejos).

    El caso real no es un código inventado: es el botón de un mensaje de hace
    días para alguien que ya se dio de baja.
    """
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Empleada

    buscado = str(code or "").strip()
    if not buscado:
        return False
    return session.scalar(
        select(Empleada).where(
            func.upper(Empleada.codigo) == buscado.upper(),
            Empleada.activo.is_(True),
        )
    ) is not None


def _no_es_del_equipo(session, code: str) -> str:
    """El mismo recado para los tres caminos, para que no discrepen."""
    return (
        f"No tengo a nadie activo con el código «{code}».\n\n"
        "Si es un botón de hace días, la persona pudo darse de baja. "
        "Mira /pagos para los de ahora."
    )


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
    # Se enseña lo que el pago SÍ descontó, no el préstamo entero: el total no
    # baja de cero, así que restar $2,000 de un sueldo de $1,300 nunca cuadra.
    cubierto = getattr(det, "prestamo_cubierto", None)
    if cubierto is None:
        cubierto = getattr(det, "prestamos", 0)
    if cubierto:
        lineas.append(f"Préstamo: −${cubierto:,.2f}")
    lineas.append("")
    lineas.append(f"TOTAL: ${det.total:,.2f}")
    sin_cubrir = getattr(det, "prestamo_sin_cubrir", 0)
    if sin_cubrir:
        lineas.append(f"(le siguen quedando ${sin_cubrir:,.2f} del préstamo para el próximo pago)")
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


def quienes_cobran(session: Session, *, hoy: date | None = None) -> list[tuple[str, str]]:
    """(código, nombre) de quienes tienen algo pendiente. Para los botones."""
    from pos_uniformes.services import nomina_service as nom

    salida = []
    for a in nom.avisos_de_pago(session, hoy):
        det = nom.pago_pendiente(session, a.employee_code, hoy)
        if det.total > 0:
            salida.append((str(a.employee_code), _nombre(session, a.employee_code)))
    return salida


def tiene_pendiente(session: Session, code: str, *, hoy: date | None = None) -> bool:
    from pos_uniformes.services import nomina_service as nom

    if not existe_y_trabaja(session, code):
        return False
    return nom.pago_pendiente(session, code, hoy).total > 0


def desglose_por_code(session: Session, code: str, *, hoy: date | None = None) -> str:
    """De dónde sale cada peso. Lo mismo que enseña `/pagar Fulana`."""
    from pos_uniformes.services import nomina_service as nom

    if not existe_y_trabaja(session, code):
        return _no_es_del_equipo(session, code)
    nombre = _nombre(session, code)
    det = nom.pago_pendiente(session, code, hoy)
    if det.total <= 0:
        return f"{nombre} no tiene nada pendiente ahora mismo."
    return "\n".join(_detalle_texto(det, nombre))


def pagar_por_code(session: Session, code: str, *, quien: str, hoy: date | None = None) -> str:
    """Registra el pago. Ya viene confirmado por el segundo toque."""
    from pos_uniformes.services import nomina_service as nom

    if not existe_y_trabaja(session, code):
        return _no_es_del_equipo(session, code)
    nombre = _nombre(session, code)
    det = nom.pago_pendiente(session, code, hoy)
    if det.total <= 0:
        return f"{nombre} no tiene nada pendiente ahora mismo."
    try:
        nom.registrar_pago_con_monto(session, code, creado_por=quien, fecha=hoy)
    except (PermissionError, ValueError) as exc:
        # ValueError = ya cobró hoy (doble toque o reentrega de Telegram).
        session.rollback()
        return f"No se pudo: {exc}"
    session.commit()
    return f"✅ Pagado a {nombre}: ${det.total:,.2f}\n\nSi fue un error, /deshacerpago"


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
        return desglose_por_code(session, code, hoy=hoy) + f"\n\nSi está bien: /pagar {nombre_buscado} si"

    return pagar_por_code(session, code, quien=quien, hoy=hoy)


# ------------------------------------------------------------------ /retiro

def retiro(session: Session, argumento: str, *, quien: str) -> str:
    """Saca dinero del cajón dejando dicho para qué: `/retiro 500 gasolina`."""
    from pos_uniformes.services import retiros_service

    partes = (argumento or "").split()
    if not partes:
        return "¿Cuánto y para qué? Por ejemplo:\n/retiro 500 gasolina"

    from pos_uniformes.services.telegram_bot_service import leer_cifra

    monto = leer_cifra(partes[0])
    if monto is None:
        return f"No entendí «{partes[0]}» como cantidad. Por ejemplo:\n/retiro 500 gasolina"
    if monto <= 0:
        return "El retiro tiene que ser mayor a cero."

    motivo = " ".join(partes[1:]).strip()
    if not motivo:
        # Sin motivo, el corte de la noche es un misterio.
        return f"¿Para qué son los ${monto:,.2f}? Por ejemplo:\n/retiro {partes[0]} gasolina"

    try:
        retiros_service.registrar_retiro(session, monto=monto, motivo=motivo, creado_por=quien)
    except ValueError as exc:
        session.rollback()
        return f"No lo apunté: {exc}"
    session.commit()
    return f"✅ Retirado del cajón: ${monto:,.2f} para {motivo}.\n\nEl corte de hoy ya lo toma en cuenta."


# ------------------------------------------------------------ /deshacerpago

def deshacer_pago(session: Session, *, quien: str, hoy: date | None = None) -> str:
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
    hoy_ = hoy or date.today()
    if ultimo.fecha != hoy_:
        # La red debajo de /pagar es para el dedazo de HOY. El último pago de
        # la tabla puede ser de otro día y de otra persona (el encargado en el
        # kiosko), y deshacerlo desde el celular sin verlo era demasiado fácil
        # (2026-10-10).
        return (
            f"El último pago es del {ultimo.fecha:%d/%m} a {nombre} (${monto:,.2f}), no de hoy. "
            "Desde aquí solo se deshace el de hoy; ese se corrige en la tienda."
        )
    try:
        nom.deshacer_pago(session, int(ultimo.id), creado_por=quien)
    except PermissionError as exc:
        return f"No se pudo: {exc}"
    session.commit()
    return f"↩️ Deshecho el pago a {nombre} de ${monto:,.2f}."


def _ajuste_comisiones(r: dict) -> str:
    """«Le quedaron 83 comisiones ($1,436.00); las 20 del 19/10 pasan al siguiente pago.»"""
    de, a = int(r.get("comisiones_de") or 0), int(r.get("comisiones_a") or 0)
    if de == a:
        return ""
    if a < de:
        return (f" Le quedaron {a} comisiones (${r['total_a']:,.2f}); las {de - a} de después del"
                f" {r['a']:%d/%m} pasan al siguiente pago.")
    return f" Ahora cubre {a} comisiones (${r['total_a']:,.2f}), {a - de} más."


def fecha_pago(session: Session, argumento: str, *, quien: str, hoy: date | None = None) -> str:
    """«/fechapago Stayce 18/10»: el último pago de esa persona pasa a ese día.

    Para cuando se le pagó un día y se registró al siguiente (Stayce,
    2026-10-20). No deshace nada: mueve la fecha, la marca del calendario y el
    arranque de su siguiente ciclo. También vale «ayer» y «antier»."""
    import re

    from pos_uniformes.services import asistencia_service as asis
    from pos_uniformes.services import nomina_service as nom

    hoy = hoy or date.today()
    partes = (argumento or "").strip().split()
    if len(partes) < 2:
        return "¿De quién y qué día? Por ejemplo:\n/fechapago Stayce 18/10\n/fechapago Stayce ayer"
    cuando = partes[-1].lower()
    nombre_buscado = " ".join(partes[:-1])
    if cuando == "ayer":
        nueva = hoy - timedelta(days=1)
    elif cuando in ("antier", "anteayer"):
        nueva = hoy - timedelta(days=2)
    else:
        m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", cuando)
        if not m:
            return f"No entendí «{cuando}» como fecha. Escríbela como 18/10, o «ayer»."
        anio = int(m.group(3)) if m.group(3) else hoy.year
        if anio < 100:
            anio += 2000
        try:
            nueva = date(anio, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return f"«{cuando}» no es un día que exista."
    code = asis.buscar_code(session, nombre_buscado)
    if not code or not existe_y_trabaja(session, code):
        return f"¿Quién es «{nombre_buscado}»? Escríbelo como aparece en /asistencia."
    nombre = _nombre(session, code)
    ultimo = nom.ultimo_pago_registrado(session, code)
    if ultimo is None:
        return f"{nombre} no tiene ningún pago registrado."
    try:
        r = nom.mover_fecha_pago(session, int(ultimo.id), nueva, creado_por=quien)
    except (ValueError, PermissionError) as exc:
        return f"No se pudo: {exc}"
    session.commit()
    extra = " Su siguiente pago también se recorrió." if r["ciclo_movido"] else ""
    extra += _ajuste_comisiones(r)
    return (
        f"📅 El pago a {nombre} de ${r['total']:,.2f} pasó del {r['de']:%d/%m} al {r['a']:%d/%m}.{extra}"
    )
