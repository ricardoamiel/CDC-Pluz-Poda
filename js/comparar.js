/* Comparación de distritos. Pluz Energía y UTEC, curso DS5045.

   Pestaña pedida en la reunión N°3: poner el piloto de Los Olivos al lado de otro distrito
   de Lima Norte, con el mismo modelo, los mismos componentes y los mismos pesos.

   Decisiones que conviene conocer antes de leer el código:

   1. Escala de color fija de 0 a 100 en los dos mapas. El índice es un percentil dentro de
      cada distrito, de modo que el color compara posiciones relativas. Una escala por
      distrito haría que el mismo tono significara cifras distintas en cada mapa.
   2. Lo que sí es comparable entre distritos en términos absolutos (riesgo estimado, SAIDI,
      interrupciones, cortes por vegetación) va en el panel de cifras, una fila por
      indicador y cada fila con su propia escala: son magnitudes distintas.
   3. El mapa repite la construcción del piloto: Voronoi de las subestaciones aéreas,
      recortado al límite real del distrito, con las costuras entre celdas de un mismo
      alimentador apagadas y el contorno del plan dibujado aparte.
*/

(function () {
  "use strict";

  const DATOS = window.DATOS_DISTRITOS;
  const GEO = window.GEO_DISTRITOS;
  if (!DATOS || !GEO) return;

  const PILOTO = "LOL";
  const RAMPA = ["--idx-1", "--idx-2", "--idx-3", "--idx-4", "--idx-5", "--idx-6", "--idx-7"];
  const MAX_MARCAS = 5;

  const parametros = new URLSearchParams(location.search);
  const otros = DATOS.orden.filter((c) => c !== PILOTO);
  const estado = {
    nivel: parametros.get("nivel") === "subestaciones" ? "subestaciones" : "alimentadores",
    // San Juan de Lurigancho abre por defecto: es el distrito con más evidencia.
    distrito: otros.includes(parametros.get("distrito")) ? parametros.get("distrito") : otros[0],
    fondo: "coropletico",
  };
  // Postes de media tensión por distrito, con su subestación más cercana.
  const POSTES = (window.POSTES_MT && window.POSTES_MT.distritos) || {};
  // Lo que hace falta para acercar cada mapa a una unidad desde su lista.
  const mapas = {};

  const $ = (sel) => document.querySelector(sel);
  const miles = (v) => (v === null || v === undefined ? "-"
    : String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, "."));
  const coma = (v, d = 1) => (v === null || v === undefined ? "-" : v.toFixed(d).replace(".", ","));
  // Igual que en la pestaña del piloto: cero meses es una poda en el mismo mes del corte, y
  // un alimentador fuera del registro de poda no tiene reloj.
  function textoPoda(u) {
    if (u.sin_registro_poda) return "sin poda registrada";
    if (u.meses_sin_poda === 0) return "podado este mes";
    return `${miles(u.meses_sin_poda)} meses`;
  }
  const pct = (v) => (v === null || v === undefined ? "-" : Math.round(v * 100) + " %");

  function leerRampa() {
    const estilo = getComputedStyle(document.querySelector(".viz-root"));
    return RAMPA.map((v) => estilo.getPropertyValue(v).trim() || "#cccccc");
  }
  let escala = null;
  const construirEscala = () => {
    escala = d3.scaleQuantize().domain([0, 100]).range(leerRampa());
  };

  /* ---------------------------------------------------------------- selector */

  const selector = $("#distrito");
  selector.innerHTML = otros.map((c) =>
    `<option value="${c}">${DATOS.distritos[c].meta.distrito}</option>`).join("");
  selector.value = estado.distrito;
  selector.addEventListener("change", () => {
    estado.distrito = selector.value;
    const p = new URLSearchParams(location.search);
    p.set("distrito", estado.distrito);
    history.replaceState(null, "", location.pathname + "?" + p);
    dibujar();
  });

  function marcarNivel() {
    d3.selectAll("#nivel-cmp button")
      .classed("activo", function () { return this.dataset.nivel === estado.nivel; })
      .attr("aria-checked", function () { return String(this.dataset.nivel === estado.nivel); });
  }
  d3.selectAll("#fondo-cmp button").on("click", function () {
    estado.fondo = this.dataset.fondo;
    d3.selectAll("#fondo-cmp button")
      .classed("activo", function () { return this.dataset.fondo === estado.fondo; })
      .attr("aria-checked", function () { return String(this.dataset.fondo === estado.fondo); });
    dibujar();
  });

  d3.selectAll("#nivel-cmp button").on("click", function () {
    estado.nivel = this.dataset.nivel;
    marcarNivel();
    dibujar();
  });
  marcarNivel();

  /* ------------------------------------------------------------------ cifras */

  // Cada fila es un indicador y lleva su propia escala, porque son magnitudes distintas.
  // Las dos barras de una fila sí comparten escala: es lo que se compara.
  const INDICADORES = [
    { clave: "sed_aereas", nombre: "Subestaciones aéreas, expuestas a vegetación", fmt: miles },
    { clave: "clientes_expuestos", nombre: "Clientes de baja tensión en red aérea", fmt: miles },
    { clave: "riesgo_medio", nombre: "Probabilidad media de corte por vegetación a 3 meses, por alimentador", fmt: pct },
    { clave: "saidi_ltm", nombre: "SAIDI del último año, en minutos", fmt: (v) => `${coma(v, 2)} min` },
    { clave: "interrupciones_12m", nombre: "Interrupciones por todas las causas, último año", fmt: miles },
    { clave: "cortes_vegetacion_12m", nombre: "Interrupciones por vegetación y no ubicadas, último año", fmt: miles },
    { clave: "podas_12m", nombre: "Cantidad de mantenimientos por vegetación, último año",
      fmt: miles, nota: "Podas registradas por Pluz en las subestaciones del distrito." },
    { clave: "cortes_veg_por_100_sed", nombre: "Interrupciones por vegetación por cada 100 subestaciones aéreas, desde enero de 2024",
      fmt: miles,
      nota: "Aproximación a cuánta vegetación hay: mientras no exista un inventario de arbolado, se mide por sus efectos." },
    { clave: "meses_sin_poda_mediana", nombre: "Meses desde la última poda, mediana por alimentador", fmt: miles },
  ];

  function dibujarCifras() {
    const a = DATOS.distritos[PILOTO].meta;
    const b = DATOS.distritos[estado.distrito].meta;
    const filas = INDICADORES.map((ind) => {
      const va = a.resumen[ind.clave], vb = b.resumen[ind.clave];
      const max = Math.max(va || 0, vb || 0) || 1;
      return `
        <div class="cifra-fila">
          <div class="cifra-nombre">${ind.nombre}${ind.nota ? `<span class="cifra-nota">${ind.nota}</span>` : ""}</div>
          <div class="cifra-barras">
            <div class="cifra-barra"><span class="cifra-quien quien-a">${a.distrito}</span>
              <span class="cifra-pista"><i class="cifra-a" style="width:${(100 * (va || 0)) / max}%"></i></span>
              <b>${ind.fmt(va)}</b></div>
            <div class="cifra-barra"><span class="cifra-quien quien-b">${b.distrito}</span>
              <span class="cifra-pista"><i class="cifra-b" style="width:${(100 * (vb || 0)) / max}%"></i></span>
              <b>${ind.fmt(vb)}</b></div>
          </div>
        </div>`;
    }).join("");
    $("#cifras").innerHTML = filas;
    $("#cifras-leyenda").innerHTML =
      `<span><i class="cifra-a"></i>${a.distrito}</span><span><i class="cifra-b"></i>${b.distrito}</span>`;
  }

  /* -------------------------------------------------------------------- mapa */

  // d3 trabaja sobre la esfera y espera los anillos exteriores en sentido horario. Los de
  // OpenStreetMap vienen en sentido antihorario, y d3 los leería como el planeta entero
  // menos el distrito. Se corrige comprobando el área en lugar de suponer el sentido.
  function geoDistrito(codigo) {
    const anillos = GEO.limites[codigo].map((anillo) => {
      const poligono = { type: "Polygon", coordinates: [anillo] };
      return d3.geoArea(poligono) > 2 * Math.PI ? anillo.slice().reverse() : anillo;
    });
    return { type: "MultiPolygon", coordinates: anillos.map((a) => [a]) };
  }

  const lado = (a, b, p) => (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
  function recortarSegmento(p, q, recorte) {
    const centro = d3.polygonCentroid(recorte);
    const orientado = lado(recorte[0], recorte[1], centro) >= 0 ? recorte : recorte.slice().reverse();
    let t0 = 0, t1 = 1;
    const dx = q[0] - p[0], dy = q[1] - p[1];
    for (let i = 0; i < orientado.length; i++) {
      const a = orientado[i], b = orientado[(i + 1) % orientado.length];
      const nx = -(b[1] - a[1]), ny = b[0] - a[0];
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

  // Aristas de Voronoi que separan dos claves distintas, leídas de la triangulación de
  // Delaunay. Es la misma construcción del mapa del piloto.
  function fronteras(geo, claveDe) {
    const { delaunay, voronoi, marco, puntos } = geo;
    const { triangles, halfedges } = delaunay;
    const cc = voronoi.circumcenters;
    const salida = [];
    for (let e = 0; e < halfedges.length; e++) {
      const opuesta = halfedges[e];
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
        const k = triangles[e % 3 === 0 ? e + 2 : e - 1];
        const a = puntos[i], b = puntos[j], c = puntos[k];
        let nx = -(b.y - a.y), ny = b.x - a.x;
        const largo = Math.hypot(nx, ny) || 1;
        nx /= largo; ny /= largo;
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        if (nx * (mx - c.x) + ny * (my - c.y) < 0) { nx = -nx; ny = -ny; }
        q = [p[0] + nx * 1e5, p[1] + ny * 1e5];
      }
      const seg = recortarSegmento(p, q, marco);
      if (seg) salida.push(seg);
    }
    return salida;
  }

  const caminoSegmentos = (segs) => segs.map(([a, b]) => `M${a[0]},${a[1]}L${b[0]},${b[1]}`).join("");

  function dibujarMapa(lado_, codigo) {
    const datos = DATOS.distritos[codigo];
    const meta = datos.meta;
    const porAlim = new Map(datos.alimentadores.map((d) => [d.id, d]));
    const seds = datos.subestaciones.filter((d) => porAlim.has(d.alimentador));
    const porAlimentador = estado.nivel === "alimentadores";
    const unidad = (s) => (porAlimentador ? porAlim.get(s.alimentador) : s);
    const corte = porAlimentador ? meta.k_alimentadores : meta.capacidad_mes;
    const unidades = porAlimentador ? datos.alimentadores : datos.subestaciones;
    const enPlan = new Set(unidades.slice(0, corte).map((d) => d.id));

    const caja = $(`#caja-mapa-${lado_}`);
    const ancho = Math.max(280, caja.clientWidth);
    const geo = geoDistrito(codigo);
    // Mercator sin rotación, la de las teselas del fondo satelital.
    const proyeccion = d3.geoMercator();
    // La altura la decide la forma del distrito, con un tope para que dos distritos muy
    // distintos no descuadren la página: Carabayllo es alto y Callao es ancho.
    proyeccion.fitWidth(ancho - 20, geo);
    const [[, y0], [, y1]] = d3.geoPath(proyeccion).bounds(geo);
    const alto = Math.round(Math.min(Math.max(y1 - y0 + 20, 320), 560));
    proyeccion.fitExtent([[10, 10], [ancho - 10, alto - 10]], geo);
    const ruta = d3.geoPath(proyeccion);

    const puntos = seds.map((s) => {
      const p = proyeccion([s.lon, s.lat]);
      return { sed: s, x: p[0], y: p[1] };
    });
    const delaunay = d3.Delaunay.from(puntos, (p) => p.x, (p) => p.y);
    const voronoi = delaunay.voronoi([0, 0, ancho, alto]);
    const marco = [[0, 0], [ancho, 0], [ancho, alto], [0, alto]];
    const g = { delaunay, voronoi, marco, puntos };

    const raiz = d3.select(`#mapa-${lado_}`)
      .attr("viewBox", `0 0 ${ancho} ${alto}`).attr("width", ancho).attr("height", alto);
    raiz.selectAll("*").remove();
    const idRecorte = `recorte-${lado_}`;
    raiz.append("defs").append("clipPath").attr("id", idRecorte)
      .append("path").attr("d", ruta(geo));
    // Todo va en un lienzo que se acerca, igual que en el piloto (reunión N°3, punto 8).
    const svg = raiz.append("g").attr("class", "lienzo")
      .classed("satelital", estado.fondo === "satelital");
    const capaSatelite = svg.append("g").attr("class", "capa-satelite");
    const recortada = svg.append("g").attr("clip-path", `url(#${idRecorte})`);

    const color = (u) => (u ? escala(u.indice) : "#cccccc");
    recortada.append("g").selectAll("path")
      .data(puntos.map((p, i) => ({ p, camino: voronoi.cellPolygon(i) })).filter((c) => c.camino))
      .join("path")
      .attr("class", "celda")
      .attr("d", (c) => "M" + c.camino.join("L") + "Z")
      .attr("fill", (c) => color(unidad(c.p.sed)))
      .attr("stroke", (c) => color(unidad(c.p.sed)))
      .on("pointerenter", (evento, c) => mostrarFicha(lado_, unidad(c.p.sed), evento, enPlan))
      .on("pointermove", (evento) => moverFicha(lado_, evento))
      .on("pointerleave", () => { $(`#ficha-${lado_}`).hidden = true; });

    recortada.append("path").attr("class", "borde-alimentador")
      .classed("tenue", !porAlimentador)
      .attr("d", caminoSegmentos(fronteras(g, (i) => puntos[i].sed.alimentador)));
    const planSegs = fronteras(g, (i) => (enPlan.has(unidad(puntos[i].sed).id) ? 1 : 0));
    recortada.append("path").attr("class", "contorno-plan-funda").attr("d", caminoSegmentos(planSegs));
    recortada.append("path").attr("class", "contorno-plan").attr("d", caminoSegmentos(planSegs));

    recortada.append("g").selectAll("circle")
      .data(datos.no_expuestas)
      .join("circle").attr("class", "punto-no-expuesto")
      .attr("cx", (d) => proyeccion([d.lon, d.lat])[0])
      .attr("cy", (d) => proyeccion([d.lon, d.lat])[1]).attr("r", 1);

    const capaReferencia = svg.append("g").attr("class", "capa-referencia");

    // Subestaciones aéreas como punto y postes de media tensión: se ven al acercar.
    const capaDetalle = svg.append("g").attr("class", "capa-postes").attr("display", "none");
    const postes = (POSTES[codigo] || []).map(([poste, lon, lat, sed]) => {
      const q = proyeccion([lon, lat]);
      return { poste, sed, x: q[0], y: q[1] };
    });
    capaDetalle.selectAll("circle.poste").data(postes).join("circle").attr("class", "poste")
      .attr("cx", (d) => d.x).attr("cy", (d) => d.y)
      .append("title").text((d) => `Poste ${d.poste}` + (d.sed ? `, subestación más cercana ${d.sed}` : ""));
    capaDetalle.selectAll("circle.punto-sed").data(puntos).join("circle").attr("class", "punto-sed")
      .attr("cx", (d) => d.x).attr("cy", (d) => d.y)
      .append("title").text((d) => `Subestación ${d.sed.id}, alimentador ${d.sed.alimentador}`);

    svg.append("path").attr("class", "contorno-distrito").attr("d", ruta(geo));

    // Marcas numeradas en los primeros puestos. Cada unidad se ancla en la subestación más
    // cercana al centro de sus subestaciones, que siempre está dentro del distrito.
    const marcas = unidades.slice(0, MAX_MARCAS).map((u) => {
      const propios = puntos.filter((p) => unidad(p.sed).id === u.id);
      if (!propios.length) return null;
      const cx = d3.mean(propios, (p) => p.x), cy = d3.mean(propios, (p) => p.y);
      const ancla = propios.reduce((m, p) =>
        Math.hypot(p.x - cx, p.y - cy) < Math.hypot(m.x - cx, m.y - cy) ? p : m, propios[0]);
      return { puesto: u.puesto, x: ancla.x, y: ancla.y };
    }).filter(Boolean);
    const gm = svg.append("g").selectAll("g").data(marcas).join("g")
      .attr("class", "marca")
      .attr("transform", (m) => `translate(${m.x},${m.y})`);
    gm.append("circle").attr("class", "marca-plan-fondo").attr("r", 9);
    gm.append("text").attr("class", "marca-plan").attr("text-anchor", "middle")
      .attr("dy", "0.34em").text((m) => m.puesto);

    const etiqueta = porAlimentador ? "alimentadores" : "subestaciones";
    $(`#nota-mapa-${lado_}`).textContent =
      `${unidades.length} ${etiqueta} con red aérea. El plan toma ${articulo()} ${corte} de mayor ` +
      `índice` + (porAlimentador ? "." :
        meta.capacidad_regla === "registro de poda 2025"
          ? ", la capacidad de poda que el distrito ejecutó en 2025."
          : ", la misma proporción que el piloto, porque el registro de poda del distrito está incompleto.");
    dibujarTop(lado_, unidades, corte);

    const ajustar = (t) => {
      svg.attr("transform", t);
      gm.attr("transform", (m) => `translate(${m.x},${m.y}) scale(${1 / t.k})`);
      capaDetalle.attr("display", t.k >= 2.5 ? null : "none");
      capaDetalle.selectAll("circle.poste").attr("r", 2 / t.k);
      capaDetalle.selectAll("circle.punto-sed").attr("r", 3.5 / t.k);
      if (window.TESELAS) {
        window.TESELAS.actualizar({ base: capaSatelite, referencia: capaReferencia, proyeccion,
          transform: t, ancho, alto, activo: estado.fondo === "satelital" });
      }
    };
    let pendiente = null;
    const zoom = d3.zoom().scaleExtent([1, 40])
      .extent([[0, 0], [ancho, alto]]).translateExtent([[0, 0], [ancho, alto]])
      .filter((e) => (e.type !== "wheel" || e.ctrlKey || e.metaKey) && !e.button)
      .on("zoom", (e) => {
        if (pendiente) cancelAnimationFrame(pendiente);
        const t = e.transform;
        pendiente = requestAnimationFrame(() => ajustar(t));
      });
    raiz.call(zoom).on("dblclick.zoom", null);
    ajustar(d3.zoomIdentity);
    const previo = mapas[lado_];
    mapas[lado_] = { raiz, zoom, puntos, postes, ancho, alto, porAlimentador, recortada, elegida: null,
                     codigo, nivel: estado.nivel, unidades, enPlan };
    // Al cambiar de fondo se redibuja el mapa: la unidad elegida se conserva si sigue siendo
    // el mismo distrito y el mismo nivel.
    $(`#elegida-${lado_}`).hidden = true;
    if (previo && previo.elegida && previo.codigo === codigo && previo.nivel === estado.nivel) {
      acercarUnidad(lado_, previo.elegida);
    }
    $(`#atribucion-${lado_}`).hidden = estado.fondo !== "satelital";
    $(`#atribucion-${lado_}`).textContent = window.TESELAS ? window.TESELAS.ATRIBUCION : "";
  }

  const articulo = () => (estado.nivel === "alimentadores" ? "los" : "las");

  function dibujarTop(lado_, unidades, corte) {
    const filas = unidades.slice(0, 8).map((u) => `
      <tr class="${u.puesto <= corte ? "en-plan" : "fuera"}" data-id="${u.id}" tabindex="0" title="Clic para verla en el mapa">
        <td class="celda-puesto">${u.puesto}</td>
        <td class="celda-id">${u.id}<span class="celda-sub">${estado.nivel === "alimentadores"
          ? `${u.sed_aereas} subestaciones aéreas` : `alimentador ${u.alimentador}`}</span></td>
        <td><div class="indice-celda"><span class="barra-fondo"><span class="barra-valor" style="width:${Math.max(4, u.indice)}%;background:${escala(u.indice)}"></span></span><span class="barra-texto">${coma(u.indice, 0)}</span></div></td>
        <td class="num">${pct(u.probabilidad)}</td>
      </tr>`).join("");
    $(`#top-${lado_}`).innerHTML = `
      <table class="tabla">
        <caption class="oculto">Primeras unidades del plan del distrito</caption>
        <thead><tr><th scope="col">N°</th><th scope="col">Unidad</th><th scope="col">Índice</th><th scope="col" class="num" title="Probabilidad de al menos un corte por vegetación en los próximos 3 meses">Prob. de corte, 3 meses</th></tr></thead>
        <tbody>${filas}</tbody>
      </table>`;
    d3.selectAll(`#top-${lado_} tbody tr`)
      .on("click", function () { acercarUnidad(lado_, this.dataset.id); })
      .on("keydown", function (evento) {
        if (evento.key === "Enter" || evento.key === " ") {
          evento.preventDefault();
          acercarUnidad(lado_, this.dataset.id);
        }
      });
  }

  // Clic en una fila de la lista de un distrito: su mapa va a la unidad, con sus
  // subestaciones y postes, y la celda queda marcada. Otro clic en la misma fila la suelta.
  function acercarUnidad(lado_, id) {
    const m = mapas[lado_];
    if (!m) return;
    const soltar = m.elegida === id;
    m.elegida = soltar ? null : id;
    d3.selectAll(`#top-${lado_} tbody tr`).classed("activa", function () { return this.dataset.id === m.elegida; });
    m.recortada.selectAll("path.celda").classed("resaltado", (c) =>
      Boolean(m.elegida) && (m.porAlimentador ? c.p.sed.alimentador : c.p.sed.id) === m.elegida);
    tarjetaElegida(lado_);
    if (soltar) {
      m.raiz.transition().duration(500).call(m.zoom.transform, d3.zoomIdentity);
      return;
    }
    const seds = m.puntos.filter((p) => (m.porAlimentador ? p.sed.alimentador : p.sed.id) === id);
    const ids = new Set(seds.map((p) => p.sed.id));
    const pts = seds.concat(m.postes.filter((p) => ids.has(p.sed)));
    if (!pts.length) return;
    const [x0, x1] = d3.extent(pts, (p) => p.x), [y0, y1] = d3.extent(pts, (p) => p.y);
    const kMax = estado.fondo === "satelital" ? 18 : 7;
    const kMin = m.porAlimentador ? 2 : 4;
    const k = Math.min(kMax, Math.max(kMin, 0.8 * Math.min(m.ancho / Math.max(x1 - x0, 1), m.alto / Math.max(y1 - y0, 1))));
    const t = d3.zoomIdentity.translate(m.ancho / 2, m.alto / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    m.raiz.transition().duration(650).call(m.zoom.transform, t);
  }

  // Cifras de la unidad elegida bajo su mapa, con los mismos cinco datos de la etiqueta:
  // con una unidad elegida en cada distrito se comparan lado a lado.
  function tarjetaElegida(lado_) {
    const m = mapas[lado_];
    const caja = $(`#elegida-${lado_}`);
    const u = m.elegida ? m.unidades.find((x) => x.id === m.elegida) : null;
    caja.hidden = !u;
    if (!u) return;
    caja.innerHTML =
      `<div class="elegida-tope"><span class="ficha-chip" style="background:${escala(u.indice)}"></span>` +
      `<b>${u.id}</b><span>puesto ${u.puesto} de ${m.unidades.length}, índice ${coma(u.indice, 0)}` +
      `${m.enPlan.has(u.id) ? ", entra al plan" : ""}</span>` +
      `<button type="button" class="boton boton-sutil" aria-label="Quitar la unidad elegida">×</button></div>` +
      `<dl><dt>Probabilidad de corte por vegetación, 3 meses</dt><dd>${pct(u.probabilidad)}</dd>` +
      `<dt>Sin poda</dt><dd>${textoPoda(u)}</dd>` +
      `<dt>Clientes</dt><dd>${miles(u.clientes)}</dd>` +
      `<dt>SAIDI, último año</dt><dd>${coma(u.saidi_ltm, 2)} min</dd>` +
      `<dt>Interrupciones por vegetación y no ubicadas, último año</dt><dd>${miles(u.eventos_12m)}</dd></dl>`;
    caja.querySelector("button").addEventListener("click", () => acercarUnidad(lado_, u.id));
  }

  function mostrarFicha(lado_, u, evento, enPlan) {
    if (!u) return;
    const ficha = $(`#ficha-${lado_}`);
    const sub = estado.nivel === "alimentadores"
      ? `${u.sed_aereas} subestaciones aéreas`
      : `Alimentador ${u.alimentador}`;
    ficha.innerHTML =
      `<div class="ficha-tope"><h3>${u.id}</h3><span class="ficha-puesto">puesto ${u.puesto}</span></div>` +
      `<p class="ficha-sub">${sub}</p>` +
      `<div class="ficha-indice"><span class="ficha-chip" style="background:${escala(u.indice)}"></span>` +
      `<span class="ficha-indice-num">${coma(u.indice, 0)}</span><span class="ficha-indice-de">índice<br>de 100</span></div>` +
      // Los mismos cinco datos y en el mismo orden que la ficha de la pestaña del piloto.
      `<dl><dt>Probabilidad de corte por vegetación, 3 meses</dt><dd>${pct(u.probabilidad)}</dd>` +
      `<dt>Sin poda</dt><dd>${textoPoda(u)}</dd>` +
      `<dt>Clientes</dt><dd>${miles(u.clientes)}</dd>` +
      `<dt>SAIDI, último año</dt><dd>${coma(u.saidi_ltm, 2)} min</dd>` +
      `<dt>Interrupciones por vegetación y no ubicadas, último año</dt><dd>${miles(u.eventos_12m)}</dd></dl>` +
      (enPlan.has(u.id) ? '<span class="pastilla">Entra al plan</span>' : "");
    ficha.hidden = false;
    moverFicha(lado_, evento);
  }

  function moverFicha(lado_, evento) {
    const ficha = $(`#ficha-${lado_}`);
    if (ficha.hidden) return;
    const caja = $(`#caja-mapa-${lado_}`).getBoundingClientRect();
    const x = evento.clientX - caja.left, y = evento.clientY - caja.top;
    let izq = x + 16, arr = y + 16;
    if (izq + ficha.offsetWidth > caja.width) izq = Math.max(4, x - ficha.offsetWidth - 16);
    if (arr + ficha.offsetHeight > caja.height) arr = Math.max(4, y - ficha.offsetHeight - 16);
    ficha.style.left = izq + "px";
    ficha.style.top = arr + "px";
  }

  function dibujarLeyenda() {
    const ancho = 460, alto = 42, izq = 2, der = ancho - 2;
    const pasos = escala.range();
    const paso = (der - izq) / pasos.length;
    const svg = d3.select("#leyenda-cmp").selectAll("svg").data([0]).join("svg")
      .attr("viewBox", `0 0 ${ancho} ${alto}`).attr("role", "img")
      .attr("aria-label", "Escala de color del índice de criticidad, común a los dos mapas");
    svg.selectAll("*").remove();
    svg.append("text").attr("class", "leyenda-titulo").attr("x", izq).attr("y", 10)
      .text("Índice de criticidad dentro de cada distrito, misma escala en los dos mapas");
    svg.selectAll("rect").data(pasos).join("rect")
      .attr("x", (_, i) => izq + i * paso).attr("y", 16).attr("width", paso).attr("height", 12)
      .attr("fill", (c) => c);
    svg.append("text").attr("class", "leyenda-texto").attr("x", izq).attr("y", 40).text("0 · menos crítico");
    svg.append("text").attr("class", "leyenda-texto").attr("x", der).attr("y", 40)
      .attr("text-anchor", "end").text("más crítico · 100");
  }

  function dibujar() {
    if ($("#vista-comparar").hidden) return;
    construirEscala();
    $("#nombre-b").textContent = DATOS.distritos[estado.distrito].meta.distrito;
    dibujarCifras();
    dibujarMapa("a", PILOTO);
    dibujarMapa("b", estado.distrito);
    dibujarLeyenda();
  }

  window.COMPARADOR = { dibujar };
})();
