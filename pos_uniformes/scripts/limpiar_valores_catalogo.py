"""Limpieza de valores del catálogo: tallas a su forma oficial, taxonomías con acento y
nombres que repiten la escuela (tanda 5 del alta, 2026-11-15).

La lógica vive en `services/limpiar_valores_service.py` (con pruebas). Este script
solo la corre contra la base que diga la configuración (o `--env-file`).

- Sin argumentos: SOLO LEE (la transacción se abre con SET TRANSACTION READ ONLY
  en PostgreSQL) e imprime el plan agrupado: tallas a juntar (Uni/NT → Unitalla,
  Ch → CH, M → MD, G → GD, XL → EXG…), taxonomías con dos escrituras («Basico» →
  «Básico»), nombres con la escuela repetida (ESTV), los CHOQUES que no se tocan
  y, como informativo, los colores (no se tocan: decisión 2026-11-13) y los
  valores parecidos.
- Con `--aplicar`: lo mismo, en UNA transacción, con bitácora en cambio_catalogo
  («LIMPIEZA-VALORES-2026-11 · …») a nombre del ADMIN de `--admin`. No cambia
  SKU, precios ni existencias. Se puede repetir: la segunda vez no hace nada.
  SOLO con el sí de Daniel después de ver la corrida sin `--aplicar`.

Uso (desde pos_uniformes/):
    python scripts/limpiar_valores_catalogo.py --env-file "<ruta del .env de la caja>"
    python scripts/limpiar_valores_catalogo.py --env-file "<...>" --aplicar --admin admin
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*noload.*")


def _cargar_env(ruta: str) -> None:
    archivo = Path(ruta).expanduser()
    if not archivo.is_file():
        raise SystemExit(f"No existe el env «{archivo}».")
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ[clave.strip()] = valor.strip().strip('"').strip("'")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", help="archivo .env con la conexión (no se imprime)")
    ap.add_argument("--aplicar", action="store_true", help="escribir los cambios (por defecto solo lee)")
    ap.add_argument("--admin", default="admin", help="usuario ADMIN que firma la bitácora")
    args = ap.parse_args(argv)
    if args.env_file:
        _cargar_env(args.env_file)

    from sqlalchemy import select, text

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.database.models import RolUsuario, Usuario
    from pos_uniformes.services import limpiar_valores_service as lv

    with get_session() as session:
        bind = session.get_bind()
        destino = f"{bind.url.host or 'local'}/{bind.url.database or ''}"
        print(f"Base: {destino} · {'APLICAR' if args.aplicar else 'solo lectura'}")
        if not args.aplicar and bind.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
        try:
            plan = lv.planear_limpieza(session)
            print(plan.texto())
            if not args.aplicar or not plan.hay_cambios:
                if plan.hay_cambios:
                    print("\nEnsayo: no se escribió nada. Con el sí de Daniel, repetir con --aplicar.")
                else:
                    print("\nNo hay nada que limpiar.")
                session.rollback()
                return 0
            admin = session.scalar(select(Usuario).where(Usuario.username == args.admin))
            if admin is None or admin.rol != RolUsuario.ADMIN or not admin.activo:
                print(f"«{args.admin}» no es un ADMIN activo.")
                session.rollback()
                return 2
            resultado = lv.aplicar_limpieza(session, plan, admin, commit=True)
            print(f"\n{resultado.texto()} Referencia en la bitácora: {lv.REFERENCIA}.")
        except Exception:
            session.rollback()
            raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
