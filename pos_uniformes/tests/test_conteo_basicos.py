"""Tests de conteo de 'productos básicos' (sin escuela, ligados por catálogo)."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    CatalogSchoolProductLink,
    Categoria,
    Escuela,
    Marca,
    Producto,
    Variante,
)
from pos_uniformes.services.conteo_calendario_service import obtener_calendario_conteo
from pos_uniformes.services.conteo_service import (
    DIAS_VIGENCIA_DEFAULT,
    ESCUELA_ID_BASICOS,
    NOMBRE_BASICOS,
    guardar_dias_vigencia_basicos,
    obtener_dias_vigencia_basicos,
    obtener_estado_conteo_basicos,
)


def _seed_basico(session: Session) -> None:
    """Un producto básico: sin escuela, ligado por catálogo a una escuela."""
    esc = Escuela(nombre="EscuelaLink")
    cat = Categoria(nombre="CatB")
    marca = Marca(nombre="MarcaB")
    session.add_all([esc, cat, marca])
    session.flush()
    prod = Producto(
        nombre="Playera Básica", nombre_base="Playera Básica",
        categoria_id=cat.id, marca_id=marca.id, escuela_id=None,  # básico
    )
    session.add(prod)
    session.flush()
    session.add(Variante(
        producto_id=prod.id, sku="BAS1", talla="CH", color="BLANCO",
        precio_venta=80, stock_actual=3,
    ))
    session.add(CatalogSchoolProductLink(escuela_id=esc.id, producto_id=prod.id, activo=True))
    session.commit()


class ConteoBasicosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_dias_vigencia_default_y_setter(self) -> None:
        with Session(self.engine) as s:
            self.assertEqual(obtener_dias_vigencia_basicos(s), DIAS_VIGENCIA_DEFAULT)
            guardar_dias_vigencia_basicos(s, 15)
            s.commit()
        with Session(self.engine) as s:
            self.assertEqual(obtener_dias_vigencia_basicos(s), 15)

    def test_estado_basicos_nunca_contado(self) -> None:
        with Session(self.engine) as s:
            _seed_basico(s)
            estado = obtener_estado_conteo_basicos(s)
            self.assertEqual(estado.escuela_id, ESCUELA_ID_BASICOS)
            self.assertEqual(estado.escuela_nombre, NOMBRE_BASICOS)
            self.assertEqual(estado.total_variantes, 1)
            self.assertIsNone(estado.ultimo_conteo)

    def test_basicos_aparece_en_calendario(self) -> None:
        with Session(self.engine) as s:
            _seed_basico(s)
            cal = obtener_calendario_conteo(s)
            basicos = [e for e in cal if e.escuela_id == ESCUELA_ID_BASICOS]
            self.assertEqual(len(basicos), 1)
            self.assertTrue(basicos[0].vencida)  # nunca contado -> vencido
            self.assertTrue(basicos[0].nunca_contada)

    def test_basicos_sin_productos_no_aparece(self) -> None:
        with Session(self.engine) as s:
            cal = obtener_calendario_conteo(s)  # sin básicos sembrados
            self.assertEqual([e for e in cal if e.escuela_id == ESCUELA_ID_BASICOS], [])


if __name__ == "__main__":
    unittest.main()
