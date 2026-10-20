"""La foto del modelo: se recorta y comprime al subir, viaja por hash, y el kiosko la cachea."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Categoria, Marca, Producto
from pos_uniformes.services import foto_local_cache_service as cache
from pos_uniformes.services import producto_foto_service as fotos


def _jpeg(ancho: int, alto: int, color=(200, 30, 30)) -> bytes:
    img = Image.new("RGB", (ancho, alto), color)
    salida = io.BytesIO()
    img.save(salida, format="JPEG", quality=95)
    return salida.getvalue()


class PrepararTests(unittest.TestCase):
    def test_una_foto_de_celular_queda_chica_y_en_proporcion(self) -> None:
        mini, media, ancho, alto, h = fotos.preparar(_jpeg(3000, 4000))
        self.assertLess(len(mini), 40_000)                 # cabe en una tarjeta sin pesar
        self.assertLess(len(media), 300_000)
        self.assertEqual((ancho, alto), (750, 1000))        # 3:4, lado largo 1000
        self.assertEqual(len(h), 32)

    def test_una_foto_acostada_se_recorta_al_centro(self) -> None:
        mini, _, ancho, alto, _ = fotos.preparar(_jpeg(4000, 2000))
        self.assertAlmostEqual(ancho / alto, 3 / 4, places=2)
        self.assertEqual(Image.open(io.BytesIO(mini)).size, (300, 400))

    def test_el_hash_cambia_con_la_foto(self) -> None:
        a = fotos.preparar(_jpeg(800, 1000, (200, 30, 30)))[4]
        b = fotos.preparar(_jpeg(800, 1000, (30, 30, 200)))[4]
        self.assertNotEqual(a, b)
        self.assertEqual(a, fotos.preparar(_jpeg(800, 1000, (200, 30, 30)))[4])

    def test_lo_que_no_es_imagen_se_dice(self) -> None:
        with self.assertRaises(fotos.NoSePuede):
            fotos.preparar(b"esto no es una foto")
        with self.assertRaises(fotos.NoSePuede):
            fotos.preparar(b"")


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        cat, marca = Categoria(nombre="Ropa casual"), Marca(nombre="Yamo")
        self.s.add_all([cat, marca])
        self.s.flush()
        self.p = Producto(nombre="Sudadera QS227", nombre_base="Sudadera QS227", categoria=cat, marca=marca)
        self.s.add(self.p)
        self.s.flush()
        self._quieto = patch.object(fotos, "_avisar_catalogo")
        self._quieto.start()

    def tearDown(self) -> None:
        self._quieto.stop()


class GuardarTests(_ConBase):
    def test_guardar_y_reemplazar(self) -> None:
        f = fotos.guardar(self.s, self.p.id, _jpeg(1200, 1600))
        h1 = f.hash
        self.assertEqual(fotos.hashes(self.s), {self.p.id: h1})
        self.assertTrue(fotos.miniatura(self.s, self.p.id))
        fotos.guardar(self.s, self.p.id, _jpeg(1200, 1600, (0, 0, 0)))
        self.assertNotEqual(fotos.hash_de(self.s, self.p.id), h1)
        self.assertEqual(len(fotos.hashes(self.s)), 1)      # sigue siendo UNA por modelo

    def test_quitar(self) -> None:
        fotos.guardar(self.s, self.p.id, _jpeg(900, 1200))
        self.assertTrue(fotos.quitar(self.s, self.p.id))
        self.assertFalse(fotos.quitar(self.s, self.p.id))
        self.assertEqual(fotos.hash_de(self.s, self.p.id), "")

    def test_un_producto_que_no_existe(self) -> None:
        with self.assertRaises(fotos.NoSePuede):
            fotos.guardar(self.s, 9999, _jpeg(900, 1200))


class CacheDelKioskoTests(_ConBase):
    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self._p = patch.object(cache, "satellite_data_dir", return_value=Path(self._tmp.name))
        self._p.start()

    def tearDown(self) -> None:
        self._p.stop()
        self._tmp.cleanup()
        super().tearDown()

    def _filas(self):
        return [{"producto_id": self.p.id, "foto_hash": fotos.hash_de(self.s, self.p.id)}]

    def test_baja_lo_que_falta_una_sola_vez(self) -> None:
        fotos.guardar(self.s, self.p.id, _jpeg(900, 1200))
        self.assertEqual(cache.sincronizar(self.s, self._filas()), 1)
        self.assertIsNotNone(cache.ruta_miniatura(fotos.hash_de(self.s, self.p.id)))
        self.assertEqual(cache.sincronizar(self.s, self._filas()), 0)     # ya la tiene

    def test_una_foto_nueva_reemplaza_y_la_vieja_se_borra(self) -> None:
        fotos.guardar(self.s, self.p.id, _jpeg(900, 1200))
        vieja = fotos.hash_de(self.s, self.p.id)
        cache.sincronizar(self.s, self._filas())
        fotos.guardar(self.s, self.p.id, _jpeg(900, 1200, (0, 0, 0)))
        cache.sincronizar(self.s, self._filas())
        self.assertIsNone(cache.ruta_miniatura(vieja))
        self.assertIsNotNone(cache.ruta_miniatura(fotos.hash_de(self.s, self.p.id)))

    def test_sin_foto_no_hay_nada_que_bajar_ni_que_romper(self) -> None:
        self.assertEqual(cache.sincronizar(self.s, [{"producto_id": self.p.id, "foto_hash": ""}]), 0)
        self.assertIsNone(cache.ruta_miniatura(""))

    def test_la_mediana_se_baja_al_abrir_la_ficha_y_se_queda(self) -> None:
        fotos.guardar(self.s, self.p.id, _jpeg(900, 1200))
        h = fotos.hash_de(self.s, self.p.id)
        self.assertIsNone(cache.ruta_mediana(h))
        ruta = cache.asegurar_mediana(self.s, self.p.id, h)
        self.assertIsNotNone(ruta)
        self.assertIs(cache.asegurar_mediana(None, self.p.id, h).exists(), True)   # sin base, del disco

    def test_una_descarga_que_falla_no_frena_a_las_demas(self) -> None:
        fotos.guardar(self.s, self.p.id, _jpeg(900, 1200))
        filas = [{"producto_id": 777, "foto_hash": "deadbeef" * 4}] + self._filas()
        with patch.object(fotos, "miniatura", side_effect=[OSError("sin red"), fotos.miniatura(self.s, self.p.id)]):
            self.assertEqual(cache.sincronizar(self.s, filas), 1)


if __name__ == "__main__":
    unittest.main()
