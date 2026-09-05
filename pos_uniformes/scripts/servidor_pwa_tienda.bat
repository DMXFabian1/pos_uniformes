@echo off
rem =====================================================
rem  SERVIDOR PWA - corre en la PC PRINCIPAL de la tienda.
rem  Base viva: consulta al segundo + encolar etiquetas a
rem  la Brother (via la cola de trabajos del satelite).
rem  Los celulares en el WiFi entran a http://192.168.0.10:8000
rem =====================================================
setlocal
cd /d "%~dp0.."
echo Servidor PWA de TIENDA en http://192.168.0.10:8000
.\.venv\Scripts\python.exe -m uvicorn pos_uniformes.api.main:app --host 0.0.0.0 --port 8000
