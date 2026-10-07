"""Los ajustes ESC/POS se guardan COMPLETOS.

La lista de claves estaba escrita a mano en el guardado, y al agregar
`ticket_como_imagen` nadie la actualizó: se leía pero no se escribía. Daniel
marcaba la casilla, guardaba, volvía a abrir y estaba desmarcada — sin error ni
aviso, como si no hubiera tocado nada (2026-10-07).
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import escpos_settings_cache_service as esc


class _ConCache(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ruta = Path(self._tmp.name) / "escpos.json"
        self._p = patch.object(esc, "_cache_path", return_value=self._ruta)
        self._p.start()

    def tearDown(self) -> None:
        self._p.stop()
        self._tmp.cleanup()


class TodoSobreviveAlGuardadoTests(_ConCache):
    def test_el_ticket_dibujado_se_queda_marcado(self) -> None:
        """El caso exacto que falló."""
        esc.save_escpos_settings(esc.EscPosSettings(ticket_como_imagen=True))
        self.assertTrue(esc.load_escpos_settings().ticket_como_imagen)

    def test_NINGUN_campo_se_pierde_en_el_viaje(self) -> None:
        """La prueba que hace que esto no se repita con el campo que venga:
        se cambian TODOS respecto al default y se exige que vuelvan igual."""
        d = esc.EscPosSettings()
        cambiados = {}
        for campo in dataclasses.fields(esc.EscPosSettings):
            valor = getattr(d, campo.name)
            if isinstance(valor, bool):
                cambiados[campo.name] = not valor
            elif isinstance(valor, int):
                cambiados[campo.name] = valor + 7
            elif isinstance(valor, str):
                cambiados[campo.name] = valor + "x"
        distintos = dataclasses.replace(d, **cambiados)
        esc.save_escpos_settings(distintos)
        self.assertEqual(esc.load_escpos_settings(), distintos)

    def test_el_archivo_lleva_una_clave_por_campo(self) -> None:
        esc.save_escpos_settings(esc.EscPosSettings())
        guardado = json.loads(self._ruta.read_text(encoding="utf-8"))
        esperadas = {f.name for f in dataclasses.fields(esc.EscPosSettings)}
        self.assertEqual(set(guardado), esperadas)

    def test_un_archivo_viejo_sin_la_clave_nueva_sigue_abriendo(self) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_text(json.dumps({"enabled": True, "codepage": 2}), encoding="utf-8")
        s = esc.load_escpos_settings()
        self.assertTrue(s.enabled)
        self.assertFalse(s.ticket_como_imagen)   # el default, no un error


if __name__ == "__main__":
    unittest.main()
