"""Despachador de trabajos del satélite (Fase 1, núcleo sin Qt).

Toma trabajos PENDIENTE de la cola, ejecuta el handler que corresponde a su
tipo (imprimir un ticket, etc.) y marca el resultado (HECHO / ERROR).

Diseñado igual que TicketPrintQueue: sin dependencia de Qt. El `schedule`
(timer) y los `handlers` de impresión se inyectan, de modo que toda la lógica
—reclamar, ejecutar, marcar, drenar la cola— se testea sin un event loop real.

Semántica transaccional:
  1. Reclama el siguiente PENDIENTE y **commitea** el paso a EN_PROCESO, para
     que el reclamo sea visible de inmediato. Si el proceso muere mientras
     imprime, el trabajo queda EN_PROCESO (visible, se re-encola a mano) en
     vez de reimprimirse solo.
  2. Ejecuta el handler. Si lanza, marca ERROR con el mensaje; si no, HECHO.
  3. Cada transición se commitea.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Optional

from sqlalchemy.orm import Session

from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo, Trabajo
from pos_uniformes.services import trabajos_service as svc

# Un handler recibe el Trabajo reclamado y lo procesa; lanza si algo falla.
Handler = Callable[[Trabajo], None]

DEFAULT_IDLE_INTERVAL_MS = 1500  # espera cuando la cola está vacía


class TrabajoDispatcher:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        handlers: dict[TipoTrabajo, Handler],
        *,
        schedule: Callable[[int, Callable[[], None]], None] | None = None,
        tipos: Iterable[TipoTrabajo] | None = None,
        on_event: Callable[[int, EstadoTrabajo, str | None], None] | None = None,
        idle_interval_ms: int = DEFAULT_IDLE_INTERVAL_MS,
    ) -> None:
        """
        session_factory: crea una Session nueva por ciclo (p.ej. get_session).
        handlers: mapea cada TipoTrabajo a la función que lo procesa.
        schedule: agenda un callback tras N ms (QTimer.singleShot en prod).
                  Requerido solo para el modo loop (start/stop), no para poll_once.
        tipos: qué tipos atiende este despachador (por defecto, los que tiene handler).
        on_event: callback para GUI/log tras finalizar cada trabajo.
        """
        self._session_factory = session_factory
        self._handlers = dict(handlers)
        self._schedule = schedule
        self._tipos = list(tipos) if tipos is not None else list(self._handlers.keys())
        self._on_event = on_event
        self._idle_interval_ms = idle_interval_ms
        self._running = False

    # ── API ──────────────────────────────────────────────────────────────────

    def poll_once(self) -> Optional[EstadoTrabajo]:
        """Procesa como máximo un trabajo. Devuelve su estado final, o None si no había."""
        session = self._session_factory()
        try:
            trabajo = svc.reclamar_siguiente(session, tipos=self._tipos)
            if trabajo is None:
                session.rollback()
                return None
            trabajo_id = trabajo.id
            tipo = trabajo.tipo
            session.commit()  # el reclamo (EN_PROCESO) queda visible ya

            handler = self._handlers.get(tipo)
            try:
                if handler is None:
                    raise RuntimeError(f"No hay handler para el tipo {tipo.value}.")
                # Recargar dentro de esta sesión (el commit expiró el objeto).
                vigente = svc.obtener(session, trabajo_id)
                handler(vigente)
            except Exception as exc:  # noqa: BLE001 — un fallo no debe tumbar el loop
                svc.marcar_error(session, trabajo_id, str(exc))
                session.commit()
                self._emit(trabajo_id, EstadoTrabajo.ERROR, str(exc))
                return EstadoTrabajo.ERROR

            svc.marcar_hecho(session, trabajo_id)
            session.commit()
            self._emit(trabajo_id, EstadoTrabajo.HECHO, None)
            return EstadoTrabajo.HECHO
        finally:
            session.close()

    def drain(self, max_trabajos: int = 1000) -> int:
        """Procesa trabajos hasta vaciar la cola (o tope de seguridad). Devuelve cuántos."""
        procesados = 0
        while procesados < max_trabajos and self.poll_once() is not None:
            procesados += 1
        return procesados

    def start(self) -> None:
        """Arranca el loop de polling (requiere `schedule`)."""
        if self._schedule is None:
            raise RuntimeError("start() necesita un `schedule` (p.ej. QTimer.singleShot).")
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    # ── Interno ──────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if not self._running:
            return
        try:
            resultado = self.poll_once()
        except Exception:  # noqa: BLE001 — problema de conexión: reintentar tras el idle
            resultado = None
        # Si procesó algo, sigue de inmediato; si no, espera el idle.
        delay = 0 if resultado is not None else self._idle_interval_ms
        assert self._schedule is not None  # garantizado por start()
        self._schedule(delay, self._tick)

    def _emit(self, trabajo_id: int, estado: EstadoTrabajo, error: str | None) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(trabajo_id, estado, error)
        except Exception:  # noqa: BLE001 — un observador roto no debe afectar el loop
            pass
