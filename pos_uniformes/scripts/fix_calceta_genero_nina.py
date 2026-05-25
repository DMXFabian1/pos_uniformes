"""Fix puntual: actualiza genero='Niña' para todos los productos de tipo Calceta.

Ejecutar una sola vez en cada ambiente (Mac y Windows):
    python pos_uniformes/scripts/fix_calceta_genero_nina.py
"""
from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Producto, TipoPieza
from sqlalchemy import func, select, update


def main() -> None:
    with get_session() as session:
        calceta_ids = [
            r[0]
            for r in session.execute(
                select(Producto.id)
                .join(TipoPieza, Producto.tipo_pieza_id == TipoPieza.id)
                .where(func.lower(TipoPieza.nombre).contains("calceta"))
            ).all()
        ]

        if not calceta_ids:
            print("No se encontraron productos de tipo Calceta.")
            return

        print(f"Actualizando {len(calceta_ids)} productos (ids: {calceta_ids}) → genero='Niña'")
        session.execute(
            update(Producto)
            .where(Producto.id.in_(calceta_ids))
            .values(genero="Niña")
        )
        session.commit()

        rows = session.execute(
            select(Producto.nombre, Producto.genero)
            .join(TipoPieza, Producto.tipo_pieza_id == TipoPieza.id)
            .where(func.lower(TipoPieza.nombre).contains("calceta"))
            .order_by(Producto.nombre)
        ).all()
        for r in rows:
            print(f"  ✓ {r.nombre} → {r.genero}")
        print("Listo.")


if __name__ == "__main__":
    main()
