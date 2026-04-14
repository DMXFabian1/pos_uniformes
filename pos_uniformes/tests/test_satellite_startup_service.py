"""Tests para satellite_startup_service."""

from __future__ import annotations

import socket
import unittest
from unittest.mock import MagicMock, patch


class ProbeDatabaseHostTests(unittest.TestCase):

    def test_returns_true_when_connection_succeeds(self) -> None:
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("pos_uniformes.services.satellite_startup_service.socket.create_connection", return_value=mock_conn):
            from pos_uniformes.services.satellite_startup_service import probe_database_host
            result = probe_database_host()

        self.assertTrue(result)

    def test_returns_false_on_connection_refused(self) -> None:
        with patch(
            "pos_uniformes.services.satellite_startup_service.socket.create_connection",
            side_effect=ConnectionRefusedError,
        ):
            from pos_uniformes.services.satellite_startup_service import probe_database_host
            result = probe_database_host()

        self.assertFalse(result)

    def test_returns_false_on_timeout(self) -> None:
        with patch(
            "pos_uniformes.services.satellite_startup_service.socket.create_connection",
            side_effect=socket.timeout,
        ):
            from pos_uniformes.services.satellite_startup_service import probe_database_host
            result = probe_database_host()

        self.assertFalse(result)

    def test_returns_false_on_os_error(self) -> None:
        with patch(
            "pos_uniformes.services.satellite_startup_service.socket.create_connection",
            side_effect=OSError("host no disponible"),
        ):
            from pos_uniformes.services.satellite_startup_service import probe_database_host
            result = probe_database_host()

        self.assertFalse(result)

    def test_uses_configured_host_and_port(self) -> None:
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("pos_uniformes.services.satellite_startup_service.socket.create_connection", return_value=mock_conn) as mock_create, \
             patch("pos_uniformes.services.satellite_startup_service.settings") as mock_settings:
            mock_settings.db_host = "192.168.1.100"
            mock_settings.db_port = 5432
            from pos_uniformes.services.satellite_startup_service import probe_database_host
            probe_database_host(timeout_sec=2.0)

        mock_create.assert_called_once_with(("192.168.1.100", 5432), timeout=2.0)


if __name__ == "__main__":
    unittest.main()
