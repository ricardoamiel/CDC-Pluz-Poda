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

**Las variables del modelo.** Historial acumulado de vegetación, eventos de vegetación de los últimos doce meses, meses desde la última poda, interrupciones totales de los últimos doce meses y estacionalidad. El SAIDI y el número de clientes no entran, por el acuerdo de la reunión N°3: ya están en el índice como componentes propios y se contarían dos veces.

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


## Arquitectura propuesta para la operación

### El punto de partida

Antes de elegir herramientas conviene fijar tres hechos, porque son los que deciden:

1. **El volumen es pequeño.** Unas 200 interrupciones al mes, unos cuantos cientos de podas al mes y una guía de unas 14.000 subestaciones. Todo el histórico cabe en menos de 20 MB. Cualquier base de datos lo maneja sin esfuerzo, y el cálculo completo tarda segundos en un computador de oficina.
2. **La frecuencia es semanal.** No hace falta procesar en tiempo real: un proceso por lotes, una vez por semana, es la arquitectura que corresponde.
3. **El equipo de Pluz trabaja en Excel.** La solución tiene que respetar esa forma de trabajo: el área entrega un Excel y recibe un Excel y una página, sin aprender una herramienta nueva.

### Opciones evaluadas

* **Access.** Descartado. Tiene un límite de 2 GB por archivo, funciona mal con varios usuarios a la vez, solo corre en Windows, no maneja coordenadas y Microsoft ya no lo desarrolla como plataforma de datos. Además, nuestro equipo no lo usa, de modo que no podríamos dejarlo listo ni darle soporte.
* **Seguir solo con Excel y carpetas.** Es lo que funciona hoy y sirve para el piloto, pero no guarda historial: cada lote reemplaza al anterior, y no se puede comprobar después si el plan de un trimestre acertó.
* **Base de datos en sus propias instalaciones con PostgreSQL.** Es la opción recomendada, y se detalla abajo.
* **Nube con AWS.** Técnicamente impecable, pero sobredimensionada para este volumen en esta etapa. Se detalla abajo como fase posterior.
* **Orquestadores como Airflow, o plataformas como Databricks.** Descartados. Resuelven problemas de cientos de procesos y terabytes, y aquí hay un proceso semanal de megabytes; su costo de operación superaría al del problema.

### Recomendación: lotes semanales en las instalaciones de Pluz

Cuatro piezas, todas gratuitas o ya disponibles en una empresa como Pluz:

1. **Entrada.** Una carpeta compartida, en OneDrive o SharePoint si usan Microsoft 365, o en una unidad de red. El área deja ahí el Excel semanal, igual que hoy lo envía por correo. Es lo único que cambia para ellos.
2. **Proceso.** Este mismo pipeline, instalado en un servidor o en un computador de la Subgerencia, programado con el Programador de tareas de Windows para correr cada lunes. No hay que reescribir nada: la orden programada es python pipeline/actualizar.py.
3. **Almacenamiento.** PostgreSQL, con la extensión PostGIS para las coordenadas de las subestaciones. Se elige por cinco razones: es gratuito y de código abierto; es un estándar que cualquier área de sistemas sabe administrar; guarda el historial de predicciones, que es lo que permitirá medir si el plan acertó; varias personas pueden consultarlo a la vez; y se conecta directamente con Excel y con Power BI. Si el área de sistemas de Pluz ya trabaja con Microsoft, SQL Server Express es una alternativa equivalente y también gratuita hasta 10 GB: el pipeline escribe en cualquiera de las dos cambiando solo la dirección de conexión.
4. **Consumo.** Tres salidas para tres usos: la página, para la reunión y la decisión; el libro de Excel del plan, para la programación de cuadrillas; y Excel o Power BI conectados a la base de datos, desde Datos, Obtener datos, Desde una base de datos, para quien quiera cruzar la información con sus propias planillas.

Sobre la publicación de la página: hoy vive en GitHub Pages, que es público y sirve para el prototipo. En operación debería servirse dentro de la red de Pluz, porque los datos que dibuja incluyen direcciones de subestaciones y número de clientes. Como es una página estática, basta con copiar la carpeta a un servidor web interno o a un sitio de SharePoint; no necesita servidor de aplicaciones.

### Lo que dejamos listo y lo que pone Pluz

Queda listo en este repositorio:

* El pipeline completo, con validación del lote, medición del modelo antes de publicar y reporte de cada corrida.
* El plan en Excel, en pipeline/salidas/plan_de_poda_AAAAMM.xlsx, con una hoja de resumen y el plan de cada distrito en los dos niveles.
* La escritura en base de datos, ya probada con SQLite, que es una base de datos en un solo archivo y no requiere instalar nada. Sirve como primer paso antes de tener un servidor.
* Esta documentación.

Le corresponde a Pluz:

* Un computador o servidor donde corra el proceso, y la carpeta compartida de entrada.
* La instalación de PostgreSQL o SQL Server, normalmente a cargo de su área de sistemas.
* La decisión de dónde se sirve la página dentro de su red.

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

Las tablas que escribe son de dos tipos:

* **Se reemplazan en cada corrida**, porque son la versión consolidada vigente: interrupciones, poda, guia_sed, ranking_saidi y base_analitica.
* **Se acumulan con la fecha de la corrida**, porque son el historial con el que se medirá si el plan acertó: historial_predicciones, historial_indice_alimentador, historial_indice_subestacion y corridas.

### Cuándo pasar a la nube

AWS, o Azure si Pluz trabaja con Microsoft, tiene sentido en una fase posterior, cuando se cumpla alguna de estas condiciones: que la herramienta se extienda a toda la concesión con datos diarios, que varias áreas la consuman, o que el área de sistemas de Pluz ya tenga un acuerdo de nube y prefiera no mantener servidores propios.

El diseño en AWS sería el mismo flujo con piezas administradas: el Excel se deja en un depósito de Amazon S3; su llegada dispara el pipeline, empaquetado en un contenedor que corre en AWS Fargate o en AWS Lambda; los resultados se guardan en Amazon RDS para PostgreSQL; y la página se sirve desde S3 con Amazon CloudFront y acceso restringido con Amazon Cognito. El costo es bajo pero recurrente, y lo domina la base de datos administrada. El paso es directo porque el pipeline ya está escrito para ese flujo: solo cambian la carpeta de entrada y la dirección de la base de datos.


## Límites conocidos

* La poda de Norte Chico que llegó en setiembre tiene otro formato, por SET y circuito y sin alimentador, y todavía no entra. Por eso Norte Chico no está en la comparación.
* No hay un dato de cuánta vegetación tiene cada distrito. La comparación lo aproxima con los cortes por vegetación por cada 100 subestaciones aéreas.
* El modelo sigue en paridad con la regla por historial. Lo que aporta es una probabilidad calibrada que el índice puede sumar. Bajar de alimentador a tramo exige el maestro de estructuras.
