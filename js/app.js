/* Prototipo de priorización de poda por vegetación. Piloto de Los Olivos.
   Pluz Energía y UTEC, curso DS5045.

   Decisiones de construcción que conviene conocer antes de leer el código:

   1. Proyección. Las coordenadas llegan en grados decimales sobre WGS 84. Se proyectan con
      una Mercator transversa rotada al meridiano del distrito, que es la misma familia de
      proyección que la zona UTM 18 sur en la que trabaja la empresa. Es conforme, de modo
      que los ángulos y las formas locales se conservan, y a la escala de un distrito la
      distorsión de área es despreciable. Usar coordenadas geográficas como si fueran
      cartesianas habría estirado el mapa de forma visible en latitud.
   2. Mapa de calor. El distrito no tiene un polígono de límites en las fuentes entregadas,
      solo puntos de subestación. Se construye entonces un teselado de Voronoi sobre las
      subestaciones aéreas, recortado a la envolvente convexa del catastro. Cada celda es el
      área de influencia de una subestación y se pinta según el índice de la unidad elegida.
   3. Fronteras. Las costuras entre celdas de un mismo alimentador se apagan y solo se
      dibujan las aristas que separan alimentadores distintos, de modo que cada alimentador
      se lee como un territorio y no como un mosaico de celdas sueltas. Se calculan sobre la
      triangulación de Delaunay, que ya sabe qué celdas son vecinas.
   4. Color. Cada canal hace un solo trabajo. El azul corporativo es identidad de interfaz;
      el índice, que es una magnitud continua, va en una rampa secuencial de un solo tono
      nacida del amarillo corporativo; los cuatro componentes del índice, que son identidad
      de serie, llevan cuatro tonos categóricos validados. Ninguna lectura depende solo del
      color: la lista ordenada repite la misma información en texto y es la vista de tabla
      accesible del mapa.
*/

(function () {
  "use strict";

  const DATOS = window.DATOS_PLUZ;
  const META = DATOS.meta;
  // Límite administrativo y avenidas de Los Olivos, de OpenStreetMap.
  const GEO = window.GEO_LOS_OLIVOS;

  // Un parámetro en la dirección permite abrir la página directamente en un tema, lo que
  // sirve para incrustarla o para capturarla en un informe sin depender de la
  // configuración del equipo. Sin parámetro se respeta el tema del sistema.
  const parametros = new URLSearchParams(location.search);
  const temaPedido = parametros.get("tema");
  if (temaPedido === "claro") document.documentElement.setAttribute("data-theme", "light");
  if (temaPedido === "oscuro") document.documentElement.setAttribute("data-theme", "dark");

  const RAMPA = ["--idx-1", "--idx-2", "--idx-3", "--idx-4", "--idx-5", "--idx-6", "--idx-7"];
  const COMPS = ["--comp-1", "--comp-2", "--comp-3", "--comp-4"];

  // El nivel también se puede fijar desde la dirección, de modo que en la reunión se puede
  // compartir un enlace que abra directamente la vista por subestación.
  const nivelPedido = parametros.get("nivel") === "subestaciones"
    ? "subestaciones" : "alimentadores";

  // Un único estado compartido: el mapa, la lista, la curva, la leyenda y el detalle son
  // cinco vistas del mismo objeto, y cualquiera de ellas puede escribir en él. Eso es lo
  // que hace que un clic en una se note en todas las demás.
  const estado = {
    nivel: nivelPedido,
    corte: nivelPedido === "subestaciones"
      ? Math.min(META.capacidad_mes, DATOS.subestaciones.length)
      : Math.min(META.k_alimentadores || 10, DATOS.alimentadores.length),
    busqueda: "",
    activo: null,
    fijado: null,
    // Filtros de exploración. No cambian el plan, que lo define siempre el corte: sirven
    // para resaltar un subconjunto a la vez en todas las vistas.
    tramo: null,        // índice del paso de la rampa, 0 a 6
    alimentador: null,  // código de alimentador
  };

  /* ------------------------------------------------------------------ utilidades */

  // El resto de los entregables del proyecto usa el punto como separador de miles y la
  // coma como separador decimal, así que la página hace lo mismo en lugar de confiar en
  // la configuración regional del navegador, que varía de equipo a equipo.
  const miles = (v) =>
    v === null || v === undefined
      ? "-"
      : String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const coma = (v, d = 1) =>
    v === null || v === undefined ? "-" : v.toFixed(d).replace(".", ",");
  const pct = (v) => (v === null || v === undefined ? "-" : Math.round(v * 100) + " %");

  const $ = (sel) => document.querySelector(sel);

  function leerTokens(nombres) {
    const estilo = getComputedStyle(document.querySelector(".viz-root"));
    return nombres.map((v) => estilo.getPropertyValue(v).trim() || "#cccccc");
  }
  const leerRampa = () => leerTokens(RAMPA);
  const leerToken = (n) => leerTokens([n])[0];

  const icono = (id) => `<svg class="ico" aria-hidden="true"><use href="#${id}"/></svg>`;

  // Tinta legible sobre un paso de la rampa. El extremo claro del amarillo corporativo
  // no admite texto blanco, así que la cifra grande del detalle elige su color en lugar
  // de suponerlo.
  function tintaSobre(hex) {
    const c = String(hex).trim().replace("#", "");
    if (c.length !== 6) return "#ffffff";
    const canal = (i) => {
      const v = parseInt(c.slice(i, i + 2), 16) / 255;
      return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    };
    const lum = 0.2126 * canal(0) + 0.7152 * canal(2) + 0.0722 * canal(4);
    // Compara el contraste WCAG contra blanco y contra la tinta oscura y se queda con el
    // mejor de los dos.
    return (1.05 / (lum + 0.05)) >= ((lum + 0.05) / 0.05) ? "#ffffff" : "#131a26";
  }

  /* ------------------------------------------------- índices y datos derivados */

  const porAlimentador = new Map(DATOS.alimentadores.map((d) => [d.id, d]));
  const porSubestacion = new Map(DATOS.subestaciones.map((d) => [d.id, d]));
  // Solo se dibujan las subestaciones cuyo alimentador tiene índice, para que ninguna
  // celda del mapa quede sin valor que mostrar.
  const subestacionesMapa = DATOS.subestaciones.filter((d) => porAlimentador.has(d.alimentador));

  // Los cuatro componentes en orden de peso, con el peso al lado. El índice es la suma de
  // valor × peso, así que el orden por peso es también el orden en el que se apilan.
  const CLAVE_PESO = {
    "Probabilidad del alimentador": "probabilidad",
    "Reloj de poda": "reloj_poda",
    "Criticidad por SAIDI": "criticidad",
    "Exposición": "exposicion",
  };
  const COMPONENTES = Object.values(META.nombres_componentes)
    .map((nombre) => ({ nombre, peso: META.pesos[CLAVE_PESO[nombre]] ?? 0 }))
    .sort((a, b) => b.peso - a.peso);

  // Mediana de cada componente dentro del nivel, para que el detalle pueda decir si un 60
  // es alto o bajo en este piloto en lugar de dejar la cifra sola. Se calcula una vez por
  // nivel: el detalle se redibuja en cada paso del puntero y no vale la pena recorrer las
  // 252 subestaciones cada vez.
  const cacheMedianas = new Map();
  function medianas() {
    if (cacheMedianas.has(estado.nivel)) return cacheMedianas.get(estado.nivel);
    const us = unidades();
    const m = new Map();
    for (const { nombre } of COMPONENTES) {
      m.set(nombre, d3.median(us, (d) => d.componentes[nombre]) ?? 0);
    }
    cacheMedianas.set(estado.nivel, m);
    return m;
  }

  function unidades() {
    return estado.nivel === "alimentadores" ? DATOS.alimentadores : DATOS.subestaciones;
  }

  function etiquetaNivel(plural = true) {
    if (estado.nivel === "alimentadores") return plural ? "alimentadores" : "alimentador";
    return plural ? "subestaciones" : "subestación";
  }

  // Alimentador es masculino y subestación femenino, así que el artículo tiene que
  // concordar o los rótulos generados suenan mal en cada cambio de vista.
  const articulo = (plural = true) =>
    estado.nivel === "alimentadores" ? (plural ? "los" : "el") : (plural ? "las" : "la");

  // Índice que le corresponde a una celda del mapa según el nivel elegido.
  function unidadDeCelda(sed) {
    return estado.nivel === "alimentadores" ? porAlimentador.get(sed.alimentador) : sed;
  }

  function claveDeCelda(sed) {
    return estado.nivel === "alimentadores" ? sed.alimentador : sed.id;
  }

  const seleccion = () => unidades().slice(0, estado.corte);
  const clavesSeleccionadas = () => new Set(seleccion().map((d) => d.id));

  // Alimentador al que pertenece una unidad, sea cual sea el nivel.
  const alimentadorDe = (u) =>
    estado.nivel === "alimentadores" ? u.id : u.alimentador;

  function coincide(u) {
    if (estado.tramo !== null && escalaColor(u.indice) !== escalaColor.range()[estado.tramo]) {
      return false;
    }
    if (estado.alimentador && alimentadorDe(u) !== estado.alimentador) return false;
    if (estado.busqueda) {
      const q = estado.busqueda.toLowerCase();
      if (!(u.id + " " + (u.alimentador || "") + " " + (u.direccion || ""))
          .toLowerCase().includes(q)) return false;
    }
    return true;
  }

  const hayFiltro = () =>
    estado.tramo !== null || Boolean(estado.alimentador) || Boolean(estado.busqueda);

  function limpiarFiltros() {
    estado.tramo = null;
    estado.alimentador = null;
    estado.busqueda = "";
    $("#buscar").value = "";
  }

  /* ------------------------------------------------------------------ escala */

  let escalaColor = null;

  function construirEscala() {
    const valores = unidades().map((d) => d.indice);
    escalaColor = d3.scaleQuantize()
      .domain([d3.min(valores), d3.max(valores)])
      .range(leerRampa());
  }

  const color = (v) => (v === null || v === undefined ? leerToken("--neutro-mapa") : escalaColor(v));

  /* ------------------------------------------------------------------- mapa */

  const svgMapa = d3.select("#mapa");
  // Todo lo que rellena el distrito va dentro de un grupo recortado por el límite real.
  // El contorno, las marcas y las etiquetas van fuera del recorte, porque tienen que poder
  // apoyarse en el borde o salirse de él.
  const recorteDistrito = svgMapa.append("defs").append("clipPath")
    .attr("id", "recorte-distrito").append("path");
  const capaRecortada = svgMapa.append("g").attr("clip-path", "url(#recorte-distrito)");
  const capaCeldas = capaRecortada.append("g").attr("class", "capa-celdas");
  const capaFronteras = capaRecortada.append("g").attr("class", "capa-fronteras");
  const capaPuntos = capaRecortada.append("g").attr("class", "capa-puntos");
  const capaVias = capaRecortada.append("g").attr("class", "capa-vias");
  const capaContornos = svgMapa.append("g").attr("class", "capa-contornos");
  const capaPlan = svgMapa.append("g").attr("class", "capa-plan");

  let geometria = null;

  // Ancho reservado a la derecha del mapa para las etiquetas directas de las unidades del
  // plan. El distrito de Los Olivos es muy alargado de norte a sur, de modo que al ajustarlo
  // a la altura del panel sobra espacio a los lados: ese espacio se usa para nombrar las
  // unidades priorizadas en lugar de dejarlo vacío.
  const MARGEN_ETIQUETAS = 122;

  // Cuántas unidades del plan se numeran sobre el mapa y se nombran en el margen.
  const MAX_MARCAS = 12;

  function calcularGeometria(ancho, alto) {
    const margen = 10;
    // Mercator transversa rotada al meridiano central del distrito. Equivale a trabajar
    // en la zona UTM local: conforme y con distorsión despreciable a esta escala.
    const meridiano = d3.mean(subestacionesMapa, (d) => d.lon);
    const proyeccion = d3.geoTransverseMercator().rotate([-meridiano, 0]);

    // El encuadre lo manda el distrito, no la nube de puntos: así el mapa es el mapa de
    // Los Olivos y no el del trozo que casualmente tiene subestaciones.
    const distritoGeo = { type: "Polygon", coordinates: [GEO.limite] };
    // En pantallas estrechas se renuncia a las etiquetas directas y el mapa ocupa todo el
    // ancho disponible, porque el margen que necesitarían vale más como mapa.
    const reserva = ancho > 540 ? MARGEN_ETIQUETAS : 0;
    proyeccion.fitExtent(
      [[margen + reserva, margen], [ancho - margen - reserva, alto - margen]], distritoGeo);

    const limite = GEO.limite.map((c) => proyeccion(c));
    const avenidas = GEO.avenidas.map((a) => ({
      nombre: a.nombre,
      lineas: a.lineas.map((l) => l.map((c) => proyeccion(c))),
    }));

    const puntos = subestacionesMapa.map((d) => {
      const p = proyeccion([d.lon, d.lat]);
      return { sed: d, x: p[0], y: p[1] };
    });
    const noExpuestos = DATOS.no_expuestas.map((d) => proyeccion([d.lon, d.lat]));

    // Las celdas ya no se recortan contra una envolvente convexa. El recorte contra el
    // límite real del distrito, que es cóncavo, lo hace un clipPath de SVG: el navegador
    // lo resuelve exacto y evita tener que escribir un recortador de polígonos general.
    const delaunay = d3.Delaunay.from(puntos, (p) => p.x, (p) => p.y);
    const voronoi = delaunay.voronoi([0, 0, ancho, alto]);
    const celdas = puntos.map((p, i) => ({
      indice: i,
      punto: p,
      camino: voronoi.cellPolygon(i),
    })).filter((c) => c.camino);

    // Las aristas de Voronoi sí se recortan en el guion, contra el marco del lienzo, para
    // que las semirrectas del borde no generen coordenadas disparatadas. Del marco al
    // límite del distrito se encarga después el mismo clipPath.
    const marco = [[0, 0], [ancho, 0], [ancho, alto], [0, alto]];

    const bordeDerecho = d3.max(limite, (p) => p[0]);
    const bordeIzquierdo = d3.min(limite, (p) => p[0]);
    return { proyeccion, puntos, noExpuestos, limite, avenidas, marco, celdas,
             delaunay, voronoi, ancho, alto, bordeDerecho, bordeIzquierdo, reserva };
  }

  // Punto en polígono por el método del rayo. Sirve para no anclar una marca del plan en
  // un sitio que el recorte del distrito va a dejar fuera de la vista.
  function dentroDelLimite(p, poligono) {
    let dentro = false;
    for (let i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
      const [xi, yi] = poligono[i], [xj, yj] = poligono[j];
      if ((yi > p[1]) !== (yj > p[1]) &&
          p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) dentro = !dentro;
    }
    return dentro;
  }

  // De qué lado de cada arista queda el interior depende del sentido de recorrido del
  // polígono, y ese sentido depende a su vez de que el eje vertical de la pantalla crece
  // hacia abajo. En lugar de deducirlo del signo del área, que es justo donde se cuela el
  // error, se comprueba de forma directa con el centro del propio polígono.
  function aristasOrientadas(recorte) {
    const centro = d3.polygonCentroid(recorte);
    const orientado = lado(recorte[0], recorte[1], centro) >= 0
      ? recorte
      : recorte.slice().reverse();
    return orientado.map((a, i) => [a, orientado[(i + 1) % orientado.length]]);
  }

  const lado = (a, b, p) => (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);

  // Recorte de un segmento contra un polígono convexo (aquí, el marco del lienzo):
  // basta con ir estrechando el intervalo de parámetro válido arista por arista.
  function recortarSegmento(p, q, recorte) {
    let t0 = 0, t1 = 1;
    const dx = q[0] - p[0], dy = q[1] - p[1];
    for (const [a, b] of aristasOrientadas(recorte)) {
      const nx = -(b[1] - a[1]), ny = b[0] - a[0];      // normal hacia el interior
      const den = nx * dx + ny * dy;
      const num = nx * (p[0] - a[0]) + ny * (p[1] - a[1]);
      if (den === 0) { if (num < 0) return null; continue; }
      const t = -num / den;
      if (den > 0) { if (t > t1) return null; if (t > t0) t0 = t; }
      else { if (t < t0) return null; if (t < t1) t1 = t; }
    }
    if (t1 - t0 < 1e-9) return null;
    return [[p[0] + t0 * dx, p[1] + t0 * dy], [p[0] + t1 * dx, p[1] + t1 * dy]];
  }

  // Aristas del teselado que separan dos unidades distintas. Se leen de la triangulación
  // de Delaunay: cada semiarista une dos puntos vecinos y la arista de Voronoi que les
  // corresponde va de un circuncentro al otro. Las semiaristas del borde de la
  // triangulación no tienen circuncentro opuesto: su arista de Voronoi es una semirrecta,
  // y si se descartan el territorio queda abierto justo en el perímetro del distrito, que
  // es donde más se nota. Se construyen como rayo perpendicular y se recortan igual.
  const LEJOS = 1e5;
  function fronteras(claveDe) {
    const { delaunay, voronoi, marco, puntos } = geometria;
    const { triangles, halfedges } = delaunay;
    const cc = voronoi.circumcenters;
    const salida = [];
    for (let e = 0; e < halfedges.length; e++) {
      const opuesta = halfedges[e];
      // Cada arista interior aparece dos veces; se queda solo con una.
      if (opuesta !== -1 && opuesta < e) continue;
      const i = triangles[e];
      const j = triangles[e % 3 === 2 ? e - 2 : e + 1];
      if (claveDe(i) === claveDe(j)) continue;

      const t = Math.floor(e / 3);
      const p = [cc[t * 2], cc[t * 2 + 1]];
      let q;
      if (opuesta !== -1) {
        const t2 = Math.floor(opuesta / 3);
        q = [cc[t2 * 2], cc[t2 * 2 + 1]];
      } else {
        // Semirrecta perpendicular a la arista i-j, alejándose del tercer vértice del
        // triángulo, que es el que marca hacia dónde queda el interior.
        const k = triangles[e % 3 === 0 ? e + 2 : e - 1];
        const a = puntos[i], b = puntos[j], c = puntos[k];
        let nx = -(b.y - a.y), ny = b.x - a.x;
        const largo = Math.hypot(nx, ny) || 1;
        nx /= largo; ny /= largo;
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        if (nx * (mx - c.x) + ny * (my - c.y) < 0) { nx = -nx; ny = -ny; }
        q = [p[0] + nx * LEJOS, p[1] + ny * LEJOS];
      }
      const seg = recortarSegmento(p, q, marco);
      if (seg) salida.push(seg);
    }
    return salida;
  }

  const camino = (puntos) => "M" + puntos.map((p) => p.join(",")).join("L") + "Z";
  const caminoSegmentos = (segs) =>
    segs.map(([a, b]) => `M${a[0]},${a[1]}L${b[0]},${b[1]}`).join("");

  function dibujarMapa() {
    const caja = $("#mapa-caja");
    const ancho = Math.max(280, caja.clientWidth);
    const alto = Math.round(Math.min(Math.max(ancho * 1.34, 420), 780));
    svgMapa.attr("viewBox", `0 0 ${ancho} ${alto}`)
           .attr("width", ancho).attr("height", alto);
    geometria = calcularGeometria(ancho, alto);
    recorteDistrito.attr("d", camino(geometria.limite));
    pintarMapa();
  }

  function pintarMapa() {
    if (!geometria) return;
    const seleccionadas = clavesSeleccionadas();
    // Cualquier filtro atenúa el mapa, no solo la búsqueda de texto: los tres son el
    // mismo gesto de resaltar un subconjunto.
    const filtrando = hayFiltro();
    const porIndicePunto = (i) => geometria.puntos[i].sed;

    capaCeldas.selectAll("path.celda")
      .data(geometria.celdas, (c) => c.punto.sed.id)
      .join("path")
      .attr("class", "celda")
      .attr("d", (c) => camino(c.camino))
      .attr("fill", (c) => color(unidadDeCelda(c.punto.sed).indice))
      // Las costuras internas se pintan del propio color de relleno para que las celdas de
      // una misma unidad se fundan; lo que separa territorios se dibuja aparte, en la capa
      // de fronteras, y así el mapa deja de leerse como un mosaico.
      .attr("stroke", (c) => color(unidadDeCelda(c.punto.sed).indice))
      .classed("apagada", (c) => filtrando && !coincide(unidadDeCelda(c.punto.sed)))
      .classed("resaltado", (c) => claveDeCelda(c.punto.sed) === claveActiva())
      .on("pointerenter", (evento, c) => activar(claveDeCelda(c.punto.sed), evento))
      .on("pointermove", (evento) => moverFicha(evento))
      .on("pointerleave", () => desactivar())
      .on("click", (evento, c) => fijar(claveDeCelda(c.punto.sed)))
      .append("title")
      .text((c) => {
        const u = unidadDeCelda(c.punto.sed);
        return `${u.id}. Índice ${coma(u.indice, 0)} de 100, puesto ${u.puesto}`;
      });

    // Fronteras entre alimentadores. En la vista por alimentador son la estructura
    // principal del mapa; en la vista por subestación se dejan tenues, como contexto de
    // a qué alimentador pertenece cada celda.
    capaFronteras.selectAll("path.borde-alimentador")
      .data([fronteras((i) => porIndicePunto(i).alimentador)])
      .join("path")
      .attr("class", "borde-alimentador")
      .classed("tenue", estado.nivel === "subestaciones")
      .attr("d", (segs) => caminoSegmentos(segs));

    // Contorno de lo que entra al plan: una sola línea alrededor del conjunto
    // seleccionado, que es lo que se busca de un vistazo. Se dibuja dos veces, funda y
    // línea, para que no se pierda sobre ningún paso de la rampa.
    const planSegs = fronteras((i) => {
      const u = unidadDeCelda(porIndicePunto(i));
      return seleccionadas.has(u.id) ? "dentro" : "fuera";
    });
    for (const clase of ["contorno-plan-funda", "contorno-plan"]) {
      capaFronteras.selectAll("path." + clase)
        .data([planSegs])
        .join("path")
        .attr("class", clase)
        .attr("d", (segs) => caminoSegmentos(segs));
    }

    capaPuntos.selectAll("circle.punto-no-expuesto")
      .data(geometria.noExpuestos)
      .join("circle")
      .attr("class", "punto-no-expuesto")
      .attr("cx", (p) => p[0]).attr("cy", (p) => p[1]).attr("r", 1.1);

    // Avenidas principales. No aportan ningún dato del modelo: están para que quien
    // conoce Los Olivos se ubique. Por eso van en tinta translúcida, por debajo de todo
    // lo que sí decide, y con la Panamericana algo más marcada por ser la referencia.
    capaVias.selectAll("path.via")
      .data(geometria.avenidas, (a) => a.nombre)
      .join("path")
      .attr("class", "via")
      .classed("via-troncal", (a) => a.nombre.includes("Panamericana"))
      .attr("d", (a) => a.lineas.map((l) =>
        "M" + l.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("L")).join(""))
      .append("title").text((a) => a.nombre);

    capaContornos.selectAll("path.contorno-distrito")
      .data([geometria.limite])
      .join("path")
      .attr("class", "contorno-distrito")
      .attr("d", (p) => camino(p));

    // Marca numerada sobre las unidades que entran al plan. Cada unidad se ancla en la
    // mayor de sus celdas. Ahora que las celdas se extienden hasta el marco y es el
    // recorte del distrito el que las corta, una celda del borde puede tener su centroide
    // fuera de lo que se ve: esas se descartan como ancla, y si una unidad se queda sin
    // ninguna se usa la posición de la propia subestación, que siempre está dentro.
    const mejorCelda = new Map();
    const respaldo = new Map();
    for (const celda of geometria.celdas) {
      const u = unidadDeCelda(celda.punto.sed);
      if (!seleccionadas.has(u.id)) continue;
      if (!respaldo.has(u.id)) respaldo.set(u.id, { celda, unidad: u });
      const centro = d3.polygonCentroid(celda.camino);
      if (!dentroDelLimite(centro, geometria.limite)) continue;
      const area = Math.abs(d3.polygonArea(celda.camino));
      const previa = mejorCelda.get(u.id);
      if (!previa || area > previa.area) mejorCelda.set(u.id, { celda, area, unidad: u, centro });
    }
    for (const [id, alt] of respaldo) {
      if (!mejorCelda.has(id)) {
        mejorCelda.set(id, { ...alt, area: 0, centro: [alt.celda.punto.x, alt.celda.punto.y] });
      }
    }
    // Numerar las decenas de unidades de un plan largo llena el mapa de círculos y deja de
    // informar. Se numeran solo las primeras y el resto del plan se reconoce por su
    // contorno.
    const marcas = Array.from(mejorCelda.values())
      .sort((a, b) => a.unidad.puesto - b.unidad.puesto)
      .slice(0, MAX_MARCAS)
      .map(({ unidad, centro }) =>
        ({ id: unidad.id, puesto: unidad.puesto, x: centro[0], y: centro[1] }));

    const grupos = capaPlan.selectAll("g.marca").data(marcas, (m) => m.id)
      .join((entrar) => {
        const g = entrar.append("g").attr("class", "marca");
        g.append("circle").attr("class", "marca-plan-fondo").attr("r", 9.5);
        g.append("text").attr("class", "marca-plan")
          .attr("text-anchor", "middle").attr("dy", "0.34em");
        return g;
      });
    grupos.attr("transform", (m) => `translate(${m.x},${m.y})`);
    grupos.select("text").text((m) => m.puesto);

    dibujarRotulosVias(marcas);
    dibujarEtiquetas(marcas);
  }

  // Rótulos de las avenidas. Se colocan en el punto medio del tramo más largo de cada
  // avenida y en horizontal: sobre una vía diagonal un texto girado se lee peor de lo que
  // gana, y a esta escala el rótulo se asocia igual a su línea. Se descarta el que caiga
  // encima de otro ya puesto, y en mapas estrechos no se dibuja ninguno.
  const VIAS_ROTULADAS = [
    "Avenida Panamericana Norte", "Avenida Universitaria", "Avenida Naranjal",
    "Avenida Carlos Alberto Izaguirre", "Avenida Santiago Antúnez de Mayolo",
    "Avenida Tomás Valle", "Avenida Los Alisos", "Avenida Las Palmeras",
  ];
  // Los nombres largos se comen el ancho del distrito sin añadir nada: se acortan a la
  // parte por la que la avenida se conoce.
  const NOMBRE_CORTO = {
    "Avenida Santiago Antúnez de Mayolo": "Av. Antúnez de Mayolo",
    "Avenida Carlos Alberto Izaguirre": "Av. Izaguirre",
    "Avenida Panamericana Norte": "Panamericana Norte",
  };
  const corto = (n) => NOMBRE_CORTO[n] || n.replace(/^Avenida /, "Av. ");

  // Colisión por caja y no por distancia: un rótulo es mucho más ancho que alto, de modo
  // que un radio único o dejaba pasar solapes horizontales o descartaba rótulos que en
  // realidad cabían.
  const ALTO_ROTULO = 21;
  const anchoRotulo = (texto) => texto.length * 4.9;
  function chocan(a, b) {
    return Math.abs(a.x - b.x) < (a.mitad + b.mitad) &&
           Math.abs(a.y - b.y) < ALTO_ROTULO;
  }

  function dibujarRotulosVias(obstaculos) {
    const capa = capaContornos.selectAll("g.capa-rotulos").data([0])
      .join("g").attr("class", "capa-rotulos");
    capa.selectAll("*").remove();
    if (geometria.ancho < 520) return;

    const porNombre = new Map(geometria.avenidas.map((a) => [a.nombre, a]));
    const puestos = [];
    for (const nombre of VIAS_ROTULADAS) {
      const via = porNombre.get(nombre);
      if (!via) continue;
      const linea = via.lineas.reduce((mejor, l) =>
        largoDe(l) > largoDe(mejor) ? l : mejor, via.lineas[0]);
      const p = linea[Math.floor(linea.length / 2)];
      if (!dentroDelLimite(p, geometria.limite)) continue;
      const texto = corto(nombre);
      const caja = { x: p[0], y: p[1], mitad: anchoRotulo(texto) / 2 };
      if (puestos.some((q) => chocan(caja, q))) continue;
      // Las marcas del plan mandan: son dato del modelo y el rótulo es solo contexto.
      if (obstaculos.some((m) => chocan(caja, { x: m.x, y: m.y, mitad: 13 }))) continue;
      puestos.push(caja);
      capa.append("text").attr("class", "rotulo-via")
        .attr("x", p[0]).attr("y", p[1]).attr("text-anchor", "middle")
        .text(texto);
    }
  }

  const largoDe = (l) =>
    l.reduce((t, p, i) => i ? t + Math.hypot(p[0] - l[i-1][0], p[1] - l[i-1][1]) : 0, 0);

  // Etiquetas directas de las unidades del plan, en los márgenes laterales con una línea
  // guía. Cada marca va al margen que le queda más cerca: con una silueta tan estrecha,
  // mandarlas todas a la derecha obligaba a las guías de la mitad izquierda a cruzar el
  // distrito entero. Se separan en vertical para que no se pisen, y se omiten cuando el
  // plan es tan largo que el margen no alcanza o cuando la pantalla es estrecha.
  function dibujarEtiquetas(marcas) {
    const capa = capaPlan.selectAll("g.capa-etiquetas").data([0])
      .join("g").attr("class", "capa-etiquetas");
    capa.selectAll("*").remove();
    const alturaFila = 17;
    const caben = Math.floor((geometria.alto - 20) / alturaFila);
    if (!(geometria.reserva > 0 && marcas.length <= Math.min(2 * caben, MAX_MARCAS))) return;

    const centro = (geometria.bordeIzquierdo + geometria.bordeDerecho) / 2;
    const lados = [
      { signo: -1, marcas: marcas.filter((m) => m.x < centro),
        x: Math.max(geometria.bordeIzquierdo - 26, geometria.reserva - 24) },
      { signo: +1, marcas: marcas.filter((m) => m.x >= centro),
        x: Math.min(geometria.bordeDerecho + 26, geometria.ancho - geometria.reserva + 24) },
    ];

    for (const lado of lados) {
      if (!lado.marcas.length) continue;
      const ordenadas = lado.marcas.slice().sort((a, b) => a.y - b.y);
      let anterior = -Infinity;
      for (const m of ordenadas) {
        m.yEtiqueta = Math.max(m.y, anterior + alturaFila);
        anterior = m.yEtiqueta;
      }
      const exceso = anterior - (geometria.alto - 10);
      if (exceso > 0) ordenadas.forEach((m) => { m.yEtiqueta -= exceso; });

      const g = capa.selectAll(null).data(ordenadas).join("g").attr("class", "etiqueta");
      g.append("path").attr("class", "guia-etiqueta")
        .attr("d", (m) => `M${m.x},${m.y}L${lado.x + lado.signo * -8},${m.yEtiqueta}`);
      g.append("text").attr("class", "texto-etiqueta").attr("dy", "0.34em")
        .attr("x", lado.x).attr("y", (m) => m.yEtiqueta)
        .attr("text-anchor", lado.signo < 0 ? "end" : "start")
        .text((m) => `${m.puesto}. ${m.id}`);
    }
  }

  /* ------------------------------------------------------------------ leyenda */

  // La leyenda lleva encima el histograma de la distribución: el mismo objeto explica qué
  // significa cada color y muestra cuántas unidades caen en cada tramo, en lugar de gastar
  // dos piezas de la interfaz en decir cosas que se leen mejor juntas. La marca del umbral
  // muestra dónde corta el plan sobre esa misma distribución.
  // Límites de valor que scaleQuantize asigna a cada paso de la rampa. Se le preguntan a
  // la propia escala en vez de recalcularlos, para que no puedan desincronizarse.
  function rangoTramo(i) {
    return escalaColor.invertExtent(escalaColor.range()[i]);
  }

  function dibujarLeyenda() {
    const ancho = 460, altoHist = 32, barra = 13, alto = altoHist + barra + 40;
    const svg = d3.select("#leyenda").selectAll("svg").data([0]).join("svg")
      .attr("viewBox", `0 0 ${ancho} ${alto}`)
      .attr("role", "img")
      .attr("aria-label", "Escala de color del índice de criticidad y distribución de las unidades del piloto");
    svg.selectAll("*").remove();

    const pasos = escalaColor.range();
    const [lo, hi] = escalaColor.domain();
    const izq = 2, der = ancho - 2;
    const paso = (der - izq) / pasos.length;
    const us = unidades();
    const conteos = pasos.map((c) => us.filter((d) => escalaColor(d.indice) === c).length);
    const maxConteo = d3.max(conteos) || 1;
    const alturaDe = (n) => Math.max(1, (n / maxConteo) * altoHist);

    svg.append("text").attr("class", "leyenda-titulo").attr("x", izq).attr("y", 9)
      .text(`Índice de criticidad y reparto de ${articulo()} ${us.length} ${etiquetaNivel()}`);

    // Se liga el índice del tramo en el propio dato. El manejador de clic de d3 recibe
    // (evento, dato) y no el índice, y buscarlo después con indexOf sobre los conteos
    // devolvería el tramo equivocado en cuanto dos tramos tuviesen el mismo conteo.
    const tramos = pasos.map((color, i) => ({
      i, color, n: conteos[i], rango: rangoTramo(i),
      x: izq + i * paso,
      atenuado: estado.tramo !== null && estado.tramo !== i,
    }));

    const y0 = 21 + altoHist;
    svg.selectAll("rect.h").data(tramos).join("rect")
      .attr("class", "h leyenda-barra-conteo tramo-conteo")
      .attr("x", (t) => t.x + 1).attr("width", paso - 2)
      .attr("y", (t) => y0 - alturaDe(t.n)).attr("height", (t) => alturaDe(t.n))
      .attr("opacity", (t) => (t.atenuado ? 0.35 : 1))
      .attr("rx", 2);
    svg.selectAll("text.hn").data(tramos).join("text")
      .attr("class", "hn leyenda-texto")
      .attr("x", (t) => t.x + paso / 2).attr("text-anchor", "middle")
      .attr("y", (t) => y0 - alturaDe(t.n) - 3)
      .attr("opacity", (t) => (t.atenuado ? 0.45 : 1))
      .text((t) => t.n || "");

    svg.selectAll("rect.s").data(tramos).join("rect")
      .attr("class", "s")
      .attr("x", (t) => t.x).attr("y", y0 + 3)
      .attr("width", paso).attr("height", barra)
      .attr("fill", (t) => t.color)
      .attr("opacity", (t) => (t.atenuado ? 0.35 : 1));

    if (estado.tramo !== null) {
      svg.append("rect").attr("class", "tramo-marco")
        .attr("x", izq + estado.tramo * paso).attr("y", y0 + 3)
        .attr("width", paso).attr("height", barra).attr("rx", 2);
    }

    // Una sola zona de clic por tramo, que cubre histograma y rampa: apuntar a una barra
    // de un píxel de alto no es un objetivo razonable.
    svg.selectAll("rect.z").data(tramos).join("rect")
      .attr("class", "z tramo")
      .attr("x", (t) => t.x).attr("y", y0 - altoHist - 4)
      .attr("width", paso).attr("height", altoHist + barra + 11)
      .attr("fill", "transparent")
      .on("click", (_, t) => alternarTramo(t.i))
      .append("title")
      .text((t) => `${t.n} ${etiquetaNivel()} con índice entre ${coma(t.rango[0], 0)} y ` +
                   `${coma(t.rango[1], 0)}. Clic para filtrar por este tramo.`);

    const yTexto = y0 + barra + 16;
    svg.append("text").attr("class", "leyenda-texto").attr("x", izq).attr("y", yTexto)
      .text(`${coma(lo, 0)} · menos crítico`);
    svg.append("text").attr("class", "leyenda-texto").attr("x", der).attr("y", yTexto)
      .attr("text-anchor", "end").text(`más crítico · ${coma(hi, 0)}`);

    // Dónde cae el umbral del plan sobre la propia escala.
    const sel = seleccion();
    if (sel.length && hi > lo) {
      const umbral = sel[sel.length - 1].indice;
      const x = izq + ((umbral - lo) / (hi - lo)) * (der - izq);
      svg.append("line").attr("class", "leyenda-marca-plan")
        .attr("x1", x).attr("x2", x).attr("y1", y0 - altoHist - 3).attr("y2", y0 + barra + 5);
      const anclaje = x > ancho * 0.6 ? "end" : "start";
      svg.append("text").attr("class", "leyenda-marca-texto")
        .attr("x", anclaje === "end" ? x - 4 : x + 4).attr("y", yTexto)
        .attr("text-anchor", anclaje)
        .text(`umbral del plan ${coma(umbral, 0)}`);
    }
  }

  /* -------------------------------------------------------------------- lista */

  function dibujarLista() {
    const seleccionadas = clavesSeleccionadas();
    const filas = unidades().filter(coincide);
    const cuerpo = d3.select("#tabla-cuerpo");

    const tr = cuerpo.selectAll("tr").data(filas, (d) => d.id).join("tr")
      .attr("tabindex", 0)
      .classed("en-plan", (d) => seleccionadas.has(d.id))
      .classed("fuera", (d) => !seleccionadas.has(d.id))
      .classed("activa", (d) => d.id === claveActiva())
      .on("pointerenter", (_, d) => activar(d.id, null))
      .on("pointerleave", () => desactivar())
      .on("focus", (_, d) => activar(d.id, null))
      .on("click", (_, d) => fijar(d.id))
      .on("keydown", (evento, d) => {
        if (evento.key === "Enter" || evento.key === " ") {
          evento.preventDefault();
          fijar(d.id);
        }
      });
    tr.selectAll("td").remove();

    tr.append("td").attr("class", "celda-puesto").text((d) => d.puesto);
    tr.append("td").attr("class", "celda-id").html((d) =>
      estado.nivel === "alimentadores"
        ? `${d.id}<span class="celda-sub">${d.sed_aereas} subestaciones aéreas</span>`
        : `${d.id}<span class="celda-sub"><button type="button" class="enlace-alim" ` +
          `data-alim="${d.alimentador}" title="Ver solo las subestaciones de ${d.alimentador}">` +
          `${d.alimentador}</button></span>`);
    // La barra comparte la rampa del mapa: es lo que enlaza cada fila con su celda. La
    // cifra va siempre escrita al lado, que es además el canal de alivio que exige el
    // extremo claro de la rampa.
    tr.append("td").html((d) => {
      const ancho = Math.max(4, Math.round(d.indice));
      return '<div class="indice-celda">' +
             `<span class="barra-fondo"><span class="barra-valor" style="width:${ancho}%;background:${color(d.indice)}"></span></span>` +
             `<span class="barra-texto">${coma(d.indice, 0)}</span></div>`;
    });
    tr.append("td").attr("class", "num").text((d) => miles(d.clientes));

    // El clic en el alimentador filtra; no debe además fijar la subestación de esa fila.
    cuerpo.selectAll("button.enlace-alim").on("click", function (evento) {
      evento.stopPropagation();
      alternarAlimentador(this.dataset.alim);
    });

    // Con un filtro puesto, "las N de mayor índice entran al plan" sería falso: el plan lo
    // fija el corte sobre el total, no sobre lo que el filtro deja ver. Se cuenta cuántas
    // de las filas visibles están de verdad dentro del plan.
    const enPlan = filas.filter((d) => seleccionadas.has(d.id)).length;
    $("#lista-nota").textContent = hayFiltro()
      ? `${filas.length} de ${unidades().length} ${etiquetaNivel()} coinciden con el filtro. ` +
        `${enPlan} de ellas ${enPlan === 1 ? "está" : "están"} dentro del plan de ${estado.corte}.`
      : `${filas.length} ${etiquetaNivel()} del piloto. ` +
        `${estado.nivel === "alimentadores" ? "Los" : "Las"} ${Math.min(estado.corte, filas.length)} ` +
        `de mayor índice entran al plan del trimestre.`;
  }

  /* -------------------------------------------------------------- interacción */

  // Las cinco vistas comparten estado, así que cualquiera de ellas puede llamar aquí y el
  // resto se entera. Toda la interacción cruzada pasa por estas cuatro funciones.

  function alternarTramo(i) {
    estado.tramo = estado.tramo === i ? null : i;
    actualizar();
  }

  function alternarAlimentador(codigo) {
    estado.alimentador = estado.alimentador === codigo ? null : codigo;
    actualizar();
  }

  // Cambia el tamaño del plan desde la curva. Se usa al arrastrar el asa del corte.
  function fijarCorte(n) {
    const total = unidades().length;
    const v = Math.max(1, Math.min(total, Math.round(n)));
    if (v === estado.corte) return;
    estado.corte = v;
    ajustarCorte();
    actualizar();
  }

  function dibujarFiltros() {
    const barra = $("#filtros");
    barra.hidden = !hayFiltro();
    if (barra.hidden) return;
    const chips = [];
    if (estado.tramo !== null) {
      const [a, b] = rangoTramo(estado.tramo);
      chips.push({
        clave: "tramo",
        muestra: escalaColor.range()[estado.tramo],
        texto: `Índice ${coma(a, 0)} a ${coma(b, 0)}`,
      });
    }
    if (estado.alimentador) {
      chips.push({ clave: "alimentador", texto: `Alimentador ${estado.alimentador}` });
    }
    if (estado.busqueda) {
      chips.push({ clave: "busqueda", texto: `"${estado.busqueda}"` });
    }
    const sel = d3.select("#filtros-chips").selectAll("span.chip")
      .data(chips, (c) => c.clave)
      .join("span").attr("class", "chip");
    sel.html((c) =>
      (c.muestra ? `<span class="chip-muestra" style="background:${c.muestra}"></span>` : "") +
      `<span>${c.texto}</span><button type="button" aria-label="Quitar filtro">×</button>`);
    sel.select("button").on("click", (_, c) => {
      if (c.clave === "tramo") estado.tramo = null;
      if (c.clave === "alimentador") estado.alimentador = null;
      if (c.clave === "busqueda") { estado.busqueda = ""; $("#buscar").value = ""; }
      actualizar();
    });

    const n = unidades().filter(coincide).length;
    barra.querySelector(".filtros-titulo").textContent =
      `${n} ${etiquetaNivel()} ${n === 1 ? "coincide" : "coinciden"}`;
  }

  // Al fijar una unidad desde el mapa o desde la curva, la lista tiene 252 filas y lo más
  // probable es que la fila elegida no se vea. Se lleva a la vista, pero solo al fijar:
  // hacerlo también al pasar el puntero convertiría la tabla en un carrusel.
  function acercarFila(id) {
    const cuerpo = $("#tabla-cuerpo");
    if (!cuerpo) return;
    for (const tr of cuerpo.children) {
      if (tr.__data__ && tr.__data__.id === id) {
        tr.scrollIntoView({ block: "nearest" });
        return;
      }
    }
  }

  /* ------------------------------------------------------------------ resumen */

  function dibujarResumen() {
    const sel = seleccion();
    const us = unidades();
    const totalClientes = d3.sum(us, (d) => d.clientes);
    const totalKva = d3.sum(us, (d) => d.kva);
    const clientes = d3.sum(sel, (d) => d.clientes);
    const kva = d3.sum(sel, (d) => d.kva);

    $("#kpi-unidades").textContent = sel.length;
    $("#kpi-unidades-et").textContent =
      estado.nivel === "alimentadores" ? "Alimentadores en el plan" : "Subestaciones en el plan";
    $("#kpi-unidades-pie").textContent =
      `de ${us.length} ${etiquetaNivel()} del piloto`;

    $("#kpi-clientes").textContent = miles(clientes);
    $("#kpi-clientes-pie").textContent = totalClientes
      ? `${coma((clientes / totalClientes) * 100, 0)} % de los clientes del piloto` : "-";

    $("#kpi-kva").innerHTML = miles(kva) + '<span class="unidad">kVA</span>';
    $("#kpi-kva-pie").textContent = totalKva
      ? `${coma((kva / totalKva) * 100, 0)} % de la potencia del piloto` : "-";

    $("#kpi-indice").textContent = sel.length ? coma(sel[sel.length - 1].indice, 0) : "-";
    $("#kpi-indice-pie").textContent = sel.length
      ? `la unidad ${sel[sel.length - 1].id} cierra el plan` : "-";
  }

  /* -------------------------------------------------------------------- curva */

  // Dos gráficos apilados sobre el mismo eje de puesto. Nunca dos escalas verticales en un
  // mismo marco: el índice y el porcentaje acumulado de clientes son magnitudes distintas
  // y superponerlas en un solo panel invita a leer cruces que no significan nada.
  function dibujarCurva() {
    const caja = $("#curva-caja");
    const ancho = Math.max(300, caja.clientWidth);
    const estrecho = ancho < 560;
    const m = { arriba: 16, derecha: estrecho ? 10 : 16, abajo: 30, izquierda: 40 };
    const hA = 96, hB = 68, hueco = 30;
    const alto = m.arriba + hA + hueco + hB + m.abajo;

    const svg = d3.select("#curva")
      .attr("viewBox", `0 0 ${ancho} ${alto}`)
      .attr("width", ancho).attr("height", alto);
    svg.selectAll("*").remove();

    const us = unidades();
    if (!us.length) return;
    const total = us.length;
    const totalClientes = d3.sum(us, (d) => d.clientes) || 1;
    let acc = 0;
    const datos = us.map((d, i) => {
      acc += d.clientes;
      return { puesto: i + 1, indice: d.indice, id: d.id, pasa: coincide(d),
               cobertura: (acc / totalClientes) * 100 };
    });

    const x = d3.scaleLinear().domain([0.5, total + 0.5]).range([m.izquierda, ancho - m.derecha]);
    const yA = d3.scaleLinear().domain([0, 100]).range([m.arriba + hA, m.arriba]);
    const yBase = m.arriba + hA + hueco;
    const yB = d3.scaleLinear().domain([0, 100]).range([yBase + hB, yBase]);

    const xCorte = x(estado.corte + 0.5);
    const enPlan = datos[estado.corte - 1];

    // Banda del plan, primero, para que quede por debajo de todo lo demás.
    svg.append("rect").attr("class", "curva-banda")
      .attr("x", x(0.5)).attr("y", m.arriba)
      .attr("width", Math.max(0, xCorte - x(0.5)))
      .attr("height", hA + hueco + hB);

    const rejilla = (escala, etiqueta) => {
      const g = svg.append("g");
      for (const v of [0, 25, 50, 75, 100]) {
        g.append("line").attr("class", "curva-rejilla")
          .attr("x1", m.izquierda).attr("x2", ancho - m.derecha)
          .attr("y1", escala(v)).attr("y2", escala(v));
        g.append("text").attr("class", "curva-eje")
          .attr("x", m.izquierda - 7).attr("y", escala(v) + 3.5).attr("text-anchor", "end")
          .text(etiqueta(v));
      }
    };
    rejilla(yA, (v) => v);
    rejilla(yB, (v) => v + "%");

    // Panel de arriba: el índice de cada unidad en su puesto, con el color de la rampa.
    // Es la vista que muestra dónde se aplana la curva, que es la pregunta de capacidad.
    const anchoBarra = Math.max(1, (x(2) - x(1)) - (total > 80 ? 0.5 : 2));
    const activa = claveActiva();
    svg.append("g").selectAll("rect").data(datos).join("rect")
      .attr("class", "curva-barra")
      .attr("x", (d) => x(d.puesto) - anchoBarra / 2)
      .attr("y", (d) => yA(d.indice))
      .attr("width", anchoBarra)
      .attr("height", (d) => yA(0) - yA(d.indice))
      .attr("rx", Math.min(2, anchoBarra / 2))
      .attr("fill", (d) => color(d.indice))
      // Dos atenuaciones que se multiplican: estar fuera del plan y no pasar el filtro.
      .attr("opacity", (d) => (d.puesto <= estado.corte ? 1 : 0.55) * (d.pasa ? 1 : 0.22))
      .on("pointerenter", (_, d) => activar(d.id, null))
      .on("pointerleave", () => desactivar())
      .on("click", (_, d) => fijar(d.id))
      .append("title").text((d) =>
        `Puesto ${d.puesto}. ${d.id}, índice ${coma(d.indice, 0)}. Clic para fijarla.`);

    // La unidad activa se marca también aquí: es lo que cierra el círculo entre el mapa,
    // la lista y la curva.
    const dActiva = datos.find((d) => d.id === activa);
    if (dActiva) {
      svg.append("rect").attr("class", "curva-activa")
        .attr("x", x(dActiva.puesto) - anchoBarra / 2 - 1.5)
        .attr("y", yA(dActiva.indice) - 1.5)
        .attr("width", anchoBarra + 3)
        .attr("height", yA(0) - yA(dActiva.indice) + 3)
        .attr("rx", 3);
    }

    // Panel de abajo: qué porcentaje de los clientes del piloto queda cubierto al llegar a
    // ese puesto. Es el argumento con el que se defiende el tamaño del plan.
    const area = d3.area().x((d) => x(d.puesto)).y0(yB(0)).y1((d) => yB(d.cobertura));
    const linea = d3.line().x((d) => x(d.puesto)).y((d) => yB(d.cobertura));
    svg.append("path").datum(datos).attr("class", "curva-area").attr("d", area);
    svg.append("path").datum(datos).attr("class", "curva-linea").attr("d", linea);

    // Línea de corte y su rótulo, en los dos paneles.
    svg.append("line").attr("class", "curva-corte")
      .attr("x1", xCorte).attr("x2", xCorte)
      .attr("y1", m.arriba).attr("y2", yB(0));

    // Asa para mover el corte arrastrando sobre la propia curva. Va aparte de las barras
    // y con su propio cursor: si el lienzo entero cambiase el plan, no se podría hacer
    // clic en una barra para seleccionarla sin mover el plan sin querer.
    const arrastre = d3.drag()
      .on("start drag", (evento) => fijarCorte(x.invert(evento.x) - 0.5));
    svg.append("rect").attr("class", "curva-asa-zona")
      .attr("x", xCorte - 11).attr("y", m.arriba - 8)
      .attr("width", 22).attr("height", hA + hueco + hB + 8)
      .call(arrastre);
    svg.append("rect").attr("class", "curva-asa")
      .attr("x", xCorte - 5).attr("y", m.arriba - 7)
      .attr("width", 10).attr("height", 12).attr("rx", 3)
      .call(arrastre)
      .append("title").text("Arrastre para cambiar el tamaño del plan");

    if (enPlan) {
      svg.append("circle").attr("class", "curva-punto")
        .attr("cx", x(enPlan.puesto)).attr("cy", yB(enPlan.cobertura)).attr("r", 4.5);
      const aIzq = xCorte > ancho * 0.6;
      svg.append("text").attr("class", "curva-et")
        .attr("x", aIzq ? xCorte - 7 : xCorte + 7)
        .attr("y", yB(enPlan.cobertura) - 9)
        .attr("text-anchor", aIzq ? "end" : "start")
        .text(`${coma(enPlan.cobertura, 0)} % de los clientes`);
      svg.append("text").attr("class", "curva-corte-et")
        .attr("x", aIzq ? xCorte - 7 : xCorte + 7).attr("y", m.arriba + 10)
        .attr("text-anchor", aIzq ? "end" : "start")
        .text(`plan: ${estado.corte} ${etiquetaNivel(estado.corte !== 1)}`);
    }

    // Títulos de cada panel, directos sobre el gráfico en lugar de en una leyenda aparte:
    // cada panel tiene una sola serie, así que el título ya la nombra.
    svg.append("text").attr("class", "curva-titulo")
      .attr("x", m.izquierda).attr("y", m.arriba - 4)
      .text("Índice de criticidad de cada unidad");
    svg.append("text").attr("class", "curva-titulo")
      .attr("x", m.izquierda).attr("y", yBase - 8)
      .text("Clientes de baja tensión cubiertos, acumulado");

    // Eje de puesto, compartido y rotulado una sola vez al pie.
    const marcas = x.ticks(estrecho ? 5 : 10).filter((v) => Number.isInteger(v) && v >= 1 && v <= total);
    const g = svg.append("g");
    for (const v of marcas) {
      g.append("text").attr("class", "curva-eje")
        .attr("x", x(v)).attr("y", yB(0) + 14).attr("text-anchor", "middle").text(v);
    }
    g.append("text").attr("class", "curva-eje")
      .attr("x", (m.izquierda + ancho - m.derecha) / 2).attr("y", yB(0) + 27)
      .attr("text-anchor", "middle")
      .text(`Puesto en la lista priorizada, de 1 a ${total}`);
  }

  /* ------------------------------------------------------------------- ficha */

  const ficha = $("#ficha");

  const claveActiva = () => estado.fijado || estado.activo;
  const buscarUnidad = (id) => porAlimentador.get(id) || porSubestacion.get(id) || null;

  function activar(id, evento) {
    estado.activo = id;
    if (evento) mostrarFicha(id, evento);
    sincronizarSeleccion();
  }

  function desactivar() {
    estado.activo = null;
    ficha.hidden = true;
    sincronizarSeleccion();
  }

  // Un único sitio donde la selección se propaga a las cuatro vistas que la muestran.
  // Antes cada llamada repetía la lista de repintados y era cuestión de tiempo que una
  // vista nueva se quedara fuera.
  function sincronizarSeleccion() {
    pintarMapa();
    d3.select("#tabla-cuerpo").selectAll("tr").classed("activa", (d) => d.id === claveActiva());
    dibujarCurva();
    dibujarDetalle();
  }

  function fijar(id) {
    estado.fijado = estado.fijado === id ? null : id;
    activar(id, null);
    if (estado.fijado) acercarFila(estado.fijado);
  }

  function mostrarFicha(id, evento) {
    const u = buscarUnidad(id);
    if (!u) return;
    const enPlan = clavesSeleccionadas().has(u.id);
    const sub = estado.nivel === "alimentadores"
      ? `${u.sed_aereas} subestaciones aéreas expuestas`
      : `Alimentador ${u.alimentador}`;
    ficha.innerHTML =
      `<div class="ficha-tope"><h3>${u.id}</h3><span class="ficha-puesto">puesto ${u.puesto}</span></div>` +
      `<p class="ficha-sub">${sub}</p>` +
      '<div class="ficha-indice">' +
        `<span class="ficha-chip" style="background:${color(u.indice)}"></span>` +
        `<span class="ficha-indice-num">${coma(u.indice, 0)}</span>` +
        '<span class="ficha-indice-de">índice<br>de 100</span>' +
      "</div>" +
      "<dl>" +
      `<dt>Riesgo a 3 meses</dt><dd>${pct(u.probabilidad)}</dd>` +
      `<dt>Sin poda</dt><dd>${miles(u.meses_sin_poda)} meses</dd>` +
      `<dt>Clientes</dt><dd>${miles(u.clientes)}</dd>` +
      `<dt>Potencia</dt><dd>${miles(u.kva)} kVA</dd>` +
      "</dl>" +
      (enPlan ? `<span class="pastilla">${icono("i-tilde")}Entra al plan</span>` : "");
    ficha.hidden = false;
    moverFicha(evento);
  }

  function moverFicha(evento) {
    if (ficha.hidden || !evento) return;
    const caja = $("#mapa-caja").getBoundingClientRect();
    const x = evento.clientX - caja.left;
    const y = evento.clientY - caja.top;
    const ancho = ficha.offsetWidth, alto = ficha.offsetHeight;
    let izq = x + 16, arr = y + 16;
    if (izq + ancho > caja.width) izq = Math.max(4, x - ancho - 16);
    if (arr + alto > caja.height) arr = Math.max(4, y - alto - 16);
    ficha.style.left = izq + "px";
    ficha.style.top = arr + "px";
  }

  /* ----------------------------------------------------------------- detalle */

  function dibujarDetalle() {
    const contenedor = $("#detalle");
    const u = buscarUnidad(claveActiva());
    if (!u) {
      contenedor.innerHTML =
        `<p class="detalle-vacio">${icono("i-pin")} Ninguna unidad seleccionada. Pase el puntero sobre el mapa o la lista para ver su composición, y haga clic para fijarla.</p>`;
      return;
    }
    const alimentador = estado.nivel === "alimentadores" ? u : porAlimentador.get(u.alimentador);
    const enPlan = clavesSeleccionadas().has(u.id);
    const med = medianas();
    const tonos = leerTokens(COMPS);

    // Aportes: valor del componente × su peso. Los cuatro suman exactamente el índice, así
    // que la barra apilada no es una metáfora del cálculo, es el cálculo.
    const aportes = COMPONENTES.map((c, i) => ({
      nombre: c.nombre,
      peso: c.peso,
      valor: u.componentes[c.nombre] ?? 0,
      aporte: (u.componentes[c.nombre] ?? 0) * c.peso,
      tono: tonos[i],
      mediana: med.get(c.nombre) ?? 0,
    }));
    const suma = d3.sum(aportes, (a) => a.aporte) || 1;

    const segmentos = aportes.map((a) =>
      `<span class="aportes-seg" style="flex:${a.aporte};background:${a.tono}" ` +
      `title="${a.nombre}: ${coma(a.valor, 0)} × ${coma(a.peso, 2)} = ${coma(a.aporte, 1)} puntos"></span>`
    ).join("");

    const filas = aportes.map((a) =>
      '<div class="comp-fila">' +
        `<span class="comp-punto" style="background:${a.tono}"></span>` +
        `<span class="comp-nombre">${a.nombre} <span class="comp-peso">peso ${coma(a.peso, 2)}</span></span>` +
        `<span class="comp-cifras"><b>${coma(a.valor, 0)}</b> <i>→ ${coma(a.aporte, 1)} pts</i></span>` +
        `<span class="comp-pista">` +
          `<i style="width:${Math.max(2, a.valor)}%;background:${a.tono}"></i>` +
          `<span class="comp-mediana" style="left:${a.mediana}%" title="Mediana del piloto: ${coma(a.mediana, 0)}"></span>` +
        "</span>" +
      "</div>"
    ).join("");

    const motivos = (alimentador && alimentador.motivos && alimentador.motivos.length)
      ? alimentador.motivos.map((m) => `<li>${icono("i-alerta")}<span>${m}</span></li>`).join("")
      : `<li>${icono("i-info")}<span>Sin razones destacadas por el modelo</span></li>`;

    const identidad = estado.nivel === "alimentadores"
      ? `<dt>${icono("i-capas")}Subestaciones aéreas</dt><dd>${u.sed_aereas}</dd>`
      : `<dt>${icono("i-capas")}Alimentador</dt>` +
        `<dd><button type="button" class="enlace-alim" data-alim="${u.alimentador}">${u.alimentador}</button></dd>` +
        `<dt>${icono("i-pin")}Dirección</dt><dd style="text-align:left;font-weight:400">${u.direccion}</dd>`;

    contenedor.innerHTML = `
      <div class="bloque">
        <h3>Ficha de la unidad</h3>
        <div class="detalle-tope">
          <div class="detalle-indice" style="background:${color(u.indice)};color:${tintaSobre(color(u.indice))}">
            <b>${coma(u.indice, 0)}</b><span>de 100</span>
          </div>
          <div class="detalle-ident">
            <h4>${u.id}</h4>
            <p>Puesto ${u.puesto} de ${unidades().length} ${etiquetaNivel()}</p>
            <span class="etiqueta-plan${enPlan ? "" : " fuera-plan"}">
              ${icono(enPlan ? "i-tilde" : "i-reloj")}${enPlan ? "Entra al plan" : "Fuera del plan actual"}
            </span>
          </div>
        </div>
        <dl>
          <dt>${icono("i-medidor")}Riesgo estimado a 3 meses</dt><dd>${pct(u.probabilidad)}</dd>
          <dt>${icono("i-reloj")}Meses desde la última poda</dt><dd>${miles(u.meses_sin_poda)}</dd>
          <dt>${icono("i-clientes")}Clientes de baja tensión</dt><dd>${miles(u.clientes)}</dd>
          <dt>${icono("i-rayo")}Potencia instalada</dt><dd>${miles(u.kva)} kVA</dd>
          ${identidad}
        </dl>
      </div>

      <div class="bloque">
        <h3>De qué se compone el índice</h3>
        <div class="aportes">
          <div class="aportes-barra">${segmentos}</div>
          <div class="aportes-escala">
            <span style="left:0">0</span>
            <span style="left:50%">${coma(suma / 2, 0)}</span>
            <span style="left:100%">${coma(suma, 0)} puntos de índice</span>
          </div>
        </div>
        <div class="comp-tabla">${filas}</div>
        <p class="comp-nota">${icono("i-info")}<span>Cada componente es un percentil de 0 a 100 dentro del piloto. La marca gris sobre cada barra es la mediana de ${articulo()} ${unidades().length} ${etiquetaNivel()}.</span></p>
      </div>

      <div class="bloque">
        <h3>Por qué está en esta posición</h3>
        <ul class="motivos">${motivos}</ul>
        <dl>
          <dt>${icono("i-alerta")}Eventos históricos del alimentador</dt><dd>${alimentador ? alimentador.eventos_historicos : "-"}</dd>
          <dt>${icono("i-reloj")}Eventos del último año</dt><dd>${alimentador ? alimentador.eventos_12m : "-"}</dd>
          <dt>${icono("i-medidor")}SAIDI de los últimos 12 meses</dt><dd>${alimentador ? coma(alimentador.saidi_ltm, 2) : "-"}</dd>
        </dl>
      </div>`;

    contenedor.querySelectorAll("button.enlace-alim").forEach((b) => {
      b.addEventListener("click", () => alternarAlimentador(b.dataset.alim));
    });
  }

  /* -------------------------------------------------------------- descarga */

  function descargarCsv() {
    const sel = seleccion();
    const encabezado = estado.nivel === "alimentadores"
      ? ["puesto", "alimentador", "indice", "riesgo_3_meses", "meses_sin_poda",
         "clientes", "kva", "sed_aereas", "motivos"]
      : ["puesto", "subestacion", "alimentador", "direccion", "indice",
         "riesgo_3_meses", "meses_sin_poda", "clientes", "kva"];
    const filas = sel.map((d) => estado.nivel === "alimentadores"
      ? [d.puesto, d.id, d.indice, d.probabilidad, d.meses_sin_poda, d.clientes,
         d.kva, d.sed_aereas, (d.motivos || []).join(" | ")]
      : [d.puesto, d.id, d.alimentador, d.direccion, d.indice, d.probabilidad,
         d.meses_sin_poda, d.clientes, d.kva]);
    const escapar = (v) => {
      const s = String(v === null || v === undefined ? "" : v);
      return /[",;\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const texto = "﻿" + [encabezado].concat(filas)
      .map((f) => f.map(escapar).join(";")).join("\n");
    const url = URL.createObjectURL(new Blob([texto], { type: "text/csv;charset=utf-8" }));
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = `plan_poda_${estado.nivel}_${META.corte}.csv`;
    document.body.appendChild(enlace);
    enlace.click();
    document.body.removeChild(enlace);
    URL.revokeObjectURL(url);
  }

  /* -------------------------------------------------------------- redibujado */

  function actualizar({ regeometrizar = false } = {}) {
    construirEscala();
    if (regeometrizar) dibujarMapa();
    else pintarMapa();
    dibujarFiltros();
    dibujarLeyenda();
    dibujarLista();
    dibujarResumen();
    dibujarCurva();
    dibujarDetalle();
  }

  function ajustarCorte() {
    const total = unidades().length;
    const control = $("#corte");
    control.max = total;
    if (estado.corte > total) estado.corte = total;
    control.value = estado.corte;
    $("#corte-valor").textContent = `${estado.corte} de ${total}`;
  }

  /* ------------------------------------------------------------------ eventos */

  d3.selectAll(".segmentado button").on("click", function () {
    const nivel = this.dataset.nivel;
    if (nivel === estado.nivel) return;
    estado.nivel = nivel;
    estado.activo = null;
    limpiarFiltros();
    estado.fijado = (nivel === "alimentadores" ? DATOS.alimentadores : DATOS.subestaciones)[0].id;
    ficha.hidden = true;
    d3.selectAll(".segmentado button")
      .classed("activo", function () { return this.dataset.nivel === nivel; })
      .attr("aria-checked", function () { return String(this.dataset.nivel === nivel); });
    estado.corte = nivel === "alimentadores"
      ? Math.min(META.k_alimentadores, DATOS.alimentadores.length)
      : Math.min(META.capacidad_mes, DATOS.subestaciones.length);
    ajustarCorte();
    actualizar();
  });

  $("#corte").addEventListener("input", function () {
    estado.corte = +this.value;
    ajustarCorte();
    actualizar();
  });

  $("#buscar").addEventListener("input", function () {
    estado.busqueda = this.value.trim();
    actualizar();
  });

  $("#limpiar-filtros").addEventListener("click", () => {
    limpiarFiltros();
    actualizar();
  });

  $("#descargar").addEventListener("click", descargarCsv);

  const botonTema = $("#boton-tema");
  function iconoTema() {
    const oscuroSistema = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const actual = document.documentElement.getAttribute("data-theme");
    const esOscuro = actual ? actual === "dark" : oscuroSistema;
    botonTema.querySelector("use").setAttribute("href", esOscuro ? "#i-sol" : "#i-luna");
    botonTema.title = esOscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro";
  }
  botonTema.addEventListener("click", function () {
    const actual = document.documentElement.getAttribute("data-theme");
    const oscuro = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const siguiente = actual ? (actual === "dark" ? "light" : "dark") : (oscuro ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", siguiente);
    iconoTema();
    actualizar();
  });

  let temporizador = null;
  window.addEventListener("resize", () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => actualizar({ regeometrizar: true }), 140);
  });

  /* ------------------------------------------------------------------ arranque */

  $("#ventana").textContent = META.ventana;
  $("#sello-corte").querySelector("span").textContent = `Corte ${META.corte}`;
  $("#pie-meta").textContent =
    `Corte de datos ${META.corte}. Modelo: ${META.modelo}. ` +
    `${META.n_alimentadores} alimentadores, ${META.n_subestaciones} subestaciones aéreas y ` +
    `${META.n_no_expuestas} subestaciones no expuestas. Generado el ${META.generado}.`;

  // La página abre con la unidad más crítica ya fijada, para que el panel de detalle
  // muestre desde el principio qué información entrega y no haya que descubrirlo.
  estado.fijado = unidades()[0] ? unidades()[0].id : null;

  d3.selectAll(".segmentado button")
    .classed("activo", function () { return this.dataset.nivel === estado.nivel; })
    .attr("aria-checked", function () { return String(this.dataset.nivel === estado.nivel); });

  iconoTema();
  ajustarCorte();
  construirEscala();
  dibujarMapa();
  dibujarFiltros();
  dibujarLeyenda();
  dibujarLista();
  dibujarResumen();
  dibujarCurva();
  dibujarDetalle();
})();
