"""Lo que hay que dejar en su lugar DESPUÉS de cada actualización, solo.

    python -m pos_uniformes.scripts.postactualizacion [--forzar]

Lo llaman `abrir_pos.bat` y `actualizar_pc_principal.bat` al final. Aquí vive
todo lo que no es código: tareas de Windows, servicios que hay que reiniciar
con el código nuevo, limpiezas de cosas viejas. Así Daniel nunca tiene que
correr un instalador a mano cuando cambiamos la infraestructura.

Reglas de la casa:
- **Idempotente**: correrlo dos veces no hace daño (`schtasks /Create /F`).
- **Barato**: si `INFRA_VERSION` no cambió desde la última vez, no toca nada
  (salvo `--forzar`); el reinicio de servicios sí va siempre.
- **Nunca truena**: si algo falla, lo anota en `logs/postactualizacion.log` y
  la actualización sigue. El POS abre igual.
- Fuera de Windows no hace nada (la Mac de desarrollo no tiene schtasks).

**Para agregar un paso nuevo**: si es una tarea de Windows, métela en
`tareas_esperadas()`; si es algo que se retira, en `TAREAS_OBSOLETAS`. Sube
`INFRA_VERSION` y listo: entra sola en la siguiente actualización.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Súbela cuando cambien las tareas de abajo: es lo que dispara el trabajo.
#   1 = vigías cada 5 min (2026-09-09)
#   2 = supervisor único oculto + diarias por correr_oculto.vbs (2026-09-10)
#   3 = "POS Snapshot Casa" también oculta: se creaba directo con
#       programar_snapshot_casa.bat y abría la ventana negra cada 15 min;
#       la limpieza de la v2 no la conocía y la dejó viva (2026-09-12)
INFRA_VERSION = 3

# Tareas que ya no van (las crearon versiones anteriores).
TAREAS_OBSOLETAS = (
    "POS Telegram bot",
    "POS Telegram vigia",
    "POS PWA servidor",
    "POS PWA vigia",
)

# Tarea diaria a hora fija que Daniel pudo haber elegido: si existe, respetamos
# su hora y no ponemos las dos automáticas.
TAREA_RESUMEN_FIJO = "POS Resumen diario"


@dataclass(frozen=True)
class Tarea:
    """Una tarea de Windows, siempre oculta (via correr_oculto.vbs)."""

    nombre: str
    schedule: tuple[str, ...]      # p.ej. ("/SC", "ONLOGON")
    script: str                    # .bat dentro de scripts/
    args: tuple[str, ...] = field(default_factory=tuple)

    def comando(self, scripts_dir: Path) -> list[str]:
        vbs = scripts_dir / "correr_oculto.vbs"
        partes = ["wscript.exe", f'"{vbs}"', self.script, *self.args]
        return ["schtasks", "/Create", "/F", "/TN", self.nombre, *self.schedule, "/TR", " ".join(partes)]


def tareas_esperadas(*, hay_telegram: bool, resumen_a_hora_fija: bool, snapshot_casa: bool = False) -> list[Tarea]:
    """Las tareas que deben existir en esta PC (puro, testeable).

    `snapshot_casa`: la copia de la Libreta a la PC de la casa cada 15 min
    (PWA). Solo se conserva si ya existía: es opcional y la programó Daniel.
    Pase lo que pase, va OCULTA — la versión directa era la ventana negra.
    """
    tareas = [
        Tarea("POS Supervisor", ("/SC", "ONLOGON"), "supervisor.bat"),
        Tarea("POS Supervisor check", ("/SC", "MINUTE", "/MO", "30"), "supervisor.bat"),
    ]
    if snapshot_casa:
        tareas.append(Tarea("POS Snapshot Casa", ("/SC", "MINUTE", "/MO", "15"), "enviar_snapshot_casa.bat"))
    if hay_telegram and not resumen_a_hora_fija:
        # El resumen sale 15 min antes de cerrar; el script decide cuál toca.
        tareas.append(Tarea("POS Resumen 1645", ("/SC", "DAILY", "/ST", "16:45"), "resumen_diario_telegram.bat", ("--si-toca",)))
        tareas.append(Tarea("POS Resumen 1745", ("/SC", "DAILY", "/ST", "17:45"), "resumen_diario_telegram.bat", ("--si-toca",)))
    if hay_telegram:
        tareas.append(Tarea("POS Pendientes", ("/SC", "DAILY", "/ST", "13:30"), "resumen_diario_telegram.bat", ("--pendientes",)))
    return tareas


# ─────────────────────────────────────────────────────────── infraestructura
def _base() -> Path:
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir()


def scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def ruta_version() -> Path:
    return _base() / "data" / "infra_version.txt"


def version_aplicada() -> int:
    try:
        return int(ruta_version().read_text(encoding="utf-8").strip())
    except Exception:  # noqa: BLE001 — nunca aplicada, archivo raro, etc.
        return 0


def marcar_aplicada(version: int = INFRA_VERSION) -> None:
    p = ruta_version()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(version), encoding="utf-8")


def _correr(cmd: list[str], timeout: float = 30.0) -> bool:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def existe_tarea(nombre: str) -> bool:
    return _correr(["schtasks", "/Query", "/TN", nombre], timeout=15)


def borrar_tarea(nombre: str) -> bool:
    return _correr(["schtasks", "/Delete", "/F", "/TN", nombre], timeout=15)


def crear_tarea(t: Tarea) -> bool:
    return _correr(t.comando(scripts_dir()))


def hay_telegram() -> bool:
    try:
        from pos_uniformes.services import telegram_service

        return bool(telegram_service.token_configurado() and telegram_service.chat_id_configurado())
    except Exception:  # noqa: BLE001
        return False


def reiniciar_servicios() -> None:
    """Bot y PWA toman el código nuevo; si el supervisor no corre, se levanta."""
    from pos_uniformes.scripts import supervisor

    supervisor.pedir_reinicio()
    if not sys.platform.startswith("win"):
        return
    vbs = scripts_dir() / "correr_oculto.vbs"
    try:
        subprocess.Popen(
            ["wscript.exe", str(vbs), "supervisor.bat"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001 — el mutex evita duplicados; si falla, la tarea lo levanta
        pass


def aplicar(*, forzar: bool = False) -> list[str]:
    """Deja la infraestructura al día. Devuelve qué hizo (para log/tests)."""
    hechos: list[str] = []
    if not sys.platform.startswith("win"):
        return ["fuera de Windows: nada que hacer"]
    if forzar or version_aplicada() < INFRA_VERSION:
        for nombre in TAREAS_OBSOLETAS:
            if existe_tarea(nombre) and borrar_tarea(nombre):
                hechos.append(f"quitada la tarea vieja: {nombre}")
        fijo = existe_tarea(TAREA_RESUMEN_FIJO)
        # El snapshot a la casa solo se conserva si Daniel ya lo tenía; se
        # recrea con /F por encima de la versión visible (misma /TN).
        snapshot = existe_tarea("POS Snapshot Casa")
        for t in tareas_esperadas(hay_telegram=hay_telegram(), resumen_a_hora_fija=fijo, snapshot_casa=snapshot):
            hechos.append(f"tarea al dia: {t.nombre}" if crear_tarea(t) else f"NO se pudo crear: {t.nombre}")
        marcar_aplicada()
        hechos.append(f"infraestructura en la version {INFRA_VERSION}")
    else:
        hechos.append(f"infraestructura ya en la version {INFRA_VERSION}")
    return hechos


def _log() -> logging.Logger:
    from logging.handlers import RotatingFileHandler

    ruta = _base() / "logs" / "postactualizacion.log"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    h = RotatingFileHandler(ruta, maxBytes=500_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%d/%m %H:%M:%S"))
    log = logging.getLogger("postactualizacion")
    log.setLevel(logging.INFO)
    log.addHandler(h)
    return log


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        log = _log()
    except Exception:  # noqa: BLE001
        log = logging.getLogger("postactualizacion")
    try:
        hechos = aplicar(forzar="--forzar" in argv)
    except Exception as exc:  # noqa: BLE001 — jamás detener la actualización
        log.exception("Postactualizacion")
        print(f"Aviso: no se pudo dejar todo al dia ({exc}). El POS abre igual.")
        return 0
    for h in hechos:
        log.info(h)
        print(f"  {h}")
    try:
        reiniciar_servicios()
        print("  bot y PWA se reinician con el codigo nuevo")
    except Exception:  # noqa: BLE001
        log.exception("Reinicio de servicios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
