# Flujo de datos: del lote de Pluz a la herramienta

Este pipeline convierte cada lote de datos que envía Pluz Energía en los archivos que dibuja la página. Con una sola orden valida el lote, reconstruye la base analítica, mide el modelo, lo reentrena, predice los tres meses siguientes, calcula el índice de criticidad de cada distrito, escribe la carpeta data y deja el plan en un libro de Excel. La página no cambia: solo cambian sus datos.

El recorrido completo es este:

1. **Lote de Pluz.** Los archivos de Excel tal como llegan.
2. **Fuentes.** Se localiza cada archivo y se valida que traiga las columnas pactadas.
3. **Base analítica.** Una fila por alimentador y mes, con sus variables y su objetivo.
4. **Modelo.** Se mide fuera de muestra, se reentrena y se predice el último mes.
5. **Índice.** Se calcula por distrito, en dos niveles, y se escribe en la carpeta data.
6. **Salidas.** Plan en Excel, reporte de la corrida y, si está configurada, la base de datos.
7. **Publicación.** La carpeta data se sube a GitHub y la página se actualiza sola.


## La rutina semanal

1. Guardar el lote en una carpeta nueva dentro de pipeline/datos/lotes, cuyo nombre empiece por la fecha de recepción en formato AAAAMMDD, por ejemplo 20261012_semana41. Los archivos se copian tal como llegan: no hace falta renombrarlos ni que el lote traiga todas las fuentes.
2. Validar el lote:
   ```
   python pipeline/actualizar.py validar
   ```
   Si falta un archivo o una columna, la orden se detiene y dice cuál y en qué lote.
3. Actualizar, que tarda unos segundos:
   ```
   python pipeline/actualizar.py
   ```
4. Revisar el reporte en pipeline/salidas/reporte.md y mirar la página en local:
   ```
   python pipeline/actualizar.py ver
   ```
5. Publicar en GitHub, previa confirmación:
   ```
   python pipeline/actualizar.py subir
   ```

La primera vez hay que instalar las bibliotecas:

```
python pipeline/actualizar.py instalar
```

Todas las órdenes disponibles:

* **validar.** Solo revisa que los lotes cumplan el contrato de datos.
* **calcular.** Corre todo, pero no toca la carpeta data.
* **forzar.** Publica aunque el modelo quede por debajo de la regla por historial.
* **ver.** Abre la página en el navegador, servida desde el propio equipo.
* **subir.** Publica la carpeta data en GitHub.
* **geografia.** Vuelve a descargar los límites de los distritos de OpenStreetMap.
* **instalar.** Instala las bibliotecas. Con instalar base agrega las de la base de datos.
* **benchmark.** Compara modelos y genera el reporte interactivo en pipeline/salidas/benchmark.
* **mlflow.** Abre MLflow con las corridas del benchmark.


## Contrato de datos

Cada fuente se reconoce por el nombre del archivo, sin distinguir mayúsculas ni tildes. Los patrones y las columnas exigidas están en pipeline/config.py, que es el único archivo que hay que tocar si Pluz cambia un nombre.

* **Interrupciones.** Un archivo cuyo nombre contenga «interrupciones» y «diarias», con la hoja Falla_Alim y las columnas Referencia, Inicio, Alimentador, Causa, Localización, SAIDI y N° Clientes. Modo histórico.
* **Poda.** Archivos cuyo nombre contenga «poda», «formato» y «unificado», con una hoja por contratista y las columnas FECHA, ALIMENTADOR, CIRCUITO y DIRECCION DE TRABAJO. Modo histórico.
* **Ranking de SAIDI.** Un archivo cuyo nombre contenga «ranking» y «saidi», con la hoja Evolutivo SAIDI y las columnas Alimentador y SAIDI LTM. Modo foto.
* **Guía de subestaciones.** Un archivo cuyo nombre empiece por «guia» o «guía», con las columnas SED, ALIM, KVA, Clientes BT Cantidad Referencial, DIRECCION, DISTRITO, TIPO DE CONSTRUCCIÓN y las dos coordenadas. Modo foto. La fila de títulos se busca sola, porque cambió entre la versión de agosto y la de setiembre.
* **Diccionario de causas.** Opcional. Si llega, se usa para avisar cuando aparece una causa que no está definida. Modo foto.

**Modo histórico.** Se juntan todos los lotes. El lote más reciente manda sobre el periodo que cubre, y los anteriores solo aportan lo que es más antiguo. Así funciona igual si Pluz envía cada semana el histórico completo o solo la semana nueva, sin duplicar eventos. Se comprobó con un lote simulado que solo traía agosto: el total se mantuvo en 6.423 interrupciones.

**Modo foto.** Solo vale el archivo más reciente, porque la guía y el ranking describen el estado actual de la red y no una serie en el tiempo.


## Qué hace cada etapa

* **Fuentes**, en etapas/fuentes.py. Entrega las tablas limpias y un registro de qué archivo de qué lote se usó.
* **Base analítica**, en etapas/base_analitica.py. Entrega una fila por alimentador y mes, con variables y objetivo.
* **Modelo**, en etapas/modelo.py. Entrega las métricas fuera de muestra, el modelo reentrenado y la probabilidad del último mes.
* **Índice**, en etapas/indice.py. Entrega el índice en dos niveles por distrito y escribe la carpeta data.
* **Salidas**, en etapas/salidas.py. Escribe el plan en Excel y, si está configurada, la base de datos.

**El corte se fija solo.** Es el último mes con interrupciones en los datos, y la ventana que se predice son los tres meses siguientes. Los textos de la página, como la ventana de setiembre a noviembre de 2026 o el periodo de enero de 2024 a agosto de 2026, salen de ahí.

**El objetivo.** Vale 1 si el alimentador registra al menos un evento de crecimiento de árbol, tala de árbol o causa no ubicada en red aérea en los tres meses siguientes. La causa no ubicada en red aérea entra por el acuerdo de la reunión N°2.

**Las variables del modelo.** Historial acumulado de vegetación, eventos de vegetación de los últimos doce meses, interrupciones totales de los últimos doce meses y estacionalidad. Por los acuerdos de la reunión N°3, el modelo no usa ninguna de las tres variables que el índice de criticidad ya cuenta por su lado: el reloj de poda, que son los meses desde la última poda; la criticidad por SAIDI; y la exposición por clientes y potencia instalada. Así no se cuenta dos veces el mismo criterio. Las interrupciones sí entran, porque Pluz las pidió como indicador principal, aunque tienen una correlación de 0,82 con el SAIDI; el benchmark lo mide en cada corrida.

**Medir antes de publicar.** En cada corrida el modelo se entrena con los meses antiguos, deja tres meses de separación y se prueba con los últimos cinco meses que ya tienen su ventana completa, contra la regla por historial, que es lo que Pluz podría hacer hoy sin modelo. Después se reentrena con todos los meses que ya tienen resultado, y ese es el modelo que predice. Si en la prueba queda más de 10 puntos de cobertura por debajo de la regla, la corrida no publica: algo cambió en los datos y alguien tiene que revisarlo antes de que llegue a la página.

**El índice.** Probabilidad con peso 0,40, reloj de poda con 0,20, criticidad por SAIDI con 0,20 y exposición por clientes y potencia con 0,20, cada componente como percentil dentro del distrito. El plan por alimentador toma un tercio de los alimentadores del distrito. El plan por subestación del piloto usa la capacidad de poda que el distrito registró en el último año completo; fuera del piloto ese registro está incompleto y se usa la misma proporción que en Los Olivos.


## Cómo leer los meses desde la última poda

El reloj de poda cuenta los meses transcurridos entre la última poda registrada del alimentador y el mes del corte. Hay dos casos que conviene no confundir:

* **Cero meses** significa que el alimentador tuvo una poda registrada en el mismo mes del corte. La página lo muestra como «podado este mes».
* **Sin poda registrada** significa que el alimentador no aparece en el registro de poda desde que ese registro empieza, en enero de 2025. No quiere decir que nunca se haya podado: puede haberse podado antes de 2025 o en un trabajo que no quedó en el formato unificado. Para el cálculo se le asigna el tope de 24 meses, que lo trata como el caso de mayor exposición, y la página lo muestra como «sin poda registrada» en lugar de mostrar ese 24 como si fuera un dato.

En los datos de la página, el campo meses_sin_poda trae el número y el campo sin_registro_poda indica el segundo caso. El plan que se descarga en CSV trae las dos columnas. Con los datos al corte de agosto de 2026, en Los Olivos hay tres alimentadores podados en el mes del corte y tres sin poda registrada.


## Qué se publica y qué no

El repositorio es público porque lo sirve GitHub Pages. Por eso el archivo .gitignore deja fuera de git la carpeta pipeline/datos, con los Excel originales de cada lote, y la carpeta pipeline/salidas, con la base analítica, la predicción, el modelo, el plan en Excel y el reporte. Sí se publican pipeline/referencia, con los límites de distritos de OpenStreetMap, y la carpeta data, que es lo que la página necesita para dibujarse.


## Cambios frecuentes

* **Pluz renombra un archivo o una columna.** Ajustar FUENTES en pipeline/config.py.
* **Agregar un distrito.** Añadirlo a DISTRITOS en pipeline/config.py con su código y el identificador de su relación en OpenStreetMap, y correr una vez la orden geografia. La pestaña de comparación lo muestra sin tocar la página.
* **Cambiar los pesos del índice o el horizonte.** PESOS y HORIZONTE_MESES en pipeline/config.py.


## Benchmark de modelos

```
python pipeline/actualizar.py benchmark
python pipeline/actualizar.py mlflow
```

La primera orden compara, con la misma partición temporal del pipeline, la regla por historial, la regresión logística vigente, la regresión logística ponderada, el refuerzo de gradiente de histograma, Random Forest, XGBoost, LightGBM y SVM. Los hiperparámetros y el umbral de cada modelo se eligen en una validación interna, separada de la prueba por tres meses, y la prueba no interviene en ninguna elección. Escribe un reporte interactivo con D3 en pipeline/salidas/benchmark/benchmark_modelos.html, que se abre sin conexión, deja una copia en la carpeta benchmark de la raíz para publicarla en GitHub Pages como segundo enlace, y registra cada modelo en MLflow. La segunda orden abre MLflow en el navegador.

El reporte incluye la tabla de métricas (ROC AUC, PR AUC, Brier, pérdida logarítmica, precisión, exhaustividad, F1, F2 y cobertura de las listas de 20, 40 y 80), las curvas ROC y de precisión y exhaustividad, la calibración, las curvas de pérdida por iteración y de aprendizaje, las matrices de confusión, la correlación entre las variables del modelo y las del índice, el aporte de cada bloque de variables y ejemplos reales de verdaderos y falsos positivos y negativos contrastados con lo que pasó.

**Qué se minimiza.** Un falso negativo es un alimentador que quedó fuera del plan y tuvo una interferencia: corte de servicio, minutos de SAIDI, clientes afectados, posibles multas y riesgo de seguridad. Un falso positivo es una visita de cuadrilla que todavía no hacía falta. Por eso se privilegia la exhaustividad, pero dentro de la capacidad de las cuadrillas: la métrica que decide es la cobertura de la lista mensual, y el umbral se elige maximizando F2.

**Regla de decisión.** Otro modelo reemplaza a la regresión logística solo si la supera en la cobertura de la lista de 40 con un intervalo que no cruza el cero al remuestrear alimentadores. En empate se queda la regresión logística, que es la más simple, está calibrada y se explica sin traducción.

**Resultado con los datos al corte de agosto de 2026.** Ningún modelo supera a la regresión logística de forma distinguible. Random Forest logra la cobertura más alta, 24,8 % frente a 23,7 %, con un intervalo que cruza el cero; XGBoost y LightGBM quedan por debajo, y SVM pierde calibración y capacidad de ordenamiento. Se mantiene la regresión logística.


## Arquitectura para la operación

Las dos propuestas, en las instalaciones de Pluz y en AWS, con sus diagramas, las mejoras sobre la propuesta inicial de AWS y la comparación entre ambas, están en ARQUITECTURA.md, en la raíz del repositorio.

### Cómo conectar la base de datos

1. Instalar las bibliotecas de conexión:
   ```
   python pipeline/actualizar.py instalar base
   ```
2. Definir la variable de entorno PLUZ_BASE_DE_DATOS con la dirección de la base. Para empezar sin servidor:
   ```
   sqlite:///pipeline/salidas/pluz.db
   ```
   Con un servidor PostgreSQL:
   ```
   postgresql://usuario:clave@servidor:5432/pluz
   ```
3. Correr la actualización como siempre. Al terminar, el pipeline informa si la base quedó actualizada.

Las tablas que se reemplazan en cada corrida son interrupciones, poda, guia_sed, ranking_saidi y base_analitica. Las que se acumulan con la fecha de la corrida, porque son el historial con el que se medirá si el plan acertó, son historial_predicciones, historial_indice_alimentador, historial_indice_subestacion y corridas.


## Límites conocidos

* La poda de Norte Chico que llegó en setiembre tiene otro formato, por SET y circuito y sin alimentador, y todavía no entra. Por eso Norte Chico no está en la comparación.
* No hay un dato de cuánta vegetación tiene cada distrito. La comparación lo aproxima con los cortes por vegetación por cada 100 subestaciones aéreas.
* El modelo sigue en paridad con la regla por historial. Lo que aporta es una probabilidad calibrada que el índice puede sumar. Bajar de alimentador a tramo exige el maestro de estructuras.
