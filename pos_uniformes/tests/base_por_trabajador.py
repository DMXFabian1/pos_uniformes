"""Una base de prueba propia para cada proceso de pytest-xdist.

Con `-n 6` los seis procesos compartían `pos_uniformes_test`. Las pruebas que
suman una tabla entera (el informe de finanzas suma TODAS las ventas de la
semana) leían las filas que otro proceso tenía escritas en ese momento (las
`TSTA-…` de la prueba de comisiones concurrentes) y fallaban de vez en cuando.

Cómo queda (2026-11-11):

- El controlador de xdist copia `pos_uniformes_test` a una plantilla de la
  corrida: `pos_uniformes_tmp_<epoch>_<azar>_plantilla_test`.
- Cada proceso (gw0, gw1, …) crea su base desde esa plantilla:
  `pos_uniformes_tmp_<epoch>_<azar>_gw0_test`, y la borra al terminar.
- Al final el controlador borra la plantilla y lo que haya quedado de la
  corrida; al empezar, lo de corridas viejas (> 12 h) que alguien mató.
- Sin xdist todo sigue igual: se usa `pos_uniformes_test`.

Los nombres terminan en `_test` y el host es local, así que la red de
`conftest.pytest_configure` no cambia. Este módulo no importa `settings` a
propósito: conftest lo usa antes de que exista.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import time

BASE_FUENTE = "pos_uniformes_test"
PREFIJO = "pos_uniformes_tmp_"
HOSTS_LOCALES = frozenset({"127.0.0.1", "localhost", "::1"})

#: Lo pone el controlador al importar conftest; los procesos lo heredan.
ENV_CORRIDA = "POS_PRUEBAS_CORRIDA"
#: Lo pone xdist en cada proceso antes de importar conftest.
ENV_TRABAJADOR = "PYTEST_XDIST_WORKER"

_PATRON = re.compile(r"^pos_uniformes_tmp_(\d{10})_([0-9a-f]{6})_(gw\d+|plantilla)_test$")
_PATRON_CORRIDA = re.compile(r"^\d{10}_[0-9a-f]{6}$")
_PATRON_TRABAJADOR = re.compile(r"^gw\d+$")

HORAS_PARA_VIEJA = 12
_LLAVE_CANDADO = 0x506F735465737442  # "PosTestB": serializa los CREATE DATABASE


# ── nombres (puro) ─────────────────────────────────────────────────────────


def nueva_corrida(ahora: float | None = None) -> str:
    momento = int(time.time() if ahora is None else ahora)
    return f"{momento:010d}_{secrets.token_hex(3)}"


def _validar_corrida(corrida: str) -> None:
    if not _PATRON_CORRIDA.match(corrida or ""):
        raise ValueError(f"Identificador de corrida inválido: {corrida!r}")


def nombre_plantilla(corrida: str) -> str:
    _validar_corrida(corrida)
    return f"{PREFIJO}{corrida}_plantilla_test"


def nombre_base_trabajador(corrida: str, trabajador: str) -> str:
    _validar_corrida(corrida)
    if not _PATRON_TRABAJADOR.match(trabajador or ""):
        raise ValueError(f"Trabajador de xdist inválido: {trabajador!r}")
    return f"{PREFIJO}{corrida}_{trabajador}_test"


def es_temporal_de_prueba(nombre: str | None) -> bool:
    """Solo los nombres que este módulo arma. Nunca `pos_uniformes_test`."""
    return bool(_PATRON.match(nombre or ""))


def es_de_la_corrida(nombre: str, corrida: str) -> bool:
    return es_temporal_de_prueba(nombre) and nombre.startswith(f"{PREFIJO}{corrida}_")


def es_vieja(nombre: str, ahora: float | None = None, horas: float = HORAS_PARA_VIEJA) -> bool:
    m = _PATRON.match(nombre or "")
    if not m:
        return False
    momento = time.time() if ahora is None else ahora
    return momento - int(m.group(1)) > horas * 3600


def es_base_de_prueba_local(url) -> bool:
    """La base local de prueba: `pos_uniformes_test` o la copia de un proceso.

    Reemplaza a `url.database == "pos_uniformes_test"` en las pruebas que solo
    deben correr en local: con la base por proceso esa comparación las habría
    saltado en silencio.
    """
    if (url.host or "") not in HOSTS_LOCALES:
        return False
    nombre = url.database or ""
    return nombre == BASE_FUENTE or (es_temporal_de_prueba(nombre) and not nombre.endswith("_plantilla_test"))


def base_para_este_proceso(environ=os.environ) -> str:
    """Qué base le toca a este proceso, y deja la corrida anotada en `environ`.

    Idempotente: conftest se puede importar dos veces (`from tests.conftest
    import …`) y debe dar el mismo nombre.
    """
    corrida = environ.get(ENV_CORRIDA)
    if not corrida:
        corrida = environ[ENV_CORRIDA] = nueva_corrida()
    trabajador = environ.get(ENV_TRABAJADOR)
    if not trabajador:
        return BASE_FUENTE
    return nombre_base_trabajador(corrida, trabajador)


# ── operaciones contra el Postgres local ───────────────────────────────────


def _admin(url):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    base = make_url(url) if isinstance(url, str) else url
    if (base.host or "") not in HOSTS_LOCALES:
        raise RuntimeError("Las bases por proceso solo se crean en el Postgres local.")
    return create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")


def _citar(nombre: str) -> str:
    if not (es_temporal_de_prueba(nombre) or nombre == BASE_FUENTE):
        raise ValueError(f"Nombre de base no permitido aquí: {nombre!r}")
    return f'"{nombre}"'


def _ocupada(exc: Exception) -> bool:
    return "is being accessed by other users" in str(exc)


def crear_desde(url, nombre: str, fuente: str, *, intentos: int = 3, espera: float = 0.25) -> None:
    """`CREATE DATABASE nombre TEMPLATE fuente`, con reintentos.

    Postgres rechaza copiar una base mientras alguien está conectado a ella.
    Si `fuente` sigue ocupada (otra carpeta de trabajo corriendo pruebas en
    serie), se copia con pg_dump/pg_restore, que no necesita exclusividad.
    Cada intento ocupado tarda ~5 s (Postgres espera a que se suelte), por eso
    son pocos. `intentos=0` va directo a pg_dump.
    """
    from sqlalchemy import text

    if not es_temporal_de_prueba(nombre):
        raise ValueError(f"Solo se crean bases temporales de prueba: {nombre!r}")
    motor = _admin(url)
    try:
        ultimo: Exception | None = None
        for i in range(intentos):
            try:
                with motor.connect() as conn:
                    conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _LLAVE_CANDADO})
                    try:
                        conn.execute(text(f"CREATE DATABASE {_citar(nombre)} TEMPLATE {_citar(fuente)}"))
                    finally:
                        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LLAVE_CANDADO})
                return
            except Exception as exc:  # noqa: BLE001
                if not _ocupada(exc):
                    raise
                ultimo = exc
                time.sleep(min(espera * (i + 1), 2.0))
        _copiar_con_pg_dump(url, motor, nombre, fuente, ultimo)
    finally:
        motor.dispose()


def _copiar_con_pg_dump(url, motor, nombre: str, fuente: str, causa: Exception | None) -> None:
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    pg_dump, pg_restore = shutil.which("pg_dump"), shutil.which("pg_restore")
    if not (pg_dump and pg_restore):
        raise RuntimeError(
            f"La base {fuente} está ocupada y no hay pg_dump/pg_restore para copiarla."
        ) from causa
    base = make_url(url) if isinstance(url, str) else url
    env = dict(os.environ)
    if base.password:
        env["PGPASSWORD"] = str(base.password)  # solo al hijo; nunca se imprime
    comunes = ["-h", base.host or "127.0.0.1", "-p", str(base.port or 5432), "-U", base.username or "postgres"]
    with motor.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {_citar(nombre)}"))
    volcado = subprocess.run(
        [pg_dump, *comunes, "-Fc", "-d", fuente], env=env, capture_output=True, check=True
    )
    subprocess.run(
        [pg_restore, *comunes, "--no-owner", "-d", nombre], input=volcado.stdout,
        env=env, capture_output=True, check=True,
    )


def borrar(url, nombre: str) -> None:
    from sqlalchemy import text

    if not es_temporal_de_prueba(nombre):
        raise ValueError(f"Solo se borran bases temporales de prueba: {nombre!r}")
    motor = _admin(url)
    try:
        with motor.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {_citar(nombre)} WITH (FORCE)"))
    finally:
        motor.dispose()


def temporales(url) -> list[str]:
    from sqlalchemy import text

    motor = _admin(url)
    try:
        with motor.connect() as conn:
            nombres = conn.execute(
                text("SELECT datname FROM pg_database WHERE datname LIKE :p"), {"p": f"{PREFIJO}%"}
            ).scalars().all()
    finally:
        motor.dispose()
    return sorted(n for n in nombres if es_temporal_de_prueba(n))


def existe(url, nombre: str) -> bool:
    from sqlalchemy import text

    motor = _admin(url)
    try:
        with motor.connect() as conn:
            return bool(conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": nombre}
            ).first())
    finally:
        motor.dispose()


def limpiar(url, *, corrida: str | None = None, ahora: float | None = None) -> list[str]:
    """Borra lo de esta corrida (si se da) y lo viejo de corridas muertas."""
    borradas = []
    for nombre in temporales(url):
        if (corrida and es_de_la_corrida(nombre, corrida)) or es_vieja(nombre, ahora):
            borrar(url, nombre)
            borradas.append(nombre)
    return borradas
