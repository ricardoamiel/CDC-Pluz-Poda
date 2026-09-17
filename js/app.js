/* Prototipo de priorización de poda por vegetación. Piloto de Los Olivos.
   Pluz Energía y UTEC, curso DS5045. Primer prototipo, reunión N°3.

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
   3. Color. El índice es una magnitud continua, así que se codifica con una rampa de un solo
      tono de claro a oscuro. La identidad nunca depende solo del color: la lista ordenada
      repite la misma información en texto y es la vista de tabla accesible del mapa.
*/

(function () {
  "use strict";

  const DATOS = window.DATOS_PLUZ;
  const META = DATOS.meta;

  // Un parámetro en la dirección permite abrir la página directamente en un tema, lo que
  // sirve para incrustarla o para capturarla en un informe sin depender de la
  // configuración del equipo. Sin parámetro se respeta el tema del sistema.
  const parametros = new URLSearchParams(location.search);
  const temaPedido = parametros.get("tema");
  if (temaPedido === "claro") document.documentElement.setAttribute("data-theme", "light");
  if (temaPedido === "oscuro") document.documentElement.setAttribute("data-theme", "dark");

  const RAMPA = ["--idx-1", "--idx-2", "--idx-3", "--idx-4",
                 "--idx-5", "--idx-6", "--idx-7", "--idx-8"];

  // El nivel también se puede fijar desde la dirección, de modo que en la reunión se puede
  // compartir un enlace que abra directamente la vista por subestación.
  const nivelPedido = parametros.get("nivel") === "subestaciones"
    ? "subestaciones" : "alimentadores";

  const estado = {
    nivel: nivelPedido,
    corte: nivelPedido === "subestaciones"
      ? Math.min(META.capacidad_mes, DATOS.subestaciones.length)
      : Math.min(META.k_alimentadores || 10, DATOS.alimentadores.length),
    busqueda: "",
    activo: null,
    fijado: null,
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

  function leerRampa() {
    const estilo = getComputedStyle(document.querySelector(".viz-root"));
    return RAMPA.map((v) => estilo.getPropertyValue(v).trim() || "#cccccc");
  }

  const $ = (sel) => document.querySelector(sel);

  /* ------------------------------------------------- índices y datos derivados */

  const porAlimentador = new Map(DATOS.alimentadores.map((d) => [d.id, d]));
  const porSubestacion = new Map(DATOS.subestaciones.map((d) => [d.id, d]));
  // Solo se dibujan las subestaciones cuyo alimentador tiene índice, para que ninguna
  // celda del mapa quede sin valor que mostrar.
  const subestacionesMapa = DATOS.subestaciones.filter((d) => porAlimentador.has(d.alimentador));

  function unidades() {
    return estado.nivel === "alimentadores" ? DATOS.alimentadores : DATOS.subestaciones;
  }

  function etiquetaNivel(plural = true) {
    if (estado.nivel === "alimentadores") return plural ? "alimentadores" : "alimentador";
    return plural ? "subestaciones" : "subestación";
  }

  // Índice que le corresponde a una celda del mapa según el nivel elegido.
  function unidadDeCelda(sed) {
    return estado.nivel === "alimentadores" ? porAlimentador.get(sed.alimentador) : sed;
  }

  function claveDeCelda(sed) {
    return estado.nivel === "alimentadores" ? sed.alimentador : sed.id;
  }

  function seleccion() {
    return unidades().slice(0, estado.corte);
  }

  function clavesSeleccionadas() {
    return new Set(seleccion().map((d) => d.id));
  }

  function coincide(u) {
    if (!estado.busqueda) return true;
    const q = estado.busqueda.toLowerCase();
    return (u.id + " " + (u.alimentador || "") + " " + (u.direccion || ""))
      .toLowerCase().includes(q);
  }

  /* ------------------------------------------------------------------ escala */

  let escalaColor = null;

  function construirEscala() {
    const valores = unidades().map((d) => d.indice);
    escalaColor = d3.scaleQuantize()
      .domain([d3.min(valores), d3.max(valores)])
      .range(leerRampa());
  }

  const color = (v) => (v === null || v === undefined ? "var(--neutro-mapa)" : escalaColor(v));

  /* ------------------------------------------------------------------- mapa */

  const svgMapa = d3.select("#mapa");
  const capaCeldas = svgMapa.append("g").attr("class", "capa-celdas");
  const capaContornos = svgMapa.append("g").attr("class", "capa-contornos");
  const capaPuntos = svgMapa.append("g").attr("class", "capa-puntos");
  const capaPlan = svgMapa.append("g").attr("class", "capa-plan");

  let geometria = null;

  // Ancho reservado a la derecha del mapa para las etiquetas directas de las unidades del
  // plan. El distrito de Los Olivos es muy alargado de norte a sur, de modo que al ajustarlo
  // a la altura del panel sobra espacio a los lados: ese espacio se usa para nombrar las
  // unidades priorizadas en lugar de dejarlo vacío.
  const MARGEN_ETIQUETAS = 118;

  // Cuántas unidades del plan se numeran sobre el mapa y se nombran en el margen.
  const MAX_MARCAS = 12;

  function calcularGeometria(ancho, alto) {
    const margen = 10;
    // Mercator transversa rotada al meridiano central del distrito. Equivale a trabajar
    // en la zona UTM local: conforme y con distorsión despreciable a esta escala.
    const meridiano = d3.mean(subestacionesMapa, (d) => d.lon);
    const proyeccion = d3.geoTransverseMercator().rotate([-meridiano, 0]);

    const puntosGeo = {
      type: "MultiPoint",
      coordinates: DATOS.subestaciones.concat(DATOS.no_expuestas).map((d) => [d.lon, d.lat]),
    };
    // En pantallas estrechas se renuncia a las etiquetas directas y el mapa ocupa todo el
    // ancho disponible, porque el margen que necesitarían vale más como mapa.
    const reserva = ancho > 520 ? MARGEN_ETIQUETAS : 0;
    proyeccion.fitExtent(
      [[margen, margen], [ancho - margen - reserva, alto - margen]], puntosGeo);

    const puntos = subestacionesMapa.map((d) => {
      const p = proyeccion([d.lon, d.lat]);
      return { sed: d, x: p[0], y: p[1] };
    });
    const noExpuestos = DATOS.no_expuestas.map((d) => proyeccion([d.lon, d.lat]));

    const todos = puntos.map((p) => [p.x, p.y]).concat(noExpuestos);
    const envolvente = d3.polygonHull(todos);

    const delaunay = d3.Delaunay.from(puntos, (p) => p.x, (p) => p.y);
    const voronoi = delaunay.voronoi([0, 0, ancho, alto]);
    const celdas = puntos.map((p, i) => ({
      punto: p,
      camino: recortar(voronoi.cellPolygon(i), envolvente),
    })).filter((c) => c.camino);

    const bordeDerecho = d3.max(envolvente, (p) => p[0]);
    return { proyeccion, puntos, noExpuestos, envolvente, celdas, ancho, alto,
             bordeDerecho, reserva };
  }

  // Recorte de un polígono contra la envolvente del catastro por el algoritmo de
  // Sutherland y Hodgman. Evita que las celdas del borde se estiren hasta el marco.
  function recortar(poligono, recorte) {
    if (!poligono || !recorte) return null;
    let salida = poligono.slice();
    const n = recorte.length;
    // De qué lado de cada arista queda el interior depende del sentido de recorrido de la
    // envolvente, y ese sentido depende a su vez de que el eje vertical de la pantalla
    // crece hacia abajo. En lugar de deducirlo del signo del área, que es justo donde se
    // cuela el error, se comprueba de forma directa con el centro del propio polígono.
    const centro = d3.polygonCentroid(recorte);
    const orientado = lado(recorte[0], recorte[1], centro) >= 0
      ? recorte
      : recorte.slice().reverse();
    for (let i = 0; i < n; i++) {
      const a = orientado[i];
      const b = orientado[(i + 1) % n];
      const entrada = salida;
      salida = [];
      if (!entrada.length) return null;
      let previo = entrada[entrada.length - 1];
      for (const actual of entrada) {
        const dentroActual = lado(a, b, actual) >= 0;
        const dentroPrevio = lado(a, b, previo) >= 0;
        if (dentroActual) {
          if (!dentroPrevio) salida.push(interseccion(previo, actual, a, b));
          salida.push(actual);
        } else if (dentroPrevio) {
          salida.push(interseccion(previo, actual, a, b));
        }
        previo = actual;
      }
    }
    return salida.length > 2 ? salida : null;
  }

  const lado = (a, b, p) => (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);

  function interseccion(p1, p2, a, b) {
    const dx1 = p2[0] - p1[0], dy1 = p2[1] - p1[1];
    const dx2 = b[0] - a[0], dy2 = b[1] - a[1];
    const den = dx1 * dy2 - dy1 * dx2;
    if (!den) return p1.slice();
    const t = ((a[0] - p1[0]) * dy2 - (a[1] - p1[1]) * dx2) / den;
    return [p1[0] + t * dx1, p1[1] + t * dy1];
  }

  const camino = (puntos) => "M" + puntos.map((p) => p.join(",")).join("L") + "Z";

  function dibujarMapa() {
    const caja = $("#mapa-caja");
    const ancho = Math.max(280, caja.clientWidth);
    const alto = Math.round(Math.min(Math.max(ancho * 1.18, 380), 660));
    svgMapa.attr("viewBox", `0 0 ${ancho} ${alto}`)
           .attr("width", ancho).attr("height", alto);
    geometria = calcularGeometria(ancho, alto);
    pintarMapa();
  }

  function pintarMapa() {
    if (!geometria) return;
    const seleccionadas = clavesSeleccionadas();
    const hayBusqueda = Boolean(estado.busqueda);

    capaCeldas.selectAll("path.celda")
      .data(geometria.celdas, (c) => c.punto.sed.id)
      .join("path")
      .attr("class", "celda")
      .attr("d", (c) => camino(c.camino))
      .attr("fill", (c) => color(unidadDeCelda(c.punto.sed).indice))
      // En la vista por alimentador cada celda se perfila con su propio color para que las
      // celdas de un mismo alimentador se fundan en un territorio. En la vista por
      // subestación, donde el plan puede tener decenas de unidades, el contorno oscuro es
      // lo que deja ver de un vistazo qué parte del distrito entra al programa.
      .attr("stroke", (c) => {
        const u = unidadDeCelda(c.punto.sed);
        if (estado.nivel === "subestaciones") {
          return seleccionadas.has(u.id) ? "var(--plan-borde)" : null;
        }
        return color(u.indice);
      })
      .attr("stroke-width", (c) =>
        estado.nivel === "subestaciones" && seleccionadas.has(unidadDeCelda(c.punto.sed).id)
          ? 1.5 : null)
      .classed("apagada", (c) => hayBusqueda && !coincide(unidadDeCelda(c.punto.sed)))
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

    capaContornos.selectAll("path.contorno-distrito")
      .data([geometria.envolvente])
      .join("path")
      .attr("class", "contorno-distrito")
      .attr("d", (p) => camino(p));

    capaPuntos.selectAll("circle.punto-no-expuesto")
      .data(geometria.noExpuestos)
      .join("circle")
      .attr("class", "punto-no-expuesto")
      .attr("cx", (p) => p[0]).attr("cy", (p) => p[1]).attr("r", 1.5);

    // Marca numerada sobre las unidades que entran al plan. Cada unidad se ancla en la
    // mayor de sus celdas, que es la que con más seguridad contiene a su propio centroide.
    const mejorCelda = new Map();
    for (const celda of geometria.celdas) {
      const u = unidadDeCelda(celda.punto.sed);
      if (!seleccionadas.has(u.id)) continue;
      const area = Math.abs(d3.polygonArea(celda.camino));
      const previa = mejorCelda.get(u.id);
      if (!previa || area > previa.area) mejorCelda.set(u.id, { celda, area, unidad: u });
    }
    // Numerar las decenas de unidades de un plan largo llena el mapa de círculos y deja de
    // informar. Se numeran solo las primeras y el resto del plan se reconoce por su
    // contorno.
    const marcas = Array.from(mejorCelda.values())
      .sort((a, b) => a.unidad.puesto - b.unidad.puesto)
      .slice(0, MAX_MARCAS)
      .map(({ celda, unidad }) => {
        const centro = d3.polygonCentroid(celda.camino);
        return { id: unidad.id, puesto: unidad.puesto, x: centro[0], y: centro[1] };
      });

    const grupos = capaPlan.selectAll("g.marca").data(marcas, (m) => m.id)
      .join((entrar) => {
        const g = entrar.append("g").attr("class", "marca");
        g.append("circle").attr("class", "marca-plan-fondo").attr("r", 9);
        g.append("text").attr("class", "marca-plan")
          .attr("text-anchor", "middle").attr("dy", "0.34em");
        return g;
      });
    grupos.attr("transform", (m) => `translate(${m.x},${m.y})`);
    grupos.select("text").text((m) => m.puesto);

    dibujarEtiquetas(marcas);
  }

  // Etiquetas directas de las unidades del plan, colocadas en el margen derecho con una
  // línea guía. Se separan verticalmente para que no se pisen, y se omiten cuando el plan
  // es tan largo que el margen no alcanza o cuando la pantalla es estrecha.
  function dibujarEtiquetas(marcas) {
    const capa = capaPlan.selectAll("g.capa-etiquetas").data([0])
      .join("g").attr("class", "capa-etiquetas");
    const alturaFila = 17;
    const caben = Math.floor((geometria.alto - 20) / alturaFila);
    const mostrar = geometria.reserva > 0 && marcas.length <= Math.min(caben, MAX_MARCAS);
    if (!mostrar) {
      capa.selectAll("*").remove();
      return;
    }

    const x = Math.min(geometria.bordeDerecho + 26, geometria.ancho - geometria.reserva + 24);
    const ordenadas = marcas.slice().sort((a, b) => a.y - b.y);
    let anterior = -Infinity;
    for (const m of ordenadas) {
      m.yEtiqueta = Math.max(m.y, anterior + alturaFila);
      anterior = m.yEtiqueta;
    }
    const exceso = anterior - (geometria.alto - 10);
    if (exceso > 0) ordenadas.forEach((m) => { m.yEtiqueta -= exceso; });

    const g = capa.selectAll("g.etiqueta").data(ordenadas, (m) => m.id)
      .join((entrar) => {
        const e = entrar.append("g").attr("class", "etiqueta");
        e.append("path").attr("class", "guia-etiqueta");
        e.append("text").attr("class", "texto-etiqueta").attr("dy", "0.34em");
        return e;
      });
    g.select("path").attr("d", (m) =>
      `M${m.x},${m.y}L${x - 8},${m.yEtiqueta}`);
    g.select("text").attr("x", x).attr("y", (m) => m.yEtiqueta)
      .text((m) => `${m.puesto}. ${m.id}`);
  }

  /* ------------------------------------------------------------------ leyenda */

  function dibujarLeyenda() {
    const ancho = 360, alto = 46, barra = 14;
    const svg = d3.select("#leyenda").selectAll("svg").data([0]).join("svg")
      .attr("viewBox", `0 0 ${ancho} ${alto}`)
      .attr("role", "img")
      .attr("aria-label", "Escala de color del índice de criticidad, de menor a mayor");
    svg.selectAll("*").remove();

    const pasos = escalaColor.range();
    const paso = (ancho - 8) / pasos.length;
    svg.selectAll("rect").data(pasos).join("rect")
      .attr("x", (_, i) => 4 + i * paso).attr("y", 14)
      .attr("width", paso).attr("height", barra)
      .attr("fill", (c) => c);

    const [lo, hi] = escalaColor.domain();
    svg.append("text").attr("class", "escala-barra").attr("x", 4).attr("y", 10)
      .text("Menor criticidad");
    svg.append("text").attr("class", "escala-barra").attr("x", ancho - 4).attr("y", 10)
      .attr("text-anchor", "end").text("Mayor criticidad");
    svg.append("text").attr("class", "escala-barra").attr("x", 4).attr("y", alto - 3)
      .text(coma(lo, 0));
    svg.append("text").attr("class", "escala-barra").attr("x", ancho - 4)
      .attr("y", alto - 3).attr("text-anchor", "end").text(coma(hi, 0));
    svg.append("text").attr("class", "escala-barra").attr("x", ancho / 2)
      .attr("y", alto - 3).attr("text-anchor", "middle")
      .text("Índice de criticidad, de 0 a 100");
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

    tr.append("td").text((d) => d.puesto);
    tr.append("td").attr("class", "celda-id").html((d) =>
      estado.nivel === "alimentadores"
        ? `${d.id}<span class="celda-sub">${d.sed_aereas} subestaciones aéreas</span>`
        : `${d.id}<span class="celda-sub">${d.alimentador}</span>`);
    // La cifra va fuera de la barra y no encima: superpuesta perdería contraste justo en
    // los valores altos, que son los que más importa poder leer.
    tr.append("td").html((d) => {
      const ancho = Math.max(4, Math.round(d.indice));
      return '<div class="indice-celda">' +
             `<span class="barra-fondo"><span class="barra-valor" style="width:${ancho}%;background:${color(d.indice)}"></span></span>` +
             `<span class="barra-texto">${coma(d.indice, 0)}</span></div>`;
    });
    tr.append("td").attr("class", "num").text((d) => miles(d.clientes));

    $("#lista-nota").textContent =
      `${filas.length} ${etiquetaNivel()} del piloto. Las ${Math.min(estado.corte, filas.length)} ` +
      `de mayor índice entran al plan del trimestre.`;
  }

  /* ------------------------------------------------------------------ resumen */

  function dibujarResumen() {
    const sel = seleccion();
    $("#kpi-unidades").textContent = sel.length;
    $("#kpi-unidades-et").textContent =
      estado.nivel === "alimentadores" ? "Alimentadores en el plan" : "Subestaciones en el plan";
    $("#kpi-clientes").textContent = miles(d3.sum(sel, (d) => d.clientes));
    $("#kpi-kva").textContent = miles(d3.sum(sel, (d) => d.kva));
    $("#kpi-indice").textContent = sel.length ? coma(sel[sel.length - 1].indice, 0) : "-";
  }

  /* ------------------------------------------------------------------- ficha */

  const ficha = $("#ficha");

  function claveActiva() {
    return estado.fijado || estado.activo;
  }

  function buscarUnidad(id) {
    return porAlimentador.get(id) || porSubestacion.get(id) || null;
  }

  function activar(id, evento) {
    estado.activo = id;
    if (evento) mostrarFicha(id, evento);
    pintarMapa();
    d3.select("#tabla-cuerpo").selectAll("tr").classed("activa", (d) => d.id === claveActiva());
    dibujarDetalle();
  }

  function desactivar() {
    estado.activo = null;
    ficha.hidden = true;
    pintarMapa();
    d3.select("#tabla-cuerpo").selectAll("tr").classed("activa", (d) => d.id === claveActiva());
    dibujarDetalle();
  }

  function fijar(id) {
    estado.fijado = estado.fijado === id ? null : id;
    activar(id, null);
  }

  function mostrarFicha(id, evento) {
    const u = buscarUnidad(id);
    if (!u) return;
    const enPlan = clavesSeleccionadas().has(u.id);
    const sub = estado.nivel === "alimentadores"
      ? `${u.sed_aereas} subestaciones aéreas expuestas`
      : `Alimentador ${u.alimentador}`;
    ficha.innerHTML =
      `<h3>${u.id}</h3><p class="ficha-sub">${sub}</p>` +
      `<p class="ficha-indice" style="color:${color(u.indice)}">${coma(u.indice, 0)}<span style="font-size:11px;color:var(--tinta-3)"> / 100, puesto ${u.puesto}</span></p>` +
      "<dl>" +
      `<dt>Riesgo a 3 meses</dt><dd>${pct(u.probabilidad)}</dd>` +
      `<dt>Sin poda</dt><dd>${miles(u.meses_sin_poda)} meses</dd>` +
      `<dt>Clientes</dt><dd>${miles(u.clientes)}</dd>` +
      `<dt>Potencia</dt><dd>${miles(u.kva)} kVA</dd>` +
      "</dl>" +
      (enPlan ? '<span class="pastilla">Entra al plan</span>' : "");
    ficha.hidden = false;
    moverFicha(evento);
  }

  function moverFicha(evento) {
    if (ficha.hidden || !evento) return;
    const caja = $("#mapa-caja").getBoundingClientRect();
    const x = evento.clientX - caja.left;
    const y = evento.clientY - caja.top;
    const ancho = ficha.offsetWidth, alto = ficha.offsetHeight;
    let izq = x + 14, arr = y + 14;
    if (izq + ancho > caja.width) izq = Math.max(4, x - ancho - 14);
    if (arr + alto > caja.height) arr = Math.max(4, y - alto - 14);
    ficha.style.left = izq + "px";
    ficha.style.top = arr + "px";
  }

  /* ----------------------------------------------------------------- detalle */

  function dibujarDetalle() {
    const contenedor = $("#detalle");
    const u = buscarUnidad(claveActiva());
    if (!u) {
      contenedor.innerHTML =
        '<p class="detalle-vacio">Ninguna unidad seleccionada. Pase el puntero sobre el mapa o la lista para ver su composición, y haga clic para fijarla.</p>';
      return;
    }
    const alimentador = estado.nivel === "alimentadores" ? u : porAlimentador.get(u.alimentador);
    const componentes = Object.entries(u.componentes)
      .map(([nombre, valor]) =>
        `<div class="componente"><span>${nombre}</span><span><strong>${coma(valor, 0)}</strong></span>` +
        `<span class="componente-barra"><span style="width:${Math.max(2, valor)}%"></span></span></div>`)
      .join("");
    const motivos = (alimentador && alimentador.motivos && alimentador.motivos.length)
      ? alimentador.motivos.map((m) => `<li>${m}</li>`).join("")
      : "<li>Sin razones destacadas por el modelo</li>";
    const identidad = estado.nivel === "alimentadores"
      ? `<dt>Subestaciones aéreas</dt><dd>${u.sed_aereas}</dd>`
      : `<dt>Alimentador</dt><dd>${u.alimentador}</dd><dt>Dirección</dt><dd style="text-align:left">${u.direccion}</dd>`;

    contenedor.innerHTML = `
      <div class="bloque">
        <h3>${u.id}, puesto ${u.puesto} de ${unidades().length}</h3>
        <dl>
          <dt>Índice de criticidad</dt><dd><strong>${coma(u.indice, 0)}</strong> de 100</dd>
          <dt>Riesgo estimado a 3 meses</dt><dd>${pct(u.probabilidad)}</dd>
          <dt>Meses desde la última poda</dt><dd>${miles(u.meses_sin_poda)}</dd>
          <dt>Clientes de baja tensión</dt><dd>${miles(u.clientes)}</dd>
          <dt>Potencia instalada</dt><dd>${miles(u.kva)} kVA</dd>
          ${identidad}
        </dl>
      </div>
      <div class="bloque">
        <h3>De qué se compone el índice</h3>
        ${componentes}
      </div>
      <div class="bloque">
        <h3>Por qué está en esta posición</h3>
        <ol class="motivos">${motivos}</ol>
        <dl style="margin-top:8px">
          <dt>Eventos históricos del alimentador</dt><dd>${alimentador ? alimentador.eventos_historicos : "-"}</dd>
          <dt>Eventos del último año</dt><dd>${alimentador ? alimentador.eventos_12m : "-"}</dd>
          <dt>SAIDI de los últimos 12 meses</dt><dd>${alimentador ? coma(alimentador.saidi_ltm, 2) : "-"}</dd>
        </dl>
      </div>`;
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
    dibujarLeyenda();
    dibujarLista();
    dibujarResumen();
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
    pintarMapa();
    dibujarLista();
  });

  $("#descargar").addEventListener("click", descargarCsv);

  $("#boton-tema").addEventListener("click", function () {
    const actual = document.documentElement.getAttribute("data-theme");
    const oscuro = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const siguiente = actual ? (actual === "dark" ? "light" : "dark") : (oscuro ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", siguiente);
    actualizar();
  });

  let temporizador = null;
  window.addEventListener("resize", () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => actualizar({ regeometrizar: true }), 140);
  });

  /* ------------------------------------------------------------------ arranque */

  $("#ventana").textContent = META.ventana;
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

  ajustarCorte();
  construirEscala();
  dibujarMapa();
  dibujarLeyenda();
  dibujarLista();
  dibujarResumen();
  dibujarDetalle();
})();
