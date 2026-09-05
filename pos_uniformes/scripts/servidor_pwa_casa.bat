@echo off
rem =====================================================
rem  SERVIDOR PWA - corre en la PC de la CASA.
rem  Lee el snapshot SQLite que manda la tienda y sirve
rem  la Libreta movil en el puerto 8000 (via Tailscale).
rem  Requisitos (una vez): git clone del repo + venv con
rem  requirements.txt + Tailscale + compartir C:\pos_movil.
rem =====================================================
setlocal
cd /d "%~dp0.."

if not exist C:\pos_movil mkdir C:\pos_movil
set POS_UNIFORMES_DB_URL=sqlite:///C:/pos_movil/snapshot_movil.sqlite

if not exist C:\pos_movil\snapshot_movil.sqlite (
    echo Aun no llega ningun snapshot de la tienda.
    echo En la PC principal corre: scripts\enviar_snapshot_casa.bat
    echo Este servidor arrancara de todas formas y esperara.
)

echo Servidor PWA en http://localhost:8000  (celulares: por Tailscale)
.\.venv\Scripts\python.exe -m uvicorn pos_uniformes.api.main:app --host 0.0.0.0 --port 8000
