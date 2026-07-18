"""Tests de la Fase A de anuncios/cartelera: servicio, cache local e imagen.

Todo sin Qt ni Postgres: la Session usa SQLite en memoria y el cache local se
redirige a un directorio temporal. El NOTIFY se ignora en SQLite (best-effort).
"""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.services import anuncio_service as svc
from pos_uniformes.services.anuncio_image_service import preparar_imagen
from pos_uniformes.services.anuncio_local_cache_service import (
    load_anuncios_cache,
    save_anuncios_cache,
)

_CACHE_MOD = "pos_uniformes.services.anuncio_local_cache_service.satellite_data_dir"


class AnuncioServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()

    def test_crear_solo_texto(self) -> None:
        a = svc.crear_anuncio(self.session, titulo="Aviso", mensaje="Cerramos temprano")
        self.assertIsNotNone(a.id)
        self.assertTrue(a.activo)
        self.assertEqual(a.titulo, "Aviso")
        self.assertIsNone(a.imagen)

    def test_crear_solo_imagen(self) -> None:
        a = svc.crear_anuncio(self.session, imagen=b"\xff\xd8\xff", imagen_mime="image/jpeg")
        self.assertEqual(a.imagen, b"\xff\xd8\xff")
        self.assertEqual(a.imagen_mime, "image/jpeg")

    def test_crear_sin_contenido_falla(self) -> None:
        with self.assertRaises(ValueError):
            svc.crear_anuncio(self.session, titulo="   ", mensaje="")

    def test_crear_imagen_gigante_falla(self) -> None:
        enorme = b"x" * (svc.MAX_IMAGEN_BYTES + 1)
        with self.assertRaises(ValueError):
            svc.crear_anuncio(self.session, imagen=enorme, imagen_mime="image/jpeg")

    def test_mime_se_limpia_sin_imagen(self) -> None:
        # Si no hay imagen, el mime no debe quedar colgado.
        a = svc.crear_anuncio(self.session, mensaje="hola", imagen_mime="image/png")
        self.assertIsNone(a.imagen_mime)

    def test_listar_activos_ordena_por_prioridad_y_fecha(self) -> None:
        a = svc.crear_anuncio(self.session, mensaje="normal")
        b = svc.crear_anuncio(self.session, mensaje="urgente", prioridad=10)
        c = svc.crear_anuncio(self.session, mensaje="tambien normal")
        self.session.commit()
        ids = [x.id for x in svc.listar_activos(self.session)]
        # Prioridad alta primero; a igual prioridad, el más viejo primero.
        self.assertEqual(ids, [b.id, a.id, c.id])

    def test_desactivar_saca_de_activos(self) -> None:
        a = svc.crear_anuncio(self.session, mensaje="uno")
        svc.crear_anuncio(self.session, mensaje="dos")
        self.session.commit()
        svc.desactivar(self.session, a.id)
        self.session.commit()
        mensajes = [x.mensaje for x in svc.listar_activos(self.session)]
        self.assertEqual(mensajes, ["dos"])

    def test_desactivar_todos(self) -> None:
        svc.crear_anuncio(self.session, mensaje="uno")
        svc.crear_anuncio(self.session, mensaje="dos")
        self.session.commit()
        n = svc.desactivar_todos(self.session)
        self.session.commit()
        self.assertEqual(n, 2)
        self.assertEqual(svc.listar_activos(self.session), [])

    def test_notificar_no_revienta_en_sqlite(self) -> None:
        a = svc.crear_anuncio(self.session, mensaje="uno")
        self.session.commit()
        # SQLite no tiene pg_notify; debe ser best-effort sin lanzar.
        svc.notificar(self.session, "inmediato", a.id)

    def test_destinos_filtran_por_satelite(self) -> None:
        svc.crear_anuncio(self.session, mensaje="a todos")  # destinos None
        svc.crear_anuncio(self.session, mensaje="solo sat-1", destinos=["sat-1"])
        svc.crear_anuncio(self.session, mensaje="sat-1 y sat-2", destinos=["sat-1", "sat-2"])
        self.session.commit()
        # sat-1 ve los tres; sat-3 solo el de "todos".
        m1 = [a.mensaje for a in svc.listar_activos(self.session, para="sat-1")]
        self.assertEqual(m1, ["a todos", "solo sat-1", "sat-1 y sat-2"])
        m3 = [a.mensaje for a in svc.listar_activos(self.session, para="sat-3")]
        self.assertEqual(m3, ["a todos"])
        # Sin `para`, el admin ve todos.
        self.assertEqual(len(svc.listar_activos(self.session)), 3)

    def test_destinos_vacios_es_todos(self) -> None:
        a = svc.crear_anuncio(self.session, mensaje="x", destinos=[])
        self.assertIsNone(a.destinos)
        self.assertTrue(svc.visible_para(a, "cualquiera"))

    def test_destinos_dedup_y_limpia(self) -> None:
        a = svc.crear_anuncio(
            self.session, mensaje="x", destinos=[" sat-1 ", "sat-1", "", "sat-2"]
        )
        self.assertEqual(a.destinos, ["sat-1", "sat-2"])

    def test_filas_para_cache_filtra_por_destino(self) -> None:
        svc.crear_anuncio(self.session, mensaje="todos")
        svc.crear_anuncio(self.session, mensaje="solo sat-9", destinos=["sat-9"])
        self.session.commit()
        filas = svc.filas_para_cache(self.session, para="sat-1")
        self.assertEqual([f["mensaje"] for f in filas], ["todos"])


class AnuncioCacheTests(unittest.TestCase):
    def _cache_rows(self):
        return [
            {"id": 1, "titulo": "T1", "mensaje": "M1", "imagen_mime": None,
             "imagen_bytes": None, "duracion_seg": 5, "prioridad": 0},
            {"id": 2, "titulo": None, "mensaje": None, "imagen_mime": "image/jpeg",
             "imagen_bytes": b"\xff\xd8\xffDATA", "duracion_seg": 10, "prioridad": 3},
        ]

    def test_roundtrip_guarda_metadata_e_imagen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_CACHE_MOD, return_value=Path(d)):
                save_anuncios_cache(self._cache_rows())
                cargados = load_anuncios_cache()
                self.assertEqual(len(cargados), 2)
                con_img = next(x for x in cargados if x["id"] == 2)
                self.assertIsNotNone(con_img["imagen_path"])
                self.assertTrue(Path(con_img["imagen_path"]).exists())
                self.assertEqual(
                    Path(con_img["imagen_path"]).read_bytes(), b"\xff\xd8\xffDATA"
                )
                sin_img = next(x for x in cargados if x["id"] == 1)
                self.assertIsNone(sin_img["imagen_path"])
                self.assertEqual(sin_img["duracion_seg"], 5)

    def test_load_sin_cache_devuelve_vacio(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_CACHE_MOD, return_value=Path(d)):
                self.assertEqual(load_anuncios_cache(), [])

    def test_save_borra_imagenes_huerfanas(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_CACHE_MOD, return_value=Path(d)):
                save_anuncios_cache(self._cache_rows())
                # Segundo guardado sin el anuncio 2 → su imagen debe borrarse.
                save_anuncios_cache([
                    {"id": 1, "titulo": "T1", "mensaje": "M1", "imagen_mime": None,
                     "imagen_bytes": None, "duracion_seg": 5, "prioridad": 0},
                ])
                carpeta = Path(d) / "data" / "anuncios"
                sobrantes = [p.name for p in carpeta.iterdir() if p.name != "index.json"]
        self.assertEqual(sobrantes, [])


class AnuncioImagenTests(unittest.TestCase):
    def _png(self, size) -> bytes:
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGBA", size, (255, 0, 0, 128)).save(buf, format="PNG")
        return buf.getvalue()

    def test_reduce_y_recodifica_a_jpeg(self) -> None:
        from PIL import Image

        data, mime = preparar_imagen(self._png((3000, 2000)), max_lado=1600)
        self.assertEqual(mime, "image/jpeg")
        img = Image.open(io.BytesIO(data))
        self.assertEqual(img.format, "JPEG")
        self.assertEqual(max(img.size), 1600)  # lado más largo topado
        self.assertEqual(img.mode, "RGB")      # alpha aplanado

    def test_no_agranda_imagen_chica(self) -> None:
        from PIL import Image

        data, _ = preparar_imagen(self._png((200, 100)), max_lado=1600)
        img = Image.open(io.BytesIO(data))
        self.assertEqual(img.size, (200, 100))

    def test_imagen_invalida_lanza(self) -> None:
        with self.assertRaises(ValueError):
            preparar_imagen(b"no soy una imagen")


if __name__ == "__main__":
    unittest.main()
