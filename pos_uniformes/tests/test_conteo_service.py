"""Tests para conteo_service — el conteo opera SOLO sobre stock de tienda.

Regla de negocio: contar en tienda nunca debe ver ni afectar bodega/piso.
La diferencia se calcula contra stock_tienda (= stock_actual - bodega - piso),
y al confirmar el ajuste solo se mueve la porción de tienda (stock_actual),
dejando intacto el contenido físico en cajas de bodega.
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    BodegaUbicacion,
    Categoria,
    Escuela,
    EstadoCaja,
    Marca,
    NivelEducativo,
    Producto,
    Variante,
)
from pos_uniformes.services.conteo_service import (
    confirmar_ajustes_lote,
    obtener_conteos_pendientes,
    registrar_conteo,
)


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_variante(session: Session, stock_actual: int = 20) -> Variante:
    cat = Categoria(nombre="Uniformes")
    marca = Marca(nombre="Genérica")
    session.add_all([cat, marca])
    session.flush()
    prod = Producto(
        nombre="Pants punto 2pz",
        nombre_base="Pants punto 2pz",
        categoria_id=cat.id,
        marca_id=marca.id,
    )
    session.add(prod)
    session.flush()
    variante = Variante(
        producto_id=prod.id,
        sku="PP2-T12",
        talla="T12",
        color="NEGRO",
        precio_venta=350.00,
        stock_actual=stock_actual,
    )
    session.add(variante)
    session.flush()
    return variante


def _meter_en_bodega(session: Session, variante: Variante, cantidad: int) -> None:
    """Mete `cantidad` piezas en una caja con ubicación real (rack != PISO)."""
    ub = BodegaUbicacion(codigo="A1-N1", rack="A1", nivel=1)
    session.add(ub)
    session.flush()
    caja = BodegaCaja(
        codigo="A-001",
        categoria="A",
        ubicacion_id=ub.id,
        estado=EstadoCaja.ACTIVA.value,
    )
    session.add(caja)
    session.flush()
    session.add(BodegaContenido(caja_id=caja.id, variante_id=variante.id, cantidad=cantidad))
    session.flush()


class TestConteoScopeTienda(unittest.TestCase):
    def test_diferencia_se_mide_contra_tienda_no_total(self) -> None:
        """Bug crítico: con stock en bodega, contar lo de tienda no debe
        producir diferencia falsa contra el total."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=20)
        _meter_en_bodega(session, v, 8)  # bodega=8 -> tienda=12

        # El usuario cuenta 12 en tienda (coincide con el sistema)
        conteo = registrar_conteo(session, v.id, stock_fisico=12, contado_por="Ana")

        # stock_sistema registrado debe ser el de tienda (12), no el total (20)
        self.assertEqual(conteo.stock_sistema, 12)
        # Y por tanto NO hay diferencia (antes daba 12 - 20 = -8)
        self.assertEqual(conteo.diferencia, 0)

    def test_diferencia_real_en_tienda(self) -> None:
        """Si se cuenta de más en tienda, la diferencia es contra tienda."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=20)
        _meter_en_bodega(session, v, 8)  # tienda=12

        conteo = registrar_conteo(session, v.id, stock_fisico=15, contado_por="Ana")
        self.assertEqual(conteo.stock_sistema, 12)
        self.assertEqual(conteo.diferencia, 3)  # 15 - 12, no 15 - 20

    def test_ajuste_solo_mueve_tienda_no_toca_bodega(self) -> None:
        """Confirmar el ajuste solo cambia la porción de tienda; el contenido
        físico de bodega queda intacto."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=20)
        _meter_en_bodega(session, v, 8)  # bodega=8, tienda=12

        conteo = registrar_conteo(session, v.id, stock_fisico=15, contado_por="Ana")
        session.flush()
        ajustados, _omitidos = confirmar_ajustes_lote(session, [conteo.id], "ADMIN")
        session.flush()

        self.assertEqual(ajustados, 1)
        session.refresh(v)
        # stock_actual sube exactamente la diferencia de tienda (+3): 20 -> 23
        self.assertEqual(v.stock_actual, 23)
        # La bodega física NO se tocó: sigue habiendo 8 piezas en la caja
        total_bodega = session.scalar(
            select(func.coalesce(func.sum(BodegaContenido.cantidad), 0))
            .where(BodegaContenido.variante_id == v.id)
        )
        self.assertEqual(total_bodega, 8)

    def test_ajuste_que_deja_stock_negativo_se_aplica_igual(self) -> None:
        """Si el stock bajó desde el conteo (ventas) y el ajuste deja el total
        en negativo, se aplica igual: el negativo es la señal de recontar. Antes
        se omitía y el número quedaba inflado justo en la talla que se acabó."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=10)  # tienda=10

        # Se contaron 3 (el conteo dice que faltan 7)
        conteo = registrar_conteo(session, v.id, stock_fisico=3, contado_por="Ana")
        session.flush()
        self.assertEqual(conteo.diferencia, -7)

        # Entre el conteo y el ajuste, el stock bajó a 2 (p.ej. ventas)
        v.stock_actual = 2
        session.flush()

        ajustados, omitidos = confirmar_ajustes_lote(session, [conteo.id], "ADMIN")
        self.assertEqual((ajustados, omitidos), (1, 0))
        session.flush()
        session.refresh(v)
        self.assertEqual(v.stock_actual, -5)
        self.assertTrue(conteo.ajustado)

    def test_sin_bodega_tienda_igual_a_total(self) -> None:
        """Sin stock en bodega, tienda == total (no hay regresión)."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=10)

        conteo = registrar_conteo(session, v.id, stock_fisico=10, contado_por="Ana")
        self.assertEqual(conteo.stock_sistema, 10)
        self.assertEqual(conteo.diferencia, 0)


class TestConteosPendientesPorNivel(unittest.TestCase):
    def _seed_en_nivel(
        self, session: Session, escuela: Escuela, nivel: NivelEducativo,
        sku: str, stock_actual: int,
    ) -> Variante:
        cat = session.query(Categoria).first() or Categoria(nombre="Uniformes")
        marca = session.query(Marca).first() or Marca(nombre="Genérica")
        session.add_all([cat, marca])
        session.flush()
        prod = Producto(
            nombre=f"Producto {sku}",
            nombre_base=f"Producto {sku}",
            categoria_id=cat.id,
            marca_id=marca.id,
            escuela_id=escuela.id,
            nivel_educativo_id=nivel.id,
        )
        session.add(prod)
        session.flush()
        v = Variante(
            producto_id=prod.id, sku=sku, talla="T12", color="NEGRO",
            precio_venta=350.00, stock_actual=stock_actual,
        )
        session.add(v)
        session.flush()
        return v

    def test_pendientes_se_filtran_por_nivel(self) -> None:
        session = _make_session()
        escuela = Escuela(nombre="Escuela X")
        primaria = NivelEducativo(nombre="Primaria")
        secundaria = NivelEducativo(nombre="Secundaria")
        session.add_all([escuela, primaria, secundaria])
        session.flush()

        v_prim = self._seed_en_nivel(session, escuela, primaria, "PRIM-1", 10)
        v_sec = self._seed_en_nivel(session, escuela, secundaria, "SEC-1", 10)

        # Conteos con diferencia (12 vs 10) en ambos niveles
        registrar_conteo(session, v_prim.id, stock_fisico=12, contado_por="Ana")
        registrar_conteo(session, v_sec.id, stock_fisico=12, contado_por="Ana")
        session.flush()

        # Sin filtro de nivel: ambos pendientes
        todos = obtener_conteos_pendientes(session, escuela.id)
        self.assertEqual(len(todos), 2)

        # Filtrando por Primaria: solo el de primaria
        solo_prim = obtener_conteos_pendientes(session, escuela.id, nivel_id=primaria.id)
        self.assertEqual(len(solo_prim), 1)
        self.assertEqual(solo_prim[0].variante_id, v_prim.id)


if __name__ == "__main__":
    unittest.main()


class TestOrdenDelUniforme(unittest.TestCase):
    """Catálogo fase 2: la hoja y el mapa listan las prendas en el orden del
    uniforme de la escuela; lo que no está en él va al final; sin uniforme,
    el orden de siempre (PIEZA_ORDER, nombre)."""

    def setUp(self) -> None:
        from pos_uniformes.database.models import TipoPieza
        from pos_uniformes.services import uniforme_service as us

        self.s = _make_session()
        cat = Categoria(nombre="Uniformes"); marca = Marca(nombre="Genérica")
        self.esc = Escuela(nombre="Justo Sierra"); self.otra = Escuela(nombre="Patria")
        self.s.add_all([cat, marca, self.esc, self.otra]); self.s.flush()
        tz = {n: TipoPieza(nombre=n) for n in ("Camisa", "Falda", "Chaleco", "Playera")}
        self.s.add_all(tz.values()); self.s.flush()

        def prod(nombre, escuela, pieza):
            p = Producto(nombre=nombre, nombre_base=nombre, categoria_id=cat.id, marca_id=marca.id, escuela_id=escuela.id, tipo_pieza_id=tz[pieza].id)
            self.s.add(p); self.s.flush()
            self.s.add(Variante(producto_id=p.id, sku=f"S{p.id}", talla="10", color="X", precio_venta=100, stock_actual=5))
            return p

        self.camisa = prod("Camisa JS", self.esc, "Camisa")
        self.falda = prod("Falda JS", self.esc, "Falda")
        self.chaleco = prod("Chaleco JS", self.esc, "Chaleco")
        self.playera = prod("Playera JS", self.esc, "Playera")
        prod("Camisa Patria", self.otra, "Camisa"); prod("Falda Patria", self.otra, "Falda")
        self.s.commit()
        self.us = us

    def _orden(self, escuela) -> list[str]:
        from pos_uniformes.services.conteo_service import obtener_variantes_agrupadas_por_producto
        return [g["producto_nombre"] for g in obtener_variantes_agrupadas_por_producto(self.s, escuela.id)]

    def test_sin_uniforme_es_el_orden_de_siempre(self) -> None:
        self.assertEqual(self._orden(self.esc), ["Playera JS", "Camisa JS", "Chaleco JS", "Falda JS"])

    def test_con_uniforme_manda_su_orden_y_lo_que_no_esta_va_al_final(self) -> None:
        uni = self.us.armar(self.s, self.esc.id)
        piezas = {p["nombre"]: p["pieza_id"] for p in self.us.piezas_de(self.s, uni.id)}
        # Daniel pone la falda hasta arriba y quita el chaleco del uniforme
        self.us.mover_pieza(self.s, piezas["Falda JS"], -10)
        self.us.quitar_pieza(self.s, piezas["Chaleco JS"]); self.s.commit()
        self.assertEqual(self._orden(self.esc), ["Falda JS", "Playera JS", "Camisa JS", "Chaleco JS"])
        # La otra escuela, sin uniforme, no se entera
        self.assertEqual(self._orden(self.otra), ["Camisa Patria", "Falda Patria"])

    def test_el_mapa_usa_el_mismo_orden(self) -> None:
        from pos_uniformes.services import conteo_mapa_service as mapa
        uni = self.us.armar(self.s, self.esc.id)
        piezas = {p["nombre"]: p["pieza_id"] for p in self.us.piezas_de(self.s, uni.id)}
        self.us.mover_pieza(self.s, piezas["Chaleco JS"], -10); self.s.commit()
        self.assertEqual([p["nombre"] for p in mapa.escuela(self.s, self.esc.id)["prendas"]][:2], ["Chaleco JS", "Playera JS"])
