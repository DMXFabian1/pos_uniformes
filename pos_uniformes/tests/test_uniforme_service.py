"""Catálogo fase 2: el uniforme de una escuela como entidad."""

from __future__ import annotations

import io
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    CatalogSchoolProductLink,
    Categoria,
    Escuela,
    Marca,
    Producto,
    TipoPieza,
    TipoPrenda,
    Uniforme,
    UniformePieza,
)
from pos_uniformes.scripts import armar_uniformes
from pos_uniformes.services import uniforme_service as us


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        cat = Categoria(nombre="Uniformes"); marca = Marca(nombre="Genérica")
        self.s.add_all([cat, marca]); self.s.flush()
        self.cat, self.marca = cat, marca
        self.tp = {n: TipoPrenda(nombre=n) for n in ("Oficial", "Deportivo", "Básico", "Escolta")}
        self.tz = {n: TipoPieza(nombre=n) for n in ("Camisa", "Falda", "Pants Suelto", "Pants 2pz", "Playera", "Suéter")}
        self.s.add_all([*self.tp.values(), *self.tz.values()]); self.s.flush()
        self.vg = Escuela(nombre="Vicente Guerrero"); self.js = Escuela(nombre="Justo Sierra")
        self.s.add_all([self.vg, self.js]); self.s.flush()
        # Propios de Vicente Guerrero (con escudo)
        self.camisa_vg = self._prod("Camisa Vicente Guerrero", escuela=self.vg, prenda="Oficial", pieza="Camisa")
        self.falda_vg = self._prod("Falda Vicente Guerrero", escuela=self.vg, prenda="Oficial", pieza="Falda")
        self.pants_vg = self._prod("Pants Suelto Vicente Guerrero", escuela=self.vg, prenda="Deportivo", pieza="Pants Suelto")
        self.pants2_vg = self._prod("Pants 2pz Deportivo Vicente Guerrero", escuela=self.vg, prenda="Deportivo", pieza="Pants 2pz")
        self.viejo_vg = self._prod("Playera Vieja Vicente Guerrero", escuela=self.vg, prenda="Deportivo", pieza="Playera", activo=False)
        # Generales del estante
        self.pants_rojo = self._prod("Pants Suelto Liso Rojo", prenda="Básico", pieza="Pants Suelto")
        self.olan = self._prod("Camisa Cuello Olan Blanca", prenda="Básico", pieza="Camisa")
        self.sueter = self._prod("Suéter Escolar Vino", prenda="Básico", pieza="Suéter")
        # Justo Sierra ya tenía ligado el pants rojo
        self.s.add(CatalogSchoolProductLink(escuela_id=self.js.id, producto_id=self.pants_rojo.id))
        self.s.commit()

    def _prod(self, nombre, *, escuela=None, prenda, pieza, activo=True):
        p = Producto(
            nombre=nombre, nombre_base=nombre, categoria_id=self.cat.id, marca_id=self.marca.id,
            escuela_id=escuela.id if escuela else None, tipo_prenda_id=self.tp[prenda].id,
            tipo_pieza_id=self.tz[pieza].id, activo=activo,
        )
        self.s.add(p); self.s.flush()
        return p

    def _ligas(self, escuela):
        return sorted(
            self.s.scalars(select(CatalogSchoolProductLink.producto_id).where(
                CatalogSchoolProductLink.escuela_id == escuela.id, CatalogSchoolProductLink.activo == True  # noqa: E712
            )).all()
        )


class ProponerTests(_Base):
    def test_propone_los_propios_activos_en_orden_de_tarifario_y_agrupados(self) -> None:
        filas = us.proponer(self.s, self.vg.id)
        self.assertEqual(
            [(f["nombre"], f["grupo"], f["origen"]) for f in filas],
            [
                ("Pants 2pz Deportivo Vicente Guerrero", "Deportivo", "Escuela"),
                ("Pants Suelto Vicente Guerrero", "Deportivo", "Escuela"),
                ("Camisa Vicente Guerrero", "Diario", "Escuela"),
                ("Falda Vicente Guerrero", "Diario", "Escuela"),
            ],
        )
        self.assertNotIn("Playera Vieja Vicente Guerrero", [f["nombre"] for f in filas])

    def test_los_generales_ligados_entran_como_generales(self) -> None:
        filas = us.proponer(self.s, self.js.id)
        self.assertEqual([(f["nombre"], f["origen"], f["grupo"]) for f in filas], [("Pants Suelto Liso Rojo", "General", "Deportivo")])

    def test_grupo_por_tipo_de_prenda(self) -> None:
        self.assertEqual(us.grupo_para(self.pants_vg), "Deportivo")
        self.assertEqual(us.grupo_para(self.camisa_vg), "Diario")
        self.assertEqual(us.grupo_para(self.olan), "Diario")
        self.assertEqual(us.grupo_para(self.pants_rojo), "Deportivo")  # básico del estante, pero es pants
        polo = self._prod("Playera Polo Oficial", escuela=self.vg, prenda="Oficial", pieza="Playera")
        self.assertEqual(us.grupo_para(polo), "Diario")  # oficial manda sobre la pieza
        escolta = self._prod("Guante Escolta", prenda="Escolta", pieza="Camisa")
        self.assertEqual(us.grupo_para(escolta), "Escolta")
        sin_tipo = Producto(nombre="X", nombre_base="X", categoria_id=self.cat.id, marca_id=self.marca.id)
        self.assertEqual(us.grupo_para(sin_tipo), "Otro")


class ArmarTests(_Base):
    def test_armar_crea_el_uniforme_con_la_propuesta_y_es_idempotente(self) -> None:
        uni = us.armar(self.s, self.vg.id); self.s.commit()
        self.assertEqual([p["nombre"] for p in us.piezas_de(self.s, uni.id)][:2], ["Pants 2pz Deportivo Vicente Guerrero", "Pants Suelto Vicente Guerrero"])
        # Daniel quita la falda y vuelve a correr el script: no la regresa ni duplica nada
        falda = next(p for p in us.piezas_de(self.s, uni.id) if p["nombre"] == "Falda Vicente Guerrero")
        us.quitar_pieza(self.s, falda["pieza_id"]); self.s.commit()
        uni2 = us.armar(self.s, self.vg.id); self.s.commit()
        self.assertEqual(uni2.id, uni.id)
        nombres = [p["nombre"] for p in us.piezas_de(self.s, uni.id)]
        self.assertEqual(len(nombres), 3); self.assertNotIn("Falda Vicente Guerrero", nombres)
        self.assertEqual(self.s.query(Uniforme).filter_by(escuela_id=self.vg.id).count(), 1)
        # Una prenda nueva de la escuela sí entra al volver a correr
        self._prod("Chaleco Vicente Guerrero", escuela=self.vg, prenda="Oficial", pieza="Suéter"); self.s.commit()
        us.armar(self.s, self.vg.id); self.s.commit()
        self.assertIn("Chaleco Vicente Guerrero", [p["nombre"] for p in us.piezas_de(self.s, uni.id)])

    def test_armar_sin_productos_deja_uniforme_vacio(self) -> None:
        vacia = Escuela(nombre="Sin nada"); self.s.add(vacia); self.s.flush()
        uni = us.armar(self.s, vacia.id)
        self.assertEqual(us.piezas_de(self.s, uni.id), [])


class PiezasTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.uni = us.armar(self.s, self.vg.id); self.s.commit()

    def test_agregar_general_crea_la_liga_en_espejo_y_quitarla_la_borra(self) -> None:
        pz = us.agregar_pieza(self.s, self.uni.id, self.pants_rojo.id, color="Rojo", obligatoria=False); self.s.commit()
        self.assertEqual(self._ligas(self.vg), [self.pants_rojo.id])
        fila = next(p for p in us.piezas_de(self.s, self.uni.id) if p["pieza_id"] == pz.id)
        self.assertEqual((fila["origen"], fila["color"], fila["obligatoria"], fila["grupo"]), ("General", "Rojo", False, "Deportivo"))
        us.quitar_pieza(self.s, pz.id); self.s.commit()
        self.assertEqual(self._ligas(self.vg), [])
        self.assertEqual(self.s.query(UniformePieza).filter_by(producto_id=self.pants_rojo.id, activo=True).count(), 0)
        self.assertNotIn(self.pants_rojo.id, [p["producto_id"] for p in us.piezas_de(self.s, self.uni.id)])

    def test_un_producto_propio_no_toca_las_ligas(self) -> None:
        camisa = next(p for p in us.piezas_de(self.s, self.uni.id) if p["nombre"] == "Camisa Vicente Guerrero")
        us.quitar_pieza(self.s, camisa["pieza_id"]); self.s.commit()
        self.assertEqual(self._ligas(self.vg), [])
        us.agregar_pieza(self.s, self.uni.id, self.camisa_vg.id); self.s.commit()
        self.assertEqual(self._ligas(self.vg), [])

    def test_el_mismo_general_en_dos_uniformes_sigue_siendo_un_producto(self) -> None:
        uni_js = us.armar(self.s, self.js.id)
        us.agregar_pieza(self.s, self.uni.id, self.pants_rojo.id); self.s.commit()
        en_vg = [p["producto_id"] for p in us.piezas_de(self.s, self.uni.id)]
        en_js = [p["producto_id"] for p in us.piezas_de(self.s, uni_js.id)]
        self.assertIn(self.pants_rojo.id, en_vg); self.assertIn(self.pants_rojo.id, en_js)
        self.assertEqual(self.s.query(Producto).filter(Producto.nombre.like("Pants Suelto Liso Rojo%")).count(), 1)
        # Quitarlo de VG no lo quita de Justo Sierra ni borra su liga
        pz = self.s.scalar(select(UniformePieza).where(UniformePieza.uniforme_id == self.uni.id, UniformePieza.producto_id == self.pants_rojo.id))
        us.quitar_pieza(self.s, pz.id); self.s.commit()
        self.assertEqual(self._ligas(self.js), [self.pants_rojo.id])
        self.assertIn(self.pants_rojo.id, [p["producto_id"] for p in us.piezas_de(self.s, uni_js.id)])

    def test_agregar_dos_veces_no_duplica_y_reactiva(self) -> None:
        a = us.agregar_pieza(self.s, self.uni.id, self.olan.id)
        us.actualizar_pieza(self.s, a.id, color="Blanca")
        b = us.agregar_pieza(self.s, self.uni.id, self.olan.id, grupo="Escolta")
        self.assertEqual(a.id, b.id)
        self.assertEqual((b.grupo, b.color), ("Escolta", "Blanca"))

    def test_actualizar_valida_grupo_y_campos(self) -> None:
        pz = us.agregar_pieza(self.s, self.uni.id, self.olan.id)
        us.actualizar_pieza(self.s, pz.id, grupo="Deportivo", obligatoria=0, color="  Blanca ", nota="")
        self.assertEqual((pz.grupo, pz.obligatoria, pz.color, pz.nota), ("Deportivo", False, "Blanca", None))
        with self.assertRaises(ValueError):
            us.actualizar_pieza(self.s, pz.id, grupo="Invierno")
        with self.assertRaises(ValueError):
            us.actualizar_pieza(self.s, pz.id, producto_id=1)

    def test_mover_sube_y_baja_sin_salirse(self) -> None:
        nombres = lambda: [p["nombre"] for p in us.piezas_de(self.s, self.uni.id)]  # noqa: E731
        self.assertEqual(nombres()[0], "Pants 2pz Deportivo Vicente Guerrero")
        camisa = next(p for p in us.piezas_de(self.s, self.uni.id) if p["nombre"] == "Camisa Vicente Guerrero")
        us.mover_pieza(self.s, camisa["pieza_id"], -1)
        self.assertEqual(nombres()[1], "Camisa Vicente Guerrero")
        us.mover_pieza(self.s, camisa["pieza_id"], -5)
        self.assertEqual(nombres()[0], "Camisa Vicente Guerrero")
        us.mover_pieza(self.s, camisa["pieza_id"], +99)
        self.assertEqual(nombres()[-1], "Camisa Vicente Guerrero")


class ScriptTests(_Base):
    def test_resumen_e_impresion(self) -> None:
        us.armar(self.s, self.js.id); self.s.commit()
        filas = us.resumen(self.s)
        por_nombre = {f["escuela"]: f for f in filas}
        self.assertEqual((por_nombre["Justo Sierra"]["armado"], por_nombre["Justo Sierra"]["generales"]), (True, 1))
        self.assertEqual((por_nombre["Vicente Guerrero"]["armado"], por_nombre["Vicente Guerrero"]["propias"]), (False, 4))
        out = io.StringIO()
        armar_uniformes.imprimir(filas, salida=out)
        texto = out.getvalue()
        self.assertIn("Justo Sierra (#%d) — ya armado" % self.js.id, texto)
        self.assertIn("○ Deportivo  Pants Suelto  Pants Suelto Liso Rojo", texto)
        self.assertIn("· Deportivo  Pants 2pz     Pants 2pz Deportivo Vicente Guerrero", texto)
        self.assertIn("2 escuelas; 1 ya con uniforme, 1 por armar.", texto)


if __name__ == "__main__":
    unittest.main()
