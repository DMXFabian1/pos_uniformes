"""«Editar datos» de una prenda: lo que no es nombre, color ni precio (tanda 5, 2026-11-15).

Reemplaza al editor viejo de la prenda (el asistente de 4 pasos con
`initial`), que se retira en esta tanda. Lo que aquel dejaba cambiar se
reparte así:

- nombre y color de toda la prenda, y los precios → «✏️ Corregir prenda»
  (`corregir_prenda_service`, tanda 4);
- código, talla, color, precio, costo y mínimo de una talla → «🔧 Editar talla»;
- todo lo demás → aquí: marca, categoría, tipo de prenda, pieza, atributo,
  nivel, escuela, género, escudo, ubicación, descripción y, opcional, el
  costo de todas las tallas a la vez.

Las listas son CERRADAS: solo se elige un valor que ya existe (sin
mayúsculas ni acentos cuenta igual: «basico» es «Básico»). Un valor nuevo de
catálogo no se crea aquí; las marcas nuevas siguen en «Poco usado → Marca
nueva».

Cambiar la escuela vuelve a armar el nombre con la escuela nueva (sin
repetirla) y mueve la prenda del uniforme de la escuela vieja al de la nueva,
con su mismo grupo y obligatoria. Se detiene si la prenda está en una receta
(Pants 3pz, Chamarra: la receta junta piezas de la misma escuela) y si se
quiere volver general una prenda de escuela, o al revés: eso se arregla en
«Uniformes por escuela» o se le pide a Claude.

Se conserva SKU, precios y existencia. La bitácora (`cambio_catalogo`) anota
cada campo con «Editar datos · desde la ficha». Solo ADMIN. Todo o nada
(savepoint).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Mapping

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    ConjuntoComponente,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    TipoPieza,
    TipoPrenda,
    Uniforme,
    UniformePieza,
    Usuario,
    Variante,
)
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import uniforme_service as us
from pos_uniformes.services.catalog_service import CatalogService

ORIGEN_DATOS = "Editar datos · desde la ficha"
GENEROS = ("Unisex", "Mujer", "Hombre")

# Campo → (modelo, atributo de Producto, rótulo). El orden es el de la pantalla.
LISTAS: dict[str, tuple[type, str, str]] = {
    "marca": (Marca, "marca", "Marca"),
    "categoria": (Categoria, "categoria", "Categoría"),
    "tipo_prenda": (TipoPrenda, "tipo_prenda", "Tipo de prenda"),
    "tipo_pieza": (TipoPieza, "tipo_pieza", "Pieza"),
    "atributo": (AtributoProducto, "atributo", "Atributo"),
    "nivel_educativo": (NivelEducativo, "nivel_educativo", "Nivel"),
    "escuela": (Escuela, "escuela", "Escuela"),
}
TEXTOS: dict[str, str] = {
    "genero": "Género",
    "escudo": "Escudo",
    "ubicacion": "Ubicación",
    "descripcion": "Descripción",
}
#: Campos que pueden quedar vacíos (los demás son obligatorios).
OPCIONALES = frozenset({"tipo_prenda", "tipo_pieza", "atributo", "nivel_educativo", "escuela",
                        "genero", "escudo", "ubicacion", "descripcion"})
ROTULOS = {**{k: v[2] for k, v in LISTAS.items()}, **TEXTOS, "costo": "Costo"}


class DatosNoValidos(ValueError):
    """El plan tiene errores: no se guarda nada."""


@dataclass(frozen=True)
class OpcionesDatos:
    """Las listas cerradas de la pantalla (valores activos, sin mayúsculas ni acentos repetidos)."""

    listas: dict[str, tuple[str, ...]]
    generos: tuple[str, ...]
    escudos: tuple[str, ...]


@dataclass(frozen=True)
class Cambio:
    campo: str
    antes: str
    despues: str

    @property
    def texto(self) -> str:
        return f"{ROTULOS.get(self.campo, self.campo)}: {self.antes or '—'} → {self.despues or '—'}"


@dataclass
class PlanDatos:
    producto_id: int
    nombre_antes: str
    nombre: str
    antes: dict[str, str]
    datos: dict[str, str]
    costo: Decimal | None = None
    tallas: int = 0
    cambios: list[Cambio] = field(default_factory=list)
    #: Piezas de uniforme que se mueven a la escuela nueva (ids de UniformePieza).
    piezas_a_mover: list[int] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def hay_cambios(self) -> bool:
        return bool(self.cambios)

    @property
    def puede_aplicar(self) -> bool:
        return self.hay_cambios and not self.errores

    @property
    def cambia_escuela(self) -> bool:
        return any(c.campo == "escuela" for c in self.cambios)

    @property
    def resumen(self) -> str:
        if not self.cambios:
            return "Sin cambios todavía."
        partes = [c.texto for c in self.cambios]
        if self.nombre != self.nombre_antes:
            partes.append(f"Pasa a llamarse «{self.nombre}»")
        partes.append("Los códigos, los precios y la existencia se quedan igual.")
        return " · ".join(partes)


def _nombres_activos(session: Session, modelo) -> list[str]:
    return [str(n) for n in session.scalars(select(modelo.nombre).where(modelo.activo.is_(True))).all()]


def opciones_datos(session: Session) -> OpcionesDatos:
    listas = {}
    for campo, (modelo, _attr, _rot) in LISTAS.items():
        nombres = valores.depurar_opciones(campo, _nombres_activos(session, modelo))
        listas[campo] = tuple(sorted(nombres, key=valores.normalizar))
    escudos = sorted({valores.limpiar(e) for e in session.scalars(select(Producto.escudo)).all()
                      if valores.limpiar(e)}, key=valores.normalizar)
    return OpcionesDatos(listas=listas, generos=GENEROS, escudos=tuple(escudos))


def _texto(valor: object) -> str:
    return valores.limpiar(valor)


def _nombre_de(fila) -> str:
    return str(fila.nombre) if fila is not None else ""


def datos_de(producto: Producto) -> dict[str, str]:
    datos = {campo: _nombre_de(getattr(producto, attr)) for campo, (_m, attr, _r) in LISTAS.items()}
    datos.update({campo: _texto(getattr(producto, campo)) for campo in TEXTOS})
    datos["descripcion"] = str(producto.descripcion or "").strip()
    return datos


def _buscar(session: Session, modelo, texto: str):
    """La fila activa con ese nombre (sin mayúsculas ni acentos), prefiriendo la acentuada."""
    exacta = session.scalar(select(modelo).where(modelo.nombre == texto))
    if exacta is not None and exacta.activo:
        return exacta
    clave = valores.normalizar(texto)
    parecidas = [f for f in session.scalars(select(modelo).where(modelo.activo.is_(True))).all()
                 if valores.normalizar(f.nombre) == clave]
    parecidas.sort(key=lambda f: (not valores.lleva_acento(f.nombre), f.id))
    return parecidas[0] if parecidas else None


def _leer_costo(costo: object) -> tuple[Decimal | None, str]:
    texto = str(costo or "").strip().replace("$", "").replace(",", "")
    if not texto:
        return None, ""
    try:
        valor = Decimal(texto).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None, "El costo no es un número."
    if valor < 0:
        return None, "El costo no puede ser negativo."
    return valor, ""


def _en_receta(session: Session, producto_id: int) -> bool:
    return session.scalar(select(ConjuntoComponente.id).where(or_(
        ConjuntoComponente.conjunto_id == producto_id, ConjuntoComponente.componente_id == producto_id,
    )).limit(1)) is not None


def planear_datos(
    session: Session,
    producto_id: int,
    *,
    cambios: Mapping[str, object] | None = None,
    costo: object = None,
) -> PlanDatos:
    """Lo que cambiaría. No escribe nada; se vuelve a llamar en cada cambio.

    `cambios` trae solo los campos tocados ({"marca": "Claudia", …}); `costo`,
    si se escribe, va a todas las tallas activas."""
    producto = session.get(Producto, int(producto_id))
    if producto is None:
        raise ValueError("Esa prenda ya no existe.")
    antes = datos_de(producto)
    datos = dict(antes)
    plan = PlanDatos(producto_id=int(producto.id), nombre_antes=str(producto.nombre),
                     nombre=str(producto.nombre), antes=antes, datos=datos)
    for campo, valor in (cambios or {}).items():
        if campo not in LISTAS and campo not in TEXTOS:
            raise ValueError(f"Campo desconocido: {campo}")
        texto = str(valor or "").strip() if campo == "descripcion" else _texto(valor)
        if campo in LISTAS and texto:
            fila = _buscar(session, LISTAS[campo][0], texto)
            if fila is None:
                plan.errores.append(f"«{texto}» no está en la lista de {ROTULOS[campo].lower()}: elige uno de la lista.")
                continue
            texto = str(fila.nombre)
        if campo == "genero" and texto:
            oficial = next((g for g in GENEROS if valores.normalizar(g) == valores.normalizar(texto)), None)
            if oficial is None:
                plan.errores.append(f"Género: elige {', '.join(GENEROS[:-1])} o {GENEROS[-1]}.")
                continue
            texto = oficial
        if not texto and campo not in OPCIONALES:
            plan.errores.append(f"Falta {ROTULOS[campo].lower()}.")
            continue
        datos[campo] = texto

    for campo in (*LISTAS, *TEXTOS):
        if datos[campo] != antes[campo]:
            plan.cambios.append(Cambio(campo, antes[campo], datos[campo]))

    variantes = [v for v in producto.variantes if v.activo]
    plan.tallas = len(variantes)
    plan.costo, problema = _leer_costo(costo)
    if problema:
        plan.errores.append(problema)
    elif plan.costo is not None:
        costos = {v.costo_referencia for v in variantes}
        if costos != {plan.costo}:
            antes_costo = ", ".join(sorted(f"${c:.0f}" for c in costos if c is not None)) or "sin costo"
            plan.cambios.append(Cambio("costo", antes_costo, f"${plan.costo:.0f} en {plan.tallas} tallas"))

    if plan.cambia_escuela:
        _planear_escuela(session, producto, plan)
    if any(c.campo in ("tipo_pieza", "atributo") for c in plan.cambios):
        plan.avisos.append("El nombre no cambia solo: si hace falta, corrígelo con «✏️ Corregir prenda».")

    escuela = datos["escuela"] or None
    marca = _buscar(session, Marca, datos["marca"]) if datos["marca"] else None
    if any(c.campo != "costo" for c in plan.cambios):
        # El nombre se vuelve a armar igual que al guardar (`actualizar_producto`):
        # lo que se ve es lo que se guarda.
        base = CatalogService.nombre_sin_escuela(producto.nombre_base or producto.nombre, antes["escuela"] or None)
        plan.nombre = CatalogService.armar_nombre(base, escuela)
        if marca is not None:
            otro = session.scalar(select(Producto.id).where(
                Producto.id != producto.id, Producto.nombre == plan.nombre, Producto.marca_id == marca.id))
            if otro is not None:
                plan.errores.append(f"Ya existe otra prenda «{plan.nombre}» de la marca {marca.nombre}.")
    return plan


def _planear_escuela(session: Session, producto: Producto, plan: PlanDatos) -> None:
    antes, despues = plan.antes["escuela"], plan.datos["escuela"]
    if bool(antes) != bool(despues):
        plan.errores.append(
            "Una prenda de escuela no se vuelve general aquí (ni al revés): pídeselo a Claude."
        )
        return
    if _en_receta(session, producto.id):
        plan.errores.append(
            "Está en una receta (Pants 3pz o Chamarra): cambia la escuela desde «Uniformes por escuela»."
        )
        return
    piezas = session.scalars(
        select(UniformePieza).join(Uniforme, UniformePieza.uniforme_id == Uniforme.id).where(
            UniformePieza.producto_id == producto.id,
            UniformePieza.activo.is_(True),
            Uniforme.escuela_id == producto.escuela_id,
        )
    ).all()
    plan.piezas_a_mover = [int(p.id) for p in piezas]
    if piezas:
        plan.avisos.append(f"Sale del uniforme de {antes} y entra al de {despues}, en el mismo grupo.")


@dataclass(frozen=True)
class ResultadoDatos:
    producto_id: int
    nombre: str
    campos: int


def aplicar_datos(session: Session, plan: PlanDatos, usuario: Usuario, *, commit: bool = False) -> ResultadoDatos:
    """Guarda los datos, todo o nada (savepoint). Solo ADMIN."""
    if plan.errores:
        raise DatosNoValidos("\n".join(plan.errores))
    if not plan.hay_cambios:
        raise DatosNoValidos("No hay nada que cambiar.")
    CatalogService._validar_admin(usuario)
    with session.begin_nested():
        producto = session.get(Producto, plan.producto_id)
        if producto is None:
            raise ValueError("Esa prenda ya no existe.")
        if datos_de(producto) != plan.antes:
            raise DatosNoValidos("La prenda cambió mientras la editabas: revisa otra vez.")
        filas = {campo: (_buscar(session, LISTAS[campo][0], plan.datos[campo]) if plan.datos[campo] else None)
                 for campo in LISTAS}
        if filas["marca"] is None or filas["categoria"] is None:
            raise DatosNoValidos("Falta la marca o la categoría.")
        cambian_producto = [c for c in plan.cambios if c.campo != "costo"]
        if cambian_producto:
            base = CatalogService.nombre_sin_escuela(producto.nombre_base or producto.nombre,
                                                     plan.antes["escuela"] or None)
            CatalogService.actualizar_producto(
                session, usuario, producto,
                categoria=filas["categoria"], marca=filas["marca"], nombre=base,
                descripcion=plan.datos["descripcion"] or None, escuela=filas["escuela"],
                tipo_prenda=filas["tipo_prenda"], tipo_pieza=filas["tipo_pieza"],
                nivel_educativo=filas["nivel_educativo"], atributo=filas["atributo"],
                genero=plan.datos["genero"], escudo=plan.datos["escudo"], ubicacion=plan.datos["ubicacion"],
                observacion=ORIGEN_DATOS,
            )
        if plan.cambia_escuela and plan.piezas_a_mover:
            nuevo = us.uniforme_de(session, filas["escuela"].id, crear=True)
            for pieza_id in plan.piezas_a_mover:
                vieja = session.get(UniformePieza, pieza_id)
                if vieja is None:
                    continue
                us.agregar_pieza(session, nuevo.id, producto.id, grupo=vieja.grupo, color=vieja.color,
                                 obligatoria=vieja.obligatoria)
                us.quitar_pieza(session, vieja.id)
        if plan.costo is not None and any(c.campo == "costo" for c in plan.cambios):
            for v in session.scalars(select(Variante).where(
                    Variante.producto_id == producto.id, Variante.activo.is_(True)).order_by(Variante.id)).all():
                if v.costo_referencia == plan.costo:
                    continue
                CatalogService.actualizar_variante(
                    session, usuario, v, producto, v.sku, v.talla, v.color, v.precio_venta,
                    costo_referencia=plan.costo, stock_minimo=v.stock_minimo, observacion=ORIGEN_DATOS,
                )
        session.flush()
        resultado = ResultadoDatos(int(producto.id), str(producto.nombre), len(plan.cambios))
    if commit:
        session.commit()
    return resultado


__all__ = [
    "Cambio",
    "DatosNoValidos",
    "GENEROS",
    "LISTAS",
    "ORIGEN_DATOS",
    "OpcionesDatos",
    "PlanDatos",
    "ResultadoDatos",
    "aplicar_datos",
    "datos_de",
    "opciones_datos",
    "planear_datos",
]
