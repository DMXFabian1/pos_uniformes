"""Alertas al celular de Daniel por Telegram.

Dos caminos:

1. **Cola en la base** (`alerta_telegram`): cortes y retiros la llenan desde
   donde ocurran (kiosko, PWA, bot, tarea). El bot de la PC servidor, que ya
   está escuchando, manda lo pendiente en cada vuelta. Los kioskos no
   necesitan el token.
2. **Vigilante**: el bot revisa cada vuelta si ya cerró la tienda sin corte
   y si hubo movimientos fuera de horario. Lógica pura en `Vigilante.revisar`.

Todo lo que encola es defensivo: si la tabla aún no existe (base sin
migrar) no rompe la operación que la llamó.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

logger = logging.getLogger("alertas")

_CENT = Decimal("0.01")
# Un corte del dueño con más de esto de diferencia se marca con ⚠️.
TOLERANCIA_DIFERENCIA = Decimal("50.00")
# Minutos después del cierre para avisar que no hubo corte.
MINUTOS_SIN_CORTE = 10
MAX_INTENTOS = 5


def _d(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(_CENT)


def _local(momento: datetime | None) -> datetime:
    if momento is None:
        return datetime.now()
    return momento.astimezone().replace(tzinfo=None) if momento.tzinfo else momento


# ----------------------------------------------------------------- cola
def encolar(session, texto: str) -> bool:
    """Deja la alerta en la cola. Devuelve False (sin romper) si no se pudo."""
    texto = (texto or "").strip()
    if not texto:
        return False
    try:
        from pos_uniformes.database.models import AlertaTelegram

        session.add(AlertaTelegram(texto=texto, created_at=datetime.now().astimezone()))
        session.commit()
        return True
    except Exception as exc:  # noqa: BLE001 — base sin la tabla, sin red, etc.
        logger.warning("No se pudo encolar la alerta: %s", exc)
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


def pendientes(session) -> list:
    from pos_uniformes.database.models import AlertaTelegram

    stmt = (
        select(AlertaTelegram)
        .where(AlertaTelegram.enviado_at.is_(None), AlertaTelegram.intentos < MAX_INTENTOS)
        .order_by(AlertaTelegram.id)
    )
    return list(session.scalars(stmt).all())


def enviar_pendientes(session, enviar) -> int:
    """Manda cada alerta pendiente con `enviar(texto)`; marca enviadas. Devuelve cuántas salieron."""
    enviadas = 0
    for alerta in pendientes(session):
        alerta.intentos = int(alerta.intentos or 0) + 1
        try:
            enviar(alerta.texto)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Alerta %s no salió (intento %s): %s", alerta.id, alerta.intentos, exc)
            session.commit()
            break  # sin red: lo demás tampoco va a salir ahora
        alerta.enviado_at = datetime.now().astimezone()
        enviadas += 1
        session.commit()
    return enviadas


# ----------------------------------------------------------------- textos
def texto_alerta_corte(corte, venta_efectivo, *, pagos=None, retiros=None) -> str:
    """Aviso al momento de cualquier corte: quién, venta, pagos, lo que se saca."""
    quien = str(corte.creado_por or "").upper() or "?"
    hora = _local(getattr(corte, "hasta", None) or getattr(corte, "created_at", None)).strftime("%H:%M")
    se_saca = (_d(corte.monto_final) - _d(corte.reactivo_final)).quantize(_CENT)
    lineas = [f"🧾 Corte hecho por {quien} a las {hora}"]
    lineas.append(f"Venta efectivo ${_d(venta_efectivo):,.2f}")
    detalle = []
    if _d(corte.retiros_pagos) > 0:
        detalle.append(f"pagos ${_d(corte.retiros_pagos):,.2f}")
    if _d(corte.otros_retiros) > 0:
        detalle.append(f"retiros ${_d(corte.otros_retiros):,.2f}")
    if detalle:
        lineas[-1] += " · " + " · ".join(detalle)
    for p in pagos or []:
        nombre = (getattr(p, "employee_name", "") or getattr(p, "employee_code", "")).split()[0]
        lineas.append(f"  💵 {nombre}: ${_d(p.total):,.2f}")
    lineas.append(f"Se saca ${se_saca:,.2f} · reactivo queda ${_d(corte.reactivo_final):,.2f}")
    if getattr(corte, "hasta", None) is not None:
        dif = (_d(corte.monto_final) - _d(corte.monto_esperado)).quantize(_CENT)
        if dif != 0 and quien == "VEND-1":
            # Su corte con ajuste: solo el dueño recibe esto; el encargado ve la cifra final.
            lineas.append(f"Ajuste: real ${_d(corte.monto_esperado):,.2f} → tu cifra ${_d(corte.monto_final):,.2f} ({'+' if dif > 0 else '−'}${abs(dif):,.2f})")
        elif dif != 0:
            marca = "⚠️ " if abs(dif) >= TOLERANCIA_DIFERENCIA else ""
            lineas.append(f"{marca}{'Sobraron' if dif > 0 else 'FALTARON'} ${abs(dif):,.2f}")
    if corte.nota:
        lineas.append(f"Nota: {corte.nota}")
    return "\n".join(lineas)


def texto_alerta_retiro(retiro) -> str:
    hora = _local(getattr(retiro, "created_at", None)).strftime("%H:%M")
    return f"💸 Retiro del cajón: ${_d(retiro.monto):,.2f} — {retiro.motivo} ({str(retiro.creado_por).upper()}, {hora})"


def texto_sin_corte(dia: date, cierre) -> str:
    return (
        f"⏰ Ya cerró la tienda ({cierre.strftime('%H:%M')}) y hoy no se ha hecho corte.\n"
        "Manda /corte para hacerlo ahora."
    )


def texto_fuera_de_horario(row, apertura, cierre) -> str:
    momento = _local(row.created_at)
    nombre = (row.employee_name or row.employee_code or "?").split()[0]
    return (
        f"🚨 Movimiento fuera de horario: {row.tipo} ${_d(row.monto_total):,.2f} por {nombre} "
        f"a las {momento.strftime('%H:%M')} (horario {apertura.strftime('%H:%M')}–{cierre.strftime('%H:%M')})"
    )


# ----------------------------------------------------------------- vigilante
@dataclass
class Vigilante:
    """Estado entre vueltas del bot: qué ya se avisó y hasta qué movimiento se revisó."""

    ultimo_id: int | None = None
    dia_sin_corte_avisado: date | None = None
    _apertura: object = field(default=None, repr=False)

    def revisar(self, session, ahora: datetime | None = None) -> list[str]:
        """Devuelve los textos a mandar ahora (puede ser vacío)."""
        ahora = _local(ahora or datetime.now().astimezone())
        textos: list[str] = []
        textos += self._movimientos_fuera_de_horario(session, ahora)
        textos += self._cierre_sin_corte(session, ahora)
        return textos

    def _movimientos_fuera_de_horario(self, session, ahora: datetime) -> list[str]:
        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.horario_tienda_service import hora_apertura, hora_cierre

        if self.ultimo_id is None:
            # Primera vuelta: no reclamar lo viejo, solo marcar dónde vamos.
            self.ultimo_id = int(session.scalar(select(func.coalesce(func.max(LibretaVenta.id), 0))) or 0)
            return []
        rows = list(session.scalars(
            select(LibretaVenta).where(LibretaVenta.id > self.ultimo_id).order_by(LibretaVenta.id)
        ).all())
        textos = []
        for row in rows:
            self.ultimo_id = max(self.ultimo_id, int(row.id))
            momento = _local(row.created_at)
            apertura, cierre = hora_apertura(momento.date()), hora_cierre(momento.date())
            if not (apertura <= momento.time() <= cierre):
                textos.append(texto_fuera_de_horario(row, apertura, cierre))
        return textos

    def _cierre_sin_corte(self, session, ahora: datetime) -> list[str]:
        from pos_uniformes.database.models import LibretaCorte, LibretaVenta
        from pos_uniformes.services.horario_tienda_service import hora_cierre

        hoy = ahora.date()
        if self.dia_sin_corte_avisado == hoy:
            return []
        cierre = hora_cierre(hoy)
        if ahora < datetime.combine(hoy, cierre) + timedelta(minutes=MINUTOS_SIN_CORTE):
            return []
        inicio = datetime.combine(hoy, datetime.min.time()).astimezone()
        hubo_corte = session.scalar(
            select(func.count(LibretaCorte.id)).where(LibretaCorte.fecha == hoy)
        )
        self.dia_sin_corte_avisado = hoy  # se avisa una sola vez al día (o se anota que no hacía falta)
        if hubo_corte:
            return []
        hubo_movimiento = session.scalar(
            select(func.count(LibretaVenta.id)).where(LibretaVenta.created_at >= inicio)
        )
        if not hubo_movimiento:
            return []
        return [texto_sin_corte(hoy, cierre)]


def procesar(session_factory, enviar, vigilante: Vigilante | None = None) -> int:
    """Una vuelta completa: manda la cola y lo que vea el vigilante. Nunca truena."""
    enviadas = 0
    try:
        with session_factory() as session:
            enviadas += enviar_pendientes(session, enviar)
            if vigilante is not None:
                for texto in vigilante.revisar(session):
                    if encolar(session, texto):
                        enviadas += enviar_pendientes(session, enviar)
    except Exception as exc:  # noqa: BLE001 — base sin migrar, sin red...
        logger.debug("Alertas: vuelta sin efecto (%s)", exc)
    return enviadas
