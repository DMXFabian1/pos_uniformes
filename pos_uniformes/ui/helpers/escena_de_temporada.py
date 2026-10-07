"""El fondo de pantalla completa del kiosko cuando nadie está atendiendo.

Daniel lo pidió el 07/10 mirando la pantalla de «Escanea tu QR»: una extensión
de color vacía. «Motivos de halloween aquí, igual con degradado, a modo El
extraño mundo de Jack».

La película es de Disney, así que la escena es **original**: no hay personajes
suyos, ni arte bajado de internet. Lo que sí se puede tomar es el género —noche
morada, luna grande, árboles pelones, cerca chueca, calabazas encendidas—, que
es de donde esa película también lo tomó. La dibuja
`scripts/generar_escena_halloween.py`.

Va SOLO en esta pantalla. Mientras se vende, la pantalla es para vender.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QStyle, QStyleOption, QWidget


class FondoDeTemporada(QWidget):
    """Un `QWidget` que pinta la escena de la temporada, o nada."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._renderer = None
        self.releer_temporada()

    def releer_temporada(self) -> None:
        """Vuelve a preguntar qué temporada es y se repinta.

        Para el menú de Temporada: se elige y se ve, sin reiniciar el kiosko.
        """
        self._renderer = self._cargar()
        self.update()

    @staticmethod
    def _cargar():
        try:
            from PyQt6.QtSvg import QSvgRenderer

            from pos_uniformes.services.temporada_service import actual, escena_de

            ruta = escena_de(actual())
            if ruta is None:
                return None
            r = QSvgRenderer(str(ruta))
            return r if r.isValid() else None
        except Exception:  # noqa: BLE001 — sin escena, el fondo de siempre
            return None

    @property
    def tiene_escena(self) -> bool:
        return self._renderer is not None

    def paintEvent(self, event) -> None:  # noqa: N802 — nombre de Qt
        pintor = QPainter(self)
        if self._renderer is None:
            opcion = QStyleOption()
            opcion.initFrom(self)
            self.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_Widget, opcion, pintor, self
            )
            return
        try:
            self._pintar_escena(pintor)
        except Exception:  # noqa: BLE001 — un fondo no deja sin trabajar
            pass

    def _pintar_escena(self, pintor: QPainter) -> None:
        """La escena CUBRE el widget: se agranda hasta tapar y se recorta.

        Nunca se estira a la fuerza —la luna saldría ovalada— ni se encoge para
        caber, que dejaría franjas de fondo arriba y abajo. Y se ancla abajo:
        lo que se recorta es cielo, que es lo que sobra; las calabazas y la
        cerca son lo que no se puede perder.
        """
        caja = self._renderer.viewBoxF()
        if caja.width() <= 0 or caja.height() <= 0:
            return
        w, h = self.width(), self.height()
        escala = max(w / caja.width(), h / caja.height())
        ew, eh = caja.width() * escala, caja.height() * escala
        self._renderer.render(pintor, QRectF((w - ew) / 2, h - eh, ew, eh))
