"""El SQL que correrá la actualización en la caja, EN SECO (alembic --sql). No escribe nada.

Toma la revisión actual de la caja (lectura) o --desde, y genera el SQL hasta la cabeza
de --ref con `alembic upgrade <desde>:<cabeza> --sql` en un proceso aparte con el entorno
LIMPIO (solo PATH/HOME y una URL local de mentira): el modo `--sql` no se conecta, y así
aunque algo fallara no podría tocar producción.

  --ref origin/chore/reorganizacion-repo  (por omisión) lo que bajará la tienda
  --ref HEAD                              ANTES de hacer push de una migración nueva

Las migraciones que leen la base (`get_bind`) truenan en este modo: no quiere decir que
estén mal. Para esas, el ensayo real es `ensayo_migracion.py` (copia local de la caja).

Uso (desde la raíz del repo):
  "$PY" .claude/skills/actualizar-tienda/scripts/migraciones_sql.py --env-file "<env de la caja>" \
      [--ref HEAD] [--desde REV] [--salida <scratchpad>/migracion.sql] [--intentar]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tienda as t  # noqa: E402
from _tienda import _comun  # noqa: E402

URL_DE_MENTIRA = "postgresql+psycopg://nadie@127.0.0.1:1/sin_base"  # solo da el dialecto; --sql no conecta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _comun.agregar_argumentos_db(ap)
    ap.add_argument("--ref", default=t.TRONCO, help="de qué commit salen las migraciones (HEAD antes de un push)")
    ap.add_argument("--desde", help="revisión de partida (si no, se lee de la caja)")
    ap.add_argument("--salida", help="archivo donde guardar el SQL (si no, se imprime)")
    ap.add_argument("--intentar", action="store_true",
                    help="correr aunque haya get_bind (sale el SQL hasta antes de la primera que lo usa)")
    ap.add_argument("--sin-fetch", action="store_true")
    args = ap.parse_args()

    if not args.sin_fetch and (err := t.traer_tronco()):
        print(f"⚠ git fetch falló ({err[:100]}); uso lo último traído.")
    if args.ref != t.TRONCO and not t.es_ancestro(t.TRONCO, args.ref):
        print(f"🛑 {args.ref} no sale del tronco ({t.TRONCO}): primero tráelo (git merge --ff-only).")
        return 1
    migs = t.migraciones(args.ref)
    heads = t.cabezas(migs)
    if len(heads) != 1:
        print(f"🛑 {args.ref} tiene {len(heads)} cabezas ({', '.join(heads)}): hace falta una migración de unión.")
        return 1
    cabeza = heads[0]
    if problema := t.carpeta_igual_a(args.ref):
        print(f"🛑 Alembic lee esta carpeta y {problema}. Usa una carpeta en ese commit, o --ref HEAD tras commitear.")
        return 1

    desde = args.desde
    if not desde:
        from sqlalchemy import text

        engine = _comun.motor(args, solo_lectura=True)
        with engine.connect() as c:
            filas = [r[0] for r in c.execute(text("select version_num from alembic_version"))]
        if len(filas) != 1:
            print(f"🛑 La caja tiene {len(filas)} revisiones ({', '.join(filas)}); revisar a mano.")
            return 1
        desde = filas[0]
    print(f"Caja en {desde} · cabeza de {args.ref}: {cabeza}")
    if desde not in migs:
        print(f"🛑 {desde} no está en {args.ref}: la caja va por otra rama. No actualizar.")
        return 1
    faltan = t.pendientes(migs, [desde], [cabeza])
    if not faltan:
        print("✅ No hay migraciones pendientes: la actualización no cambia la estructura de la base.")
        return 0
    for m in faltan:
        print(f"  - {m.rev}  {m.titulo[:100]}{'  ← get_bind' if m.usa_get_bind else ''}")
    con_bind = [m for m in faltan if m.usa_get_bind]
    if con_bind and not args.intentar:
        print("\n⚠ Estas leen o rellenan datos y NO salen en --sql: "
              + ", ".join(m.rev for m in con_bind)
              + ".\n  Ensayo real: ensayo_migracion.py (copia LOCAL de la caja; nunca createdb -T sobre la caja)."
              "\n  Con --intentar sale el SQL hasta antes de la primera que usa get_bind.")
        return 0

    cmd = [sys.executable, "-m", "alembic", "upgrade", f"{desde}:{cabeza}", "--sql"]
    assert "--sql" in cmd  # este script nunca migra
    r = subprocess.run(cmd, cwd=str(t.RAIZ / "pos_uniformes"), env=t.entorno_alembic(URL_DE_MENTIRA),
                       capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
    sql = r.stdout
    if r.returncode != 0:
        ultima = (r.stderr or "").strip().splitlines()[-1:] or ["?"]
        print(f"✗ alembic --sql no terminó: {ultima[0][:200]}")
        if con_bind:
            print("  Es esperable: hay migraciones con get_bind (ver arriba).")
        if sql.strip():
            print(f"\n-- SQL que alcanzó a salir antes del error (sin COMMIT) --\n{sql}")
        return 1
    sentencias = sum(1 for linea in sql.splitlines() if linea.rstrip().endswith(";"))
    if args.salida:
        Path(args.salida).expanduser().write_text(sql, encoding="utf-8")
        print(f"\nSQL en seco: {sentencias} sentencias → {args.salida}")
    else:
        print(f"\n-- SQL en seco ({sentencias} sentencias) --\n{sql}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
