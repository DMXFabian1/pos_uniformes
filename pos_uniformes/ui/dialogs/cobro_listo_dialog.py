"""La ventana de cobro, ya cobrada: «Imprimir otra vez» y «Listo».

Daniel, 2026-11-24: «¿puedes hacer que no se cierre en automático? así le
puede dar otra vez clic, por si se atora el papel o algo». Al tocar «Imprimir
aquí» o «Mandar a PC principal» la venta se anota UNA vez y el ticket sale;
en el mismo lugar queda esta ventana para reimprimirlo (aquí o en otra PC)
sin volver a anotar nada, y «Listo» (o Enter) pasa a la siguiente venta.

La impresión y el envío los hace quien la abre (`ticket_routing_helper`): la
ventana solo pinta el estado y llama a `reimprimir` / `mandar`.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

_ESTILO = (
    "QDialog { background: #f4ede2; }"
    "QLabel { color: #2c2a27; background: transparent; }"
    "QPushButton#otraVez, QPushButton#mandarOtraVez { background: #f8f2e9; color: #73341c;"
    "  border: 1px solid #ddd0c0; border-radius: 14px;"
    "  min-height: 60px; font-size: 16px; font-weight: 700; }"
    "QPushButton#otraVez:pressed, QPushButton#mandarOtraVez:pressed { background: #e8dbc7; }"
    "QPushButton:disabled { background: #f1ece4; color: #a89f93; border-color: #e6ddd0; }"
    "QPushButton#listo { background: #a84f2d; color: #ffffff; border: none;"
    "  border-radius: 14px; min-height: 64px; font-size: 18px; font-weight: 800; }"
    "QPushButton#listo:pressed { background: #8a4326; }"
)

_COLOR_OK = "#2f6b3a"
_COLOR_MAL = "#b3261e"
_COLOR_NEUTRO = "#5f594f"


class VentanaCobrado:
    """`reimprimir(textos, al_terminar)` imprime aquí y al acabar llama
    `al_terminar(no_salieron)`; `mandar(destino, textos) -> bool` encola en
    otra PC. `destinos`: las otras PCs que imprimen tickets
    ([{identificador, nombre, online}]); una apagada se ve pero no se toca.
    `al_cerrar_con_fallas(no_salieron)`: si se cierra antes de que acabe la
    impresión y algo no salió, a quién avisar."""

    def __init__(
        self,
        parent: QWidget | None,
        tickets: list[str],
        *,
        total_txt: str | None,
        destinos: list[dict],
        reimprimir: Callable[[list[str], Callable[[list[str]], None]], object],
        mandar: Callable[[dict, list[str]], bool],
        al_cerrar_con_fallas: Callable[[list[str]], None] | None = None,
    ) -> None:
        self._tickets = list(tickets)
        self._no_salieron: list[str] = []
        self._reimprimir = reimprimir
        self._mandar = mandar
        self._al_cerrar_con_fallas = al_cerrar_con_fallas
        self._imprimiendo = False
        self._cerrada = False

        dlg = QDialog(parent)
        dlg.setWindowTitle("Cobrado")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet(_ESTILO)
        self.dialog = dlg
        ly = QVBoxLayout(dlg)
        ly.setContentsMargins(22, 20, 22, 18)
        ly.setSpacing(12)

        encabezado = QHBoxLayout()
        titulo = QLabel("✓  Cobrado")
        titulo.setStyleSheet("font-size: 21px; font-weight: 900; color: #73341c;")
        encabezado.addWidget(titulo, 1)
        if total_txt:
            total = QLabel(f"Total\n{total_txt}")
            total.setObjectName("cobradoTotal")
            total.setAlignment(Qt.AlignmentFlag.AlignCenter)
            total.setStyleSheet(
                "QLabel#cobradoTotal { background: #a84f2d; color: #ffffff;"
                "  border-radius: 14px; padding: 6px 18px; font-size: 22px; font-weight: 900; }"
            )
            encabezado.addWidget(total, 0, Qt.AlignmentFlag.AlignTop)
        ly.addLayout(encabezado)

        self.estado = QLabel("")
        self.estado.setObjectName("cobradoEstado")
        self.estado.setWordWrap(True)
        ly.addWidget(self.estado)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.otra_vez = QPushButton("🖨  Imprimir otra vez\naquí")
        self.otra_vez.setObjectName("otraVez")
        self.otra_vez.setAutoDefault(False)
        self.otra_vez.clicked.connect(self._on_otra_vez)
        fila.addWidget(self.otra_vez, 1)
        self.mandar_botones: list[QPushButton] = []
        for destino in destinos[:2]:
            nombre = destino.get("nombre") or "otra PC"
            encendida = bool(destino.get("online"))
            b = QPushButton(f"📡  Mandar a\n{nombre}" if encendida else f"📡  {nombre}\napagada")
            b.setObjectName("mandarOtraVez")
            b.setAutoDefault(False)
            b.setEnabled(encendida)
            b.clicked.connect(lambda _=False, d=destino: self._on_mandar(d))
            fila.addWidget(b, 1)
            self.mandar_botones.append(b)
        ly.addLayout(fila)

        self.listo = QPushButton("✓  Listo · siguiente venta")
        self.listo.setObjectName("listo")
        # Enter = Listo: lo normal después de cobrar es la siguiente venta.
        self.listo.setDefault(True)
        self.listo.setAutoDefault(True)
        self.listo.clicked.connect(dlg.accept)
        ly.addWidget(self.listo)
        dlg.finished.connect(self._on_cerrar)

    # ── Estado ───────────────────────────────────────────────────────────

    def _pintar(self, texto: str, color: str) -> None:
        self.estado.setText(texto)
        self.estado.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {color};")

    def imprimiendo(self) -> None:
        self._imprimiendo = True
        self.otra_vez.setEnabled(False)
        self._pintar("🖨  Imprimiendo…", _COLOR_NEUTRO)

    def termino(self, no_salieron: list[str]) -> None:
        """La impresión de aquí acabó; `no_salieron`: los que fallaron."""
        self._imprimiendo = False
        self._no_salieron = list(no_salieron)
        if self._cerrada:
            if self._no_salieron and self._al_cerrar_con_fallas is not None:
                self._al_cerrar_con_fallas(list(self._no_salieron))
            return
        self.otra_vez.setEnabled(True)
        if self._no_salieron:
            self._pintar(
                "⚠  No salió el ticket. Revisa el papel y toca «Imprimir otra vez». "
                "La venta ya quedó anotada: no la cobres de nuevo.",
                _COLOR_MAL,
            )
        else:
            self._pintar("✓  Ticket impreso. Si se atoró el papel, imprímelo otra vez.", _COLOR_OK)

    def mandado(self, nombre: str) -> None:
        self._pintar(f"📡  Mandado a {nombre}. Si no sale allá, imprímelo aquí.", _COLOR_OK)

    # ── Acciones ─────────────────────────────────────────────────────────

    def textos_para_reimprimir(self) -> list[str]:
        """Lo que no salió; si salió todo, solo el del cliente (el que se
        atora en la mano del cliente, no la copia de la tienda)."""
        return list(self._no_salieron) or self._tickets[:1]

    def _on_otra_vez(self) -> None:
        if self._imprimiendo:
            return
        textos = self.textos_para_reimprimir()
        self.imprimiendo()
        self._reimprimir(textos, self.termino)

    def _on_mandar(self, destino: dict) -> None:
        nombre = destino.get("nombre") or "otra PC"
        if self._mandar(destino, self.textos_para_reimprimir()):
            self._no_salieron = []
            self.mandado(nombre)
        else:
            self._pintar(f"⚠  No se pudo mandar a {nombre}. Revisa la conexión o imprímelo aquí.", _COLOR_MAL)

    def _on_cerrar(self, _resultado: int) -> None:
        self._cerrada = True

    def exec(self) -> None:
        self.dialog.exec()
        self._cerrada = True
