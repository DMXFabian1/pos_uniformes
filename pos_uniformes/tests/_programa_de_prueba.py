"""E5-A: desde 2026-11-10 el % del Monedero es el del programa del cliente.
Las pruebas del Monedero inscriben a sus clientes en un programa de prueba
con la tasa que antes ponían en la configuración general."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pos_uniformes.database.models import Membresia, Programa

DESDE = datetime(2020, 1, 1, tzinfo=timezone.utc)


def programa_de_prueba(session, tasa, *, clave: str | None = None) -> Programa:
    clave = clave or f"PRUEBA_{str(tasa).replace('.', '_')}"
    programa = Programa(clave=clave, nombre=f"Programa de prueba {clave}", estado="activo",
                        ingreso_modo="directo_empleada", tasa_monedero=Decimal(str(tasa)), orden=99)
    session.add(programa)
    session.flush()
    return programa


def inscribir(session, cliente_id: int, programa: Programa, *, desde=DESDE, hasta=None,
              estado: str = "activa") -> Membresia:
    m = Membresia(cliente_id=int(cliente_id), programa_id=programa.id, estado=estado, desde=desde, hasta=hasta)
    session.add(m)
    session.flush()
    return m
