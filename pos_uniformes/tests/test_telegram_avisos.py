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
        # La lista lleva al aviso; quitarlo es un segundo toque, ya en su pantalla.
        self.assertIn("av:ver:", botones)

    def test_el_toque_de_quitar_llega_por_el_bot(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        bot.atender_texto("/aviso Junta", session_factory=self.factory)
        with self.factory() as session:
            aviso_id = asvc.listar_activos(session)[0].id
        aviso, _, _ = bot.atender_toque(f"av:quitar:{aviso_id}", session_factory=self.factory)
        self.assertEqual(aviso, "Quitado")
        with self.factory() as session:
            self.assertEqual(asvc.listar_activos(session), [])


class PantallaTests(_BaseDB):
    """`/aviso @caja2 …` manda a una sola pantalla."""

    def setUp(self) -> None:
        super().setUp()
        self._pantallas = [
            {"identificador": "s1", "nombre": "Entrada", "online": True, "arroba": "@entrada"},
            {"identificador": "s2", "nombre": "Caja 2", "online": False, "arroba": "@caja2"},
        ]

    def _con_pantallas(self):
        from unittest.mock import patch

        return patch.object(av, "pantallas", return_value=self._pantallas)

    def test_el_arroba_ignora_espacios_y_acentos(self) -> None:
        with self._con_pantallas():
            self.assertEqual(av.buscar_pantalla(self.session, "caja2")["identificador"], "s2")
            self.assertEqual(av.buscar_pantalla(self.session, "ENTRADA")["identificador"], "s1")

    def test_no_adivina_si_dos_empiezan_igual(self) -> None:
        self._pantallas = [
            {"identificador": "a", "nombre": "Caja 1", "online": True, "arroba": "@caja1"},
            {"identificador": "b", "nombre": "Caja 2", "online": True, "arroba": "@caja2"},
        ]
        with self._con_pantallas():
            # Mandar el aviso a la pantalla equivocada es peor que pedirlo completo.
            self.assertIsNone(av.buscar_pantalla(self.session, "caja"))

    def test_manda_solo_a_esa_pantalla(self) -> None:
        with self._con_pantallas():
            texto = av.mandar(self.session, "@caja2 Ven un momento")
        aviso = asvc.listar_activos(self.session)[0]
        self.assertEqual(aviso.destinos, ["s2"])
        self.assertEqual(aviso.titulo, "Ven un momento")
        self.assertIn("Caja 2", texto)

    def test_avisa_si_la_pantalla_esta_apagada(self) -> None:
        with self._con_pantallas():
            texto = av.mandar(self.session, "@caja2 Ven")
        self.assertIn("apagada", texto)

    def test_una_pantalla_que_no_existe_no_pierde_el_aviso(self) -> None:
        with self._con_pantallas():
            texto = av.mandar(self.session, "@bodega Junta a las 6")
        aviso = asvc.listar_activos(self.session)[0]
        self.assertIsNone(aviso.destinos)  # fue a todas
        self.assertEqual(aviso.titulo, "Junta a las 6")
        self.assertIn("no encontré", texto.lower())

    def test_plazo_y_pantalla_juntos_en_cualquier_orden(self) -> None:
        with self._con_pantallas():
            av.mandar(self.session, "3h @caja2 Ven")
            av.mandar(self.session, "@entrada 3h Ven")
        avisos = asvc.listar_activos(self.session)
        self.assertEqual({tuple(a.destinos) for a in avisos}, {("s2",), ("s1",)})
        for a in avisos:
            self.assertEqual(a.titulo, "Ven")

    def test_un_correo_en_el_texto_no_es_una_pantalla(self) -> None:
        with self._con_pantallas():
            av.mandar(self.session, "Manda todo a juan@correo.com")
        aviso = asvc.listar_activos(self.session)[0]
        self.assertIsNone(aviso.destinos)
        self.assertIn("juan@correo.com", aviso.titulo or aviso.mensaje or "")


class CartelTests(_BaseDB):
    """`/cartel` no interrumpe: ni acuse ni prioridad por encima de nadie."""

    def test_no_pide_acuse_ni_se_pone_por_delante(self) -> None:
        texto = av.mandar(self.session, "Promoción de mochilas", interrumpe=False)
        cartel = asvc.listar_activos(self.session)[0]
        self.assertFalse(cartel.pide_acuse)
        self.assertEqual(cartel.prioridad, 0)
        self.assertIn("No interrumpe", texto)

    def test_el_aviso_si_va_por_delante(self) -> None:
        av.mandar(self.session, "Promoción", interrumpe=False)
        av.mandar(self.session, "Junta a las 6")
        # El aviso urgente sale primero en la rotación.
        self.assertEqual(asvc.listar_activos(self.session)[0].titulo, "Junta a las 6")

    def test_el_comando_cartel(self) -> None:
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.services import telegram_bot_service as bot

        factory = sessionmaker(self.engine)
        bot.atender_texto("/cartel Promoción de mochilas", session_factory=factory)
        with factory() as session:
            self.assertFalse(asvc.listar_activos(session)[0].pide_acuse)


class AlargarYReponerTests(_BaseDB):
    def setUp(self) -> None:
        super().setUp()
        self.factory = sessionmaker(self.engine)
        av.mandar(self.session, "1h Junta a las 6")
        self.aviso = asvc.listar_activos(self.session)[0]

    def test_mas_horas_desde_ahora(self) -> None:
        asvc.alargar(self.session, self.aviso.id, 3)
        self.session.commit()
        falta = asvc._aware(self.aviso.expira_en) - datetime.now(timezone.utc)
        self.assertLess(abs(falta.total_seconds() - 4 * 3600), 60)

    def test_alargar_uno_ya_vencido_cuenta_desde_ahora(self) -> None:
        # Si contara desde el vencimiento viejo, «+3 h» dejaría el aviso vencido.
        self.aviso.expira_en = datetime.now(timezone.utc) - timedelta(hours=5)
        self.session.commit()
        asvc.alargar(self.session, self.aviso.id, 3)
        self.session.commit()
        self.assertTrue(asvc.vigente(self.aviso))
        falta = asvc._aware(self.aviso.expira_en) - datetime.now(timezone.utc)
        self.assertLess(abs(falta.total_seconds() - 3 * 3600), 60)

    def test_reponer_hace_uno_nuevo_y_apaga_el_viejo(self) -> None:
        # Tiene que ser id NUEVO: cada kiosko recuerda los ids que ya acusó.
        nuevo = asvc.reponer(self.session, self.aviso.id)
        self.session.commit()
        self.assertNotEqual(nuevo.id, self.aviso.id)
        self.assertFalse(self.aviso.activo)
        self.assertEqual(nuevo.titulo, "Junta a las 6")
        self.assertTrue(nuevo.pide_acuse)
        self.assertEqual([a.id for a in asvc.listar_activos(self.session)], [nuevo.id])

    def test_reponer_conserva_la_foto_y_la_pantalla(self) -> None:
        a = asvc.crear_anuncio(
            self.session, titulo="Con foto", imagen=b"xx", imagen_mime="image/jpeg",
            destinos=["s2"], pide_acuse=True,
        )
        self.session.commit()
        nuevo = asvc.reponer(self.session, a.id)
        self.assertEqual(nuevo.imagen, b"xx")
        self.assertEqual(nuevo.destinos, ["s2"])

    def test_los_acuses_de_la_vuelta_anterior_se_quedan(self) -> None:
        asvc.marcar_visto(self.session, self.aviso.id, satelite="s1", empleada="Evelyn")
        self.session.commit()
        asvc.reponer(self.session, self.aviso.id)
        self.session.commit()
        self.assertEqual(len(asvc.quien_vio(self.session, self.aviso.id)), 1)

    def test_los_botones(self) -> None:
        aviso, texto, botones = av.atender(
            f"{av.PREFIJO}ver:{self.aviso.id}", session_factory=self.factory
        )
        self.assertIn("Junta a las 6", texto)
        self.assertIn("av:mas:", botones)
        self.assertIn("av:otra:", botones)
        self.assertIn("av:quitar:", botones)

    def test_boton_de_mas_tiempo(self) -> None:
        aviso, _, _ = av.atender(
            f"{av.PREFIJO}mas:{self.aviso.id}:12", session_factory=self.factory
        )
        self.assertIn("se quita en", aviso.lower())

    def test_boton_de_otra_vez(self) -> None:
        aviso, _, _ = av.atender(
            f"{av.PREFIJO}otra:{self.aviso.id}", session_factory=self.factory
        )
        self.assertEqual(aviso, "Puesto otra vez")
        with self.factory() as session:
            self.assertEqual(len(asvc.listar_activos(session)), 1)

    def test_botones_de_un_aviso_que_ya_no_existe(self) -> None:
        for dato in ("ver:99999", "mas:99999:3", "otra:99999", "quitar:99999"):
            aviso, texto, _ = av.atender(f"{av.PREFIJO}{dato}", session_factory=self.factory)
            self.assertTrue(aviso or texto)  # contesta algo, no revienta

    def test_un_boton_mal_formado_no_revienta(self) -> None:
        aviso, _, _ = av.atender(f"{av.PREFIJO}ver:abc", session_factory=self.factory)
        self.assertEqual(aviso, "No conozco ese botón")


def _png(color=(200, 30, 30)) -> bytes:
    """Un PNG de verdad, para que `preparar_imagen` tenga qué masticar."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (80, 60), color).save(buf, format="PNG")
    return buf.getvalue()


class FotoTests(unittest.TestCase):
    """Mandarle una foto al bot la pone a pantalla completa, sin comando."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)

    def _msg(self, **extra) -> dict:
        msg = {"photo": [
            {"file_id": "chico", "file_size": 100},
            {"file_id": "grande", "file_size": 9000},
        ]}
        msg.update(extra)
        return msg

    def test_toma_la_version_mas_grande(self) -> None:
        from pos_uniformes.services import telegram_service

        self.assertEqual(telegram_service.foto_mas_grande(self._msg()), "grande")

    def test_una_foto_mandada_como_archivo_tambien_cuenta(self) -> None:
        from pos_uniformes.services import telegram_service

        msg = {"document": {"file_id": "doc1", "mime_type": "image/png"}}
        self.assertEqual(telegram_service.foto_mas_grande(msg), "doc1")

    def test_un_pdf_no_es_una_foto(self) -> None:
        from pos_uniformes.services import telegram_service

        msg = {"document": {"file_id": "doc1", "mime_type": "application/pdf"}}
        self.assertIsNone(telegram_service.foto_mas_grande(msg))

    def test_un_mensaje_sin_foto_devuelve_none(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        self.assertIsNone(
            bot.atender_foto({"text": "hola"}, session_factory=self.factory)
        )

    def test_la_foto_queda_como_aviso_con_su_pie(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import telegram_bot_service as bot

        with patch(
            "pos_uniformes.services.telegram_service.bajar_archivo", return_value=_png()
        ):
            respuesta = bot.atender_foto(
                self._msg(caption="Así va el aparador"), session_factory=self.factory
            )
        with self.factory() as session:
            aviso = asvc.listar_activos(session)[0]
        self.assertIsNotNone(aviso.imagen)
        self.assertEqual(aviso.imagen_mime, "image/jpeg")
        self.assertEqual(aviso.titulo, "Así va el aparador")
        self.assertTrue(aviso.pide_acuse)
        self.assertIn("Así va el aparador", respuesta)

    def test_una_foto_sin_pie_se_pone_igual(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import telegram_bot_service as bot

        with patch(
            "pos_uniformes.services.telegram_service.bajar_archivo", return_value=_png()
        ):
            respuesta = bot.atender_foto(self._msg(), session_factory=self.factory)
        with self.factory() as session:
            self.assertEqual(len(asvc.listar_activos(session)), 1)
        self.assertIn("solo la imagen", respuesta)

    def test_el_pie_puede_llevar_plazo_y_pantalla(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import telegram_bot_service as bot

        with patch(
            "pos_uniformes.services.telegram_service.bajar_archivo", return_value=_png()
        ):
            bot.atender_foto(self._msg(caption="3h Mira esto"), session_factory=self.factory)
        with self.factory() as session:
            aviso = asvc.listar_activos(session)[0]
            falta = asvc._aware(aviso.expira_en) - datetime.now(timezone.utc)
        self.assertEqual(aviso.titulo, "Mira esto")
        self.assertLess(abs(falta.total_seconds() - 3 * 3600), 60)

    def test_un_pie_con_cartel_no_interrumpe(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import telegram_bot_service as bot

        with patch(
            "pos_uniformes.services.telegram_service.bajar_archivo", return_value=_png()
        ):
            bot.atender_foto(
                self._msg(caption="/cartel Promoción"), session_factory=self.factory
            )
        with self.factory() as session:
            aviso = asvc.listar_activos(session)[0]
        self.assertFalse(aviso.pide_acuse)
        self.assertEqual(aviso.titulo, "Promoción")

    def test_un_pie_con_otro_comando_se_atiende_como_comando(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        respuesta = bot.atender_foto(
            self._msg(caption="/ayuda"), session_factory=self.factory
        )
        self.assertIn("/aviso", respuesta)
        with self.factory() as session:
            self.assertEqual(asvc.listar_activos(session), [])

    def test_si_no_se_puede_bajar_no_se_pone_nada(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import telegram_bot_service as bot

        with patch(
            "pos_uniformes.services.telegram_service.bajar_archivo",
            side_effect=RuntimeError("sin internet"),
        ):
            respuesta = bot.atender_foto(self._msg(), session_factory=self.factory)
        self.assertIn("No pude bajar", respuesta)
        with self.factory() as session:
            # Más vale no poner nada que poner un cuadro negro en la tienda.
            self.assertEqual(asvc.listar_activos(session), [])

    def test_una_imagen_ilegible_no_se_pone(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import telegram_bot_service as bot

        with patch(
            "pos_uniformes.services.telegram_service.bajar_archivo", return_value=b"no soy png"
        ):
            respuesta = bot.atender_foto(self._msg(), session_factory=self.factory)
        self.assertIn("No pude usar esa imagen", respuesta)
        with self.factory() as session:
            self.assertEqual(asvc.listar_activos(session), [])


class SeCierraCuandoYaLoVieronTests(_BaseDB):
    """Un aviso es un recado, no un cartel: cuando llegó, terminó.

    Daniel (02/10): "una vez que ponen enterada, debería de ya no salir de
    nuevo, solo que me avise que ya se enteraron y ya".
    """

    def setUp(self) -> None:
        super().setUp()
        self._pantallas = [
            {"identificador": "s1", "nombre": "Entrada", "online": True, "arroba": "@entrada"},
            {"identificador": "s2", "nombre": "Caja 2", "online": True, "arroba": "@caja2"},
        ]

    def _con_registro(self):
        from unittest.mock import patch

        return patch(
            "pos_uniformes.services.satelite_registry_service.listar_con_estado",
            return_value=self._pantallas,
        )

    def _aviso(self, **extra):
        a = asvc.crear_anuncio(self.session, titulo="Junta a las 6", pide_acuse=True, **extra)
        self.session.commit()
        return a

    def test_con_una_pantalla_que_falta_no_se_cierra(self) -> None:
        a = self._aviso()
        asvc.marcar_visto(self.session, a.id, satelite="s1")
        with self._con_registro():
            cerrado, faltan = asvc.cerrar_si_ya_lo_vieron(self.session, a.id)
        self.assertFalse(cerrado)
        self.assertEqual(faltan, 1)
        self.assertTrue(a.activo)

    def test_cuando_todas_vieron_se_apaga(self) -> None:
        a = self._aviso()
        asvc.marcar_visto(self.session, a.id, satelite="s1")
        asvc.marcar_visto(self.session, a.id, satelite="s2")
        with self._con_registro():
            cerrado, faltan = asvc.cerrar_si_ya_lo_vieron(self.session, a.id)
        self.session.commit()
        self.assertTrue(cerrado)
        self.assertEqual(faltan, 0)
        self.assertEqual(asvc.listar_activos(self.session), [])

    def test_uno_dirigido_se_cierra_con_esa_sola(self) -> None:
        # Si va solo a Caja 2, no tiene que esperar a Entrada.
        a = self._aviso(destinos=["s2"])
        asvc.marcar_visto(self.session, a.id, satelite="s2")
        with self._con_registro():
            cerrado, _ = asvc.cerrar_si_ya_lo_vieron(self.session, a.id)
        self.assertTrue(cerrado)

    def test_sin_saber_cuantas_pantallas_hay_no_se_apaga_nada(self) -> None:
        # Más vale un aviso de más que uno apagado sin que nadie lo viera.
        from unittest.mock import patch

        a = self._aviso()
        asvc.marcar_visto(self.session, a.id, satelite="s1")
        with patch(
            "pos_uniformes.services.satelite_registry_service.listar_con_estado",
            side_effect=OSError("sin DB"),
        ):
            cerrado, faltan = asvc.cerrar_si_ya_lo_vieron(self.session, a.id)
        self.assertFalse(cerrado)
        self.assertTrue(a.activo)

    def test_cerrar_uno_ya_apagado_no_hace_nada(self) -> None:
        a = self._aviso()
        asvc.desactivar(self.session, a.id)
        self.session.commit()
        with self._con_registro():
            self.assertEqual(asvc.cerrar_si_ya_lo_vieron(self.session, a.id), (False, 0))

    def test_el_cartel_no_entra_en_esto(self) -> None:
        # El que no pide acuse no se acusa, así que nunca se cierra solo:
        # se queda hasta que vence o lo quitas. Para eso existe.
        av.mandar(self.session, "Promoción", interrumpe=False)
        cartel = asvc.listar_activos(self.session)[0]
        self.assertFalse(cartel.pide_acuse)
        with self._con_registro():
            cerrado, _ = asvc.cerrar_si_ya_lo_vieron(self.session, cartel.id)
        self.assertFalse(cerrado)

    def test_el_mensaje_cierra_el_tema_cuando_ya_no_falta_nadie(self) -> None:
        texto = av.aviso_de_acuse(
            etiqueta="Junta", empleada="Evelyn", pantalla="Entrada", faltan=0
        )
        self.assertIn("Ya lo vieron", texto)
        self.assertIn("se quitó", texto)

    def test_el_mensaje_dice_cuantas_faltan(self) -> None:
        texto = av.aviso_de_acuse(
            etiqueta="Junta", empleada="Evelyn", pantalla="Entrada", faltan=2
        )
        self.assertIn("Faltan 2 pantallas", texto)
