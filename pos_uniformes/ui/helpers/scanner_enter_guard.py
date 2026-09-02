"""Guard contra el Enter fantasma del escáner QR en diálogos de impresión.

El escáner HID teclea el código como una ráfaga muy rápida y remata con un
Enter (o CR+LF, según la config del escáner). Si en ese momento hay abierto un
diálogo de impresión (tickets o etiquetas), ese Enter activa el botón default
— imprime o cierra sin querer.

`ScannerEnterGuard(dialog)` instala un filtro que detecta la ráfaga (teclas a
ritmo de máquina, imposible para un humano) y se traga solo el/los Enter
finales. El Enter tecleado a mano sigue funcionando normal.
"""

from __future__ import annotations

import time

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QApplication, QWidget


class ScannerBurstDetector:
    """Lógica pura de detección de ráfaga, con timestamps inyectables (ms)."""

    def __init__(
        self,
        *,
        burst_gap_ms: float = 80.0,
        min_chars: int = 4,
        enter_window_ms: float = 150.0,
    ) -> None:
        self._burst_gap_ms = burst_gap_ms
        self._min_chars = min_chars
        self._enter_window_ms = enter_window_ms
        self._count = 0
        self._last_ms: float | None = None
        self._last_swallow_ms: float | None = None

    def feed_char(self, now_ms: float) -> None:
        if self._last_ms is None or now_ms - self._last_ms > self._burst_gap_ms:
            self._count = 1
        else:
            self._count += 1
        self._last_ms = now_ms

    def should_swallow_enter(self, now_ms: float) -> bool:
        # Enter pegado a otro Enter ya tragado: es el LF de un escáner con
        # terminador CR+LF — también se traga, si no activaría el botón.
        if (
            self._last_swallow_ms is not None
            and now_ms - self._last_swallow_ms <= self._enter_window_ms
        ):
            self._last_swallow_ms = now_ms
            return True
        is_burst = (
            self._last_ms is not None
            and self._count >= self._min_chars
            and now_ms - self._last_ms <= self._enter_window_ms
        )
        self._count = 0
        self._last_ms = None
        self._last_swallow_ms = now_ms if is_burst else None
        return is_burst


class ScannerEnterGuard(QObject):
    """Filtro de eventos con el ciclo de vida del diálogo (parent=dialog).

    Se instala a nivel aplicación porque el KeyPress llega al widget con foco
    (editor, spinbox, botón), no al diálogo; el filtro solo actúa sobre eventos
    dirigidos al diálogo o sus hijos. Se DESINSTALA cuando el diálogo termina
    (finished) — varios diálogos de impresión no se destruyen al cerrarse, y
    sin esto los filtros de aplicación se acumularían uno por impresión.
    """

    def __init__(self, dialog: QWidget) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._detector = ScannerBurstDetector()
        # (timestamp, key) del último KeyPress procesado: el mismo QKeyEvent
        # se entrega varias veces al propagarse foco→padre→diálogo, y no debe
        # contar como varias teclas.
        self._last_ident: tuple[int, int] | None = None
        self._installed = False
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._installed = True
        finished = getattr(dialog, "finished", None)
        if finished is not None:
            finished.connect(self._uninstall)

    def _uninstall(self, *_args) -> None:
        if not self._installed:
            return
        self._installed = False
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() != QEvent.Type.KeyPress:
            return False
        if not isinstance(watched, QWidget):
            return False
        if watched is not self._dialog and not self._dialog.isAncestorOf(watched):
            return False
        # Auto-repeat de una tecla sostenida (~30Hz) parece ráfaga pero es
        # humano: no alimenta el detector ni se traga.
        if event.isAutoRepeat():
            return False
        ident = (int(event.timestamp()), int(event.key()))
        if ident == self._last_ident:
            # Mismo evento propagándose entre widgets: ya se procesó. Si se
            # hubiera tragado (True), la propagación no habría ocurrido.
            return False
        self._last_ident = ident
        now_ms = time.monotonic() * 1000.0
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return self._detector.should_swallow_enter(now_ms)
        text = event.text()
        if text and text.isprintable():
            self._detector.feed_char(now_ms)
        return False
