"""CatalogService: nombre sin escuela repetida, $0, SKU con candado, búsqueda
después del commit y borrar/reactivar prendas (tanda 1 del alta, 2026-11-13)."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConjuntoComponente,
    Escuela,
    Marca,
    Producto,
    RolUsuario,
    SkuSequence,
    Uniforme,
    UniformePieza,
    Usuario,
    Variante,
)
from pos_uniformes.services.catalog_service import CatalogService as C
from pos_uniformes.ui.helpers.catalog_product_form_summary_helper import (
    build_catalog_product_display_name_preview,
)


class ArmarNombreTests(unittest.TestCase):
    def test_quita_la_escuela_repetida_de_estv(self) -> None:
        self.assertEqual(
            C.armar_nombre("Pants 3pz Deportivo Estv 154 ESTV 154", "ESTV 154"),
            "Pants 3pz Deportivo ESTV 154",
        )

    def test_no_repite_la_escuela_si_ya_viene_en_el_nombre(self) -> None:
        self.assertEqual(C.armar_nombre("Playera Deportiva UVEG", "UVEG"), "Playera Deportiva UVEG")
        self.assertEqual(C.armar_nombre("Playera Deportiva", "UVEG"), "Playera Deportiva UVEG")

    def test_escuela_escrita_sin_acentos_o_sin_parentesis(self) -> None:
        self.assertEqual(
            C.armar_nombre("Suéter Ignacio Ramirez Lopez", "Ignacio Ramírez López"),
            "Suéter Ignacio Ramírez López",
        )
        self.assertEqual(
            C.armar_nombre("Pants Suelto Álvaro Obregón El Carretón", "Álvaro Obregón (El Carretón)"),
            "Pants Suelto Álvaro Obregón (El Carretón)",
        )

    def test_la_escuela_en_medio_tambien_se_quita(self) -> None:
        self.assertEqual(C.armar_nombre("Playera CONALEP Deportiva", "CONALEP"), "Playera Deportiva CONALEP")

    def test_sin_escuela_solo_titulo(self) -> None:
        self.assertEqual(C.armar_nombre("chaleco mujer KY18005"), "Chaleco Mujer KY18005")

    def test_quitar_la_escuela_anterior(self) -> None:
        self.assertEqual(
            C.armar_nombre("Pants Suelto Miguel Hidalgo", "Ignacio Allende", quitar=("Miguel Hidalgo",)),
            "Pants Suelto Ignacio Allende",
        )


    def test_escuela_nueva_contenida_en_la_anterior(self) -> None:
        # De «Miguel Hidalgo (Rancho Nuevo)» a «Miguel Hidalgo», con el
        # nombre completo (como lo mandan scripts, Por nombrar o la API).
        self.assertEqual(
            C.armar_nombre(
                "Pants 2pz Miguel Hidalgo (Rancho Nuevo)",
                "Miguel Hidalgo",
                quitar=("Miguel Hidalgo (Rancho Nuevo)",),
            ),
            "Pants 2pz Miguel Hidalgo",
        )
        self.assertEqual(
            C.armar_nombre(
                "Pants 2pz Miguel Hidalgo", "Miguel Hidalgo (Rancho Nuevo)", quitar=("Miguel Hidalgo",)
            ),
            "Pants 2pz Miguel Hidalgo (Rancho Nuevo)",
        )


class TitleCaseSiglasTests(unittest.TestCase):
    def test_siglas_conocidas_no_se_bajan_aunque_todo_venga_en_mayusculas(self) -> None:
        self.assertEqual(C._title_case("PANTS 3PZ DEPORTIVO ESTV 154"), "Pants 3pz Deportivo ESTV 154")
        self.assertEqual(C._title_case("playera uveg"), "Playera UVEG")
        self.assertEqual(C._title_case("camisa conalep"), "Camisa CONALEP")

    def test_siglas_de_la_escuela_que_se_pasan(self) -> None:
        self.assertEqual(C._title_case("FALDA CBTA 33", siglas=("CBTA",)), "Falda CBTA 33")

    def test_lo_de_antes_sigue_igual(self) -> None:
        self.assertEqual(C._title_case("pants 3pz azul"), "Pants 3pz Azul")
        self.assertEqual(C._title_case("PLAYERA DEPORTIVA"), "Playera Deportiva")
        self.assertEqual(C._title_case("sudadera KY357H"), "Sudadera KY357H")


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine, expire_on_commit=False)
        self.admin = Usuario(username="admin", nombre_completo="Admin", rol=RolUsuario.ADMIN, password_hash="x")
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="Sin marca")
        self.estv = Escuela(nombre="ESTV 154")
        self.allende = Escuela(nombre="Ignacio Allende")
        self.s.add_all([self.admin, self.cat, self.marca, self.estv, self.allende])
        self.s.commit()
        self._quieto = patch.object(C, "_avisar_busqueda")
        self.avisos = self._quieto.start()
        self.addCleanup(self._quieto.stop)

    def _producto(self, nombre: str, escuela: Escuela | None = None) -> Producto:
        return C.crear_producto(self.s, self.admin, self.cat, self.marca, nombre, escuela=escuela)

    def _talla(self, producto: Producto, talla: str, precio: str = "245") -> Variante:
        return C.crear_variante(self.s, self.admin, producto, None, talla, "Sin color", Decimal(precio))


class NombreAlGuardarTests(_ConBase):
    def _editar(self, producto: Producto, nombre: str, escuela: Escuela | None) -> Producto:
        return C.actualizar_producto(
            self.s, self.admin, producto, self.cat, self.marca, nombre, escuela=escuela
        )

    def test_crear_no_repite_la_escuela(self) -> None:
        p = self._producto("Pants 3pz Deportivo ESTV 154", self.estv)
        self.assertEqual(p.nombre, "Pants 3pz Deportivo ESTV 154")
        self.assertEqual(p.nombre_base, p.nombre)

    def test_editar_con_el_nombre_guardado_no_duplica(self) -> None:
        p = self._producto("Pants 3pz Deportivo", self.estv)
        for _ in range(3):
            self._editar(p, p.nombre_base, self.estv)
        self.assertEqual(p.nombre, "Pants 3pz Deportivo ESTV 154")

    def test_editar_el_nombre_viejo_ya_duplicado_lo_limpia(self) -> None:
        p = self._producto("Pants 3pz Deportivo", self.estv)
        p.nombre = p.nombre_base = "Pants 3pz Deportivo Estv 154 ESTV 154"
        self._editar(p, p.nombre_base, self.estv)
        self.assertEqual(p.nombre, "Pants 3pz Deportivo ESTV 154")

    def test_cambiar_de_escuela_quita_la_anterior(self) -> None:
        p = self._producto("Pants Suelto", self.estv)
        self._editar(p, p.nombre_base, self.allende)
        self.assertEqual(p.nombre, "Pants Suelto Ignacio Allende")

    def test_la_vista_previa_es_lo_que_se_guarda(self) -> None:
        casos = [
            ("pants 3pz deportivo", self.estv),
            ("Pants 3pz Deportivo Estv 154 ESTV 154", self.estv),
            ("PLAYERA DEPORTIVA ESTV 154", self.estv),
            ("Chamarra Ignacio Allende", self.allende),
            ("chaleco mujer KY18005", None),
        ]
        for i, (escrito, escuela) in enumerate(casos):
            with self.subTest(escrito=escrito):
                previa = build_catalog_product_display_name_preview(
                    base_name=escrito,
                    context_values=(escuela.nombre if escuela else "", "Deportivo", "Pants 3pz"),
                )
                marca = Marca(nombre=f"M{i}")
                self.s.add(marca)
                self.s.flush()
                p = C.crear_producto(self.s, self.admin, self.cat, marca, escrito, escuela=escuela)
                self.assertEqual(previa, p.nombre)
                # Y al editar con lo que el asistente carga, sigue igual.
                cargado = C.nombre_sin_escuela(p.nombre_base, escuela.nombre if escuela else None)
                previa_edicion = build_catalog_product_display_name_preview(
                    base_name=cargado, context_values=(escuela.nombre if escuela else "", "", "")
                )
                C.actualizar_producto(self.s, self.admin, p, self.cat, marca, cargado, escuela=escuela)
                self.assertEqual(previa_edicion, p.nombre)


class PrecioTests(_ConBase):
    def test_cero_o_vacio_no_se_guarda(self) -> None:
        p = self._producto("Bata", None)
        for precio in (Decimal("0"), Decimal("0.00"), None, "", "  "):
            with self.subTest(precio=precio):
                with self.assertRaises(ValueError):
                    C.crear_variante(self.s, self.admin, p, None, "Unitalla", "Sin color", precio)
        self.assertEqual(self.s.scalars(select(Variante)).all(), [])

    def test_editar_a_cero_no_se_puede(self) -> None:
        v = self._talla(self._producto("Bata", None), "Unitalla", "75")
        with self.assertRaisesRegex(ValueError, r"\$0"):
            C.actualizar_variante(self.s, self.admin, v, v.producto, v.sku, "Unitalla", "Sin color", Decimal("0"))

    def test_una_talla_vieja_en_cero_se_puede_editar_sin_tocar_el_precio(self) -> None:
        v = self._talla(self._producto("Bata", None), "Unitalla", "75")
        v.precio_venta = Decimal("0")
        C.actualizar_variante(self.s, self.admin, v, v.producto, v.sku, "Unitalla", "Blanco", Decimal("0"))
        self.assertEqual(v.color, "Blanco")

    def test_validar_precio(self) -> None:
        self.assertEqual(C.validar_precio_venta("245"), Decimal("245"))
        with self.assertRaises(ValueError):
            C.validar_precio_venta("-1")
        with self.assertRaises(ValueError):
            C.validar_precio_venta("abc")


class SkuConCandadoTests(_ConBase):
    def _sentencias_del_contador(self, accion) -> list:
        vistas = []

        def capturar(estado) -> None:
            if estado.is_select and "sku_sequence" in str(estado.statement):
                vistas.append(estado.statement)

        event.listen(self.s, "do_orm_execute", capturar)
        try:
            accion()
        finally:
            event.remove(self.s, "do_orm_execute", capturar)
        return vistas

    def test_dar_de_alta_toma_el_contador_con_for_update(self) -> None:
        p = self._producto("Bata", None)
        self._talla(p, "4")  # crea el contador
        vistas = self._sentencias_del_contador(lambda: self._talla(p, "6"))
        self.assertTrue(vistas)
        for sentencia in vistas:
            self.assertIsNotNone(sentencia._for_update_arg)
            self.assertIn("FOR UPDATE", str(sentencia.compile(dialect=postgresql.dialect())))
            self.assertTrue(sentencia.get_execution_options().get("populate_existing"))

    def test_la_vista_previa_no_bloquea(self) -> None:
        p = self._producto("Bata", None)
        self._talla(p, "4")
        vistas = self._sentencias_del_contador(lambda: C.preview_next_skus(self.s, 3))
        vistas += self._sentencias_del_contador(
            lambda: C.generar_sku_sugerido(self.s, p, "6", "Sin color")
        )
        self.assertTrue(vistas)
        self.assertTrue(all(s._for_update_arg is None for s in vistas))

    def test_otra_computadora_avanza_el_contador_y_no_chocamos(self) -> None:
        p = self._producto("Bata", None)
        primera = self._talla(p, "4")
        self.s.commit()
        # La otra PC (otra sesión) da de alta y avanza el contador.
        otra = Session(self.engine)
        admin = otra.get(Usuario, self.admin.id)
        prod = otra.get(Producto, p.id)
        de_la_otra = C.crear_variante(otra, admin, prod, None, "6", "Sin color", Decimal("245"))
        otra.commit()
        # Nuestra sesión tenía en memoria el contador viejo (expire_on_commit=False).
        segunda = self._talla(p, "8")
        self.s.commit()
        skus = {primera.sku, de_la_otra.sku, segunda.sku}
        self.assertEqual(len(skus), 3)
        contador = self.s.scalar(select(SkuSequence))
        self.assertEqual(contador.ultimo_numero, 3)
        otra.close()


class BusquedaDespuesDelCommitTests(_ConBase):
    def test_avisa_una_vez_y_despues_del_commit(self) -> None:
        self.avisos.reset_mock()
        p = self._producto("Bata", None)
        self._talla(p, "4")
        self._talla(p, "6")
        self.avisos.assert_not_called()
        self.s.commit()
        self.avisos.assert_called_once()

    def test_si_hay_rollback_no_avisa(self) -> None:
        self.avisos.reset_mock()
        self._producto("Bata", None)
        self.s.rollback()
        self.s.commit()
        self.avisos.assert_not_called()

    def test_lote_con_savepoints_avisa_hasta_el_commit_aunque_falle_la_ultima(self) -> None:
        # Como «Presentaciones por lote»: cada talla en su begin_nested; la
        # última choca. Ni liberar un savepoint ni deshacerlo cuenta como el
        # commit o el rollback de afuera.
        p = self._producto("Bata", None)
        self.s.commit()
        self.avisos.reset_mock()
        for talla, sku in (("6", "SKUL6"), ("8", "SKUL8"), ("10", "SKUL8")):
            try:
                with self.s.begin_nested():
                    C.crear_variante(self.s, self.admin, p, sku, talla, "Sin color", Decimal("10"))
                    self.s.flush()
            except ValueError:
                pass
        self.avisos.assert_not_called()
        self.s.commit()
        self.avisos.assert_called_once()
        self.assertEqual(sorted(v.talla for v in p.variantes), ["6", "8"])

    def test_savepoint_fallido_despues_de_crear_no_borra_el_aviso(self) -> None:
        self.avisos.reset_mock()
        self._producto("Bata", None)
        try:
            with self.s.begin_nested():
                raise ValueError("talla repetida")
        except ValueError:
            pass
        self.s.commit()
        self.avisos.assert_called_once()

    def test_borrar_tambien_avisa(self) -> None:
        p = self._producto("Bata", None)
        self._talla(p, "4")
        self.s.commit()
        self.avisos.reset_mock()
        C.eliminar_producto(self.s, self.admin, p)
        self.s.commit()
        self.avisos.assert_called_once()


class BorrarYReactivarTests(_ConBase):
    def test_no_borra_una_prenda_que_esta_en_un_uniforme(self) -> None:
        p = self._producto("Pants Suelto", self.allende)
        uniforme = Uniforme(escuela_id=self.allende.id, nombre="Uniforme")
        self.s.add(uniforme)
        self.s.flush()
        self.s.add(UniformePieza(uniforme_id=uniforme.id, producto_id=p.id, grupo="Deportivo"))
        self.s.flush()
        with self.assertRaisesRegex(ValueError, "uniforme de Ignacio Allende"):
            C.eliminar_producto(self.s, self.admin, p)

    def test_no_borra_una_pieza_de_receta(self) -> None:
        pants2 = self._producto("Pants 2pz", self.allende)
        pants3 = self._producto("Pants 3pz", self.allende)
        self.s.add(ConjuntoComponente(conjunto_id=pants3.id, componente_id=pants2.id, cantidad=1))
        self.s.flush()
        with self.assertRaisesRegex(ValueError, "receta de Pants 3pz"):
            C.eliminar_producto(self.s, self.admin, pants2)
        with self.assertRaisesRegex(ValueError, "tiene receta"):
            C.eliminar_producto(self.s, self.admin, pants3)

    def test_validar_eliminable_es_staticmethod_simple(self) -> None:
        # @classmethod encima de @staticmethod deja de funcionar en Python 3.13.
        self.assertIsInstance(C.__dict__["_validar_producto_eliminable"], staticmethod)

    def test_borra_la_que_esta_suelta(self) -> None:
        p = self._producto("Short", None)
        self._talla(p, "4")
        self.s.flush()
        C.eliminar_producto(self.s, self.admin, p)
        self.s.flush()
        self.assertIsNone(self.s.get(Producto, p.id))

    def test_reactivar_no_revive_las_tallas_dadas_de_baja_aparte(self) -> None:
        p = self._producto("Chamarra", self.allende)
        t4, t6, t8 = (self._talla(p, t) for t in ("4", "6", "8"))
        C.cambiar_estado_variante(self.s, self.admin, t8, False)
        self.s.flush()
        C.cambiar_estado_producto(self.s, self.admin, p, False)
        self.s.flush()
        self.assertEqual([t.activo for t in (t4, t6, t8)], [False, False, False])
        C.cambiar_estado_producto(self.s, self.admin, p, True)
        self.s.flush()
        self.assertEqual([t.activo for t in (t4, t6, t8)], [True, True, False])

    def test_bajas_viejas_sin_rastro_se_reactivan_todas(self) -> None:
        p = self._producto("Chamarra", self.allende)
        t4, t6 = (self._talla(p, t) for t in ("4", "6"))
        p.activo = False
        t4.activo = t6.activo = False
        self.s.flush()
        C.cambiar_estado_producto(self.s, self.admin, p, True)
        self.assertEqual([t4.activo, t6.activo], [True, True])


if __name__ == "__main__":
    unittest.main()
