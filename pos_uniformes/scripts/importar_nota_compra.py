"""Importa una nota de compra de ropa normal desde un CSV.

Cada nota es un archivo en `pos_uniformes/data/notas_compra/`. Las lineas que
empiezan con `#` son datos de la nota; el resto es una tabla de productos:

    # proveedor: Mios
    # documento: MIOS-0008952
    # observacion: Nota 0008952 Mios Uriangato, 19/oct/2026
    nombre,marca,cantidad,costo,precio
    Leggings S01,Showey,288,34,89
    Sudadera KY357H,Yamo,40,55,99

Columnas opcionales: `categoria` (default "Ropa casual"), `talla` (default
"Unitalla"), `color` (default "Surtido"), y las de la ficha de ropa normal
acordada el 2026-10-13: `linea` (tipo_prenda), `pieza` (tipo_pieza),
`detalle` (atributo) y `genero`. Una línea, pieza o detalle que no exista se
crea una sola vez; se busca sin importar mayúsculas ni acentos, para no
repetir lo de «Basico» y «Básico».

Si el producto (nombre + marca) y la talla/color ya existen, no se duplica:
solo entra el stock de la compra. Su precio de venta se respeta salvo que se
use --actualizar-precios, y aun asi nunca se baja.

Por defecto solo simula. Para guardar:
    python -m pos_uniformes.scripts.importar_nota_compra pos_uniformes/data/notas_compra/mios_0008952.csv --usuario admin --aplicar
"""
from __future__ import annotations

import argparse
import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    Compra,
    Marca,
    Producto,
    Proveedor,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
)
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.compra_service import CompraItemInput, CompraService

DEFAULT_CATEGORIA = "Ropa casual"
DEFAULT_TALLA = "Unitalla"
#: Ropa normal: nunca «Sin color» (2026-10-13). Lo que llega revuelto es «Surtido».
DEFAULT_COLOR = "Surtido"
COLUMNAS_REQUERIDAS = ("nombre", "marca", "cantidad", "costo", "precio")


@dataclass(frozen=True)
class LineaNota:
    nombre: str
    marca: str
    cantidad: int
    costo: Decimal
    precio: Decimal
    categoria: str = DEFAULT_CATEGORIA
    talla: str = DEFAULT_TALLA
    color: str = DEFAULT_COLOR
    linea: str = ""
    pieza: str = ""
    detalle: str = ""
    genero: str = ""


@dataclass(frozen=True)
class NotaCompra:
    proveedor: str
    documento: str
    observacion: str | None
    lineas: list[LineaNota]


def _decimal(valor: str, campo: str, fila: int) -> Decimal:
    limpio = valor.replace("$", "").replace(",", "").strip()
    try:
        numero = Decimal(limpio)
    except InvalidOperation:
        raise ValueError(f"Fila {fila}: '{campo}' no es un numero valido ({valor!r}).") from None
    if numero < 0:
        raise ValueError(f"Fila {fila}: '{campo}' no puede ser negativo.")
    return numero


def parsear_nota(texto: str) -> NotaCompra:
    """Lee el CSV de una nota y valida sus datos sin tocar la base."""
    meta: dict[str, str] = {}
    lineas_tabla: list[str] = []
    for linea in texto.splitlines():
        if linea.strip().startswith("#"):
            clave, _, valor = linea.strip().lstrip("#").partition(":")
            meta[clave.strip().lower()] = valor.strip()
        elif linea.strip():
            lineas_tabla.append(linea)

    proveedor = meta.get("proveedor", "")
    documento = meta.get("documento", "")
    if not proveedor or not documento:
        raise ValueError("La nota necesita '# proveedor:' y '# documento:' al inicio.")
    if len(documento) > 40:
        raise ValueError("El documento no puede pasar de 40 caracteres.")

    reader = csv.DictReader(io.StringIO("\n".join(lineas_tabla)))
    columnas = {(c or "").strip().lower() for c in reader.fieldnames or []}
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in columnas]
    if faltantes:
        raise ValueError(f"Faltan columnas en la tabla: {', '.join(faltantes)}.")

    lineas: list[LineaNota] = []
    vistos: set[tuple[str, str, str, str]] = set()
    for fila, row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        nombre, marca = row["nombre"], row["marca"]
        if not nombre or not marca:
            raise ValueError(f"Fila {fila}: nombre y marca son obligatorios.")
        try:
            cantidad = int(row["cantidad"].replace(",", "").split(".")[0])
        except ValueError:
            raise ValueError(f"Fila {fila}: cantidad invalida ({row['cantidad']!r}).") from None
        if cantidad <= 0:
            raise ValueError(f"Fila {fila}: la cantidad debe ser mayor a cero.")
        linea = LineaNota(
            nombre=nombre,
            marca=marca,
            cantidad=cantidad,
            costo=_decimal(row["costo"], "costo", fila),
            precio=_decimal(row["precio"], "precio", fila),
            categoria=row.get("categoria") or DEFAULT_CATEGORIA,
            talla=row.get("talla") or DEFAULT_TALLA,
            color=row.get("color") or DEFAULT_COLOR,
            linea=row.get("linea", ""),
            pieza=row.get("pieza", ""),
            detalle=row.get("detalle", ""),
            genero=row.get("genero", ""),
        )
        clave = (linea.nombre.lower(), linea.marca.lower(), linea.talla.lower(), linea.color.lower())
        if clave in vistos:
            raise ValueError(f"Fila {fila}: '{nombre}' ({marca}, {linea.talla}, {linea.color}) esta repetido.")
        vistos.add(clave)
        lineas.append(linea)

    if not lineas:
        raise ValueError("La nota no tiene productos.")
    return NotaCompra(proveedor, documento, meta.get("observacion") or None, lineas)


def _get_or_create_categoria(session, usuario: Usuario, nombre: str) -> Categoria:
    categoria = session.scalar(select(Categoria).where(Categoria.nombre == nombre))
    return categoria or CatalogService.crear_categoria(session, usuario, nombre)


def _get_or_create_marca(session, usuario: Usuario, nombre: str) -> Marca:
    marca = session.scalar(select(Marca).where(Marca.nombre == nombre))
    return marca or CatalogService.crear_marca(session, usuario, nombre)


def _sin_acentos(texto: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", texto.casefold()) if unicodedata.category(c) != "Mn"
    ).strip()


def _get_or_create_por_nombre(session, modelo, nombre: str):
    """La fila con ese nombre (sin importar mayúsculas ni acentos), o una nueva.

    Si ya hay una con acento y otra sin él, gana la que tiene acento: así se
    va dejando de usar la mal escrita."""
    nombre = " ".join((nombre or "").split())
    if not nombre:
        return None
    buscado = _sin_acentos(nombre)
    parecidas = [f for f in session.scalars(select(modelo)).all() if _sin_acentos(f.nombre) == buscado]
    if parecidas:
        import unicodedata

        def _lleva_acento(texto: str) -> bool:
            return any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", texto))

        parecidas.sort(key=lambda f: (not _lleva_acento(f.nombre), f.id))
        return parecidas[0]
    nueva = modelo(nombre=nombre)
    session.add(nueva)
    session.flush()
    return nueva


def _get_or_create_proveedor(session, nombre: str) -> Proveedor:
    proveedor = session.scalar(select(Proveedor).where(Proveedor.nombre == nombre))
    if proveedor is None:
        proveedor = Proveedor(nombre=nombre)
        session.add(proveedor)
        session.flush()
    return proveedor


def _resolver_variante(session, usuario: Usuario, linea: LineaNota, actualizar_precios: bool) -> tuple[Variante, str]:
    marca = _get_or_create_marca(session, usuario, linea.marca)
    producto = session.scalar(
        select(Producto).where(Producto.nombre == linea.nombre, Producto.marca_id == marca.id)
    )
    estado = "existente"
    if producto is None:
        producto = CatalogService.crear_producto(
            session,
            usuario,
            categoria=_get_or_create_categoria(session, usuario, linea.categoria),
            marca=marca,
            nombre=linea.nombre,
            tipo_prenda=_get_or_create_por_nombre(session, TipoPrenda, linea.linea),
            tipo_pieza=_get_or_create_por_nombre(session, TipoPieza, linea.pieza),
            atributo=_get_or_create_por_nombre(session, AtributoProducto, linea.detalle),
            genero=linea.genero or None,
        )
        # crear_producto aplica title case; conservamos el codigo del proveedor en mayusculas.
        producto.nombre = producto.nombre_base = linea.nombre
        estado = "nuevo"

    variante = session.scalar(
        select(Variante).where(
            Variante.producto_id == producto.id,
            Variante.talla == linea.talla,
            Variante.color == linea.color,
        )
    )
    if variante is None:
        variante = CatalogService.crear_variante(
            session,
            usuario,
            producto=producto,
            sku=None,
            talla=linea.talla,
            color=linea.color,
            precio_venta=linea.precio,
            costo_referencia=linea.costo,
        )
        return variante, estado if estado == "nuevo" else "nueva talla"

    if not variante.activo:
        raise ValueError(f"'{linea.nombre}' ({linea.marca}, {linea.talla}) existe pero esta inactivo. Activalo primero.")
    if variante.precio_venta != linea.precio:
        if actualizar_precios and linea.precio > variante.precio_venta:
            estado = f"resurtido, precio ${variante.precio_venta} -> ${linea.precio}"
            variante.precio_venta = linea.precio
        else:
            estado = f"resurtido, conserva precio ${variante.precio_venta}"
    else:
        estado = "resurtido"
    return variante, estado


def importar(session, usuario: Usuario, nota: NotaCompra, actualizar_precios: bool = False) -> Compra:
    if session.scalar(select(Compra).where(Compra.numero_documento == nota.documento)):
        raise ValueError(f"La compra {nota.documento} ya estaba registrada. No se hizo nada.")

    items: list[CompraItemInput] = []
    for linea in nota.lineas:
        variante, estado = _resolver_variante(session, usuario, linea, actualizar_precios)
        items.append(CompraItemInput(variante.id, linea.cantidad, linea.costo))
        print(
            f"  {variante.sku}  {linea.nombre:<24} {linea.marca:<8} {linea.talla:<9}"
            f" {linea.cantidad:>4} pzas  costo ${linea.costo:>7}  venta ${variante.precio_venta:>7}  [{estado}]"
        )

    compra = CompraService.crear_borrador(
        session,
        proveedor=_get_or_create_proveedor(session, nota.proveedor),
        usuario=usuario,
        numero_documento=nota.documento,
        items=items,
        observacion=nota.observacion,
    )
    session.flush()
    CompraService.confirmar_compra(session, compra)
    session.flush()
    return compra


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa una nota de compra de ropa normal desde CSV.")
    parser.add_argument("archivo", type=Path, help="CSV de la nota")
    parser.add_argument("--usuario", required=True, help="username ADMIN que registra la compra")
    parser.add_argument("--aplicar", action="store_true", help="guardar cambios (sin esto solo simula)")
    parser.add_argument(
        "--actualizar-precios",
        action="store_true",
        help="en resurtidos, subir el precio de venta al del CSV (nunca lo baja)",
    )
    args = parser.parse_args()

    try:
        nota = parsear_nota(args.archivo.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise SystemExit(f"Error en {args.archivo.name}: {exc}")

    with get_session() as session:
        usuario = session.scalar(select(Usuario).where(Usuario.username == args.usuario))
        if usuario is None:
            raise SystemExit(f"No existe el usuario '{args.usuario}'.")

        print(f"Nota {nota.documento} de {nota.proveedor}:")
        try:
            compra = importar(session, usuario, nota, args.actualizar_precios)
        except (ValueError, PermissionError) as exc:
            session.rollback()
            raise SystemExit(str(exc))
        piezas = sum(linea.cantidad for linea in nota.lineas)
        print(f"Compra {nota.documento}: {len(nota.lineas)} productos, {piezas} pzas, total ${compra.total}")

        if args.aplicar:
            session.commit()
            print("Listo: cambios guardados.")
        else:
            session.rollback()
            print("Simulacion: no se guardo nada. Agrega --aplicar para guardar.")


if __name__ == "__main__":
    main()
