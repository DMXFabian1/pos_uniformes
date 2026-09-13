"""Jornadas de conteo: abrir, retomar, avance, terminar, revisar y aplicar."""

from __future__ import annotations

import unittest

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

    def test_solo_quien_la_abrio_o_el_dueno_pueden_seguirla(self) -> None:
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        self.assertTrue(jn.puede_seguirla(j, "VEND-4"))
        self.assertTrue(jn.puede_seguirla(j, "VEND-1"))
        self.assertFalse(jn.puede_seguirla(j, "VEND-5"))
        with self.assertRaises(jn.JornadaAjena):
            jn.terminar_jornada(self.s, j, empleada_code="VEND-5")

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
        abierta = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        aplicada = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4")
        descartada = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-5")
        por_revisar = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-2")
        for j in (aplicada, descartada, por_revisar):
            jn.terminar_jornada(self.s, j, empleada_code="VEND-1")
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
        self.assertEqual(n, 1)
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
