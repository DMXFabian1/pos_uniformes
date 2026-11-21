"""Freno a quien adivina PIN en la Libreta de casa (POS_PWA_MODO=casa).

La copia de casa se alcanza por Tailscale y el PIN es de 4 a 8 dígitos: sin
freno, 10 000 intentos contra el PIN del dueño son unos minutos. Aquí, por
empleada: tras 5 PIN equivocados seguidos se bloquea 1 min, y cada fallo
siguiente duplica el bloqueo hasta 15 min (unos 4 intentos por hora). Un PIN
bueno lo reinicia. Vive en memoria: reiniciar la API lo borra (es un freno, no
un registro).

Solo en casa: en la tienda nada cambia (ahí entran las empleadas todo el día).
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

FALLOS_ANTES_DE_BLOQUEAR = 5
BLOQUEO_INICIAL_S = 60
BLOQUEO_MAXIMO_S = 15 * 60


@dataclass
class _Estado:
    fallos: int = 0
    bloqueada_hasta: float = 0.0


class LimiteLogin:
    def __init__(self, reloj=time.monotonic) -> None:
        self._reloj = reloj
        self._candado = threading.Lock()
        self._por_empleada: dict[int, _Estado] = {}

    def intento(self, empleada_id: int) -> int:
        """Pide permiso para probar un PIN: 0 = adelante; si no, segundos que faltan.

        El intento se cuenta como fallo ANTES de revisar el PIN (y exito() lo
        borra si era bueno): así muchos intentos en paralelo no se cuelan
        mientras se calcula el PBKDF2 de los primeros."""
        with self._candado:
            estado = self._por_empleada.setdefault(empleada_id, _Estado())
            falta = estado.bloqueada_hasta - self._reloj()
            if falta > 0:
                return math.ceil(falta)
            estado.fallos += 1
            if estado.fallos >= FALLOS_ANTES_DE_BLOQUEAR:
                extra = estado.fallos - FALLOS_ANTES_DE_BLOQUEAR
                espera = min(BLOQUEO_INICIAL_S * (2 ** min(extra, 10)), BLOQUEO_MAXIMO_S)
                estado.bloqueada_hasta = self._reloj() + espera
            return 0

    def exito(self, empleada_id: int) -> None:
        with self._candado:
            self._por_empleada.pop(empleada_id, None)

    def olvidar(self) -> None:
        """Para pruebas."""
        with self._candado:
            self._por_empleada.clear()


limite_login = LimiteLogin()
