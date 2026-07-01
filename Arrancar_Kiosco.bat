@echo off
title Kiosco AI Pro
cd /d "%~dp0"

:: Iniciar el servidor de Streamlit minimizado
start /min .venv\Scripts\streamlit.exe run app.py

:: Esperar 4 segundos para que cargue el sistema
timeout /t 4 /nobreak > NUL

:: Abrir el programa en una ventana nativa usando Brave
start "Brave" "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --app="http://localhost:8501"