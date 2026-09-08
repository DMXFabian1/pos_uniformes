"""Manda el resumen del día por Telegram (corre solo en la PC servidor al cierre).

Uso (desde la carpeta padre del paquete, como el resto de scripts):
    python -m pos_uniformes.scripts.resumen_diario_telegram             # manda el de hoy
    python -m pos_uniformes.scripts.resumen_diario_telegram --imprimir  # solo lo muestra
    python -m pos_uniformes.scripts.resumen_diario_telegram --chat-ids  # descubre tu chat id
    python -m pos_uniformes.scripts.resumen_diario_telegram --fecha 2026-09-07

Configuración en pos_uniformes.env:
    POS_UNIFORMES_TELEGRAM_BOT_TOKEN  (de @BotFather)
    POS_UNIFORMES_TELEGRAM_CHAT_ID    (tu chat; se descubre con --chat-ids)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resumen diario del negocio por Telegram")
    parser.add_argument("--imprimir", action="store_true", help="mostrar en pantalla sin enviar")
    parser.add_argument("--chat-ids", action="store_true", help="listar chats que le han escrito al bot")
    parser.add_argument("--fecha", default="", help="AAAA-MM-DD (default: hoy)")
    args = parser.parse_args(argv)

    from pos_uniformes.services import telegram_service

    if args.chat_ids:
        try:
            chats = telegram_service.obtener_chat_ids()
        except Exception as exc:  # noqa: BLE001
            print(f"No se pudo consultar el bot: {exc}")
            return 1
        if not chats:
            print("Nadie le ha escrito al bot todavía. Mándale un 'hola' desde Telegram y vuelve a correr esto.")
            return 1
        for chat_id, nombre in chats:
            print(f"POS_UNIFORMES_TELEGRAM_CHAT_ID={chat_id}    # {nombre}")
        return 0

    hoy = date.fromisoformat(args.fecha) if args.fecha else date.today()
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.resumen_diario_service import formatear, recolectar

    with get_session() as session:
        texto = formatear(recolectar(session, hoy))
    if args.imprimir:
        print(texto)
        return 0
    try:
        n = telegram_service.enviar_mensaje(texto)
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo enviar: {exc}")
        print(texto)
        return 1
    print(f"Resumen enviado ({n} mensaje(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
