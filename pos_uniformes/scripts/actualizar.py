"""Actualizar la tienda con cuidado: build → respaldo → migraciones → publicar.

    python -m pos_uniformes.scripts.actualizar [--al-abrir] [--traer] [--volver] [--estado]

Lo llaman `actualizar_pc_principal.bat`, `abrir_pos.bat`, el bot (`/actualizar`)
y, si se enciende, la tarea de la noche. Antes cada `.bat` hacía sus pasos a
mano y en este orden: traer → migrar → build. Tres huecos (Daniel, 2026-11-06:
«¿el sistema de actualizaciones tiene rango de mejora?» → «hazlo completo»):

1. **Se migraba sin respaldo.** Ahora, si hay migraciones pendientes, primero
   se respalda la base; sin respaldo NO se migra.
2. **Si el build fallaba, la base ya había cambiado** y los kioskos se quedaban
   con el programa viejo («Base de datos no lista»). Ahora el build va primero
   y sin publicar; solo si sale bien se migra, y solo entonces se publica.
3. **No había vuelta atrás.** Si algo falla antes de publicar, el código
   regresa al commit que corren los kioskos (`git reset --keep`: nunca pisa
   cambios locales). Y la versión anterior de los kioskos se guarda junto a la
   nueva: `--volver` las intercambia y deja la publicación en pausa hasta que
   llegue un commit distinto.

Pase lo que pase, avisa por Telegram cómo terminó: el silencio no es éxito.

Todo lo que toca el mundo (git, PowerShell, pg_dump, Telegram) entra por
`Mundo`, para poder probar el orden y las decisiones en la Mac.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# Qué pasó, en una palabra (para las pruebas y para el código de salida).
AL_DIA = "al_dia"
ACTUALIZADO = "actualizado"
EN_PAUSA = "en_pausa"
SIN_BASE = "sin_base"
FALLO_TRAER = "fallo_traer"
FALLO_BUILD = "fallo_build"
FALLO_RESPALDO = "fallo_respaldo"
FALLO_MIGRACION = "fallo_migracion"
FALLO_PUBLICAR = "fallo_publicar"
YA_HABIA_FALLADO = "ya_habia_fallado"

_BIEN = (AL_DIA, ACTUALIZADO, EN_PAUSA)


@dataclass(frozen=True)
class Resultado:
    que: str
    texto: str                      # lo que se dice en pantalla y por Telegram
    pasos: tuple[str, ...] = ()     # lo que sí se hizo, en orden

    @property
    def ok(self) -> bool:
        return self.que in _BIEN


@dataclass
class Mundo:
    """Las manos del actualizador. Cada una se cambia en las pruebas."""

    commit_actual: Callable[[], str]
    hay_share: Callable[[], bool]
    commit_publicado: Callable[[], str | None]
    migraciones_pendientes: Callable[[], bool]      # truena si no hay base
    construir: Callable[[], bool]
    respaldar: Callable[[], Path]                   # truena si no salió
    migrar: Callable[[], bool]
    publicar: Callable[[], bool]
    volver_a: Callable[[str], bool]
    existe_commit: Callable[[str], bool]
    cambios_entre: Callable[[str, str], int]
    version_de: Callable[[], str]
    avisar: Callable[[str], None]
    leer_marca: Callable[[str], str]
    escribir_marca: Callable[[str, str], None]
    traer: Callable[[], bool] = lambda: True
    decir: Callable[[str], None] = print
    hechos: list[str] = field(default_factory=list)


# Las marcas viven en data/ de la PC principal.
MARCA_FALLIDA = "actualizacion_fallida.txt"     # commit que no se pudo aplicar
MARCA_PAUSA = "kioskos_en_pausa.txt"            # commit que NO se publica (se volvió atrás)


def _mismo(a: str | None, b: str | None) -> bool:
    """Dos claves de commit son la misma aunque una sea más corta."""
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))


def actualizar(m: Mundo, *, al_abrir: bool = False, traer: bool = False) -> Resultado:
    """Deja la tienda en el código de ahora, o en el de antes. Nunca a medias."""
    pasos: list[str] = []

    def _fin(que: str, texto: str, *, avisar: bool = True) -> Resultado:
        m.decir(texto)
        if avisar:
            m.avisar(texto)
        return Resultado(que, texto, tuple(pasos))

    if traer:
        m.decir("Trayendo lo nuevo del repositorio...")
        if not m.traer():
            return _fin(
                FALLO_TRAER,
                "🛑 Actualización: no se pudo traer lo nuevo (¿sin internet, o cambios locales "
                "que chocan?). No se tocó nada.",
            )
        pasos.append("traer")

    ahora = m.commit_actual()
    publicado = m.commit_publicado() if m.hay_share() else None
    antes = publicado if publicado and not _mismo(publicado, ahora) and m.existe_commit(publicado) else None

    try:
        pendientes = m.migraciones_pendientes()
    except Exception as exc:  # noqa: BLE001 — sin base no se decide nada
        return _fin(
            SIN_BASE,
            f"🛑 Actualización: no se pudo hablar con la base ({exc}). No se tocó nada.",
        )

    pausa = m.leer_marca(MARCA_PAUSA)
    if pausa and not _mismo(pausa, ahora):
        m.escribir_marca(MARCA_PAUSA, "")        # llegó un commit distinto: se acabó la pausa
        pausa = ""
    falta_publicar = m.hay_share() and not _mismo(publicado, ahora) and not pausa

    if not pendientes and not falta_publicar:
        if pausa:
            return _fin(
                EN_PAUSA,
                f"⏸ Los kioskos siguen en la versión anterior: {ahora} está en pausa "
                "(se volvió atrás). Se publica sola cuando llegue un cambio nuevo.",
                avisar=False,
            )
        return _fin(AL_DIA, f"Ya está al día ({m.version_de()}).", avisar=False)

    def _regresar(motivo: str) -> str:
        """El código vuelve a donde estaban los kioskos. Devuelve qué decir."""
        m.escribir_marca(MARCA_FALLIDA, ahora)
        if antes is None:
            return "El código se quedó en lo nuevo (no se sabe cuál era el anterior)."
        if m.volver_a(antes):
            pasos.append("volver")
            return f"El código regresó a {antes}, lo que corren los kioskos."
        return (
            f"⚠️ No se pudo regresar el código a {antes} ({motivo}): revisar en la tienda "
            "con scripts\\revisar_actualizacion.bat."
        )

    # Al abrir el POS no se vuelve a intentar lo que ya falló: son minutos de
    # build cada vez. Se reintenta a mano, con actualizar_pc_principal.bat.
    if al_abrir and _mismo(m.leer_marca(MARCA_FALLIDA), ahora):
        cola = _regresar("ya había fallado")
        return _fin(
            YA_HABIA_FALLADO,
            f"⚠️ La actualización a {ahora} ya había fallado y no se reintenta al abrir. "
            f"{cola} Para reintentar: scripts\\actualizar_pc_principal.bat.",
            avisar=False,
        )

    # 1 — El build primero y sin publicar: si no sale, no se ha tocado nada.
    if falta_publicar:
        m.decir("Build del kiosko (unos minutos; todavía no se publica)...")
        if not m.construir():
            cola = _regresar("falló el build")
            return _fin(
                FALLO_BUILD,
                f"🛑 Actualización a {ahora}: falló el build del kiosko. La base NO se tocó y los "
                f"kioskos siguen igual. {cola}",
            )
        pasos.append("build")

    # 2 — Respaldo, y solo entonces migrar.
    respaldo: Path | None = None
    if pendientes:
        m.decir("Respaldando la base antes de migrar...")
        try:
            respaldo = m.respaldar()
        except Exception as exc:  # noqa: BLE001
            cola = _regresar("falló el respaldo")
            return _fin(
                FALLO_RESPALDO,
                f"🛑 Actualización a {ahora}: no salió el respaldo ({exc}) y sin respaldo no se "
                f"migra. La base NO se tocó. {cola}",
            )
        pasos.append("respaldo")
        m.decir("Aplicando migraciones...")
        if not m.migrar():
            cola = _regresar("falló la migración")
            return _fin(
                FALLO_MIGRACION,
                f"🛑 Actualización a {ahora}: falló una migración. Los kioskos NO se publicaron. "
                f"El respaldo de antes está en {respaldo}. {cola}",
            )
        pasos.append("migrar")

    # 3 — Publicar al final: los kioskos nunca reciben un programa sin su base.
    if falta_publicar:
        m.decir("Publicando a los kioskos (se guarda la versión anterior)...")
        if not m.publicar():
            m.escribir_marca(MARCA_FALLIDA, "")      # el código nuevo es el bueno: la base ya migró
            return _fin(
                FALLO_PUBLICAR,
                f"⚠️ Actualización a {ahora}: la base quedó al día pero NO se pudo publicar a los "
                "kioskos (siguen con la versión anterior, que abre igual). Se reintenta al "
                "abrir el POS.",
            )
        pasos.append("publicar")

    m.escribir_marca(MARCA_FALLIDA, "")
    renglones = [f"✅ Tienda actualizada a {m.version_de()}."]
    if antes is not None:
        n = m.cambios_entre(antes, ahora)
        if n > 0:
            renglones[0] = f"✅ Tienda actualizada a {m.version_de()} ({n} cambio{'s' if n != 1 else ''})."
    if respaldo is not None:
        renglones.append(f"• Base: migraciones aplicadas (respaldo antes: {Path(respaldo).name})")
    else:
        renglones.append("• Base: sin cambios")
    if "publicar" in pasos:
        renglones.append("• Kioskos: publicado; se actualizan solos al abrir")
    elif pausa:
        renglones.append("• Kioskos: en pausa (se volvió a la versión anterior)")
    return _fin(ACTUALIZADO, "\n".join(renglones))


# ─────────────────────────────────────────────── volver a la versión anterior

def volver_kioskos(
    *, carpeta: Path, commit_actual: str, escribir_marca: Callable[[str, str], None],
    avisar: Callable[[str], None], decir: Callable[[str], None] = print,
) -> tuple[bool, str]:
    """Intercambia lo publicado con la versión anterior. Los kioskos la toman al abrir.

    La base no se regresa: un kiosko más viejo que la base abre igual
    (`assert_database_ready` lo deja pasar desde el 2026-09-22). Y la
    publicación queda en pausa para este commit: si no, el siguiente
    «abrir POS» vería que lo publicado no es lo de ahora y lo republicaría."""
    actual = carpeta / "PresupuestosSatelite"
    anterior = carpeta / "PresupuestosSatelite_anterior"
    if not (anterior / "VERSION.txt").exists():
        texto = "No hay una versión anterior guardada: se guarda a partir de la siguiente actualización."
        decir(texto)
        return False, texto
    vuelve_a = (anterior / "VERSION.txt").read_text(encoding="utf-8").strip()
    temporal = carpeta / "PresupuestosSatelite_cambio"
    try:
        if temporal.exists():
            import shutil

            shutil.rmtree(temporal)
        actual.rename(temporal)
        try:
            anterior.rename(actual)
        except Exception:
            temporal.rename(actual)              # como estaba
            raise
        temporal.rename(anterior)
    except Exception as exc:  # noqa: BLE001
        texto = (
            f"🛑 No se pudo volver a la versión anterior ({exc}). ¿Un kiosko está copiando "
            "ahora mismo? Espera un minuto y vuelve a intentar."
        )
        decir(texto)
        avisar(texto)
        return False, texto
    escribir_marca(MARCA_PAUSA, commit_actual)
    texto = (
        f"↩ Los kioskos vuelven a la versión {vuelve_a}: la toman al abrir (o con «Buscar "
        f"actualizaciones»). La publicación de {commit_actual} queda en pausa hasta que llegue "
        "un cambio nuevo. Para deshacer esto, corre de nuevo volver_version_anterior.bat."
    )
    decir(texto)
    avisar(texto)
    return True, texto


# ───────────────────────────────────────────────────────── el mundo de verdad

def _raiz_repo() -> Path:
    return Path(__file__).resolve().parents[2]


def _base_pos() -> Path:
    return Path(__file__).resolve().parents[1]


def carpeta_updates() -> Path:
    return Path(os.getenv("POS_UNIFORMES_UPDATES_DIR") or r"C:\pos_updates")


def _git(*args: str, timeout: float = 120.0) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", *args], cwd=str(_raiz_repo()), capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)
    return r.returncode, (r.stdout or "").strip() or (r.stderr or "").strip()


def _a_la_vista(cmd: list[str], *, cwd: Path, timeout: float) -> bool:
    """Corre algo largo dejando ver lo que escribe (y que el .bat lo guarde en su log)."""
    try:
        return subprocess.run(cmd, cwd=str(cwd), timeout=timeout, stdin=subprocess.DEVNULL).returncode == 0
    except Exception as exc:  # noqa: BLE001
        print(f"*** No se pudo correr {cmd[0]}: {exc}")
        return False


def _powershell(script: str, *args: str, timeout: float) -> bool:
    return _a_la_vista(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(_base_pos() / "scripts" / script), *args],
        cwd=_base_pos(), timeout=timeout,
    )


def _commit_publicado() -> str | None:
    try:
        texto = (carpeta_updates() / "PresupuestosSatelite" / "VERSION.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return texto.rsplit("+", 1)[-1].strip() or None if "+" in texto else None


def _migraciones_pendientes() -> bool:
    from pos_uniformes.database.preflight import inspect_database_status

    estado = inspect_database_status()
    return not estado.is_up_to_date and not estado.base_adelante


def _respaldar() -> Path:
    from pos_uniformes.services.backup_service import create_backup

    # El mismo formato y la misma carpeta que el respaldo de cada noche.
    archivo, _borrados = create_backup(dump_format="custom", retention_days=14)
    if not archivo.exists() or archivo.stat().st_size < 1024:
        raise RuntimeError(f"el archivo {archivo.name} quedó vacío")
    return archivo


def _ruta_marca(nombre: str) -> Path:
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / nombre


def _leer_marca(nombre: str) -> str:
    try:
        return _ruta_marca(nombre).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _escribir_marca(nombre: str, valor: str) -> None:
    ruta = _ruta_marca(nombre)
    try:
        if not valor:
            ruta.unlink(missing_ok=True)
            return
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(valor, encoding="utf-8")
    except OSError as exc:
        print(f"(no se pudo anotar {nombre}: {exc})")


def _avisar(texto: str) -> None:
    """Por Telegram, si está configurado. Si no sale, se dice: el silencio no es éxito."""
    try:
        from pos_uniformes.services import telegram_service

        if not (telegram_service.token_configurado() and telegram_service.chat_id_configurado()):
            return
        telegram_service.enviar_mensaje(texto, conservar=True)
    except Exception as exc:  # noqa: BLE001
        print(f"(no se pudo avisar por Telegram: {exc})")


def _version_de() -> str:
    try:
        from pos_uniformes.utils import app_metadata

        app_metadata._sello_de_git.cache_clear()       # el commit pudo cambiar en esta corrida
        return app_metadata.version_visible()
    except Exception:  # noqa: BLE001
        return _git("rev-parse", "--short", "HEAD")[1]


def mundo_real() -> Mundo:
    return Mundo(
        commit_actual=lambda: _git("rev-parse", "--short", "HEAD")[1],
        hay_share=lambda: carpeta_updates().exists(),
        commit_publicado=_commit_publicado,
        migraciones_pendientes=_migraciones_pendientes,
        construir=lambda: _powershell("build_presupuestos_satelite_windows.ps1", "-SinPublicar", timeout=45 * 60),
        respaldar=_respaldar,
        migrar=lambda: _a_la_vista(
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=_base_pos(), timeout=15 * 60
        ),
        publicar=lambda: _powershell("publicar_satelite.ps1", timeout=20 * 60),
        volver_a=lambda commit: _git("reset", "--keep", commit)[0] == 0,
        existe_commit=lambda commit: _git("cat-file", "-e", f"{commit}^{{commit}}")[0] == 0,
        cambios_entre=lambda a, b: int(_git("rev-list", "--count", f"{a}..{b}")[1] or 0)
        if _git("rev-list", "--count", f"{a}..{b}")[0] == 0 else 0,
        version_de=_version_de,
        avisar=_avisar,
        leer_marca=_leer_marca,
        escribir_marca=_escribir_marca,
        traer=lambda: _git("pull", "--ff-only", timeout=300)[0] == 0,
    )


def estado_en_texto(m: Mundo) -> str:
    """Para `/version` y `--estado`: qué trae la principal y qué corren los kioskos."""
    ahora = m.commit_actual()
    renglones = [f"PC principal: {m.version_de()}"]
    if m.hay_share():
        publicado = m.commit_publicado()
        if publicado is None:
            renglones.append("Kioskos: todavía no hay nada publicado")
        elif _mismo(publicado, ahora):
            renglones.append("Kioskos: publicada la misma versión")
        else:
            renglones.append(f"Kioskos: publicada {publicado} (distinta de la principal)")
    if _mismo(m.leer_marca(MARCA_PAUSA), ahora):
        renglones.append("⏸ Publicación en pausa: se volvió a la versión anterior")
    if _mismo(m.leer_marca(MARCA_FALLIDA), ahora):
        renglones.append("⚠️ La última actualización falló")
    return "\n".join(renglones)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Actualiza la tienda con respaldo y vuelta atrás.")
    p.add_argument("--al-abrir", action="store_true", help="lo llama abrir_pos.bat: no reintenta lo que ya falló")
    p.add_argument("--traer", action="store_true", help="hace el git pull aquí (el bot y la tarea de la noche)")
    p.add_argument("--volver", action="store_true", help="los kioskos vuelven a la versión anterior")
    p.add_argument("--estado", action="store_true", help="solo dice en qué versión está cada cosa")
    args = p.parse_args(argv)

    m = mundo_real()
    if args.estado:
        print(estado_en_texto(m))
        return 0
    if args.volver:
        ok, _texto = volver_kioskos(
            carpeta=carpeta_updates(), commit_actual=m.commit_actual(),
            escribir_marca=m.escribir_marca, avisar=m.avisar,
        )
        return 0 if ok else 1
    try:
        return 0 if actualizar(m, al_abrir=args.al_abrir, traer=args.traer).ok else 1
    finally:
        # Si la arrancó el bot (/actualizar), ya puede arrancarse otra.
        try:
            from pos_uniformes.services.telegram_actualizar_service import quitar_candado

            quitar_candado()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
