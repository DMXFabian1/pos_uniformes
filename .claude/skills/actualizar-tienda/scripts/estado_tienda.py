"""¿Qué le falta a la tienda? (o, con --esperado, ¿quedó bien la actualización?). SOLO LECTURA.

Compara el tronco de GitHub (origin/chore/reorganizacion-repo, tras un `git fetch`) con:
  - la revisión de Alembic de la caja (`alembic_version`) → migraciones pendientes;
  - la versión que late cada PC en `satelite` (kioskos y servidor de impresión) → commits
    atrás y si ese programa conoce la revisión de la caja (si no, NO abre);
  - señales del bot (cola de `alerta_telegram`) y de impresión atorada (`trabajo`).

La PC principal (POS) y el bot NO laten en `satelite`: su versión se pide con /version.

Uso (desde la raíz del repo):
  "$PY" .claude/skills/actualizar-tienda/scripts/estado_tienda.py --env-file "<env de la caja>"
  "$PY" .claude/skills/actualizar-tienda/scripts/estado_tienda.py --env-file … --esperado 12842fea
Sale con 1 si con --esperado algo no cuadra (o si no hay base).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tienda as t  # noqa: E402
from _tienda import _comun  # noqa: E402

from sqlalchemy import text  # noqa: E402

UMBRAL_ONLINE_SEG = 150          # igual que services/satelite_registry_service.py
ATORADO_MIN = 15                 # igual que trabajos_service (TICKET, CORTE, ETIQUETA, CONTEO)


def _consulta(engine, sql: str, params: dict | None = None):
    """Cada consulta en su propia conexión: si una tabla no existe, las demás siguen."""
    try:
        with engine.connect() as c:
            return c.execute(text(sql), params or {}).fetchall()
    except Exception as exc:  # noqa: BLE001
        print(f"  (no se pudo leer: {str(exc).splitlines()[0][:120]})")
        return None


def _hace(dt: datetime | None, ahora: datetime) -> str:
    if dt is None:
        return "nunca"
    seg = int((ahora - dt).total_seconds())
    if seg < 0:
        return f"en {-seg} s (¿reloj adelantado?)"
    if seg < 120:
        return f"hace {seg} s"
    if seg < 7200:
        return f"hace {seg // 60} min"
    if seg < 172800:
        return f"hace {seg // 3600} h"
    return f"hace {seg // 86400} días"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _comun.agregar_argumentos_db(ap)
    ap.add_argument("--esperado", help="commit que debería correr la tienda tras actualizar (modo verificación)")
    ap.add_argument("--sin-fetch", action="store_true", help="no hacer git fetch (usa lo último traído)")
    args = ap.parse_args()
    faltas: list[str] = []

    # ── 1. El tronco ──────────────────────────────────────────────────────
    print("== Tronco (lo que bajaría la PC principal con git pull)")
    if not args.sin_fetch:
        err = t.traer_tronco()
        if err:
            print(f"  ⚠ git fetch falló ({err[:100]}); uso lo último traído.")
    sello_tronco = t.sello(t.TRONCO)
    hash_tronco = t.hash_de(sello_tronco)
    print(f"  {t.TRONCO} = {sello_tronco or '¿?'}")
    rc, local = t.git("rev-parse", "--short", "HEAD")
    if rc == 0 and not t.mismo_commit(local, hash_tronco):
        print(f"  (esta carpeta está en {local}; se compara contra el tronco de GitHub, no contra ella)")
    esperado = None
    if args.esperado:
        rc, esperado = t.git("rev-parse", "--short", args.esperado)
        if rc != 0:
            print(f"  ⚠ no conozco el commit esperado «{args.esperado}».")
            esperado = args.esperado

    migs = t.migraciones(t.TRONCO)
    heads = t.cabezas(migs)
    print(f"  Migraciones en el tronco: {len(migs)} · cabeza: {', '.join(heads)}")

    # ── 2. La caja ────────────────────────────────────────────────────────
    print("\n== Caja (base de datos)")
    engine = _comun.motor(args, solo_lectura=True)
    filas = _consulta(engine, "select version_num from alembic_version")
    if filas is None:
        print("  ✗ Sin base: no se puede seguir.")
        return 1
    aplicadas = [f[0] for f in filas]
    print(f"  Revisión: {', '.join(aplicadas) or '(vacía)'}")
    ajenas = [a for a in aplicadas if a not in migs]
    faltan = []
    if ajenas:
        print(f"  🛑 La caja tiene {', '.join(ajenas)}, que el tronco NO conoce: alguien migró desde otra rama"
              " o falta un push. NO actualizar nada hasta aclararlo (actualizar.py diría PROGRAMA_VIEJO).")
        faltas.append("la caja tiene una revisión que el tronco no conoce")
    else:
        faltan = t.pendientes(migs, aplicadas, heads)
        if not faltan:
            print("  ✅ Al día con el tronco: la actualización NO migrará nada.")
        else:
            print(f"  ⚠ Le faltan {len(faltan)} migración(es); se aplican al actualizar, con respaldo antes:")
            for m in faltan:
                rellena = "  ← lee/rellena datos (get_bind): no sale en --sql, ensayar en copia" if m.usa_get_bind else ""
                print(f"    - {m.rev}  {m.titulo[:90]}{rellena}")
            faltas.append(f"{len(faltan)} migración(es) pendiente(s) en la caja")

    # ── 3. Las PCs que laten ──────────────────────────────────────────────
    print("\n== PCs que laten en `satelite` (kioskos y servidor de impresión)")
    pcs = _consulta(engine, """
        select nombre, identificador, version, imprime, ultimo_visto
        from satelite order by ultimo_visto desc nulls last""")
    reloj = _consulta(engine, "select now()")
    ahora = reloj[0][0] if reloj else datetime.now(timezone.utc)  # el reloj de la caja, no el de la Mac
    if pcs is None and esperado:
        faltas.append("no se pudo leer la tabla satelite")
    if pcs is not None and esperado and not any(
            v and (ahora - v).total_seconds() <= UMBRAL_ONLINE_SEG for *_, v in pcs):
        faltas.append("ninguna PC está latiendo: no se pudo verificar ningún kiosko")
    if pcs is not None:
        for nombre, ident, version, imprime, visto in pcs:
            seg = (ahora - visto).total_seconds() if visto else None
            prendida = seg is not None and seg <= UMBRAL_ONLINE_SEG
            h = t.hash_de(version)
            notas = []
            # Para verificar: cuenta si está prendida o latió en las últimas 24 h (apagada o con el reloj mal).
            cuenta = esperado and seg is not None and seg <= 86400
            servidor_principal = (nombre or "").strip().lower() == "pc principal"
            if seg is not None and seg < 0:
                notas.append("⚠ su reloj va adelantado respecto a la caja")
            if not version:
                notas.append("no reporta versión")
                if cuenta:
                    faltas.append(f"{nombre}: no reporta versión, no se puede verificar")
            elif not h or not t.existe(h):
                notas.append(f"versión {version}: commit desconocido (¿no está en GitHub?)")
                if cuenta:
                    faltas.append(f"{nombre}: versión {version} no verificable")
            else:
                if t.mismo_commit(h, hash_tronco):
                    notas.append("✅ igual al tronco")
                elif t.es_ancestro(h):
                    notas.append(f"{t.commits_atras(h)} commits atrás del tronco")
                else:
                    notas.append("no está en el tronco (otra rama)")
                desconoce = [a for a in aplicadas if not t.conoce_revision(h, a)]
                if desconoce:
                    notas.append(f"🛑 su programa no conoce la revisión de la caja ({', '.join(desconoce)}): NO abre")
                    if prendida:
                        faltas.append(f"{nombre} corre un programa que no abre con la base actual")
                if cuenta and not t.mismo_commit(h, esperado):
                    if servidor_principal:
                        notas.append("su servidor de impresión toma lo nuevo al reiniciarlo (o reiniciar la PC)")
                    elif prendida:
                        faltas.append(f"{nombre} sigue en {version}, no en {esperado} (¿no la han reabierto?)")
                    else:
                        faltas.append(f"{nombre} sigue en {version} y no está latiendo (apagada o con el reloj mal):"
                                      " se actualiza al abrirla")
            uso = f" · imprime {imprime}" if imprime else ""
            estado = "🟢" if prendida else "⚪"
            print(f"  {estado} {nombre} ({ident}) · {version or '—'} · latió {_hace(visto, ahora)}{uso}")
            print(f"      {' · '.join(notas)}")
        print("  (Encendida = latió hace ≤150 s según el reloj de la caja; la hora la escribe cada PC. El renglón «PC principal» es su"
              " servidor de impresión; el POS de la PC principal y el bot NO laten aquí: su versión se pide"
              " por Telegram con /version.)")

    # ── 4. Bot e impresión ────────────────────────────────────────────────
    print("\n== Bot de Telegram (señal indirecta) e impresión")
    bot = _consulta(engine, """
        select max(enviado_at), count(*) filter (where enviado_at is null) from alerta_telegram""")
    if bot:
        ultimo, cola = bot[0]
        print(f"  Último aviso enviado: {_hace(ultimo, ahora)} · en cola sin enviar: {cola}")
        if cola and cola > 5:
            print("  ⚠ Muchos avisos sin enviar: ¿el bot está caído o la PC principal sin internet?")
    atorados = _consulta(engine, """
        select tipo, count(*), min(created_at) from trabajo
        where estado = 'PENDIENTE' and tipo in ('TICKET','CORTE','ETIQUETA','CONTEO')
          and created_at < now() - make_interval(mins => :m)
          and (disponible_en is null or disponible_en <= now())
        group by tipo""", {"m": ATORADO_MIN})
    if atorados is not None:
        if atorados:
            for tipo, n, desde in atorados:
                print(f"  ⚠ {n} {tipo} atorado(s) desde {_hace(desde, ahora)}")
            if esperado:
                faltas.append("hay impresión atorada")
        else:
            print("  Impresión: nada atorado.")

    # ── 5. Veredicto ──────────────────────────────────────────────────────
    print()
    if esperado:
        if faltas:
            print("✗ FALTA:")
            for f in faltas:
                print(f"  - {f}")
            print("  Pedir a la tienda: el Telegram de cómo terminó (✅/⚠️/🛑), /version y,"
                  " si algo falló, reportes\\ultimo_update.log de la PC principal.")
            return 1
        print(f"✓ OK: la caja está al día y los kioskos corren {esperado}."
              " Falta confirmar la PC principal con /version y reabrir su POS.")
        return 0
    if faltas:
        print("Resumen: " + "; ".join(faltas) + ".")
    else:
        print("Resumen: la caja está al día con el tronco; actualizar no cambia la estructura de la base"
              " (la postactualización sí descuenta del stock ventas pasadas que falten).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
