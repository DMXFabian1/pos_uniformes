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

import logging
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


def _hay_que_pagar(det) -> bool:
    """¿Hay un pago que registrar? También cuando el préstamo se come todo:
    se entrega $0 pero el ciclo se cierra y el préstamo queda cobrado. Antes
    decía «no tiene nada pendiente» y el ciclo nunca se cerraba (auditoría
    2026-11-07, #13)."""
    return det.total > 0 or Decimal(getattr(det, "prestamo_cubierto", 0) or 0) > 0


def quienes_cobran(session: Session, *, hoy: date | None = None) -> list[tuple[str, str]]:
    """(código, nombre) de quienes tienen algo pendiente. Para los botones."""
    from pos_uniformes.services import nomina_service as nom

    salida = []
    for a in nom.avisos_de_pago(session, hoy):
        det = nom.pago_pendiente(session, a.employee_code, hoy)
        if _hay_que_pagar(det):
            salida.append((str(a.employee_code), _nombre(session, a.employee_code)))
    return salida


def tiene_pendiente(session: Session, code: str, *, hoy: date | None = None) -> bool:
    from pos_uniformes.services import nomina_service as nom

    if not existe_y_trabaja(session, code):
        return False
    return _hay_que_pagar(nom.pago_pendiente(session, code, hoy))


def monto_pendiente(session: Session, code: str, *, hoy: date | None = None):
    """Lo que se le pagaría ahora mismo (0 si no trabaja aquí o no hay nada)."""
    from decimal import Decimal

    from pos_uniformes.services import nomina_service as nom

    if not existe_y_trabaja(session, code):
        return Decimal("0.00")
    return Decimal(nom.pago_pendiente(session, code, hoy).total).quantize(Decimal("0.01"))


def desglose_por_code(session: Session, code: str, *, hoy: date | None = None) -> str:
    """De dónde sale cada peso. Lo mismo que enseña `/pagar Fulana`."""
    from pos_uniformes.services import nomina_service as nom

    if not existe_y_trabaja(session, code):
        return _no_es_del_equipo(session, code)
    nombre = _nombre(session, code)
    det = nom.pago_pendiente(session, code, hoy)
    if not _hay_que_pagar(det):
        return f"{nombre} no tiene nada pendiente ahora mismo."
    return "\n".join(_detalle_texto(det, nombre))


def pagar_por_code(session: Session, code: str, *, quien: str, hoy: date | None = None) -> str:
    """Registra el pago. Ya viene confirmado por el segundo toque."""
    from pos_uniformes.services import nomina_service as nom

    if not existe_y_trabaja(session, code):
        return _no_es_del_equipo(session, code)
    nombre = _nombre(session, code)
    det = nom.pago_pendiente(session, code, hoy)
    if not _hay_que_pagar(det):
        return f"{nombre} no tiene nada pendiente ahora mismo."
    try:
        nom.registrar_pago_con_monto(session, code, creado_por=quien, fecha=hoy)
    except (PermissionError, ValueError) as exc:
        # ValueError = ya cobró hoy (doble toque o reentrega de Telegram).
        session.rollback()
        return f"No se pudo: {exc}"
    session.commit()
    if det.total <= 0:
        return (f"✅ Ciclo de {nombre} cerrado: el préstamo se llevó todo el pago "
                f"(${Decimal(getattr(det, 'prestamo_cubierto', 0) or 0):,.2f}). No se le entrega nada.\n\nSi fue un error, /deshacerpago")
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
    if not _hay_que_pagar(det):
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

    resto = partes[1:]
    forzar = bool(resto) and resto[-1].lower() in ("forzar", "!")
    if forzar:
        resto = resto[:-1]
    motivo = " ".join(resto).strip()
    if not motivo:
        # Sin motivo, el corte de la noche es un misterio.
        return f"¿Para qué son los ${monto:,.2f}? Por ejemplo:\n/retiro {partes[0]} gasolina"

    # Tope: lo que debería haber en el cajón. Con un cero de más el esperado
    # quedaba negativo y el siguiente corte dejaba el fondo en $0 (auditoría
    # 2026-11-07, #9). Si de verdad hay más (lo contaste), «forzar» al final.
    if not forzar:
        hay = _en_cajon(session)
        if hay is not None and monto > hay:
            return (
                f"⚠️ No lo apunté: en el cajón debería haber ${hay:,.2f} y quieres sacar ${monto:,.2f}.\n"
                "¿Un cero de más?\n\n"
                f"Si de verdad hay más (lo contaste), mándalo con «forzar» al final:\n"
                f"/retiro {partes[0]} {motivo} forzar"
            )

    try:
        retiros_service.registrar_retiro(session, monto=monto, motivo=motivo, creado_por=quien)
    except ValueError as exc:
        session.rollback()
        return f"No lo apunté: {exc}"
    session.commit()
    return f"✅ Retirado del cajón: ${monto:,.2f} para {motivo}.\n\nEl corte de hoy ya lo toma en cuenta."


def _en_cajon(session) -> Decimal | None:
    """Lo que debería haber en el cajón ahora (None si no se puede saber)."""
    try:
        from pos_uniformes.services.corte_caja_service import estado_caja

        return estado_caja(session).esperado
    except Exception:  # noqa: BLE001 — sin saberlo, no se frena el retiro
        logging.getLogger(__name__).warning("Retiro: no se pudo calcular el cajón", exc_info=True)
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


def entrada(session: Session, argumento: str, *, quien: str) -> str:
    """Dinero que entró al cajón sin ser venta: `/entrada 1750 papá`.

    El fondo que deja el papá de Daniel para la nómina (2026-10-20). Los pagos
    siguen saliendo del cajón completos; el corte suma esto al esperado."""
    from pos_uniformes.services import entradas_service

    partes = (argumento or "").split()
    if not partes:
        return "¿Cuánto entró y de dónde? Por ejemplo:\n/entrada 1750 papá"

    from pos_uniformes.services.telegram_bot_service import leer_cifra

    monto = leer_cifra(partes[0])
    if monto is None:
        return f"No entendí «{partes[0]}» como cantidad. Por ejemplo:\n/entrada 1750 papá"
    if monto <= 0:
        return "La entrada tiene que ser mayor a cero."
    motivo = " ".join(partes[1:]).strip() or entradas_service.MOTIVO_POR_DEFECTO
    if motivo.lower() in ("papá", "papa", "mi papá", "mi papa"):
        motivo = entradas_service.MOTIVO_POR_DEFECTO
    try:
        entradas_service.registrar_entrada(session, monto=monto, motivo=motivo, creado_por=quien)
    except ValueError as exc:
        session.rollback()
        return f"No lo apunté: {exc}"
    session.commit()
    return (f"✅ Entró al cajón: ${monto:,.2f} ({motivo}).\n\n"
            "Los pagos salen del cajón como siempre; el corte ya suma esto y lo que sobre se queda.")


# ------------------------------------------------------------ /deshacer

def _dia_local(momento) -> date | None:
    if momento is None:
        return None
    return (momento.astimezone() if momento.tzinfo else momento).date()


def _movimientos_de_hoy(session: Session, hoy: date) -> list[tuple[str, object]]:
    """Los retiros y entradas de hoy, el más nuevo primero: («r12», fila)."""
    from pos_uniformes.database.models import CajaEntrada, CajaRetiro
    from sqlalchemy import select

    filas: list[tuple[str, object]] = []
    for letra, modelo in (("r", CajaRetiro), ("e", CajaEntrada)):
        for f in session.scalars(select(modelo).order_by(modelo.created_at.desc()).limit(20)).all():
            if _dia_local(f.created_at) == hoy:
                filas.append((f"{letra}{f.id}", f))
    filas.sort(key=lambda x: x[1].created_at, reverse=True)
    return filas


def _renglon_movimiento(clave: str, fila) -> str:
    que = "Retiro" if clave.startswith("r") else "Entrada"
    hora = f"{fila.created_at.astimezone() if fila.created_at.tzinfo else fila.created_at:%H:%M}"
    return f"{que} de ${Decimal(str(fila.monto)):,.2f} ({fila.motivo or 'sin motivo'}, {hora}) → /deshacer_{clave}"


def deshacer(session: Session, argumento: str = "", *, quien: str, hoy: date | None = None) -> str:
    """«/deshacer»: los retiros y entradas de hoy, cada uno con su
    «/deshacer r12». Con la clave, se borra (auditoría 2026-11-07, sección 5:
    las funciones existían y el celular no las ofrecía).

    Mismas redes que /deshacerpago: solo de hoy, nunca uno que ya entró en un
    corte, y el retiro de un préstamo no (ese se arregla con el préstamo)."""
    from pos_uniformes.services import entradas_service, retiros_service

    hoy_ = hoy or date.today()
    movimientos = _movimientos_de_hoy(session, hoy_)
    clave = (argumento or "").strip().lower().lstrip("#")
    if not clave:
        if not movimientos:
            return "Hoy no hay retiros ni entradas que deshacer."
        lineas = [_renglon_movimiento(c, f) for c, f in movimientos[:8]]
        return "Retiros y entradas de hoy (toca el comando del que quieras deshacer):\n\n" + "\n".join(lineas)
    fila = dict(movimientos).get(clave)
    if fila is None:
        return (f"No encuentro «{clave}» entre los retiros y entradas de hoy. "
                "Manda /deshacer para ver la lista. Los de otros días se corrigen en la tienda.")
    monto = Decimal(str(fila.monto))
    if clave.startswith("r") and str(fila.motivo or "").startswith("Préstamo a"):
        return (f"Ese retiro es el préstamo ({fila.motivo}, ${monto:,.2f}). Borrarlo dejaría el préstamo "
                "aprobado sin su dinero; se corrige en la tienda.")
    corte = _corte_despues(session, fila.created_at)
    if corte is not None:
        hora = f" de las {corte.created_at:%H:%M}" if getattr(corte, "created_at", None) else ""
        return (f"Ese ya entró en el corte{hora}: deshacerlo dejaría ese corte descuadrado. "
                "Se corrige en la tienda.")
    try:
        if clave.startswith("r"):
            ok = retiros_service.eliminar_retiro(session, fila.id, creado_por=quien)
        else:
            ok = entradas_service.eliminar_entrada(session, fila.id, creado_por=quien)
    except PermissionError as exc:
        return f"No se pudo: {exc}"
    if not ok:
        return "Ya no estaba; nada que deshacer."
    que = "el retiro" if clave.startswith("r") else "la entrada"
    return f"↩️ Deshice {que} de ${monto:,.2f} ({fila.motivo or 'sin motivo'}). El cajón ya no lo cuenta."


# ------------------------------------------------------------ /deshacerpago

def _corte_despues(session: Session, cuando):
    """El primer corte hecho después de `cuando` (o None)."""
    from pos_uniformes.database.models import LibretaCorte
    from sqlalchemy import select

    if cuando is None:
        return None
    return session.scalars(
        select(LibretaCorte).where(LibretaCorte.created_at > cuando).order_by(LibretaCorte.created_at).limit(1)
    ).first()


def deshacer_pago(session: Session, argumento: str = "", *, quien: str, hoy: date | None = None) -> str:
    """Deshace el último pago registrado. La red debajo de /pagar.

    Dos pasos (auditoría 2026-11-07, #10): «/deshacerpago» dice a quién, cuánto
    y a qué hora, y pide «/deshacerpago <id>»; con el id, si sigue siendo el
    último, se deshace. Si ya hubo un corte después del pago, no se toca desde
    aquí: ese corte ya restó el pago, y deshacerlo dejaba ese corte y el
    siguiente descuadrados."""
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
    corte = _corte_despues(session, getattr(ultimo, "created_at", None))
    if corte is not None:
        hora = f" de las {corte.created_at:%H:%M}" if getattr(corte, "created_at", None) else ""
        return (
            f"El pago a {nombre} (${monto:,.2f}) ya entró en el corte{hora}: ese corte ya lo restó. "
            "Deshacerlo desde aquí dejaría ese corte y el siguiente descuadrados; corrígelo en la tienda."
        )
    arg = (argumento or "").strip().lstrip("#")
    if arg != str(ultimo.id):
        hora = f" a las {ultimo.created_at:%H:%M}" if getattr(ultimo, "created_at", None) else ""
        if arg:
            aviso = f"#{arg} ya no es el último pago. "
        else:
            aviso = ""
        return (
            f"{aviso}El último pago es a {nombre} de ${monto:,.2f} (hoy{hora}, #{ultimo.id}).\n"
            f"Para deshacerlo manda: /deshacerpago {ultimo.id}"
        )
    try:
        r = nom.deshacer_pago(session, int(ultimo.id), creado_por=quien)
    except PermissionError as exc:
        return f"No se pudo: {exc}"
    session.commit()
    texto = f"↩️ Deshecho el pago a {nombre} de ${monto:,.2f}."
    regresado = Decimal(str((r or {}).get("prestamo_regresado") or 0))
    if regresado:
        texto += f" Su préstamo de ${regresado:,.2f} vuelve a estar pendiente: se le descuenta en el siguiente pago."
    return texto


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
