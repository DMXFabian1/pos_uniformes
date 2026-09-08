"""Configuración local del DVR de cámaras: guardar/cargar, reglas de acceso y URLs."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pos_uniformes.services.dvr_settings_cache_service as svc
from pos_uniformes.services.dvr_settings_cache_service import (
    CanalDVR,
    DVRSettings,
    es_entrada_por_nombre,
    load_dvr_settings,
    parse_channel_titles,
    save_dvr_settings,
)

_SDD = "pos_uniformes.services.dvr_settings_cache_service.satellite_data_dir"
_ENV_KEYS = ("POS_UNIFORMES_DVR_HOST", "POS_UNIFORMES_DVR_USER", "POS_UNIFORMES_DVR_PASSWORD")


def _sin_env():
    """Aísla del pos_uniformes.env real de la máquina."""
    limpio = {k: v for k, v in os.environ.items() if k not in _ENV_KEYS}
    return patch.dict(os.environ, limpio, clear=True), patch.object(
        svc, "load_runtime_env_overrides", return_value={}
    )


class DVRSettingsRulesTests(unittest.TestCase):
    def _settings(self) -> DVRSettings:
        return DVRSettings(
            host="192.168.0.11",
            user="dany",
            password="p@ss:1",
            canales=[
                CanalDVR(1, "VESTIDOR"),
                CanalDVR(2, "CAJA"),
                CanalDVR(4, "ENTRADA1", entrada=True),
                CanalDVR(6, "ENTRADA2", entrada=True),
            ],
        )

    def test_empleada_solo_ve_entradas(self) -> None:
        visibles = self._settings().canales_visibles(admin=False)
        self.assertEqual([c.nombre for c in visibles], ["ENTRADA1", "ENTRADA2"])

    def test_admin_ve_todas(self) -> None:
        visibles = self._settings().canales_visibles(admin=True)
        self.assertEqual(len(visibles), 4)

    def test_rtsp_url_substream_y_principal(self) -> None:
        s = self._settings()
        self.assertEqual(
            s.rtsp_url(4),
            "rtsp://dany:p%40ss%3A1@192.168.0.11:554/cam/realmonitor?channel=4&subtype=1",
        )
        self.assertTrue(s.rtsp_url(4, substream=False).endswith("channel=4&subtype=0"))

    def test_configurado(self) -> None:
        self.assertFalse(DVRSettings().configurado())
        self.assertTrue(DVRSettings(host="h", user="u").configurado())


class DVRSettingsPersistenceTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)):
            original = DVRSettings(
                host="192.168.0.11",
                user="dany",
                password="634700",
                canales=[CanalDVR(4, "ENTRADA1", True), CanalDVR(2, "CAJA", False)],
            )
            save_dvr_settings(original)
            cargado = load_dvr_settings()
        self.assertEqual(cargado, original)

    def test_sin_archivo_cae_a_env(self) -> None:
        env_patch, overrides_patch = _sin_env()
        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)), env_patch, overrides_patch:
            os.environ["POS_UNIFORMES_DVR_HOST"] = "10.0.0.5"
            os.environ["POS_UNIFORMES_DVR_USER"] = "admin"
            os.environ["POS_UNIFORMES_DVR_PASSWORD"] = "x"
            cargado = load_dvr_settings()
        self.assertEqual((cargado.host, cargado.user, cargado.password), ("10.0.0.5", "admin", "x"))
        self.assertEqual(cargado.canales, [])

    def test_sin_archivo_ni_env_no_esta_configurado(self) -> None:
        env_patch, overrides_patch = _sin_env()
        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)), env_patch, overrides_patch:
            cargado = load_dvr_settings()
        self.assertFalse(cargado.configurado())

    def test_archivo_corrupto_no_lanza(self) -> None:
        env_patch, overrides_patch = _sin_env()
        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)), env_patch, overrides_patch:
            path = Path(d) / "data" / "dvr_settings.json"
            path.parent.mkdir(parents=True)
            path.write_text("{no es json", encoding="utf-8")
            cargado = load_dvr_settings()
        self.assertFalse(cargado.configurado())


class ChannelTitleParsingTests(unittest.TestCase):
    def test_parsea_respuesta_dahua_y_marca_entradas(self) -> None:
        texto = (
            "table.ChannelTitle[0].Name=VESTIDOR\r\n"
            "table.ChannelTitle[1].Name=CAJA\r\n"
            "table.ChannelTitle[3].Name=ENTRADA1\r\n"
            "table.ChannelTitle[5].Name=entrada2\r\n"
        )
        canales = parse_channel_titles(texto)
        self.assertEqual([(c.canal, c.nombre, c.entrada) for c in canales], [
            (1, "VESTIDOR", False),
            (2, "CAJA", False),
            (4, "ENTRADA1", True),
            (6, "entrada2", True),
        ])

    def test_respuesta_vacia(self) -> None:
        self.assertEqual(parse_channel_titles(""), [])
        self.assertEqual(parse_channel_titles("OK"), [])

    def test_es_entrada_por_nombre(self) -> None:
        self.assertTrue(es_entrada_por_nombre("Entrada 2.2"))
        self.assertFalse(es_entrada_por_nombre("MOSTRADOR1"))
        self.assertFalse(es_entrada_por_nombre(""))


if __name__ == "__main__":
    unittest.main()
