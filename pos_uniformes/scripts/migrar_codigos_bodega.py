"""Migra códigos de cajas de bodega al nuevo formato con ubicación.

Formato anterior: A-001 (categoría-secuencia)
Formato nuevo:    A-P1-001 (categoría-ubicación-secuencia)

Ejecutar UNA VEZ en cada máquina después de git pull.
Es idempotente: si ya tiene el nuevo formato, no hace nada.
"""

import sys
from pathlib import Path

# Asegurar que el paquete pos_uniformes sea importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import BodegaCaja, BodegaUbicacion
from pos_uniformes.services.bodega_service import BodegaService
from sqlalchemy import select
from sqlalchemy.orm import joinedload


def main():
    with get_session() as session:
        # 1. Asegurar que ALMACEN-N1 existe
        almacen = session.scalar(
            select(BodegaUbicacion).where(
                BodegaUbicacion.rack == "ALMACEN",
                BodegaUbicacion.nivel == 1,
            )
        )
        if not almacen:
            almacen = BodegaUbicacion(
                codigo="ALMACEN-N1", rack="ALMACEN", nivel=1,
                descripcion="Almacén nivel 1",
            )
            session.add(almacen)
            session.flush()
            print("Creada ubicación ALMACEN-N1")

        # 2. Migrar códigos de cajas
        cajas = session.scalars(
            select(BodegaCaja)
            .options(joinedload(BodegaCaja.ubicacion))
            .order_by(BodegaCaja.codigo)
        ).unique().all()

        migradas = 0
        for caja in cajas:
            old = caja.codigo
            # Si ya tiene formato nuevo (3 partes con guión), saltar
            if old.count("-") >= 2:
                print(f"  {old} — ya migrada, saltar")
                continue
            parts = old.split("-")
            if len(parts) != 2:
                print(f"  {old} — formato desconocido, saltar")
                continue
            abrev = BodegaService._abrev_ubicacion(caja.ubicacion)
            new_code = f"{parts[0]}-{abrev}-{parts[1]}"
            caja.codigo = new_code
            caja.qr_data = f"BODEGA:CAJA:{new_code}"
            print(f"  {old} → {new_code}")
            migradas += 1

        session.commit()
        print(f"\nMigración completada: {migradas} cajas actualizadas, {len(cajas) - migradas} sin cambios.")


if __name__ == "__main__":
    main()
