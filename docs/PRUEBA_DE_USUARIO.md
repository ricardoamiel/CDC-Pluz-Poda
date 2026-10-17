# Prueba de usuario de la herramienta

Recorrido hecho el 16 de octubre de 2026 en el papel de un analista de programación de poda de la Subgerencia MT/BT: conoce la red y el SAIDI, trabaja en Excel, no sabe de modelos ni de ciencia de datos y abre la herramienta por primera vez desde el enlace. Sirve como insumo para el testeo con Pluz de la reunión N°4.

La prueba siguió seis tareas, las que haría esa persona en un lunes normal. Para cada una se anota qué pasó, dónde dudó y qué se propone.


## Las tareas y lo que pasó

### 1. Entender qué es la herramienta

* **Lo que funcionó.** El encabezado dice qué es, para qué piloto y qué meses cubre: plan de poda priorizado, piloto Los Olivos, ventana de setiembre a noviembre de 2026.
* **Dónde dudé.** Hay mucho en pantalla a la vez: dos pestañas, cuatro controles, una franja de modelos, cuatro indicadores, mapa, lista, curva y detalle. No queda claro por dónde empezar. La etiqueta Corte 2026 08 es lenguaje técnico.
* **Propuesta.** Una franja de tres pasos al abrir, que se pueda cerrar: mire el mapa, revise la lista del plan, descargue el plan. Cambiar el sello por algo como Datos al 20 de agosto de 2026.

### 2. Saber qué alimentadores podar este mes

* **Lo que funcionó.** Es la tarea mejor resuelta. La lista priorizada marca con una barra cuáles entran al plan, el mapa los numera y el indicador dice cuántos clientes cubren. Mover el control del tamaño del plan actualiza todo al instante.
* **Dónde dudé.** No sé qué número poner en el tamaño del plan: la herramienta propone 10 alimentadores, pero no dice de dónde sale ese número ni cuál es la capacidad real de las cuadrillas.
* **Propuesta.** Mostrar junto al control la referencia de capacidad, por ejemplo capacidad registrada en 2025: 76 subestaciones al mes.

### 3. Entender por qué un alimentador está primero

* **Lo que funcionó.** El detalle de la unidad explica el puntaje en cuatro partes con sus pesos y da las razones en palabras: alta frecuencia de interrupciones, historial de vegetación. Es lo que más confianza da.
* **Dónde dudé.** Riesgo a 3 meses 24 % no dice riesgo de qué. El SAIDI aparece sin unidad: 5,54 no sé si son horas o minutos. Índice de criticidad y percentil son palabras que no uso.
* **Propuesta.** Escribir probabilidad de al menos un corte por vegetación en los próximos tres meses. Agregar la unidad del SAIDI. Una línea de ayuda junto al índice: 100 es el alimentador más urgente del distrito.

### 4. Pasar el plan a la cuadrilla

* **Lo que funcionó.** El botón Descargar plan entrega el archivo en un clic y abre en Excel. En la vista por subestación cada fila trae la dirección.
* **Dónde dudé.** Las columnas del archivo tienen nombres de sistema, como riesgo_3_meses o saidi_alimentador_ultimo_anio. La cuadrilla necesita llegar al punto, y la dirección del catastro a veces es vaga.
* **Propuesta.** Encabezados en palabras y archivo en formato Excel. Un enlace a Google Maps por subestación, armado con sus coordenadas, en la página y en el archivo.

### 5. Comparar Los Olivos con otro distrito

* **Lo que funcionó.** Elegir el distrito es inmediato, el panel de cifras se lee bien y los dos mapas lado a lado son atractivos.
* **Dónde dudé.** Los colores de los dos mapas parecen comparables, pero no lo son: cada distrito se mide contra sí mismo. La aclaración existe, pero es un párrafo largo que no se lee. En los otros distritos no hay calles y cuesta ubicarse.
* **Propuesta.** Una etiqueta visible sobre los mapas: el color compara dentro de cada distrito, no entre distritos. Agregar las avenidas principales de cada distrito, como en Los Olivos.

### 6. El selector de modelo

* **Lo que funcionó.** La franja responde la pregunta que importa: con cualquiera de los dos modelos, el plan es el mismo.
* **Dónde dudé.** Modelo 1 Logística y Modelo 2 XGBoost no me dicen nada; me pregunto cuál debo usar y si estoy usando el equivocado.
* **Propuesta.** Para Pluz, renombrarlo modelo vigente y modelo de contraste, o llevarlo a una sección de opciones avanzadas. Para el curso, dejarlo visible tal como está.


## Lo fuerte de la herramienta

* **Se abre con un enlace**, sin instalar nada, también en el teléfono.
* **Responde la pregunta del lunes** en una pantalla: qué podar, en qué orden y a cuántos clientes protege.
* **Explica cada puesto.** Ninguna fila es una caja cerrada: siempre se puede ver de qué se compone el puntaje y por qué.
* **El mapa, la lista, la curva y el detalle están enlazados**: un clic en uno se refleja en todos.
* **El plan se ajusta a la capacidad real** moviendo un solo control, y la curva muestra cuánto rinde estirarlo.
* **Sale en Excel**, el formato con el que el área ya trabaja.
* **Es honesta con sus límites**: dice qué no está medido, como la cantidad de vegetación, y que no reemplaza la inspección en campo.


## Mejoras, por prioridad

**Rápidas, sin cambiar la lógica. Aplicadas en la semana 11:**

1. Unidad del SAIDI, en minutos, y redacción del riesgo a tres meses en indicadores, tooltip y detalle.
2. Sello Datos al 20 de agosto de 2026 en lugar de Corte 2026 08.
3. Referencia de capacidad junto al tamaño del plan.
4. Encabezados en palabras en el archivo descargado.
5. Etiqueta visible en la comparación: el color compara dentro de cada distrito.
6. Renombrar el selector de modelo para Pluz: Modelo 1 · Vigente y Modelo 2 · Contraste.

**De esfuerzo medio:**

1. Enlace a Google Maps por subestación, en la página y en el plan descargado.
2. Franja de tres pasos al abrir, que se pueda cerrar.
3. Novedades de la semana: qué unidades entraron o salieron del plan respecto de la corrida anterior.
4. Avenidas principales en los mapas de los otros distritos.

**De mayor alcance, para la siguiente etapa:**

1. Marcar en la herramienta las unidades ya podadas y si la poda fue preventiva o correctiva. Cerraría el ciclo: Pluz vería el avance del plan y el modelo ganaría la etiqueta que hoy falta para medir cuánto evita la poda.
2. Seguimiento de aciertos: tres meses después, mostrar cuántas unidades del plan tuvieron o no un corte. Es el indicador de éxito que falta acordar con Pluz.


## Preguntas para el testeo con Pluz

* ¿Qué número usan hoy para decidir cuántos alimentadores programar al mes?
* ¿El plan lo arma una persona o se discute en una reunión? ¿Desde la computadora o desde el teléfono?
* ¿Qué necesita la cuadrilla para llegar al punto: dirección, coordenadas o el código de la estructura?
* ¿Qué indicador les convencería de que la herramienta funciona: cortes evitados, minutos de SAIDI o eficiencia de la poda?
