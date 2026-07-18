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

import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from pos_uniformes.database.models import EstadoTrabajo, TipoTrabajo, Trabajo
from pos_uniformes.services import trabajos_service as svc

logger = logging.getLogger(__name__)

# Un handler recibe el Trabajo reclamado y lo procesa; lanza si algo falla.
Handler = Callable[[Trabajo], None]

DEFAULT_IDLE_INTERVAL_MS = 1500      # espera cuando la cola está vacía
DEFAULT_OFFLINE_INTERVAL_MS = 30_000  # espera cuando la DB está caída (no martillar la UI)
DEFAULT_MAX_INTENTOS = 3             # reintentos antes de ERROR definitivo
DEFAULT_BACKOFF_BASE_S = 5.0         # 5s, 10s, 20s… entre reintentos
DEFAULT_BACKOFF_MAX_S = 300.0        # tope de espera entre reintentos


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrabajoDispatcher:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        handlers: dict[TipoTrabajo, Handler],
        *,
        schedule: Callable[[int, Callable[[], None]], None] | None = None,
        tipos: Iterable[TipoTrabajo] | None = None,
        on_event: Callable[[int, EstadoTrabajo, str | None], None] | None = None,
        connectivity_probe: Callable[[], bool] | None = None,
        idle_interval_ms: int = DEFAULT_IDLE_INTERVAL_MS,
        offline_interval_ms: int = DEFAULT_OFFLINE_INTERVAL_MS,
        max_intentos: int = DEFAULT_MAX_INTENTOS,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        backoff_max_s: float = DEFAULT_BACKOFF_MAX_S,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        """
        session_factory: crea una Session nueva por ciclo (p.ej. get_session).
        handlers: mapea cada TipoTrabajo a la función que lo procesa.
        schedule: agenda un callback tras N ms (QTimer.singleShot en prod).
                  Requerido solo para el modo loop (start/stop), no para poll_once.
        tipos: qué tipos atiende este despachador (por defecto, los que tiene handler).
        on_event: callback para GUI/log tras finalizar cada trabajo.
        connectivity_probe: predicado BARATO y CACHEADO (no bloqueante) que dice
                  si la DB está disponible. Si devuelve False, el loop NO abre
                  conexión (que bloquearía el hilo de UI hasta el connect_timeout)
                  y reintenta tras `offline_interval_ms`. Lo mantiene el watchdog
                  off-thread del satélite; no debe abrir sockets él mismo.
        idle_interval_ms: espera entre polls cuando la cola está vacía.
        offline_interval_ms: espera entre polls cuando la DB está caída (largo,
                  para no congelar la UI con conexiones que expiran).
        max_intentos: reintentos antes de dejar un trabajo en ERROR.
        backoff_base_s / backoff_max_s: espera creciente entre reintentos.
        now_fn: reloj inyectable (para tests).
        """
        self._session_factory = session_factory
        self._handlers = dict(handlers)
        self._schedule = schedule
        self._tipos = list(tipos) if tipos is not None else list(self._handlers.keys())
        self._on_event = on_event
        self._connectivity_probe = connectivity_probe
        self._idle_interval_ms = idle_interval_ms
        self._offline_interval_ms = offline_interval_ms
        self._max_intentos = max_intentos
        self._backoff_base_s = backoff_base_s
        self._backoff_max_s = backoff_max_s
        self._now = now_fn or _utcnow
        self._running = False
        # True si el último poll falló por la DB (no por cola vacía). Deja que el
        # loop pase a intervalo largo aunque el probe externo no se haya enterado.
        self._last_poll_db_down = False

    def _backoff_para(self, proximo_intento: int) -> datetime:
        """Momento a partir del cual reintentar (backoff exponencial acotado)."""
        segundos = min(
            self._backoff_max_s, self._backoff_base_s * (2 ** max(0, proximo_intento - 1))
        )
        return self._now() + timedelta(seconds=segundos)

    # ── API ──────────────────────────────────────────────────────────────────

    def poll_once(self) -> Optional[EstadoTrabajo]:
        """Procesa como máximo un trabajo. Devuelve su estado resultante, o None.

        Devuelve None también si la DB no está disponible (el loop reintenta tras
        el idle) o si no había trabajo. Un fallo del handler NO tumba el loop:
        el trabajo se reprograma (backoff) o queda en ERROR según los reintentos.
        """
        self._last_poll_db_down = False
        try:
            session = self._session_factory()
        except Exception as exc:  # noqa: BLE001 — DB caída: reintentar luego
            logger.warning("Despachador: no se pudo abrir sesión: %s", exc)
            self._last_poll_db_down = True
            return None

        try:
            trabajo = svc.reclamar_siguiente(session, tipos=self._tipos)
            if trabajo is None:
                session.rollback()
                return None
            trabajo_id = trabajo.id
            tipo = trabajo.tipo
            proximo_intento = (trabajo.intentos or 0) + 1
            session.commit()  # el reclamo (EN_PROCESO) queda visible ya

            handler = self._handlers.get(tipo)
            try:
                if handler is None:
                    raise RuntimeError(f"No hay handler para el tipo {tipo.value}.")
                # Recargar dentro de esta sesión (el commit expiró el objeto).
                vigente = svc.obtener(session, trabajo_id)
                handler(vigente)
            except Exception as exc:  # noqa: BLE001 — un fallo no debe tumbar el loop
                resultado = svc.registrar_fallo(
                    session,
                    trabajo_id,
                    str(exc),
                    max_intentos=self._max_intentos,
                    disponible_en=self._backoff_para(proximo_intento),
                )
                estado_final = resultado.estado
                session.commit()
                self._emit(trabajo_id, estado_final, str(exc))
                return estado_final

            svc.marcar_hecho(session, trabajo_id)
            session.commit()
            self._emit(trabajo_id, EstadoTrabajo.HECHO, None)
            return EstadoTrabajo.HECHO
        except Exception as exc:  # noqa: BLE001 — error de conexión/DD: no matar el loop
            logger.warning("Despachador: error de DB, se reintenta luego: %s", exc)
            self._last_poll_db_down = True
            try:
                session.rollback()
            except Exception:  # noqa: BLE001
                pass
            return None
        finally:
            try:
                session.close()
            except Exception:  # noqa: BLE001
                pass

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
        assert self._schedule is not None  # garantizado por start()
        # 1) Gate barato y cacheado: si el watchdog ya sabe que la DB está caída,
        #    ni intentamos abrir conexión (bloquearía el hilo de UI hasta el
        #    connect_timeout). Reintentar lento hasta que vuelva el servidor.
        if self._connectivity_probe is not None and not self._connectivity_probe():
            self._schedule(self._offline_interval_ms, self._tick)
            return
        try:
            resultado = self.poll_once()
        except Exception:  # noqa: BLE001 — problema de conexión: reintentar tras el idle
            resultado = None
            self._last_poll_db_down = True
        # 2) Autoprotección: si el poll falló por la DB (no por cola vacía), pasa a
        #    intervalo largo aunque el probe externo aún no se haya enterado — así
        #    una caída a mitad de sesión no congela la UI hasta el próximo watchdog.
        if self._last_poll_db_down:
            self._schedule(self._offline_interval_ms, self._tick)
            return
        # Si procesó algo, sigue de inmediato; si no, espera el idle.
        delay = 0 if resultado is not None else self._idle_interval_ms
        self._schedule(delay, self._tick)

    def _emit(self, trabajo_id: int, estado: EstadoTrabajo, error: str | None) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(trabajo_id, estado, error)
        except Exception:  # noqa: BLE001 — un observador roto no debe afectar el loop
            pass
