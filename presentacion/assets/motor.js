// Motor de la presentación: láminas de 1280 x 720 escaladas a la ventana, fragmentos que
// aparecen de a uno, contadores animados, foco en la viñeta actual y notas del expositor.
// Teclas: flechas, espacio, AvPág y RePág para avanzar o retroceder; F pantalla completa;
// S notas; T mostrar todo; Inicio y Fin.
(function () {
  "use strict";
  const laminas = Array.from(document.querySelectorAll(".lamina"));
  const escena = document.querySelector(".escena");
  const barra = document.querySelector(".progreso span");
  const contador = document.querySelector(".contador");
  const notas = document.querySelector(".notas");
  let actual = 0;
  let paso = 0;

  // Grupos de fragmentos por lámina: los que comparten data-o aparecen juntos.
  const grupos = laminas.map((l) => {
    const frags = Array.from(l.querySelectorAll(".f"));
    const orden = new Map();
    frags.forEach((f, i) => {
      const clave = f.dataset.o !== undefined ? Number(f.dataset.o) : 1000 + i;
      if (!orden.has(clave)) orden.set(clave, []);
      orden.get(clave).push(f);
    });
    return Array.from(orden.keys()).sort((a, b) => a - b).map((k) => orden.get(k));
  });

  function escalar() {
    const s = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
    escena.style.transform = `translate(-50%, -50%) scale(${s})`;
  }

  // Formato de los documentos: punto para miles y coma para decimales (1.328 y 3,87).
  function formato(v, dec) {
    const [ent, frac] = Math.abs(v).toFixed(dec).split(".");
    const miles = ent.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (v < 0 ? "-" : "") + miles + (frac ? "," + frac : "");
  }

  function contar(el) {
    const fin = Number(el.dataset.valor);
    const dec = Number(el.dataset.dec || 0);
    const pre = el.dataset.pre || "";
    const suf = el.dataset.suf || "";
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.textContent = pre + formato(fin, dec) + suf;
      return;
    }
    const t0 = performance.now();
    const dur = 900;
    function cuadro(t) {
      const x = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - x, 3);
      el.textContent = pre + formato(fin * e, dec) + suf;
      if (x < 1) requestAnimationFrame(cuadro);
    }
    requestAnimationFrame(cuadro);
  }

  function enfocar(l) {
    // En cada figura solo queda visible el último resaltado; los anteriores se apagan.
    l.querySelectorAll(".fig").forEach((fg) => {
      const marcas = Array.from(fg.querySelectorAll(".marca.on"));
      marcas.forEach((m, i) => m.classList.toggle("pasada", i < marcas.length - 1));
    });
    // En las listas con foco, la última viñeta visible queda resaltada y las anteriores se atenúan.
    l.querySelectorAll(".lista-foco").forEach((lista) => {
      const vis = Array.from(lista.querySelectorAll(":scope > .f.on"));
      vis.forEach((v, i) => v.classList.toggle("atenuado", i < vis.length - 1));
    });
  }

  function mostrar(n, p, animar) {
    const cambia = n !== actual;
    if (cambia) {
      laminas[actual].querySelectorAll("video").forEach((v) => v.pause());
    }
    actual = n;
    paso = p;
    laminas.forEach((l, i) => l.classList.toggle("activa", i === n));
    grupos[n].forEach((g, i) => {
      g.forEach((f) => {
        const on = i < p;
        const antes = f.classList.contains("on");
        f.classList.toggle("on", on);
        if (on && !antes) {
          f.querySelectorAll(".cuenta").forEach((c) => (animar ? contar(c) : (c.textContent =
            (c.dataset.pre || "") + formato(Number(c.dataset.valor), Number(c.dataset.dec || 0)) + (c.dataset.suf || ""))));
          if (f.classList.contains("cuenta")) contar(f);
        }
      });
    });
    // Contadores fuera de fragmentos: se animan al entrar a la lámina.
    if (cambia || !animar) {
      laminas[n].querySelectorAll(".cuenta").forEach((c) => {
        if (!c.closest(".f")) contar(c);
      });
    }
    // Al mostrar todo de golpe (tecla T o al volver atrás) no se atenúa nada.
    if (animar) enfocar(laminas[n]);
    else {
      laminas[n].querySelectorAll(".atenuado").forEach((x) => x.classList.remove("atenuado"));
      laminas[n].querySelectorAll(".marca").forEach((x) => x.classList.add("pasada"));
    }
    barra.style.width = `${(100 * (n + 1)) / laminas.length}%`;
    contador.textContent = `${n + 1} / ${laminas.length}`;
    notas.innerHTML = laminas[n].querySelector("template.nota")?.innerHTML || "";
    if (location.hash !== `#${n + 1}`) history.replaceState(null, "", `#${n + 1}`);
  }

  function siguiente() {
    if (paso < grupos[actual].length) mostrar(actual, paso + 1, true);
    else if (actual < laminas.length - 1) mostrar(actual + 1, 0, true);
  }

  function anterior() {
    if (paso > 0) mostrar(actual, paso - 1, false);
    else if (actual > 0) mostrar(actual - 1, grupos[actual - 1].length, false);
  }

  document.addEventListener("keydown", (e) => {
    if (e.target.closest && e.target.closest("video")) {
      if (e.key === " ") return;
    }
    const k = e.key;
    if (["ArrowRight", "ArrowDown", "PageDown", " ", "Enter"].includes(k)) { e.preventDefault(); siguiente(); }
    else if (["ArrowLeft", "ArrowUp", "PageUp", "Backspace"].includes(k)) { e.preventDefault(); anterior(); }
    else if (k === "Home") mostrar(0, 0, false);
    else if (k === "End") mostrar(laminas.length - 1, grupos[laminas.length - 1].length, false);
    else if (k === "f" || k === "F") {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen?.();
    } else if (k === "s" || k === "S") document.body.classList.toggle("ver-notas");
    else if (k === "t" || k === "T") mostrar(actual, grupos[actual].length, false);
  });

  document.addEventListener("click", (e) => {
    if (e.target.closest("a, video, button, .notas")) return;
    if (e.clientX < window.innerWidth / 4) anterior();
    else siguiente();
  });

  let x0 = null;
  document.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  document.addEventListener("touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 50) (dx < 0 ? siguiente : anterior)();
    x0 = null;
  });

  window.addEventListener("resize", escalar);
  window.addEventListener("hashchange", () => {
    const n = Math.max(0, Math.min(laminas.length - 1, parseInt(location.hash.slice(1), 10) - 1 || 0));
    if (n !== actual) mostrar(n, 0, true);
  });

  escalar();
  const inicial = Math.max(0, Math.min(laminas.length - 1, parseInt(location.hash.slice(1), 10) - 1 || 0));
  actual = inicial;
  mostrar(inicial, 0, true);
  document.querySelector(".ayuda button")?.addEventListener("click", (e) => {
    e.stopPropagation();
    e.currentTarget.parentElement.remove();
  });
})();
