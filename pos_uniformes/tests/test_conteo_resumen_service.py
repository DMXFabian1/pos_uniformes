"""El resumen del ajuste de un conteo (tanda 2 de «Revisar conteo», 2026-11-15).

Por talla: el sistema decía, contó, diferencia, vendidas desde el conteo,
tienda hoy, queda hoy, precio y otro ajuste posterior. Y el total."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    Categoria,
    ConjuntoComponente,
    ConteoInventario,
    Escuela,
    LibretaVenta,
    Marca,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    Variante,
)
from pos_uniformes.services import conteo_jornada_service as jn
from pos_uniformes.services import conteo_resumen_service as rs
from pos_uniformes.services import conteo_revision_vista_service as vista

CONTADO = datetime(2026, 10, 5, 17, 0)   # UTC sin zona, como lo guarda SQLite
HOY = date(2026, 11, 15)

# Jornada 86 (Playera Chazarilla Azul Marino), datos de la caja del 15-nov.
TALLAS_86 = ("4", "6", "8", "10", "12", "14", "16", "18", "20", "28", "30", "32", "34", "36", "38", "40", "42")
DIFERENCIAS_86 = {"8": (7, 6, 185), "32": (10, 6, 199), "34": (9, 8, 199), "36": (19, 18, 205)}
VENDIDAS_86 = {"16": 5, "32": 2, "34": 2, "38": 1, "40": 3}


def _tallita(talla: str, *, sistema: int, conto: int, diferencia: int | None = None, ajustado: bool = False,
             vendidas: int = 0, tienda: int = 0, precio="100", ajuste=None, producto: str = "Playera") -> rs.TallaResumen:
    dif = conto - sistema if diferencia is None else diferencia
    return rs.TallaResumen(
        conteo_id=hash(talla) % 1000, variante_id=1, producto=producto, talla=talla, stock_sistema=sistema,
        conto=conto, diferencia=dif, ajustado=ajustado, vendidas_desde=vendidas, tienda_hoy=tienda,
        queda_hoy=rs.queda_hoy(tienda_hoy=tienda, diferencia=dif, ajustado=ajustado),
        precio_venta=None if precio is None else Decimal(precio), ajuste_posterior=ajuste,
    )


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.escuela = Escuela(nombre="Chazarilla")
        self.cat, self.marca = Categoria(nombre="C"), Marca(nombre="M")
        self.s.add_all([self.escuela, self.cat, self.marca])
        self.s.flush()

    def tearDown(self) -> None:
        self.s.close()

    def _producto(self, nombre: str, tallas, *, precio=100, stock=0) -> dict[str, Variante]:
        p = Producto(nombre=nombre, nombre_base=nombre, categoria_id=self.cat.id, marca_id=self.marca.id, escuela_id=self.escuela.id)
        self.s.add(p)
        self.s.flush()
        out = {}
        for t in tallas:
            v = Variante(producto_id=p.id, sku=f"{p.id}-{t}", talla=t, color="AZUL MARINO", precio_venta=precio, stock_actual=stock)
            self.s.add(v)
            out[t] = v
        self.s.flush()
        return out

    def _jornada(self, renglones: list[tuple[Variante, int, int]], contado: datetime = CONTADO):
        """renglones: (variante, el sistema decía, contó)."""
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4", empleada_nombre="Stayce")
        for v, sistema, conto in renglones:
            self.s.add(ConteoInventario(
                variante_id=v.id, escuela_id=self.escuela.id, stock_sistema=sistema, stock_fisico=conto,
                diferencia=conto - sistema, contado_por="VEND-4", contado_at=contado, jornada_id=j.id,
            ))
        self.s.flush()
        return j

    def _venta(self, cuando: datetime, sku: str, cantidad: int, tipo: str = "venta", **extra) -> LibretaVenta:
        lv = LibretaVenta(
            employee_code="VEND-4", tipo=tipo, piezas=cantidad, monto_total=100 * cantidad,
            detalle=[{"sku": sku, "talla": "x", "nombre": "x", "cantidad": cantidad, "precio": "100", "subtotal": "100", **extra}],
            created_at=cuando,
        )
        self.s.add(lv)
        self.s.flush()
        return lv

    def _ajuste(self, v: Variante, cuando: datetime, cantidad: int, referencia: str | None = None) -> None:
        tipo = TipoMovimientoInventario.AJUSTE_ENTRADA if cantidad > 0 else TipoMovimientoInventario.AJUSTE_SALIDA
        self.s.add(MovimientoInventario(
            variante_id=v.id, tipo_movimiento=tipo, cantidad=cantidad, stock_anterior=0, stock_posterior=cantidad,
            referencia=referencia, creado_por="x", created_at=cuando,
        ))
        self.s.flush()

    def _caja(self, codigo: str, v: Variante, cantidad: int) -> None:
        caja = BodegaCaja(codigo=codigo)
        self.s.add(caja)
        self.s.flush()
        self.s.add(BodegaContenido(caja_id=caja.id, variante_id=v.id, cantidad=cantidad))
        self.s.flush()

    @staticmethod
    def _por_talla(r: rs.ResumenAjuste) -> dict[str, rs.TallaResumen]:
        return {t.talla: t for t in r.tallas}


class CasoJornada86Tests(_Base):
    """El caso tipo: 4 tallas a corregir, faltan 7, −$1,385, 13 vendidas después."""

    def setUp(self) -> None:
        super().setUp()
        vs = self._producto("Playera Chazarilla Azul Marino", TALLAS_86, precio=185)
        renglones = []
        for t, v in vs.items():
            sistema, conto, precio = DIFERENCIAS_86.get(t, (6, 6, 185))
            v.precio_venta = precio
            # Hoy: lo de tienda = lo que decía − lo vendido; la 32 trae 12 en cajas (stock_actual 20).
            v.stock_actual = sistema - VENDIDAS_86.get(t, 0)
            renglones.append((v, sistema, conto))
        self.s.flush()
        self._caja("A-12", vs["32"], 12)
        vs["32"].stock_actual += 12
        self.j = self._jornada(renglones)
        for t, n in VENDIDAS_86.items():
            self._venta(CONTADO + timedelta(days=3), vs[t].sku, n)
        self._venta(CONTADO - timedelta(days=2), vs["16"].sku, 4)   # antes del conteo: no cuenta
        self.vs = vs

    def test_totales(self) -> None:
        r = rs.resumen_de_jornada(self.s, self.j)
        self.assertEqual(len(r.tallas), len(TALLAS_86))
        self.assertEqual((r.tallas_a_corregir, r.salen, r.entran), (4, 7, 0))
        self.assertEqual(r.valor, Decimal("-1385"))
        self.assertEqual(r.vendidas_desde, 13)
        self.assertEqual((r.tallas_con_ajuste_posterior, r.tallas_sin_precio), (0, 0))
        self.assertEqual([t.talla for t in r.a_corregir], ["8", "32", "34", "36"])

    def test_la_talla_32(self) -> None:
        t = self._por_talla(rs.resumen_de_jornada(self.s, self.j))["32"]
        self.assertEqual((t.stock_sistema, t.conto, t.diferencia, t.vendidas_desde), (10, 6, -4, 2))
        # stock_actual 20 incluye las 12 de la caja: en tienda hay 8; al corregir quedan 4.
        self.assertEqual((t.tienda_hoy, t.queda_hoy), (8, 4))
        self.assertEqual(t.precio_venta, Decimal("199"))
        self.assertEqual(t.valor, Decimal("-796"))
        self.assertIsNone(t.ajuste_posterior)

    def test_los_textos(self) -> None:
        r = rs.resumen_de_jornada(self.s, self.j)
        self.assertEqual(vista.texto_resumen_ajuste(r), "Se corrigen 4 tallas: faltan 7, sobran 0 (−$1,385 a precio de venta).")
        self.assertEqual(vista.texto_ojo_ajuste_posterior(r), "")
        self.assertEqual(
            vista.aviso_conteo_viejo(41, r),
            "Conteo de hace 41 días: desde entonces se vendieron 13 piezas. Conviene recontar antes de corregir.",
        )
        texto = vista.texto_confirmar_aplicar(
            quien="Stayce", contado=CONTADO, diferencias=[t.diferencia for t in r.a_corregir], hoy=HOY, resumen=r,
        )
        self.assertIn("A cada talla se le suma la diferencia que encontró Stayce el lun 5 oct.", texto)
        self.assertIn("Se corrigen 4 tallas: faltan 7, sobran 0 (−$1,385 a precio de venta).", texto)
        self.assertIn("desde entonces se vendieron 13 piezas", texto)
        self.assertNotIn("Ojo", texto)

    def test_con_otro_ajuste_en_la_36(self) -> None:
        self._ajuste(self.vs["36"], datetime(2026, 10, 20, 18, 0), -2)
        r = rs.resumen_de_jornada(self.s, self.j)
        self.assertEqual(self._por_talla(r)["36"].ajuste_posterior.date(), date(2026, 10, 20))
        self.assertEqual(r.tallas_con_ajuste_posterior, 1)
        self.assertEqual(
            vista.texto_ojo_ajuste_posterior(r),
            "Ojo: la talla 36 tuvo otro ajuste el 20 oct; se le suma la diferencia otra vez.",
        )
        self.assertEqual(
            vista.aviso_conteo_viejo(41, r),
            "Conteo de hace 41 días: desde entonces se vendieron 13 piezas y la talla 36 (20 oct) tuvo otro ajuste. "
            "Conviene recontar antes de corregir.",
        )
        # Corto (la ventana de Revisar): con una sola talla dice lo mismo.
        self.assertEqual(vista.aviso_conteo_viejo(41, r, corto=True), vista.aviso_conteo_viejo(41, r))

    def test_el_aviso_corto_solo_cuenta_las_tallas_con_otro_ajuste(self) -> None:
        # Escuela grande: el aviso enumeraba hasta 5 tallas y se iba a 3 líneas al 125 %.
        self._ajuste(self.vs["36"], datetime(2026, 10, 20, 18, 0), -2)
        self._ajuste(self.vs["8"], datetime(2026, 10, 21, 18, 0), -1)
        r = rs.resumen_de_jornada(self.s, self.j)
        self.assertEqual(
            vista.aviso_conteo_viejo(41, r, corto=True),
            "Conteo de hace 41 días: desde entonces se vendieron 13 piezas y 2 tallas tuvieron otro ajuste. "
            "Conviene recontar antes de corregir.",
        )
        self.assertIn("(20 oct)", vista.aviso_conteo_viejo(41, r))     # el largo (tooltip) trae el detalle

    def test_la_confirmacion_nombra_la_36_una_sola_vez(self) -> None:
        self._ajuste(self.vs["36"], datetime(2026, 10, 20, 18, 0), -2)
        r = rs.resumen_de_jornada(self.s, self.j)
        texto = vista.texto_confirmar_aplicar(
            quien="Stayce", contado=CONTADO, diferencias=[t.diferencia for t in r.a_corregir], hoy=HOY, resumen=r,
        )
        self.assertIn("Ojo: la talla 36 tuvo otro ajuste el 20 oct; se le suma la diferencia otra vez.", texto)
        self.assertIn("⚠ Conteo de hace 41 días: desde entonces se vendieron 13 piezas. Conviene recontar", texto)
        self.assertEqual(texto.count("36"), 1)

    def test_pocas_consultas_sin_importar_cuantas_tallas(self) -> None:
        sentencias = []
        event.listen(self.engine, "before_cursor_execute", lambda *a, **k: sentencias.append(1))
        rs.resumen_de_jornada(self.s, self.j)
        self.assertLessEqual(len(sentencias), 6)

    def test_pocas_consultas_con_muchos_conjuntos_vendidos(self) -> None:
        # 20 tallas de Pants 3pz (receta: la playera de la jornada) vendidas después del conteo.
        tallas = tuple(str(n) for n in range(2, 42, 2))
        pz3 = self._producto("Pants 3pz", tallas)
        p3 = pz3[tallas[0]].producto_id
        self.s.add(ConjuntoComponente(conjunto_id=p3, componente_id=self.vs["32"].producto_id, cantidad=1, grupo=0))
        self.s.flush()
        for t in tallas:
            self._venta(CONTADO + timedelta(days=2), pz3[t].sku, 1)
        sentencias = []
        event.listen(self.engine, "before_cursor_execute", lambda *a, **k: sentencias.append(1))
        r = rs.resumen_de_jornada(self.s, self.j)
        self.assertLessEqual(len(sentencias), 8)
        # Las 20 tallas del 3pz solo tocan las de la playera que existen (4..42 de la jornada).
        por = self._por_talla(r)
        self.assertEqual(por["32"].vendidas_desde, 3)   # 2 sueltas + 1 en el 3pz
        self.assertEqual(por["16"].vendidas_desde, 6)
        self.assertEqual(por["4"].vendidas_desde, 1)


class VendidasDesdeTests(_Base):
    def test_cuenta_desde_el_momento_del_conteo_no_desde_el_dia(self) -> None:
        v = self._producto("P", ("6",))["6"]
        j = self._jornada([(v, 5, 5)])
        self._venta(CONTADO - timedelta(hours=2), v.sku, 3)    # mismo día, antes de contar
        self._venta(CONTADO + timedelta(hours=1), v.sku, 1)
        self._venta(CONTADO + timedelta(days=1), v.sku, 2, tipo="apartado")
        self._venta(CONTADO + timedelta(days=1), v.sku, 9, tipo="abono")   # no se lleva piezas
        self.assertEqual(rs.resumen_de_jornada(self.s, j).tallas[0].vendidas_desde, 3)

    def test_un_conjunto_vendido_cuenta_en_sus_piezas(self) -> None:
        pz2 = self._producto("Pants 2pz", ("10",))
        play = self._producto("Playera", ("10",))
        pz3 = self._producto("Pants 3pz", ("10",))
        p3 = self.s.get(Variante, pz3["10"].id).producto_id
        for comp in (pz2["10"], play["10"]):
            self.s.add(ConjuntoComponente(conjunto_id=p3, componente_id=comp.producto_id, cantidad=1, grupo=0))
        self.s.flush()
        j = self._jornada([(pz2["10"], 4, 4), (play["10"], 3, 3)])
        self._venta(CONTADO + timedelta(days=1), pz3["10"].sku, 2)
        self._venta(CONTADO + timedelta(days=1), play["10"].sku, 1)
        por = self._por_talla_producto(rs.resumen_de_jornada(self.s, j))
        self.assertEqual(por["Pants 2pz"].vendidas_desde, 2)
        self.assertEqual(por["Playera"].vendidas_desde, 3)

    def _por_talla_producto(self, r):
        return {t.producto: t for t in r.tallas}

    def test_una_venta_borrada_no_cuenta_y_un_cambio_resta_lo_que_regresa(self) -> None:
        vs = self._producto("P", ("6", "8"))
        j = self._jornada([(vs["6"], 5, 5), (vs["8"], 5, 5)])
        borrada = self._venta(CONTADO + timedelta(days=1), vs["6"].sku, 2)
        self._venta(CONTADO + timedelta(days=1), vs["6"].sku, 3)
        # El dueño borra la venta: sale de la Libreta (y su stock regresa).
        self.s.delete(borrada)
        self.s.flush()
        # Cambio: regresa una 6 y se lleva una 8.
        self.s.add(LibretaVenta(
            employee_code="VEND-4", tipo="cambio", piezas=0, monto_total=0,
            detalle=[
                {"cambio": "entra", "sku": vs["6"].sku, "cantidad": 1},
                {"cambio": "sale", "sku": vs["8"].sku, "cantidad": 1},
            ],
            created_at=CONTADO + timedelta(days=2),
        ))
        self.s.flush()
        por = self._por_talla(rs.resumen_de_jornada(self.s, j))
        self.assertEqual((por["6"].vendidas_desde, por["8"].vendidas_desde), (2, 1))


class AjustadoTests(_Base):
    def test_ya_ajustado_no_se_corrige_otra_vez_y_su_ajuste_no_es_ajeno(self) -> None:
        vs = self._producto("P", ("6", "8"), stock=10)
        j = self._jornada([(vs["6"], 10, 7), (vs["8"], 10, 10)])
        antes = rs.resumen_de_jornada(self.s, j)
        self.assertEqual(self._por_talla(antes)["6"].queda_hoy, 7)
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        jn.aplicar_jornada(self.s, j, revisada_por="VEND-1")
        self.s.flush()
        r = rs.resumen_de_jornada(self.s, j)
        t6 = self._por_talla(r)["6"]
        self.assertTrue(t6.ajustado)
        self.assertEqual((t6.tienda_hoy, t6.queda_hoy), (7, 7))
        self.assertIsNone(t6.ajuste_posterior)        # el CONTEO-<id> propio no cuenta
        self.assertEqual((r.tallas_a_corregir, r.salen, r.valor), (0, 0, Decimal("0")))


class AjustePosteriorTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.vs = self._producto("P", ("6", "8", "10", "12"))
        self.j = self._jornada([(v, 5, 4) for v in self.vs.values()])
        self.ids = {c.variante_id: c.id for c in self.s.scalars(select(ConteoInventario))}

    def test_propio_vs_ajeno(self) -> None:
        despues = CONTADO + timedelta(days=5)
        v6, v8, v10, v12 = (self.vs[t] for t in ("6", "8", "10", "12"))
        self._ajuste(v6, despues, -1, rs.referencia_de(self.ids[v6.id]))        # el de este conteo
        self._ajuste(v8, despues, 2, "CONTEO-99999")                             # otro conteo aplicado
        self._ajuste(v8, despues + timedelta(days=3), -1, None)                  # luego uno a mano
        self._ajuste(v10, CONTADO - timedelta(days=1), 3, None)                   # antes del conteo
        self._ajuste(v10, despues, -1, "libreta:17")                             # lo hizo la venta
        self._ajuste(v12, despues, 1, "derivado:4")                              # stock de un conjunto
        por = self._por_talla(rs.resumen_de_jornada(self.s, self.j))
        self.assertIsNone(por["6"].ajuste_posterior)
        self.assertEqual(por["8"].ajuste_posterior.date(), despues.date())      # el primero
        self.assertIsNone(por["10"].ajuste_posterior)
        self.assertIsNone(por["12"].ajuste_posterior)

    def test_referencia_exacta(self) -> None:
        v6 = self.vs["6"]
        propia = rs.referencia_de(self.ids[v6.id])
        self._ajuste(v6, CONTADO + timedelta(days=1), 1, propia + "0")   # CONTEO-10 no es CONTEO-1
        self.assertIsNotNone(self._por_talla(rs.resumen_de_jornada(self.s, self.j))["6"].ajuste_posterior)

    def test_otro_ajuste_que_no_es_venta_si_cuenta(self) -> None:
        self._ajuste(self.vs["12"], CONTADO + timedelta(days=2), 3, "A-12")   # recuento de caja
        r = rs.resumen_de_jornada(self.s, self.j)
        self.assertEqual(r.tallas_con_ajuste_posterior, 1)


class ResumirPuroTests(unittest.TestCase):
    def test_precio_nulo_no_entra_al_valor_y_se_dice(self) -> None:
        r = rs.resumir([
            _tallita("6", sistema=5, conto=3, precio="150"),
            _tallita("8", sistema=5, conto=7, precio=None),
            _tallita("10", sistema=5, conto=5),
        ])
        self.assertEqual((r.tallas_a_corregir, r.salen, r.entran), (2, 2, 2))
        self.assertEqual(r.valor, Decimal("-300"))
        self.assertEqual(r.tallas_sin_precio, 1)
        self.assertEqual(
            vista.texto_resumen_ajuste(r),
            "Se corrigen 2 tallas: faltan 2, sobran 2 (−$300 a precio de venta; 1 talla sin precio).",
        )

    def test_una_sola_talla_y_sobrantes(self) -> None:
        r = rs.resumir([_tallita("6", sistema=5, conto=8, precio="199.50")])
        self.assertEqual(vista.texto_resumen_ajuste(r), "Se corrige 1 talla: faltan 0, sobran 3 (+$598.50 a precio de venta).")

    def test_queda_hoy(self) -> None:
        self.assertEqual(rs.queda_hoy(tienda_hoy=8, diferencia=-4, ajustado=False), 4)
        self.assertEqual(rs.queda_hoy(tienda_hoy=1, diferencia=-3, ajustado=False), -2)
        self.assertEqual(rs.queda_hoy(tienda_hoy=8, diferencia=-4, ajustado=True), 8)

    def test_varias_tallas_con_otro_ajuste(self) -> None:
        r = rs.resumir([
            _tallita("32", sistema=10, conto=6, ajuste=datetime(2026, 10, 18, 18)),
            _tallita("36", sistema=19, conto=18, ajuste=datetime(2026, 10, 20, 18)),
            _tallita("38", sistema=2, conto=2, ajuste=datetime(2026, 10, 21, 18)),   # sin diferencia: no recibe nada
        ])
        self.assertEqual(
            vista.texto_ojo_ajuste_posterior(r),
            "Ojo: las tallas 32 (18 oct) y 36 (20 oct) tuvieron otro ajuste después del conteo; se les suma la diferencia otra vez.",
        )
        self.assertEqual(
            vista.texto_desde_entonces(r),
            "desde entonces las tallas 32 (18 oct), 36 (20 oct) y 38 (21 oct) tuvieron otro ajuste",
        )

    def test_con_varias_prendas_dice_cual(self) -> None:
        r = rs.resumir([
            _tallita("10", sistema=4, conto=3, producto="Pants 2pz | Oficial", ajuste=datetime(2026, 10, 20, 18)),
            _tallita("10", sistema=4, conto=4, producto="Playera"),
        ])
        self.assertEqual(
            vista.texto_ojo_ajuste_posterior(r),
            "Ojo: Pants 2pz 10 tuvo otro ajuste el 20 oct; se le suma la diferencia otra vez.",
        )

    def test_sin_nada_que_decir(self) -> None:
        r = rs.resumir([_tallita("6", sistema=5, conto=5)])
        self.assertEqual(vista.texto_desde_entonces(r), "")
        self.assertEqual(vista.aviso_conteo_viejo(41, r), "Conteo de hace 41 días: conviene recontar antes de corregir.")
        self.assertEqual(vista.aviso_conteo_viejo(3, r), "")
        self.assertEqual(vista.texto_resumen_ajuste(r), "Ninguna talla cambia.")

    def test_una_pieza_vendida(self) -> None:
        r = rs.resumir([_tallita("6", sistema=5, conto=5, vendidas=1)])
        self.assertEqual(vista.texto_desde_entonces(r), "desde entonces se vendió 1 pieza")

    def test_linea_de_la_talla_para_el_por_que(self) -> None:
        t = _tallita("32", sistema=10, conto=6, vendidas=2, tienda=8)
        self.assertEqual(vista.texto_talla_ajuste(t), "el sistema decía 10, contó 6 (−4) · vendidas desde el conteo 2 · queda hoy 4")
        t = _tallita("10", sistema=2, conto=0, vendidas=1, tienda=1, ajuste=datetime(2026, 10, 20, 18))
        self.assertEqual(
            vista.texto_talla_ajuste(t),
            "el sistema decía 2, contó 0 (−2) · vendidas desde el conteo 1 · queda hoy -1 (recontar) · otro ajuste el 20 oct",
        )
        t = _tallita("6", sistema=4, conto=4, tienda=4)
        self.assertEqual(vista.texto_talla_ajuste(t), "el sistema decía 4, contó 4 (cuadra) · vendidas desde el conteo 0")


class PesosTests(unittest.TestCase):
    def test_formato(self) -> None:
        self.assertEqual(vista.pesos(Decimal("1385")), "$1,385")
        self.assertEqual(vista.pesos(Decimal("-1385"), signo=True), "−$1,385")
        self.assertEqual(vista.pesos(Decimal("300"), signo=True), "+$300")
        self.assertEqual(vista.pesos(0, signo=True), "$0")
        self.assertEqual(vista.pesos(Decimal("12.5")), "$12.50")


if __name__ == "__main__":
    unittest.main()
