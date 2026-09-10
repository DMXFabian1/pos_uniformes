"""Supervisor del POS en la PC principal: UN solo proceso, oculto, que cuida
al bot de Telegram y al servidor de la PWA.

    python -m pos_uniformes.scripts.supervisor [--reiniciar | --pedir-reinicio]

Sustituye a las cuatro tareas de Windows que corrían cada 5 minutos (cada
una abría una consola un instante y arrancaba Python de cero). Aquí:
- un proceso que duerme y cada 60 s revisa: ¿el bot late? ¿la PWA contesta?
  Si no, mata al pegado y lo levanta (sin ventana). Reintentos con calma:
  no más de uno cada 3 min por servicio.
- candado (mutex): si ya hay un supervisor, el nuevo sale.
- `--reiniciar`: al arrancar reinicia bot y PWA (código nuevo).
- `--pedir-reinicio`: deja una bandera en data/ y sale; el supervisor que ya
  corre la ve en su siguiente vuelta y reinicia ambos. Lo usa la
  actualización, sin abrir nada.
- log en logs/supervisor.log.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

INTERVALO_SEG = 60
CALMA_SEG = 180
NOMBRE_MUTEX = "Global\\POSUniformesSupervisor"
_MUTEX = None


def _base() -> Path:
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir()


def ruta_bandera() -> Path:
    return _base() / "data" / "supervisor.reiniciar"


def pedir_reinicio() -> None:
    p = ruta_bandera()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(time.time()), encoding="utf-8")


def hay_bandera() -> bool:
    p = ruta_bandera()
    if not p.exists():
        return False
    try:
        p.unlink()
    except Exception:  # noqa: BLE001
        pass
    return True


def tomar_candado() -> bool:
    if not sys.platform.startswith("win"):
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.CreateMutexW(None, True, NOMBRE_MUTEX)
    if not handle:
        return True
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return False
    global _MUTEX
    _MUTEX = handle
    return True


class Servicio:
    """Un servicio vigilado: cómo saber si vive y cómo levantarlo/reiniciarlo."""

    def __init__(self, nombre: str, vivo, levantar, reiniciar) -> None:
        self.nombre = nombre
        self.vivo = vivo
        self.levantar = levantar
        self.reiniciar = reiniciar
        self.ultimo_arranque: float = 0.0


def decidir(*, vivo: bool, ultimo_arranque: float, ahora: float, calma: float = CALMA_SEG) -> str:
    """'nada' | 'levantar' | 'esperar' (puro, testeable)."""
    if vivo:
        return "nada"
    if ahora - ultimo_arranque < calma:
        return "esperar"  # acaba de arrancar: darle tiempo
    return "levantar"


def vuelta(servicios: list[Servicio], *, ahora: float | None = None, reiniciar_todo: bool = False, log=None) -> list[str]:
    """Una revisión. Devuelve qué hizo (para log/tests)."""
    ahora = ahora if ahora is not None else time.time()
    hechos: list[str] = []
    for s in servicios:
        try:
            if reiniciar_todo:
                s.reiniciar()
                s.ultimo_arranque = ahora
                hechos.append(f"{s.nombre}: reiniciado")
                continue
            accion = decidir(vivo=s.vivo(), ultimo_arranque=s.ultimo_arranque, ahora=ahora)
            if accion == "levantar":
                s.levantar()
                s.ultimo_arranque = ahora
                hechos.append(f"{s.nombre}: levantado")
        except Exception as exc:  # noqa: BLE001 — un servicio no tumba al supervisor
            hechos.append(f"{s.nombre}: error {exc}")
            if log:
                log.exception("Supervisor: %s", s.nombre)
    return hechos


def servicios_reales() -> list[Servicio]:
    from pos_uniformes.scripts import servidor_pwa_vigia as pwa
    from pos_uniformes.scripts import telegram_bot as bot
    from pos_uniformes.scripts import telegram_bot_vigia as bot_vigia
    from pos_uniformes.services import telegram_service

    lista: list[Servicio] = []
    if telegram_service.token_configurado() and telegram_service.chat_id_configurado():
        def _bot_arriba():
            bot_vigia.matar(bot_vigia._pid_guardado())
            time.sleep(2)
            bot_vigia.levantar()

        lista.append(Servicio("Telegram bot", vivo=bot.latido_fresco, levantar=_bot_arriba, reiniciar=_bot_arriba))

    def _pwa_arriba():
        pwa.matar(pwa._pid_guardado())
        time.sleep(2)
        pwa.levantar()

    lista.append(Servicio("PWA", vivo=lambda: pwa.responde(timeout=3.0), levantar=_pwa_arriba, reiniciar=_pwa_arriba))
    return lista


def _configurar_log() -> logging.Logger:
    from logging.handlers import RotatingFileHandler

    ruta = _base() / "logs" / "supervisor.log"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%d/%m %H:%M:%S")
    h = RotatingFileHandler(ruta, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(fmt)
    log = logging.getLogger("supervisor")
    log.setLevel(logging.INFO)
    log.addHandler(h)
    return log


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--pedir-reinicio" in argv:
        pedir_reinicio()
        print("Reinicio pedido: el supervisor lo hace en su siguiente vuelta.")
        return 0
    if not tomar_candado():
        print("Ya hay un supervisor corriendo; este sale.")
        return 0
    log = _configurar_log()
    servicios = servicios_reales()
    log.info("Supervisor arrancando: %s", ", ".join(s.nombre for s in servicios))
    reiniciar = "--reiniciar" in argv
    while True:
        hechos = vuelta(servicios, reiniciar_todo=reiniciar or hay_bandera(), log=log)
        reiniciar = False
        for h in hechos:
            log.info(h)
        try:
            time.sleep(INTERVALO_SEG)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
