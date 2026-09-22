"""Jornadas de conteo: abrir, retomar, avance, terminar, revisar y aplicar."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConteoInventario,
    Escuela,
    Marca,
    Producto,
    Variante,
)
from pos_uniformes.services import conteo_jornada_service as jn
from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote


def _seed(session: Session, nombre: str, *, productos: int = 2, tallas=("6", "8"), stock: int = 10):
    e = Escuela(nombre=nombre)
    session.add(e)
    session.flush()
    cat = Categoria(nombre=f"C{nombre}")
    marca = Marca(nombre=f"M{nombre}")
    session.add_all([cat, marca])
    session.flush()
    for i in range(productos):
        prod = Producto(
            nombre=f"Prenda {i} {nombre}", nombre_base=f"Prenda {i} {nombre}",
            categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id,
        )
        session.add(prod)
        session.flush()
        for talla in tallas:
            session.add(Variante(
                producto_id=prod.id, sku=f"S{nombre}{i}{talla}", talla=talla,
                color="AZUL", precio_venta=100, stock_actual=stock,
            ))
    session.flush()
    return e


def _seed_basicos(session: Session, escuela, tipo: str, prendas=("Pantalón Gris Escolar", "Pantalón Azul Escolar"), tallas=("6", "8")):
    """Productos básicos (sin escuela) de un tipo, ligados por catálogo a `escuela`."""
    from pos_uniformes.database.models import CatalogSchoolProductLink, TipoPieza

    tp = session.scalar(select(TipoPieza).where(TipoPieza.nombre == tipo))
    if tp is None:
        tp = TipoPieza(nombre=tipo)
        session.add(tp)
        session.flush()
    cat = session.scalar(select(Categoria))
    marca = session.scalar(select(Marca))
    nombres = []
    for nombre in prendas:
        completo = f"{nombre} | Oficial | {tipo}"
        prod = Producto(nombre=completo, nombre_base=nombre, categoria_id=cat.id, marca_id=marca.id, escuela_id=None, tipo_pieza_id=tp.id)
        session.add(prod)
        session.flush()
        session.add(CatalogSchoolProductLink(escuela_id=escuela.id, producto_id=prod.id, activo=True))
        for talla in tallas:
            session.add(Variante(producto_id=prod.id, sku=f"B{prod.id}{talla}", talla=talla, color="X", precio_venta=100, stock_actual=5))
        nombres.append(completo)
    session.flush()
    return nombres


class JornadaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.escuela = _seed(self.s, "Uno")
        self.s.commit()

    def tearDown(self) -> None:
        self.s.close()

    def _variantes(self):
        return list(self.s.scalars(select(Variante).order_by(Variante.id)).all())

    def test_abrir_anota_cuantas_tallas_abarca(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="vend-4", empleada_nombre="Stayce")
        self.assertEqual(j.total_tallas, 4)          # 2 prendas × 2 tallas
        self.assertEqual(j.empleada_code, "VEND-4")  # normalizado
        self.assertEqual(j.titulo, "Uno")
        self.assertIsNone(j.terminada_at)
        self.assertIn(j, jn.jornadas_abiertas(self.s))

    def test_sin_gafete_no_hay_jornada(self) -> None:
        with self.assertRaises(ValueError):
            jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="  ")

    def test_el_avance_cuenta_tallas_y_prendas_completas(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        v = self._variantes()
        # Prenda 0 completa (sus 2 tallas), prenda 1 a medias (1 de 2).
        registrar_conteos_lote(
            self.s,
            [ConteoInput(v[0].id, 9), ConteoInput(v[1].id, 10), ConteoInput(v[2].id, 0)],
            "Stayce (VEND-4)",
            jornada_id=j.id,
        )
        a = jn.avance(self.s, j)
        self.assertEqual((a.tallas_hechas, a.tallas_total), (3, 4))
        self.assertEqual((a.prendas_hechas, a.prendas_total), (1, 2))
        self.assertEqual(a.porcentaje, 75)
        self.assertFalse(a.completa)

    def test_al_retomar_se_ve_lo_ya_capturado(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        v = self._variantes()
        registrar_conteos_lote(self.s, [ConteoInput(v[0].id, 7)], "x", jornada_id=j.id)
        self.assertEqual(jn.capturado_en_jornada(self.s, j.id), {v[0].id: 7})

    def test_cualquiera_con_gafete_la_sigue(self) -> None:
        # 2026-09-13: las empleadas imprimían con la sesión de otra y luego no
        # podían capturar. La jornada es de la escuela; cada talla guarda quién.
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        self.assertTrue(jn.puede_seguirla(j, "VEND-4"))
        self.assertTrue(jn.puede_seguirla(j, "VEND-1"))
        self.assertTrue(jn.puede_seguirla(j, "VEND-5"))
        self.assertFalse(jn.puede_seguirla(j, ""))
        jn.terminar_jornada(self.s, j, empleada_code="VEND-5")
        self.assertIsNotNone(j.terminada_at)

    def test_una_sola_jornada_abierta_por_escuela(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4", empleada_nombre="Fanny")
        with self.assertRaises(jn.JornadaEnProceso) as ctx:
            jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-5")
        self.assertIs(ctx.exception.jornada, j)
        self.assertIn("Fanny", str(ctx.exception))
        self.assertIs(jn.jornada_abierta_de(self.s, self.escuela.id), j)
        self.assertEqual(jn.abiertas_por_alcance(self.s), {self.escuela.id: j})
        # Otra escuela sí puede abrir a la vez.
        otra = _seed(self.s, "Dos")
        self.s.flush()
        jn.abrir_jornada(self.s, escuela_id=otra.id, empleada_code="VEND-5")
        # Y al terminarla, la misma escuela vuelve a poder abrirse.
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        self.assertIsNone(jn.jornada_abierta_de(self.s, self.escuela.id))
        jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-5")

    def test_eliminar_una_jornada_a_medias_se_lleva_sus_tallas(self) -> None:
        # Se abrieron dos de la misma escuela (antes de la regla de una sola): sobra una.
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        v = self._variantes()
        registrar_conteos_lote(self.s, [ConteoInput(v[0].id, 3)], "x", jornada_id=j.id)
        self.assertFalse(jn.puede_eliminarla(j, "VEND-5"))
        with self.assertRaises(PermissionError):
            jn.eliminar_jornada(self.s, j, empleada_code="VEND-5")
        self.assertTrue(jn.puede_eliminarla(j, "VEND-4"))
        n = jn.eliminar_jornada(self.s, j, empleada_code="VEND-1")
        self.s.commit()
        self.assertEqual(n, 1)
        self.assertEqual(jn.jornadas_abiertas(self.s), [])
        self.assertEqual(self.s.scalars(select(ConteoInventario)).all(), [])
        self.assertEqual(v[0].stock_actual, 10)   # nunca tocó el inventario

    def test_una_terminada_no_se_elimina(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        self.assertFalse(jn.puede_eliminarla(j, "VEND-1"))
        with self.assertRaises(PermissionError):
            jn.eliminar_jornada(self.s, j, empleada_code="VEND-1")

    def test_reasignar_solo_el_dueno_y_lo_capturado_conserva_quien(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4", empleada_nombre="Stayce")
        v = self._variantes()
        registrar_conteos_lote(self.s, [ConteoInput(v[0].id, 3)], "Stayce (VEND-4)", jornada_id=j.id)
        with self.assertRaises(PermissionError):
            jn.reasignar_jornada(self.s, j, a_code="VEND-5", a_nombre="Fanny", por_code="VEND-4")
        jn.reasignar_jornada(self.s, j, a_code="vend-5", a_nombre="Fanny Ortiz", por_code="VEND-1")
        self.assertEqual((j.empleada_code, j.quien if hasattr(j, "quien") else j.empleada_nombre), ("VEND-5", "Fanny Ortiz"))
        self.assertEqual(self.s.scalars(select(ConteoInventario)).one().contado_por, "Stayce (VEND-4)")

    def test_el_tablero_trae_todas_las_escuelas_en_orden(self) -> None:
        from datetime import datetime, timedelta

        dos = _seed(self.s, "Dos")
        tres = _seed(self.s, "Tres")
        self.s.commit()
        # Uno: jornada aplicada ayer. Dos: en proceso. Tres: nunca.
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4", empleada_nombre="Stayce")
        v = self._variantes()
        registrar_conteos_lote(self.s, [ConteoInput(v[0].id, 3)], "x", jornada_id=j.id)
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        jn.aplicar_jornada(self.s, j, revisada_por="VEND-1")
        self.s.commit()
        j.terminada_at = datetime.now() - timedelta(days=1)
        self.s.commit()
        jn.abrir_jornada(self.s, escuela_id=dos.id, empleada_code="VEND-5", empleada_nombre="Fanny")
        self.s.commit()
        filas = jn.tablero_conteos(self.s)
        self.assertEqual([f.titulo for f in filas], ["Dos", "Uno", "Tres"])
        self.assertEqual((filas[0].estado, filas[0].quien_en_proceso), ("En proceso", "Fanny"))
        self.assertEqual((filas[1].estado, filas[1].tallas, filas[1].ultimo.quien), ("Aplicada", "1 de 4", "Stayce"))
        self.assertEqual((filas[2].estado, filas[2].tallas, filas[2].dias), ("Nunca", "", None))

    def test_el_tablero_trae_lo_capturado_de_todas_las_jornadas_de_un_jalon(self) -> None:
        # Una consulta para todas (antes una por escuela: 85 consultas y 1.5 s
        # en abrir Conteos por wifi).
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        v = self._variantes()
        registrar_conteos_lote(self.s, [ConteoInput(v[0].id, 3), ConteoInput(v[1].id, 0)], "x", jornada_id=j.id)
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        self.s.commit()
        lote = jn.capturado_por_jornada(self.s, [j.id, 999])
        self.assertEqual(lote, {j.id: {v[0].id: 3, v[1].id: 0}, 999: {}})
        # avance con lo ya traído no vuelve a preguntar por lo capturado
        with patch.object(jn, "capturado_en_jornada", side_effect=AssertionError("no debía consultar")):
            a = jn.avance(self.s, j, lote[j.id])
        self.assertEqual((a.tallas_hechas, a.tallas_total), (2, 4))

    def test_alcances_en_lote_da_lo_mismo_que_alcance_uno_por_uno(self) -> None:
        dos = _seed(self.s, "Dos")
        _seed_basicos(self.s, self.escuela, "Pantalón")
        self.s.commit()
        j1 = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        j2 = jn.abrir_jornada(self.s, escuela_id=dos.id, empleada_code="VEND-5")
        j3 = jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", empleada_code="VEND-6")
        self.s.commit()
        lote = jn.alcances_en_lote(self.s, [j1, j2, j3])
        for j in (j1, j2, j3):
            uno = jn.alcance(self.s, j.escuela_id, j.tipo_pieza, j.prenda)
            self.assertEqual(
                [(g["producto_nombre"], [v.variante_id for v in g["variantes"]]) for g in lote[j.id]],
                [(g["producto_nombre"], [v.variante_id for v in g["variantes"]]) for g in uno],
            )
        self.assertTrue(lote[j1.id] and lote[j3.id])

    def test_el_tablero_no_pregunta_escuela_por_escuela(self) -> None:
        _seed(self.s, "Dos"); _seed(self.s, "Tres")
        for e, code in ((self.escuela, "VEND-4"),):
            j = jn.abrir_jornada(self.s, escuela_id=e.id, empleada_code=code)
            jn.terminar_jornada(self.s, j, empleada_code=code)
        self.s.commit()
        with patch.object(jn, "alcance", side_effect=AssertionError("el tablero debe usar alcances_en_lote")), patch.object(
            jn, "capturado_en_jornada", side_effect=AssertionError("el tablero debe usar capturado_por_jornada")
        ):
            filas = jn.tablero_conteos(self.s)
        self.assertEqual(len(filas), 3)

    def test_imprimir_la_hoja_abre_la_jornada_a_nombre_de_quien_imprime(self) -> None:
        # Daniel (2026-09-18): imprimían conteos que otra ya estaba haciendo, porque imprimir no dejaba huella.
        j, ya_habia = jn.registrar_impresion(self.s, escuela_id=self.escuela.id, empleada_code="VEND-5", empleada_nombre="Fanny")
        self.s.commit()
        self.assertFalse(ya_habia)
        self.assertEqual((j.empleada_code, j.hojas_impresas), ("VEND-5", 1))
        self.assertIsNotNone(j.impresa_at)
        r = jn.ref(j)
        self.assertTrue(r.hoja_texto.startswith("hoja impresa "))
        # Ana quiere imprimir la misma: se ve EN PROCESO (Fanny) y su hoja se anota en la misma jornada
        self.assertIs(jn.abiertas_por_alcance(self.s)[self.escuela.id], j)
        j2, ya_habia = jn.registrar_impresion(self.s, escuela_id=self.escuela.id, empleada_code="VEND-3", empleada_nombre="Ana")
        self.assertTrue(ya_habia)
        self.assertIs(j2, j)
        self.assertEqual(j.hojas_impresas, 2)
        self.assertTrue(jn.ref(j).hoja_texto.startswith("2 hojas impresas"))
        # y "Empezar" en pantalla cae en la misma jornada, no en otra
        with self.assertRaises(jn.JornadaEnProceso):
            jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-3")

    def test_imprimir_sin_gafete_no_abre_nada(self) -> None:
        with self.assertRaises(ValueError):
            jn.registrar_impresion(self.s, escuela_id=self.escuela.id, empleada_code="")

    def test_basicos_son_todos_los_generales_de_uniforme_menos_la_ropa_normal(self) -> None:
        # Daniel (2026-09-20): "me gustaría que aparezcan, menos lo que es ropa normal, como blusa, jeans".
        from pos_uniformes.database.models import Categoria, Marca, Producto, TipoPieza, TipoPrenda
        from pos_uniformes.services.conteo_service import obtener_variantes_basicos_agrupadas

        marca = self.s.scalar(select(Marca))
        cats = {n: Categoria(nombre=n) for n in ("Básico", "Accesorio", "Ropa casual", "Temporada")}
        tps = {n: TipoPrenda(nombre=n) for n in ("Básico", "Casual", "Interior")}
        tipos = {n: TipoPieza(nombre=n) for n in ("Pants 2pz", "Moño", "Jeans", "Blusa", "Camisa")}
        self.s.add_all([*cats.values(), *tps.values(), *tipos.values()]); self.s.flush()
        casos = [  # (nombre, categoría, tipo_prenda, tipo_pieza, stock, ¿debe salir?)
            ("Pants 2pz Liso Rojo", "Básico", "Básico", "Pants 2pz", 0, True),        # en cero y sin liga: sí (es uniforme)
            ("Moño Verde", "Accesorio", "Básico", "Moño", 0, True),                  # accesorio de uniforme: sí
            ("Jeans Brillos Adulto", "Ropa casual", "Casual", "Jeans", 5, False),     # ropa normal por categoría
            ("Blusa de Dama", "Temporada", "Básico", "Blusa", 9, False),              # temporada = ropa normal
            ("Camiseta Interior", "Básico", "Interior", "Camisa", 3, False),          # ropa normal por tipo de prenda
        ]
        for nombre, cat, tp, tipo, stock, _ in casos:
            prod = Producto(nombre=nombre, nombre_base=nombre, categoria_id=cats[cat].id, marca_id=marca.id, escuela_id=None,
                            tipo_pieza_id=tipos[tipo].id, tipo_prenda_id=tps[tp].id)
            self.s.add(prod); self.s.flush()
            self.s.add(Variante(producto_id=prod.id, sku=f"G{prod.id}", talla="8", color="", precio_venta=100, stock_actual=stock))
        self.s.commit()
        nombres = {g["producto_nombre"] for g in obtener_variantes_basicos_agrupadas(self.s)}
        for nombre, _c, _t, _p, _s, debe in casos:
            (self.assertIn if debe else self.assertNotIn)(nombre, nombres)

    def test_basicos_una_abierta_por_prenda(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Playera", empleada_code="VEND-4")
        with self.assertRaises(jn.JornadaEnProceso):
            jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Playera", empleada_code="VEND-5")
        jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pants", empleada_code="VEND-5")
        self.assertIs(jn.abiertas_por_alcance(self.s)[("basicos", "Playera")], j)

    def test_basicos_una_sola_prenda(self) -> None:
        # Daniel (2026-09-14): "a veces no quiero contar todos los pantalones, solo un tipo o un color".
        gris, azul = _seed_basicos(self.s, self.escuela, "Pantalón")
        self.s.commit()
        self.assertEqual(jn.prendas_basicas(self.s, "Pantalón"), [azul, gris])   # orden alfabético
        self.assertEqual([g["producto_nombre"] for g in jn.alcance(self.s, None, "Pantalón", gris)], [gris])
        j = jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", prenda=gris, empleada_code="VEND-4", empleada_nombre="Stayce")
        self.assertEqual((j.prenda, j.titulo, j.total_tallas), (gris, "Básicos · Pantalón Gris Escolar", 2))
        self.assertEqual(jn.ref(j).prenda, gris)
        # Otra prenda del mismo tipo sí puede abrirse a la vez; todo el tipo, no.
        jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", prenda=azul, empleada_code="VEND-5")
        with self.assertRaises(jn.JornadaEnProceso):
            jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", empleada_code="VEND-5")
        with self.assertRaises(jn.JornadaEnProceso):
            jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", prenda=gris, empleada_code="VEND-5")
        self.assertIn(("basicos", "Pantalón", gris), jn.abiertas_por_alcance(self.s))
        # La hoja y el avance ven solo esa prenda.
        hoja = jn.hoja_de_jornada(self.s, j)
        self.assertEqual([p["nombre"] for p in hoja["prendas"]], ["Pantalón Gris Escolar"])   # nombre corto
        self.assertEqual(jn.avance(self.s, j).tallas_total, 2)
        # Y al terminarla, la prenda (y el tipo) saben cuándo se contó; la otra prenda, no.
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        self.s.commit()
        u = jn.ultimos_conteos(self.s)
        self.assertEqual(jn.ultimo_conteo_de(u, None, "Pantalón", gris).texto(), "hoy (Stayce)")
        self.assertEqual(jn.ultimo_conteo_de(u, None, "Pantalón").texto(), "hoy (Stayce)")
        self.assertEqual(jn.ultimo_conteo_de(u, None, "Pantalón", azul).texto(), "nunca")

    def test_todo_el_tipo_abierto_bloquea_una_prenda(self) -> None:
        gris, _azul = _seed_basicos(self.s, self.escuela, "Pantalón")
        self.s.commit()
        jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", empleada_code="VEND-4")
        with self.assertRaises(jn.JornadaEnProceso):
            jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", prenda=gris, empleada_code="VEND-5")

    def test_basicos_sin_jornada_recuerdan_la_fecha_de_sus_tallas(self) -> None:
        from datetime import datetime, timedelta

        gris, azul = _seed_basicos(self.s, self.escuela, "Pantalón")
        v = self.s.scalar(select(Variante).where(Variante.sku.like("B%")).order_by(Variante.id))
        v.ultimo_conteo_at = datetime.now() - timedelta(days=5)
        self.s.commit()
        u = jn.ultimos_conteos(self.s)
        contada = next(n for n in (gris, azul) if n.startswith(v.producto.nombre_base))
        self.assertEqual(jn.ultimo_conteo_de(u, None, "Pantalón", contada).texto(), "hace 5 días")
        self.assertEqual(jn.ultimo_conteo_de(u, None, "Pantalón").texto(), "hace 5 días")

    def test_terminar_no_toca_el_inventario(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        v = self._variantes()
        registrar_conteos_lote(self.s, [ConteoInput(v[0].id, 3)], "x", jornada_id=j.id)
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        self.s.commit()
        self.assertIsNotNone(j.terminada_at)
        self.assertNotIn(j, jn.jornadas_abiertas(self.s))
        self.assertIn(j, jn.jornadas_por_revisar(self.s))
        self.assertEqual(self.s.get(Variante, v[0].id).stock_actual, 10)  # intacto

    def test_la_revision_lista_las_diferencias(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4", empleada_nombre="Stayce")
        v = self._variantes()
        registrar_conteos_lote(
            self.s, [ConteoInput(v[0].id, 7), ConteoInput(v[1].id, 10), ConteoInput(v[2].id, 12)],
            "x", jornada_id=j.id,
        )
        r = jn.resumen_para_revisar(self.s, j)
        self.assertEqual(r.quien, "Stayce")
        self.assertEqual(len(r.lineas), 3)
        self.assertEqual(len(r.con_diferencia), 2)
        self.assertEqual(r.piezas_de_menos, 3)
        self.assertEqual(r.piezas_de_mas, 2)

    def test_solo_el_dueno_aplica_y_entonces_si_cambia_el_stock(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        v = self._variantes()
        registrar_conteos_lote(
            self.s, [ConteoInput(v[0].id, 7), ConteoInput(v[1].id, 10)], "x", jornada_id=j.id
        )
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        with self.assertRaises(PermissionError):
            jn.aplicar_jornada(self.s, j, revisada_por="VEND-4")

        ajustados, omitidos = jn.aplicar_jornada(self.s, j, revisada_por="VEND-1")
        self.s.commit()
        self.assertEqual((ajustados, omitidos), (1, 0))   # solo la que difería
        self.assertEqual(self.s.get(Variante, v[0].id).stock_actual, 7)
        self.assertEqual(self.s.get(Variante, v[1].id).stock_actual, 10)
        self.assertEqual(j.revisada_por, "VEND-1")
        self.assertNotIn(j, jn.jornadas_por_revisar(self.s))
        self.assertTrue(all(c.ajustado for c in self.s.scalars(select(ConteoInventario)).all() if c.diferencia))

    def test_descartar_la_saca_de_la_cola_sin_tocar_nada(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        v = self._variantes()
        registrar_conteos_lote(self.s, [ConteoInput(v[0].id, 0)], "x", jornada_id=j.id)
        jn.descartar_jornada(self.s, j, revisada_por="VEND-1")
        self.s.commit()
        self.assertEqual(self.s.get(Variante, v[0].id).stock_actual, 10)
        self.assertNotIn(j, jn.jornadas_por_revisar(self.s))
        self.assertNotIn(j, jn.jornadas_abiertas(self.s))

    def test_cuando_habla_como_persona(self) -> None:
        from datetime import datetime, timedelta

        ahora = datetime.now()
        self.assertTrue(jn.cuando(ahora).startswith("hoy "))
        self.assertTrue(jn.cuando(ahora - timedelta(days=1)).startswith("ayer "))
        self.assertEqual(jn.cuando(None), "")


if __name__ == "__main__":
    unittest.main()


class HistorialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.escuela = _seed(self.s, "Uno")
        self.s.commit()

    def tearDown(self) -> None:
        self.s.close()

    def test_recientes_solo_terminadas_y_con_su_estado(self) -> None:
        # Una abierta a la vez por escuela: se abren y terminan en secuencia.
        aplicada = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        jn.terminar_jornada(self.s, aplicada, empleada_code="VEND-1")
        descartada = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-5")
        jn.terminar_jornada(self.s, descartada, empleada_code="VEND-1")
        por_revisar = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-2")
        jn.terminar_jornada(self.s, por_revisar, empleada_code="VEND-1")
        abierta = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        jn.aplicar_jornada(self.s, aplicada, revisada_por="VEND-1")
        jn.descartar_jornada(self.s, descartada, revisada_por="VEND-1")
        self.s.commit()

        recientes = jn.jornadas_recientes(self.s)
        self.assertNotIn(abierta, recientes)
        self.assertEqual(len(recientes), 3)
        estados = {jn.ref(j).empleada_code + str(j.id): jn.ref(j).estado for j in recientes}
        self.assertEqual(jn.ref(aplicada).estado, "Aplicada")
        self.assertEqual(jn.ref(descartada).estado, "Descartada")
        self.assertEqual(jn.ref(por_revisar).estado, "Por revisar")
        self.assertEqual(jn.ref(abierta).estado, "A medias")

    def test_el_limite_se_respeta(self) -> None:
        for _ in range(4):
            j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
            jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        self.s.commit()
        self.assertEqual(len(jn.jornadas_recientes(self.s, limite=2)), 2)


class HojaEnElCelularTests(unittest.TestCase):
    """guardar_tallas: se llena como una hoja, se puede corregir, no duplica."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.escuela = _seed(self.s, "Uno")   # 2 prendas × 2 tallas, stock 10
        self.s.commit()
        self.j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4", empleada_nombre="Stayce")
        self.v = list(self.s.scalars(select(Variante).order_by(Variante.id)).all())

    def tearDown(self) -> None:
        self.s.close()

    def _renglones(self):
        return list(self.s.scalars(select(ConteoInventario).where(ConteoInventario.jornada_id == self.j.id)).all())

    def test_guarda_solo_lo_que_trae_numero(self) -> None:
        n = jn.guardar_tallas(self.s, self.j, [
            {"variante_id": self.v[0].id, "fisico": 7, "pedido": 3},
            {"variante_id": self.v[1].id, "fisico": None},
        ], contado_por="Stayce (VEND-4)")
        self.assertEqual((n.guardadas, n.conflictos), (1, []))
        r = self._renglones()
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0].stock_fisico, r[0].diferencia, r[0].notas), (7, -3, "Pedido: 3"))

    def test_corregir_actualiza_en_vez_de_duplicar(self) -> None:
        jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": 7}], contado_por="x")
        jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": 9, "pedido": 1}], contado_por="x")
        r = self._renglones()
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0].stock_fisico, r[0].diferencia, r[0].notas), (9, -1, "Pedido: 1"))
        # Y la revisión de Daniel ve UNA sola línea, con el último número.
        self.assertEqual(len(jn.resumen_para_revisar(self.s, self.j).lineas), 1)

    def test_borrar_el_numero_deshace_la_talla(self) -> None:
        jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": 7}], contado_por="x")
        jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": ""}], contado_por="x")
        self.assertEqual(self._renglones(), [])

    def test_lo_de_otra_no_se_pisa_sin_preguntar(self) -> None:
        # Dos capturando la misma prenda: la segunda no pisa a la primera.
        jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": 5}], contado_por="Ana López (VEND-3)")
        res = jn.guardar_tallas(self.s, self.j, [
            {"variante_id": self.v[0].id, "fisico": 7},
            {"variante_id": self.v[1].id, "fisico": 2},
        ], contado_por="Fanny Ortiz (VEND-5)")
        self.assertEqual(res.guardadas, 1)
        self.assertEqual(len(res.conflictos), 1)
        c = res.conflictos[0]
        self.assertEqual((c.variante_id, c.talla, c.fisico_suyo, c.fisico_tuyo), (self.v[0].id, "6", 5, 7))
        self.assertEqual((c.quien, c.nombre_corto), ("Ana López (VEND-3)", "Ana"))
        self.assertIn("Prenda 0", c.producto)
        self.assertTrue(c.cuando.startswith("hoy"))
        r = {x.variante_id: x for x in self._renglones()}
        self.assertEqual(r[self.v[0].id].stock_fisico, 5)   # sigue lo de Ana
        # Mismo número que Ana: no es conflicto, no hay nada que pisar.
        res = jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": 5}], contado_por="Fanny Ortiz (VEND-5)")
        self.assertEqual((res.guardadas, res.conflictos), (1, []))
        # Con permiso explícito, gana lo que llega y queda a nombre de quien reemplazó.
        res = jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": 7}], contado_por="Fanny Ortiz (VEND-5)", reemplazar_ajenas=True)
        self.assertEqual((res.guardadas, res.conflictos), (1, []))
        r = {x.variante_id: x for x in self._renglones()}
        self.assertEqual((r[self.v[0].id].stock_fisico, r[self.v[0].id].contado_por), (7, "Fanny Ortiz (VEND-5)"))

    def test_borrar_lo_de_otra_tambien_pregunta(self) -> None:
        jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": 5}], contado_por="Ana López (VEND-3)")
        res = jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": None}], contado_por="Fanny Ortiz (VEND-5)")
        self.assertEqual(len(res.conflictos), 1)
        self.assertIsNone(res.conflictos[0].fisico_tuyo)
        self.assertEqual(len(self._renglones()), 1)

    def test_la_hoja_dice_quien_capturo_cada_talla(self) -> None:
        jn.guardar_tallas(self.s, self.j, [{"variante_id": self.v[0].id, "fisico": 5}], contado_por="Ana López (VEND-3)")
        hoja = jn.hoja_de_jornada(self.s, self.j)
        tallas = hoja["prendas"][0]["tallas"]
        self.assertEqual(tallas[0]["quien"], "Ana")
        self.assertEqual(tallas[1]["quien"], "")

    def test_la_hoja_trae_lo_capturado_y_el_avance(self) -> None:
        jn.guardar_tallas(self.s, self.j, [
            {"variante_id": self.v[0].id, "fisico": 7, "pedido": 2},
            {"variante_id": self.v[1].id, "fisico": 10},
        ], contado_por="x")
        self.s.commit()
        hoja = jn.hoja_de_jornada(self.s, self.j)
        self.assertEqual(hoja["jornada"]["titulo"], "Uno")
        self.assertEqual(hoja["avance"], {"tallas_hechas": 2, "tallas_total": 4, "prendas_hechas": 1, "prendas_total": 2})
        p0, p1 = hoja["prendas"]
        self.assertEqual((p0["numero"], p0["total"]), (1, 2))
        self.assertTrue(p0["completa"])
        self.assertEqual(p0["tallas"][0]["fisico"], 7)
        self.assertEqual(p0["tallas"][0]["pedido"], 2)
        self.assertIsNone(p1["tallas"][0]["fisico"])
        self.assertFalse(p1["completa"])
        # Nunca viaja el stock del sistema al celular.
        self.assertNotIn("stock", str(hoja).lower().replace("stock_fisico", ""))


class UltimoConteoTests(unittest.TestCase):
    """Cuándo se contó cada escuela, para no contar la misma a cada rato."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.a = _seed(self.s, "A")
        self.b = _seed(self.s, "B")
        self.c = _seed(self.s, "C")
        self.s.commit()

    def tearDown(self) -> None:
        self.s.close()

    def test_reciente_es_menos_de_catorce_dias(self) -> None:
        from datetime import datetime, timedelta

        hoy = date(2026, 9, 13)
        nunca = jn.UltimoConteo(None)
        self.assertIsNone(nunca.dias(hoy))
        self.assertFalse(nunca.reciente(hoy))
        hace_5 = jn.UltimoConteo(datetime(2026, 9, 8, 10, 0))
        self.assertEqual(hace_5.dias(hoy), 5)
        self.assertTrue(hace_5.reciente(hoy))
        hace_14 = jn.UltimoConteo(datetime.combine(hoy - timedelta(days=14), datetime.min.time()))
        self.assertFalse(hace_14.reciente(hoy))
        self.assertTrue(hace_14.reciente(hoy, dias=30))

    def test_texto_habla_como_persona(self) -> None:
        from datetime import datetime, timedelta

        hoy = date(2026, 9, 13)
        u = lambda d, q="": jn.UltimoConteo(datetime(2026, 9, 13) - timedelta(days=d), q)
        self.assertEqual(jn.UltimoConteo(None).texto(hoy), "nunca")
        self.assertEqual(u(0).texto(hoy), "hoy")
        self.assertEqual(u(1, "Stayce Chavarria").texto(hoy), "ayer (Stayce)")
        self.assertEqual(u(3).texto(hoy), "hace 3 días")
        self.assertEqual(u(45).texto(hoy), "hace 1 mes")
        self.assertEqual(u(75, "Fanny Ortiz").texto(hoy), "hace 2 meses (Fanny)")
        self.assertEqual(u(400).texto(hoy), "hace más de 1 año")

    def test_manda_la_ultima_jornada_terminada_con_quien(self) -> None:
        j1 = jn.abrir_jornada(self.s, escuela_id=self.a.id, empleada_code="VEND-4", empleada_nombre="Stayce Chavarria")
        jn.terminar_jornada(self.s, j1, empleada_code="VEND-4")
        j2 = jn.abrir_jornada(self.s, escuela_id=self.a.id, empleada_code="VEND-5", empleada_nombre="Fanny Ortiz")
        jn.terminar_jornada(self.s, j2, empleada_code="VEND-5")
        abierta = jn.abrir_jornada(self.s, escuela_id=self.b.id, empleada_code="VEND-4")   # sin terminar: no cuenta
        self.s.commit()
        u = jn.ultimos_conteos(self.s)
        self.assertEqual(jn.ultimo_conteo_de(u, self.a.id).quien, "Fanny Ortiz")   # la más reciente
        self.assertIsNone(jn.ultimo_conteo_de(u, self.b.id).fecha)
        self.assertEqual(jn.ultimo_conteo_de(u, self.c.id).texto(), "nunca")

    def test_sin_jornada_se_cae_a_la_fecha_de_las_tallas(self) -> None:
        """Los conteos de antes de las jornadas también cuentan (sin quién)."""
        from datetime import datetime, timedelta

        v = self.s.scalars(select(Variante).join(Variante.producto).where(Variante.producto.has(escuela_id=self.b.id))).first()
        v.ultimo_conteo_at = datetime.now() - timedelta(days=10)
        self.s.commit()
        u = jn.ultimo_conteo_de(jn.ultimos_conteos(self.s), self.b.id)
        self.assertIsNotNone(u.fecha)
        self.assertEqual(u.quien, "")
        self.assertEqual(u.texto(), "hace 10 días")

    def test_basicos_por_prenda(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Camisa", empleada_code="VEND-4", empleada_nombre="Stayce")
        jn.terminar_jornada(self.s, j, empleada_code="VEND-4")
        self.s.commit()
        u = jn.ultimos_conteos(self.s)
        self.assertEqual(jn.ultimo_conteo_de(u, None, "Camisa").texto(), "hoy (Stayce)")
        self.assertEqual(jn.ultimo_conteo_de(u, None, "Pantalón").texto(), "nunca")


class AvancesEnLoteTests(unittest.TestCase):
    """El avance de varias jornadas en tres consultas, no tres por cada una
    (35 jornadas por revisar eran 99 idas a la base — 2026-09-22)."""

    def test_da_lo_mismo_que_una_por_una_y_comparte_el_alcance(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import patch
        from pos_uniformes.services import conteo_jornada_service as jn

        jornadas = [SimpleNamespace(id=i, escuela_id=1 if i % 2 else 2, tipo_pieza="", prenda="", total_tallas=0) for i in (1, 2, 3)]
        grupos = {j.id: [{"producto_nombre": "P", "variantes": [SimpleNamespace(variante_id=10 + j.id)]}] for j in jornadas}
        hechas = {1: {11: 3}, 2: {}, 3: {13: 1}}
        with patch.object(jn, "alcances_en_lote", return_value=grupos) as alcances, \
             patch.object(jn, "capturado_por_jornada", return_value=hechas) as capturado:
            resultado = jn.avances_en_lote(None, jornadas)
        self.assertEqual(alcances.call_count, 1)      # un solo alcance para las tres
        self.assertEqual(capturado.call_count, 1)     # y una sola lectura de lo capturado
        self.assertEqual({i: (a.tallas_hechas, a.prendas_hechas) for i, a in resultado.items()},
                         {1: (1, 1), 2: (0, 0), 3: (1, 1)})

    def test_sin_jornadas_no_consulta_nada(self) -> None:
        from unittest.mock import patch
        from pos_uniformes.services import conteo_jornada_service as jn

        with patch.object(jn, "alcances_en_lote") as alcances:
            self.assertEqual(jn.avances_en_lote(None, []), {})
        alcances.assert_not_called()


class AlcanceCompartidoTests(unittest.TestCase):
    """El mismo refresco pide el alcance dos veces (avances y tablero); con el
    cache las tallas de cada escuela se traen una sola vez."""

    def test_la_segunda_llamada_no_vuelve_a_la_base(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import patch
        from pos_uniformes.services import conteo_jornada_service as jn

        jornadas = [SimpleNamespace(id=1, escuela_id=7, tipo_pieza="", prenda="")]
        cache: dict = {}
        with patch("pos_uniformes.services.conteo_service.obtener_variantes_para_conteo_varias", return_value={7: []}) as traer, \
             patch("pos_uniformes.services.conteo_service.agrupar_variantes_por_producto", return_value=[]):
            jn.alcances_en_lote(None, jornadas, cache=cache)
            jn.alcances_en_lote(None, jornadas, cache=cache)
        self.assertEqual(traer.call_count, 1)
        self.assertEqual(traer.call_args[0][1], [7])
        # sin cache, cada llamada vuelve a pedirlas
        with patch("pos_uniformes.services.conteo_service.obtener_variantes_para_conteo_varias", return_value={7: []}) as traer, \
             patch("pos_uniformes.services.conteo_service.agrupar_variantes_por_producto", return_value=[]):
            jn.alcances_en_lote(None, jornadas)
            jn.alcances_en_lote(None, jornadas)
        self.assertEqual(traer.call_count, 2)


class LoQueTocaTests(unittest.TestCase):
    """`lo_que_toca` mide **talla por talla**, igual que el mapa: lo que nunca
    se contó y lo que ya venció. Así, un tipo contado en dos tandas deja de
    aparecer cuando de verdad está completo, y lo que se cerró a medias sigue
    en la lista (Daniel, 2026-09-22: la Calceta se contó de un color)."""

    def _mapa(self, escuelas=(), basicos=()):
        return {"escuelas": list(escuelas), "basicos": list(basicos)}

    def _escuela(self, nombre, eid, *, tallas, al_dia, viejas=0, nunca=0, en_proceso="", en_rojo=0):
        return {"nombre": nombre, "escuela_id": eid, "tallas": tallas, "al_dia": al_dia,
                "viejas": viejas, "nunca": nunca, "en_proceso": en_proceso, "en_rojo": en_rojo}

    def _basico(self, tipo, *, tallas, al_dia, viejas=0, nunca=0, en_proceso="", en_rojo=0):
        return {"tipo_pieza": tipo, "tallas": tallas, "al_dia": al_dia,
                "viejas": viejas, "nunca": nunca, "en_proceso": en_proceso, "en_rojo": en_rojo}

    def _correr(self, mapa, ultimos=None):
        from unittest.mock import patch
        from pos_uniformes.services import conteo_jornada_service as jn

        with patch.object(jn, "ultimos_conteos", return_value=ultimos or {}):
            return jn.lo_que_toca(None, mapa=mapa)


    def test_el_semaforo_es_el_mismo_del_mapa(self) -> None:
        """Antes el kiosko pintaba de gris lo que el mapa pintaba de rojo."""
        mapa = self._mapa(
            basicos=[
                self._basico("Calceta", tallas=42, al_dia=42, en_rojo=5),
                self._basico("Jumper", tallas=20, al_dia=2, nunca=18),
            ],
        )
        por_titulo = {f.titulo: f.salud for f in self._correr(mapa)}
        self.assertEqual(por_titulo["Básicos · Calceta"], "rojo", "se vendió sin contar")
        self.assertEqual(por_titulo["Básicos · Jumper"], "ambar", "solo le falta contarse")

    def test_lo_que_esta_en_rojo_va_primero_aunque_se_haya_contado_ayer(self) -> None:
        """El sistema cree que hay menos que nada: alguien vendió sin contar."""
        mapa = self._mapa(
            basicos=[
                self._basico("Calceta", tallas=42, al_dia=42, en_rojo=5),
                self._basico("Jumper", tallas=20, al_dia=2, nunca=18),
            ],
        )
        filas = self._correr(mapa)
        self.assertEqual(filas[0].titulo, "Básicos · Calceta", "lo rojo le gana a la vigencia")
        self.assertEqual(filas[0].motivo, "5 tallas en rojo · se vendió sin contar")

    def test_una_sola_talla_en_rojo_se_dice_en_singular(self) -> None:
        mapa = self._mapa(basicos=[self._basico("Bata", tallas=37, al_dia=37, en_rojo=1)])
        filas = self._correr(mapa)
        self.assertEqual(filas[0].motivo, "una talla en rojo · se vendió sin contar")

    def test_entre_dos_rojos_va_primero_el_mas_rojo(self) -> None:
        mapa = self._mapa(
            basicos=[
                self._basico("Corbatín", tallas=9, al_dia=9, en_rojo=2),
                self._basico("Calceta", tallas=42, al_dia=42, en_rojo=5),
            ],
        )
        self.assertEqual(
            [f.titulo for f in self._correr(mapa)],
            ["Básicos · Calceta", "Básicos · Corbatín"],
        )

    def test_lo_rojo_que_alguien_esta_contando_no_se_vuelve_a_ofrecer(self) -> None:
        mapa = self._mapa(
            basicos=[self._basico("Calceta", tallas=42, al_dia=42, en_rojo=5, en_proceso="Fanny")],
        )
        self.assertEqual(self._correr(mapa), [], "ya la están contando")

    def test_lo_completo_no_aparece_y_lo_incompleto_si(self) -> None:
        mapa = self._mapa(
            basicos=[self._basico("Bata", tallas=37, al_dia=37),
                     self._basico("Calceta", tallas=42, al_dia=6, nunca=36)],
        )
        filas = self._correr(mapa)
        self.assertEqual([f.titulo for f in filas], ["Básicos · Calceta"])
        fila = filas[0]
        self.assertEqual((fila.faltan, fila.empezado, fila.motivo), (36, True, "faltan 36 de 42 tallas"))

    def test_primero_lo_empezado_de_lo_que_menos_falta_luego_vencido_y_al_final_nunca(self) -> None:
        from datetime import datetime, timedelta, timezone
        from pos_uniformes.services import conteo_jornada_service as jn

        hace = lambda d: jn.UltimoConteo(fecha=datetime.now(timezone.utc) - timedelta(days=d), quien="Stayce")  # noqa: E731
        mapa = self._mapa(
            escuelas=[
                self._escuela("Nunca contada", 1, tallas=10, al_dia=0, nunca=10),
                self._escuela("Vencida vieja", 2, tallas=10, al_dia=0, viejas=10),
                self._escuela("Vencida nueva", 3, tallas=10, al_dia=0, viejas=10),
                self._escuela("Empezada grande", 4, tallas=100, al_dia=50, nunca=50),
                self._escuela("Empezada chica", 5, tallas=10, al_dia=8, nunca=2),
            ],
        )
        ultimos = {2: hace(120), 3: hace(30), 4: hace(3), 5: hace(3)}
        filas = self._correr(mapa, ultimos)
        self.assertEqual(
            [f.titulo for f in filas],
            ["Empezada chica", "Empezada grande", "Vencida vieja", "Vencida nueva", "Nunca contada"],
        )

    def test_lo_que_alguien_esta_contando_no_entra(self) -> None:
        mapa = self._mapa(basicos=[self._basico("Calceta", tallas=42, al_dia=6, nunca=36, en_proceso="Fanny")])
        self.assertEqual(self._correr(mapa), [])

    def test_limite(self) -> None:
        mapa = self._mapa(basicos=[self._basico(f"T{i}", tallas=10, al_dia=0, nunca=10) for i in range(5)])
        self.assertEqual(len(self._correr(mapa)), 5)
        from unittest.mock import patch
        from pos_uniformes.services import conteo_jornada_service as jn
        with patch.object(jn, "ultimos_conteos", return_value={}):
            self.assertEqual(len(jn.lo_que_toca(None, mapa=mapa, limite=2)), 2)
