"""Revisión de la limpieza del chat del bot (2026-11-20).

- Una lista que no se pudo leer ya no hace mandar (y fijar) un menú nuevo
  en cada vuelta, ni retirar el de ayer como si no existiera.
- El menú nuevo de media tarde tapa la pantalla de trabajo, y un aviso de
  otro proceso entre el envío de la pantalla y su apunte también.
- «message to delete not found» cuenta como borrado; un 429 como sin red.
- Al quitar un candado abandonado no se borra el recién tomado por otro.
Ninguna prueba habla con Telegram.
"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import telegram_limpieza_service as limpieza


class _ConArchivo(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            limpieza, "ruta_estado", return_value=Path(self._dir.name) / "bot_mensajes.json"
        )
        parche.start()
        self.addCleanup(parche.stop)

    def _ids(self) -> list[int]:
        return [int(m["id"]) for m in limpieza._leer()["mensajes"]]


def _sin_lectura():
    return patch.object(limpieza, "_leer", side_effect=limpieza.NoSeLeyo("antivirus"))


def _menu_fijo():
    from pos_uniformes.services import telegram_menu_service as menu

    return patch.object(menu, "menu_raiz", return_value=("Menú de hoy", "{}"))


def _sin_base():
    raise RuntimeError("sin base")


class _Telegram:
    """Un `_llamar` falso que apunta cada método."""

    def __init__(self, *, editar=None, mid=100) -> None:
        self.metodos: list[str] = []
        self._editar = editar
        self._mid = mid

    def __call__(self, token, metodo, datos=None, timeout=15.0):
        self.metodos.append(metodo)
        if metodo == "editMessageText" and self._editar is not None:
            raise self._editar
        if metodo == "sendMessage":
            mid, self._mid = self._mid, self._mid + 1
            return {"ok": True, "result": {"message_id": mid}}
        return {"ok": True, "result": True}


# ── (0) Sin poder leer la lista no se decide nada ────────────────────────────


class SinLeerLaListaTests(_ConArchivo):
    HOY = datetime(2026, 11, 20, 9, 5)

    def test_limpiar_si_toca_no_manda_menus_en_cada_vuelta(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        limpieza.recordar_menu(10)
        falso = _Telegram()
        with _sin_lectura(), _menu_fijo(), patch.object(telegram_service, "_llamar", falso):
            for _ in range(3):
                bot.limpiar_si_toca(session_factory=_sin_base, token="t", chat_id="c", ahora=self.HOY)
        self.assertEqual(falso.metodos, [])
        self.assertEqual(limpieza.menu_fijado(), 10)

    def test_asegurar_menu_no_manda_otro_sin_lista(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        falso = _Telegram()
        with _sin_lectura(), _menu_fijo(), patch.object(telegram_service, "_llamar", falso):
            mid = bot.asegurar_menu_fijado(session_factory=_sin_base, token="t", chat_id="c")
        self.assertEqual(mid, 0)
        self.assertEqual(falso.metodos, [])

    def test_si_no_se_pudo_apuntar_el_menu_nuevo_se_quita_y_no_se_fija(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        falso = _Telegram(mid=100)
        with _menu_fijo(), patch.object(telegram_service, "_llamar", falso), \
                patch.object(limpieza, "recordar_menu", return_value=False):
            mid = bot.asegurar_menu_fijado(session_factory=_sin_base, token="t", chat_id="c")
        self.assertEqual(mid, 0)
        self.assertEqual(falso.metodos, ["sendMessage", "deleteMessage"])

    def test_un_toque_sin_lista_no_reescribe_el_mensaje_tocado(self) -> None:
        """Si no se sabe cuál es el menú, se trata como el menú: no se pisa."""
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        toque = {"id": "q1", "data": "mn:caja",
                 "message": {"chat": {"id": "c"}, "message_id": 10, "date": int(time.time())}}
        with _sin_lectura(), \
                patch.object(telegram_service, "responder_toque"), \
                patch.object(telegram_service, "editar_mensaje") as editar, \
                patch.object(bot, "mostrar_en_pantalla") as pantalla, \
                patch.object(bot, "atender_toque", return_value=("", "Caja", "{}")):
            bot._atender_toque(toque, session_factory=_sin_base, token="t", chat_id="c")
        editar.assert_not_called()
        pantalla.assert_called_once()


# ── (3) La pantalla tapada ───────────────────────────────────────────────────


class PantallaTapadaTests(_ConArchivo):
    def test_el_menu_nuevo_de_media_tarde_tapa_la_pantalla(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        hoy = date.today().isoformat()
        limpieza.recordar_pantalla(200, hoy)
        falso = _Telegram(mid=210)
        with _menu_fijo(), patch.object(telegram_service, "_llamar", falso):
            self.assertEqual(bot.asegurar_menu_fijado(session_factory=_sin_base, token="t", chat_id="c"), 210)
        self.assertEqual(limpieza.pantalla(), (200, hoy, True))

    def test_aviso_de_otro_proceso_antes_del_apunte_deja_tapada(self) -> None:
        limpieza.recordar_pantalla(100, "2026-11-20")
        limpieza.tapar_pantalla(200)          # la pantalla nueva sale y se anota
        limpieza.tapar_pantalla(201)          # otro proceso manda su aviso
        limpieza.recordar_pantalla(200, "2026-11-20")
        self.assertTrue(limpieza.pantalla()[2])

    def test_sin_nada_abajo_la_pantalla_nueva_no_queda_tapada(self) -> None:
        limpieza.recordar_pantalla(100, "2026-11-20")
        limpieza.tapar_pantalla(200)
        limpieza.recordar_pantalla(200, "2026-11-20")
        self.assertFalse(limpieza.pantalla()[2])


# ── (4) y (5) Lo que contesta Telegram ───────────────────────────────────────


class MotivosDeBorradoTests(unittest.TestCase):
    def _motivo(self, exc) -> str:
        from pos_uniformes.services import telegram_service

        with patch.object(telegram_service, "_llamar", side_effect=exc):
            return telegram_service.borrar_con_motivo(5, token="t", chat_id="c")

    def test_ya_no_existe_cuenta_como_borrado(self) -> None:
        exc = RuntimeError("Telegram respondió: Bad Request: message to delete not found")
        self.assertEqual(self._motivo(exc), "ok")

    def test_un_429_es_como_sin_red(self) -> None:
        exc = RuntimeError("Telegram respondió: Too Many Requests: retry after 7")
        self.assertEqual(self._motivo(exc), "red")

    def test_otro_no_sigue_siendo_no(self) -> None:
        exc = RuntimeError("Telegram respondió: Bad Request: message can't be deleted")
        self.assertEqual(self._motivo(exc), "no")

    def test_es_limite_de_velocidad(self) -> None:
        from pos_uniformes.services import telegram_service

        self.assertTrue(telegram_service.es_limite_de_velocidad(
            RuntimeError("Telegram respondió: Too Many Requests: retry after 3")))
        self.assertFalse(telegram_service.es_limite_de_velocidad(OSError("timeout")))


class BarridoConLimiteTests(_ConArchivo):
    def test_un_429_para_la_vuelta_y_no_pospone_lo_demas_una_hora(self) -> None:
        from pos_uniformes.services import telegram_service

        for mid in (1, 2, 3):
            limpieza.anotar(mid, ts=datetime(2026, 11, 19, 12, 0).timestamp())
        llamados: list[str] = []

        def _llamar(token, metodo, datos=None, timeout=15.0):
            llamados.append(datos["message_id"])
            raise RuntimeError("Telegram respondió: Too Many Requests: retry after 5")

        with patch.object(telegram_service, "_llamar", side_effect=_llamar):
            limpieza.barrer(
                borrar=lambda mid: telegram_service.borrar_con_motivo(mid, token="t", chat_id="c"),
                ahora=datetime(2026, 11, 20, 9, 30),
            )
        self.assertEqual(llamados, ["1"])
        self.assertTrue(all("reintentar" not in m for m in limpieza._leer()["mensajes"]))


class PropuestaRetiradaSeOlvidaTests(_ConArchivo):
    def test_retirar_la_propuesta_la_quita_de_la_lista(self) -> None:
        from pos_uniformes.services import corte_propuesta_service as cps
        from pos_uniformes.services import telegram_service

        with patch.object(cps, "ruta_estado", return_value=Path(self._dir.name) / "corte.json"):
            cps.anotar_propuesta(datetime.now(), message_id=501)
            limpieza.anotar(501, conservar=True)
            with patch.object(telegram_service, "borrar_con_motivo", return_value="ok"):
                self.assertTrue(cps.retirar_mensaje())
        self.assertEqual(self._ids(), [])


class MenuConLimiteTests(_ConArchivo):
    def test_un_429_al_reescribir_no_cambia_el_menu(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        limpieza.recordar_menu(100)
        falso = _Telegram(
            editar=RuntimeError("Telegram respondió: Too Many Requests: retry after 9"), mid=999
        )
        with _menu_fijo(), patch.object(telegram_service, "_llamar", falso):
            mid = bot.asegurar_menu_fijado(session_factory=_sin_base, token="t", chat_id="c")
        self.assertEqual(mid, 100)
        self.assertEqual(falso.metodos, ["editMessageText"])
        self.assertEqual(limpieza.menu_fijado(), 100)


# ── (6) El candado entre procesos ────────────────────────────────────────────


class CandadoTests(_ConArchivo):
    def _candado(self) -> Path:
        ruta = limpieza.ruta_estado().with_suffix(".lock")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        return ruta

    def test_quitar_un_abandonado_no_borra_el_recien_tomado_por_otro(self) -> None:
        ruta = self._candado()
        ruta.write_text("otro:vigente", encoding="utf-8")   # recién tomado por A
        b = limpieza._CandadoEntreProcesos()
        b._ruta = ruta
        b._quitar_abandonado()                               # B lo vio viejo antes
        self.assertTrue(ruta.exists())
        self.assertEqual(ruta.read_text(encoding="utf-8"), "otro:vigente")
        self.assertEqual(sorted(p.name for p in ruta.parent.iterdir()), [ruta.name])

    def test_al_salir_no_se_borra_un_candado_ajeno(self) -> None:
        ruta = self._candado()
        with limpieza._CandadoEntreProcesos():
            ruta.write_text("otro:suyo", encoding="utf-8")   # otro lo tomó a la mala
        self.assertTrue(ruta.exists())

    def test_un_candado_propio_que_no_se_pudo_borrar_no_hace_esperar(self) -> None:
        ruta = self._candado()
        ruta.write_text(f"{os.getpid()}:viejo", encoding="utf-8")
        inicio = time.monotonic()
        limpieza.anotar(1)
        self.assertLess(time.monotonic() - inicio, 1.0)
        self.assertEqual(self._ids(), [1])
        self.assertFalse(ruta.exists())


if __name__ == "__main__":
    unittest.main()
