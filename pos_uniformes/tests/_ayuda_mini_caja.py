"""Una caja en miniatura para probar el motor del alta (SQLite en memoria).

Imita lo que hay en la tienda (perfil del 2026-11-13, `alta_datos.md`):
escuelas de primaria con el molde estándar (Pants 2pz, Pants 3pz, Playera,
Chamarra, Pants Suelto, Suéter, Chaleco), una de secundaria, prendas ligadas a
su uniforme y recetas de Pants 3pz y Chamarra. «Ignacio Allende (Jaral)» es
como quedó el 14-sep: copia de Ignacio Allende en Gris, sin Pants Suelto, sin
suéteres y sin chaleco; su Pants 3pz tiene receta y su Chamarra no (le falta
el Pants Suelto).

Los precios son de ejemplo, con la forma de las escaleras reales.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    ConjuntoComponente,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    RolUsuario,
    TipoPieza,
    TipoPrenda,
    Uniforme,
    UniformePieza,
    Usuario,
    Variante,
)

PRIMARIA = ["4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD"]

ESCALERAS = {
    "Pants Suelto": {"4": 245, "6": 245, "8": 245, "10": 245, "12": 245, "14": 255, "16": 255,
                     "CH": 285, "MD": 285, "GD": 295},
    "Pants 2pz": {"4": 485, "6": 485, "8": 485, "10": 485, "12": 485, "14": 495, "16": 495,
                  "CH": 585, "MD": 585, "GD": 595},
    "Pants 3pz": {"4": 585, "6": 585, "8": 585, "10": 585, "12": 585, "14": 595, "16": 595,
                  "CH": 685, "MD": 685, "GD": 695},
    "Playera": {"4": 199, "6": 199, "8": 199, "10": 199, "12": 209, "14": 209, "16": 209,
                "CH": 219, "MD": 225, "GD": 235},
    "Chamarra": {t: 335 for t in PRIMARIA},
}

NOMBRES = {
    "Pants Suelto": ("Pants Suelto", "Deportivo", None),
    "Pants 2pz": ("Pants 2pz Deportivo", "Deportivo", "Deportivo"),
    "Pants 3pz": ("Pants 3pz Deportivo", "Deportivo", "Deportivo"),
    "Playera": ("Playera Deportiva", "Deportivo", "Deportiva"),
    "Chamarra": ("Chamarra Deportiva", "Deportivo", "Deportiva"),
}


class MiniCaja:
    def __init__(self, engine) -> None:
        Base.metadata.create_all(engine)
        self.s = Session(engine, autoflush=False, expire_on_commit=False)
        s = self.s
        self.admin = Usuario(username="admin", nombre_completo="Admin", rol=RolUsuario.ADMIN, password_hash="x")
        self.cajera = Usuario(username="caja", nombre_completo="Caja", rol=RolUsuario.CAJERO, password_hash="x")
        self.cat = {n: Categoria(nombre=n) for n in ("Deportivo", "Oficial")}
        self.marca = Marca(nombre="Sin marca")
        self.nivel = {n: NivelEducativo(nombre=n) for n in ("Primaria", "Secundaria")}
        self.prenda = {n: TipoPrenda(nombre=n) for n in ("Deportivo", "Oficial", "Básico")}
        self.pieza = {
            n: TipoPieza(nombre=n)
            for n in ("Pants 2pz", "Pants 3pz", "Playera", "Chamarra", "Pants Suelto", "Suéter", "Chaleco")
        }
        self.atributo = {n: AtributoProducto(nombre=n) for n in ("Deportivo", "Deportiva")}
        s.add_all([self.admin, self.cajera, self.marca, *self.cat.values(), *self.nivel.values(),
                   *self.prenda.values(), *self.pieza.values(), *self.atributo.values()])
        s.flush()
        self._sku = 0

        self.escuelas: dict[str, Escuela] = {}
        self.productos: dict[tuple[str, str], Producto] = {}
        completas = ("Miguel Hidalgo", "Justo Sierra", "Ignacio Allende")
        for nombre in (*completas, "Benito Juárez", "Ignacio Allende (Jaral)"):
            self.escuelas[nombre] = self._escuela(nombre)
        for nombre in completas:
            for pieza in ("Pants 2pz", "Pants 3pz", "Playera", "Chamarra", "Pants Suelto"):
                self.prod(nombre, pieza)
        # Benito Juárez: su Pants Suelto lleva EXG (otro juego de tallas).
        for pieza in ("Pants 2pz", "Playera"):
            self.prod("Benito Juárez", pieza)
        self.prod("Benito Juárez", "Pants Suelto", extra={"EXG": 305})
        # Ignacio Allende también tiene suéter y chaleco (rojos).
        self.prod("Ignacio Allende", "Suéter", nombre="Suéter Botones M Rojo", prenda="Oficial", color="Rojo",
                  precios={**{t: 299 for t in ("4", "6", "8", "10")}, **{t: 315 for t in ("12", "14", "16")}})
        self.prod("Ignacio Allende", "Chaleco", nombre="Chaleco Rojo", prenda="Oficial", color="Rojo",
                  precios={t: 275 for t in ("4", "6", "8", "10", "12", "14", "16")})
        # Jaral (14-sep): en Gris, sin Pants Suelto, suéteres ni chaleco.
        for pieza in ("Pants 2pz", "Pants 3pz", "Playera", "Chamarra"):
            self.prod("Ignacio Allende (Jaral)", pieza, color="Gris")
        # Secundaria: otra escalera.
        self.escuelas["Técnica 18"] = self._escuela("Técnica 18")
        self.prod("Técnica 18", "Pants Suelto", nivel="Secundaria",
                  precios={**{t: 265 for t in ("12", "14", "16")}, "CH": 295, "MD": 295, "GD": 305})

        # Uniformes y recetas.
        for nombre, escuela in self.escuelas.items():
            uni = Uniforme(escuela_id=escuela.id, nombre="Uniforme")
            s.add(uni)
            s.flush()
            for orden, ((esc, pieza), prod) in enumerate(
                (k, v) for k, v in self.productos.items() if k[0] == nombre
            ):
                grupo = "Deportivo" if pieza in ESCALERAS else "Diario"
                s.add(UniformePieza(uniforme_id=uni.id, producto_id=prod.id, grupo=grupo, orden=orden + 1))
        for nombre in completas:
            self.receta(nombre, "Pants 3pz", [("Pants 2pz", 1), ("Playera", 1)])
            self.receta(nombre, "Chamarra", [("Pants 2pz", 1), ("Pants Suelto", -1)])
        self.receta("Ignacio Allende (Jaral)", "Pants 3pz", [("Pants 2pz", 1), ("Playera", 1)])
        s.commit()

    # ── piezas ────────────────────────────────────────────────────────────
    def _escuela(self, nombre: str) -> Escuela:
        e = Escuela(nombre=nombre)
        self.s.add(e)
        self.s.flush()
        return e

    def prod(self, escuela: str, pieza: str, *, nombre=None, prenda="Deportivo", color="Sin color",
             nivel="Primaria", precios=None, extra=None) -> Producto:
        base, _prenda, atributo = NOMBRES.get(pieza, (pieza, prenda, None))
        nombre = nombre or base
        esc = self.escuelas[escuela]
        precios = dict(precios or ESCALERAS[pieza])
        precios.update(extra or {})
        p = Producto(
            nombre=f"{nombre} {esc.nombre}", nombre_base=f"{nombre} {esc.nombre}",
            categoria_id=self.cat["Deportivo" if prenda == "Deportivo" else "Oficial"].id,
            marca_id=self.marca.id, escuela_id=esc.id,
            tipo_prenda_id=self.prenda[prenda].id, tipo_pieza_id=self.pieza[pieza].id,
            nivel_educativo_id=self.nivel[nivel].id,
            atributo_id=self.atributo[atributo].id if atributo else None,
            genero="Unisex", escudo="Con Escudo",
        )
        self.s.add(p)
        self.s.flush()
        for talla, precio in precios.items():
            self._sku += 1
            self.s.add(Variante(producto_id=p.id, sku=f"SKU{self._sku:06d}", talla=talla, color=color,
                                precio_venta=Decimal(precio), stock_actual=0))
        self.s.flush()
        self.productos[(escuela, pieza)] = p
        return p

    def receta(self, escuela: str, conjunto: str, piezas) -> None:
        c = self.productos[(escuela, conjunto)]
        for grupo, (pieza, cantidad) in enumerate(piezas):
            self.s.add(ConjuntoComponente(conjunto_id=c.id, componente_id=self.productos[(escuela, pieza)].id,
                                          cantidad=cantidad, grupo=grupo))
        self.s.flush()
