"""La bandeja «Por nombrar»: lo que entró con código sale al ponerle nombre."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    Marca,
    Producto,
    RolUsuario,
    TipoPieza,
    Usuario,
    Variante,
)
from pos_uniformes.services import por_nombrar_service as pn


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.admin = Usuario(username="admin", nombre_completo="Admin", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
        self.cat = Categoria(nombre="Ropa casual")
        self.marca = Marca(nombre="Darong")
        self.s.add_all([self.admin, self.cat, self.marca, TipoPieza(nombre="Sudadera")])
        self.s.flush()
        self._quieto = patch("pos_uniformes.services.catalog_service.CatalogService._notify_meili")
        self._quieto.start()

    def tearDown(self) -> None:
        self._quieto.stop()

    def _codigo(self, nombre="YT0572", por_identificar=True, color="Surtido") -> Producto:
        p = Producto(nombre=nombre, nombre_base=nombre, categoria=self.cat, marca=self.marca,
                     genero="Mujer", por_identificar=por_identificar)
        self.s.add(p)
        self.s.flush()
        self.s.add(Variante(producto_id=p.id, sku=f"SKU{p.id:06d}", talla="Unitalla", color=color,
                            precio_venta=Decimal("99.00"), stock_actual=30))
        self.s.flush()
        return p


class ListarTests(_Base):
    def test_lista_solo_lo_marcado_y_lo_mas_viejo_primero(self) -> None:
        a = self._codigo("YT0572")
        self._codigo("Sudadera KY357H", por_identificar=False)
        b = self._codigo("MO194")
        self.assertEqual([x.producto_id for x in pn.listar(self.s)], [a.id, b.id])
        self.assertEqual(pn.cuantos(self.s), 2)

    def test_trae_lo_que_hace_falta_para_decidir(self) -> None:
        self._codigo()
        x = pn.listar(self.s)[0]
        self.assertEqual((x.marca, x.categoria, x.genero, x.color, x.precio, x.existencia), ("Darong", "Ropa casual", "Mujer", "Surtido", "99.00", 30))
        self.assertEqual(len(x.skus), 1)


class NombrarTests(_Base):
    def test_al_nombrar_sale_de_la_bandeja_con_su_ficha(self) -> None:
        p = self._codigo()
        pn.nombrar(self.s, self.admin, p.id, nombre="Chamarra YT0572", pieza="Chamarra", detalle="Invierno", color="Negro")
        self.assertEqual(p.nombre, "Chamarra YT0572")          # el código se conserva, en mayúsculas
        self.assertEqual(p.tipo_pieza.nombre, "Chamarra")      # pieza nueva, creada una vez
        self.assertEqual(p.atributo.nombre, "Invierno")
        self.assertEqual({v.color for v in p.variantes}, {"Negro"})
        self.assertFalse(p.por_identificar)
        self.assertEqual(pn.listar(self.s), [])

    def test_reusa_la_pieza_que_ya_existe_sin_importar_mayusculas(self) -> None:
        p = self._codigo()
        pn.nombrar(self.s, self.admin, p.id, nombre="Sudadera YT0572", pieza="sudadera")
        self.assertEqual(self.s.query(TipoPieza).count(), 1)

    def test_sin_pieza_no_se_da_por_nombrado(self) -> None:
        p = self._codigo()
        with self.assertRaises(pn.NoSePuede):
            pn.nombrar(self.s, self.admin, p.id, nombre="Algo YT0572")
        self.assertTrue(p.por_identificar)

    def test_se_puede_guardar_a_medias_sin_sacarlo(self) -> None:
        p = self._codigo()
        pn.nombrar(self.s, self.admin, p.id, nombre="Chamarra YT0572", listo=False)
        self.assertEqual(p.nombre, "Chamarra YT0572")
        self.assertTrue(p.por_identificar)

    def test_el_color_vacio_no_toca_las_tallas(self) -> None:
        p = self._codigo(color="Surtido")
        pn.nombrar(self.s, self.admin, p.id, nombre="Chamarra YT0572", pieza="Chamarra")
        self.assertEqual({v.color for v in p.variantes}, {"Surtido"})

    def test_solo_admin(self) -> None:
        p = self._codigo()
        cajero = Usuario(username="c", nombre_completo="Cajero", password_hash="x", rol=RolUsuario.CAJERO, activo=True)
        self.s.add(cajero)
        with self.assertRaises(PermissionError):
            pn.nombrar(self.s, cajero, p.id, nombre="X", pieza="Chamarra")

    def test_queda_en_el_historial_de_cambios(self) -> None:
        from pos_uniformes.database.models import CambioCatalogo

        p = self._codigo()
        pn.nombrar(self.s, self.admin, p.id, nombre="Chamarra YT0572", pieza="Chamarra")
        self.assertGreater(self.s.query(CambioCatalogo).count(), 0)


if __name__ == "__main__":
    unittest.main()
