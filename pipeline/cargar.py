# -*- coding: utf-8 -*-
"""Carga semanal de datos de Pluz desde el navegador.

Uso, desde la raíz del repositorio:

    python pipeline/cargar.py            abre http://127.0.0.1:8050/cargar/ en el navegador
    python pipeline/cargar.py exportar   escribe cargar/estado.json para GitHub Pages

La página vive en cargar/index.html y funciona de dos maneras:

  * En GitHub Pages (/cargar/) es estática, como /benchmark/: valida el archivo de la semana
    y dibuja lo que trae dentro del navegador. El archivo no sale del equipo. Los gráficos
    del modelo y la literatura salen de cargar/estado.json, que solo lleva métricas
    agregadas, nada fila a fila de los Excel de Pluz.
  * Servida por este programa, en local, además guarda el archivo en un lote nuevo
    (pipeline/datos/lotes/AAAAMMDD_carga), corre la actualización completa y abre la
    herramienta con los datos nuevos. Antes de actualizar guarda un respaldo en
    pipeline/salidas/respaldos/, y «Restaurar» deshace la carga: borra el lote y devuelve
    data/, las salidas del modelo y cargar/estado.json a como estaban. Ahí la validación definitiva la hace pandas con el
    mismo contrato de config.FUENTES que usa actualizar.py.
"""
import fnmatch
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
CARPETA_PAGINA = config.REPO / "cargar"
ESTADO_PUBLICO = CARPETA_PAGINA / "estado.json"


# ----------------------------------------------------------------- recibir un archivo

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


def recibir_archivo(nombre, contenido):
    """Guarda el archivo en un lote nuevo y lo valida con el contrato. Si falla, no queda nada."""
    from etapas.fuentes import _leer
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
        filas = len(_leer(archivo, config.FUENTES[fuente]))
        return {"lote": lote.name, "fuente": fuente, "archivo": archivo.name, "filas": filas}
    except Exception:
        shutil.rmtree(lote, ignore_errors=True)
        raise


# ----------------------------------------------------------------- respaldo y restauración
# Antes de cada actualización desde la página se guarda una copia de lo que la carga va a
# cambiar. «Restaurar» devuelve esa copia y borra el lote: la herramienta queda como estaba
# antes de subir el archivo. Las corridas de MLflow no se borran: quedan como historial.

RESPALDOS = config.SALIDAS / "respaldos"
MAXIMO_RESPALDOS = 5
_NO_RESPALDAR = {"mlflow.db", "mlruns", "benchmark", "respaldos", "registros"}


def respaldar(lote):
    marca = time.strftime("%Y%m%d_%H%M%S")
    destino = RESPALDOS / f"{marca}_{Path(lote).name or 'sin_lote'}"
    destino.mkdir(parents=True)
    shutil.copytree(config.DATA_WEB, destino / "data")
    salidas = destino / "salidas"
    salidas.mkdir()
    for f in config.SALIDAS.iterdir():
        if f.is_file() and f.name not in _NO_RESPALDAR:
            shutil.copy2(f, salidas / f.name)
    if not config.DEMO and ESTADO_PUBLICO.exists():
        shutil.copy2(ESTADO_PUBLICO, destino / "estado.json")
    reporte = config.SALIDAS / "reporte.json"
    previo = json.loads(reporte.read_text(encoding="utf-8")) if reporte.exists() else {}
    (destino / "respaldo.json").write_text(json.dumps(
        {"lote": Path(lote).name, "fecha": time.strftime("%Y-%m-%d %H:%M"),
         "corte_previo": previo.get("corte"), "corrida_previa": previo.get("fecha")},
        ensure_ascii=False), encoding="utf-8")
    for viejo in sorted(p for p in RESPALDOS.iterdir() if p.is_dir())[:-MAXIMO_RESPALDOS]:
        shutil.rmtree(viejo)
    return destino


def respaldos():
    if not RESPALDOS.exists():
        return []
    out = []
    for p in sorted((p for p in RESPALDOS.iterdir() if (p / "respaldo.json").exists()), reverse=True):
        out.append({"id": p.name, **json.loads((p / "respaldo.json").read_text(encoding="utf-8"))})
    return out


def _renovar_version():
    """Cambia ?v= de los datos en index.html para que el navegador no use la copia vieja."""
    import re
    pagina = config.DATA_WEB.parent / "index.html"
    if pagina.exists():
        html = pagina.read_text(encoding="utf-8")
        html = re.sub(r'(src="data/[a-z_]+\.js)(\?v=[0-9]+)?"',
                      rf'\1?v={time.strftime("%Y%m%d%H%M")}"', html)
        pagina.write_text(html, encoding="utf-8")


def restaurar(ident):
    """Vuelve al estado previo a la carga del respaldo indicado (el más reciente si no hay)."""
    lista = respaldos()
    if not lista:
        raise ValueError("No hay ninguna carga que deshacer.")
    elegido = next((r for r in lista if r["id"] == ident), None) if ident else lista[0]
    if elegido is None:
        raise ValueError("Ese respaldo ya no existe.")
    origen = RESPALDOS / elegido["id"]
    shutil.rmtree(config.DATA_WEB)
    shutil.copytree(origen / "data", config.DATA_WEB)
    for f in (origen / "salidas").iterdir():
        shutil.copy2(f, config.SALIDAS / f.name)
    if not config.DEMO and (origen / "estado.json").exists():
        shutil.copy2(origen / "estado.json", ESTADO_PUBLICO)
    lote = config.LOTES / elegido["lote"]
    if "_carga" in elegido["lote"] and lote.is_dir():
        shutil.rmtree(lote)
    _renovar_version()
    # Este respaldo y los posteriores ya no aplican: la configuración volvió a antes de ellos.
    for r in lista:
        shutil.rmtree(RESPALDOS / r["id"])
        if r["id"] == elegido["id"]:
            break
    return elegido


# ----------------------------------------------------------------- estado para la página

def _literatura(con_pdf):
    """Fuentes de papers/README.md, agrupadas por la decisión del proyecto que respaldan."""
    import re
    texto = (config.REPO / "papers" / "README.md").read_text(encoding="utf-8")
    pdfs = sorted(p.name for p in (config.REPO / "papers").glob("*.pdf")) if con_pdf else []
    grupos, actual = [], None
    for linea in texto.splitlines():
        if linea.startswith("### "):
            actual = {"decision": re.sub(r"^\d+\.\s*", "", linea[4:]).strip(), "fuentes": []}
            grupos.append(actual)
        elif actual and linea.startswith("* **"):
            m = re.match(r"\* \*\*(.+?)\*\*\s*(.*)", linea)
            if not m:
                continue
            num = re.search(r"Archivo (\d\d)", m.group(2))
            pdf = next((p for p in pdfs if num and p.startswith(num.group(1))), None)
            actual["fuentes"].append({"autor": m.group(1).rstrip("."),
                                      "nota": re.sub(r"\s*Archivo \d\d\.?$", "", m.group(2)),
                                      "pdf": pdf})
    return [g for g in grupos if g["fuentes"]]


def _mlflow():
    """Historial del modelo vigente y último benchmark, leídos directo de la base de MLflow."""
    import sqlite3
    db = config.SALIDAS / "mlflow.db"
    if not db.exists():
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


def _contrato():
    """Lo que la página necesita para validar en el navegador, tomado de config.FUENTES."""
    return {f: {k: e.get(k) for k in ("patrones", "hoja", "encabezado", "columnas", "fecha", "modo")}
            for f, e in config.FUENTES.items()}


def estado(publico=False):
    reporte = config.SALIDAS / "reporte.json"
    rep = json.loads(reporte.read_text(encoding="utf-8")) if reporte.exists() else {}
    fuentes = rep.get("fuentes", {})
    if publico:   # sin nombres de archivo de Pluz, solo conteos y periodos
        fuentes = {k: ({"filas": v["filas"]} if isinstance(v, dict) and "filas" in v else v)
                   for k, v in fuentes.items() if k not in ("avisos",)}
    return {"modo": "estatico" if publico else "local",
            "web": "../" if publico or not config.DEMO else "/web/",
            "reporte": {k: rep.get(k) for k in ("fecha", "corte", "ventana", "validacion",
                                                 "monitoreo", "publicado")},
            "fuentes": fuentes,
            "lotes": [] if publico else
            ([p.name for p in sorted(config.LOTES.iterdir()) if p.is_dir()]
             if config.LOTES.exists() else []),
            "respaldos": [] if publico else respaldos(),
            "contrato": _contrato(), "mlflow": _mlflow(), "literatura": _literatura(not publico)}


def exportar():
    """Escribe cargar/estado.json, la foto que usa la página en GitHub Pages."""
    if config.DEMO:
        return None   # el modo demostración nunca toca lo que se publica
    ESTADO_PUBLICO.write_text(json.dumps(estado(publico=True), ensure_ascii=False),
                              encoding="utf-8")
    return ESTADO_PUBLICO


# ----------------------------------------------------------------- servidor local

class Manejador(http.server.SimpleHTTPRequestHandler):
    """Sirve el repositorio (página de carga y herramienta) y la API de carga en /api/."""

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(config.REPO), **k)

    def log_message(self, *a):
        pass

    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def end_headers(self):
        # Sin caché: cada carga tiene que ver los datos recién publicados.
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta in ("/", "/cargar"):
            self.send_response(302)
            self.send_header("Location", "/cargar/")
            self.end_headers()
        elif ruta == "/api/estado":
            try:
                self._json(200, estado())
            except Exception as e:
                self._json(500, {"error": str(e)})
        elif ruta.startswith("/pipeline/"):
            self.send_error(404)   # los lotes de Pluz no se sirven nunca
        elif ruta.startswith("/web/") and config.DEMO:
            # En modo demostración la herramienta es la copia propia del demo.
            self.directory = str(config.DATA_WEB.parent)
            self.path = self.path[4:]
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        if self.path == "/api/subir":
            nombre = urllib.parse.unquote(self.headers.get("X-Nombre", "archivo.xlsx"))
            try:
                self._json(200, recibir_archivo(nombre, self.rfile.read(largo)))
            except Exception as e:  # el mensaje llega tal cual a la página
                self._json(400, {"error": str(e)})
        elif self.path == "/api/descartar":
            lote = Path(json.loads(self.rfile.read(largo) or b"{}").get("lote", "")).name
            destino = config.LOTES / lote
            if "_carga" in lote and destino.is_dir():
                shutil.rmtree(destino)
            self._json(200, {"ok": True})
        elif self.path == "/api/actualizar":
            lote = json.loads(self.rfile.read(largo) or b"{}").get("lote", "")
            respaldar(lote)   # para poder deshacer la carga con «Restaurar»
            r = subprocess.run([sys.executable, str(PIPELINE / "actualizar.py")],
                               cwd=config.REPO, capture_output=True, text=True)
            self._json(200, {"ok": r.returncode == 0, "codigo": r.returncode,
                             "log": (r.stdout + r.stderr)[-6000:]})
        elif self.path == "/api/restaurar":
            ident = json.loads(self.rfile.read(largo) or b"{}").get("id")
            try:
                self._json(200, {"ok": True, "restaurado": restaurar(ident)})
            except Exception as e:
                self._json(400, {"error": str(e)})
        else:
            self.send_error(404)


def main():
    if sys.argv[1:2] == ["exportar"]:
        destino = exportar()
        print(f"Escrito {destino}" if destino else "En modo demostración no se exporta nada.")
        return
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    url = f"http://127.0.0.1:{PUERTO}/cargar/"
    print(f"Carga semanal en {url}. Cierre con Ctrl y C.")
    webbrowser.open(url)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
