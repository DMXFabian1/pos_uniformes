"""QR de descuento de temporada (Daniel, 2026-11-16: «Sí, con candados»).

Un solo QR con el texto «DSCT-» + el código secreto. El código es el mismo
«Codigo promo manual» de Configuración: se valida contra
`ConfiguracionNegocio.promo_authorization_code_hash` (no hay columna nueva).

Al escanearlo en la venta, la empleada elige 5 %, 10 % o 15 %. El motor de
beneficios (`services/beneficios/motor.py`) lo aplica solo a la ropa normal
y por línea gana el mayor entre mayoreo, empleada y QR.

Candados:
- Los códigos de fábrica y los de antes están en el repo público: si el
  código escaneado o el guardado es uno de ellos, se rechaza («Cambia el
  código del QR en Configuración»).
- Nunca se imprime ni se anota el código escaneado.
- Sin conexión no se acepta («El QR de descuento necesita conexión»).
- Tres códigos equivocados seguidos bloquean el QR 5 minutos en esa máquina.
- Vence el 6 de enero de 2027 (fin del día, hora local): después se rechaza
  y el motor no lo aplica aunque venga en la entrada.
- Solo ropa normal (no uniformes, ni rebajas, ni promo 3pz). El 15 % pide
  $600 de ropa normal a precio de lista; si el carrito baja de eso, el
  motor aplica 10 % y lo dice.
- Las líneas con QR no abonan Monedero.

Este módulo es puro salvo `validar_codigo` y `hash_guardado`, que reciben
la sesión de quien llama. El aviso por Telegram está en
`descuento_qr_aviso_service.py`.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

from pos_uniformes.services.beneficios.contrato import (
    QR_CATEGORIAS_ROPA_NORMAL,
    QR_MINIMO_15,
    QR_PORCENTAJES,
    QR_VENCE,
)

_logger = logging.getLogger(__name__)

#: El texto del QR empieza así; lo que sigue es el código secreto.
PREFIJO = "DSCT-"
#: Las reglas que usa el motor viven en su contrato (el motor no importa
#: nada fuera de `services/beneficios`); aquí se reexportan.
#: Último día del descuento (incluido, hora local).
VENCE = QR_VENCE
#: Los únicos porcentajes que se pueden elegir.
PORCENTAJES = QR_PORCENTAJES
#: El 15 % pide al menos esto de ropa normal elegible, a precio de lista.
MINIMO_15 = QR_MINIMO_15
#: Si el carrito ya no llega al mínimo, el 15 % baja a esto.
PCT_SIN_MINIMO = Decimal("10")
#: Ropa normal: lo que NO es uniforme. «accesorio» no entra (calcetas y
#: corbatas escolares son de uniforme).
CATEGORIAS_ROPA_NORMAL = QR_CATEGORIAS_ROPA_NORMAL
#: Intentos equivocados seguidos antes de bloquear, y cuánto dura el bloqueo.
MAX_FALLOS = 3
MINUTOS_BLOQUEO = 5

# ─── Textos que ve la empleada ───────────────────────────────────────────

TXT_CODIGO_CONOCIDO = "Cambia el código del QR en Configuración"
TXT_SIN_CONEXION = "El QR de descuento necesita conexión"
TXT_VENCIDO = "El descuento de temporada terminó"
TXT_NO_VALIDO = "Ese QR de descuento no es válido."
TXT_SIN_EMPLEADA = "Escanea primero tu QR de empleada."
TXT_NO_MEJORA = "no mejora el descuento que ya tiene"
#: Sin el motor de beneficios (cálculo de respaldo) el QR no se cobra: es
#: una regla del motor, igual que sin conexión (QR_SIN_CONEXION).
TXT_SIN_MOTOR = "NO se aplicó: las reglas de descuento no respondieron"


def normalizar_categoria(categoria) -> str:
    """Como el motor: espacios de más fuera y en minúsculas."""
    return " ".join(str(categoria or "").split()).lower()


def es_ropa_normal(categoria, categorias: Iterable[str] = CATEGORIAS_ROPA_NORMAL) -> bool:
    return normalizar_categoria(categoria) in set(categorias)


# ─── El texto escaneado ──────────────────────────────────────────────────


def _limpio(raw) -> str:
    return "".join(c for c in str(raw or "") if c.isprintable()).strip()


def es_qr_descuento(raw) -> bool:
    """¿El texto escaneado es un QR de descuento? El escáner con teclado en
    español manda «'» en vez de «-» y puede cambiar mayúsculas: el prefijo se
    reconoce de las dos formas."""
    cabeza = _limpio(raw)[: len(PREFIJO)].replace("'", "-").upper()
    return cabeza == PREFIJO and len(_limpio(raw)) > len(PREFIJO)


def codigo_de(raw) -> str:
    """El código secreto (lo que va después del prefijo), tal como llegó."""
    texto = _limpio(raw)
    return texto[len(PREFIJO):].strip() if es_qr_descuento(texto) else ""


def _candidatos(codigo: str) -> list[str]:
    """El código tal cual y con el cambio del teclado español («'» → «-»)."""
    salida = [codigo]
    otro = codigo.replace("'", "-")
    if otro != codigo:
        salida.append(otro)
    return salida


# ─── Vencimiento ─────────────────────────────────────────────────────────


def fecha_local(momento: datetime | date | None = None) -> date:
    if momento is None:
        return datetime.now().date()
    if isinstance(momento, datetime):
        return (momento.astimezone() if momento.tzinfo else momento).date()
    return momento


def vencido(momento: datetime | date | None = None, *, vence: date = VENCE) -> bool:
    """True a partir del día siguiente a `vence` (hora local)."""
    return fecha_local(momento) > vence


# ─── Validar el código (con los candados) ────────────────────────────────

VALIDO = "valido"
CODIGO_CONOCIDO = "codigo_conocido"
NO_VALIDO = "no_valido"
#: La base dice que la temporada ya terminó (aunque el reloj de la máquina
#: diga otra cosa). No cuenta como intento equivocado.
VENCIDO = "vencido"


def _codigos_publicos() -> tuple[str, ...]:
    from pos_uniformes.services.manual_promo_service import (
        DEFAULT_PROMO_AUTHORIZATION_CODE,
        LEGACY_DEFAULT_PROMO_AUTHORIZATION_CODES,
    )

    return (DEFAULT_PROMO_AUTHORIZATION_CODE, *LEGACY_DEFAULT_PROMO_AUTHORIZATION_CODES)


def _verificar_por_omision(codigo: str, guardado: str) -> bool:
    from pos_uniformes.services.auth_service import AuthService

    return AuthService.verify_password(codigo, guardado)


def validar_contra_hash(
    codigo: str,
    hash_guardado: str | None,
    *,
    verificar: Callable[[str, str], bool] | None = None,
) -> str:
    """VALIDO, CODIGO_CONOCIDO o NO_VALIDO. Puro (sin base).

    - Un código de los que están en el repo público se rechaza aunque sea el
      que está guardado.
    - Sin hash guardado, la caja usaría el de fábrica: se rechaza igual."""
    verificar = verificar or _verificar_por_omision
    codigo = (codigo or "").strip()
    if not codigo:
        return NO_VALIDO
    publicos = _codigos_publicos()
    if any(c in publicos for c in _candidatos(codigo)):
        return CODIGO_CONOCIDO
    if not hash_guardado:
        return CODIGO_CONOCIDO
    if any(verificar(p, hash_guardado) for p in publicos):
        return CODIGO_CONOCIDO
    if any(verificar(c, hash_guardado) for c in _candidatos(codigo)):
        return VALIDO
    return NO_VALIDO


def hash_guardado(session) -> str | None:
    """El hash del «Codigo promo manual». Solo lee: no crea el de fábrica."""
    from sqlalchemy import select

    from pos_uniformes.database.models import ConfiguracionNegocio

    return session.scalar(select(ConfiguracionNegocio.promo_authorization_code_hash).limit(1))


def fecha_servidor(session) -> date | None:
    """La fecha de hoy según la base (revisión 2026-11-16: el reloj de la PC
    del kiosko se puede atrasar). None si no se pudo leer."""
    try:
        from sqlalchemy import func, select

        valor = session.scalar(select(func.current_date()))
    except Exception as exc:  # noqa: BLE001
        _logger.warning("QR de descuento: no se pudo leer la fecha de la base (%s)", type(exc).__name__)
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def vencido_segun_la_base(session, *, vence: date = VENCE) -> bool:
    hoy = fecha_servidor(session)
    return hoy is not None and hoy > vence


def validar_codigo(session, raw) -> str:
    """Valida el QR escaneado contra la Configuración de la caja. Antes, el
    vencimiento con la fecha de la base."""
    if vencido_segun_la_base(session):
        return VENCIDO
    return validar_contra_hash(codigo_de(raw), hash_guardado(session))


# ─── Intentos equivocados ────────────────────────────────────────────────


def ruta_intentos() -> Path:
    """Dónde se guarda la cuenta de intentos de esta máquina (solo la cuenta
    y la hora en que termina el bloqueo; nunca el código)."""
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / "descuento_qr_intentos.json"


class ContadorIntentos:
    """Tres códigos equivocados SEGUIDOS bloquean 5 minutos en esta máquina.
    Un código bueno reinicia la cuenta.

    Con `archivo`, la cuenta vive en disco: cerrar y abrir el POS o el
    kiosko no regala intentos (revisión 2026-11-16). Por eso el reloj es el
    de la pared, no el monotónico (que vuelve a cero al reiniciar). Si el
    archivo no se puede leer o escribir, se sigue con lo que hay en memoria:
    el contador nunca detiene la venta."""

    def __init__(self, *, max_fallos: int = MAX_FALLOS, minutos: float = MINUTOS_BLOQUEO,
                 reloj: Callable[[], float] = time.time,
                 archivo: Callable[[], Path] | None = None):
        self.max_fallos = max_fallos
        self.segundos = minutos * 60
        self._reloj = reloj
        self._archivo = archivo
        self._fallos = 0
        self._hasta: float | None = None
        self._lock = threading.Lock()

    # ─── Disco ───────────────────────────────────────────────────────────

    def _leer(self) -> None:
        if self._archivo is None:
            return
        try:
            ruta = Path(self._archivo())
            if not ruta.exists():
                self._fallos, self._hasta = 0, None
                return
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            self._fallos = max(0, int(datos.get("fallos") or 0))
            hasta = datos.get("hasta")
            self._hasta = float(hasta) if hasta is not None else None
        except Exception as exc:  # noqa: BLE001 — archivo dañado u ocupado
            _logger.warning("QR de descuento: no se pudo leer la cuenta de intentos (%s)", type(exc).__name__)

    def _guardar(self) -> None:
        if self._archivo is None:
            return
        try:
            ruta = Path(self._archivo())
            ruta.parent.mkdir(parents=True, exist_ok=True)
            tmp = ruta.with_name(ruta.name + ".tmp")
            tmp.write_text(json.dumps({"fallos": self._fallos, "hasta": self._hasta}), encoding="utf-8")
            os.replace(tmp, ruta)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("QR de descuento: no se pudo guardar la cuenta de intentos (%s)", type(exc).__name__)

    # ─── Cuenta ──────────────────────────────────────────────────────────

    def segundos_bloqueado(self) -> int:
        """0 si se puede intentar; si no, cuántos segundos faltan."""
        with self._lock:
            self._leer()
            if self._hasta is None:
                return 0
            falta = self._hasta - self._reloj()
            if falta <= 0:
                self._hasta = None
                self._fallos = 0
                self._guardar()
                return 0
            return int(falta + 0.999)

    def bloqueado(self) -> bool:
        return self.segundos_bloqueado() > 0

    def fallo(self) -> bool:
        """Anota un código equivocado. True si con este quedó bloqueado."""
        with self._lock:
            self._leer()
            self._fallos += 1
            bloqueado = self._fallos >= self.max_fallos
            if bloqueado:
                self._hasta = self._reloj() + self.segundos
            self._guardar()
            return bloqueado

    def exito(self) -> None:
        with self._lock:
            self._fallos = 0
            self._hasta = None
            self._guardar()


#: El de esta máquina (el kiosko y el POS corren un proceso cada uno; los
#: dos leen el mismo archivo si están en la misma PC).
CONTADOR = ContadorIntentos(archivo=lambda: ruta_intentos())


def texto_bloqueado(segundos: int) -> str:
    minutos = max(1, -(-int(segundos) // 60))
    return (
        "Demasiados QR de descuento equivocados seguidos. "
        f"Espera {minutos} min para volver a intentar."
    )


def rechazo_previo(*, hay_empleada: bool, en_linea: bool, momento=None,
                   contador: ContadorIntentos | None = None) -> str | None:
    """Lo que se revisa antes de ir a la base. None si se puede validar."""
    contador = contador or CONTADOR
    if not hay_empleada:
        return TXT_SIN_EMPLEADA
    if vencido(momento):
        return TXT_VENCIDO
    if not en_linea:
        return TXT_SIN_CONEXION
    segundos = contador.segundos_bloqueado()
    if segundos:
        return texto_bloqueado(segundos)
    return None


# ─── Elegir el % ─────────────────────────────────────────────────────────


def _dinero(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def base_elegible(lineas, categorias: Iterable[str] = CATEGORIAS_ROPA_NORMAL) -> Decimal:
    """Ropa normal a precio de lista (sin rebajas ni promo 3pz). Acepta
    `LineaEntrada` del motor o renglones del carrito (dict)."""
    categorias = set(categorias)
    total = Decimal("0.00")
    for l in lineas:
        if isinstance(l, dict):
            from pos_uniformes.services.beneficios_carrito import linea_desde_item

            if int(l.get("cantidad", 0) or 0) <= 0:
                continue
            l = linea_desde_item({"linea_uid": "00000000-0000-4000-8000-000000000000", **l})
        if l.rebaja is not None or l.promo_3pz or l.playera_3pz:
            continue
        if normalizar_categoria(l.categoria) not in categorias:
            continue
        total += l.precio_lista * l.cantidad
    return _dinero(total)


@dataclass(frozen=True)
class OpcionPct:
    pct: Decimal
    habilitada: bool
    razon: str = ""

    @property
    def texto(self) -> str:
        return f"{self.pct.normalize():f} %"


def opciones(base: Decimal, *, minimo_15: Decimal = MINIMO_15) -> list[OpcionPct]:
    """Los tres botones del diálogo; el 15 % deshabilitado (con su porqué)
    si no hay $600 de ropa normal."""
    salida = []
    for pct in PORCENTAJES:
        if pct == Decimal("15") and base < minimo_15:
            salida.append(OpcionPct(
                pct, False, f"15 % pide ${minimo_15:,.0f} de ropa normal (llevas ${base:,.2f})"
            ))
        else:
            salida.append(OpcionPct(pct, True))
    return salida


def texto_pct(pct) -> str:
    return f"{Decimal(str(pct)).normalize():f} %"


def texto_bajo_a_10(minimo_15: Decimal = MINIMO_15) -> str:
    return f"15 % pide ${minimo_15:,.0f} de ropa normal; se aplicó 10 %"


def texto_chip(pct_pedido, calculo=None, *, sin_motor: bool = False) -> str:
    """El chip de la venta para quitar el QR: «Descuento QR 10 % ✕».

    `sin_motor`: el motor no pudo calcular y la venta va con el cálculo de
    respaldo, que no conoce el QR. El chip lo dice para que la empleada no
    crea que el descuento está en el total (2026-11-19)."""
    if sin_motor:
        return f"Descuento QR {texto_pct(pct_pedido)} ({TXT_SIN_MOTOR})  ✕"
    pct = pct_pedido
    info = getattr(calculo, "descuento_qr", None) if calculo is not None else None
    if info is not None and info.pct > 0:
        pct = info.pct
    texto = f"Descuento QR {texto_pct(pct)}"
    razon = texto_motivo(getattr(info, "motivo", None))
    if not razon and info is not None and info.pct > 0 and not info.importe:
        # El mayoreo o la empleada ya dan lo mismo o más en esas piezas: el
        # QR no descontó nada y la cajera no debe creer que sí.
        razon = TXT_NO_MEJORA
    if razon:
        texto += f" ({razon})"
    return texto + "  ✕"


def texto_aviso_sin_motor(pct_pedido) -> str:
    """Lo que se suma al aviso «las reglas de descuento no pudieron
    calcular» cuando la venta lleva QR. El cálculo de respaldo no aplica el
    QR (es regla del motor, como sin conexión; 2026-11-19): se dice para
    que nadie le prometa a la clienta un descuento que no se cobró."""
    return (
        f"El descuento del QR ({texto_pct(pct_pedido)}) NO está en este total: sin las reglas de "
        "descuento el QR no se aplica. Cobra sin él o espera a que vuelvan."
    )


#: Los motivos del motor (`motivos.py`, 2026-11-16) en palabras de mostrador.
_TEXTO_MOTIVO = {
    "QR_15_A_10": texto_bajo_a_10(),
    "QR_VENCIDO": TXT_VENCIDO,
    "QR_SIN_CONEXION": TXT_SIN_CONEXION,
    "QR_SIN_LINEAS_ELEGIBLES": "aún no hay ropa normal en la venta",
}


def texto_motivo(motivo: str | None) -> str:
    return _TEXTO_MOTIVO.get(str(motivo or ""), "")
