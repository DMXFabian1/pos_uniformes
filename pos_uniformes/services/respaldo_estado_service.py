"""¿Hay respaldo de hoy, y sirve?

Separado de `backup_service` (que *hace* el respaldo) porque esto solo *mira*:
lee el archivo de estado que dejó la tarea y los dumps de la carpeta, y decide
si hay que molestar a alguien. Sin DB y sin red, para poder probarlo.

Existe por un hueco encontrado el 01/10, antes de que Daniel se fuera una
semana: `run_scheduled_backup.py` estaba escrito desde siempre y **nada lo
corría** — no había tarea ni instalador. Un respaldo que nadie dispara no es un
respaldo. Y peor: si la tarea se borra o la PC pasa días apagada, nada falla y
por lo tanto nada avisa. El silencio se veía igual que el éxito.

De ahí las dos vigilancias, a propósito por caminos distintos:

1. La tarea del respaldo avisa cuando **truena** (lo sabe en el momento).
2. El bot avisa cuando el último respaldo está **viejo** (lo nota aunque la
   tarea no haya corrido nunca).

Si las dos colgaran del mismo proceso, un proceso caído se llevaría también la
manera de enterarse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

#: Arriba de esto el respaldo ya es viejo y se avisa. Dos días deja pasar un
#: domingo cerrado sin dar lata, y no deja pasar una semana muerta.
DIAS_PARA_AVISAR = 2

#: Un dump bueno de esta tienda pesa cientos de KB. Mucho menos que esto
#: significa que `pg_dump` escribió algo que no es la base (pasó con una
#: contraseña mal puesta: 0 bytes y «éxito»).
MINIMO_CREIBLE_BYTES = 50 * 1024


@dataclass(frozen=True)
class EstadoRespaldo:
    """Lo que se sabe del último respaldo, ya interpretado."""

    ultimo: datetime | None
    archivo: Path | None
    tamano: int = 0
    error: str | None = None
    copia_externa: Path | None = None
    error_externa: str | None = None

    @property
    def dias(self) -> int | None:
        """Días desde el último respaldo bueno. None si nunca hubo uno."""
        if self.ultimo is None:
            return None
        delta = datetime.now(timezone.utc) - _aware(self.ultimo)
        return max(0, int(delta.total_seconds() // 86400))

    @property
    def al_dia(self) -> bool:
        if self.ultimo is None:
            return False
        if self.sospechoso:
            return False
        return _aware(self.ultimo) > datetime.now(timezone.utc) - timedelta(days=DIAS_PARA_AVISAR)

    @property
    def sospechoso(self) -> bool:
        """Hay archivo, dice que salió bien, pero pesa lo que no debe pesar."""
        return self.archivo is not None and 0 <= self.tamano < MINIMO_CREIBLE_BYTES


def _aware(momento: datetime) -> datetime:
    """Sin zona = hora local, no UTC.

    `list_backups` saca la fecha con `datetime.fromtimestamp`, que da hora local
    sin zona. Tomarla por UTC dejaría un respaldo de hace un rato "en el
    futuro" y lo daría por bueno seis horas de más.
    """
    return momento if momento.tzinfo else momento.astimezone()


def leer_estado(output_dir: Path | None = None) -> EstadoRespaldo:
    """Junta el archivo de estado con lo que de verdad hay en la carpeta.

    El archivo de estado puede mentir por omisión (quedó de una versión vieja,
    o alguien borró los dumps a mano), así que el que manda es el dump que
    todavía existe en el disco.
    """
    from pos_uniformes.services.backup_service import (
        backup_output_dir,
        list_backups,
        read_automatic_backup_status,
    )

    carpeta = (output_dir or backup_output_dir())
    try:
        status = read_automatic_backup_status(carpeta)
    except Exception:  # noqa: BLE001 — estado ilegible = como si no hubiera
        status = None
    try:
        dumps = list_backups(carpeta)
    except Exception:  # noqa: BLE001
        dumps = []

    archivo: Path | None = None
    tamano = 0
    ultimo: datetime | None = None
    if dumps:
        # list_backups ordena; se toma el más reciente por fecha de archivo.
        mejor = max(dumps, key=lambda e: getattr(e, "modified_at", None) or datetime.min)
        archivo = getattr(mejor, "path", None)
        tamano = int(getattr(mejor, "size_bytes", 0) or 0)
        ultimo = getattr(mejor, "modified_at", None)
    if status is not None and status.last_success_at is not None:
        # Si el estado dice algo más reciente que el archivo, se cree al archivo:
        # lo que importa es que el dump EXISTA, no que un día se haya hecho.
        if ultimo is None:
            ultimo = status.last_success_at
    return EstadoRespaldo(
        ultimo=ultimo,
        archivo=archivo,
        tamano=tamano,
        error=(status.last_error if status is not None else None),
        copia_externa=(status.external_copy_dir if status is not None else None),
        error_externa=(status.external_last_error if status is not None else None),
    )


# ── Lo que se dice ───────────────────────────────────────────────────────────


def texto_sin_respaldo(estado: EstadoRespaldo) -> str:
    """El aviso de que el respaldo no está al día. Dice qué se perdería."""
    if estado.ultimo is None:
        return (
            "🛑 No hay ningún respaldo de la base.\n\n"
            "Una falla de disco hoy se lleva TODO: catálogo, ventas, cortes, conteos.\n"
            "En la tienda: scripts\\respaldo_diario.bat"
        )
    if estado.sospechoso:
        return (
            f"🛑 El respaldo de hoy pesa {estado.tamano // 1024} KB — eso no es la base.\n\n"
            "Dice que salió bien, pero un archivo así no se puede restaurar.\n"
            "Revísalo con scripts\\revisar_respaldos.bat"
        )
    dias = estado.dias or 0
    cuando = "ayer" if dias == 1 else f"hace {dias} días"
    aviso = (
        f"⚠️ El último respaldo es de {cuando}.\n\n"
        f"Si la base se pierde hoy, se pierden {dias} "
        f"{'día' if dias == 1 else 'días'} de trabajo."
    )
    if estado.error:
        aviso += f"\n\nEl último intento falló: {estado.error}"
    return aviso


def texto_fallo(error: str) -> str:
    """Lo que se manda cuando el respaldo de hoy truena."""
    return (
        f"🛑 El respaldo de hoy NO salió.\n\n{error}\n\n"
        "Mientras no salga, la base vive en un solo disco."
    )


def texto_volvio(estado: EstadoRespaldo) -> str:
    """Cuando vuelve a salir tras haber fallado: se dice, para cerrar el tema."""
    tamano = f"{estado.tamano // 1024} KB" if estado.tamano else "listo"
    return f"✅ El respaldo volvió a salir ({tamano})."


def texto_resumen(estado: EstadoRespaldo) -> str:
    """Una línea para el resumen diario o el reporte, siempre legible."""
    if estado.ultimo is None:
        return "Respaldo: ninguno. ⚠️"
    dias = estado.dias or 0
    cuando = "hoy" if dias == 0 else ("ayer" if dias == 1 else f"hace {dias} días")
    marca = "✅" if estado.al_dia else "⚠️"
    linea = f"Respaldo: {cuando} {marca}"
    if estado.sospechoso:
        linea += f" (solo {estado.tamano // 1024} KB)"
    if estado.error_externa:
        linea += " · la copia aparte falló"
    elif estado.copia_externa is not None:
        linea += " · con copia aparte"
    return linea
