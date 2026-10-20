/* Fondo satelital de los mapas. Pluz Energía y UTEC, curso DS5045.

   Reunión N°3, puntos 3 y 8: el mapa coroplético ubica la zona pero no la calle. La vista
   satelital pone debajo del índice las imágenes de Esri World Imagery y encima sus capas de
   referencia de vías y nombres, sin clave de acceso. Es el mismo esquema que usamos en el
   mapa del proyecto Frank Arnott.

   Las teselas solo se piden cuando alguien elige la vista satelital: la vista coroplética
   sigue sin hacer ninguna petición de red.

   Requisito: el mapa tiene que usar d3.geoMercator sin rotación, que es la proyección de
   las teselas. A la escala de un distrito no se distingue de la transversa que se usaba.
*/

(function () {
  "use strict";

  const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/";
  const BASE = ["World_Imagery"];
  const REFERENCIA = ["Reference/World_Transportation", "Reference/World_Boundaries_and_Places"];
  const ZOOM_MAXIMO = 19;
  const ATRIBUCION = "Imágenes: Esri, Maxar, Earthstar Geographics y la comunidad de usuarios de SIG";

  // Teselas que cubren el lienzo visible. Se devuelven en coordenadas del lienzo, antes de
  // aplicar el acercamiento, para poder intercalarlas con las capas del mapa.
  function calcular(proyeccion, t, ancho, alto) {
    const S = proyeccion.scale() * t.k;
    const [tx, ty] = proyeccion.translate();
    const X = tx * t.k + t.x, Y = ty * t.k + t.y;
    const mundo = 2 * Math.PI * S;
    const z = Math.max(0, Math.min(ZOOM_MAXIMO, Math.round(Math.log2(mundo / 256))));
    const n = 2 ** z, lado = mundo / n;
    const x0 = X - Math.PI * S, y0 = Y - Math.PI * S;
    const salida = [];
    for (let i = Math.floor(-x0 / lado); i <= Math.floor((ancho - x0) / lado); i++) {
      for (let j = Math.max(0, Math.floor(-y0 / lado)); j <= Math.min(n - 1, Math.floor((alto - y0) / lado)); j++) {
        salida.push({
          z, x: ((i % n) + n) % n, y: j,
          // De pantalla a lienzo: se deshace el acercamiento.
          px: (x0 + i * lado - t.x) / t.k, py: (y0 + j * lado - t.y) / t.k,
          lado: lado / t.k,
        });
      }
    }
    return salida;
  }

  function pintar(capa, servicios, teselas) {
    const datos = teselas.flatMap((t) => servicios.map((s) => ({ ...t, s })));
    capa.selectAll("image")
      .data(datos, (d) => `${d.s}/${d.z}/${d.y}/${d.x}`)
      .join("image")
      .attr("href", (d) => `${ESRI}${d.s}/MapServer/tile/${d.z}/${d.y}/${d.x}`)
      .attr("x", (d) => d.px).attr("y", (d) => d.py)
      // Medio píxel de más para que no se vean juntas entre teselas.
      .attr("width", (d) => d.lado * 1.004).attr("height", (d) => d.lado * 1.004)
      .attr("preserveAspectRatio", "none");
  }

  // Dibuja o borra el fondo y las referencias según el modo.
  function actualizar({ base, referencia, proyeccion, transform, ancho, alto, activo }) {
    if (!activo) {
      base.selectAll("image").remove();
      referencia.selectAll("image").remove();
      return;
    }
    const teselas = calcular(proyeccion, transform, ancho, alto);
    pintar(base, BASE, teselas);
    pintar(referencia, REFERENCIA, teselas);
  }

  window.TESELAS = { actualizar, ATRIBUCION };
})();
