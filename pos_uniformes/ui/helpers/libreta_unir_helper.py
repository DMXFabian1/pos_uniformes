"""«Unir con la anterior» / «Separar» en MOVIMIENTOS de la Libreta del
kiosko (Daniel, 2026-11-13). Solo con el gafete del dueño.

La clienta compró, se imprimió el ticket y luego se llevó otra cosa: dos
ventas que deben contar como UNA operación. Unir no anula ni borra nada: el
dinero, las piezas y las comisiones no cambian. La lógica vive en
`services/libreta_unir_service.py`; aquí solo el botón, la confirmación
(con «Cancelar» por defecto) y la marca «🔗 misma clienta» de la tabla.
"""

from __future__ import annotations

import logging

from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QMessageBox, QPushButton

from pos_uniformes.services import libreta_unir_service as lu

logger = logging.getLogger(__name__)

TEXTO_UNIR = "🔗 Unir con la anterior"
TEXTO_SEPARAR = "✂ Separar de su operación"
AYUDA_UNIR = (
    "La misma clienta se llevó otra cosa después de imprimir el ticket: "
    "las dos ventas cuentan como 1 operación. El dinero, las piezas y las "
    "comisiones no cambian."
)
#: Color de la marca en la tabla (terracota oscuro de la Libreta): el tono va
#: en el texto, no en el fondo de la celda.
COLOR_MARCA = "#73341c"


def crear_boton(ventana) -> QPushButton:
    boton = QPushButton(TEXTO_UNIR)
    boton.setObjectName("libretaAccion")
    boton.setAutoDefault(False)
    boton.setMinimumHeight(42)
    boton.setToolTip(AYUDA_UNIR)
    boton.clicked.connect(lambda _checked=False: al_tocar(ventana))
    return boton


def actualizar_boton(boton: QPushButton | None, row, *, es_dueno: bool) -> None:
    """«Unir con la anterior» en una venta suelta; «Separar» en una unida;
    escondido en lo que no se une (abonos, apartados, cambios, compras de
    empleada) y para quien no es el dueño."""
    if boton is None:
        return
    if row is None or not es_dueno:
        boton.setVisible(False)
        return
    if lu.esta_unida(row):
        boton.setText(TEXTO_SEPARAR)
        boton.setToolTip("Vuelve a contar como su propia operación. El dinero, las piezas y las comisiones no cambian.")
        boton.setVisible(True)
        boton.setEnabled(True)
        return
    boton.setText(TEXTO_UNIR)
    boton.setToolTip(AYUDA_UNIR)
    se_une = str(getattr(row, "tipo", None) or "venta") in lu.TIPOS_QUE_SE_UNEN and not getattr(
        row, "descuento_empleada", False
    )
    boton.setVisible(se_une)
    # Sin id (aún en la cola sin red) se ve, pero apagado.
    boton.setEnabled(lu.puede_ofrecerse(row))


def construir_confirmacion(parent, titulo: str, texto: str, detalle: str, accion: str) -> tuple[QMessageBox, object]:
    """La pregunta con «Cancelar» por defecto (Enter no une por accidente).
    Devuelve (caja, botón de la acción)."""
    caja = QMessageBox(parent)
    caja.setIcon(QMessageBox.Icon.Question)
    caja.setWindowTitle(titulo)
    caja.setText(texto)
    if detalle:
        caja.setInformativeText(detalle)
    si = caja.addButton(accion, QMessageBox.ButtonRole.AcceptRole)
    cancelar = caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    caja.setDefaultButton(cancelar)
    caja.setEscapeButton(cancelar)
    return caja, si


def _confirmar(parent, titulo, texto, detalle, accion) -> bool:
    caja, si = construir_confirmacion(parent, titulo, texto, detalle, accion)
    caja.exec()
    return caja.clickedButton() is si


def _fila_elegida(ventana):
    rows = list(getattr(ventana, "_libreta_rows_pintadas", []) or [])
    idx = ventana.libreta_table.currentRow()
    return rows[idx] if 0 <= idx < len(rows) else None


def _quien(row) -> str:
    from pos_uniformes.services.nombres_empleadas_service import mostrar

    code = str(getattr(row, "employee_code", "") or "")
    nombre = mostrar(getattr(row, "employee_name", "") or code, corto=True)
    return f"{nombre} ({code})" if nombre and code and nombre != code else (nombre or code)


def al_tocar(ventana) -> None:
    """Une la venta elegida con la anterior de la misma empleada ese día, o la
    separa si ya estaba unida. Pregunta antes y refresca la Libreta."""
    from pos_uniformes.database.connection import get_session

    if not getattr(ventana, "_libreta_is_owner", False):
        return
    row = _fila_elegida(ventana)
    if row is None:
        QMessageBox.information(ventana, "Sin selección", "Elige en MOVIMIENTOS la venta que quieres unir.")
        return
    if getattr(row, "id", None) is None:
        QMessageBox.information(
            ventana, "Aún sin sincronizar",
            "Esa venta todavía no sube al servidor; presiona Actualizar en un momento e inténtalo de nuevo.",
        )
        return
    actor = str(getattr(ventana, "_libreta_code", None) or "")
    resumen = getattr(ventana, "_libreta_resumen_de", None) or (lambda r: f"#{r.id}")
    try:
        if lu.esta_unida(row):
            if not _confirmar(ventana, "Separar", lu.texto_confirmar_separar(row.id), resumen(row), "Separar"):
                return
            with get_session() as session:
                lu.separar(session, int(row.id), actor=actor)
                session.commit()
            mensaje = f"#{row.id} vuelve a contar como su propia operación."
        else:
            with get_session() as session:
                anterior = lu.anterior_para_unir(session, int(row.id))
                if anterior is not None:
                    juntas = (
                        lu.miembros(session, anterior.operacion_grupo_id)
                        if anterior.operacion_grupo_id is not None else [anterior]
                    ) + [session.get(type(anterior), int(row.id))]
                    juntas.sort(key=lambda r: (r.created_at, r.id))
                    ids = [r.id for r in juntas]
                    anterior_id = int(anterior.id)
                    detalle = "\n".join(f"#{r.id} · {resumen(r)}" for r in juntas)
            if anterior is None:
                QMessageBox.information(
                    ventana, "Unir con la anterior",
                    f"{_quien(row)} no tiene otra venta antes de esta ese mismo día para unirla.",
                )
                return
            texto = lu.texto_confirmar_union(ids, _quien(row))
            if not _confirmar(ventana, "Unir en una operación", texto, detalle, "Unir"):
                return
            with get_session() as session:
                lu.unir(session, anterior_id, int(row.id), actor=actor)
                session.commit()
            mensaje = f"Listo: {' y '.join(f'#{i}' for i in sorted(ids))} cuentan como 1 operación."
    except (lu.NoSePuedeUnir, lu.SoloElDuenoUne) as exc:
        QMessageBox.information(ventana, "No se pudo", str(exc))
        return
    except Exception as exc:  # noqa: BLE001 — se le dice al dueño, no se cae el kiosko
        logger.exception("Libreta: no se pudo unir/separar la venta %s", getattr(row, "id", None))
        QMessageBox.warning(ventana, "No se pudo", str(exc))
        return
    set_status = getattr(ventana, "_set_status", None)
    if set_status is not None:
        set_status(mensaje)
    refrescar = getattr(ventana, "_refresh_libreta_view", None)
    if refrescar is not None:
        refrescar()


# ─── La marca en la tabla ────────────────────────────────────────────────


def marcar_tipo(texto_tipo: str, row, posiciones: dict | None = None) -> str:
    """«🔗 Venta — Fanny López»: el eslabón va delante (corto, para que el
    nombre quepa) y las ventas unidas se leen juntas sin perder cada renglón.
    «misma clienta» y con cuál se dice al pasar el mouse y en «Movimiento
    elegido» (`texto_detalle`)."""
    if not lu.esta_unida(row):
        return texto_tipo
    return f"🔗 {texto_tipo}"


def texto_detalle(row, rows) -> str:
    """El renglón extra de «Movimiento elegido» para una venta unida:
    «🔗 Misma clienta que #1639: cuentan como 1 operación.» ("" si va sola)."""
    if row is None or not lu.esta_unida(row):
        return ""
    otras = sorted(
        int(r.id) for r in rows or ()
        if getattr(r, "operacion_grupo_id", None) == row.operacion_grupo_id and getattr(r, "id", None) != row.id
    ) or [int(row.operacion_grupo_id)]
    lista = " y ".join(f"#{i}" for i in otras)
    return f"🔗 Misma clienta que {lista}: cuentan como 1 operación."


def pintar_fila(tabla, fila: int, row) -> None:
    """Texto terracota y una explicación al pasar el mouse en la celda Tipo."""
    if not lu.esta_unida(row):
        return
    item = tabla.item(fila, 2)
    if item is None:
        return
    item.setForeground(QBrush(QColor(COLOR_MARCA)))
    letra = item.font()
    letra.setBold(True)
    item.setFont(letra)
    quien = getattr(row, "operacion_unida_por", None)
    cuando = getattr(row, "operacion_unida_en", None)
    pie = ""
    if quien or cuando:
        momento = cuando.astimezone().strftime("%d/%m %H:%M") if getattr(cuando, "tzinfo", None) else (
            cuando.strftime("%d/%m %H:%M") if cuando else ""
        )
        pie = f"\nUnida por {quien or '—'}" + (f" el {momento}" if momento else "") + "."
    item.setToolTip(
        f"🔗 Misma clienta (operación #{row.operacion_grupo_id}): junto con las otras ventas "
        "con 🔗 de ese número cuenta como 1 operación. El dinero, las piezas y las "
        "comisiones de cada renglón no cambian." + pie
    )
