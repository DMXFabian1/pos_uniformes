"""La Mac de desarrollo no late: el bot de la tienda no avisa cuando se cierra."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from pos_uniformes.services import satelite_registry_service as rsvc


class SateliteDeDesarrolloTests(unittest.TestCase):
    def _sesion(self, existente=None) -> MagicMock:
        session = MagicMock()
        session.scalar.return_value = existente
        return session

    def test_en_desarrollo_no_se_da_de_alta(self) -> None:
        session = self._sesion()
        with patch.dict(os.environ, {"POS_UNIFORMES_SATELITE_DESARROLLO": "1"}):
            sat = rsvc.registrar(session, "mac", "MacBook Air")
        session.add.assert_not_called()
        self.assertEqual(sat.identificador, "mac")

    def test_en_desarrollo_no_mueve_el_latido(self) -> None:
        # Si el latido no cambia, el vigilante nunca la ve «prendida hoy» y no
        # hay «se apagó» ni «ya volvió».
        viejo = MagicMock(ultimo_visto="antes")
        session = self._sesion(viejo)
        with patch.dict(os.environ, {"POS_UNIFORMES_SATELITE_DESARROLLO": "1"}):
            rsvc.registrar(session, "mac", "MacBook Air")
        self.assertEqual(viejo.ultimo_visto, "antes")

    def test_una_pantalla_de_la_tienda_late_como_siempre(self) -> None:
        session = self._sesion()
        with patch.dict(os.environ, {"POS_UNIFORMES_SATELITE_DESARROLLO": "0"}):
            sat = rsvc.registrar(session, "entrada", "Entrada")
        session.add.assert_called_once()
        self.assertIsNotNone(sat.ultimo_visto)


if __name__ == "__main__":
    unittest.main()
