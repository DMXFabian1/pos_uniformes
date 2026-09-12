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


def _escribir_env(nombre: str, valor: str) -> None:
    """Agrega o reemplaza NOMBRE=valor en el pos_uniformes.env de esta máquina."""
    from pathlib import Path

    from pos_uniformes.utils.config import _appdata_config_dir, runtime_base_dir

    base = _appdata_config_dir() or runtime_base_dir()
    ruta = base / "pos_uniformes.env"
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    nuevas = [l for l in lineas if not l.strip().startswith(f"{nombre}=")]
    nuevas.append(f"{nombre}={valor}")
    ruta.write_text("\n".join(nuevas) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resumen diario del negocio por Telegram")
    parser.add_argument("--imprimir", action="store_true", help="mostrar en pantalla sin enviar")
    parser.add_argument("--chat-ids", action="store_true", help="listar chats que le han escrito al bot")
    parser.add_argument("--guardar-chat", action="store_true", help="con --chat-ids: escribe el chat id en pos_uniformes.env si es uno solo")
    parser.add_argument("--guardar-token", default="", help="escribe el token en pos_uniformes.env y sale")
    parser.add_argument("--fecha", default="", help="AAAA-MM-DD (default: hoy)")
    parser.add_argument("--pendientes", action="store_true", help="solo el recordatorio de pendientes (mediodía)")
    parser.add_argument("--asistencia", action="store_true", help="solo la lista de asistencia (media mañana)")
    parser.add_argument(
        "--si-toca",
        action="store_true",
        help="solo enviar si es la hora del resumen de hoy (cierre − 15 min); para programarlo a 16:45 y 17:45",
    )
    args = parser.parse_args(argv)

    if args.si_toca:
        from datetime import datetime

        from pos_uniformes.services.horario_tienda_service import es_momento_de_resumen, hora_resumen

        ahora = datetime.now()
        if not es_momento_de_resumen(ahora):
            print(f"No es la hora del resumen de hoy ({hora_resumen(ahora.date()):%H:%M}); no se envía.")
            return 0

    from pos_uniformes.services import telegram_service

    if args.guardar_token:
        _escribir_env("POS_UNIFORMES_TELEGRAM_BOT_TOKEN", args.guardar_token.strip())
        print("Token guardado en pos_uniformes.env.")
        return 0

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
        if args.guardar_chat:
            if len(chats) != 1:
                print("Hay más de un chat: copia a mano el tuyo al pos_uniformes.env.")
                return 1
            _escribir_env("POS_UNIFORMES_TELEGRAM_CHAT_ID", chats[0][0])
            print(f"Chat id guardado en pos_uniformes.env ({chats[0][1]}).")
        return 0

    hoy = date.fromisoformat(args.fecha) if args.fecha else date.today()
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.resumen_diario_service import formatear, recolectar

    with get_session() as session:
        if args.pendientes:
            from pos_uniformes.services.resumen_diario_service import texto_solo_pendientes

            texto = texto_solo_pendientes(session, hoy)
            if not texto:
                print("Sin pendientes: no se envía nada.")
                return 0
        elif args.asistencia:
            from pos_uniformes.services.asistencia_service import asistencia_del_dia, texto_asistencia

            # La tienda abre todos los días (horario_tienda_service).
            texto = texto_asistencia(asistencia_del_dia(session, hoy), hoy)
        else:
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
