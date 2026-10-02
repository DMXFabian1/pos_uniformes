"""Respaldo diario de la base, con aviso por Telegram si no sale.

Lo corre la tarea «POS Respaldo» todos los días. Envuelve a
`run_scheduled_backup` (que ya existía y que nadie disparaba) y agrega lo único
que faltaba para poder confiar en él estando lejos: que **hable**.

    python -m pos_uniformes.scripts.respaldo_diario
    python -m pos_uniformes.scripts.respaldo_diario --revisar   # solo mirar
    python -m pos_uniformes.scripts.respaldo_diario --sin-avisar

Qué avisa y qué no:

- Si truena, avisa en el momento. Es lo que no se puede descubrir tarde.
- Si sale después de haber fallado, lo dice una vez para cerrar el tema.
- Si sale y antes también salía, se calla. Un aviso diario de que todo está
  bien se vuelve ruido, y el ruido se ignora — que es como se pierde el aviso
  que sí importaba.
- Si el archivo pesa mucho menos de lo creíble, avisa aunque `pg_dump` haya
  dicho que todo bien. Un dump de 0 bytes es un éxito para el programa y una
  catástrofe para la tienda.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.services import respaldo_estado_service as est  # noqa: E402

RETENCION_DIAS = 14
FORMATO = "custom"  # .dump: es el que `revisar_respaldos.bat` sabe restaurar


def _avisar(texto: str, *, callar: bool = False) -> None:
    """Manda por Telegram si se puede. Nunca truena por esto."""
    if callar or not texto:
        return
    try:
        from pos_uniformes.services import telegram_service

        if telegram_service.token_configurado() and telegram_service.chat_id_configurado():
            telegram_service.enviar_mensaje(texto)
        else:
            print("(Telegram sin configurar: no se avisó)")
    except Exception as exc:  # noqa: BLE001
        print(f"(Telegram no disponible: {exc})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Respaldo diario con aviso por Telegram.")
    parser.add_argument("--revisar", action="store_true", help="solo decir cómo va, sin respaldar")
    parser.add_argument("--sin-avisar", action="store_true", help="no mandar nada por Telegram")
    parser.add_argument("--carpeta", default=None, help="dónde guardar (default: la de siempre)")
    args = parser.parse_args(argv)

    carpeta = Path(args.carpeta).expanduser().resolve() if args.carpeta else None

    if args.revisar:
        estado = est.leer_estado(carpeta)
        print(est.texto_resumen(estado))
        if not estado.al_dia:
            print()
            print(est.texto_sin_respaldo(estado))
            _avisar(est.texto_sin_respaldo(estado), callar=args.sin_avisar)
            return 1
        return 0

    # Cómo veníamos: para saber si esto es una recuperación o la rutina.
    antes = est.leer_estado(carpeta)
    venia_mal = bool(antes.error) or not antes.al_dia

    from pos_uniformes.services.backup_service import run_automatic_backup

    try:
        archivo, borrados, _status = run_automatic_backup(
            output_dir=carpeta, dump_format=FORMATO, retention_days=RETENCION_DIAS
        )
    except Exception as exc:  # noqa: BLE001 — el aviso es el punto de todo esto
        print(f"Falló el respaldo: {exc}", file=sys.stderr)
        _avisar(est.texto_fallo(str(exc)), callar=args.sin_avisar)
        return 1

    ahora = est.leer_estado(carpeta)
    print(f"Respaldo: {archivo}")
    print(est.texto_resumen(ahora))
    if borrados:
        print(f"Rotación: se borraron {len(borrados)} respaldo(s) viejos.")

    if ahora.sospechoso:
        # Salió «bien» pero el archivo no puede ser la base.
        _avisar(est.texto_sin_respaldo(ahora), callar=args.sin_avisar)
        return 1
    if ahora.error_externa:
        _avisar(
            f"⚠️ El respaldo salió, pero la copia aparte falló:\n{ahora.error_externa}",
            callar=args.sin_avisar,
        )
        return 0
    if venia_mal:
        _avisar(est.texto_volvio(ahora), callar=args.sin_avisar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
