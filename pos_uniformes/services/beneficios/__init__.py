"""Motor central de beneficios (T1). M1a: cálculo puro, sin conectar a nada.

Diseño: `diseno_motor_beneficios.md` (§2) y `decisiones_previas_M1.md`.
"""

from pos_uniformes.services.beneficios.contrato import (  # noqa: F401
    Calculo,
    ClienteCtx,
    CompradoraCtx,
    EntradaInvalida,
    EntradaVenta,
    LineaEntrada,
    Pago,
    Rebaja,
    ReglasCtx,
)
from pos_uniformes.services.beneficios.fotografia import fotografia, huella  # noqa: F401
from pos_uniformes.services.beneficios.motor import VERSION_MOTOR, calcular  # noqa: F401
