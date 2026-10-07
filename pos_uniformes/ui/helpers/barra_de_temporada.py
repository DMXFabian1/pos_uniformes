"""Una barra de encabezado que se adorna sola según la temporada.

Daniel la pidió el 07/10 —«¿puedes hacer que en esta barra haya calabazas?»—
después de que las temporadas ya salían en el ticket. Es la misma idea en la
pantalla: la tienda se nota que sabe en qué mes está.

Tres reglas, las mismas que en el papel:

- **El motivo va DETRÁS del texto, nunca junto a él.** La barra dice quién está
  atendiendo y qué versión corre; eso se lee todos los días. Un adorno que haya
  que esquivar para leer dejó de ser un adorno.
- **Casi todo el año no hay nada.** Lo decide `temporada_service.actual()`, que
  es el mismo que manda en el ticket y el que obedece el menú de Temporada: si
  Daniel las apaga ahí, la barra se apaga también. Un solo interruptor.
- **Si algo truena, la barra sale lisa.** Es el encabezado de la aplicación: no
  puede dejar de dibujarse porque falte una calabaza.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QFont, QPainter
from PyQt6.QtWidgets import QFrame, QStyle, QStyleOption

#: Qué tan presente está el motivo. Bajo a propósito: a 0.5 compite con el
#: texto blanco del encabezado y la barra se vuelve ilegible.
OPACIDAD = 0.22
#: Cada cuántos puntos se repite. Más apretado parece papel tapiz.
PASO = 104


class TarjetaConTemporada(QFrame):
    """Un `QFrame` normal que, además, pinta el motivo de la temporada al fondo.

    Se pinta en `paintEvent` y no con una imagen de fondo en la hoja de estilos
    porque el fondo de esta tarjeta es un degradado que ya viene de ahí, y hay
    uno solo: o el degradado o el motivo. Dibujando encima se quedan los dos.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._temporada = self._leer_temporada()

    @staticmethod
    def _leer_temporada():
        try:
            from pos_uniformes.services.temporada_service import actual

            return actual()
        except Exception:  # noqa: BLE001 — el encabezado se dibuja igual
            return None

    def releer_temporada(self) -> None:
        """Vuelve a preguntar qué temporada es y se repinta.

        Existe para el menú: se cambia el ajuste y la barra cambia sin cerrar
        la aplicación. Sin esto habría que reiniciar el kiosko para ver si lo
        que se eligió era lo que se quería.
        """
        self._temporada = self._leer_temporada()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        # El fondo de la hoja de estilos primero. Medido el 07/10: un QFrame
        # dibuja su `background` de QSS aunque no se pida, así que esta línea
        # hoy es redundante — se queda porque deja de serlo en cuanto alguien
        # cambie la clase base a QWidget, y entonces la barra saldría gris con
        # el título blanco encima, o sea invisible.
        opcion = QStyleOption()
        opcion.initFrom(self)
        pintor = QPainter(self)
        self.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_Widget, opcion, pintor, self
        )
        t = self._temporada
        if t is None or not t.emoji:
            return
        try:
            self._pintar_motivo(pintor, t.emoji)
        except Exception:  # noqa: BLE001 — un adorno no borra el encabezado
            pass

    def _pintar_motivo(self, pintor: QPainter, emoji: str) -> None:
        alto = self.height()
        if alto <= 0:
            return
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pintor.setOpacity(OPACIDAD)
        fuente = QFont(self.font())
        fuente.setPixelSize(max(12, int(alto * 0.46)))
        pintor.setFont(fuente)
        # Se montan un poco fuera por los dos lados para que el motivo no
        # arranque ni termine en seco justo en el borde redondeado.
        x = -PASO // 2
        i = 0
        while x < self.width() + PASO:
            # Los nones más abajo y ligeramente ladeados: en hilera perfecta
            # parece una regla, y lo que se quiere es que se vea esparcido.
            dy = alto * (0.08 if i % 2 else -0.06)
            pintor.save()
            pintor.translate(x, alto / 2 + dy)
            pintor.rotate(-8 if i % 2 else 7)
            pintor.drawText(
                QRectF(-PASO / 2, -alto / 2, PASO, alto),
                int(Qt.AlignmentFlag.AlignCenter),
                emoji,
            )
            pintor.restore()
            x += PASO
            i += 1
