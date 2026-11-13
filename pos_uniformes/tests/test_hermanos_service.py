"""El modelo de una prenda nueva y «Ya tiene / Le falta» (tanda 2 del alta, 2026-11-13)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from sqlalchemy import create_engine, event

from pos_uniformes.services import hermanos_service as hs
from tests._ayuda_mini_caja import ESCALERAS, MiniCaja


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.caja = MiniCaja(self.engine)
        self.s = self.caja.s
        self.jaral = self.caja.escuelas["Ignacio Allende (Jaral)"]


class BuscarModeloTests(_Base):
    def test_el_modelo_es_el_juego_que_mas_se_repite(self) -> None:
        h = hs.buscar_modelo(self.s, "Pants Suelto", "Primaria", escuela_id=self.jaral.id)
        self.assertIsNotNone(h.modelo)
        m = h.modelo
        # 3 escuelas (MH, JS, IA) lo tienen igual; Benito Juárez trae EXG.
        self.assertEqual(m.iguales, 3)
        self.assertEqual(m.texto_iguales, "igual en 3 escuelas de primaria")
        self.assertEqual(m.precios, {t: Decimal(p) for t, p in ESCALERAS["Pants Suelto"].items()})
        self.assertEqual([t.talla for t in m.tallas], ["4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD"])
        self.assertEqual(m.nombre_sin_escuela, "Pants Suelto")
        self.assertEqual(m.grupo_uniforme, "Deportivo")
        self.assertEqual(h.total, 4)
        self.assertFalse(h.relajado)
        self.assertEqual(len(h.alternativas), 1)
        self.assertIn("EXG", [t.talla for t in h.alternativas[0].tallas])
        self.assertEqual(m.texto_rango, "10 tallas · $245 a $295")
        self.assertTrue(h.texto.startswith("Copiado de: Pants Suelto "))

    def test_no_cuenta_la_escuela_que_lo_recibe(self) -> None:
        ia = self.caja.escuelas["Ignacio Allende"]
        h = hs.buscar_modelo(self.s, "Pants Suelto", "Primaria", escuela_id=ia.id)
        self.assertNotEqual(h.modelo.escuela_id, ia.id)
        self.assertEqual(h.modelo.iguales, 2)

    def test_acentos_y_mayusculas_no_importan(self) -> None:
        h = hs.buscar_modelo(self.s, "pants suelto", "primaria")
        self.assertEqual(h.tipo_pieza, "Pants Suelto")
        self.assertEqual(h.nivel, "Primaria")

    def test_sin_hermanas_en_el_nivel_busca_en_otros(self) -> None:
        h = hs.buscar_modelo(self.s, "Chaleco", "Secundaria")
        self.assertTrue(h.relajado)
        self.assertEqual(h.modelo.nombre, "Chaleco Rojo Ignacio Allende")
        self.assertIn("No hay en secundaria", h.texto)

    def test_sin_ninguna_hermana(self) -> None:
        h = hs.buscar_modelo(self.s, "Boina", "Primaria")
        self.assertIsNone(h.modelo)
        self.assertIn("No hay otra Boina", h.texto)

    def test_modelo_elegido_a_mano(self) -> None:
        bj = self.caja.productos[("Benito Juárez", "Pants Suelto")]
        h = hs.buscar_modelo(self.s, "Pants Suelto", "Primaria", escuela_id=self.jaral.id, modelo_id=bj.id)
        self.assertEqual(h.modelo.producto_id, bj.id)
        self.assertEqual(h.modelo.iguales, 1)
        self.assertNotIn(bj.id, [a.producto_id for a in h.alternativas])

    def test_pocas_consultas(self) -> None:
        consultas = []
        event.listen(self.engine, "before_cursor_execute", lambda *a, **k: consultas.append(1))
        hs.buscar_modelo(self.s, "Pants Suelto", "Primaria", escuela_id=self.jaral.id)
        self.assertLessEqual(len(consultas), 4)


class CompararEscuelaTests(_Base):
    def test_ya_tiene_y_le_falta(self) -> None:
        c = hs.comparar_escuela(self.s, self.jaral.id)
        self.assertEqual(c.nivel, "Primaria")
        self.assertEqual(c.escuelas_del_nivel, 4)
        faltan = {p.tipo_pieza: p for p in c.le_falta}
        self.assertEqual(list(faltan), ["Pants Suelto", "Chaleco", "Suéter"])
        self.assertEqual(faltan["Pants Suelto"].texto, "lo tienen 4 de 4")
        self.assertEqual(faltan["Chaleco"].texto, "lo tienen 1 de 4")
        tiene = {p.tipo_pieza: p for p in c.ya_tiene}
        self.assertEqual(tiene["Pants 3pz"].escuelas_con_ella, 3)
        self.assertEqual(tiene["Playera"].productos, ("Playera Deportiva Ignacio Allende (Jaral)",))

    def test_escuela_sin_prendas_pide_el_nivel(self) -> None:
        nueva = self.caja._escuela("Escuela Nueva")
        with self.assertRaisesRegex(ValueError, "di de qué nivel"):
            hs.comparar_escuela(self.s, nueva.id)
        c = hs.comparar_escuela(self.s, nueva.id, "primaria")
        self.assertEqual(c.ya_tiene, ())
        self.assertEqual(c.le_falta[0].tipo_pieza, "Pants 2pz")
        self.assertEqual(c.le_falta[0].texto, "lo tienen 5 de 5")

    def test_escuelas_sin_la_pieza(self) -> None:
        sp = hs.escuelas_sin_pieza(self.s, "Pants Suelto", "Primaria")
        self.assertEqual([e.escuela for e in sp.escuelas], ["Ignacio Allende (Jaral)"])
        self.assertEqual(sp.texto, "le falta a 1 de primaria")
        sp = hs.escuelas_sin_pieza(self.s, "Suéter", "Primaria")
        self.assertEqual(len(sp.escuelas), 4)


if __name__ == "__main__":
    unittest.main()
