"""El bot también sabe de la tienda, no solo de dinero.

Daniel usa el bot todos los días pero tenía que abrir el POS para la pregunta
más común: "¿cuánto cuesta y cuántas hay?" (2026-09-25). Estas respuestas no
calculan nada: le preguntan a los mismos servicios que el kiosko y el panel.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria, DemandaNoAtendida, Escuela, Marca, NivelEducativo, Producto,
    TipoPieza, TipoPrenda, Variante,
)
from pos_uniformes.services import telegram_inventario_service as inv


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="G")
        self.prenda_t = TipoPrenda(nombre="Deportivo")
        self.nivel = NivelEducativo(nombre="Primaria")
        self.esc = Escuela(nombre="Justo Sierra")
        self.s.add_all([self.cat, self.marca, self.prenda_t, self.nivel, self.esc])
        self.piezas = {n: TipoPieza(nombre=n) for n in ("Playera", "Pants 2pz")}
        self.s.add_all(list(self.piezas.values()))
        self.s.flush()

    def _prod(self, nombre, pieza="Playera", *, escuela=True, tallas=None):
        p = Producto(
            nombre=nombre, nombre_base=nombre, categoria_id=self.cat.id, marca_id=self.marca.id,
            escuela_id=self.esc.id if escuela else None, nivel_educativo_id=self.nivel.id,
            tipo_prenda_id=self.prenda_t.id, tipo_pieza_id=self.piezas[pieza].id,
        )
        self.s.add(p)
        self.s.flush()
        for (talla, color), stock in (tallas or {("10", "Rojo"): 3}).items():
            self.s.add(Variante(producto_id=p.id, sku=f"{p.id}-{talla}-{color}", talla=talla,
                                color=color, precio_venta=100, stock_actual=stock))
        self.s.flush()
        return p


class PrendaTest(_Base):
    def test_dice_precio_existencia_y_total(self):
        self._prod("Playera Justo Sierra", tallas={("10", "Rojo"): 3, ("12", "Rojo"): 0})
        r = inv.prenda(self.s, "playera justo")
        self.assertIn("Playera Justo Sierra", r)
        self.assertIn("$100.00", r)
        self.assertIn("10: 3", r)
        self.assertIn("12: —", r)       # cero se ve como raya, no como 0
        self.assertIn("En total: 3 piezas", r)

    def test_marca_lo_que_esta_en_rojo(self):
        self._prod("Playera Justo Sierra", tallas={("10", "Rojo"): -2})
        self.assertIn("⚠️", inv.prenda(self.s, "playera"))

    def test_las_tallas_van_en_su_orden_no_en_el_alfabetico(self):
        self._prod("Playera JS", tallas={("CH", "R"): 1, ("EXG", "R"): 1, ("GD", "R"): 1, ("MD", "R"): 1})
        r = inv.prenda(self.s, "Playera JS")
        self.assertLess(r.index("MD:"), r.index("GD:"))
        self.assertLess(r.index("GD:"), r.index("EXG:"))

    def test_con_varios_colores_los_agrupa(self):
        self._prod("Licra", tallas={("CH", "Azul"): 1, ("CH", "Negro"): 2})
        r = inv.prenda(self.s, "Licra")
        self.assertIn("— Azul —", r)
        self.assertIn("— Negro —", r)

    def test_con_varias_que_empatan_las_enseña_y_no_elige(self):
        self._prod("Playera Roja")
        self._prod("Playera Azul")
        r = inv.prenda(self.s, "playera")
        self.assertIn("empata con 2", r)
        self.assertNotIn("En total", r)

    def test_encuentra_aunque_las_palabras_esten_sueltas(self):
        # "justo playera" no es el nombre, pero se entiende.
        self._prod("Playera Deportiva Justo Sierra")
        self.assertIn("En total", inv.prenda(self.s, "justo playera"))

    def test_sin_argumento_explica_como_se_usa(self):
        self.assertIn("/prenda", inv.prenda(self.s, ""))

    def test_lo_que_no_existe_lo_dice(self):
        self.assertIn("No encontré", inv.prenda(self.s, "zapatos"))


class EscuelaTest(_Base):
    def test_trae_el_titular_y_las_cifras(self):
        self._prod("Playera Justo Sierra", tallas={("10", "Rojo"): 4})
        r = inv.escuela(self.s, "justo")
        self.assertIn("Justo Sierra", r)
        self.assertIn("nunca se ha contado", r)
        self.assertIn("En tienda: 4 piezas", r)

    def test_con_varias_que_empatan_no_elige(self):
        self.s.add(Escuela(nombre="Justo Sierra Secundaria"))
        self.s.flush()
        self.assertIn("empata con 2", inv.escuela(self.s, "justo"))

    def test_sin_argumento_explica_como_se_usa(self):
        self.assertIn("/escuela", inv.escuela(self.s, ""))


class FaltasTest(_Base):
    def _falta(self, producto, talla, *, veces=1, hace_dias=1):
        from pos_uniformes.services.demanda_service import TALLA_AGOTADA

        for _ in range(veces):
            self.s.add(DemandaNoAtendida(
                tipo=TALLA_AGOTADA, sku="X", producto=producto, talla=talla, piezas=1,
                created_at=datetime.now(timezone.utc) - timedelta(days=hace_dias),
            ))
        self.s.flush()

    def test_agrupa_y_marca_lo_repetido(self):
        self._falta("Playera JS", "10", veces=4)
        self._falta("Pants JS", "12", veces=1)
        r = inv.faltas(self.s)
        self.assertIn("Playera JS · 10 — 4 veces 🔴", r)
        self.assertIn("una vez", r)

    def test_lo_viejo_no_entra(self):
        self._falta("Playera JS", "10", hace_dias=30)
        self.assertIn("Nadie pidió", inv.faltas(self.s, dias=7))


class ContarTest(_Base):
    def test_sin_nada_pendiente_lo_dice(self):
        from unittest.mock import patch

        from pos_uniformes.services import conteo_jornada_service as jn

        with patch.object(jn, "lo_que_toca", return_value=[]):
            self.assertIn("No hay nada pendiente", inv.contar(self.s))

    def test_pinta_el_semaforo_de_cada_renglon(self):
        from unittest.mock import patch

        from pos_uniformes.services import conteo_jornada_service as jn

        class _Fila:
            titulo, motivo, salud = "Básicos · Calceta", "5 tallas en rojo", "rojo"

        with patch.object(jn, "lo_que_toca", return_value=[_Fila()]):
            r = inv.contar(self.s)
        self.assertIn("🔴 Básicos · Calceta", r)
        self.assertIn("5 tallas en rojo", r)


class ElBotLosConoceTest(unittest.TestCase):
    def test_estan_en_la_ayuda_y_en_el_despachador(self):
        from pos_uniformes.services.telegram_bot_service import AYUDA
        from pathlib import Path

        for c in ("/prenda", "/escuela", "/contar", "/faltas"):
            self.assertIn(c, AYUDA, f"{c} no sale en /ayuda")
        fuente = (
            Path(__file__).resolve().parent.parent / "services" / "telegram_bot_service.py"
        ).read_text(encoding="utf-8")
        self.assertIn('cmd.nombre in ("prenda", "precio")', fuente)   # los dos nombres valen
        for c in ("contar", "escuela", "faltas"):
            self.assertIn(f'cmd.nombre == "{c}"', fuente)


if __name__ == "__main__":
    unittest.main()
