"""Ensayo REAL de las migraciones pendientes en una COPIA LOCAL de la caja. A la caja solo la LEE.

Para las migraciones que rellenan o leen datos (`get_bind`), que no salen en `--sql`:
  1. `pg_dump -Fc` de la caja (solo lectura; pesa unos 33 MB) a --carpeta (el scratchpad).
  2. Base nueva en el Postgres LOCAL de la Mac (nombre único) y `pg_restore` ahí.
  3. `alembic upgrade <cabeza>` contra la copia, en un proceso con entorno limpio cuya URL
     apunta a localhost (se aborta si el host no es local).
  4. Revisión final de la copia y, por cada migración, lo que imprimió. Se borran la copia
     y el dump (trae datos personales), salvo --conservar.

Uso (desde la raíz del repo, con la carpeta en el commit de --ref):
  "$PY" .claude/skills/actualizar-tienda/scripts/ensayo_migracion.py --env-file "<env de la caja>" \
      --carpeta <scratchpad> [--ref HEAD] [--conservar]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tienda as t  # noqa: E402
from _tienda import _comun  # noqa: E402

LOCALES = {"localhost", "127.0.0.1", "::1"}


def _bin(nombre: str) -> str:
    ruta = shutil.which(nombre) or f"/Applications/Postgres.app/Contents/Versions/latest/bin/{nombre}"
    if not Path(ruta).exists():
        raise SystemExit(f"ERROR: no encuentro {nombre} (Postgres.app).")
    return ruta


def _correr(cmd: list[str], env: dict[str, str], timeout: float = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def _url_local():
    """La base local de la Mac según la config del proyecto, SIN el env de la caja."""
    from sqlalchemy.engine import make_url

    from pos_uniformes.utils.config import Settings

    url = make_url(Settings.from_env().database_url)
    if url.host not in LOCALES:
        raise SystemExit(f"🛑 La config local apunta a {url.host}, no a esta Mac. No ensayo.")
    return url


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", required=True, help="env de la caja (solo para LEERLA con pg_dump)")
    ap.add_argument("--carpeta", required=True, help="dónde dejar el dump (el scratchpad)")
    ap.add_argument("--ref", default=t.TRONCO, help="commit cuyas migraciones se ensayan (HEAD antes de un push)")
    ap.add_argument("--conservar", action="store_true", help="no borrar la copia ni el dump al terminar")
    ap.add_argument("--sin-fetch", action="store_true")
    args = ap.parse_args()

    if not args.sin_fetch and (err := t.traer_tronco()):
        print(f"⚠ git fetch falló ({err[:100]}); uso lo último traído.")
    if args.ref != t.TRONCO and not t.es_ancestro(t.TRONCO, args.ref):
        print(f"🛑 {args.ref} no sale del tronco: primero tráelo.")
        return 1
    migs = t.migraciones(args.ref)
    heads = t.cabezas(migs)
    if len(heads) != 1:
        print(f"🛑 {args.ref} tiene {len(heads)} cabezas: hace falta una migración de unión.")
        return 1
    if problema := t.carpeta_igual_a(args.ref):
        print(f"🛑 Alembic lee esta carpeta y {problema}.")
        return 1

    caja = t.leer_env(args.env_file)  # NO va a os.environ
    host = caja.get("POS_UNIFORMES_DB_HOST") or caja.get("POS_UNIFORMES_SERVER_HOST")
    if not host:
        print("🛑 El env no trae POS_UNIFORMES_DB_HOST.")
        return 1
    local = _url_local()
    if host in LOCALES:
        print("🛑 El env dado apunta a esta Mac, no a la caja.")
        return 1

    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    copia = f"pos_ensayo_{sello}"
    carpeta = Path(args.carpeta).expanduser()
    carpeta.mkdir(parents=True, exist_ok=True)
    dump = carpeta / f"caja_{sello}.dump"
    env_caja = {"PATH": "/usr/bin:/bin", "PGPASSWORD": caja.get("POS_UNIFORMES_DB_PASSWORD", ""),
                "PGCONNECT_TIMEOUT": "10"}
    env_local = {"PATH": "/usr/bin:/bin", "PGPASSWORD": local.password or ""}
    puerto_local = str(local.port or 5432)
    hecho_db = False
    try:
        print(f"1) Copiando la caja ({host}) en modo lectura → {dump.name}")
        r = _correr([_bin("pg_dump"), "-Fc", "--no-owner", "-h", host,
                     "-p", caja.get("POS_UNIFORMES_DB_PORT", "5432"),
                     "-U", caja.get("POS_UNIFORMES_DB_USER", "postgres"),
                     "-d", caja.get("POS_UNIFORMES_DB_NAME", "pos_uniformes"), "-f", str(dump)], env_caja)
        if r.returncode != 0:
            print(f"✗ pg_dump falló: {r.stderr.strip()[:300]}")
            return 1
        print(f"   {dump.stat().st_size / 1e6:.1f} MB")

        print(f"2) Base local {copia} en {local.host}:{puerto_local}")
        base_local = ["-h", local.host, "-p", puerto_local, "-U", local.username or "postgres"]
        r = _correr([_bin("createdb"), *base_local, copia], env_local)
        if r.returncode != 0:
            print(f"✗ createdb falló: {r.stderr.strip()[:300]}")
            return 1
        hecho_db = True
        r = _correr([_bin("pg_restore"), "--no-owner", "--no-privileges", *base_local, "-d", copia, str(dump)],
                    env_local)
        if r.returncode != 0:
            # pg_restore da 1 con avisos menores (extensiones, roles); se reporta y se sigue.
            print(f"   (avisos de pg_restore: {r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else '?'})")

        url_copia = local.set(database=copia)
        assert url_copia.host in LOCALES and url_copia.database == copia
        cmd = [sys.executable, "-m", "alembic", "upgrade", heads[0]]
        print(f"3) alembic upgrade {heads[0]} contra {url_copia.host}/{copia}")
        r = subprocess.run(cmd, cwd=str(t.RAIZ / "pos_uniformes"),
                           env=t.entorno_alembic(url_copia.render_as_string(hide_password=False)),
                           capture_output=True, text=True, timeout=1800, stdin=subprocess.DEVNULL)
        salida = (r.stdout + r.stderr).strip()
        for linea in salida.splitlines():
            if "Running upgrade" in linea or "Error" in linea or "rror:" in linea or not linea.startswith("INFO"):
                print(f"   {linea[:220]}")
        if r.returncode != 0:
            print("✗ La migración FALLÓ en la copia: en la tienda también fallaría (y actualizar.py"
                  " regresaría el código sin publicar). Corregir antes de subir.")
            return 1

        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import NullPool

        motor = create_engine(url_copia, poolclass=NullPool)  # sin pool: si no, dropdb no puede borrarla
        with motor.connect() as c:
            rev = c.execute(text("select version_num from alembic_version")).scalar()
        motor.dispose()
        corridas = sum(1 for linea in salida.splitlines() if "Running upgrade" in linea)
        if corridas:
            print(f"4) ✅ {corridas} migración(es) corrieron limpias sobre los datos de hoy; la copia quedó en {rev}.")
        else:
            print(f"4) No había migraciones pendientes: la copia (= la caja) ya estaba en {rev}.")
        return 0
    finally:
        if not args.conservar:
            dump.unlink(missing_ok=True)
            if hecho_db:
                r = _correr([_bin("dropdb"), "--force", "-h", local.host, "-p", puerto_local,
                             "-U", local.username or "postgres", copia], env_local)
                if r.returncode != 0:
                    print(f"   ⚠ NO se pudo borrar la copia local {copia} (trae datos de la caja):"
                          f" {r.stderr.strip()[:160]}. Bórrala con dropdb.")
                else:
                    print("   (copia local y dump borrados)")
            else:
                print("   (dump borrado)")
        else:
            print(f"   (se conservan: base local {copia} y {dump})")


if __name__ == "__main__":
    raise SystemExit(main())
