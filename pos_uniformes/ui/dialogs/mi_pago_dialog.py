"""💼 Mi pago: la cuenta del pago del dueño (VEND-1), en el kiosko (2026-11-19).

Libreta del dueño → menú «💼 Caja ▾» → «💼 Mi pago». Solo VEND-1.

- Arriba, la tarjeta del PRÓXIMO pago (vino, como la cifra fuerte de «Hacer
  corte»): «3 de 4», la fecha, el monto grande, cuándo toca y «Ya me pagaron».
  Si hay atrasados, en su lugar va el atrasado más viejo («PAGO ATRASADO»).
  Debajo, tres fichas: último pago, días a favor y atrasados.
- Los pagos del mes (7, 14, 21 y 28): una tira con los cuatro por color y la
  navegación de mes como píldora (tocar un cuadro baja a su tarjeta); luego
  una tarjeta por pago con su estado y, solo si hay algo que desglosar, el
  desglose. También lleva tarjeta un pago de antes del inicio que sí se
  registró, para poder deshacerlo.
- Si no se pudo leer la base, lo dice y no abre la configuración (no se
  invita a sobrescribir la cuenta real con los valores por omisión).
- Los días de más con su destino, para cambiarlo.
- La configuración (monto, valor del día, fechas de pago e inicio), plegada:
  casi no se usa. Se abre sola si la cuenta no está configurada.

Es solo la cuenta: nada de esto sale del cajón ni toca el corte. La lógica
vive en `services/pago_dueno_service.py`; aquí solo se pinta y se pregunta.

También vive aquí `despues_de_marcar_dueno`, lo que el calendario del dueño
llama tras marcar un día suyo: si quedó un día de más, pregunta «¿Te lo
pagamos o te lo guardamos?».

Estética (Daniel, 2026-11-19: «mejoremos la estética»): los mismos colores
que «Hacer corte», el calendario y los avisos (vino #6b1f3a, crema, verde de
pagado, ámbar de pronto, rojo de atrasado).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services import pago_dueno_service as pd

logger = logging.getLogger(__name__)

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")

#: Un pago del mes que cae antes del inicio de la cuenta (y no se registró).
ANTES = "antes"

# Solo colores y formas, como `_ESTILO_CORTE`. Paleta: crema #f4ede2, tarjeta
# #fbf7f0, vino #6b1f3a; verde/ámbar/rojo de los avisos (avisos_bonitos).
_ESTILO = """
QDialog#miPago { background: #f4ede2; }
QDialog#miPago QLabel { color: #2c2a27; background: transparent; }
QDialog#miPago QScrollArea { background: transparent; border: none; }
QDialog#miPago QScrollArea > QWidget > QWidget { background: transparent; }

QDialog#miPago QLabel#miPagoEncabezado { font-size: 22px; font-weight: 800; color: #2c2a27; }
QFrame#miPagoPie { background: #efe6d8; border: none; border-top: 1px solid #e6dccb; }
QDialog#miPago QLabel#miPagoNota { color: #6f665c; font-size: 12px; }
QDialog#miPago QLabel#miPagoMesResumen { color: #6f665c; font-size: 12px; font-weight: 700; }
QDialog#miPago QLabel#miPagoMesResumen[completo="true"] { color: #2f7d4f; }
QDialog#miPago QLabel#miPagoSeccion { color: #7b2d14; font-size: 12px; font-weight: 800; letter-spacing: 1px; }
QDialog#miPago QLabel#miPagoAviso { background: #fbefd5; color: #8a5600; border-radius: 10px;
                                    padding: 8px 12px; font-size: 13px; font-weight: 600; }

QFrame#miPagoHeroe { background: #6b1f3a; border: none; border-radius: 16px; }
QDialog#miPago QFrame#miPagoHeroe QLabel { color: #ffffff; }
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoHeroeKicker { color: #e9cfd6; font-size: 11px; font-weight: 800; letter-spacing: 1px; }
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoHeroeTitulo { font-size: 17px; font-weight: 800; }
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoHeroeMonto { font-size: 36px; font-weight: 800; }
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoHeroePie { color: #ecd7dd; font-size: 13px; }
/* «Cuándo toca»: los mismos colores que la tira (toca hoy = vino, aquí al
   revés porque el fondo ya es vino; nunca verde, que es «pagado»). */
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoCuando { border-radius: 11px; padding: 4px 12px; font-size: 12px; font-weight: 800; }
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoCuando[tono="hoy"] { background: #ffffff; color: #6b1f3a; }
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoCuando[tono="pronto"] { background: #fbefd5; color: #8a5600; }
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoCuando[tono="luego"] { background: #84405a; color: #ffffff; }
QDialog#miPago QFrame#miPagoHeroe QLabel#miPagoCuando[tono="atrasado"] { background: #f8e1df; color: #b3261e; }
QDialog#miPago QFrame#miPagoHeroe QPushButton#miPagoHeroeBoton { background: #ffffff; color: #6b1f3a; border: none;
    border-radius: 12px; min-height: 48px; padding: 0 20px; font-size: 15px; font-weight: 800; }
QDialog#miPago QFrame#miPagoHeroe QPushButton#miPagoHeroeBoton:pressed { background: #f1e3e8; }

QFrame#miPagoVacio { background: #fbf7f0; border: 1.5px dashed #d9cdb8; border-radius: 16px; }
QDialog#miPago QLabel#miPagoVacioTitulo { font-size: 17px; font-weight: 800; color: #6b1f3a; }

QFrame#miPagoFicha { background: #fbf7f0; border: 1px solid #e6dccb; border-radius: 12px; }
QDialog#miPago QLabel#miPagoFichaTitulo { color: #6f665c; font-size: 11px; font-weight: 800; letter-spacing: 1px; }
QDialog#miPago QLabel#miPagoFichaValor { font-size: 18px; font-weight: 800; }
QDialog#miPago QLabel#miPagoFichaValor[alerta="true"] { color: #b3261e; }
QDialog#miPago QLabel#miPagoFichaPie { color: #6f665c; font-size: 12px; }

QFrame#miPagoMesNav { background: #ffffff; border: 1px solid #ddd0c0; border-radius: 22px; }
QDialog#miPago QFrame#miPagoMesNav QPushButton { background: transparent; color: #6b1f3a; border: none;
    border-radius: 18px; min-height: 36px; max-height: 36px; min-width: 36px; max-width: 36px;
    padding: 0; font-size: 16px; font-weight: 800; }
QDialog#miPago QFrame#miPagoMesNav QPushButton:pressed { background: #f1e3e8; }
QDialog#miPago QLabel#miPagoMes { font-size: 14px; font-weight: 800; color: #2c2a27; }

QFrame#miPagoPaso { border-radius: 12px; border: 1px solid transparent; }
QFrame#miPagoPaso[estado="pagado"] { background: #e3f1e6; border-color: #c4e0cb; }
QFrame#miPagoPaso[estado="toca_hoy"] { background: #6b1f3a; }
QFrame#miPagoPaso[estado="pendiente"] { background: #ffffff; border-color: #ddd0c0; }
QFrame#miPagoPaso[estado="atrasado"] { background: #f8e1df; border-color: #efc2bd; }
QFrame#miPagoPaso[estado="antes"] { background: #efe8dd; border: 1px dashed #d9cdb8; }
QFrame#miPagoPaso[destacado="true"] { border: 2px solid #6b1f3a; }
QDialog#miPago QLabel#miPagoPasoNumero { font-size: 20px; font-weight: 800; }
QDialog#miPago QLabel#miPagoPasoFecha { font-size: 12px; font-weight: 700; }
QDialog#miPago QLabel#miPagoPasoEstado { font-size: 11px; font-weight: 800; }
QDialog#miPago QFrame#miPagoPaso[estado="pagado"] QLabel { color: #2f7d4f; }
QDialog#miPago QFrame#miPagoPaso[estado="toca_hoy"] QLabel { color: #ffffff; }
QDialog#miPago QFrame#miPagoPaso[estado="pendiente"] QLabel { color: #5f564c; }
QDialog#miPago QFrame#miPagoPaso[estado="atrasado"] QLabel { color: #b3261e; }
QDialog#miPago QFrame#miPagoPaso[estado="antes"] QLabel { color: #8a8177; }
QDialog#miPago QFrame#miPagoPaso[estado="antes"] QLabel#miPagoPasoNumero { color: #a59a8c; }

QFrame#miPagoCard { background: #fbf7f0; border: 1px solid #e6dccb; border-radius: 12px; }
QFrame#miPagoCard[estado="atrasado"] { background: #fdf4f2; border-color: #efc2bd; }
QDialog#miPago QLabel#miPagoTitulo { font-size: 15px; font-weight: 800; }
QDialog#miPago QLabel#miPagoMonto { font-size: 18px; font-weight: 800; }
QDialog#miPago QLabel#miPagoCubre { color: #6f665c; font-size: 13px; }
QFrame#miPagoRecibo { background: #f4ede2; border: none; border-radius: 10px; }
QDialog#miPago QLabel#miPagoRenglon { color: #5f564c; font-size: 13px; }
QDialog#miPago QLabel#miPagoRenglonMonto { color: #2c2a27; font-size: 13px; font-weight: 700; }
QDialog#miPago QLabel#miPagoRenglonMonto[clase="suma"] { color: #2f7d4f; }
QDialog#miPago QLabel#miPagoRenglonMonto[clase="resta"] { color: #b3261e; }
QDialog#miPago QLabel#miPagoRenglonMonto[clase="nota"] { color: #6f665c; font-weight: 600; }

QDialog#miPago QLabel#miPagoEstado { border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 800; }
QDialog#miPago QLabel#miPagoEstado[estado="pagado"] { background: #e3f1e6; color: #2f7d4f; }
QDialog#miPago QLabel#miPagoEstado[estado="toca_hoy"] { background: #6b1f3a; color: #ffffff; }
QDialog#miPago QLabel#miPagoEstado[estado="pendiente"] { background: #ece6dc; color: #5f564c; }
QDialog#miPago QLabel#miPagoEstado[estado="atrasado"] { background: #f8e1df; color: #b3261e; }
QDialog#miPago QLabel#miPagoEstado[estado="sin_decidir"] { background: #fbefd5; color: #8a5600; }
QDialog#miPago QLabel#miPagoEstado[estado="pagar"] { background: #e3f1e6; color: #2f7d4f; }
QDialog#miPago QLabel#miPagoEstado[estado="acumular"] { background: #f1e3e8; color: #6b1f3a; }

QDialog#miPago QPushButton { background: #ffffff; color: #6b1f3a; border: 1.5px solid #d9cdb8; border-radius: 10px;
                             min-height: 40px; padding: 0 16px; font-size: 13px; font-weight: 700; }
QDialog#miPago QPushButton:pressed { background: #f1e6d6; border-color: #6b1f3a; }
QDialog#miPago QPushButton:disabled { color: #b5aa9c; background: #f4eee4; border-color: #e6dccd; }
QDialog#miPago QPushButton#miPagoPrimario { background: #6b1f3a; color: #ffffff; border: none; }
QDialog#miPago QPushButton#miPagoPrimario:pressed { background: #561730; }
QDialog#miPago QPushButton#miPagoPrimario:disabled { background: #d8c3ca; color: #f8f2f4; }
QDialog#miPago QPushButton#miPagoChico { min-height: 40px; padding: 0 14px; font-size: 13px; border-radius: 10px; }
QDialog#miPago QPushButton#miPagoSegmento { min-height: 40px; padding: 0 10px; font-size: 12px; border-radius: 10px; }
QDialog#miPago QPushButton#miPagoSegmento:disabled { background: #6b1f3a; color: #ffffff; border-color: #6b1f3a; }
/* Deshacer: una acción que borra no se parece a «Ya me pagaron». */
QDialog#miPago QPushButton#miPagoDeshacer { background: transparent; border: none; color: #6f665c;
    text-decoration: underline; font-size: 12px; font-weight: 600; padding: 0 6px; }
QDialog#miPago QPushButton#miPagoDeshacer:pressed { color: #b3261e; background: transparent; }
QDialog#miPago QPushButton#miPagoPlegable { background: transparent; color: #6b1f3a; border: none; text-align: left;
                                            padding: 6px 2px; font-size: 15px; font-weight: 800; }
QDialog#miPago QLabel#miPagoExtraFecha { font-size: 14px; font-weight: 800; }

QDialog#miPago QDoubleSpinBox, QDialog#miPago QDateEdit, QDialog#miPago QLineEdit#miPagoCampo {
    background: #ffffff; color: #2c2a27; border: 1px solid #d9cdb8; border-radius: 10px;
    padding: 4px 10px; min-height: 34px; font-size: 14px; }
QDialog#miPago QDoubleSpinBox:focus, QDialog#miPago QDateEdit:focus, QDialog#miPago QLineEdit#miPagoCampo:focus {
    border: 2px solid #6b1f3a; }
QDialog#miPago QDateEdit::drop-down { border: none; width: 28px; }
/* Sin flechitas: con borde por hoja de estilos y sin esto, Qt deja el campo
   de texto del spinbox de 1 px de ancho y no se ve la cifra. */
QDialog#miPago QDoubleSpinBox::up-button { subcontrol-origin: border; width: 0px; border: none; }
QDialog#miPago QDoubleSpinBox::down-button { width: 0px; border: none; }
QDialog#miPago QCheckBox { color: #2c2a27; font-size: 13px; spacing: 10px; }
QDialog#miPago QCheckBox::indicator { width: 18px; height: 18px; border: 1.5px solid #d9cdb8;
                                      border-radius: 5px; background: #ffffff; }
QDialog#miPago QCheckBox::indicator:checked { background: #6b1f3a; border-color: #6b1f3a; }
QDialog#miPago QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QDialog#miPago QScrollBar::handle:vertical { background: #d9cdb8; border-radius: 3px; min-height: 40px; }
QDialog#miPago QScrollBar::add-line:vertical, QDialog#miPago QScrollBar::sub-line:vertical { height: 0px; }
QDialog#miPago QScrollBar::add-page:vertical, QDialog#miPago QScrollBar::sub-page:vertical { background: none; }
"""

ESTADOS_TEXTO = {
    pd.PAGADO: "Pagado",
    pd.TOCA_HOY: "Toca hoy",
    pd.PENDIENTE: "Pendiente",
    pd.ATRASADO: "Atrasado",
}

#: Lo que dice cada cuadro de la tira del mes.
PASO_TEXTO = {
    pd.PAGADO: "✓ Pagado",
    pd.TOCA_HOY: "Toca hoy",
    pd.PENDIENTE: "Pendiente",
    pd.ATRASADO: "Atrasado",
    ANTES: "Antes de la cuenta",
}

DESTINO_TEXTO = {
    pd.PAGAR: "Se paga en su pago",
    pd.ACUMULAR: "Guardado a favor",
}

_MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


# ─── Textos y cuentas de pantalla (puros, probados) ──────────────────────


def _dias(n: int) -> str:
    return f"{n} día" if n == 1 else f"{n} días"


def _faltas(n: int) -> str:
    return f"{n} falta" if n == 1 else f"{n} faltas"


def _fechas(fechas: list[date]) -> str:
    return ", ".join(pd.fecha_corta(f) for f in fechas)


TEXTO_SIN_DESCANSO = (
    "⚠ Tu descanso fijo no está guardado en el calendario, así que no se cuentan "
    "días de más. Guárdalo (martes) en tu horario del calendario."
)


def titulo_pago(p: pd.DesglosePago) -> str:
    """'3 de 4 · sáb 21-nov'."""
    return f"{p.etiqueta} · {pd.fecha_corta(p.fecha_programada, con_dia=True)}"


def texto_estado(p: pd.DesglosePago, hoy: date) -> str:
    """El chip: 'Pagado el 19-nov', 'Toca hoy', 'Pendiente' o 'Atrasado'.
    (El monto ya va en grande en la tarjeta.)"""
    estado = p.estado(hoy)
    if estado == pd.PAGADO and p.registro is not None:
        return f"Pagado el {pd.fecha_corta(p.registro.fecha_pago)}"
    return ESTADOS_TEXTO[estado]


def _dia_mes(f: date) -> str:
    """'7-nov' (sin cero a la izquierda, como se dice en la tienda)."""
    return f"{f.day}-{_MESES_CORTOS[f.month - 1]}"


def rango_corto(desde: date, hasta: date) -> str:
    """'del 1 al 7-nov' (mismo mes) o 'del 29-oct al 7-nov'."""
    if (desde.year, desde.month) == (hasta.year, hasta.month):
        return f"del {desde.day} al {_dia_mes(hasta)}"
    return f"del {_dia_mes(desde)} al {_dia_mes(hasta)}"


def texto_cubre(p: pd.DesglosePago) -> str:
    """'Cubre del 15 al 21-nov'."""
    return f"Cubre {rango_corto(p.desde, p.hasta)}"


def monto_de_la_tarjeta(p: pd.DesglosePago) -> Decimal:
    """La cifra grande: lo que de verdad se pagó si ya está registrado; si no,
    lo calculado."""
    if p.pagado and p.registro is not None:
        return p.registro.monto
    return p.monto


@dataclass(frozen=True)
class Renglon:
    """Un renglón del desglose: texto a la izquierda, cifra a la derecha.
    `clase`: 'base', 'suma', 'resta' o 'nota' (gris, no cambia el total)."""

    texto: str
    cifra: str
    clase: str


def renglones_desglose(p: pd.DesglosePago) -> list[Renglon]:
    """El desglose de un pago, en palabras de la tienda. Vacío si no hay nada
    que desglosar (base sola, pagado lo calculado): entonces basta «Cubre…»."""
    r: list[Renglon] = []
    if p.dias_extra_pagados:
        n = len(p.dias_extra_pagados)
        r.append(Renglon(f"+ {_dias(n)} de más ({_fechas(p.dias_extra_pagados)})",
                         f"+{pd.dinero_texto(p.monto_extra)}", "suma"))
    if p.faltas_descontadas:
        n = len(p.faltas_descontadas)
        r.append(Renglon(f"− {_faltas(n)} ({_fechas(p.faltas_descontadas)})",
                         f"−{pd.dinero_texto(p.descuento_faltas)}", "resta"))
    if p.faltas_cubiertas:
        r.append(Renglon(f"Falta cubierta con día a favor ({_fechas(p.faltas_cubiertas)})",
                         "no se descuenta", "nota"))
    guardados = [f for f in p.dias_extra_acumulados if f not in p.dias_extra_sin_decidir]
    if guardados:
        r.append(Renglon(f"Día de más guardado ({_fechas(guardados)})", "a favor", "nota"))
    if p.dias_extra_sin_decidir:
        r.append(Renglon(f"Día de más sin decidir ({_fechas(p.dias_extra_sin_decidir)})",
                         "se guarda", "nota"))
    pagado = monto_de_la_tarjeta(p)
    if pagado != p.monto:
        # Lo que de verdad se pagó no es lo calculado (monto editado, o algo
        # cambió después de registrarlo): se ven las dos cifras.
        r.append(Renglon("Calculado", pd.dinero_texto(p.monto), "nota"))
        r.append(Renglon("Pagado", pd.dinero_texto(pagado), "base"))
    if r:
        r.insert(0, Renglon("Base", pd.dinero_texto(p.base), "base"))
    return r


def resumen_ajustes(p: pd.DesglosePago) -> str:
    """Lo que mueve el monto, en una línea: '+1 día de más · 1 falta (−$385)'."""
    partes = []
    if p.dias_extra_pagados:
        partes.append(f"+{_dias(len(p.dias_extra_pagados))} de más")
    if p.faltas_descontadas:
        partes.append(f"{_faltas(len(p.faltas_descontadas))} (−{pd.dinero_texto(p.descuento_faltas)})")
    if p.faltas_cubiertas:
        n = len(p.faltas_cubiertas)
        partes.append(f"{_faltas(n)} cubierta" + ("s" if n != 1 else ""))
    return " · ".join(partes)


def tono_cuando_toca(dias_faltan: int) -> str:
    """El color del chip «cuándo toca»: 'hoy' (blanco con letra vino, como el
    cuadro vino de la tira), 'pronto' (ámbar, en 1 a 3 días) o 'luego'."""
    if dias_faltan <= 0:
        return "hoy"
    if dias_faltan <= 3:
        return "pronto"
    return "luego"


@dataclass(frozen=True)
class Paso:
    """Un cuadro de la tira del mes."""

    numero: int
    fecha: date
    estado: str   # pagado / toca_hoy / pendiente / atrasado / antes


def pasos_del_mes(
    dias_de_pago: tuple[int, ...], year: int, month: int, pagos: list[pd.DesglosePago],
    registradas: set[date], hoy: date,
) -> list[Paso]:
    """Los pagos del mes (los 4) con su estado. Uno antes del inicio de la
    cuenta sale «antes», salvo que se haya registrado (el 14-nov pagado el
    19-nov con la cuenta arrancando el 19)."""
    por_fecha = {p.fecha_programada: p for p in pagos}
    pasos = []
    for i, dia in enumerate(sorted(dias_de_pago), start=1):
        f = date(year, month, dia)
        p = por_fecha.get(f)
        if p is not None:
            estado = p.estado(hoy)
        elif f in registradas:
            estado = pd.PAGADO
        else:
            estado = ANTES
        pasos.append(Paso(i, f, estado))
    return pasos


def resumen_del_mes(pasos: list[Paso]) -> tuple[str, bool]:
    """Junto al título: ('2 de 4 pagados', False) o ('✓ Todos pagados', True).
    No cuenta los de antes del inicio de la cuenta."""
    cuentan = [p for p in pasos if p.estado != ANTES]
    if not cuentan:
        return "", False
    pagados = sum(1 for p in cuentan if p.estado == pd.PAGADO)
    if pagados == len(cuentan):
        return "✓ Todos pagados", True
    return f"{pagados} de {len(cuentan)} pagados", False


def estado_dia_extra(e: pd.DiaExtra) -> str:
    """'sin_decidir', 'pagar' o 'acumular' (para el chip)."""
    return "sin_decidir" if e.sin_decidir else e.destino


def texto_dia_extra(e: pd.DiaExtra, pago: date | None = None) -> str:
    """El chip del destino. Con `pago` (la fecha del pago que lo cubre), el de
    «págamelo» dice cuándo: «Se paga el 14-nov»."""
    if e.sin_decidir:
        return "Sin decidir · se guarda"
    if e.destino == pd.PAGAR and pago is not None:
        return f"Se paga el {_dia_mes(pago)}"
    return DESTINO_TEXTO[e.destino]


def texto_ultimo_pago(registros: dict[date, pd.RegistroPago]) -> tuple[str, str]:
    """La ficha «Último pago»: ('19-nov', 'fue el pago del 14-nov') si se
    pagó otro día que el programado; si no, el pie de siempre."""
    if not registros:
        return "Ninguno", "todavía no se registra ninguno"
    r = max(registros.values(), key=lambda x: (x.fecha_pago, x.fecha_programada))
    if r.fecha_pago != r.fecha_programada:
        return pd.fecha_corta(r.fecha_pago), f"fue el pago del {_dia_mes(r.fecha_programada)}"
    return pd.fecha_corta(r.fecha_pago), "la última vez que te pagaron"


def pago_de_la_tarjeta_grande(rec: pd.Recordatorio) -> pd.DesglosePago:
    """El pago que va arriba: el atrasado más viejo si hay; si no, el próximo."""
    if rec.atrasados:
        return min(rec.atrasados, key=lambda p: p.fecha_programada)
    return rec.proximo


def texto_atraso(dias: int) -> str:
    """'Atrasado 1 día' / 'Atrasado 5 días'."""
    return f"Atrasado {_dias(max(1, dias))}"


def leer_dias_de_pago(texto: str) -> tuple[int, ...]:
    """'7, 14, 21, 28' → (7, 14, 21, 28). ValueError si algo no es un día válido."""
    partes = [t for t in texto.replace(";", ",").replace(" ", ",").split(",") if t.strip()]
    try:
        dias = [int(t) for t in partes]
    except ValueError as exc:
        raise ValueError("Las fechas de pago son números del 1 al 28, separados por comas.") from exc
    return pd.dias_de_pago_validos(dias)


def _mes_siguiente(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def _qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _de_qdate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


def _sesion():
    from pos_uniformes.database.connection import get_session

    return get_session()


def _label(texto: str, nombre: str, *, wrap: bool = False) -> QLabel:
    lbl = QLabel(texto)
    lbl.setObjectName(nombre)
    lbl.setWordWrap(wrap)
    return lbl


def _repulir(w: QWidget) -> None:
    """Vuelve a aplicar la hoja de estilos tras cambiar una propiedad."""
    w.style().unpolish(w)
    w.style().polish(w)


def _dinero_spin(valor: Decimal, maximo: float) -> QDoubleSpinBox:
    """Sin flechitas, como en «Hacer corte»: se escribe."""
    s = QDoubleSpinBox()
    s.setRange(0, maximo)
    s.setDecimals(2)
    s.setPrefix("$ ")
    s.setGroupSeparatorShown(True)
    s.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    s.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    s.setValue(float(valor))
    s.lineEdit().setTextMargins(6, 0, 6, 0)
    return s


# ─── Pregunta del calendario ─────────────────────────────────────────────


def preguntar_destino(parent: QWidget | None, fecha: date, valor_dia: Decimal, actual: str | None) -> str | None:
    """«¿Te lo pagamos o te lo guardamos?» → 'pagar' / 'acumular' / None (luego)."""
    caja = QMessageBox(parent)
    caja.setIcon(QMessageBox.Icon.Question)
    caja.setWindowTitle("Día de más")
    caja.setText(
        f"Trabajaste el {pd.fecha_corta(fecha, con_dia=True)} en tu descanso.\n\n"
        "¿Te lo pagamos o te lo guardamos?\n\n"
        f"Págamelo: suma {pd.dinero_texto(valor_dia)} a tu pago de esa semana.\n"
        "Guárdamelo: queda como un día a favor para cubrir una falta."
    )
    pagar = caja.addButton("💵 Págamelo", QMessageBox.ButtonRole.AcceptRole)
    guardar = caja.addButton("📦 Guárdamelo", QMessageBox.ButtonRole.AcceptRole)
    luego = caja.addButton("Luego", QMessageBox.ButtonRole.RejectRole)
    caja.setDefaultButton(pagar if actual == pd.PAGAR else guardar)
    caja.setEscapeButton(luego)
    caja.exec()
    elegido = caja.clickedButton()
    if elegido is pagar:
        return pd.PAGAR
    if elegido is guardar:
        return pd.ACUMULAR
    return None


def despues_de_marcar_dueno(
    parent: QWidget | None, fecha: date, tipo: str, *, session_factory=None, preguntar=None,
) -> str | None:
    """Lo que hace el calendario del dueño tras marcar o quitar un día SUYO.

    1. Borra las decisiones que quedaron sin día de más (se quitó la marca o
       se movió el descanso): así no revive un «págamelo» viejo.
    2. Si marcó «Sí trabajó» y el día es de más, pregunta y guarda.

    Devuelve el destino guardado, o None. Nunca rompe el calendario."""
    from pos_uniformes.services.calendario_empleadas_service import TRABAJO

    sf = session_factory or _sesion
    try:
        with sf() as session:
            pd.limpiar_decisiones_huerfanas(session)
            if tipo != TRABAJO or not pd.es_dia_extra(session, fecha):
                return None
            actual = pd.decision_dia_extra(session, fecha)
            config = pd.cargar_config(session)
            valor_dia = config.valor_dia if config is not None else pd.VALOR_DIA_DEFAULT
    except Exception:  # noqa: BLE001 — la marca ya quedó; la cuenta es aparte
        logger.exception("Mi pago: no se pudo revisar el día de más")
        return None
    destino = (preguntar or preguntar_destino)(parent, fecha, valor_dia, actual)
    if destino is None:
        return None
    try:
        with sf() as session:
            pd.decidir_dia_extra(session, fecha, destino)
    except Exception:  # noqa: BLE001
        logger.exception("Mi pago: no se guardó el destino del día de más")
        QMessageBox.warning(parent, "No se guardó", "No se guardó si se paga o se guarda. Cámbialo en 💼 Mi pago.")
        return None
    return destino


# ─── El diálogo ──────────────────────────────────────────────────────────


class _CuadroPaso(QFrame):
    """Un cuadro de la tira: al tocarlo, baja a la tarjeta de su pago."""

    def __init__(self, al_tocar):
        super().__init__()
        self._al_tocar = al_tocar
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self._al_tocar()
        super().mouseReleaseEvent(event)


class _YaMePagaronDialog(QDialog):
    """Fecha real y monto (el calculado por omisión)."""

    def __init__(self, parent: QWidget | None, p: pd.DesglosePago, hoy: date):
        super().__init__(parent)
        self.setObjectName("miPago")
        self.setStyleSheet(_ESTILO)
        self.setWindowTitle("Ya me pagaron")
        ly = QVBoxLayout(self)
        ly.setContentsMargins(22, 18, 22, 16)
        ly.setSpacing(12)
        ly.addWidget(_label(f"Pago {titulo_pago(p)}", "miPagoEncabezado"))
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.fecha = QDateEdit(_qdate(hoy))
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setMaximumDate(_qdate(hoy))      # no se apunta un pago que no ha pasado
        form.addRow("¿Qué día te pagaron?", self.fecha)
        self.monto = _dinero_spin(p.monto, 1_000_000)
        form.addRow("¿Cuánto?", self.monto)
        ly.addLayout(form)
        ly.addWidget(_label(
            f"Lo calculado es {pd.dinero_texto(p.monto)}. Es solo la cuenta: no sale del cajón.",
            "miPagoNota", wrap=True,
        ))
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok = botones.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Guardar")
        ok.setObjectName("miPagoPrimario")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        ly.addWidget(botones)

    def valores(self) -> tuple[date, Decimal]:
        return _de_qdate(self.fecha.date()), Decimal(str(self.monto.value())).quantize(Decimal("0.01"))


class MiPagoDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, quien: str = pd.EMPLOYEE_CODE,
                 session_factory=None, hoy: date | None = None):
        super().__init__(parent)
        self.setObjectName("miPago")
        self.setWindowTitle("💼 Mi pago")
        self.setStyleSheet(_ESTILO)
        self.resize(780, 820)
        self._quien = str(quien or "").strip().upper()
        self._sf = session_factory or _sesion
        self._hoy = hoy or date.today()
        self._year, self._month = self._hoy.year, self._hoy.month
        self._config: pd.ConfigPagoDueno | None = None
        self._rec: pd.Recordatorio | None = None
        self.pagos: list[pd.DesglosePago] = []
        self.extras: list[pd.DiaExtra] = []
        self._registradas: set[date] = set()
        self._datos: pd.DatosPagoDueno | None = None
        self._config_pintada = False   # la configuración guardada ya está en los campos
        self._carga_ok = False         # la última lectura de la base salió bien
        self._cargo_alguna_vez = False

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        self._cuerpo = QWidget()
        self._ly = QVBoxLayout(self._cuerpo)
        self._ly.setContentsMargins(22, 18, 22, 12)
        self._ly.setSpacing(12)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(self._cuerpo)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._area = area
        raiz.addWidget(area, 1)

        # Encabezado.
        self._ly.addWidget(_label("💼 Mi pago", "miPagoEncabezado"))
        self._ly.addWidget(_label(
            "Es solo la cuenta de tu pago: no sale del cajón ni cambia el corte.", "miPagoNota", wrap=True,
        ))
        self.aviso_descanso = _label(TEXTO_SIN_DESCANSO, "miPagoAviso", wrap=True)
        self.aviso_descanso.setVisible(False)
        self._ly.addWidget(self.aviso_descanso)

        # El próximo pago (o «sin configurar») y las tres fichas.
        self._ly.addWidget(self._armar_heroe())
        self.vacio_config = self._armar_vacio()
        self._ly.addWidget(self.vacio_config)
        self.fichas = QWidget()
        fichas = QHBoxLayout(self.fichas)
        fichas.setContentsMargins(0, 0, 0, 0)
        fichas.setSpacing(10)
        self.stat_ultimo = self._ficha(fichas, "ÚLTIMO PAGO")
        self.stat_favor = self._ficha(fichas, "DÍAS A FAVOR")
        self.stat_atrasados = self._ficha(fichas, "ATRASADOS")
        self._ly.addWidget(self.fichas)

        # Pagos del mes: título, píldora de mes, tira y tarjetas.
        self.seccion_pagos = QWidget()
        sp = QVBoxLayout(self.seccion_pagos)
        sp.setContentsMargins(0, 8, 0, 0)
        sp.setSpacing(10)
        cabeza = QHBoxLayout()
        cabeza.setSpacing(10)
        cabeza.addWidget(_label("PAGOS DEL MES", "miPagoSeccion"))
        self.mes_resumen = _label("", "miPagoMesResumen")
        cabeza.addWidget(self.mes_resumen)
        cabeza.addStretch(1)
        cabeza.addWidget(self._armar_nav_mes())
        sp.addLayout(cabeza)
        self._tira_box = QHBoxLayout()
        self._tira_box.setSpacing(8)
        sp.addLayout(self._tira_box)
        self._pagos_box = QVBoxLayout()
        self._pagos_box.setSpacing(8)
        sp.addLayout(self._pagos_box)
        self._ly.addWidget(self.seccion_pagos)

        # Días de más.
        self.seccion_extras = QWidget()
        se = QVBoxLayout(self.seccion_extras)
        se.setContentsMargins(0, 8, 0, 0)
        se.setSpacing(8)
        cab = QHBoxLayout()
        cab.addWidget(_label("DÍAS DE MÁS", "miPagoSeccion"))
        cab.addStretch(1)
        self.extras_nota = _label("", "miPagoNota")
        cab.addWidget(self.extras_nota)
        se.addLayout(cab)
        extras_card = QFrame()
        extras_card.setObjectName("miPagoCard")
        self._extras_box = QVBoxLayout(extras_card)
        self._extras_box.setContentsMargins(14, 6, 14, 6)
        self._extras_box.setSpacing(0)
        se.addWidget(extras_card)
        self._ly.addWidget(self.seccion_extras)

        # Configuración, plegada.
        self.btn_config = QPushButton("")
        self.btn_config.setObjectName("miPagoPlegable")
        self.btn_config.setAutoDefault(False)
        self.btn_config.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_config.clicked.connect(lambda: self._mostrar_config(self.config_box.isHidden()))
        self._ly.addWidget(self.btn_config)
        self.config_box = self._seccion_config()
        self._ly.addWidget(self.config_box)
        self._ly.addStretch(1)

        pie_w = QFrame()
        pie_w.setObjectName("miPagoPie")
        pie = QHBoxLayout(pie_w)
        pie.setContentsMargins(22, 10, 22, 12)
        self.status = _label("", "miPagoNota", wrap=True)
        pie.addWidget(self.status, 1)
        cerrar = QPushButton("Cerrar")
        cerrar.setAutoDefault(False)
        cerrar.setMinimumWidth(110)
        cerrar.clicked.connect(self.accept)
        pie.addWidget(cerrar)
        raiz.addWidget(pie_w)
        self.recargar(pintar_config=True)
        # Plegada: casi no se usa. Abierta si no hay cuenta que llevar (y solo
        # si se pudo leer: sin conexión no se invita a sobrescribirla).
        self._mostrar_config(self._carga_ok and (self._config is None or not self._config.vigente))

    # ── armado ──
    def _armar_heroe(self) -> QFrame:
        self.heroe = QFrame()
        self.heroe.setObjectName("miPagoHeroe")
        ly = QHBoxLayout(self.heroe)
        ly.setContentsMargins(22, 18, 22, 18)
        ly.setSpacing(16)
        izq = QVBoxLayout()
        izq.setSpacing(3)
        self.heroe_kicker = _label("PRÓXIMO PAGO", "miPagoHeroeKicker")
        izq.addWidget(self.heroe_kicker)
        self.heroe_titulo = _label("", "miPagoHeroeTitulo")
        izq.addWidget(self.heroe_titulo)
        self.heroe_monto = _label("", "miPagoHeroeMonto")
        izq.addWidget(self.heroe_monto)
        self.heroe_pie = _label("", "miPagoHeroePie", wrap=True)
        izq.addWidget(self.heroe_pie)
        ly.addLayout(izq, 1)
        der = QVBoxLayout()
        der.setSpacing(10)
        self.heroe_cuando = _label("", "miPagoCuando")
        der.addWidget(self.heroe_cuando, 0, Qt.AlignmentFlag.AlignRight)
        der.addStretch(1)
        self.btn_heroe = QPushButton("💵 Ya me pagaron")
        self.btn_heroe.setObjectName("miPagoHeroeBoton")
        self.btn_heroe.setAutoDefault(False)
        self.btn_heroe.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_heroe.clicked.connect(lambda: self._rec and self._ya_me_pagaron(self.pago_heroe()))
        der.addWidget(self.btn_heroe, 0, Qt.AlignmentFlag.AlignRight)
        ly.addLayout(der)
        return self.heroe

    def _armar_vacio(self) -> QFrame:
        caja = QFrame()
        caja.setObjectName("miPagoVacio")
        ly = QVBoxLayout(caja)
        ly.setContentsMargins(22, 18, 22, 18)
        ly.setSpacing(4)
        self.vacio_titulo = _label("Tu cuenta todavía no está configurada", "miPagoVacioTitulo", wrap=True)
        ly.addWidget(self.vacio_titulo)
        self.vacio_texto = _label(
            "Pon abajo el monto de cada pago y el día en que empieza la cuenta, y guarda.",
            "miPagoNota", wrap=True,
        )
        ly.addWidget(self.vacio_texto)
        return caja

    @staticmethod
    def _ficha(fila: QHBoxLayout, titulo: str) -> QLabel:
        caja = QFrame()
        caja.setObjectName("miPagoFicha")
        ly = QVBoxLayout(caja)
        ly.setContentsMargins(14, 10, 14, 10)
        ly.setSpacing(2)
        ly.addWidget(_label(titulo, "miPagoFichaTitulo"))
        valor = _label("", "miPagoFichaValor")
        ly.addWidget(valor)
        pie = _label("", "miPagoFichaPie", wrap=True)
        ly.addWidget(pie)
        ly.addStretch(1)
        valor.pie = pie
        fila.addWidget(caja, 1)
        return valor

    def _armar_nav_mes(self) -> QFrame:
        nav = QFrame()
        nav.setObjectName("miPagoMesNav")
        ly = QHBoxLayout(nav)
        ly.setContentsMargins(4, 3, 4, 3)
        ly.setSpacing(4)
        self.btn_mes_prev = QPushButton("◀")
        self.btn_mes_next = QPushButton("▶")
        self.mes_label = _label("", "miPagoMes")
        self.mes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mes_label.setMinimumWidth(130)
        for b in (self.btn_mes_prev, self.btn_mes_next):
            b.setAutoDefault(False)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mes_prev.setToolTip("Mes anterior")
        self.btn_mes_next.setToolTip("Mes siguiente")
        self.btn_mes_prev.clicked.connect(lambda: self._mover_mes(-1))
        self.btn_mes_next.clicked.connect(lambda: self._mover_mes(1))
        ly.addWidget(self.btn_mes_prev)
        ly.addWidget(self.mes_label)
        ly.addWidget(self.btn_mes_next)
        return nav

    def _seccion_config(self) -> QFrame:
        card = QFrame()
        card.setObjectName("miPagoCard")
        ly = QVBoxLayout(card)
        ly.setContentsMargins(18, 14, 18, 16)
        ly.setSpacing(12)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(16)
        self.cfg_monto = _dinero_spin(pd.MONTO_DEFAULT, 1_000_000)
        self.cfg_valor_dia = _dinero_spin(pd.VALOR_DIA_DEFAULT, 100_000)
        self.cfg_dias = QLineEdit(", ".join(str(d) for d in pd.DIAS_DE_PAGO_DEFAULT))
        self.cfg_dias.setObjectName("miPagoCampo")
        self.cfg_dias.setPlaceholderText("7, 14, 21, 28")
        self.cfg_inicio = QDateEdit(_qdate(self._hoy))
        self.cfg_inicio.setCalendarPopup(True)
        self.cfg_inicio.setDisplayFormat("dd/MM/yyyy")
        campos = (
            ("MONTO DE CADA PAGO", self.cfg_monto, "Lo de una semana."),
            ("VALOR DE UN DÍA", self.cfg_valor_dia, "Lo que suma o resta un día."),
            ("DÍAS DE PAGO", self.cfg_dias, "Del 1 al 28, separados por comas."),
            ("LA CUENTA EMPIEZA EL", self.cfg_inicio, "Antes de esa fecha no se cuenta nada."),
        )
        for i, (titulo, campo, ayuda) in enumerate(campos):
            grupo = QVBoxLayout()
            grupo.setSpacing(4)
            grupo.addWidget(_label(titulo, "miPagoFichaTitulo"))
            campo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if isinstance(campo, QDoubleSpinBox):
                campo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            campo.setMinimumWidth(120)
            grupo.addWidget(campo)
            grupo.addWidget(_label(ayuda, "miPagoNota", wrap=True))
            grupo.addStretch(1)
            grid.addLayout(grupo, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        ly.addLayout(grid)
        fila = QHBoxLayout()
        self.cfg_activo = QCheckBox("Llevar la cuenta (y recordarla en el corte)")
        self.cfg_activo.setChecked(True)
        fila.addWidget(self.cfg_activo, 1)
        self.btn_guardar_config = QPushButton("Guardar configuración")
        self.btn_guardar_config.setObjectName("miPagoPrimario")
        self.btn_guardar_config.setAutoDefault(False)
        self.btn_guardar_config.clicked.connect(self._guardar_config)
        fila.addWidget(self.btn_guardar_config)
        ly.addLayout(fila)
        return card

    def _mostrar_config(self, abierta: bool) -> None:
        self.config_box.setVisible(abierta)
        self.btn_config.setText(("▾" if abierta else "▸") + "  Configuración")
        # Sin cuenta guardada no hay nada que plegar: la configuración es lo único.
        self.btn_config.setVisible(self._carga_ok and self._config is not None)

    @staticmethod
    def _limpiar(box) -> None:
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                MiPagoDialog._limpiar(item.layout())

    def recargar(self, *, pintar_config: bool = False) -> None:
        """Vuelve a leer y pinta. La configuración solo se repinta al abrir y
        al guardarla (`pintar_config`), para no borrar lo que se está editando."""
        rec = None
        sin_descanso = False
        datos = None
        try:
            with self._sf() as session:
                pd.limpiar_decisiones_huerfanas(session)
                config = pd.cargar_config(session)
                vigente = config is not None and config.vigente
                pagos = pd.pagos_del_mes_db(session, self._year, self._month) if vigente else []
                extras = pd.lista_dias_extra(session, max(self._hoy, self._fin_de_mes())) if vigente else []
                rec = pd.recordatorio(session, self._hoy) if vigente else None
                sin_descanso = pd.falta_descanso(session) if vigente else False
                if vigente:
                    datos = pd.cargar_datos(session, config)
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se pudo cargar")
            self.status.setText("Sin conexión con la PC principal.")
            self._carga_ok = False
            self.btn_guardar_config.setEnabled(False)
            if self._cargo_alguna_vez:
                return      # se queda lo que ya se veía; solo cambia el pie
            self.vacio_titulo.setText("Sin conexión con la PC principal")
            self.vacio_texto.setText("No se pudo leer tu cuenta. Cierra y vuelve a abrir Mi pago.")
            self.pagos, self.extras, self._rec, self._datos = [], [], None, None
            self._registradas = set()
            self._pintar_heroe()
            self._mostrar_config(False)
            return
        self._carga_ok = self._cargo_alguna_vez = True
        self.btn_guardar_config.setEnabled(True)
        self._config, self.pagos, self.extras, self._datos = config, pagos, extras, datos
        self._registradas = set(datos.registros) if datos is not None else set()
        self.vacio_titulo.setText("Tu cuenta todavía no está configurada")
        self.vacio_texto.setText("Pon abajo el monto de cada pago y el día en que empieza la cuenta, y guarda.")
        self.btn_config.setVisible(self._config is not None)
        self._rec = rec
        self.aviso_descanso.setVisible(sin_descanso)
        if pintar_config or not self._config_pintada:
            self._pintar_config()
        self._pintar_heroe()
        self._pintar_pagos()
        self._pintar_extras()

    def _fin_de_mes(self) -> date:
        y, m = _mes_siguiente(self._year, self._month, 1)
        return date(y, m, 1) - timedelta(days=1)

    def _pintar_config(self) -> None:
        c = self._config
        if c is None:
            return
        self._config_pintada = True
        self.cfg_monto.setValue(float(c.monto_por_pago))
        self.cfg_valor_dia.setValue(float(c.valor_dia))
        self.cfg_dias.setText(", ".join(str(d) for d in c.dias_de_pago))
        if c.fecha_inicio is not None:
            self.cfg_inicio.setDate(_qdate(c.fecha_inicio))
        self.cfg_activo.setChecked(bool(c.activo))

    def _pintar_heroe(self) -> None:
        rec = self._rec
        hay = rec is not None
        self.heroe.setVisible(hay)
        self.fichas.setVisible(hay)
        self.seccion_pagos.setVisible(hay)
        self.seccion_extras.setVisible(hay)
        self.vacio_config.setVisible(not hay)
        if self._config is not None and not self._config.vigente:
            self.vacio_texto.setText("La cuenta está apagada. Prende «Llevar la cuenta» en la configuración.")
        if not hay:
            self.heroe_titulo.setText("")
            return
        # Si hay atrasados, arriba va el más viejo: el botón más visible de la
        # pantalla registra lo que urge, no el pago que todavía no toca.
        p = pago_de_la_tarjeta_grande(rec)
        atrasado = p is not rec.proximo
        self.heroe_kicker.setText("PAGO ATRASADO" if atrasado else "PRÓXIMO PAGO")
        self.heroe_titulo.setText(titulo_pago(p))
        self.heroe_monto.setText(pd.dinero_texto(p.monto))
        ajustes = resumen_ajustes(p)
        self.heroe_pie.setText(texto_cubre(p) + (f" · {ajustes}" if ajustes else ""))
        if atrasado:
            self.heroe_cuando.setText(texto_atraso((self._hoy - p.fecha_programada).days))
            self.heroe_cuando.setProperty("tono", "atrasado")
        else:
            self.heroe_cuando.setText(pd.cuando_toca(rec.dias_faltan))
            self.heroe_cuando.setProperty("tono", tono_cuando_toca(rec.dias_faltan))
        _repulir(self.heroe_cuando)

        valor, pie = texto_ultimo_pago(self._datos.registros if self._datos is not None else {})
        self.stat_ultimo.setText(valor)
        self.stat_ultimo.pie.setText(pie)
        self.stat_favor.setText(str(rec.dias_a_favor))
        self.stat_favor.pie.setText("cubren una falta cada uno")
        n = len(rec.atrasados)
        self.stat_atrasados.setText(str(n) if n else "Ninguno")
        self.stat_atrasados.setProperty("alerta", "true" if n else "false")
        _repulir(self.stat_atrasados)
        self.stat_atrasados.pie.setText(
            ", ".join(f"{a.etiqueta} ({pd.fecha_corta(a.fecha_programada)})" for a in rec.atrasados)
            if n else "vas al día"
        )

    def _pintar_pagos(self) -> None:
        self._limpiar(self._tira_box)
        self._limpiar(self._pagos_box)
        self.mes_label.setText(f"{_MESES[self._month - 1].capitalize()} {self._year}")
        self.tira: list[QFrame] = []
        c = self._config
        pasos: list[Paso] = []
        if c is not None and c.vigente:
            pasos = pasos_del_mes(c.dias_de_pago, self._year, self._month, self.pagos, self._registradas, self._hoy)
        texto, completo = resumen_del_mes(pasos)
        self.mes_resumen.setText(texto)
        self.mes_resumen.setProperty("completo", "true" if completo else "false")
        _repulir(self.mes_resumen)
        if pasos:
            for paso in pasos:
                cuadro = self._cuadro_paso(paso)
                self.tira.append(cuadro)
                self._tira_box.addWidget(cuadro, 1)
        tarjetas = list(self.pagos)
        if c is not None and self._datos is not None:
            # Un pago de antes del inicio que sí se registró (el 14-nov pagado
            # el 19) también lleva tarjeta: se ve su monto y se puede deshacer.
            ya = {p.fecha_programada for p in tarjetas}
            for paso in pasos:
                if paso.fecha in self._registradas and paso.fecha not in ya:
                    tarjetas.append(pd.desglose_de_pago(c, self._datos, paso.fecha))
            tarjetas.sort(key=lambda p: p.fecha_programada)
        self.tarjetas: dict[date, QFrame] = {}
        if not tarjetas:
            vacio = _label("Ningún pago de este mes cae desde el inicio de la cuenta.", "miPagoNota", wrap=True)
            self._pagos_box.addWidget(vacio)
            return
        for p in tarjetas:
            tarjeta = self._tarjeta_pago(p)
            self.tarjetas[p.fecha_programada] = tarjeta
            self._pagos_box.addWidget(tarjeta)

    def _cuadro_paso(self, paso: Paso) -> QFrame:
        cuadro = _CuadroPaso(lambda f=paso.fecha: self.ir_a_tarjeta(f))
        cuadro.setObjectName("miPagoPaso")
        cuadro.setProperty("estado", paso.estado)
        cuadro.setProperty("destacado", "true" if self._es_destacado(paso.fecha) else "false")
        ly = QVBoxLayout(cuadro)
        ly.setContentsMargins(10, 8, 10, 8)
        ly.setSpacing(0)
        fila = QHBoxLayout()
        fila.addWidget(_label(str(paso.numero), "miPagoPasoNumero"))
        fila.addStretch(1)
        fila.addWidget(_label(pd.fecha_corta(paso.fecha), "miPagoPasoFecha"))
        ly.addLayout(fila)
        estado = _label(PASO_TEXTO[paso.estado], "miPagoPasoEstado")
        ly.addWidget(estado)
        cuadro.paso = paso
        cuadro.setToolTip(f"{paso.numero} de {len(self._config.dias_de_pago)} · "
                          f"{pd.fecha_corta(paso.fecha, con_dia=True)} · {PASO_TEXTO[paso.estado]}")
        return cuadro

    def pago_heroe(self) -> pd.DesglosePago | None:
        """El pago de la tarjeta grande (el atrasado más viejo, o el próximo)."""
        return pago_de_la_tarjeta_grande(self._rec) if self._rec is not None else None

    def _es_destacado(self, fecha: date) -> bool:
        p = self.pago_heroe()
        return p is not None and p.fecha_programada == fecha

    def ir_a_tarjeta(self, fecha: date) -> None:
        """Tocar un cuadro de la tira baja a la tarjeta de ese pago."""
        tarjeta = getattr(self, "tarjetas", {}).get(fecha)
        if tarjeta is not None:
            self._area.ensureWidgetVisible(tarjeta, 0, 12)

    def _tarjeta_pago(self, p: pd.DesglosePago) -> QFrame:
        estado_pago = p.estado(self._hoy)
        card = QFrame()
        card.setObjectName("miPagoCard")
        card.setProperty("estado", estado_pago)
        ly = QVBoxLayout(card)
        ly.setContentsMargins(16, 12, 16, 12)
        ly.setSpacing(6)
        fila = QHBoxLayout()
        fila.setSpacing(10)
        titulo = _label(titulo_pago(p), "miPagoTitulo")
        fila.addWidget(titulo)
        estado = _label(texto_estado(p, self._hoy), "miPagoEstado")
        estado.setProperty("estado", estado_pago)
        fila.addWidget(estado)
        fila.addStretch(1)
        monto = _label(pd.dinero_texto(monto_de_la_tarjeta(p)), "miPagoMonto")
        fila.addWidget(monto)
        ly.addLayout(fila)

        fila2 = QHBoxLayout()
        fila2.addWidget(_label(texto_cubre(p), "miPagoCubre"), 1)
        if p.pagado:
            b = QPushButton("Deshacer pago")
            b.setObjectName("miPagoDeshacer")
            b.clicked.connect(lambda _c=False, pago=p: self._deshacer(pago))
        else:
            b = QPushButton("💵 Ya me pagaron")
            # El botón lleno solo en los atrasados (y en la tarjeta de arriba);
            # en los demás, de contorno.
            b.setObjectName("miPagoPrimario" if estado_pago == pd.ATRASADO else "miPagoChico")
            b.clicked.connect(lambda _c=False, pago=p: self._ya_me_pagaron(pago))
        b.setAutoDefault(False)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        renglones = renglones_desglose(p)
        if not renglones:
            fila2.addWidget(b)
            ly.addLayout(fila2)
        else:
            ly.addLayout(fila2)
            ly.addWidget(self._recibo(renglones))
            fila3 = QHBoxLayout()
            fila3.addStretch(1)
            fila3.addWidget(b)
            ly.addLayout(fila3)
        card.boton = b          # para las pruebas
        card.monto = monto
        card.renglones = renglones
        return card

    @staticmethod
    def _recibo(renglones: list[Renglon]) -> QFrame:
        recibo = QFrame()
        recibo.setObjectName("miPagoRecibo")
        grid = QGridLayout(recibo)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(3)
        for i, r in enumerate(renglones):
            grid.addWidget(_label(r.texto, "miPagoRenglon", wrap=True), i, 0)
            cifra = _label(r.cifra, "miPagoRenglonMonto")
            cifra.setProperty("clase", r.clase)
            cifra.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(cifra, i, 1)
        grid.setColumnStretch(0, 1)
        return recibo

    def _pintar_extras(self) -> None:
        self._limpiar(self._extras_box)
        valor = self._config.valor_dia if self._config is not None else pd.VALOR_DIA_DEFAULT
        self.extras_nota.setText(f"Cada uno vale {pd.dinero_texto(valor)}")
        if not self.extras:
            vacio = _label(
                "Ninguno por ahora. Se apuntan en el calendario con «Sí trabajó» en tu descanso.",
                "miPagoNota", wrap=True,
            )
            vacio.setContentsMargins(0, 8, 0, 8)
            self._extras_box.addWidget(vacio)
            return
        for i, e in enumerate(self.extras):
            if i:
                raya = QFrame()
                raya.setFixedHeight(1)
                raya.setStyleSheet("background: #ece2d4; border: none;")
                self._extras_box.addWidget(raya)
            fila_w = QWidget()
            fila = QHBoxLayout(fila_w)
            fila.setContentsMargins(0, 8, 0, 8)
            fila.setSpacing(8)
            fecha = _label(pd.fecha_corta(e.fecha, con_dia=True), "miPagoExtraFecha")
            fecha.setMinimumWidth(84)
            fila.addWidget(fecha)
            chip = _label(texto_dia_extra(e, self._pago_que_cubre(e.fecha)), "miPagoEstado")
            chip.setProperty("estado", estado_dia_extra(e))
            fila.addWidget(chip)
            fila.addStretch(1)
            pagar = QPushButton("💵 Págamelo")
            guardar = QPushButton("📦 Guárdamelo")
            for b, destino in ((pagar, pd.PAGAR), (guardar, pd.ACUMULAR)):
                b.setObjectName("miPagoSegmento")
                b.setAutoDefault(False)
                # El destino elegido queda «encendido» (deshabilitado: ya está).
                b.setEnabled(e.sin_decidir or e.destino != destino)
                b.clicked.connect(lambda _c=False, f=e.fecha, d=destino: self._decidir(f, d))
                fila.addWidget(b)
            fila_w.extra = e
            self._extras_box.addWidget(fila_w)

    def _pago_que_cubre(self, fecha: date) -> date | None:
        if self._config is None or not self._config.dias_de_pago:
            return None
        return pd.siguiente_pago(self._config, fecha)

    # ── acciones ──
    def _mover_mes(self, delta: int) -> None:
        self._year, self._month = _mes_siguiente(self._year, self._month, delta)
        self.recargar()

    def _ya_me_pagaron(self, p: pd.DesglosePago) -> None:
        dlg = _YaMePagaronDialog(self, p, self._hoy)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        fecha_pago, monto = dlg.valores()
        self.registrar(p.fecha_programada, fecha_pago, monto)

    def registrar(self, fecha_programada: date, fecha_pago: date, monto: Decimal | None) -> bool:
        try:
            with self._sf() as session:
                hecho = pd.registrar_pago(session, fecha_programada, fecha_pago, monto, self._quien, hoy=self._hoy)
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "No se guardó", str(exc))
            return False
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se registró el pago")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return False
        self.status.setText(
            f"Pago {hecho.etiqueta} guardado: {pd.dinero_texto(hecho.registro.monto)} "
            f"el {pd.fecha_corta(fecha_pago)}."
        )
        self.recargar()
        return True

    def _deshacer(self, p: pd.DesglosePago) -> None:
        r = QMessageBox.question(
            self, "Deshacer pago",
            f"¿Deshacer el pago {titulo_pago(p)}?\n\nVuelve a quedar como pendiente.",
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        self.deshacer(p.fecha_programada)

    def deshacer(self, fecha_programada: date) -> bool:
        try:
            with self._sf() as session:
                hecho = pd.deshacer_pago(session, fecha_programada, self._quien)
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "No se deshizo", str(exc))
            return False
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se deshizo el pago")
            QMessageBox.warning(self, "No se deshizo", "Inténtalo otra vez.")
            return False
        self.status.setText("Pago deshecho." if hecho else "Ese pago ya no estaba registrado.")
        self.recargar()
        return hecho

    def _decidir(self, fecha: date, destino: str) -> None:
        try:
            with self._sf() as session:
                pd.decidir_dia_extra(session, fecha, destino)
        except ValueError as exc:
            QMessageBox.warning(self, "No se guardó", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se guardó el destino")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        pago = self._pago_que_cubre(fecha)
        if destino == pd.PAGAR:
            cuando = f"va en el pago del {_dia_mes(pago)}." if pago is not None else "se paga en su pago."
        else:
            cuando = "queda como día a favor."
        self.status.setText(f"{pd.fecha_corta(fecha)}: {cuando}")
        self.recargar()

    def _guardar_config(self) -> None:
        try:
            dias = leer_dias_de_pago(self.cfg_dias.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Revisa las fechas", str(exc))
            return
        try:
            with self._sf() as session:
                pd.guardar_config(
                    session,
                    fecha_inicio=_de_qdate(self.cfg_inicio.date()),
                    monto_por_pago=Decimal(str(self.cfg_monto.value())),
                    valor_dia=Decimal(str(self.cfg_valor_dia.value())),
                    dias_de_pago=dias,
                    activo=self.cfg_activo.isChecked(),
                )
        except ValueError as exc:
            QMessageBox.warning(self, "No se guardó", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se guardó la configuración")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        self.status.setText("Configuración guardada.")
        self.recargar(pintar_config=True)


def abrir_mi_pago(parent: QWidget | None, quien: str | None) -> bool:
    """Lo que dispara el menú «💼 Caja ▾». Solo VEND-1. True si se abrió."""
    if str(quien or "").strip().upper() != pd.EMPLOYEE_CODE:
        QMessageBox.information(parent, "Mi pago", "Esta cuenta es solo del dueño.")
        return False
    MiPagoDialog(parent, quien=pd.EMPLOYEE_CODE).exec()
    return True
