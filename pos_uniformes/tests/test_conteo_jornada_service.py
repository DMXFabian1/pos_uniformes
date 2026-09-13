"""Jornadas de conteo: abrir, retomar, avance, terminar, revisar y aplicar."""

from __future__ import annotations

import unittest
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

    def test_basicos_una_abierta_por_prenda(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Playera", empleada_code="VEND-4")
        with self.assertRaises(jn.JornadaEnProceso):
            jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Playera", empleada_code="VEND-5")
        jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pants", empleada_code="VEND-5")
        self.assertIs(jn.abiertas_por_alcance(self.s)[("basicos", "Playera")], j)

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
