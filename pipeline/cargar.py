# -*- coding: utf-8 -*-
"""Carga semanal de datos de Pluz desde el navegador.

Uso, desde la raíz del repositorio:

    python pipeline/cargar.py             abre la carga en http://127.0.0.1:8050/cargar/
    python pipeline/cargar.py publicado   abre la carga en la dirección publicada, conectada
                                          a este equipo
    python pipeline/cargar.py exportar    escribe cargar/estado.json

La página vive en cargar/index.html y funciona de tres maneras:

  * Publicada y sin este programa corriendo: valida el archivo de la semana dentro del
    navegador y dibuja lo que trae. El archivo no sale del equipo. Los gráficos del modelo
    y la literatura salen de cargar/estado.json, que solo lleva métricas agregadas.
  * Publicada y con este programa corriendo en el mismo equipo: la página lo detecta en
    http://127.0.0.1:8050 y habilita todo lo de la versión local, más «Publicar». Los
    archivos siguen sin salir del equipo: la página publicada solo habla con este programa.
  * Servida por este programa, en local: lo mismo, desde http://127.0.0.1:8050/cargar/.

Con este programa, cada archivo pasa por una doble verificación antes de tocar nada:
primero el contrato de datos, en el navegador y luego con pandas, y después la comparación
con lo ya cargado en el mismo periodo. Un lote nuevo reemplaza en las fuentes históricas
todo lo cargado desde su primera fecha. Si el archivo es idéntico a lo que ya está, no se
hace nada. Si cambia algo, la página dice cuántas filas se agregan y cuántas se quitarían,
y pide confirmación antes de actualizar.

Antes de actualizar se guarda un respaldo en pipeline/salidas/respaldos/, y «Restaurar»
deshace la carga: borra el lote y devuelve data/, las salidas del modelo y
cargar/estado.json a como estaban.
"""
import fnmatch
import http.server
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from collections import Counter
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPELINE))

import config  # noqa: E402

PUERTO = 8050
LOCAL = f"http://127.0.0.1:{PUERTO}"
CARPETA_PAGINA = config.REPO / "cargar"
ESTADO_PUBLICO = CARPETA_PAGINA / "estado.json"
EN_CURSO = config.SALIDAS / "carga_en_curso"

# Dirección publicada de la herramienta. Solo desde ella (y desde este mismo programa) se
# aceptan pedidos: ninguna otra página web puede usar la API de este equipo.
URL_PUBLICADA = os.environ.get("PLUZ_URL_PUBLICADA", "https://ricardoamiel.github.io/CDC-Pluz-Poda/")
ORIGENES = {LOCAL, f"http://localhost:{PUERTO}",
            "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(URL_PUBLICADA))}

# Lo que se publica: lo mismo que la orden subir de actualizar.py.
PUBLICABLE = ["data", "index.html", "cargar/estado.json"]


# ----------------------------------------------------------------- recibir un archivo

def _nombre_lote():
    fecha = time.strftime("%Y%m%d")
    nombre, n = f"{fecha}_carga", 2
    while (config.LOTES / nombre).exists() or (EN_CURSO / nombre).exists():
        nombre, n = f"{fecha}_carga{n}", n + 1
    return nombre


def _fuente_por_nombre(nombre):
    from etapas.fuentes import _normalizar
    n = _normalizar(nombre)
    for fuente, esp in config.FUENTES.items():
        if any(fnmatch.fnmatch(n, _normalizar(p)) for p in esp["patrones"]):
            return fuente
    return None


def _csv_a_excel(origen, carpeta, nombre_lote):
    """Convierte el CSV al Excel que espera el contrato: nombre, hoja y fila de títulos."""
    import pandas as pd
    tabla = pd.read_csv(origen, sep=None, engine="python", encoding="utf-8-sig")
    tabla.columns = [str(c).strip() for c in tabla.columns]
    for fuente, esp in config.FUENTES.items():
        if all(c in tabla.columns for c in esp["columnas"]):
            patron = " ".join(esp["patrones"][0].replace("*", " ").replace(".xlsx", "").split())
            destino = carpeta / f"{patron} carga {nombre_lote}.xlsx"
            hoja = esp["hoja"] if isinstance(esp.get("hoja"), str) else "Hoja1"
            fila = esp["encabezado"] if isinstance(esp.get("encabezado"), int) else 0
            with pd.ExcelWriter(destino) as w:
                tabla.to_excel(w, sheet_name=hoja, startrow=fila, index=False)
            return fuente, destino
    raise ValueError("Las columnas del CSV no coinciden con ninguna fuente del contrato. "
                     f"Columnas recibidas: {list(tabla.columns)[:12]}")


def _claves(tabla, esp):
    """Cada fila como una tupla comparable: fecha al minuto, números redondeados, textos limpios."""
    import pandas as pd
    filas = pd.DataFrame(index=tabla.index)
    for c in esp["columnas"]:
        s = tabla[c]
        if c == esp.get("fecha"):
            s = pd.to_datetime(s, errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
        else:
            n = pd.to_numeric(s, errors="coerce")
            s = n.round(6).map(lambda v: repr(float(v))).where(n.notna(), s.astype(str).str.strip())
        filas[c] = s.fillna("").astype(str)
    return Counter(map(tuple, filas.values.tolist()))


def comparar(fuente, nueva):
    """Compara el archivo nuevo con lo que hoy está cargado en el periodo que reemplazaría."""
    import pandas as pd
    from etapas import fuentes
    esp = config.FUENTES[fuente]
    try:
        actual = fuentes.cargar(fuente, {})
    except fuentes.ErrorDeLote:
        actual = None
    res = {"modo": esp["modo"], "desde": None, "hasta": None, "posteriores": 0}
    if actual is None or not len(actual):
        actual = nueva.iloc[0:0]
    if esp["modo"] == "historico":
        fn = pd.to_datetime(nueva[esp["fecha"]], errors="coerce")
        fa = pd.to_datetime(actual[esp["fecha"]], errors="coerce")
        desde, hasta = fn.min(), fn.max()
        res["desde"], res["hasta"] = str(desde.date()), str(hasta.date())
        actual = actual[fa >= desde]   # el lote nuevo reemplaza todo desde su primera fecha
        res["posteriores"] = int((fa > hasta + pd.Timedelta(days=1)).sum())
    viejo, nuevo = _claves(actual, esp), _claves(nueva, esp)
    res.update({"filas_actuales": int(sum(viejo.values())), "filas_nuevas": int(sum(nuevo.values())),
                "agregadas": int(sum((nuevo - viejo).values())),
                "quitadas": int(sum((viejo - nuevo).values())),
                "iguales": int(sum((nuevo & viejo).values()))})
    res["sin_cambios"] = res["agregadas"] == 0 and res["quitadas"] == 0
    return res


def recibir_archivo(nombre, contenido):
    """Valida el archivo, lo compara con lo cargado y, si cambia algo, lo deja como lote nuevo.

    Si no cumple el contrato o es idéntico a lo que ya está, no queda nada guardado.
    """
    from etapas.fuentes import _leer
    nombre = Path(nombre).name
    if Path(nombre).suffix.lower() not in config.EXTENSIONES_LOTE:
        raise ValueError(f"Solo se aceptan {config.EXTENSIONES_LOTE}")
    lote = _nombre_lote()
    trabajo = EN_CURSO / lote
    trabajo.mkdir(parents=True)
    try:
        crudo = trabajo / nombre
        crudo.write_bytes(contenido)
        if crudo.suffix.lower() == ".csv":
            fuente, archivo = _csv_a_excel(crudo, trabajo, lote)
            crudo.unlink()
        else:
            fuente, archivo = _fuente_por_nombre(nombre), crudo
            if fuente is None:
                raise ValueError("El nombre no coincide con ninguna fuente. Ejemplo esperado: "
                                 "«Interrupciones diarias ....xlsx» o «PODA ... FORMATO UNIFICADO.xlsx»")
        tabla = _leer(archivo, config.FUENTES[fuente])
        res = {"fuente": fuente, "archivo": archivo.name, "filas": int(len(tabla)),
               "comparacion": comparar(fuente, tabla)}
        if res["comparacion"]["sin_cambios"]:
            res["lote"] = None
            return res
        config.LOTES.mkdir(parents=True, exist_ok=True)
        shutil.move(str(trabajo), str(config.LOTES / lote))
        res["lote"] = lote
        return res
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)


# ----------------------------------------------------------------- respaldo y restauración
# Antes de cada actualización desde la página se guarda una copia de lo que la carga va a
# cambiar. «Restaurar» devuelve esa copia y borra el lote: la herramienta queda como estaba
# antes de subir el archivo. Las corridas de MLflow no se borran: quedan como historial.

RESPALDOS = config.SALIDAS / "respaldos"
MAXIMO_RESPALDOS = 5
_NO_RESPALDAR = {"mlflow.db", "mlruns", "benchmark", "respaldos", "registros", "carga_en_curso"}


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


# ----------------------------------------------------------------- publicar

def _git(*args):
    return subprocess.run(["git", *args], cwd=config.REPO, capture_output=True, text=True)


def pendiente_de_publicar():
    if config.DEMO:
        return False
    r = _git("status", "--porcelain", "--", *PUBLICABLE)
    return r.returncode == 0 and bool(r.stdout.strip())


def publicar():
    """Publica la página con los datos nuevos: commit y push solo de lo publicable."""
    if config.DEMO:
        raise ValueError("En modo demostración no se publica nada.")
    if not pendiente_de_publicar():
        return {"ok": True, "log": "No hay cambios que publicar: la dirección publicada ya está al día."}
    reporte = config.SALIDAS / "reporte.json"
    corte = json.loads(reporte.read_text(encoding="utf-8")).get("corte", "") if reporte.exists() else ""
    log = []
    for paso in (["add", "--", *PUBLICABLE],
                 ["commit", "-m", f"Datos al corte {corte} (carga semanal)", "--", *PUBLICABLE],
                 ["push"]):
        r = _git(*paso)
        log.append(f"$ git {' '.join(paso)}\n{r.stdout}{r.stderr}".strip())
        if r.returncode != 0:
            return {"ok": False, "log": "\n\n".join(log)}
    return {"ok": True, "log": "\n\n".join(log)}


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
    base = {"reporte": {k: rep.get(k) for k in ("fecha", "corte", "ventana", "validacion",
                                                 "monitoreo", "publicado")},
            "fuentes": fuentes, "contrato": _contrato(), "mlflow": _mlflow(),
            "literatura": _literatura(not publico)}
    if publico:
        return {"modo": "estatico", "web": "../", **base}
    return {"modo": "local", "demo": bool(config.DEMO),
            # Direcciones absolutas: la página puede estar abierta en la dirección publicada.
            "web": f"{LOCAL}/web/" if config.DEMO else f"{LOCAL}/",
            "url_publicada": URL_PUBLICADA,
            "lotes": [p.name for p in sorted(config.LOTES.iterdir()) if p.is_dir()]
            if config.LOTES.exists() else [],
            "respaldos": respaldos(), "pendiente_publicar": pendiente_de_publicar(), **base}


def exportar():
    """Escribe cargar/estado.json, la foto que usa la página publicada."""
    if config.DEMO:
        return None   # el modo demostración nunca toca lo que se publica
    ESTADO_PUBLICO.write_text(json.dumps(estado(publico=True), ensure_ascii=False),
                              encoding="utf-8")
    return ESTADO_PUBLICO


# ----------------------------------------------------------------- servidor local

class Manejador(http.server.SimpleHTTPRequestHandler):
    """Sirve el repositorio (herramienta, benchmark y carga) y la API de carga en /api/."""

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(config.REPO), **k)

    def log_message(self, *a):
        pass

    def _origen_valido(self):
        origen = self.headers.get("Origin")
        return origen is None or origen in ORIGENES

    def end_headers(self):
        origen = self.headers.get("Origin")
        if origen in ORIGENES:
            # La página publicada puede leer las respuestas de este equipo; ninguna otra.
            self.send_header("Access-Control-Allow-Origin", origen)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_OPTIONS(self):
        # Consulta previa del navegador antes de un pedido desde la dirección publicada.
        if not self._origen_valido():
            self.send_error(403)
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Nombre")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/cargar":
            self.send_response(301)
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
        # Una página de otro sitio podría intentar un pedido a este equipo: se rechaza.
        if not self._origen_valido():
            self.send_error(403)
            return
        largo = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(largo)
        datos = {}
        if self.path != "/api/subir" and cuerpo:
            datos = json.loads(cuerpo)
        try:
            if self.path == "/api/subir":
                nombre = urllib.parse.unquote(self.headers.get("X-Nombre", "archivo.xlsx"))
                self._json(200, recibir_archivo(nombre, cuerpo))
            elif self.path == "/api/descartar":
                lote = Path(datos.get("lote") or "").name
                destino = config.LOTES / lote
                if "_carga" in lote and destino.is_dir():
                    shutil.rmtree(destino)
                self._json(200, {"ok": True})
            elif self.path == "/api/actualizar":
                respaldar(datos.get("lote", ""))   # para poder deshacer con «Restaurar»
                r = subprocess.run([sys.executable, str(PIPELINE / "actualizar.py")],
                                   cwd=config.REPO, capture_output=True, text=True)
                self._json(200, {"ok": r.returncode == 0, "codigo": r.returncode,
                                 "log": (r.stdout + r.stderr)[-6000:]})
            elif self.path == "/api/restaurar":
                self._json(200, {"ok": True, "restaurado": restaurar(datos.get("id"))})
            elif self.path == "/api/publicar":
                self._json(200, publicar())
            else:
                self.send_error(404)
        except Exception as e:  # el mensaje llega tal cual a la página
            self._json(400, {"error": str(e)})


def main():
    if sys.argv[1:2] == ["exportar"]:
        destino = exportar()
        print(f"Escrito {destino}" if destino else "En modo demostración no se exporta nada.")
        return
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    local = f"{LOCAL}/cargar/"
    publicada = urllib.parse.urljoin(URL_PUBLICADA, "cargar/")
    print(f"Carga semanal en {local}")
    print(f"También desde la dirección publicada, conectada a este equipo: {publicada}")
    print("Cierre con Ctrl y C.")
    webbrowser.open(publicada if sys.argv[1:2] == ["publicado"] else local)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
