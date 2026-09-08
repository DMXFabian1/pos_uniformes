"""Escucha el bot de Telegram en la PC servidor (tarea "POS Telegram bot").

    python -m pos_uniformes.scripts.telegram_bot
"""

from __future__ import annotations

import logging
import sys


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import telegram_service
    from pos_uniformes.services.telegram_bot_service import escuchar

    token = telegram_service.token_configurado()
    chat_id = telegram_service.chat_id_configurado()
    if not token or not chat_id:
        print("Falta POS_UNIFORMES_TELEGRAM_BOT_TOKEN o POS_UNIFORMES_TELEGRAM_CHAT_ID en pos_uniformes.env.")
        return 1
    try:
        escuchar(session_factory=get_session, token=token, chat_id=chat_id)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
