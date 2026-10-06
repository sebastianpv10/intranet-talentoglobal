@echo off
title Intranet TalentoGlobal SAS - Servidor Activo
echo =================================================================
echo   INTRANET CORPORATIVA TALENTOGLOBAL SAS
echo   "Conectando el talento del futuro"
echo =================================================================
echo.
echo [1] Acceso desde este Computador:
echo     --^> http://127.0.0.1:8080/
echo.
echo [2] Acceso desde tu Celular (misma red Wi-Fi):
echo     --^> http://192.168.1.111:8080/
echo.
echo Presione Ctrl + C para detener el servidor cuando termine.
echo =================================================================
echo.

start http://127.0.0.1:8080/
python manage.py runserver 0.0.0.0:8080
pause
