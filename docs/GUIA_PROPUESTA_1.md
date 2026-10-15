# Guía de la propuesta 1: operación en las instalaciones de Pluz

Paso a paso para instalar la herramienta en un computador o servidor de Pluz y dejarla actualizándose cada semana con el Excel que envía el área. El diseño y su justificación están en ARQUITECTURA.md; esta guía es la parte práctica.

Todo lo que se corre es Python, con una sola orden de entrada: pipeline/actualizar.py. No hay que escribir código.


## 1. Qué se necesita

* **Un computador o servidor con Windows** que esté encendido los lunes por la mañana. Puede ser el de un analista de la Subgerencia. También funciona en Linux o macOS.
* **Python 3.11 o superior**, descargado de python.org. Al instalarlo hay que marcar la casilla Add python.exe to PATH.
* **Una carpeta compartida de entrada**, en OneDrive, SharePoint sincronizado o una unidad de red, donde el área deja el Excel de cada semana. En esta guía se usa C:\Pluz\entrada como ejemplo.
* **Opcional:** una carpeta que publique el servidor web interno, por ejemplo C:\inetpub\wwwroot\pluz en IIS.
* **Opcional, y en general innecesario:** un servidor PostgreSQL o SQL Server. Con este volumen, menos de 20 MB en todo el histórico, Excel alcanza: cada corrida deja el plan en un libro de Excel que Power BI puede leer directamente. Una base de datos solo suma si se quiere el historial de predicciones en un solo lugar o varias personas consultando a la vez; el pipeline ya sabe escribir en ella y se activa con una variable.


## 2. Instalación, una sola vez

1. **Copiar el repositorio al equipo.** Desde GitHub, botón Code y luego Download ZIP, y descomprimirlo en una carpeta fija, por ejemplo C:\Pluz\herramienta. Si el equipo tiene git, también se puede clonar.
2. **Abrir una consola en esa carpeta.** En el Explorador de archivos, entrar a C:\Pluz\herramienta, escribir cmd en la barra de direcciones y pulsar Enter.
3. **Instalar las bibliotecas:**
   ```
   python pipeline/actualizar.py instalar
   ```
   Si se va a usar PostgreSQL, además:
   ```
   python pipeline/actualizar.py instalar base
   ```
4. **Copiar los datos históricos.** Crear la carpeta pipeline\datos\lotes y, dentro, una carpeta por cada entrega recibida hasta hoy, con un nombre que empiece por la fecha en formato AAAAMMDD, por ejemplo 20260831_v1 y 20260930_v2. Copiar ahí los Excel tal como llegaron.
5. **Configurar las carpetas.** Abrir con el Bloc de notas el archivo pipeline\programar\actualizar_semanal.bat y cambiar las dos rutas del principio por las reales:
   ```
   set "PLUZ_CARPETA_ENTRADA=C:\Pluz\entrada"
   set "PLUZ_CARPETA_WEB=C:\inetpub\wwwroot\pluz"
   ```
   Si no hay servidor web interno, dejar la segunda ruta como está: la página igual queda actualizada en la carpeta de la herramienta y se puede abrir con la orden ver. Si se usa base de datos, quitar el REM de la línea de PLUZ_BASE_DE_DATOS y poner la dirección real.
6. **Validar los datos:**
   ```
   python pipeline/actualizar.py validar
   ```
   Debe terminar con el mensaje Los lotes cumplen el contrato de datos. Si falta un archivo o una columna, lo dice con el nombre exacto.
7. **Primera corrida:**
   ```
   python pipeline/actualizar.py
   ```
   La primera vez entrena el modelo vigente, lo mide fuera de muestra frente a la regla por historial y lo guarda. Las corridas siguientes ya no entrenan: lo usan y lo monitorean.
8. **Revisar el resultado:**
   ```
   python pipeline/actualizar.py ver
   ```
   Abre la página en el navegador, servida desde el propio equipo. Se cierra con Ctrl y C en la consola.


## 3. La corrida de cada semana

Hay dos formas de hacerla, y las dos corren exactamente lo mismo. Mientras no haya un equipo encendido todos los lunes, la opción manual es suficiente.

### Opción A: manual, cada lunes a las 10:00

1. El área deja el Excel de la semana en C:\Pluz\entrada, con los nombres de siempre.
2. El lunes a las 10:00, la persona responsable hace doble clic en pipeline\programar\actualizar_semanal.bat.
3. Se abre una ventana que dice Corriendo el pipeline semanal y, al terminar, Corrida terminada. Se cierra con cualquier tecla.
4. Revisa el reporte en pipeline\salidas\reporte.md.

### Opción B: automática, con el Programador de tareas de Windows

1. Abrir el Programador de tareas desde el menú de inicio.
2. En el panel derecho, elegir Crear tarea básica.
3. **Nombre:** Pluz actualización semanal.
4. **Desencadenador:** Semanalmente, lunes, 10:00.
5. **Acción:** Iniciar un programa.
6. **Programa o script:** la ruta completa del archivo, por ejemplo C:\Pluz\herramienta\pipeline\programar\actualizar_semanal.bat.
7. **Agregar argumentos:** escribir auto. Así la ventana no se queda esperando una tecla.
8. **Iniciar en:** C:\Pluz\herramienta.
9. Finalizar. En las propiedades de la tarea conviene marcar Ejecutar tanto si el usuario inició sesión como si no, para que corra aunque nadie haya entrado al equipo.

La misma tarea se puede crear desde una consola de Windows con una sola orden:

```
schtasks /create /tn "Pluz actualizacion semanal" /tr "C:\Pluz\herramienta\pipeline\programar\actualizar_semanal.bat auto" /sc weekly /d MON /st 10:00
```

En Linux o macOS se usa pipeline/programar/actualizar_semanal.sh con cron; la línea exacta está escrita al principio de ese archivo.

### Qué hace la corrida, paso a paso

El archivo actualizar_semanal.bat ejecuta python pipeline/actualizar.py semanal, que hace esto:

1. **Recibe el lote.** Copia los Excel y CSV de la carpeta de entrada a una carpeta nueva dentro de pipeline\datos\lotes, con la fecha del día, por ejemplo 20261019_semanal, y mueve los originales a entrada\procesados. Si esa semana no llegó nada, sigue con los lotes que ya existen.
2. **Valida el lote.** Revisa que cada archivo traiga sus columnas. Si algo falta, se detiene y no toca la página.
3. **Arma la base analítica**, una fila por alimentador y mes.
4. **Usa y monitorea el modelo vigente.** Predice los tres meses siguientes al último mes con datos. En los meses que ya tienen resultado y que el modelo no vio, compara su ordenamiento con la regla por historial y su probabilidad con la frecuencia observada. Si la probabilidad se descalibró, la recalibra sin cambiar el orden del ranking. Si el ordenamiento cayó, lo avisa.
5. **Calcula el índice de criticidad** de los ocho distritos y escribe la carpeta data.
6. **Deja las salidas:** el plan en Excel, el reporte, el registro en MLflow y, si está configurada, la base de datos.
7. **Copia la página** a la carpeta del servidor web interno.

Cada corrida deja un registro completo en pipeline\salidas\registros, con la fecha y la hora en el nombre.


## 4. Qué revisar después de cada corrida

* **El reporte**, en pipeline\salidas\reporte.md. Dice qué archivos se usaron, si hubo avisos, el estado del modelo vigente y el monitoreo.
* **El plan en Excel**, en pipeline\salidas\plan_de_poda_AAAAMM.xlsx, con una hoja de resumen y el plan de cada distrito por alimentador y por subestación. Es el archivo que se pasa a programación de cuadrillas.
* **La página**, en el servidor interno o con la orden ver.
* **El monitoreo en el tiempo**, con:
  ```
  python pipeline/actualizar.py mlflow
  ```
  En el experimento pluz_modelo_vigente se grafican, semana a semana, la PR AUC del modelo frente a la regla y la razón entre frecuencia observada y probabilidad media.


## 5. Cuándo hay que intervenir

* **El reporte dice que el lote no cumple el contrato.** Pluz cambió el nombre de un archivo o de una columna. Se corrige en FUENTES, dentro de pipeline\config.py, y se vuelve a correr.
* **El reporte recomienda reentrenar.** El modelo dejó de ordenar tan bien como la regla por historial en los meses nuevos. Primero se revisa si cambió algo en los datos; después se corre:
  ```
  python pipeline/actualizar.py reentrenar
  ```
  El modelo nuevo solo se guarda si pasa la medición fuera de muestra frente a la regla.
* **Una corrida terminó con error.** El detalle está en el último archivo de pipeline\salidas\registros.
* **Se quiere comparar modelos otra vez**, por ejemplo después de reentrenar:
  ```
  python pipeline/actualizar.py benchmark
  ```


## 6. Demostración del flujo en Ubuntu, con datos reales

Para mostrar el flujo sin tocar la operación real hay un modo demostración. Vive en pipeline/datos/demo, con sus propios lotes, salidas, modelo y página, y se borra con una orden. No usa datos inventados: es una repetición con los datos reales. El estado inicial tiene las interrupciones solo hasta julio de 2026, y las de agosto se reparten en tres Excel semanales, del 1 al 7, del 8 al 14 y del 15 al 20, que se entregan uno por uno como lo haría Pluz. En Ubuntu el lunes a las 10:00 se representa corriendo a mano el archivo de la tarea.

Todo se corre desde la raíz del repositorio.

1. **Armar la demostración:**
   ```
   python3 pipeline/demo/preparar_demo.py
   ```
2. **Entrar en modo demostración** en esa consola. Desde aquí, todo trabaja dentro de pipeline/datos/demo:
   ```
   export PLUZ_DEMO=$PWD/pipeline/datos/demo
   ```
3. **Estado inicial.** Corrida completa con los datos hasta julio: entrena el modelo vigente y deja el corte en julio de 2026.
   ```
   python3 pipeline/actualizar.py
   python3 pipeline/actualizar.py ver
   ```
   En la página se ve la ventana de agosto a octubre de 2026. La orden ver se cierra con Ctrl y C.
4. **Pluz entrega la primera semana.** Este paso deja el Excel en la carpeta de entrada, pipeline/datos/demo/entrada:
   ```
   python3 pipeline/demo/preparar_demo.py siguiente
   ```
5. **Lunes a las 10:00.** Se corre a mano el archivo de la tarea, el mismo que en producción programaría cron:
   ```
   ./pipeline/programar/actualizar_semanal.sh
   ```
   La consola muestra el lote nuevo, el corte que pasa a agosto de 2026 y el monitoreo del modelo vigente en el primer mes que ya tiene su resultado. El Excel original queda en entrada/procesados y el registro completo en pipeline/datos/demo/salidas/registros.
6. **Ver el cambio:**
   ```
   python3 pipeline/actualizar.py ver
   python3 pipeline/actualizar.py mlflow
   ```
   La página muestra ahora la ventana de setiembre a noviembre de 2026 y el plan recalculado. En MLflow, el experimento pluz_modelo_vigente tiene una corrida por cada semana, con las métricas de monitoreo.
7. **Semanas 2 y 3.** Repetir los pasos 4 y 5. El corte sigue en agosto, porque las semanas siguientes completan ese mismo mes, y el monitoreo se actualiza a medida que llegan los datos.
8. **Salir y borrar.** Al terminar, la demostración se borra y todo queda como estaba: los datos reales, el modelo vigente y la página publicada nunca se tocaron.
   ```
   unset PLUZ_DEMO
   python3 pipeline/demo/preparar_demo.py borrar
   ```


## 7. Resumen de órdenes

* **semanal.** Lo que corre cada lunes: recibir, actualizar y copiar la página.
* **recibir.** Solo arma el lote nuevo con lo que haya en la carpeta de entrada.
* **validar.** Solo revisa que los lotes cumplan el contrato de datos.
* **Sin orden.** Corrida completa con los lotes que ya existen.
* **reentrenar.** Entrena un modelo vigente nuevo, si pasa la medición.
* **ver.** Abre la página en local.
* **mlflow.** Abre el seguimiento del modelo y del benchmark.
* **benchmark.** Compara modelos y genera el reporte interactivo.
* **subir.** Publica la carpeta data en GitHub, solo para la versión del curso.
* **instalar.** Instala las bibliotecas.
