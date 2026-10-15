@echo off
REM Corrida semanal del pipeline de Pluz Energia: recibe el lote, actualiza y copia la pagina.
REM Se ejecuta con doble clic, por ejemplo los lunes a las 10:00, o desde el Programador de
REM tareas de Windows. Cada corrida deja un registro en pipeline\salidas\registros.

REM Carpetas de esta instalacion. Cambiar las rutas por las reales antes de la primera corrida.
if not defined PLUZ_CARPETA_ENTRADA set "PLUZ_CARPETA_ENTRADA=C:\Pluz\entrada"
if not defined PLUZ_CARPETA_WEB set "PLUZ_CARPETA_WEB=C:\inetpub\wwwroot\pluz"
REM Opcional: base de datos. Dejar en blanco si no se usa.
REM set "PLUZ_BASE_DE_DATOS=postgresql://usuario:clave@servidor:5432/pluz"

cd /d "%~dp0\..\.."
if not exist "pipeline\salidas\registros" mkdir "pipeline\salidas\registros"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set FECHA=%%i
set "REGISTRO=pipeline\salidas\registros\corrida_%FECHA%.log"

echo Corriendo el pipeline semanal. Registro en %REGISTRO%
python pipeline\actualizar.py semanal > "%REGISTRO%" 2>&1
if errorlevel 1 (
  echo La corrida termino con un error. Revise %REGISTRO%
) else (
  echo Corrida terminada. Reporte en pipeline\salidas\reporte.md
)
REM Si se ejecuta con doble clic, la ventana espera una tecla para que se pueda leer el resultado.
if "%1"=="" pause
