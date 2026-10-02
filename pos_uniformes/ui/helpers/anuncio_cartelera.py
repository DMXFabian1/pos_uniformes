"""Controlador de la cartelera de anuncios del satélite.

Junta el overlay con la lógica de:
- **Cartelera:** tras N segundos sin que nadie toque la pantalla, muestra el
  overlay y rota entre los anuncios activos (cada uno su `duracion_seg`).
- **Aviso inmediato:** muestra un anuncio apenas llega (NOTIFY), encima de lo
  que se esté haciendo; se cierra al tocar o tras unos segundos.
- **Acuse:** si el aviso lo pide (los que manda Daniel por Telegram), no se
  cierra solo ni con un toque al aire: espera «Enterada» o «Luego». Una vez
  acusado en esta pantalla se vuelve un anuncio común y no estorba de nuevo,
  aunque siga activo para las demás pantallas.
- **Actividad:** cualquier toque/tecla cierra el overlay y reinicia el contador
  de inactividad.

La lógica no depende del reloj real (se inyecta `now_fn`) ni de que los QTimer
corran, para poder testearla sin event loop.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PyQt6.QtCore import QObject, QTimer

from pos_uniformes.ui.anuncio_overlay import AnuncioOverlay

_INACTIVIDAD_DEFAULT_SEG = 120     # 2 min sin tocar → entra la cartelera
_CHEQUEO_INACTIVIDAD_MS = 10_000   # cada cuánto se revisa la inactividad
_INMEDIATO_AUTO_CERRAR_SEG = 20    # el aviso inmediato se cierra solo tras esto
_ANTIREBOTE_SEG = 0.8              # ignora descartes en el primer instante


class AnuncioCartelera(QObject):
    """Orquesta el overlay: cartelera por inactividad + avisos inmediatos."""

    def __init__(
        self,
        ventana,
        *,
        overlay: AnuncioOverlay | None = None,
        inactividad_seg: int = _INACTIVIDAD_DEFAULT_SEG,
        now_fn: Callable[[], float] | None = None,
        al_acusar: Callable[[dict], None] | None = None,
    ) -> None:
        super().__init__(ventana)
        self._ventana = ventana
        self._overlay = overlay if overlay is not None else AnuncioOverlay(ventana)
        self._overlay.descartado.connect(self._al_descartar)
        self._overlay.acusado.connect(self._al_acusar)
        #: Qué hacer con el acuse (escribirlo en la DB y avisarle a Daniel). Lo
        #: inyecta la ventana; aquí no se toca ni DB ni red.
        self._al_acusar_cb = al_acusar
        #: Ids ya acusados EN ESTA pantalla: dejan de pedir acuse localmente.
        self._acusados: set[int] = set()
        #: El anuncio que se está pintando, para saber qué se acusó.
        self._actual: dict | None = None
        self._now = now_fn or time.monotonic
        self._inactividad_seg = inactividad_seg

        self._anuncios: list[dict] = []
        self._idx = 0
        self._en_cartelera = False
        self._inmediato = False
        self._ultima_actividad = self._now()
        self._mostrado_en = 0.0

        # Timer de revisión de inactividad (arranca con start()).
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(_CHEQUEO_INACTIVIDAD_MS)
        self._idle_timer.timeout.connect(self._chequear_inactividad)
        # Rotación: single-shot reprogramado por anuncio.
        self._rotacion_timer = QTimer(self)
        self._rotacion_timer.setSingleShot(True)
        self._rotacion_timer.timeout.connect(self._rotar)
        # Auto-cierre del aviso inmediato.
        self._inmediato_timer = QTimer(self)
        self._inmediato_timer.setSingleShot(True)
        self._inmediato_timer.timeout.connect(self._cerrar_overlay)

    # ── API pública ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._idle_timer.start()

    def stop(self) -> None:
        self._idle_timer.stop()
        self._rotacion_timer.stop()
        self._inmediato_timer.stop()

    def set_anuncios(self, anuncios: list[dict]) -> None:
        """Actualiza la lista de anuncios activos (cartelera).

        Si estaba mostrando la cartelera y ya no hay anuncios, la cierra. Si
        sigue habiendo, reinicia la rotación desde el principio para no quedar
        en un índice inválido.
        """
        # Lo ya acusado aquí no vuelve, aunque siga activo para otras pantallas.
        self._anuncios = [
            a for a in (anuncios or []) if a.get("id") not in self._acusados
        ]
        if self._en_cartelera:
            if not self._anuncios:
                self._cerrar_overlay()
            else:
                self._idx = 0
                self._mostrar_actual()

    def notar_actividad(self) -> None:
        """Registra interacción: reinicia inactividad y cierra el overlay."""
        self._ultima_actividad = self._now()
        if self._overlay.isVisible():
            if self._necesita_acuse(self._actual):
                return  # solo sus botones lo quitan
            # Evita que un evento residual cierre el overlay apenas apareció.
            if self._now() - self._mostrado_en >= _ANTIREBOTE_SEG:
                self._cerrar_overlay()

    def mostrar_inmediato(self, anuncio: dict) -> None:
        """Muestra un anuncio ya mismo, encima de todo (aviso inmediato)."""
        if not anuncio:
            return
        self._en_cartelera = False
        self._rotacion_timer.stop()
        self._inmediato = True
        self._pintar(anuncio)
        # Un aviso con acuse no se cierra solo: nadie puede jurar que lo vieron
        # si se fue de la pantalla por su cuenta.
        if not self._necesita_acuse(anuncio):
            self._inmediato_timer.start(_INMEDIATO_AUTO_CERRAR_SEG * 1000)

    def hay_anuncios(self) -> bool:
        return bool(self._anuncios)

    # ── Interno ────────────────────────────────────────────────────────────────

    def _chequear_inactividad(self) -> None:
        if self._en_cartelera or self._inmediato or not self._anuncios:
            return
        if self._now() - self._ultima_actividad >= self._inactividad_seg:
            self._entrar_cartelera()

    def _entrar_cartelera(self) -> None:
        if not self._anuncios:
            return
        self._en_cartelera = True
        self._inmediato = False
        self._idx = 0
        self._mostrar_actual()

    def _mostrar_actual(self) -> None:
        if not self._anuncios:
            self._cerrar_overlay()
            return
        self._idx %= len(self._anuncios)
        anuncio = self._anuncios[self._idx]
        self._pintar(anuncio)
        # Programa el paso al siguiente según la duración del anuncio. Uno que
        # espera acuse se queda: rotar sería esconderlo sin que nadie contestara.
        if len(self._anuncios) > 1 and not self._necesita_acuse(anuncio):
            duracion = max(1, int(anuncio.get("duracion_seg") or 8))
            self._rotacion_timer.start(duracion * 1000)

    def _rotar(self) -> None:
        if not self._en_cartelera or not self._anuncios:
            return
        self._idx = (self._idx + 1) % len(self._anuncios)
        self._mostrar_actual()

    def _necesita_acuse(self, anuncio: dict | None) -> bool:
        """¿Este anuncio pide acuse y no se ha dado en esta pantalla?"""
        if not anuncio or not anuncio.get("pide_acuse"):
            return False
        return anuncio.get("id") not in self._acusados

    def _pintar(self, anuncio: dict) -> None:
        self._actual = anuncio
        # Si ya se acusó aquí, se pinta como anuncio común (sin botones).
        if anuncio.get("pide_acuse") and anuncio.get("id") in self._acusados:
            anuncio = {**anuncio, "pide_acuse": False}
        self._overlay.render_anuncio(anuncio)
        self._overlay.cubrir_padre()
        self._overlay.show()
        self._overlay.raise_()
        self._overlay.setFocus()
        self._mostrado_en = self._now()

    def _al_acusar(self) -> None:
        """Alguien tocó «Enterada»: se anota, se cierra y se le dice a Daniel."""
        anuncio = self._actual
        if anuncio is None:
            return
        anuncio_id = anuncio.get("id")
        if anuncio_id is not None:
            self._acusados.add(anuncio_id)
            # Y se va de la cartelera de esta pantalla. Antes solo dejaba de
            # pedir acuse y seguía rotando como anuncio común, así que el mismo
            # recado volvía a salir toda la tarde (Daniel, 02/10: "ya no salir
            # de nuevo, solo que me avise que ya se enteraron y ya").
            self._anuncios = [a for a in self._anuncios if a.get("id") != anuncio_id]
        self._ultima_actividad = self._now()
        self._cerrar_overlay()
        if self._al_acusar_cb is not None:
            try:
                self._al_acusar_cb(anuncio)
            except Exception:  # noqa: BLE001 — el acuse local ya quedó; no reventar la caja
                pass

    def _al_descartar(self) -> None:
        # «Luego» es un botón: se obedece al instante. El antirrebote es para los
        # toques al aire de la cartelera, no para alguien que apuntó al botón.
        if not self._necesita_acuse(self._actual) and (
            self._now() - self._mostrado_en < _ANTIREBOTE_SEG
        ):
            return
        self._ultima_actividad = self._now()
        self._cerrar_overlay()

    def _cerrar_overlay(self) -> None:
        self._en_cartelera = False
        self._inmediato = False
        self._rotacion_timer.stop()
        self._inmediato_timer.stop()
        self._overlay.hide()

    # Accesores para tests.
    @property
    def indice_actual(self) -> int:
        return self._idx

    @property
    def acusados(self) -> set:
        return set(self._acusados)
