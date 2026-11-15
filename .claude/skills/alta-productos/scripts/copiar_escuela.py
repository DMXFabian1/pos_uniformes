#!/usr/bin/env python3
"""Deja una escuela con el mismo uniforme que otra, con el motor del POS.

Usa `services/copiar_escuela_service.py`, lo mismo que la pantalla «Nueva
prenda → Escuela igual a otra»: cada prenda del origen sale

  NUEVA         el destino no la tiene: se da de alta con los MISMOS PRECIOS
                del origen, existencia 0, el mismo lugar en el uniforme y la
                receta propuesta (Pants 3pz / Chamarra);
  YA ESTÁ       el destino ya la tiene (misma pieza y nombre sin color): no se
                toca; si faltaba en su uniforme, se liga;
  CAMBIA COLOR  ya la tiene pero se eligió otro color para ella: cambia el
                color (y el nombre si lo lleva) de toda la prenda, sin tocar
                SKU, precios ni existencia;
  SE LIGA       pieza general (sin escuela) del uniforme del origen que falta
                en el del destino.

Todo en una transacción y la bitácora dice «Copia de escuela: A → B · modelo: …».

Uso (desde la raíz del repo):
    python .claude/skills/alta-productos/scripts/copiar_escuela.py \\
        --origen "Ignacio Allende" --destino "Ignacio Allende (Jaral)" \\
        --colores Rojo=Azul --color-de "Pants Suelto=Gris" --excluir Boina [--env-file ...]
    ... --ensayo      # hace la copia y la deshace: enseña los SKU reales
    ... --aplicar     # guarda (solo con el OK de Daniel)

  --colores ORIGEN=DESTINO   color para todas las prendas de ese color del origen (repetible)
  --color-de PATRÓN=COLOR    color de las prendas cuyo nombre o tipo de pieza contiene PATRÓN
                             (repetible; gana sobre --colores)
  --excluir PATRÓN           prendas del origen que el destino no lleva (repetible)
  --escuela-nueva            el destino no existe y Daniel ya dijo que NO es ninguna de las
                             parecidas: se crea (con un usuario ADMIN)
  --confirmar VALOR          un color nuevo que Daniel aprobó crear (repetible)

Sin --ensayo ni --aplicar solo lee (conexión de solo lectura) y enseña el plan.
Las prendas nuevas toman el color que el destino ya usa para ese color del
origen («Sin color» → «Gris» en Jaral) si no se elige otro.
"""
from __future__ import annotations

import argparse

import _comun


def pares(valores: list[str], opcion: str) -> list[tuple[str, str]]:
    salida = []
    for v in valores:
        if "=" not in v:
            raise SystemExit(f"ERROR: {opcion} espera PATRÓN=VALOR, llegó «{v}».")
        a, b = v.split("=", 1)
        salida.append((a.strip(), b.strip()))
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", required=True)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--colores", action="append", default=[])
    ap.add_argument("--color-de", action="append", default=[])
    ap.add_argument("--excluir", action="append", default=[])
    ap.add_argument("--escuela-nueva", action="store_true")
    ap.add_argument("--confirmar", action="append", default=[])
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--ensayo", action="store_true", help="hace la copia y la deshace (ROLLBACK)")
    modo.add_argument("--aplicar", action="store_true", help="hace COMMIT")
    ap.add_argument("--usuario", help="usuario ADMIN que firma (por defecto, el primer ADMIN activo)")
    _comun.agregar_argumentos_db(ap)
    args = ap.parse_args()

    escribe = args.ensayo or args.aplicar
    engine = _comun.motor(args, solo_lectura=not escribe)

    from sqlalchemy import select
    from sqlalchemy.exc import ProgrammingError
    from sqlalchemy.orm import Session

    from pos_uniformes.database.models import RolUsuario, Usuario
    from pos_uniformes.services import catalogo_valores_service as valores
    from pos_uniformes.services import copiar_escuela_service as ce

    norm = valores.normalizar
    colores = dict(pares(args.colores, "--colores"))
    color_de_patron = [(norm(a), b) for a, b in pares(args.color_de, "--color-de")]
    excluir = [norm(x) for x in args.excluir]

    def coincide(o: ce.PiezaOrigen, patron: str) -> bool:
        return patron in norm(o.nombre_sin_escuela) or patron == norm(o.tipo_pieza)

    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        try:
            plan = ce.planear_copia(session, args.origen, args.destino, colores=colores,
                                    escuela_nueva=args.escuela_nueva, confirmados=args.confirmar)
            color_de = {}
            for p in plan.piezas:
                for patron, color in color_de_patron:
                    if coincide(p.origen, patron):
                        color_de[p.origen.producto_id] = color
                        break
            quitar = [p.origen.producto_id for p in plan.piezas if any(coincide(p.origen, x) for x in excluir)]
            if color_de or quitar:
                plan = ce.replanear(session, plan, color_de=color_de, quitar=quitar)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        except ProgrammingError as exc:
            print(f"ERROR: la base no coincide con el código de esta rama ({type(exc.orig).__name__}). "
                  "Probablemente le faltan migraciones (alembic upgrade head). No se guardó nada.")
            return 1

        nueva = " (ESCUELA NUEVA)" if plan.es_nueva else ""
        print(f"\nOrigen «{plan.origen}» → destino «{plan.destino}»{nueva}\n")
        for p in plan.piezas:
            marca = "  " if p.marcada else "✗ "
            estado = p.texto_estado if p.marcada else "NO SE COPIA"
            print(f"{marca}{estado:<34} «{p.nombre}» · {p.color} · {p.origen.texto_rango}")
            if p.marcada:
                for e in p.todos_los_errores:
                    print(f"      ERROR {e}")
                for a in p.avisos:
                    print(f"      ⚠ {a}")
        if plan.solo_en_destino:
            print(f"\nSolo en el destino (no se tocan): {list(plan.solo_en_destino)}")
        if plan.parecidas:
            print(f"Escuelas parecidas: {[f'{x.valor} ({x.usos} prendas)' for x in plan.parecidas]}")
        for a in plan.avisos:
            print(f"⚠ {a}")
        for p in plan.planes:
            for a in p.todos_los_avisos:
                print(f"⚠ {p.nombre}: {a}")
            if p.receta_texto:
                print(f"  {p.nombre}: {p.receta_texto}")
        print(f"\n{plan.resumen()}")

        if not plan.puede_aplicar:
            print(f"\nNo se puede copiar todavía: {plan.nota_bloqueo()}")
            return 1
        if not escribe:
            print("\nSOLO LECTURA. Siguiente: --ensayo (SKU reales) y, con el OK de Daniel, --aplicar.")
            return 0

        filtro = [Usuario.rol == RolUsuario.ADMIN, Usuario.activo.is_(True)]
        if args.usuario:
            filtro.append(Usuario.username == args.usuario)
        admin = session.scalar(select(Usuario).where(*filtro).order_by(Usuario.id).limit(1))
        if admin is None:
            print(f"ERROR: no hay usuario ADMIN activo{f' «{args.usuario}»' if args.usuario else ''}.")
            return 2

        if args.ensayo:
            resultado = ce.ensayar_copia(session, plan, admin)
            session.rollback()
            print("\nENSAYO (rollback, no se guardó nada):")
            print(resultado.texto())
            return 0 if resultado.ok else 1
        try:
            resultado = ce.aplicar_copia(session, plan, admin)
        except (ValueError, PermissionError) as exc:
            session.rollback()
            print(f"\nERROR del POS: {exc}\nNo se guardó nada.")
            return 1
        session.commit()
        print("\n" + resultado.texto())
        print("\nCOMMIT hecho. Quedó registro en cambio_catalogo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
