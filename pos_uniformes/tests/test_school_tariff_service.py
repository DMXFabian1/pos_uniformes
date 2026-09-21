"""Tarifarios por escuela: la lista de escuelas sale en UNA consulta."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Categoria, Escuela, Marca, NivelEducativo, Producto
from pos_uniformes.services.school_tariff_service import list_schools_for_tariff


class ListSchoolsForTariffTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.consultas = 0
        event.listen(engine, "before_cursor_execute", lambda *a, **k: setattr(self, "consultas", self.consultas + 1))
        cat = Categoria(nombre="Uniformes"); marca = Marca(nombre="Genérica")
        self.prim = NivelEducativo(nombre="Primaria"); self.sec = NivelEducativo(nombre="Secundaria")
        self.s.add_all([cat, marca, self.prim, self.sec]); self.s.flush()
        self.cat, self.marca = cat, marca

    def _escuela(self, nombre: str, niveles: list, *, activa: bool = True, productos: bool = True) -> Escuela:
        e = Escuela(nombre=nombre, activo=activa); self.s.add(e); self.s.flush()
        if productos:
            for n in niveles or [None]:
                self.s.add(Producto(nombre=f"Playera {nombre} {n.nombre if n else ''}", nombre_base="Playera",
                                    categoria_id=self.cat.id, marca_id=self.marca.id, escuela_id=e.id,
                                    nivel_educativo_id=n.id if n else None))
        self.s.flush()
        return e

    def test_una_entrada_por_nivel_y_una_sola_consulta_para_todas(self) -> None:
        self._escuela("Benito Juárez", [self.prim])
        self._escuela("Práxedis", [self.prim, self.sec])
        self._escuela("Sin nivel", [])
        self._escuela("Sin productos", [], productos=False)
        self._escuela("Inactiva", [self.prim], activa=False)
        self.consultas = 0
        filas = list_schools_for_tariff(self.s)
        self.assertEqual(self.consultas, 2)   # escuelas + niveles de todas; antes 1 + 1–2 por escuela
        self.assertEqual(
            [(f["display_name"], f["nivel_nombre"]) for f in filas],
            [("Benito Juárez", "Primaria"), ("Práxedis — Primaria", "Primaria"), ("Práxedis — Secundaria", "Secundaria"), ("Sin nivel", None)],
        )

    def test_producto_inactivo_no_cuenta(self) -> None:
        e = self._escuela("Solo inactivos", [self.prim])
        for p in self.s.query(Producto).filter_by(escuela_id=e.id):
            p.activo = False
        self.s.flush()
        self.assertEqual(list_schools_for_tariff(self.s), [])


class TarifarioDesdeElUniformeTests(unittest.TestCase):
    """Catálogo fase 2: con uniforme armado, el tarifario es el uniforme
    (piezas, orden, grupo como sección, opcional, color de la pieza);
    sin uniforme, directos + ligados como siempre."""

    def setUp(self) -> None:
        from pos_uniformes.database.models import CatalogSchoolProductLink, TipoPieza, TipoPrenda, Variante

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        cat = Categoria(nombre="Uniformes"); marca = Marca(nombre="Genérica")
        self.s.add_all([cat, marca]); self.s.flush()
        tp = {n: TipoPrenda(nombre=n) for n in ("Oficial", "Deportivo", "Básico")}
        tz = {n: TipoPieza(nombre=n) for n in ("Camisa", "Pants 2pz", "Pants Suelto", "Suéter", "Chaleco")}
        self.s.add_all([*tp.values(), *tz.values()]); self.s.flush()
        self.js = Escuela(nombre="Justo Sierra"); self.s.add(self.js); self.s.flush()

        def prod(nombre, prenda, pieza, escuela=None, color="", precio=100):
            p = Producto(nombre=nombre, nombre_base=nombre, categoria_id=cat.id, marca_id=marca.id,
                         escuela_id=escuela.id if escuela else None, tipo_prenda_id=tp[prenda].id, tipo_pieza_id=tz[pieza].id)
            self.s.add(p); self.s.flush()
            for t in ("8", "10"):
                self.s.add(Variante(producto_id=p.id, sku=f"S{p.id}-{t}", talla=t, color=color, precio_venta=precio, stock_actual=1))
            return p

        self.camisa = prod("Camisa Justo Sierra", "Oficial", "Camisa", self.js, color="", precio=150)
        self.pants2 = prod("Pants 2pz Deportivo Justo Sierra", "Deportivo", "Pants 2pz", self.js, color="Rojo", precio=400)
        self.sueter_m = prod("Suéter Botones M Rojo Justo Sierra", "Oficial", "Suéter", self.js, color="Rojo", precio=250)
        self.sueter_h = prod("Suéter Cuello V H Rojo Justo Sierra", "Oficial", "Suéter", self.js, color="Rojo", precio=250)
        self.chaleco = prod("Chaleco Rojo Justo Sierra", "Oficial", "Chaleco", self.js, color="Rojo", precio=200)
        self.pants_rojo = prod("Pants Suelto Liso Rojo", "Básico", "Pants Suelto", color="Rojo", precio=180)
        self.s.add(CatalogSchoolProductLink(escuela_id=self.js.id, producto_id=self.pants_rojo.id))
        self.s.commit()

    def _tarifario(self):
        from pos_uniformes.services.school_tariff_service import build_school_tariff
        return build_school_tariff(self.s, self.js.id)["productos"]

    def test_sin_uniforme_directos_mas_ligados_por_tipo_de_prenda(self) -> None:
        filas = self._tarifario()
        self.assertEqual([f["nombre"] for f in filas], ["Pants 2pz Deportivo", "Suéter (Botones M / Cuello V H) Rojo", "Camisa", "Chaleco Rojo", "Pants Suelto Liso Rojo"])
        self.assertEqual([f["tipo_prenda"] for f in filas], ["Deportivo", "Oficial", "Oficial", "Oficial", "Básico"])
        self.assertNotIn("seccion", filas[0])

    def test_con_uniforme_manda_el_uniforme(self) -> None:
        from pos_uniformes.services import uniforme_service as us
        uni = us.armar(self.s, self.js.id)
        piezas = {p["nombre"]: p["pieza_id"] for p in us.piezas_de(self.s, uni.id)}
        us.actualizar_pieza(self.s, piezas["Camisa Justo Sierra"], color="Blanca")           # Daniel dice el color
        us.actualizar_pieza(self.s, piezas["Chaleco Rojo Justo Sierra"], obligatoria=False)  # el chaleco es opcional
        us.quitar_pieza(self.s, piezas["Suéter Cuello V H Rojo Justo Sierra"])               # ya no se vende
        us.mover_pieza(self.s, piezas["Chaleco Rojo Justo Sierra"], -10)                     # y lo pone hasta arriba de su grupo
        self.s.commit()

        filas = self._tarifario()
        # Deportivo primero (pants propio y el general del estante), luego Diario en el orden de Daniel
        self.assertEqual(
            [(f["nombre"], f["seccion"]) for f in filas],
            [("Pants 2pz Deportivo", "Deportivo"), ("Pants Suelto Liso Rojo", "Deportivo"),
             ("Chaleco Rojo", "Diario"), ("Suéter Botones M Rojo", "Diario"), ("Camisa", "Diario")],
        )
        por_nombre = {f["nombre"]: f for f in filas}
        self.assertEqual(por_nombre["Camisa"]["colores"], ["Blanca"])       # la pieza manda sobre las tallas sin color
        self.assertTrue(por_nombre["Chaleco Rojo"]["opcional"])
        self.assertFalse(por_nombre["Camisa"]["opcional"])
        # Sin uniforme los dos suéteres se fundían; con uno quitado ya no hay con qué

    def test_opcional_se_dice_en_texto_y_en_html(self) -> None:
        from pos_uniformes.services import uniforme_service as us
        from pos_uniformes.services.school_tariff_preview_service import build_school_tariff_html
        from pos_uniformes.services.school_tariff_text_service import build_school_tariff_text
        uni = us.armar(self.s, self.js.id)
        piezas = {p["nombre"]: p["pieza_id"] for p in us.piezas_de(self.s, uni.id)}
        us.actualizar_pieza(self.s, piezas["Chaleco Rojo Justo Sierra"], obligatoria=False); self.s.commit()
        from pos_uniformes.services.school_tariff_service import build_school_tariff
        data = build_school_tariff(self.s, self.js.id)
        texto = build_school_tariff_text(tariff=data)
        self.assertIn("Chaleco Rojo (opcional)", texto)
        self.assertIn("DIARIO", texto); self.assertIn("DEPORTIVO", texto)
        html = build_school_tariff_html(tariff=data)
        self.assertIn("Rojo · opcional", html); self.assertIn("DIARIO", html)
