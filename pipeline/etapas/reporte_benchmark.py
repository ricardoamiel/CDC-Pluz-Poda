# -*- coding: utf-8 -*-
"""Reporte interactivo del benchmark de modelos, en un solo archivo HTML con D3 versión 7.

Se usa la misma copia de D3 que carga la herramienta (js/vendor/d3.v7.9.0.min.js) y se
incrusta en el archivo, de modo que el reporte se abre sin conexión. Los datos van en un
bloque JSON dentro de la página y los gráficos se dibujan en el navegador. La paleta es la
de Pluz.
"""
import html
import json

import config

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "setiembre", "octubre", "noviembre", "diciembre"]


def _mes(texto):
    """De AAAA MM a «enero de 2026», para no escribir fechas con guiones."""
    anio, mes = str(texto)[:4], int(str(texto)[5:7])
    return f"{MESES[mes - 1]} de {anio}"

D3 = config.REPO / "js" / "vendor" / "d3.v7.9.0.min.js"

COLORES = {
    "Regla por historial": "#76839a",
    "Regresión logística": "#395aa1",
    "Regresión logística ponderada": "#9db1d6",
    "Refuerzo de gradiente": "#6f3e9d",
    "Random Forest": "#6cac5e",
    "XGBoost": "#ac5700",
    "LightGBM": "#e0a100",
    "SVM": "#b3261e",
}


def _pct(v):
    return f"{100 * v:.1f}".replace(".", ",") + " %"


def _dec(v, n=3):
    return "" if v is None else f"{v:.{n}f}".replace(".", ",")


def _intervalo(b):
    signo = lambda x: ("más " if x >= 0 else "menos ") + f"{abs(100 * x):.1f}".replace(".", ",")  # noqa: E731
    return f"{signo(b['media'])} puntos, entre {signo(b['li'])} y {signo(b['ls'])}"


def tabla_metricas(r):
    cab = ["Modelo", "ROC AUC", "PR AUC", "Brier", "Log loss", "Precisión", "Exhaustividad",
           "F1", "F2", "Cobertura 20", "Cobertura 40", "Cobertura 80", "Precisión en lista de 40",
           "Frente a la logística, PR AUC", "Frente a la logística, cobertura 40"]
    filas = []
    for n, m in r["modelos"].items():
        p = m["prueba"]
        contra_ap = _intervalo(m["contra_logistica"]["pr_auc"]) if "contra_logistica" in m else "referencia"
        contra = _intervalo(m["contra_logistica"]["cobertura_40"]) if "contra_logistica" in m else "referencia"
        clase = ' class="elegido"' if n == r["decision"]["modelo"] else ""
        celdas = (_dec(p["roc_auc"]), _dec(p["pr_auc"]), _dec(p.get("brier")), _dec(p.get("log_loss")),
                  _pct(p["precision"]), _pct(p["recall"]), _dec(p["f1"]), _dec(p["f2"]),
                  _pct(p["cobertura_20"]), _pct(p["cobertura_40"]), _pct(p["cobertura_80"]),
                  _pct(p["precision_40"]), contra_ap, contra)
        filas.append(f"<tr{clase}><td><span class='punto' style='background:{COLORES.get(n)}'></span>"
                     f"{html.escape(n)}</td>" + "".join(f"<td>{v}</td>" for v in celdas) + "</tr>")
    return ("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cab) +
            "</tr></thead><tbody>" + "".join(filas) + "</tbody></table>")


def tabla_ejemplos(r):
    lectura = {"VP": "Estaba en la lista y tuvo evento: la poda habría llegado a tiempo.",
               "FP": "Estaba en la lista y no tuvo evento: una visita que no hacía falta todavía.",
               "FN": "Quedó fuera de la lista y tuvo evento: el caso que más cuesta.",
               "VN": "Quedó fuera y no tuvo evento: correcto dejarlo para después."}
    filas = []
    for e in r["ejemplos"]:
        eventos = " · ".join(str(e[f"ev_mes_{k}"]) for k in range(1, config.HORIZONTE_MESES + 1))
        filas.append(
            f"<tr class='t{e['tipo']}' data-modelo='{html.escape(e['modelo'])}'>"
            f"<td>{html.escape(e['modelo'])}</td><td><b>{e['tipo']}</b></td>"
            f"<td>{html.escape(str(e['alimentador']))}</td><td>{_mes(e['periodo'])}</td>"
            f"<td>{_pct(e['probabilidad'])}</td><td>{int(e['puesto'])}</td>"
            f"<td>{int(e['veg_12m'])}</td><td>{int(e['veg_hist'])}</td><td>{int(e['eventos_12m'])}</td>"
            f"<td>{eventos}</td><td>{lectura[e['tipo']]}</td></tr>")
    cab = ["Modelo", "Tipo", "Alimentador", "Mes de corte", "Probabilidad", "Puesto en el mes",
           "Vegetación 12 meses", "Vegetación histórica", "Interrupciones 12 meses",
           "Eventos reales en los 3 meses siguientes", "Lectura"]
    return ("<table id='ejemplos'><thead><tr>" + "".join(f"<th>{c}</th>" for c in cab) +
            "</tr></thead><tbody>" + "".join(filas) + "</tbody></table>")


ESTILOS = """
body{margin:0;background:#f6f8fc;color:#131a26;font:14px/1.55 system-ui,"Segoe UI",Arial,sans-serif}
main{max-width:1240px;margin:0 auto;padding:24px 18px}
header,section{background:#fff;border:1px solid #dee5f0;border-radius:14px;padding:18px 22px;margin-bottom:16px}
header{border-top:4px solid #395aa1}
.sobre{margin:0;color:#76839a;font-size:12px;text-transform:uppercase;letter-spacing:.06em;font-weight:600}
h1{margin:4px 0 8px;font-size:26px}h2{margin:0 0 8px;font-size:18px}h3{margin:6px 0;font-size:14px}
.decision{background:#e8eef8;border-color:#9db1d6}
.tabla{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}
th,td{padding:6px 8px;border-bottom:1px solid #dee5f0;text-align:right;white-space:nowrap}
th:first-child,td:first-child,#ejemplos td:last-child{text-align:left}th{background:#f4f7fc;font-weight:600}
tr.elegido td{background:#e8eef8;font-weight:600}#ejemplos td:last-child{white-space:normal;min-width:240px}
tr.tFN td:nth-child(2){color:#b3261e}tr.tFP td:nth-child(2){color:#ac5700}tr.tVP td:nth-child(2){color:#2f7d32}
.punto{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:0}
.par{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:900px){.par{grid-template-columns:1fr}}
.rejilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.grafico svg{display:block;width:100%;height:auto;overflow:visible}
.eje text{fill:#4e5a6e;font-size:11px}.eje path,.eje line{stroke:#c2cee2}.rejilla-y line{stroke:#eef2f9}
.titulo-eje{fill:#4e5a6e;font-size:11.5px}
.leyenda{display:flex;flex-wrap:wrap;gap:6px 12px;margin:8px 0 2px;font-size:12px}
.leyenda button{font:inherit;border:1px solid #dee5f0;background:#fff;border-radius:999px;padding:3px 10px;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.leyenda button.apagado{opacity:.4}
.selector{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px}
.selector button{font:inherit;font-size:12.5px;border:1px solid #c2cee2;background:#f4f7fc;border-radius:8px;padding:5px 11px;cursor:pointer}
.selector button.activo{background:#395aa1;color:#fff;border-color:#395aa1}
.ayuda{position:fixed;pointer-events:none;background:#fff;border:1px solid #c2cee2;border-radius:8px;padding:7px 10px;font-size:12px;box-shadow:0 6px 18px rgba(19,26,38,.14);display:none;z-index:10}
.nota{color:#4e5a6e;font-size:12.5px}
th.ordenable{cursor:pointer;user-select:none}th.ordenable:hover{background:#e8eef8}
th .flecha{color:#9db1d6;margin-left:4px;font-size:10px}th.asc .flecha,th.desc .flecha{color:#395aa1}
"""

GRAFICOS = r"""
const R = JSON.parse(document.getElementById("datos").textContent);
const C = R.colores;
const fmt = (v, d = 3) => v == null ? "" : v.toFixed(d).replace(".", ",");
const pct = v => (100 * v).toFixed(1).replace(".", ",") + " %";
const ayuda = d3.select("body").append("div").attr("class", "ayuda");
const mostrar = (e, html) => ayuda.style("display", "block").html(html)
  .style("left", (e.clientX + 14) + "px").style("top", (e.clientY + 14) + "px");
const ocultar = () => ayuda.style("display", "none");

// Gráfico de líneas con leyenda que se activa y desactiva, y ayuda con el punto más cercano.
function lineas(sel, series, op) {
  const W = op.ancho || 560, H = op.alto || 340, m = {t: 18, r: 14, b: 46, l: 56};
  const caja = d3.select(sel).append("div").attr("class", "grafico");
  if (op.titulo) caja.append("h3").text(op.titulo);
  const svg = caja.append("svg").attr("viewBox", `0 0 ${W} ${H}`);
  const todos = series.flatMap(s => s.puntos);
  const x = d3.scaleLinear().domain(op.x || d3.extent(todos, p => p[0])).nice().range([m.l, W - m.r]);
  const y = d3.scaleLinear().domain(op.y || d3.extent(todos, p => p[1])).nice().range([H - m.b, m.t]);
  svg.append("g").attr("class", "rejilla-y").attr("transform", `translate(${m.l},0)`)
    .call(d3.axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r)).tickFormat("")).select(".domain").remove();
  svg.append("g").attr("class", "eje").attr("transform", `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(6));
  svg.append("g").attr("class", "eje").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5));
  svg.append("text").attr("class", "titulo-eje").attr("x", (W + m.l) / 2).attr("y", H - 8).attr("text-anchor", "middle").text(op.xt || "");
  svg.append("text").attr("class", "titulo-eje").attr("transform", "rotate(-90)").attr("x", -(H - m.b + m.t) / 2).attr("y", 14).attr("text-anchor", "middle").text(op.yt || "");
  if (op.diagonal) svg.append("line").attr("x1", x(0)).attr("y1", y(0)).attr("x2", x(1)).attr("y2", y(1))
    .attr("stroke", "#c2cee2").attr("stroke-dasharray", "4 4");
  if (op.vertical != null) {
    svg.append("line").attr("x1", x(op.vertical)).attr("x2", x(op.vertical)).attr("y1", m.t).attr("y2", H - m.b)
      .attr("stroke", "#131a26").attr("stroke-dasharray", "3 3");
    svg.append("text").attr("x", x(op.vertical) + 6).attr("y", m.t + 12).attr("font-size", 11.5)
      .attr("font-weight", 700).attr("fill", "#131a26").text(op.verticalTexto || "");
  }
  const linea = d3.line().x(p => x(p[0])).y(p => y(p[1]));
  const g = svg.append("g").selectAll("path").data(series).join("path")
    .attr("fill", "none").attr("stroke", s => s.color).attr("stroke-width", s => s.grueso ? 3 : 1.8)
    .attr("stroke-dasharray", s => s.punteada ? "5 4" : null).attr("d", s => linea(s.puntos))
    .style("display", s => s.oculta ? "none" : null);
  const marca = svg.append("circle").attr("r", 4.5).attr("fill", "#131a26").style("display", "none");
  svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", W - m.l - m.r).attr("height", H - m.t - m.b)
    .attr("fill", "transparent").on("pointermove", e => {
      const [px, py] = d3.pointer(e);
      let mejor = null;
      series.filter(s => !s.oculta).forEach(s => s.puntos.forEach(p => {
        const d = Math.hypot(x(p[0]) - px, y(p[1]) - py);
        if (!mejor || d < mejor.d) mejor = {d, s, p};
      }));
      if (!mejor) return;
      marca.style("display", null).attr("cx", x(mejor.p[0])).attr("cy", y(mejor.p[1]));
      mostrar(e, op.tip ? op.tip(mejor.s, mejor.p) : `<b>${mejor.s.nombre}</b><br>${op.xt}: ${fmt(mejor.p[0])}<br>${op.yt}: ${fmt(mejor.p[1])}`);
    }).on("pointerleave", () => { marca.style("display", "none"); ocultar(); });
  const ley = caja.append("div").attr("class", "leyenda");
  ley.selectAll("button").data(series).join("button").classed("apagado", s => s.oculta)
    .html(s => `<span class="punto" style="background:${s.color}"></span>${s.nombre}`)
    .on("click", function (_, s) {
      s.oculta = !s.oculta; d3.select(this).classed("apagado", s.oculta);
      g.style("display", d => d.oculta ? "none" : null);
    })
    .on("pointerenter", (_, s) => g.attr("opacity", d => d === s ? 1 : .15))
    .on("pointerleave", () => g.attr("opacity", 1));
}

// Barras por modelo con un selector de métrica.
function barras(sel) {
  const metricas = [["pr_auc", "PR AUC", fmt], ["roc_auc", "ROC AUC", fmt],
    ["cobertura_40", "Cobertura con lista de 40", pct], ["f2", "F2", fmt], ["f1", "F1", fmt], ["recall", "Exhaustividad", pct],
    ["precision", "Precisión", pct], ["precision_40", "Precisión en lista de 40", pct], ["brier", "Brier, menor es mejor", fmt]];
  const caja = d3.select(sel);
  const botones = caja.append("div").attr("class", "selector");
  const W = 1150, H = 330, m = {t: 14, r: 60, b: 34, l: 230};
  const svg = caja.append("div").attr("class", "grafico").append("svg").attr("viewBox", `0 0 ${W} ${H}`);
  function dibujar(k) {
    const [clave, , f] = metricas.find(d => d[0] === k);
    botones.selectAll("button").classed("activo", d => d[0] === k);
    const datos = Object.entries(R.modelos).map(([n, v]) => ({n, v: v.prueba[clave]})).filter(d => d.v != null)
      .sort((a, b) => clave === "brier" ? a.v - b.v : b.v - a.v);
    const x = d3.scaleLinear().domain([0, d3.max(datos, d => d.v) * 1.12]).range([m.l, W - m.r]);
    const y = d3.scaleBand().domain(datos.map(d => d.n)).range([m.t, H - m.b]).padding(.25);
    svg.selectAll("*").remove();
    svg.append("g").attr("class", "eje").attr("transform", `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(6));
    svg.append("g").attr("class", "eje").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).tickSize(0)).select(".domain").remove();
    svg.selectAll("rect.b").data(datos).join("rect").attr("class", "b").attr("x", m.l).attr("y", d => y(d.n))
      .attr("height", y.bandwidth()).attr("rx", 3).attr("fill", d => C[d.n])
      .attr("stroke", d => d.n === R.decision.modelo ? "#131a26" : "none").attr("stroke-width", 2)
      .attr("width", d => x(d.v) - m.l);
    svg.selectAll("text.v").data(datos).join("text").attr("class", "v").attr("x", d => x(d.v) + 6)
      .attr("y", d => y(d.n) + y.bandwidth() / 2 + 4).attr("font-size", 12).attr("fill", "#131a26").text(d => f(d.v));
  }
  botones.selectAll("button").data(metricas).join("button").text(d => d[1]).on("click", (_, d) => dibujar(d[0]));
  dibujar("pr_auc");
}

// Mapa de calor con el valor escrito en cada celda.
function calor(sel, z, xs, ys, op) {
  const W = op.ancho || 640, H = op.alto || 560, m = {t: 10, r: 10, b: op.b || 150, l: op.l || 190};
  const caja = d3.select(sel).append("div").attr("class", "grafico");
  if (op.titulo) caja.append("h3").text(op.titulo);
  const svg = caja.append("svg").attr("viewBox", `0 0 ${W} ${H}`);
  const x = d3.scaleBand().domain(xs).range([m.l, W - m.r]).padding(.04);
  const y = d3.scaleBand().domain(ys).range([m.t, H - m.b]).padding(.04);
  const color = op.color;
  const celdas = z.flatMap((fila, i) => fila.map((v, j) => ({i, j, v, t: op.texto ? op.texto[i][j] : fmt(v, 2)})));
  svg.selectAll("rect").data(celdas).join("rect").attr("x", d => x(xs[d.j])).attr("y", d => y(ys[d.i]))
    .attr("width", x.bandwidth()).attr("height", y.bandwidth()).attr("rx", 3).attr("fill", d => color(d.v))
    .on("pointermove", (e, d) => mostrar(e, `${ys[d.i]}<br>${xs[d.j]}<br><b>${d.t}</b>`)).on("pointerleave", ocultar);
  svg.selectAll("text.c").data(celdas).join("text").attr("class", "c").attr("x", d => x(xs[d.j]) + x.bandwidth() / 2)
    .attr("y", d => y(ys[d.i]) + y.bandwidth() / 2 + 4).attr("text-anchor", "middle").attr("font-size", op.fuente || 11)
    .attr("fill", d => Math.abs(op.contraste ? op.contraste(d.v) : d.v) > .55 ? "#fff" : "#131a26").text(d => d.t);
  svg.append("g").attr("class", "eje").attr("transform", `translate(0,${H - m.b})`).call(d3.axisBottom(x).tickSize(0))
    .selectAll("text").attr("transform", op.girar ? "rotate(-35)" : null).attr("text-anchor", op.girar ? "end" : "middle");
  svg.append("g").attr("class", "eje").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).tickSize(0));
  svg.selectAll(".eje .domain").remove();
}

const nombres = Object.keys(R.modelos);
const serie = (n, pts, extra = {}) => ({nombre: n, color: C[n], puntos: pts, grueso: n === R.decision.modelo, ...extra});

barras("#g-metricas");
lineas("#g-roc", Object.entries(R.roc).map(([n, c]) => serie(n, c.x.map((v, i) => [v, c.y[i]]))),
  {titulo: "Curva ROC", xt: "Tasa de falsos positivos", yt: "Exhaustividad", x: [0, 1], y: [0, 1], diagonal: true});
lineas("#g-pr", Object.entries(R.pr).map(([n, c]) => serie(n, c.x.map((v, i) => [v, c.y[i]]))),
  {titulo: "Curva de precisión y exhaustividad", xt: "Exhaustividad", yt: "Precisión", x: [0, 1], y: [0, 1]});
lineas("#g-calibracion", Object.entries(R.calibracion).map(([n, c]) => serie(n, c.x.map((v, i) => [v, c.y[i]]))),
  {xt: "Probabilidad media declarada", yt: "Frecuencia observada", x: [0, 1], y: [0, 1], diagonal: true, ancho: 1150, alto: 420});

Object.entries(R.curvas).filter(([, c]) => Object.keys(c).length).forEach(([n, c]) => {
  const div = d3.select("#g-perdida").append("div");
  lineas(div.node(), Object.entries(c).map(([et, v]) => ({nombre: et, color: et === "Prueba" ? "#ac5700" : "#395aa1",
    puntos: v.map((y, i) => [i + 1, y])})), {titulo: n, xt: "Iteración o grupo de árboles", yt: "Pérdida logarítmica", ancho: 420, alto: 280});
});
lineas("#g-aprendizaje", nombres.filter(n => R.aprendizaje[n]).flatMap(n => [
  serie(n, R.aprendizaje[n].map(p => [p.cortes, p.prueba])),
  serie(n + ", entrenamiento", R.aprendizaje[n].map(p => [p.cortes, p.entrenamiento]), {color: C[n], punteada: true, oculta: true, grueso: false})]),
  {xt: "Meses de corte usados para entrenar", yt: "Pérdida logarítmica", ancho: 1150, alto: 420});

nombres.forEach(n => {
  const mz = R.modelos[n].prueba.matriz;
  const div = d3.select("#g-matrices").append("div");
  const z = [[mz.tn, mz.fp], [mz.fn, mz.tp]], tot = mz.tn + mz.fp + mz.fn + mz.tp;
  calor(div.node(), z, ["Predice no", "Predice sí"], ["Real no", "Real sí"], {
    titulo: n, ancho: 280, alto: 190, b: 26, l: 62, fuente: 13,
    texto: [[`VN ${mz.tn}`, `FP ${mz.fp}`], [`FN ${mz.fn}`, `VP ${mz.tp}`]],
    color: v => d3.interpolateBlues(.08 + .85 * Math.sqrt(v / tot)), contraste: v => Math.sqrt(v / tot) > .5 ? 1 : 0});
});

(function () {
  const datos = R.aporte_variables, W = 1150, H = 50 + 46 * datos.length, m = {t: 10, r: 30, b: 34, l: 300};
  const svg = d3.select("#g-aporte").append("div").attr("class", "grafico").append("svg").attr("viewBox", `0 0 ${W} ${H}`);
  const ext = d3.extent(datos.flatMap(d => [d.aporte_cobertura_40.li, d.aporte_cobertura_40.ls, 0]));
  const x = d3.scaleLinear().domain(ext).nice().range([m.l, W - m.r]);
  const y = d3.scaleBand().domain(datos.map(d => d.nombre)).range([m.t, H - m.b]).padding(.35);
  svg.append("g").attr("class", "eje").attr("transform", `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(6).tickFormat(v => pct(v)));
  svg.append("g").attr("class", "eje").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).tickSize(0)).select(".domain").remove();
  svg.append("line").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t).attr("y2", H - m.b).attr("stroke", "#131a26");
  const g = svg.selectAll("g.v").data(datos).join("g").attr("class", "v")
    .on("pointermove", (e, d) => mostrar(e, `<b>${d.nombre}</b><br>Aporte a la cobertura: ${pct(d.aporte_cobertura_40.media)}<br>Intervalo: ${pct(d.aporte_cobertura_40.li)} a ${pct(d.aporte_cobertura_40.ls)}`))
    .on("pointerleave", ocultar);
  g.append("line").attr("x1", d => x(d.aporte_cobertura_40.li)).attr("x2", d => x(d.aporte_cobertura_40.ls))
    .attr("y1", d => y(d.nombre) + y.bandwidth() / 2).attr("y2", d => y(d.nombre) + y.bandwidth() / 2).attr("stroke", "#9db1d6").attr("stroke-width", 6);
  g.append("circle").attr("cx", d => x(d.aporte_cobertura_40.media)).attr("cy", d => y(d.nombre) + y.bandwidth() / 2).attr("r", 6)
    .attr("fill", d => d.aporte_cobertura_40.li > 0 ? "#395aa1" : "#76839a");
})();

const PO = R.punto_operacion;
lineas("#g-f2", [{nombre: "Regresión logística, validación interna", color: C["Regresión logística"], grueso: true,
  puntos: PO.rejilla.map((k, i) => [k, PO.f2_validacion[i]])}],
  {xt: "Alertas por mes", yt: "F2 en la validación", vertical: PO.alertas_por_mes,
   verticalTexto: `${PO.alertas_por_mes} alertas por mes`, ancho: 1150, alto: 320,
   tip: (s, p) => `<b>${p[0]} alertas por mes</b><br>F2 en validación: ${fmt(p[1])}`});
lineas("#g-ganancia", Object.entries(R.ganancia).map(([n, g]) => serie(n, g.k.map((k, i) => [k, g.recall[i], g.fp[i]]))),
  {xt: "Alertas por mes", yt: "Exhaustividad en la prueba", y: [0, 1], vertical: PO.alertas_por_mes,
   verticalTexto: "punto de operación", ancho: 1150, alto: 420,
   tip: (s, p) => `<b>${s.nombre}</b><br>${p[0]} alertas por mes<br>Exhaustividad: ${pct(p[1])}<br>Falsos positivos en 5 meses: ${p[2]}`});

const red = R.redundancia;
calor("#g-redundancia", red.matriz, red.etiquetas, red.etiquetas, {girar: true, ancho: 1150, alto: 640, l: 260, b: 170,
  color: v => d3.interpolateRdBu((1 - v) / 2)});

// Ordenar cualquier tabla al hacer clic en su encabezado. Lee cifras con coma decimal, por
// ciento y diferencias escritas como «más» o «menos»; el resto se ordena como texto.
function valorCelda(t) {
  t = t.trim();
  const signo = t.startsWith("menos") ? -1 : 1;
  const num = t.replace(/^(más|menos)\s*/, "").match(/^[0-9.]*,?[0-9]+/);
  if (num) return signo * parseFloat(num[0].replace(/\.(?=\d{3})/g, "").replace(",", "."));
  return t.toLowerCase();
}
d3.selectAll("table").each(function () {
  const tabla = d3.select(this);
  tabla.selectAll("thead th").classed("ordenable", true).attr("title", "Ordenar por esta columna")
    .each(function () { d3.select(this).append("span").attr("class", "flecha").text("⇅"); })
    .on("click", function () {
      const th = d3.select(this), col = Array.from(this.parentNode.children).indexOf(this);
      const asc = !th.classed("asc");
      tabla.selectAll("thead th").classed("asc", false).classed("desc", false).select(".flecha").text("⇅");
      th.classed(asc ? "asc" : "desc", true).select(".flecha").text(asc ? "▲" : "▼");
      const filas = tabla.select("tbody").selectAll("tr").nodes();
      filas.sort((a, b) => {
        const x = valorCelda(a.children[col].textContent), y = valorCelda(b.children[col].textContent);
        const r = (typeof x === "number" && typeof y === "number") ? x - y : String(x).localeCompare(String(y), "es");
        return asc ? r : -r;
      }).forEach(f => f.parentNode.appendChild(f));
    });
});

d3.selectAll("#filtro-ejemplos button").on("click", function () {
  const m = this.dataset.modelo;
  // Ordenar cualquier tabla al hacer clic en su encabezado. Lee cifras con coma decimal, por
// ciento y diferencias escritas como «más» o «menos»; el resto se ordena como texto.
function valorCelda(t) {
  t = t.trim();
  const signo = t.startsWith("menos") ? -1 : 1;
  const num = t.replace(/^(más|menos)\s*/, "").match(/^[0-9.]*,?[0-9]+/);
  if (num) return signo * parseFloat(num[0].replace(/\.(?=\d{3})/g, "").replace(",", "."));
  return t.toLowerCase();
}
d3.selectAll("table").each(function () {
  const tabla = d3.select(this);
  tabla.selectAll("thead th").classed("ordenable", true).attr("title", "Ordenar por esta columna")
    .each(function () { d3.select(this).append("span").attr("class", "flecha").text("⇅"); })
    .on("click", function () {
      const th = d3.select(this), col = Array.from(this.parentNode.children).indexOf(this);
      const asc = !th.classed("asc");
      tabla.selectAll("thead th").classed("asc", false).classed("desc", false).select(".flecha").text("⇅");
      th.classed(asc ? "asc" : "desc", true).select(".flecha").text(asc ? "▲" : "▼");
      const filas = tabla.select("tbody").selectAll("tr").nodes();
      filas.sort((a, b) => {
        const x = valorCelda(a.children[col].textContent), y = valorCelda(b.children[col].textContent);
        const r = (typeof x === "number" && typeof y === "number") ? x - y : String(x).localeCompare(String(y), "es");
        return asc ? r : -r;
      }).forEach(f => f.parentNode.appendChild(f));
    });
});

d3.selectAll("#filtro-ejemplos button").classed("activo", function () { return this.dataset.modelo === m; });
  d3.selectAll("#ejemplos tbody tr").style("display", function () { return !m || this.dataset.modelo === m ? null : "none"; });
});
"""


def escribir(r, destino):
    d = r["decision"]
    lr = r["modelos"]["Regresión logística"]["prueba"]
    ganadores = ", ".join(d["supera_con_intervalo"]) or "ninguno"
    del_indice = r["redundancia"]["del_indice_en_el_modelo"]
    variables = ", ".join(config.NOMBRES_VARIABLES[v] for v in r["variables"])
    part = r["particion"]
    etiquetas = {"meses_sin_poda": "Meses sin poda (índice)", "saidi_ltm": "SAIDI (índice)",
                 "clientes": "Clientes (índice)", "kva": "Potencia (índice)"}
    # JSON estricto: un NaN rompería la lectura de los datos en el navegador.
    def limpio(x):
        if isinstance(x, float) and x != x:
            return None
        if isinstance(x, dict):
            return {k: limpio(v) for k, v in x.items()}
        if isinstance(x, list):
            return [limpio(v) for v in x]
        return x
    datos = limpio({**r, "colores": COLORES})
    datos["redundancia"] = {**datos["redundancia"], "etiquetas": [
        etiquetas.get(v, config.NOMBRES_VARIABLES.get(v, v)) for v in r["redundancia"]["variables"]]}
    sin_aporte = [a["nombre"].lower() for a in r["aporte_variables"] if a["aporte_cobertura_40"]["li"] <= 0]
    corr = dict(zip(r["redundancia"]["variables"],
                    r["redundancia"]["matriz"][r["redundancia"]["variables"].index("log_eventos_12m")]))
    nota_aporte = (
        f"<p>Bloques sin aporte propio distinguible en este corte: <b>{'; '.join(sin_aporte) or 'ninguno'}</b>. "
        f"Las interrupciones de los últimos doce meses tienen una correlación de "
        f"{_dec(corr.get('saidi_ltm'), 2)} con el SAIDI, que ya entra al índice. Se mantienen en el "
        "modelo porque Pluz las pidió como indicador principal, pero si quitarlas no cambia el "
        "resultado, su información ya está contenida en el SAIDI y en el historial de vegetación. "
        "Conviene decidirlo con la empresa: el número de interrupciones ya se muestra en la "
        "herramienta como indicador aunque salga del modelo.</p>")
    po = r["punto_operacion"]
    pct_f2 = f"{100 * po['fraccion_f2_maximo']:.0f} %"
    po_pos = f"{po['positivos_por_mes']:.0f}"
    empate = (", y la regresión logística está primera o empatada en el primer lugar entre los modelos"
              if po["logistica_empata_primero"] else "; la regresión logística no es la primera en este punto")
    g_lr = r["ganancia"]["Regresión logística"]
    fila_f2 = dict(zip(po["rejilla"], po["f2_validacion"]))
    total_pos = r["positivos"]["prueba"]
    ks = sorted({40, 80, 120, 160, 200, po["alertas_por_mes"], 260, 300})
    filas_u = []
    for k in ks:
        i = g_lr["k"].index(k)
        tp = round(g_lr["recall"][i] * total_pos)
        fp = g_lr["fp"][i]
        clase = " class='elegido'" if k == po["alertas_por_mes"] else ""
        filas_u.append(f"<tr{clase}><td>{k}</td><td>{_dec(fila_f2[k])}</td><td>{_pct(g_lr['recall'][i])}</td>"
                       f"<td>{_pct(tp / max(1, tp + fp))}</td><td>{fp}</td><td>{total_pos - tp}</td></tr>")
    tabla_umbral = ("<table><thead><tr><th>Alertas por mes</th><th>F2 en validación</th><th>Exhaustividad en prueba</th>"
                    "<th>Precisión en prueba</th><th>Falsos positivos</th><th>Falsos negativos</th></tr></thead><tbody>"
                    + "".join(filas_u) + "</tbody></table>")
    abl = r["ablacion_logistica"]
    tabla_variantes = ("<table><thead><tr><th>Variante</th><th>C</th><th>PR AUC validación</th><th>PR AUC prueba</th>"
                       "<th>ROC AUC prueba</th><th>Cobertura 40</th><th>Exhaustividad</th><th>Falsos positivos</th>"
                       "<th>Falsos negativos</th></tr></thead><tbody>" + "".join(
                           f"<tr{' class=elegido' if v['variante'] == abl['elegida'] else ''}><td>{v['variante']}</td>"
                           f"<td>{_dec(v['C'], 2)}</td><td>{_dec(v['pr_auc_validacion'])}</td><td>{_dec(v['pr_auc'])}</td>"
                           f"<td>{_dec(v['roc_auc'])}</td><td>{_pct(v['cobertura_40'])}</td><td>{_pct(v['recall'])}</td>"
                           f"<td>{v['fp']}</td><td>{v['fn']}</td></tr>" for v in abl["variantes"]) + "</tbody></table>")
    modelos_ej = sorted({e["modelo"] for e in r["ejemplos"]})
    filtro = "".join(f"<button data-modelo='{html.escape(m)}'>{html.escape(m)}</button>" for m in modelos_ej)

    cuerpo = f"""
<header><p class="sobre">Pluz Energía y UTEC · Benchmark de modelos</p>
<h1>¿Regresión logística o un modelo más complejo?</h1>
<p>Corte de {_mes(r['corte'])}. Entrenamiento de {_mes(part['entrena'][0])} a {_mes(part['entrena'][1])}, con elección de hiperparámetros y umbral en {_mes(part['validacion'][0])} y {_mes(part['validacion'][1])}. Prueba de {_mes(part['prueba'][0])} a {_mes(part['prueba'][1])}, con {r['positivos']['prueba']} casos positivos en {r['filas']['prueba']} filas. Ningún modelo vio la prueba al elegir nada.</p></header>

<section class="decision"><h2>Decisión</h2>
<p>Modelo recomendado: <b>{d['modelo']}</b>. Modelos que superan a la regresión logística con un intervalo que no cruza el cero en la PR AUC: <b>{ganadores}</b>.</p>
<p>El modelo se usa para ordenar una lista, así que la métrica que decide es la de ordenamiento, y con clases desbalanceadas la más informativa es la <b>PR AUC</b>: la regresión logística tiene {_dec(lr['pr_auc'])}, la más alta o empatada con la más alta, y una ROC AUC de {_dec(lr['roc_auc'])}, prácticamente igual a la mejor. Un modelo más complejo solo la reemplaza si la supera de forma distinguible en la PR AUC. En empate se queda la regresión logística: es la más simple, entrega una probabilidad calibrada (Brier {_dec(lr.get('brier'))}) que el índice puede sumar y sus coeficientes se explican en una reunión sin traducción.</p></section>

<section><h2>Qué conviene minimizar: falsos negativos</h2>
<p>Un <b>falso negativo</b> es un alimentador que quedó fuera de la lista y tuvo una interferencia de vegetación: termina en un corte de servicio, suma minutos al SAIDI, afecta a clientes, puede generar compensaciones y multas regulatorias y, en red aérea de media tensión, implica riesgo de seguridad. Un <b>falso positivo</b> es una visita de cuadrilla a un alimentador que todavía no la necesitaba: cuesta horas de trabajo, pero no es trabajo perdido: es poda preventiva adelantada sobre alimentadores que el historial ya señala como expuestos, y que tarde o temprano habría que intervenir.</p>
<p>Por eso se privilegia la exhaustividad, es decir, minimizar falsos negativos. Pero no sin límite: la cantidad de cuadrillas fija cuántos alimentadores se pueden atender al mes, de modo que los falsos positivos tienen un techo dado por la capacidad. La métrica que decide es la <b>cobertura de la lista mensual</b>, que es la exhaustividad dentro de la capacidad real, y el punto de operación se eligió con <b>F2</b>, que pesa la exhaustividad el doble que la precisión. F1 y precisión se reportan para completar la lectura.</p></section>

<section><h2>Punto de operación: cuántas alertas por mes</h2>
<p>Los falsos positivos dependen sobre todo de cuántos alimentadores se marcan en alerta, no del modelo. El punto de operación se define como un número de alertas por mes, y no como una probabilidad, por dos razones: una probabilidad elegida en la validación no se traslada al modelo final, que se entrena con más meses y cambia de escala; y es así como opera Pluz, con una capacidad mensual.</p>
<p>Se eligió en la validación interna, con la regresión logística: el menor número de alertas por mes que alcanza el {pct_f2} del F2 máximo, porque pasado ese punto cada alerta adicional agrega casi solo falsos positivos. Resultado: <b>{po['alertas_por_mes']} alertas por mes</b>, de unos {po['alimentadores_por_mes']} alimentadores, con unos {po_pos} eventos por mes en la prueba. En ese punto, el primer modelo en exhaustividad es <b>{po['primero_en_exhaustividad']}</b>{empate}; la regla por historial, que es la referencia, logra {_pct(po['recall_regla'])}.</p>
<div id="g-f2"></div>
<h3>Curva de ganancia en la prueba</h3>
<p class="nota">Exhaustividad de cada modelo según las alertas por mes. Al pasar el puntero se ven también los falsos positivos. Con la misma cantidad de alertas, el modelo más alto es el que menos falsos positivos comete.</p>
<div id="g-ganancia"></div>
<h3>Ablación del punto de operación de la regresión logística</h3>
<div class="tabla">{tabla_umbral}</div>
<h3>Ablación de variantes de la regresión logística</h3>
<p class="nota">Cada variante elige su regularización en la validación interna. Se cambia la base solo si otra variante la supera en la validación por más de 0,005 de precisión media. Variante elegida: <b>{abl['elegida']}</b>.</p>
<div class="tabla">{tabla_variantes}</div></section>

<section><h2>Tabla de métricas en la prueba</h2>
<p class="nota">Precisión, exhaustividad, F1 y F2 se miden en el punto de operación de {po['alertas_por_mes']} alertas por mes, el mismo para todos los modelos. La cobertura y la precisión en lista se miden con las listas mensuales de 20, 40 y 80 alimentadores, que es como se usa el modelo. La última columna es la diferencia con la regresión logística al remuestrear alimentadores, con su intervalo del 95 %. La fila resaltada es el modelo recomendado.</p>
<div class="tabla">{tabla_metricas(r)}</div>
<h3>Comparación por métrica</h3><div id="g-metricas"></div></section>

<section><h2>Curvas ROC y de precisión y exhaustividad</h2>
<p class="nota">Pase el puntero sobre una curva para ver el punto; haga clic en la leyenda para ocultar o mostrar un modelo.</p>
<div class="par"><div id="g-roc"></div><div id="g-pr"></div></div></section>

<section><h2>Calibración</h2><p class="nota">Un modelo calibrado declara 30 % cuando de cada 100 casos así ocurren 30. Es lo que permite que el índice sume riesgos.</p><div id="g-calibracion"></div></section>

<section><h2>Curvas de pérdida</h2>
<p class="nota">Para los modelos que se construyen por iteraciones o por árboles, la pérdida en entrenamiento y en prueba a medida que crecen. Si la de prueba sube mientras la de entrenamiento baja, el modelo está memorizando.</p>
<div class="rejilla" id="g-perdida"></div>
<h3>Curva de aprendizaje</h3>
<p class="nota">Para todos los modelos, la pérdida en prueba según cuántos meses se usan para entrenar. Las líneas punteadas de entrenamiento se activan desde la leyenda.</p>
<div id="g-aprendizaje"></div></section>

<section><h2>Matrices de confusión</h2><p class="nota">En el punto de operación de {po['alertas_por_mes']} alertas por mes. Como todos los modelos marcan la misma cantidad de alimentadores, la diferencia de falsos positivos entre ellos es exactamente la diferencia de verdaderos positivos.</p><div class="rejilla" id="g-matrices"></div></section>

<section><h2>Sin redundancia con el índice</h2>
<p>Variables del modelo: {variables}. Variables del índice dentro del modelo: <b>{', '.join(del_indice) if del_indice else 'ninguna'}</b>. El reloj de poda, el SAIDI y la exposición por clientes y potencia entran solo al índice. Las interrupciones de los últimos doce meses sí entran al modelo, porque Pluz las pidió como indicador principal; el mapa muestra cuánto se parecen al SAIDI y al resto de variables del índice en el último corte.</p>
<div id="g-redundancia"></div>
<h3>Cuánto aporta cada variable</h3>
<p class="nota">Cuánto pierde la cobertura con lista de 40 de la regresión logística al quitar cada bloque de variables, con su intervalo del 95 % al remuestrear alimentadores. Se mide por bloques porque las variables de un mismo bloque se sustituyen entre sí. Un punto gris cuyo intervalo cruza el cero indica un bloque sin aporte propio distinguible; uno azul, un bloque que sí aporta.</p>
<div id="g-aporte"></div>
{nota_aporte}</section>

<section><h2>Ejemplos de inferencia frente a lo que pasó</h2>
<p class="nota">Casos reales del periodo de prueba, clasificados en el punto de operación de {po['alertas_por_mes']} alertas por mes. VP: verdadero positivo; FP: falso positivo; FN: falso negativo; VN: verdadero negativo. La columna de eventos reales muestra cuántas interferencias tuvo el alimentador en cada uno de los tres meses siguientes al corte.</p>
<div class="selector" id="filtro-ejemplos"><button data-modelo="" class="activo">Todos</button>{filtro}</div>
<div class="tabla">{tabla_ejemplos(r)}</div></section>
""".replace("{nota_aporte}", nota_aporte)
    pagina = (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Benchmark de modelos. Pluz Energía</title><style>{ESTILOS}</style></head>"
        f"<body><main>{cuerpo}</main>"
        f"<script id='datos' type='application/json'>{json.dumps(datos, ensure_ascii=False, default=str, allow_nan=False)}</script>"
        f"<script>{D3.read_text(encoding='utf-8')}</script><script>{GRAFICOS}</script>"
        "</body></html>")
    destino.write_text(pagina, encoding="utf-8")
    (destino.parent / "resultados_benchmark.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return destino
