"""Archiva (o desarchiva) fichas de clientes de prueba. E1-C5, decisión C15.

NO BORRA NADA. Archivar = `activo=false` + `archivado_en` + `archivado_motivo`
y un evento `archivado` por ficha (C12). Las ventas, la Libreta, los
apartados, los presupuestos y el Monedero conservan su `cliente_id`; los
códigos y las secuencias no cambian.

Por omisión solo SIMULA: muestra cuántas fichas tocaría y no escribe nada.
Para escribir hacen falta `--aplicar` y `--confirmo-base <nombre de la base>`
(el nombre exacto de la base a la que está conectado, como red de seguridad).

Ejemplos:

    python -m pos_uniformes.scripts.archivar_clientes_prueba --todos \
        --motivo "Fichas de prueba previas a E1-C" --usuario-id 1

    python -m pos_uniformes.scripts.archivar_clientes_prueba --ids 5,8 \
        --motivo "Era cliente real" --usuario-id 1 --desarchivar \
        --aplicar --confirmo-base pos_uniformes

Es idempotente: una ficha ya archivada se omite (y una no archivada se omite
al desarchivar).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.models import Apartado, Cliente, LibretaVenta, Monedero, Venta
from pos_uniformes.services.clientes import admin_service


@dataclass
class Resumen:
    accion: str
    aplicado: bool
    candidatas: int = 0
    a_cambiar: int = 0
    omitidas: int = 0
    no_encontradas: list[int] = field(default_factory=list)
    con_monedero: int = 0
    con_ventas: int = 0
    con_libreta: int = 0
    con_apartados: int = 0
    ids_cambiados: list[int] = field(default_factory=list)

    def texto(self) -> str:
        modo = "APLICADO" if self.aplicado else "SIMULACION (no se escribio nada)"
        lineas = [
            f"{self.accion.upper()} — {modo}",
            f"  Fichas candidatas:        {self.candidatas}",
            f"  Se {'cambiaron' if self.aplicado else 'cambiarian'}:           {self.a_cambiar}",
            f"  Omitidas (ya estaban):    {self.omitidas}",
            f"  Con monedero:             {self.con_monedero}  (el Monedero no se toca)",
            f"  Con ventas del POS:       {self.con_ventas}  (conservan su cliente)",
            f"  Con registros de Libreta: {self.con_libreta}  (conservan su cliente)",
            f"  Con apartados:            {self.con_apartados}  (conservan su cliente)",
        ]
        if self.no_encontradas:
            lineas.append(f"  Ids no encontrados:       {', '.join(map(str, self.no_encontradas))}")
        return "\n".join(lineas)


def _ids_con(session: Session, columna, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    return set(session.scalars(select(columna).where(columna.in_(ids)).distinct()))


def ejecutar(
    session: Session,
    *,
    usuario_id: int,
    motivo: str,
    todos: bool = False,
    ids: list[int] | None = None,
    desarchivar: bool = False,
    aplicar: bool = False,
) -> Resumen:
    """Hace el trabajo dentro de `session`. No hace commit: eso es del llamador."""
    admin_service.exigir_admin(session, usuario_id)
    if len((motivo or "").strip()) < admin_service.MOTIVO_MINIMO:
        raise ValueError(f"El motivo debe tener al menos {admin_service.MOTIVO_MINIMO} caracteres.")
    if todos == bool(ids):
        raise ValueError("Indica --todos o --ids, uno de los dos.")

    stmt = select(Cliente).order_by(Cliente.id)
    if ids:
        stmt = stmt.where(Cliente.id.in_(ids))
    fichas = list(session.scalars(stmt))
    resumen = Resumen(accion="desarchivar" if desarchivar else "archivar", aplicado=aplicar)
    resumen.candidatas = len(fichas)
    if ids:
        encontrados = {int(c.id) for c in fichas}
        resumen.no_encontradas = [i for i in ids if i not in encontrados]

    por_cambiar = [c for c in fichas if (c.archivado_en is not None) == desarchivar]
    resumen.a_cambiar = len(por_cambiar)
    resumen.omitidas = len(fichas) - len(por_cambiar)
    cambiar_ids = [int(c.id) for c in por_cambiar]
    resumen.con_monedero = len(_ids_con(session, Monedero.cliente_id, cambiar_ids))
    resumen.con_ventas = len(_ids_con(session, Venta.cliente_id, cambiar_ids))
    resumen.con_libreta = len(_ids_con(session, LibretaVenta.cliente_id, cambiar_ids))
    resumen.con_apartados = len(_ids_con(session, Apartado.cliente_id, cambiar_ids))

    if aplicar:
        accion = admin_service.desarchivar if desarchivar else admin_service.archivar
        for cliente in por_cambiar:
            accion(session, cliente_id=int(cliente.id), usuario_id=usuario_id, motivo=motivo)
            resumen.ids_cambiados.append(int(cliente.id))
        session.flush()
    return resumen


def _parse_ids(texto: str | None) -> list[int]:
    if not texto:
        return []
    return [int(parte) for parte in texto.replace(" ", "").split(",") if parte]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archiva o desarchiva fichas de clientes sin borrar nada.")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--todos", action="store_true", help="Todas las fichas existentes.")
    grupo.add_argument("--ids", help="Ids separados por coma, por ejemplo 5,8,13.")
    parser.add_argument("--motivo", required=True, help="Motivo que queda en cada ficha y en su evento.")
    parser.add_argument("--usuario-id", type=int, required=True, help="Id del usuario ADMIN que hace el cambio.")
    parser.add_argument("--desarchivar", action="store_true", help="Deshace el archivado.")
    parser.add_argument("--aplicar", action="store_true", help="Escribe. Sin esto solo simula.")
    parser.add_argument("--confirmo-base", help="Nombre exacto de la base; obligatorio con --aplicar.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from pos_uniformes.database.connection import get_session

    with get_session() as session:
        base = session.scalar(select(func.current_database())) if session.bind.dialect.name == "postgresql" else "?"
        print(f"Base conectada: {base}")
        if args.aplicar and args.confirmo_base != base:
            print("Detenido: con --aplicar hay que pasar --confirmo-base con el nombre exacto de la base.")
            return 2
        resumen = ejecutar(
            session,
            usuario_id=args.usuario_id,
            motivo=args.motivo,
            todos=args.todos,
            ids=_parse_ids(args.ids),
            desarchivar=args.desarchivar,
            aplicar=args.aplicar,
        )
        if args.aplicar:
            session.commit()
        else:
            session.rollback()
    print(resumen.texto())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
