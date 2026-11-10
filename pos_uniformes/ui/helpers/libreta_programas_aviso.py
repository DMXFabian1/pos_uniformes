"""E4-C (P-E4-5): en la Libreta, la empleada ve qué pasó con los clientes que
propuso a un programa, en el mismo recuadro y con el mismo «Entendido» que las
respuestas de descansos.

Va en su propia sesión: si la base todavía no tiene las tablas de programas,
las respuestas de descansos se siguen enseñando igual.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


def respuestas(session_factory, employee_code: str | None) -> list[tuple[int, str]]:
    """(id, texto) de lo que ya se resolvió y ella no ha visto. [] si falla."""
    if not employee_code:
        return []
    try:
        from pos_uniformes.services.fidelizacion import membresia_service as ms

        with session_factory() as session:
            return [(int(m.id), ms.texto_de_respuesta(session, m))
                    for m in ms.respuestas_sin_ver(session, employee_code)]
    except Exception:  # noqa: BLE001 — sin esto, la Libreta sigue igual
        _logger.debug("Libreta: no se pudieron leer las respuestas de programas", exc_info=True)
        return []


def marcar_vistas(session_factory, ids, employee_code: str | None) -> None:
    if not ids or not employee_code:
        return
    try:
        from pos_uniformes.services.fidelizacion import membresia_service as ms

        with session_factory() as session:
            for membresia_id in ids:
                ms.marcar_vista(session, membresia_id, employee_code)
            session.commit()
    except Exception:  # noqa: BLE001 — se le vuelve a enseñar la próxima vez
        _logger.exception("Libreta: no se pudo marcar la respuesta de programa como vista")
