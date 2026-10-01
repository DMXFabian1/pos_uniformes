"""Tests del aviso que se manda desde Telegram y vuelve con el acuse.

Sin Qt ni Postgres: la Session es SQLite en memoria y el NOTIFY se ignora.
Lo que se cuida aquí es lo que hace distinto a un aviso de lejos: que venza
solo, que pida acuse, y que el acuse no se cuente dos veces.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pos_uniformes.database.connection import Base
from pos_uniformes.services import anuncio_service as asvc
from pos_uniformes.services import telegram_avisos_service as av


class PlazoTests(unittest.TestCase):
    def test_lee_horas_minutos_y_dias(self) -> None:
        self.assertEqual(av.leer_plazo("3h"), 3.0)
        self.assertEqual(av.leer_plazo("2 horas"), 2.0)
        self.assertAlmostEqual(av.leer_plazo("30m"), 0.5)
        self.assertEqual(av.leer_plazo("2d"), 48.0)

    def test_una_palabra_normal_no_es_plazo(self) -> None:
        # «5 playeras llegaron» no debe leerse como un plazo de 5 de algo.
        self.assertIsNone(av.leer_plazo("playeras"))
        self.assertIsNone(av.leer_plazo("5"))
        self.assertIsNone(av.leer_plazo("junta"))


class PartirTextoTests(unittest.TestCase):
    def test_corto_va_de_titulo(self) -> None:
        # Lo corto se lee de lejos: va en letras grandes.
        self.assertEqual(av.partir_texto("Junta a las 6"), ("Junta a las 6", None))

    def test_largo_va_de_mensaje(self) -> None:
        largo = "x" * 120
        titulo, mensaje = av.partir_texto(largo)
        self.assertIsNone(titulo)
        self.assertEqual(mensaje, largo)

    def test_dos_renglones_son_titulo_y_mensaje(self) -> None:
        self.assertEqual(
            av.partir_texto("Junta\nHoy a las 6 en la bodega"),
            ("Junta", "Hoy a las 6 en la bodega"),
        )


class _BaseDB(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.factory = sessionmaker(self.engine)

    def tearDown(self) -> None:
        self.session.close()


class MandarTests(_BaseDB):
    def test_mandar_crea_aviso_con_acuse_y_vencimiento(self) -> None:
        texto = av.mandar(self.session, "Junta a las 6", quien="VEND-1")
        activos = asvc.listar_activos(self.session)
        self.assertEqual(len(activos), 1)
        aviso = activos[0]
        self.assertEqual(aviso.titulo, "Junta a las 6")
        self.assertTrue(aviso.pide_acuse)
        self.assertIsNotNone(aviso.expira_en)
        self.assertIn("Junta a las 6", texto)

    def test_plazo_propio(self) -> None:
        av.mandar(self.session, "3h Hoy cerramos temprano")
        aviso = asvc.listar_activos(self.session)[0]
        self.assertEqual(aviso.titulo, "Hoy cerramos temprano")
        falta = asvc._aware(aviso.expira_en) - datetime.now(timezone.utc)
        self.assertLess(abs(falta.total_seconds() - 3 * 3600), 60)

    def test_sin_texto_explica_como_se_usa(self) -> None:
        respuesta = av.mandar(self.session, "")
        self.assertIn("/aviso", respuesta)
        self.assertEqual(asvc.listar_activos(self.session), [])

    def test_solo_plazo_sin_aviso_no_crea_nada(self) -> None:
        respuesta = av.mandar(self.session, "3h")
        # «3h» solo es un aviso de un carácter, no un plazo huérfano.
        self.assertTrue(asvc.listar_activos(self.session))
        self.assertIn("3h", respuesta)


class VencimientoTests(_BaseDB):
    def test_un_aviso_vencido_ya_no_se_muestra(self) -> None:
        asvc.crear_anuncio(
            self.session,
            titulo="Viejo",
            expira_en=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        self.session.commit()
        self.assertEqual(asvc.listar_activos(self.session), [])

    def test_sin_expira_en_vive_como_siempre(self) -> None:
        asvc.crear_anuncio(self.session, titulo="De siempre")
        self.session.commit()
        self.assertEqual(len(asvc.listar_activos(self.session)), 1)

    def test_vencido_sigue_activo_en_la_tabla(self) -> None:
        # Vencer no es apagar: la fila queda para saber qué se mandó.
        a = asvc.crear_anuncio(
            self.session, titulo="Viejo",
            expira_en=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        self.session.commit()
        self.assertTrue(a.activo)


class AcuseTests(_BaseDB):
    def setUp(self) -> None:
        super().setUp()
        self.aviso = asvc.crear_anuncio(self.session, titulo="Junta", pide_acuse=True)
        self.session.commit()

    def test_marcar_visto_guarda_quien_y_donde(self) -> None:
        asvc.marcar_visto(
            self.session, self.aviso.id,
            satelite="sat-1", satelite_nombre="Entrada", empleada="Evelyn",
        )
        self.session.commit()
        vistos = asvc.quien_vio(self.session, self.aviso.id)
        self.assertEqual(len(vistos), 1)
        self.assertEqual(vistos[0].empleada, "Evelyn")
        self.assertEqual(vistos[0].satelite_nombre, "Entrada")

    def test_dos_toques_en_la_misma_pantalla_no_cuentan_doble(self) -> None:
        # Si contara doble, a Daniel le llegarían dos avisos por un solo gesto.
        asvc.marcar_visto(self.session, self.aviso.id, satelite="sat-1", empleada="Evelyn")
        asvc.marcar_visto(self.session, self.aviso.id, satelite="sat-1", empleada="Evelyn")
        self.session.commit()
        self.assertEqual(len(asvc.quien_vio(self.session, self.aviso.id)), 1)

    def test_dos_pantallas_son_dos_acuses(self) -> None:
        asvc.marcar_visto(self.session, self.aviso.id, satelite="sat-1", empleada="Evelyn")
        asvc.marcar_visto(self.session, self.aviso.id, satelite="sat-2", empleada="Fanny")
        self.session.commit()
        self.assertEqual(len(asvc.quien_vio(self.session, self.aviso.id)), 2)

    def test_ya_visto_en(self) -> None:
        self.assertFalse(asvc.ya_visto_en(self.session, self.aviso.id, "sat-1"))
        asvc.marcar_visto(self.session, self.aviso.id, satelite="sat-1")
        self.session.commit()
        self.assertTrue(asvc.ya_visto_en(self.session, self.aviso.id, "sat-1"))
        self.assertFalse(asvc.ya_visto_en(self.session, self.aviso.id, "sat-2"))

    def test_acuse_de_anuncio_que_no_existe(self) -> None:
        self.assertIsNone(asvc.marcar_visto(self.session, 99999, satelite="sat-1"))


class ResumenTests(_BaseDB):
    def test_sin_avisos_dice_como_poner_uno(self) -> None:
        texto = av.resumen(self.session)
        self.assertIn("/aviso", texto)

    def test_dice_que_nadie_lo_vio_todavia(self) -> None:
        av.mandar(self.session, "Junta a las 6")
        texto = av.resumen(self.session)
        self.assertIn("Junta a las 6", texto)
        self.assertIn("Nadie lo ha visto", texto)

    def test_dice_quien_lo_vio(self) -> None:
        av.mandar(self.session, "Junta a las 6")
        aviso = asvc.listar_activos(self.session)[0]
        asvc.marcar_visto(
            self.session, aviso.id, satelite="s1", satelite_nombre="Entrada", empleada="Evelyn"
        )
        self.session.commit()
        texto = av.resumen(self.session)
        self.assertIn("Evelyn", texto)
        self.assertIn("Entrada", texto)


class BotonesTests(_BaseDB):
    def test_quitar_lo_saca_de_las_pantallas(self) -> None:
        av.mandar(self.session, "Junta a las 6")
        aviso_id = asvc.listar_activos(self.session)[0].id
        aviso, texto, botones = av.atender(
            f"{av.PREFIJO}quitar:{aviso_id}", session_factory=self.factory
        )
        self.assertEqual(aviso, "Quitado")
        self.assertEqual(asvc.listar_activos(self.session), [])

    def test_quitar_todos(self) -> None:
        av.mandar(self.session, "Uno")
        av.mandar(self.session, "Dos")
        aviso, _, _ = av.atender(f"{av.PREFIJO}todos", session_factory=self.factory)
        self.assertEqual(aviso, "Se quitaron 2")
        self.assertEqual(asvc.listar_activos(self.session), [])

    def test_es_de_avisos(self) -> None:
        self.assertTrue(av.es_de_avisos("av:todos"))
        self.assertFalse(av.es_de_avisos("m:raiz"))
        self.assertFalse(av.es_de_avisos("pr:1"))


class MensajeDeAcuseTests(unittest.TestCase):
    def test_trae_nombre_pantalla_y_de_que_aviso(self) -> None:
        texto = av.aviso_de_acuse(
            etiqueta="Junta a las 6", empleada="Evelyn", pantalla="Entrada"
        )
        self.assertIn("Evelyn", texto)
        self.assertIn("Entrada", texto)
        self.assertIn("Junta a las 6", texto)

    def test_sin_nombre_dice_alguien(self) -> None:
        texto = av.aviso_de_acuse(etiqueta="Junta", empleada=None, pantalla="Caja 2")
        self.assertIn("Alguien", texto)


class RelojTests(unittest.TestCase):
    def test_hace_cuanto(self) -> None:
        ahora = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(av.hace_cuanto(ahora - timedelta(seconds=30), ahora), "ahora")
        self.assertEqual(av.hace_cuanto(ahora - timedelta(minutes=5), ahora), "hace 5 min")
        self.assertEqual(av.hace_cuanto(ahora - timedelta(hours=3), ahora), "hace 3 h")
        self.assertEqual(av.hace_cuanto(ahora - timedelta(days=1), ahora), "hace 1 día")

    def test_falta_para(self) -> None:
        ahora = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(av.falta_para(None, ahora), "sin vencimiento")
        self.assertEqual(av.falta_para(ahora - timedelta(minutes=1), ahora), "ya venció")
        self.assertEqual(av.falta_para(ahora + timedelta(hours=3), ahora), "se quita en 3 h")
        self.assertEqual(av.falta_para(ahora + timedelta(minutes=20), ahora), "se quita en 20 min")


if __name__ == "__main__":
    unittest.main()


class CacheTests(unittest.TestCase):
    """El aviso tiene que llegar al kiosko sabiendo que pide acuse."""

    def test_el_cache_lleva_pide_acuse_y_la_hora(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from pos_uniformes.services.anuncio_local_cache_service import (
            load_anuncios_cache,
            save_anuncios_cache,
        )

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = Session(engine)
        av.mandar(session, "Junta a las 6")
        filas = asvc.filas_para_cache(session)
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "pos_uniformes.services.anuncio_local_cache_service.satellite_data_dir",
                return_value=Path(tmp),
            ):
                save_anuncios_cache(filas)
                leidos = load_anuncios_cache()
        session.close()
        self.assertEqual(len(leidos), 1)
        self.assertTrue(leidos[0]["pide_acuse"])
        self.assertTrue(leidos[0]["creado_en"])


class BotTests(unittest.TestCase):
    """/aviso y /avisos tienen que estar enganchados al bot y al menú."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)

    def test_el_comando_pone_el_aviso(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        respuesta = bot.atender_texto("/aviso Junta a las 6", session_factory=self.factory)
        self.assertIn("Junta a las 6", respuesta)
        with self.factory() as session:
            self.assertEqual(len(asvc.listar_activos(session)), 1)

    def test_avisos_lista(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        bot.atender_texto("/aviso Junta", session_factory=self.factory)
        respuesta = bot.atender_texto("/avisos", session_factory=self.factory)
        self.assertIn("Junta", respuesta)

    def test_la_ayuda_los_menciona(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        self.assertIn("/aviso", bot.AYUDA)
        self.assertIn("/avisos", bot.AYUDA)

    def test_el_menu_tiene_el_boton(self) -> None:
        from pos_uniformes.services import telegram_menu_service as menu

        acciones = {
            dato for fila in menu._RAIZ for _, dato in fila
        }
        self.assertIn("m:avisos", acciones)

    def test_el_boton_del_menu_abre_la_lista(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        bot.atender_texto("/aviso Junta", session_factory=self.factory)
        _, texto, botones = bot.atender_toque("m:avisos", session_factory=self.factory)
        self.assertIn("Junta", texto)
        self.assertIn("av:quitar:", botones)

    def test_el_toque_de_quitar_llega_por_el_bot(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        bot.atender_texto("/aviso Junta", session_factory=self.factory)
        with self.factory() as session:
            aviso_id = asvc.listar_activos(session)[0].id
        aviso, _, _ = bot.atender_toque(f"av:quitar:{aviso_id}", session_factory=self.factory)
        self.assertEqual(aviso, "Quitado")
        with self.factory() as session:
            self.assertEqual(asvc.listar_activos(session), [])
