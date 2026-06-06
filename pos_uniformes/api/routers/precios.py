"""Endpoint publico del checador de precios para el ESP32-CAM.

A diferencia del resto de la API movil (que exige token JWT de empleada),
este endpoint es PUBLICO y minimalista: esta pensado para que un lector de
codigos QR basado en ESP32-CAM consulte el precio de un producto en la red
local, sin manejar autenticacion.

    GET /api/v1/precio/{codigo}

donde {codigo} es el SKU impreso en el QR (campo variante.sku de la BD).

La respuesta SIEMPRE es HTTP 200 con un JSON que incluye el flag "encontrado",
para que el firmware del ESP32 no tenga que distinguir codigos de estado HTTP:

    Encontrado:
        {
          "encontrado": true,
          "sku": "JUMP-6",
          "nombre": "Jumper Primaria X",
          "talla": "6",
          "color": "Azul",
          "precio": 350.00
        }

    No encontrado:
        { "encontrado": false, "sku": "XXX", "nombre": null,
          "talla": null, "color": null, "precio": null }

Seguridad: por ser publico, exponer SOLO en la red local (LAN). No publicar
este endpoint a internet sin una capa de proteccion adicional.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel

from pos_uniformes.api.dependencies import get_db
from pos_uniformes.database.models import Producto, Variante

router = APIRouter(prefix="/api/v1/precio", tags=["precio-checador"])


class PrecioResponse(BaseModel):
    """Respuesta del checador de precios (apta para parsear con ArduinoJson)."""

    encontrado: bool
    sku: str
    nombre: str | None = None
    talla: str | None = None
    color: str | None = None
    precio: Decimal | None = None


@router.get("/{codigo}", response_model=PrecioResponse)
def consultar_precio(
    codigo: str,
    db: Session = Depends(get_db),
) -> PrecioResponse:
    """
    Busca una variante activa por su SKU (el codigo leido del QR) y devuelve
    su nombre y precio. La busqueda no distingue mayusculas/minusculas.

    Siempre responde 200; usa el campo "encontrado" para indicar el resultado.
    """
    # Normalizamos el codigo: quitamos espacios y comparamos en mayusculas,
    # igual que hace el scanner de la PWA (endpoint /catalog/sku/{sku}).
    sku_normalizado = codigo.strip().upper()

    variante = db.scalar(
        select(Variante)
        .where(
            func.upper(Variante.sku) == sku_normalizado,
            Variante.activo.is_(True),
        )
        # Cargamos el producto padre para obtener el nombre a mostrar.
        .options(selectinload(Variante.producto))
    )

    # No se encontro: respondemos encontrado=false (sin error HTTP).
    if variante is None or variante.producto is None:
        return PrecioResponse(encontrado=False, sku=sku_normalizado)

    producto: Producto = variante.producto

    return PrecioResponse(
        encontrado=True,
        sku=variante.sku,
        nombre=producto.nombre,
        talla=variante.talla,
        color=variante.color,
        precio=variante.precio_venta,
    )
