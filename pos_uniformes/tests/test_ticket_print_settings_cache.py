"""Tests del cache de preferencias de impresión de tickets."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services.ticket_print_settings_cache_service import (
    falta_impresora_tickets,
    save_ticket_print_settings,
)

_SDD = "pos_uniformes.services.ticket_print_settings_cache_service.satellite_data_dir"


class FaltaImpresoraTicketsTests(unittest.TestCase):
    def test_sin_config_falta(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                self.assertTrue(falta_impresora_tickets())

    def test_predeterminada_del_sistema_falta(self) -> None:
        # "" = "Impresora predeterminada del sistema" en el combo → cuenta como falta.
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                save_ticket_print_settings("", 1)
                self.assertTrue(falta_impresora_tickets())

    def test_impresora_elegida_no_falta(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                save_ticket_print_settings("XP-80 Termica", 1)
                self.assertFalse(falta_impresora_tickets())


if __name__ == "__main__":
    unittest.main()
