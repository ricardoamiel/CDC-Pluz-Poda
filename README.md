# Prototipo de priorización de poda. Piloto de Los Olivos

Herramienta que la Subgerencia MT/BT de Pluz Energía pidió en la reunión N°2: un mapa de
calor interactivo del índice de criticidad por interferencia de vegetación, con el plan de
poda priorizado del trimestre.

Proyecto del curso DS5045, Ciencia de Datos Computacionales. Pluz Energía y UTEC.

## Qué preguntas responde

El tablero está armado alrededor de las cinco preguntas que se hacen en la reunión, y cada
pieza contesta una:

| Pregunta | Pieza |
|---|---|
| ¿Dónde se concentra el riesgo en el distrito? | Mapa de criticidad |
| ¿Qué unidades entran y en qué orden? | Lista priorizada y marcas numeradas del mapa |
| ¿Cuánto rinde estirar el plan una unidad más? | Curva de índice y cobertura acumulada |
| ¿Por qué esta unidad está en este puesto? | Descomposición del índice y razones del modelo |
| ¿Cómo se lo paso a programación? | Descarga en CSV |

Las cuatro vistas no son cuatro gráficos sueltos: son cuatro lecturas del mismo estado, y
cualquiera de ellas puede escribir en él.

| Gesto | Efecto en las demás |
|---|---|
| Clic en una celda del mapa, una fila o una barra de la curva | Fija esa unidad en las cuatro vistas y lleva su fila a la vista en la lista |
| Clic en un tramo de la escala de color | Resalta ese rango de índice en mapa, lista y curva |
| Clic en el código de un alimentador (lista o detalle) | Deja solo sus subestaciones en las tres vistas |
| Arrastrar el asa azul de la curva | Cambia el tamaño del plan, igual que el control de arriba |

Los filtros no cambian el plan. El plan lo fija siempre el tamaño elegido: filtrar sirve
para mirar un subconjunto, no para redefinir el programa. Los filtros activos aparecen como
etiquetas quitables encima de los indicadores, y se borran de golpe con «Quitar todo».

## Qué hace

- Muestra el índice de criticidad de 0 a 100 sobre el distrito de Los Olivos.
- Conmuta entre dos niveles de lectura, **alimentador** y **subestación**, con los mismos
  componentes y los mismos pesos, porque corresponden a dos decisiones distintas: el
  alimentador es la unidad de programación y la subestación es la unidad de despacho.
- Ajusta el tamaño del plan con un control, de modo que la capacidad se puede discutir en
  la propia reunión y el mapa, la lista, la curva y el resumen se recalculan a la vez.
- Muestra una ficha por unidad con el índice, la descomposición en sus cuatro componentes
  contra la mediana del piloto, y las razones principales que entregó el modelo.
- Descarga el plan seleccionado en CSV, listo para la programación.

## Cómo se abre

Basta con abrir `index.html` en el navegador. La página no hace ninguna petición de red:
los datos se cargan con una etiqueta de script, la biblioteca D3 está en el repositorio,
los iconos son un sprite SVG en línea y la tipografía es la pila del sistema. Funciona
igual desde el disco, desde un servidor local o publicada.

Para servirla en local:

```
python3 -m http.server 8000
```

y luego abrir `http://localhost:8000/`.

Dos parámetros en la dirección sirven para compartir una vista concreta o para capturarla
en un informe: `?tema=claro` o `?tema=oscuro` fija el tema, y `?nivel=subestaciones` abre
directamente la vista por subestación.

## Cómo se publica en GitHub Pages

1. Subir el contenido de esta carpeta a la raíz de un repositorio, o a la carpeta `docs`.
2. En `Settings`, `Pages`, elegir la rama y la carpeta correspondiente.
3. El archivo `.nojekyll` ya está incluido para que las rutas se sirvan tal cual.

No hace falta ningún paso de compilación ni ningún servidor de aplicación. Todas las rutas
son relativas, de modo que la página funciona igual en la raíz del dominio que en un
subdirectorio de proyecto.

## Estructura

```
index.html                          estructura de la página y sprite de iconos
css/estilos.css                     estilos y paleta, con tema claro y oscuro
js/app.js                           lógica del mapa, la curva, la lista y las fichas
js/vendor/d3.v7.9.0.min.js          biblioteca D3 versión 7
data/criticidad_los_olivos.js       datos que carga la página
data/criticidad_los_olivos.json     los mismos datos, para reutilizarlos
data/geografia_los_olivos.js        límite del distrito y avenidas, de OpenStreetMap
data/geografia_los_olivos.json      la misma geografía, para reutilizarla
assets/pluz-logo.png                logotipo completo, sobre fondo transparente
assets/pluz-isotipo.png             solo el isotipo, para usos compactos
assets/favicon.png                  icono de pestaña
```

Los datos los genera el cuaderno `Modelado_Fase4_PLUZ_Vegetacion.ipynb` de la carpeta
superior. Para actualizar el prototipo con un corte nuevo basta con volver a ejecutar el
cuaderno: reescribe los dos archivos de la carpeta `data` y la página no cambia.

## Decisiones de diseño

**Color.** Los tres tonos del logotipo son el origen de toda la paleta: azul `#395AA1`,
verde `#6CAC5E` y amarillo `#FCC13F`. De ahí salen tres familias, y ninguna hace el
trabajo de otra:

- *Identidad de interfaz*, el azul corporativo: cabecera, controles, foco, selección y el
  contorno del plan sobre el mapa.
- *Magnitud*, el índice: una rampa secuencial de un solo tono nacida del amarillo
  corporativo. Siete pasos, luminancia OKLCH monótona de 0,94 a 0,55 con saltos de 0,065 y
  giro de tono de 37°, dentro del umbral de un solo tono.
- *Identidad de serie*, los cuatro componentes del índice: cuatro tonos categóricos
  tomados del logotipo más un violeta como cuarto tono. El peor par adyacente da ΔE 36,9
  simulando protanopia y deuteranopia y ΔE 40,5 con visión normal, muy por encima de los
  umbrales de 8 y 15. Los pasos del tema oscuro no son un volteo del claro: se eligieron y
  se volvieron a validar contra la superficie oscura.

El extremo claro de la rampa queda por debajo de 3:1 contra la superficie a propósito. Las
celdas del mapa se tocan entre sí, de modo que se leen unas contra otras y no contra el
papel, y además la cifra va siempre escrita al lado en la lista, en la ficha y en el
detalle. Ninguna lectura depende solo del color: la lista ordenada repite la misma
información en texto y es la vista de tabla accesible del mapa.

**Proyección.** Las coordenadas llegan en grados decimales sobre WGS 84. Se proyectan con
una Mercator transversa rotada al meridiano central del distrito, que es la misma familia
de proyección que la zona UTM 18 sur en la que trabaja la empresa. Es conforme, conserva
las formas locales y a escala de distrito la distorsión es despreciable. Tratar las
coordenadas geográficas como si fueran cartesianas habría estirado el mapa en latitud.

**Mapa de calor.** El mapa se dibuja sobre el límite administrativo real de Los Olivos,
tomado de OpenStreetMap (relación 1944759, ODbL 1.0) junto con las avenidas principales.
Ambos se simplifican con Douglas-Peucker y se guardan en `data/geografia_los_olivos.js`, de
manera que pesan 14 kB y la página sigue sin pedir nada a la red. Las 252 subestaciones
aéreas y las 244 no expuestas caen todas dentro de ese polígono, lo que valida a la vez el
contorno y las coordenadas del catastro.

Sobre ese límite se construye un teselado de Voronoi de las subestaciones aéreas, así que
cada celda es el área de influencia de una subestación. El recorte contra el distrito lo
hace un `clipPath` de SVG y no un algoritmo propio: el límite es cóncavo, y el recortador de
Sutherland y Hodgman que se usaba antes solo vale para polígonos convexos. Las avenidas van
en tinta translúcida y por debajo de todo lo que decide: no aportan ningún dato del modelo,
están para que quien conoce el distrito se ubique.

**Fronteras.** Las costuras entre celdas de un mismo alimentador se apagan y solo se
dibujan las aristas que separan alimentadores distintos, calculadas sobre la triangulación
de Delaunay. Así cada alimentador se lee como un territorio y no como un mosaico de celdas
sueltas. El contorno del plan va fino y con funda clara debajo para que se lea sobre
cualquier paso de la rampa: los alimentadores no son territorios contiguos y en las zonas
densas su frontera es de verdad un encaje, que con un trazo grueso taparía el relleno.

**Curva de capacidad.** Dos gráficos apilados sobre el mismo eje de puesto, nunca dos
escalas verticales en un mismo marco. Arriba el índice de cada unidad, que muestra dónde
se aplana la curva; abajo el porcentaje acumulado de clientes cubiertos, que es el
argumento con el que se defiende el tamaño del plan.

**Descomposición del índice.** Los cuatro componentes multiplicados por su peso suman
exactamente el índice, así que la barra apilada del detalle no es una metáfora del
cálculo: es el cálculo. Cada componente lleva además una marca con la mediana del piloto,
porque un 60 suelto no dice si es alto o bajo dentro de este distrito.

**Leyenda.** La escala de color lleva encima el histograma de la distribución y la marca
del umbral del plan, de modo que una sola pieza explica el color, muestra el reparto y
sitúa el corte.

**Etiquetas del plan.** Los Olivos es unas tres veces y media más alto que ancho, de modo
que al ajustarlo a la altura del panel sobra margen a ambos lados. Ese margen se usa para
nombrar las unidades priorizadas, y cada marca va al lado que le queda más cerca: mandarlas
todas a la derecha obligaba a las guías de la mitad izquierda a cruzar el distrito entero.

**Responsive.** El mapa se redibuja al cambiar el tamaño de la ventana, el tablero pasa a
una sola columna por debajo de 960 píxeles y el detalle por debajo de 1080. Por debajo de
540 píxeles el mapa renuncia a las etiquetas directas y ocupa todo el ancho.

## Alcance

Es una herramienta de soporte a la decisión sobre el corte de datos de agosto de 2026. No
autoriza trabajos ni reemplaza la inspección en campo. Las subestaciones compactas y
subterráneas se dibujan en gris porque no están expuestas a interferencia de vegetación.
El índice no está validado contra resultados: sus pesos son una propuesta con análisis de
sensibilidad, y esa validación es el objetivo del testeo de la reunión N°4.
