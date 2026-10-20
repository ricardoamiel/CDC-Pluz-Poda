# Feedback de la reunión N°3 y su estado

Lista de todo lo que Pluz y el asesor pidieron desde la reunión N°3 de presentación del primer prototipo, con lo que se hizo y dónde verlo. La marca [x] es resuelto; [~] es resuelto en parte, con la razón; [ ] es pendiente.

Fecha de esta revisión: 20261019.


## Documento de sugerencias de Pluz (8 puntos y 2 recomendaciones)

* [x] **Punto 1. Interrupciones de la etiqueta solo por Vegetación y No ubicada.** Antes la etiqueta mostraba las interrupciones por todas las causas. Ahora el tooltip, el cuarto indicador y el detalle dicen Interrupciones por vegetación y no ubicadas, último año. El detalle separa las de árbol (crecimiento o tala) de las no ubicadas en red aérea y muestra aparte las de todas las causas, para que no se confundan.
* [x] **Punto 2. Indicadores del elemento buscado.** Al buscar una subestación, un alimentador, una dirección o un poste, los cuatro indicadores pasan a describir solo lo encontrado: su puesto, sus clientes, el SAIDI y las interrupciones por vegetación de su alimentador. Las tarjetas se marcan en azul mientras hay una búsqueda. Sin búsqueda vuelven a describir el plan.
* [x] **Punto 3. Llegar a la calle desde el mapa.** El mapa se acerca con botones, con Ctrl y la rueda o con dos dedos, y tiene dos fondos: el coroplético de siempre y uno satelital con las vías y sus nombres (imágenes de Esri, las mismas del mapa del proyecto Frank Arnott). Al buscar una unidad el mapa va a su calle, y el detalle tiene los botones Ver en el mapa y Ver calles en vista satelital, con la coordenada escrita para pasarla a la cuadrilla. El plan descargado trae la latitud y la longitud de cada subestación.
* [x] **Punto 4. Detalle antes de la curva y nombre ejecutivo.** El detalle de la unidad seleccionada va ahora antes que la curva, y la curva se llama Escenario de ampliación del plan.
* [x] **Punto 5. Base de postes de media tensión.** Se cargó como una fuente más del contrato de datos (49.563 postes, 1.090 en Los Olivos). La base no trae alimentador ni subestación, así que cada poste se asigna a la subestación aérea más cercana dentro de 400 m. En el mapa los postes aparecen al acercar, los de la unidad elegida se resaltan, y el buscador encuentra un poste por su código y lleva el mapa a él.
  * Se probó si el número de postes por alimentador mejora el modelo: la PR AUC sube de 0,401 a 0,416, pero el intervalo de confianza de la mejora cruza el cero (de menos 0,017 a más 0,036), la exhaustividad con 270 alertas por mes baja de 82,8 % a 80,7 % y el número de postes tiene correlación de 0,78 a 0,85 con clientes y potencia, que ya están en el índice. Por eso los postes sirven para ubicar y no entran al modelo.
  * Las interrupciones no registran el poste: la columna Punto falla trae reconectadores o alimentadores. Mientras no exista ese vínculo, los postes no pueden usarse como etiqueta.
* [x] **Punto 6. Vegetación más No ubicadas agrupadas.** Confirmado en los datos: el piloto agrupa Crecimiento de árbol (165 eventos), Tala de árbol (53) y No ubicada en red aérea (1.110). Quedan fuera 6 no ubicadas en cabecera o subestación convencional, donde no hay árboles. El diccionario de causas de Pluz define No ubicada como una falla que no se encontró en la inspección, compatible con un contacto transitorio con ramas.
* [x] **Punto 7. Comparar distritos.**
  * Se quitó la frase sobre los alimentadores que llegan a varios distritos. No hacía falta solo borrarla: ahora un alimentador compartido aporta a cada distrito la parte que corresponde a sus subestaciones en él, así que ningún evento se cuenta dos veces.
  * Cortes por vegetación pasa a Interrupciones por vegetación y no ubicadas, y se agrega la fila Cantidad de mantenimientos por vegetación, con las podas registradas del último año en las subestaciones del distrito. Se separaron porque son cosas distintas: una cuenta cortes y la otra, podas.
  * Sin decimales en las cifras por cada 100 subestaciones ni en la aproximación de cuánta vegetación hay.
  * Cada distrito tiene su color en las barras: azul para Los Olivos y verde para el otro, con su leyenda.
* [x] **Punto 8. Subestaciones y postes en los mapas de la comparación.** Los dos mapas se acercan, tienen el mismo selector de fondo coroplético o satelital y, al acercar, muestran cada subestación aérea como punto y los postes de media tensión.
* [x] **Recomendación 1. Sustento de la metodología.** La carpeta papers reúne la literatura que respalda cada decisión: la unidad y el horizonte, las variables, el reloj de poda, el índice como probabilidad por consecuencia con capacidad fija, la normalización por percentil, el SAIDI, la métrica PR AUC, la validación temporal, la calibración y los modelos comparados. Ver papers/README.md.
* [~] **Recomendación 2. Estructura y calidad de los datos para escalar.** El contrato de datos de pipeline/config.py fija las fuentes, sus columnas obligatorias y cómo se combinan los lotes, y el pipeline rechaza un lote que no lo cumple. El documento para Pluz resume qué datos hacen falta y su calidad actual. Queda acordar con Pluz el vínculo entre interrupción y estructura, el inventario de vegetación y la poda fuera del piloto con su subestación.


## Primera ronda de comentarios de la reunión N°3

* [x] El SAIDI y los clientes salieron del modelo; cuentan solo en el índice.
* [x] Los indicadores de potencia instalada e índice mínimo se reemplazaron por SAIDI del último año e interrupciones.
* [x] Insignia Piloto Los Olivos en el encabezado.
* [x] Pestaña Comparar distritos con siete distritos de Lima Norte.
* [~] Cantidad de vegetación: Pluz no tiene inventario de arbolado. Se aproxima con las interrupciones por vegetación por cada 100 subestaciones aéreas y ahora también con los mantenimientos registrados.


## Segunda ronda, con el asesor

* [x] El modelo no usa ninguna de las tres variables del índice: reloj de poda, SAIDI y exposición.
* [x] Benchmark con regresión logística, Random Forest, XGBoost, LightGBM y SVM, con F1, precisión, exhaustividad, ROC AUC y PR AUC, y la justificación de falsos positivos frente a falsos negativos. Reporte interactivo en D3 publicado en la carpeta benchmark del sitio.
* [x] MLflow con una corrida por semana y un seguimiento en líneas.
* [x] Propuestas de automatización en las instalaciones de Pluz y en AWS, en ARQUITECTURA.md y en las guías paso a paso de docs.
* [x] Modelo estable, sin entrenamiento por calendario, con monitoreo semanal y recalibración solo si hace falta.


## Tercera ronda

* [x] Modelo XGBoost en la página, con selector entre el modelo vigente y el de contraste. El plan no cambia: 10 de 10 alimentadores y 73 de 76 subestaciones.
* [x] Prueba de usuario como cliente no técnico, en docs/PRUEBA_DE_USUARIO.md, y sus seis mejoras rápidas aplicadas.


## Pendiente para la siguiente etapa

* [ ] Marcar en la herramienta lo ya podado, preventivo o correctivo, para medir el avance del plan.
* [ ] Seguimiento de aciertos tres meses después de cada plan.
* [ ] Reloj de poda por subestación con el código de subestación que trae el registro de poda (84 % de los registros lo tienen).
* [ ] Vínculo entre interrupción y estructura o tramo, para bajar el modelo del alimentador al tramo.
