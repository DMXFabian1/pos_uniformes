"""Cola offline dañada u ocupada (auditoría 2026-11-08, decisión D3).

- Un archivo ilegible NO se sobrescribe ni se borra: se aparta como
  `<nombre>.corrupto-<fecha>.json`, se empieza una cola nueva, se avisa en el
  kiosko y por Telegram.
- Un archivo ocupado (Windows/antivirus) NO está dañado: el error sube, el
  archivo queda intacto y se puede reintentar.
- Lo mismo vale para la cola de cortes.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pos_uniformes.services import libreta_local_queue_service as cola

VENTA = {"employee_code": "VEND-2", "tipo": "venta", "items": [], "monto_total": "0"}


class _ColaTemporal(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz = Path(tempfile.mkdtemp(prefix="cola_rescate_"))
        self.carpeta = self.raiz / "data"
        self.carpeta.mkdir()
        p = patch.object(cola, "satellite_data_dir", return_value=self.raiz)
        p.start()
        self.addCleanup(p.stop)
        e = patch.object(cola, "_ESPERA_ARCHIVO_OCUPADO", 0)
        e.start()
        self.addCleanup(e.stop)
        cola._RESCATES_POR_AVISAR.clear()
        cola._RESCATE_RECIENTE.clear()
        self.addCleanup(cola._RESCATES_POR_AVISAR.clear)
        self.addCleanup(cola._RESCATE_RECIENTE.clear)
        self.addCleanup(shutil.rmtree, self.raiz, True)

    def _apartados(self, stem: str) -> list[Path]:
        return sorted(self.carpeta.glob(f"{stem}.corrupto-*.json"))


class ColaDeVentasDanadaTests(_ColaTemporal):
    def test_cola_corrupta_se_aparta_intacta_y_empieza_una_nueva(self) -> None:
        cola_path = self.carpeta / "libreta_pendiente.json"
        cola_path.write_text('[{"employee_code": "VEND-3", "tipo": "ven', encoding="utf-8")

        cola.encolar_operacion(dict(VENTA))

        apartados = self._apartados("libreta_pendiente")
        self.assertEqual(len(apartados), 1)
        # El contenido original se conserva byte por byte (ahí van las ventas).
        self.assertEqual(apartados[0].read_text(encoding="utf-8"), '[{"employee_code": "VEND-3", "tipo": "ven')
        # La cola nueva solo trae la venta nueva.
        self.assertEqual(json.loads(cola_path.read_text(encoding="utf-8")), [VENTA])
        # El kiosko lo ve (etiqueta) y la pantalla de venta lo avisa una vez.
        self.assertEqual(cola.archivos_rescatados(), [apartados[0].name])
        self.assertEqual(cola.tomar_rescate_reciente(), apartados[0].name)
        self.assertIsNone(cola.tomar_rescate_reciente())

    def test_cola_que_no_es_lista_tambien_se_aparta(self) -> None:
        (self.carpeta / "libreta_pendiente.json").write_text('{"a": 1}', encoding="utf-8")
        self.assertEqual(cola.pendientes(), [])
        self.assertEqual(len(self._apartados("libreta_pendiente")), 1)

    def test_bytes_que_no_son_utf8_se_apartan(self) -> None:
        (self.carpeta / "libreta_pendiente.json").write_bytes(b"\xff\xfe\x00basura")
        self.assertEqual(cola.pendientes(), [])
        apartados = self._apartados("libreta_pendiente")
        self.assertEqual(apartados[0].read_bytes(), b"\xff\xfe\x00basura")

    def test_dos_rescates_seguidos_no_se_pisan(self) -> None:
        path = self.carpeta / "libreta_pendiente.json"
        path.write_text("{roto-1", encoding="utf-8")
        cola.pendientes()
        path.write_text("{roto-2", encoding="utf-8")
        cola.pendientes()
        contenidos = sorted(p.read_text(encoding="utf-8") for p in self._apartados("libreta_pendiente"))
        self.assertEqual(contenidos, ["{roto-1", "{roto-2"])

    def test_aviso_por_telegram_una_sola_vez(self) -> None:
        (self.carpeta / "libreta_pendiente.json").write_text("{roto", encoding="utf-8")
        session = MagicMock()
        with patch("pos_uniformes.services.alertas_service.encolar") as encolar, \
                patch("pos_uniformes.services.satellite_identity_service.get_satellite_name",
                      return_value="CAJA-2"):
            self.assertEqual(cola.drenar_pendientes(session), 0)
            encolar.assert_called_once()
            texto = encolar.call_args.args[1]
            self.assertIn("CAJA-2", texto)
            self.assertIn(".corrupto-", texto)
            # El siguiente drenado ya no repite el aviso.
            cola.drenar_pendientes(session)
            encolar.assert_called_once()

    def test_si_el_aviso_falla_se_reintenta_despues(self) -> None:
        (self.carpeta / "libreta_pendiente.json").write_text("{roto", encoding="utf-8")
        session = MagicMock()
        with patch("pos_uniformes.services.alertas_service.encolar", side_effect=RuntimeError("sin red")):
            cola.drenar_pendientes(session)
        self.assertEqual(len(cola._RESCATES_POR_AVISAR), 1)
        with patch("pos_uniformes.services.alertas_service.encolar") as encolar:
            cola.drenar_pendientes(session)
        encolar.assert_called_once()
        self.assertEqual(cola._RESCATES_POR_AVISAR, [])


class ArchivoOcupadoTests(_ColaTemporal):
    def test_archivo_bloqueado_propaga_el_error_y_no_pierde_nada(self) -> None:
        path = self.carpeta / "libreta_pendiente.json"
        original = json.dumps([{"employee_code": "VEND-3", "tipo": "venta", "items": [], "monto_total": "50"}])
        path.write_text(original, encoding="utf-8")

        with patch.object(Path, "read_text", side_effect=PermissionError("en uso por otro proceso")) as leer:
            with self.assertRaises(PermissionError):
                cola.encolar_operacion(dict(VENTA))
        self.assertEqual(leer.call_count, cola._INTENTOS_ARCHIVO_OCUPADO)  # reintentó
        self.assertEqual(path.read_text(encoding="utf-8"), original)  # intacto
        self.assertEqual(self._apartados("libreta_pendiente"), [])  # NO se trató como dañado
        self.assertEqual(cola._RESCATES_POR_AVISAR, [])

        # Ya libre, el reintento funciona y conserva lo anterior.
        cola.encolar_operacion(dict(VENTA))
        self.assertEqual(len(cola.pendientes()), 2)

    def test_ocupado_un_momento_se_lee_al_reintentar(self) -> None:
        path = self.carpeta / "libreta_pendiente.json"
        path.write_text("[]", encoding="utf-8")
        real = Path.read_text
        llamadas = {"n": 0}

        def a_veces(self_path, *a, **kw):
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                raise PermissionError("antivirus")
            return real(self_path, *a, **kw)

        with patch.object(Path, "read_text", a_veces):
            cola.encolar_operacion(dict(VENTA))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [VENTA])

    def test_pendientes_no_truena_si_esta_ocupado(self) -> None:
        path = self.carpeta / "libreta_pendiente.json"
        path.write_text("[]", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=PermissionError("ocupado")):
            self.assertEqual(cola.pendientes(), [])
        self.assertTrue(path.exists())

    def test_drenar_con_archivo_ocupado_no_sube_ni_borra(self) -> None:
        path = self.carpeta / "libreta_pendiente.json"
        original = json.dumps([VENTA])
        path.write_text(original, encoding="utf-8")
        session = MagicMock()
        with patch.object(Path, "read_text", side_effect=PermissionError("ocupado")):
            with self.assertRaises(PermissionError):
                cola.drenar_pendientes(session)
        session.commit.assert_not_called()
        self.assertEqual(path.read_text(encoding="utf-8"), original)


class ColaDeCortesTests(_ColaTemporal):
    def test_cola_de_cortes_corrupta_se_aparta(self) -> None:
        path = self.carpeta / "libreta_cortes_pendientes.json"
        path.write_text("[{corte roto", encoding="utf-8")

        corte = {"fecha": "2026-11-08", "monto_final": "100", "creado_por": "VEND-1"}
        cola.encolar_corte(corte)

        apartados = self._apartados("libreta_cortes_pendientes")
        self.assertEqual(len(apartados), 1)
        self.assertEqual(apartados[0].read_text(encoding="utf-8"), "[{corte roto")
        self.assertEqual(cola.cortes_pendientes(), [corte])
        self.assertIn(apartados[0].name, cola.archivos_rescatados())

    def test_drenar_cortes_corrupta_avisa_y_no_truena(self) -> None:
        (self.carpeta / "libreta_cortes_pendientes.json").write_text("nada", encoding="utf-8")
        session = MagicMock()
        with patch("pos_uniformes.services.alertas_service.encolar") as encolar:
            self.assertEqual(cola.drenar_cortes(session), 0)
        encolar.assert_called_once()
        self.assertEqual(len(self._apartados("libreta_cortes_pendientes")), 1)

    def test_cortes_ocupado_propaga_y_queda_intacto(self) -> None:
        path = self.carpeta / "libreta_cortes_pendientes.json"
        original = json.dumps([{"fecha": "2026-11-07", "monto_final": "5"}])
        path.write_text(original, encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=OSError("bloqueado")):
            with self.assertRaises(OSError):
                cola.encolar_corte({"fecha": "2026-11-08", "monto_final": "1"})
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertEqual(self._apartados("libreta_cortes_pendientes"), [])


if __name__ == "__main__":
    unittest.main()
