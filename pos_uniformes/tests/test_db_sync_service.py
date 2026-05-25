"""Tests unitarios para db_sync_service — fingerprint remoto."""

from __future__ import annotations

import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pos_uniformes.services.db_sync_service import _verify_remote_fingerprint


def _fp_kwargs(**overrides) -> dict:
    base = dict(
        host="192.168.1.100",
        port=5432,
        db_name="pos_uniformes",
        user="postgres",
        pg_env={"PGPASSWORD": "secret"},
    )
    base.update(overrides)
    return base


def _run_result(returncode: int, stdout: str, stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class VerifyRemoteFingerprintTests(unittest.TestCase):
    @patch("pos_uniformes.services.db_sync_service._find_pg_tool", return_value="/usr/bin/psql")
    @patch("pos_uniformes.services.db_sync_service.subprocess.run")
    def test_fingerprint_valido_retorna_ok(self, mock_run, _mock_pg):
        """DB con variantes y negocio configurado pasa la verificación."""
        mock_run.return_value = _run_result(0, "150|MAXIMODA\n")
        ok, msg = _verify_remote_fingerprint(**_fp_kwargs())
        self.assertTrue(ok)
        self.assertIn("OK", msg)

    @patch("pos_uniformes.services.db_sync_service._find_pg_tool", return_value="/usr/bin/psql")
    @patch("pos_uniformes.services.db_sync_service.subprocess.run")
    def test_fingerprint_falla_si_sin_variantes(self, mock_run, _mock_pg):
        """DB sin variantes (count=0) es rechazada."""
        mock_run.return_value = _run_result(0, "0|MAXIMODA\n")
        ok, msg = _verify_remote_fingerprint(**_fp_kwargs())
        self.assertFalse(ok)
        self.assertIn("variantes", msg)

    @patch("pos_uniformes.services.db_sync_service._find_pg_tool", return_value="/usr/bin/psql")
    @patch("pos_uniformes.services.db_sync_service.subprocess.run")
    def test_fingerprint_falla_si_negocio_vacio(self, mock_run, _mock_pg):
        """DB con negocio en blanco es rechazada."""
        mock_run.return_value = _run_result(0, "50|\n")
        ok, msg = _verify_remote_fingerprint(**_fp_kwargs())
        self.assertFalse(ok)
        self.assertIn("nombre de negocio", msg)

    @patch("pos_uniformes.services.db_sync_service._find_pg_tool", return_value="/usr/bin/psql")
    @patch("pos_uniformes.services.db_sync_service.subprocess.run")
    def test_fingerprint_falla_si_psql_error(self, mock_run, _mock_pg):
        """Si psql devuelve returncode != 0 se rechaza."""
        mock_run.return_value = _run_result(1, "", "connection refused")
        ok, msg = _verify_remote_fingerprint(**_fp_kwargs())
        self.assertFalse(ok)
        self.assertIn("consultar", msg)

    @patch("pos_uniformes.services.db_sync_service._find_pg_tool", return_value="/usr/bin/psql")
    @patch(
        "pos_uniformes.services.db_sync_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="psql", timeout=10),
    )
    def test_fingerprint_falla_si_timeout(self, _mock_run, _mock_pg):
        """Timeout al verificar el fingerprint es rechazado."""
        ok, msg = _verify_remote_fingerprint(**_fp_kwargs())
        self.assertFalse(ok)
        self.assertIn("Timeout", msg)

    @patch("pos_uniformes.services.db_sync_service._find_pg_tool", return_value=None)
    def test_fingerprint_pasa_si_psql_no_disponible(self, _mock_pg):
        """Sin psql disponible, el fingerprint se omite con advertencia (no bloquea sync)."""
        ok, msg = _verify_remote_fingerprint(**_fp_kwargs())
        self.assertTrue(ok)
        self.assertIn("omitido", msg)


if __name__ == "__main__":
    unittest.main()
