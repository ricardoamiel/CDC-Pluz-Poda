# -*- coding: utf-8 -*-
"""Página local para cargar el archivo semanal de Pluz y actualizar la herramienta.

Uso, desde la raíz del repositorio:

    python pipeline/cargar.py          abre http://127.0.0.1:8050/ en el navegador

Pasos en la página:
    1. Elegir el archivo de la semana (.xlsx o .csv). Se reconoce la fuente por el nombre
       (mismos patrones que config.FUENTES) o, si es CSV, por sus columnas.
    2. La página muestra en gráficos chicos lo que trae: filas por semana, alimentadores
       con más registros y, si existe, SAIDI por semana.
    3. «Actualizar la web» corre actualizar.py (corrida completa) y abre la página nueva.

El archivo se guarda en un lote nuevo, pipeline/datos/lotes/AAAAMMDD_carga. Si no cumple el
contrato de datos, el lote se borra y no se toca nada.
"""
import fnmatch
import functools
import http.server
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPELINE))

import config  # noqa: E402

PUERTO = 8050
PAGINA = PIPELINE / "carga" / "index.html"


def _lote_nuevo():
    fecha = time.strftime("%Y%m%d")
    lote, n = config.LOTES / f"{fecha}_carga", 2
    while lote.exists():
        lote, n = config.LOTES / f"{fecha}_carga{n}", n + 1
    lote.mkdir(parents=True)
    return lote


def _fuente_por_nombre(nombre):
    from etapas.fuentes import _normalizar
    n = _normalizar(nombre)
    for fuente, esp in config.FUENTES.items():
        if any(fnmatch.fnmatch(n, _normalizar(p)) for p in esp["patrones"]):
            return fuente
    return None


def _csv_a_excel(origen, lote):
    """Convierte el CSV al Excel que espera el contrato: nombre, hoja y fila de títulos."""
    import pandas as pd
    tabla = pd.read_csv(origen, sep=None, engine="python", encoding="utf-8-sig")
    tabla.columns = [str(c).strip() for c in tabla.columns]
    for fuente, esp in config.FUENTES.items():
        if all(c in tabla.columns for c in esp["columnas"]):
            patron = " ".join(esp["patrones"][0].replace("*", " ").replace(".xlsx", "").split())
            destino = lote / f"{patron} carga {lote.name}.xlsx"
            hoja = esp["hoja"] if isinstance(esp.get("hoja"), str) else "Hoja1"
            fila = esp["encabezado"] if isinstance(esp.get("encabezado"), int) else 0
            with pd.ExcelWriter(destino) as w:
                tabla.to_excel(w, sheet_name=hoja, startrow=fila, index=False)
            return fuente, destino
    raise ValueError("Las columnas del CSV no coinciden con ninguna fuente del contrato. "
                     f"Columnas recibidas: {list(tabla.columns)[:12]}")


def _resumen(fuente, archivo):
    """Lo que trae el archivo, para los gráficos chicos de la página."""
    import pandas as pd
    from etapas.fuentes import _leer
    esp = config.FUENTES[fuente]
    t = _leer(archivo, esp)
    res = {"fuente": fuente, "archivo": archivo.name, "filas": int(len(t)), "graficos": []}
    if esp.get("fecha"):
        f = pd.to_datetime(t[esp["fecha"]], errors="coerce")
        t = t.assign(_f=f)[f.notna()]
        if len(t):
            res["desde"], res["hasta"] = str(t["_f"].min().date()), str(t["_f"].max().date())
            semana = t["_f"].dt.to_period("W-SUN").dt.start_time.dt.strftime("%d/%m")
            orden = t["_f"].dt.to_period("W-SUN").dt.start_time
            por = t.assign(_s=semana, _o=orden).groupby(["_o", "_s"]).size().reset_index()
            res["graficos"].append({"titulo": "Registros por semana",
                                    "etiquetas": por["_s"].tolist(), "valores": por[0].tolist()})
            if "SAIDI" in t.columns:
                s = t.assign(_o=orden, _s=semana, SAIDI=pd.to_numeric(t["SAIDI"], errors="coerce"))
                s = s.groupby(["_o", "_s"])["SAIDI"].sum().reset_index()
                res["graficos"].append({"titulo": "SAIDI sumado por semana",
                                        "etiquetas": s["_s"].tolist(),
                                        "valores": [round(v, 3) for v in s["SAIDI"]]})
    col = next((c for c in ("Alimentador", "ALIMENTADOR", "ALIM") if c in t.columns), None)
    if col:
        top = t[col].astype(str).value_counts().head(10)
        res["graficos"].append({"titulo": "Alimentadores con más registros",
                                "etiquetas": top.index.tolist(), "valores": top.tolist()})
    if "DISTRITO" in t.columns:
        top = t["DISTRITO"].astype(str).value_counts().head(10)
        res["graficos"].append({"titulo": "Registros por distrito",
                                "etiquetas": top.index.tolist(), "valores": top.tolist()})
    return res


def recibir_archivo(nombre, contenido):
    nombre = Path(nombre).name
    if Path(nombre).suffix.lower() not in config.EXTENSIONES_LOTE:
        raise ValueError(f"Solo se aceptan {config.EXTENSIONES_LOTE}")
    lote = _lote_nuevo()
    try:
        crudo = lote / nombre
        crudo.write_bytes(contenido)
        if crudo.suffix.lower() == ".csv":
            fuente, archivo = _csv_a_excel(crudo, lote)
            crudo.unlink()
        else:
            fuente, archivo = _fuente_por_nombre(nombre), crudo
            if fuente is None:
                raise ValueError("El nombre no coincide con ninguna fuente. Ejemplo esperado: "
                                 "«Interrupciones diarias ....xlsx» o «PODA ... FORMATO UNIFICADO.xlsx»")
        res = _resumen(fuente, archivo)
        res["lote"] = lote.name
        return res
    except Exception:
        shutil.rmtree(lote, ignore_errors=True)
        raise


def _literatura():
    """Fuentes de papers/README.md, agrupadas por la decisión del proyecto que respaldan."""
    import re
    texto = (config.REPO / "papers" / "README.md").read_text(encoding="utf-8")
    pdfs = sorted(p.name for p in (config.REPO / "papers").glob("*.pdf"))
    grupos, actual = [], None
    for linea in texto.splitlines():
        if linea.startswith("### "):
            actual = {"decision": re.sub(r"^\d+\.\s*", "", linea[4:]).strip(), "fuentes": []}
            grupos.append(actual)
        elif actual and linea.startswith("* **"):
            m = re.match(r"\* \*\*(.+?)\*\*\s*(.*)", linea)
            if not m:
                continue
            resto = m.group(2)
            num = re.search(r"Archivo (\d\d)", resto)
            pdf = next((p for p in pdfs if num and p.startswith(num.group(1))), None)
            actual["fuentes"].append({"autor": m.group(1).rstrip("."),
                                      "nota": re.sub(r"\s*Archivo \d\d\.?$", "", resto),
                                      "pdf": pdf})
    return [g for g in grupos if g["fuentes"]]


def _mlflow():
    """Historial del modelo vigente y benchmark, leídos directo de la base de MLflow."""
    import sqlite3
    db = next((p for p in (config.SALIDAS / "mlflow.db", PIPELINE / "salidas" / "mlflow.db")
               if p.exists()), None)
    if db is None:
        return {}
    c = sqlite3.connect(db)
    exp = dict(c.execute("select name, experiment_id from experiments"))

    def corridas(nombre):
        filas = c.execute(
            "select r.run_uuid, r.name, r.start_time, m.key, m.value from runs r "
            "join metrics m on m.run_uuid = r.run_uuid where r.experiment_id = ? "
            "and r.lifecycle_stage = 'active' order by r.start_time", (exp.get(nombre, -1),))
        out = {}
        for uid, nom, t, k, v in filas:
            out.setdefault(uid, {"nombre": nom, "inicio": t, "metricas": {}})["metricas"][k] = v
        return list(out.values())

    vig = corridas("pluz_modelo_vigente")
    bench = corridas("pluz_vegetacion_benchmark")
    ultimo = max((r["inicio"] for r in bench), default=0)
    bench = [r for r in bench if r["inicio"] >= ultimo - 600_000 and "pr_auc" in r["metricas"]]
    return {"vigente": vig[-12:], "benchmark": bench}


def estado():
    reporte = config.SALIDAS / "reporte.json"
    rep = json.loads(reporte.read_text(encoding="utf-8")) if reporte.exists() else {}
    return {"reporte": {k: rep.get(k) for k in ("fecha", "corte", "ventana", "validacion",
                                                 "monitoreo", "publicado")},
            "fuentes": rep.get("fuentes", {}),
            "lotes": [p.name for p in sorted(config.LOTES.iterdir()) if p.is_dir()]
            if config.LOTES.exists() else [],
            "mlflow": _mlflow(), "literatura": _literatura()}


class Manejador(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(config.DATA_WEB.parent), **k)

    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path in ("/", "/carga"):
            cuerpo = PAGINA.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(cuerpo)
        elif self.path == "/estado":
            try:
                self._json(200, estado())
            except Exception as e:
                self._json(500, {"error": str(e)})
        elif self.path.split("/")[1] in ("css", "assets", "papers"):
            # Estilos, logo y literatura de la herramienta original, siempre del repositorio.
            ruta = (config.REPO / urllib.parse.unquote(self.path.split("?")[0]).lstrip("/")).resolve()
            if config.REPO in ruta.parents and ruta.is_file():
                tipo = self.guess_type(str(ruta))
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.end_headers()
                self.wfile.write(ruta.read_bytes())
            else:
                self.send_error(404)
        elif self.path.startswith("/web/"):
            self.path = self.path[4:]   # la herramienta se sirve bajo /web/
            super().do_GET()
        else:
            self.send_error(404)

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        if self.path == "/subir":
            nombre = urllib.parse.unquote(self.headers.get("X-Nombre", "archivo.xlsx"))
            try:
                self._json(200, recibir_archivo(nombre, self.rfile.read(largo)))
            except Exception as e:  # el mensaje llega tal cual a la página
                self._json(400, {"error": str(e)})
        elif self.path == "/descartar":
            lote = json.loads(self.rfile.read(largo) or b"{}").get("lote", "")
            destino = config.LOTES / Path(lote).name
            if lote.endswith(tuple(f"_carga{s}" for s in ["", *map(str, range(2, 50))])) \
                    and destino.is_dir():
                shutil.rmtree(destino)
            self._json(200, {"ok": True})
        elif self.path == "/actualizar":
            r = subprocess.run([sys.executable, str(PIPELINE / "actualizar.py")],
                               cwd=config.REPO, capture_output=True, text=True)
            self._json(200, {"ok": r.returncode == 0, "codigo": r.returncode,
                             "log": (r.stdout + r.stderr)[-6000:]})
        else:
            self.send_error(404)


def main():
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    url = f"http://127.0.0.1:{PUERTO}/"
    print(f"Carga semanal en {url}  (la herramienta queda en {url}web/). Cierre con Ctrl y C.")
    webbrowser.open(url)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
