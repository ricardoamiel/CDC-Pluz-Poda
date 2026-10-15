#!/usr/bin/env bash
# Corrida semanal del pipeline de Pluz Energía, para Linux o macOS: recibe el lote, actualiza y
# copia la página. Para programarla los lunes a las 10:00 con cron, agregar con crontab esta línea:
#   0 10 * * 1 /ruta/al/repositorio/pipeline/programar/actualizar_semanal.sh
# Cada corrida deja un registro en pipeline/salidas/registros.

# Carpetas de esta instalación. Se pueden fijar aquí o exportarlas antes de correr el archivo.
# En modo demostración basta con exportar PLUZ_DEMO: la carpeta de entrada sale de ahí.
export PLUZ_CARPETA_ENTRADA="${PLUZ_CARPETA_ENTRADA:-}"
export PLUZ_CARPETA_WEB="${PLUZ_CARPETA_WEB:-}"

cd "$(dirname "$0")/../.."
carpeta_registros="${PLUZ_DEMO:+$PLUZ_DEMO/salidas/registros}"
carpeta_registros="${carpeta_registros:-pipeline/salidas/registros}"
mkdir -p "$carpeta_registros"
registro="$carpeta_registros/corrida_$(date +%Y%m%d_%H%M%S).log"
echo "Corriendo el pipeline semanal. Registro en $registro"
python3 pipeline/actualizar.py semanal > "$registro" 2>&1
codigo=$?
grep -E "Lote nuevo|No hay archivos|corte operativo|Monitoreo|Modelo vigente|recalibr|AVISO|ALTO|Página copiada|Listo" "$registro"
echo "Corrida terminada con código $codigo."
