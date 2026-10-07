"""La caja de «¿qué impresoras tiene esta PC?», una sola vez.

Vive aquí porque se configura desde DOS lados: el menú admin del kiosko
(Ctrl+Shift+A) y Configuración del POS principal. Tenerla copiada dos veces es
pedir que se separen, y separarse aquí tiene un castigo feo: la copia vieja
guardaba sin la lista de impresoras y la máquina volvía a "todo o nada" en
silencio, borrando lo que se había configurado del otro lado
(2026-10-07).

De lo que se marca aquí salen las dos respuestas del ruteo: lo que esta PC
imprime de lo suyo y lo que atiende de la cola de las demás.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

#: (clave del TipoTrabajo, cómo se llama en la pantalla).
TIPOS = (
    ("TICKET", "🧾  Tickets de venta"),
    # Aparte de los tickets a propósito: el corte lleva la venta del día, los
    # pagos y los retiros, y no tiene por qué salir en la misma PC
    # (Daniel, 2026-10-07: "por privacidad no queda a la mano").
    ("CORTE", "🧮  Cortes de caja"),
    ("ETIQUETA", "🏷  Etiquetas (Brother)"),
    ("CONTEO", "📋  Hojas de conteo"),
    ("PEDIDO", "📦  Pedidos"),
)


def _nombre_corto(clave: str) -> str:
    return dict(TIPOS)[clave].split("  ")[-1]


def construir_caja_impresoras(
    parent: QWidget,
    *,
    al_cambiar: Callable[[set[str]], None] | None = None,
    titulo: str = "Impresoras de esta PC",
    boton: str = "Guardar",
) -> QGroupBox:
    """La caja completa: casillas, nombre de la PC, resumen y guardar.

    `al_cambiar` se llama con las claves marcadas cada vez que se toca una
    casilla y una vez al construirla, para que quien la use pueda esconder sus
    propias cajas de configuración de impresora.
    """
    from pos_uniformes.services.print_routing_cache_service import (
        guardar_impresoras,
        impresoras_de_esta_pc,
        load_print_routing,
    )

    box = QGroupBox(titulo)
    box.setObjectName("infoCard")
    layout = QVBoxLayout()
    layout.setSpacing(8)

    ayuda = QLabel(
        "Marca lo que esta PC tiene cómo imprimir. De ahí sale todo lo demás: "
        "lo que marques se imprime aquí (lo suyo y lo que le manden las otras "
        "PCs), y lo que no, se va a la cola para que lo imprima quien sí pueda."
    )
    ayuda.setWordWrap(True)
    ayuda.setObjectName("subtleLine")
    layout.addWidget(ayuda)

    tiene = impresoras_de_esta_pc()
    casillas: dict[str, QCheckBox] = {}
    for clave, etiqueta in TIPOS:
        cb = QCheckBox(etiqueta)
        cb.setChecked(clave in tiene)
        casillas[clave] = cb
        layout.addWidget(cb)

    resumen = QLabel("")
    resumen.setWordWrap(True)
    # Estilo en línea y no por objectName: esta caja la usan DOS apps con hojas
    # de estilo distintas (el kiosko y el POS principal), y la del kiosko pinta
    # las notas en crema para su barra oscura — sobre este fondo claro el texto
    # desaparecía y solo quedaba el emoji (2026-10-07).
    resumen.setStyleSheet(
        "background: rgba(44, 42, 39, 0.05);"
        "border: 1px solid rgba(44, 42, 39, 0.12);"
        "border-radius: 14px; padding: 8px 12px;"
        "color: #2c2a27; font-weight: 700;"
    )

    def _marcados() -> list[str]:
        return [c for c, cb in casillas.items() if cb.isChecked()]

    def _refrescar() -> None:
        marcados = _marcados()
        if not marcados:
            resumen.setText(
                "📡  Estación: esta PC no imprime nada. Todo se va a la cola y "
                "sale donde haya impresora."
            )
        elif len(marcados) == len(casillas):
            resumen.setText(
                "🖨  Servidor de impresión: esta PC imprime todo, lo suyo y lo "
                "que le manden las demás."
            )
        else:
            faltan = [c for c in casillas if c not in marcados]
            resumen.setText(
                "🖨  Imprime aquí: " + ", ".join(_nombre_corto(c) for c in marcados)
                + ".\n📡  Se va a la cola: "
                + ", ".join(_nombre_corto(c) for c in faltan) + "."
            )
        if al_cambiar is not None:
            al_cambiar(set(marcados))

    for cb in casillas.values():
        cb.toggled.connect(lambda _v: _refrescar())
    layout.addWidget(resumen)

    _modo, origen_actual = load_print_routing()
    fila = QHBoxLayout()
    fila.addWidget(QLabel("Nombre de esta PC:"))
    origen_edit = QLineEdit(origen_actual)
    origen_edit.setPlaceholderText("principal / kiosko / caja 2")
    fila.addWidget(origen_edit, 1)
    layout.addLayout(fila)

    guardar = QPushButton(boton)
    guardar.setObjectName("primaryButton")

    def _guardar() -> None:
        try:
            guardar_impresoras(origen_edit.text().strip() or "principal", _marcados())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(parent, "Error", f"No se pudo guardar:\n{exc}")
            return
        QMessageBox.information(parent, "Guardado", resumen.text())

    guardar.clicked.connect(_guardar)
    layout.addWidget(guardar)

    box.setLayout(layout)
    _refrescar()
    return box
