/* Tema de las tres páginas (herramienta, benchmark y carga semanal).

   Tres estados, en este orden al pulsar el botón: claro, el del sistema y oscuro. Por
   defecto es claro, aunque el equipo esté en oscuro. La elección se guarda en el navegador y
   vale para las tres páginas, que comparten dirección. El parámetro ?tema=claro, sistema u
   oscuro de la dirección manda sobre lo guardado, para capturas e informes.

   Va en el <head>, antes de dibujar nada, para que la página no parpadee en el otro tema.
   El estilo lo resuelve css/estilos.css: data-theme="light" o "dark" fija el tema, y sin
   atributo se sigue al sistema. Cuando el tema cambia se emite el evento «pluz-tema», que
   las páginas con gráficos usan para redibujar. */
(function () {
  var CLAVE = "pluz-tema";
  var ORDEN = ["claro", "sistema", "oscuro"];
  var raiz = document.documentElement;
  var sistemaOscuro = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function leer() {
    var pedido = new URLSearchParams(location.search).get("tema");
    if (ORDEN.indexOf(pedido) >= 0) return pedido;
    try { var g = localStorage.getItem(CLAVE); if (ORDEN.indexOf(g) >= 0) return g; } catch (e) {}
    return "claro";
  }

  var actual = leer();

  function aplicar() {
    if (actual === "claro") raiz.setAttribute("data-theme", "light");
    else if (actual === "oscuro") raiz.setAttribute("data-theme", "dark");
    else raiz.removeAttribute("data-theme");
  }

  function esOscuro() {
    return actual === "oscuro" || (actual === "sistema" && !!sistemaOscuro && sistemaOscuro.matches);
  }

  var TEXTO = { claro: "Tema claro", sistema: "Tema del sistema", oscuro: "Tema oscuro" };
  var ICONO = { claro: "#i-sol", sistema: "#i-pantalla", oscuro: "#i-luna" };

  function pintarBoton() {
    var b = document.getElementById("boton-tema");
    if (!b) return;
    var siguiente = ORDEN[(ORDEN.indexOf(actual) + 1) % ORDEN.length];
    var uso = b.querySelector("use");
    if (uso) uso.setAttribute("href", ICONO[actual]);
    b.title = TEXTO[actual] + ". Pulse para pasar a " + TEXTO[siguiente].toLowerCase() + ".";
    b.setAttribute("aria-label", b.title);
  }

  function avisar() {
    pintarBoton();
    document.dispatchEvent(new CustomEvent("pluz-tema", { detail: { tema: actual, oscuro: esOscuro() } }));
  }

  aplicar();

  window.PLUZ_TEMA = { actual: function () { return actual; }, esOscuro: esOscuro };

  document.addEventListener("DOMContentLoaded", function () {
    pintarBoton();
    var b = document.getElementById("boton-tema");
    if (b) b.addEventListener("click", function () {
      actual = ORDEN[(ORDEN.indexOf(actual) + 1) % ORDEN.length];
      try { localStorage.setItem(CLAVE, actual); } catch (e) {}
      aplicar();
      avisar();
    });
  });

  // En «sistema», si el equipo cambia de claro a oscuro, la página lo sigue.
  if (sistemaOscuro && sistemaOscuro.addEventListener) {
    sistemaOscuro.addEventListener("change", function () { if (actual === "sistema") avisar(); });
  }
})();
