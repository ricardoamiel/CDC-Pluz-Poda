# Prototipo de priorización de poda. Piloto de Los Olivos

Primer prototipo de la herramienta que la Subgerencia MT/BT de Pluz Energía pidió en la
reunión N°2: un mapa de calor interactivo del índice de criticidad por interferencia de
vegetación, con el plan de poda priorizado del trimestre.

Proyecto del curso DS5045, Ciencia de Datos Computacionales. Pluz Energía y UTEC.

## Qué hace

- Muestra el índice de criticidad de 0 a 100 sobre el distrito de Los Olivos.
- Conmuta entre dos niveles de lectura, **alimentador** y **subestación**, con los mismos
  componentes y los mismos pesos, porque corresponden a dos decisiones distintas: el
  alimentador es la unidad de programación y la subestación es la unidad de despacho.
- Ajusta el tamaño del plan con un control, de modo que la capacidad se puede discutir en
  la propia reunión y el mapa, la lista y el resumen se recalculan a la vez.
- Muestra una ficha compacta por unidad, con el índice, la descomposición en sus cuatro
  componentes y las razones principales que entregó el modelo.
- Descarga el plan seleccionado en CSV, listo para la programación.

## Cómo se abre

Basta con abrir `index.html` en el navegador. La página no hace peticiones de red: los
datos se cargan con una etiqueta de script y la biblioteca D3 está incluida en el
repositorio, de modo que funciona igual desde el disco, desde un servidor local o
publicada.

Para servirla en local:

```
python3 -m http.server 8000
```

y luego abrir `http://localhost:8000/`.

## Cómo se publica en GitHub Pages

1. Subir el contenido de esta carpeta a la raíz de un repositorio, o a la carpeta `docs`.
2. En `Settings`, `Pages`, elegir la rama y la carpeta correspondiente.
3. El archivo `.nojekyll` ya está incluido para que las rutas se sirvan tal cual.

No hace falta ningún paso de compilación ni ningún servidor de aplicación.

## Estructura

```
index.html                          estructura de la página
css/estilos.css                     estilos, con tema claro y oscuro
js/app.js                           lógica del mapa, la lista y las fichas
js/vendor/d3.v7.9.0.min.js          biblioteca D3 versión 7
data/criticidad_los_olivos.js       datos que carga la página
data/criticidad_los_olivos.json     los mismos datos, para reutilizarlos
```

Los datos los genera el cuaderno `Modelado_Fase4_PLUZ_Vegetacion.ipynb` de la carpeta
superior. Para actualizar el prototipo con un corte nuevo basta con volver a ejecutar el
cuaderno: reescribe los dos archivos de la carpeta `data` y la página no cambia.

## Decisiones técnicas

**Proyección.** Las coordenadas llegan en grados decimales sobre WGS 84. Se proyectan con
una Mercator transversa rotada al meridiano central del distrito, que es la misma familia
de proyección que la zona UTM 18 sur en la que trabaja la empresa. Es conforme, conserva
las formas locales y a escala de distrito la distorsión es despreciable. Tratar las
coordenadas geográficas como si fueran cartesianas habría estirado el mapa en latitud.

**Mapa de calor.** Las fuentes entregadas no incluyen un polígono de límites del distrito,
solo puntos de subestación. El mapa construye un teselado de Voronoi sobre las
subestaciones aéreas y lo recorta contra la envolvente convexa del catastro, de modo que
cada celda es el área de influencia de una subestación. En la vista por alimentador las
celdas de un mismo alimentador comparten color y se leen como un territorio.

**Color.** El índice es una magnitud continua, así que se codifica con una rampa de un
solo tono de claro a oscuro, monótona en luminancia. La identidad nunca depende solo del
color: la lista ordenada repite la misma información en texto y funciona como la vista de
tabla del mapa. La página respeta el tema del sistema y permite conmutarlo.

**Responsive.** El mapa se redibuja al cambiar el tamaño de la ventana y el tablero pasa a
una sola columna por debajo de 900 píxeles de ancho.

## Alcance

Es una herramienta de soporte a la decisión sobre el corte de datos de agosto de 2026. No
autoriza trabajos ni reemplaza la inspección en campo. Las subestaciones compactas y
subterráneas se dibujan en gris porque no están expuestas a interferencia de vegetación.
El índice no está validado contra resultados: sus pesos son una propuesta con análisis de
sensibilidad, y esa validación es el objetivo del testeo de la reunión N°4.
