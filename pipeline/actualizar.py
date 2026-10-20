# -*- coding: utf-8 -*-
"""Actualiza la herramienta con el último lote de datos de Pluz.

Uso, desde la raíz del repositorio:

    python pipeline/actualizar.py            corrida completa: valida, calcula y publica en data/
    python pipeline/actualizar.py semanal    recibe el lote, corre todo y copia la página al servidor
    python pipeline/actualizar.py recibir    arma un lote con lo que haya en la carpeta de entrada
    python pipeline/actualizar.py validar    solo revisa que los lotes cumplan el contrato
    python pipeline/actualizar.py calcular   calcula todo, pero no toca data/
    python pipeline/actualizar.py forzar     publica aunque el modelo quede bajo la regla
    python pipeline/actualizar.py reentrenar entrena un modelo vigente nuevo y publica
    python pipeline/actualizar.py ver        abre la página en el navegador, en local
    python pipeline/actualizar.py subir      sube data/ a GitHub, previa confirmación
    python pipeline/actualizar.py geografia  vuelve a bajar los límites de los distritos
    python pipeline/actualizar.py instalar   instala las bibliotecas, una sola vez
    python pipeline/actualizar.py instalar base   agrega las de la base de datos PostgreSQL
    python pipeline/actualizar.py benchmark  compara modelos y genera el reporte interactivo
    python pipeline/actualizar.py mlflow     abre MLflow: benchmark y monitoreo del modelo vigente

Etapas de la corrida completa:
    1. fuentes          localiza los archivos en los lotes y valida columnas
    2. base analítica   una fila por alimentador y mes, con variables y objetivo
    3. modelo           mide fuera de muestra, reentrena y predice el último corte
    4. índice           índice de criticidad por distrito y escritura de data/
    5. salidas          plan en Excel, reporte y, si está configurada, la base de datos
"""
import json
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPELINE))

import config  # noqa: E402

ORDENES = ["completa", "semanal", "recibir", "validar", "calcular", "forzar", "reentrenar", "ver",
           "subir", "geografia", "instalar", "benchmark", "mlflow"]

# Si el modelo queda claramente peor que la regla por historial, la corrida no publica:
# algo cambió en los datos y alguien tiene que revisarlo antes de que llegue a la página.
MARGEN_MAXIMO_BAJO_LA_REGLA = 0.10


def paso(texto):
    print(f"\n[{time.strftime('%H:%M:%S')}] {texto}")


def pct(v):
    return f"{100 * v:.1f}".replace(".", ",") + " %"


def dec(v, cifras=3):
    return f"{v:.{cifras}f}".replace(".", ",")


def puntos(v):
    signo = "más" if v >= 0 else "menos"
    return f"{signo} {abs(100 * v):.1f}".replace(".", ",")


def reporte_markdown(rep, nombre_mes):
    """Reporte de la corrida, sin tablas ni guiones, para leerlo en cualquier visor."""
    v = rep["validacion"]
    m, r = v["modelo"], v["regla"]
    mes = lambda texto: nombre_mes(texto)  # noqa: E731
    lineas = [
        f"# Reporte de la corrida del {rep['fecha']}", "",
        f"Corte predicho: **{mes(rep['corte'])}**. Ventana: {rep['ventana']}.", "",
        "## Fuentes usadas", "",
    ]
    for fuente, info in rep["fuentes"].items():
        if isinstance(info, dict) and "archivos" in info:
            origen = "; ".join(info["archivos"]) or "ninguno"
            lineas.append(f"* {fuente}: {info['filas']} filas, de {origen}.")
    lineas += ["", "## Avisos", ""]
    lineas += [f"* {a}." for a in rep["fuentes"]["avisos"]] or ["* Ninguno."]
    lineas += [
        "", "## Modelo vigente", "",
        f"Entrenado el {rep['modelo_vigente']['entrenado']}, con los meses hasta "
        f"{mes(rep['modelo_vigente']['entrenado_hasta'])}. "
        + ("Tiene una recalibración de la probabilidad aplicada." if rep["modelo_vigente"]["calibracion"]
           else "No tiene recalibraciones."), "",
    ]
    mon = rep.get("monitoreo")
    if not mon:
        lineas.append("Se entrenó en esta corrida, así que todavía no hay monitoreo.")
    elif "pr_auc_modelo" not in mon:
        lineas.append(f"Monitoreo: {mon['lectura']}")
    else:
        lineas += [
            f"Monitoreo en {mon['meses_nuevos']} meses nuevos, de {mes(mon['desde'])} a {mes(mon['hasta'])}, "
            f"con {mon['eventos']} eventos:", "",
            f"* PR AUC: modelo {dec(mon['pr_auc_modelo'])}, regla {dec(mon['pr_auc_regla'])}.",
            f"* Cobertura con lista de 40: modelo {pct(mon['cobertura_40_modelo'])}, regla {pct(mon['cobertura_40_regla'])}.",
            f"* Frecuencia observada sobre probabilidad media: {dec(mon['razon_observado_esperado'], 2)}.",
            f"* Recalibración: {'aplicada' if mon.get('recalibrado') else 'no hizo falta' if not mon['recalibrar'] else 'pendiente por pocos eventos'}.",
            f"* Reentrenamiento: {'recomendado' if mon['reentrenamiento_recomendado'] else 'no hace falta'}.",
        ]
    lineas += [
        "", "## Desempeño medido al entrenar el modelo vigente", "",
        f"El modelo se entrenó con los cortes de {mes(v['entrenamiento'][0])} a "
        f"{mes(v['entrenamiento'][1])} y se probó con los de {mes(v['prueba'][0])} a "
        f"{mes(v['prueba'][1])}, con una prevalencia de {pct(v['prevalencia_prueba'])}.", "",
        "Proporción de los eventos que captura la lista de cada mes:", "",
    ]
    for k in (20, 40, 80):
        lineas.append(f"* Lista de {k} alimentadores: modelo {pct(m[f'cobertura_{k}'])}, "
                      f"regla por historial {pct(r[f'cobertura_{k}'])}.")
    d40 = v["diferencia_con_regla_lista_40"]
    lineas += [
        "",
        f"Precisión media: modelo {dec(m['ap'])}, regla {dec(r['ap'])}. Área bajo la curva "
        f"ROC: modelo {dec(m['auc'])}, regla {dec(r['auc'])}.", "",
        f"Diferencia con la regla en la lista de 40, remuestreando alimentadores: "
        f"{puntos(d40['media'])} puntos, con un intervalo del 95 % entre {puntos(d40['li'])} "
        f"y {puntos(d40['ls'])} puntos.", "",
        "## Por distrito", "",
    ]
    for d in v["por_distrito"]:
        lineas.append(f"* **{d['distrito']}**, lista de {d['lista']} y {d['eventos_prueba']} "
                      f"eventos de prueba: modelo {pct(d['cobertura_modelo'])}, regla "
                      f"{pct(d['cobertura_regla'])}.")
    lineas += ["", f"Publicado en data: {'sí' if rep['publicado'] else 'no'}.",
               f"Guardado en la base de datos: {'sí' if rep['base_de_datos'] else 'no configurada'}."]
    return "\n".join(lineas) + "\n"


def corrida(publicar=True, forzar=False, reentrenar=False):
    import pandas as pd
    from etapas import fuentes, base_analitica, modelo, indice, salidas

    paso("1. Fuentes: localizar y validar los lotes")
    try:
        tablas, registro = fuentes.cargar_todo()
    except fuentes.ErrorDeLote as error:
        print(f"\nEL LOTE NO CUMPLE EL CONTRATO DE DATOS:\n  {error}")
        sys.exit(2)
    for f, info in registro.items():
        if isinstance(info, dict):
            print(f"  {f}: {info['filas']} filas; {'; '.join(info['archivos'])}")
    for aviso in registro["avisos"]:
        print(f"  AVISO: {aviso}")
    print(f"  Interrupciones del {registro['periodo_interrupciones'][0]} al "
          f"{registro['periodo_interrupciones'][1]}")
    if publicar is None:
        print("\nLos lotes cumplen el contrato de datos.")
        return

    paso("2. Base analítica de alimentador y mes")
    panel, corte, inicio = base_analitica.construir(tablas)
    print(f"  {len(panel)} filas, {panel['alimentador'].nunique()} alimentadores, "
          f"corte operativo {indice.nombre_mes(corte)}")

    paso("3. Modelo vigente: monitoreo, calibración y predicción")
    alim_distrito = indice.alimentadores_por_distrito(tablas["guia"])
    vigente, ficha = (None, None) if reentrenar else modelo.cargar_vigente()
    recien_entrenado = vigente is None
    monitoreo = None
    if vigente is None:
        # Solo se entrena la primera vez o cuando se pide de forma explícita. Antes de guardar
        # el modelo se mide fuera de muestra: si queda claramente bajo la regla, no se publica.
        print("  Entrenando el modelo vigente con todos los meses que ya tienen resultado")
        validacion, etiquetados = modelo.validar(panel, inicio, alim_distrito)
        m, r = validacion["modelo"], validacion["regla"]
        print(f"  Medición fuera de muestra, lista de 40: modelo {pct(m['cobertura_40'])}, "
              f"regla {pct(r['cobertura_40'])}")
        peor = r["cobertura_40"] - m["cobertura_40"]
        if peor > MARGEN_MAXIMO_BAJO_LA_REGLA and not forzar:
            print(f"  ALTO: el modelo queda {100 * peor:.1f} puntos bajo la regla por historial. "
                  "No se guarda ni se publica; revise el lote o corra la orden forzar.")
            return
        vigente, ficha = modelo.entrenar_vigente(etiquetados, validacion)
        print(f"  Modelo vigente guardado, entrenado hasta {indice.nombre_mes(pd.Period(ficha['entrenado_hasta'], freq='M'))}")
    else:
        print(f"  Modelo vigente del {ficha['entrenado']}, entrenado hasta "
              f"{indice.nombre_mes(pd.Period(ficha['entrenado_hasta'], freq='M'))}")
        monitoreo, nuevos = modelo.monitorear(vigente, ficha, panel)
        if monitoreo["meses_nuevos"] == 0 or "pr_auc_modelo" not in monitoreo:
            print(f"  Monitoreo: {monitoreo.get('lectura', 'sin meses nuevos con resultado.')}")
        else:
            print(f"  Monitoreo en {monitoreo['meses_nuevos']} meses nuevos: PR AUC modelo "
                  f"{monitoreo['pr_auc_modelo']:.3f}, regla {monitoreo['pr_auc_regla']:.3f}; "
                  f"observado sobre esperado {monitoreo['razon_observado_esperado']:.2f}")
            if monitoreo["recalibrar"]:
                ficha, hecho = modelo.recalibrar(vigente, ficha, nuevos)
                monitoreo["recalibrado"] = hecho
                print("  Probabilidad recalibrada; el orden del ranking no cambia." if hecho else
                      "  Hace falta recalibrar, pero todavía no hay eventos suficientes.")
            if monitoreo["reentrenamiento_recomendado"]:
                print("  AVISO: el ordenamiento cayó frente a la regla por historial. "
                      "Se recomienda revisar y correr la orden reentrenar.")
    validacion = ficha["validacion"]
    operativo = panel[panel["periodo"] == corte].copy()
    operativo["probabilidad"] = modelo.predecir(vigente, ficha, operativo)
    modelo_final = vigente

    paso("4. Índice de criticidad por distrito")
    periodo_datos = [indice.nombre_mes(tablas["fallas"]["periodo"].min()),
                     indice.nombre_mes(corte)]
    distritos, postes = indice.construir_distritos(tablas, operativo, modelo_final, corte,
                                              periodo_datos)
    for d in distritos.values():
        mt = d["meta"]
        print(f"  {mt['distrito']}: {mt['n_alimentadores']} alimentadores, "
              f"{mt['n_subestaciones']} SED aéreas, plan de {mt['k_alimentadores']} "
              f"alimentadores o {mt['capacidad_mes']} subestaciones")
    # Modelo alternativo, solo para comparar en la página: se entrena con el vigente, con los
    # mismos meses, y se reutiliza mientras el vigente no cambie.
    alterno = None if recien_entrenado else modelo.cargar_alterno()
    if alterno is None:
        etiq = panel[(panel["periodo"] >= inicio) & panel["objetivo"].notna()]
        alterno = modelo.entrenar_alterno(etiq)
        print(f"  Modelo alternativo {config.MODELO_ALTERNO['nombre']} entrenado con los mismos meses")
    operativo_alt = operativo.copy()
    operativo_alt["probabilidad"] = modelo.predecir_alterno(alterno, operativo_alt)
    distritos_alt, _ = indice.construir_distritos(
        tablas, operativo_alt, alterno, corte, periodo_datos,
        motivos_fn=lambda d: modelo.motivos_alterno(alterno, d), solo=[config.PILOTO],
        nombre_modelo=config.MODELO_ALTERNO["nombre"])
    codigo = config.DISTRITOS[config.PILOTO][0]
    for nivel, k in (("alimentadores", distritos[codigo]["meta"]["k_alimentadores"]),
                     ("subestaciones", distritos[codigo]["meta"]["capacidad_mes"])):
        a = {u["id"]: u["puesto"] for u in distritos[codigo][nivel]}
        b = {u["id"]: u["puesto"] for u in distritos_alt[codigo][nivel]}
        comunes = [i for i in a if i in b]
        rho = pd.Series([a[i] for i in comunes]).corr(pd.Series([b[i] for i in comunes]), method="spearman")
        coinciden = len({i for i in a if a[i] <= k} & {i for i in b if b[i] <= k})
        print(f"  Piloto por {nivel}: correlación de orden entre modelos {rho:.3f}; "
              f"{coinciden} de {k} unidades del plan coinciden")

    if publicar:
        print("  Publicando en data:")
        for nombre, kb in indice.publicar(distritos).items():
            print(f"    {nombre}: {kb} kB")
        for nombre, kb in indice.publicar_alterno(distritos_alt).items():
            print(f"    {nombre}: {kb} kB")
        for nombre, kb in indice.publicar_postes(postes).items():
            print(f"    {nombre}: {kb} kB")

    paso("5. Salidas para la operación")
    config.SALIDAS.mkdir(parents=True, exist_ok=True)
    sufijo = corte.strftime("%Y%m")
    panel.to_csv(config.SALIDAS / "base_analitica_alimentador_mes.csv", index=False)
    operativo[["alimentador", "periodo", "probabilidad"] + config.VARIABLES].sort_values(
        "probabilidad", ascending=False).to_csv(config.SALIDAS / "prediccion.csv", index=False)
    excel = salidas.escribir_excel(distritos, corte,
                                   config.SALIDAS / f"plan_de_poda_{sufijo}.xlsx")
    print(f"  Plan en Excel: {excel}")

    rep = {"fecha": time.strftime("%Y%m%d %H:%M"), "corte": str(corte),
           "ventana": indice.ventana(corte), "fuentes": registro,
           "validacion": validacion, "publicado": bool(publicar),
           "modelo_vigente": {k: ficha[k] for k in ("entrenado", "entrenado_hasta", "calibracion")},
           "monitoreo": monitoreo}
    rep["base_de_datos"] = salidas.guardar_en_base(tablas, panel, operativo, distritos, rep)
    print(f"  Base de datos: {'actualizada' if rep['base_de_datos'] else 'no configurada'}")

    nombre_mes = lambda t: indice.nombre_mes(pd.Period(t, freq="M"))  # noqa: E731
    (config.SALIDAS / "reporte.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    (config.SALIDAS / "reporte.md").write_text(reporte_markdown(rep, nombre_mes),
                                               encoding="utf-8")
    if modelo.registrar_mlflow(rep):
        print("  Corrida registrada en MLflow, experimento pluz_modelo_vigente")
    print(f"\nListo. Reporte en {config.SALIDAS / 'reporte.md'}")
    if publicar:
        print("Siguiente paso: revisar con la orden ver y publicar con la orden subir.")


def benchmark():
    """Compara modelos con la partición del pipeline y escribe el reporte interactivo."""
    from etapas import fuentes, base_analitica, benchmark as bm, reporte_benchmark

    paso("Benchmark de modelos: fuentes y base analítica")
    tablas, _ = fuentes.cargar_todo()
    panel, corte, inicio = base_analitica.construir(tablas)

    # Variables del índice en el último corte, para medir su relación con las del modelo.
    guia = tablas["guia"]
    expo = guia[guia["aerea"]].groupby("ALIM").agg(clientes=("clientes", "sum"), kva=("kva", "sum"))
    operativo = panel[panel["periodo"] == corte].copy()
    operativo["saidi_ltm"] = operativo["alimentador"].map(tablas["saidi_ltm"])
    operativo = operativo.join(expo, on="alimentador")

    paso("Entrenando y evaluando los modelos")
    from etapas import indice
    piloto = indice.alimentadores_por_distrito(guia)[config.PILOTO]
    resultados = bm.ejecutar(panel, inicio, corte, operativo, piloto)
    carpeta = config.SALIDAS / "benchmark"
    carpeta.mkdir(parents=True, exist_ok=True)
    reporte = reporte_benchmark.escribir(resultados, carpeta / "benchmark_modelos.html")
    uri = bm.registrar_mlflow(resultados, reporte)
    # Copia publicable: GitHub Pages sirve la carpeta benchmark como un segundo enlace. Solo
    # lleva métricas, curvas y algunos ejemplos por alimentador, nada de los Excel de Pluz.
    publico = config.REPO / "benchmark"
    publico.mkdir(exist_ok=True)
    (publico / "index.html").write_text(reporte.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"\nModelo recomendado: {resultados['decision']['modelo']}")
    print(f"Reporte: {reporte}")
    print(f"Copia para GitHub Pages: {publico / 'index.html'}")
    print("Corridas en MLflow: abrir con la orden mlflow" if uri else "MLflow no está instalado")
    webbrowser.open(reporte.as_uri())


def abrir_mlflow(puerto=5000):
    base = config.SALIDAS / "mlflow.db"
    if not base.exists():
        print("Todavía no hay corridas registradas: corra la actualización o el benchmark.")
        return
    # Se abre directo en el seguimiento del modelo vigente, que es lo que se mira cada semana.
    import sqlite3
    with sqlite3.connect(base) as conexion:
        fila = conexion.execute("select experiment_id from experiments where name = ?",
                                ("pluz_modelo_vigente",)).fetchone()
    url = f"http://127.0.0.1:{puerto}/#/experiments/{fila[0]}" if fila else f"http://127.0.0.1:{puerto}"
    print(f"MLflow en {url}. Cierre con Ctrl y C. Mientras está abierto, use otra terminal.")
    threading_timer = __import__("threading").Timer(4, lambda: webbrowser.open(url))
    threading_timer.start()
    subprocess.run([sys.executable, "-m", "mlflow", "ui", "--backend-store-uri", f"sqlite:///{base}",
                    "--port", str(puerto)], cwd=config.SALIDAS)


def recibir():
    """Copia el Excel de la carpeta de entrada a un lote nuevo y deja los originales en procesados.

    Devuelve la carpeta del lote creado, o nada si no había archivos nuevos. Así la tarea
    programada puede correr cada lunes aunque esa semana no haya llegado nada.
    """
    import shutil
    if not config.CARPETA_ENTRADA:
        print("  No hay carpeta de entrada configurada (variable PLUZ_CARPETA_ENTRADA).")
        return None
    entrada = Path(config.CARPETA_ENTRADA)
    if not entrada.is_dir():
        print(f"  La carpeta de entrada no existe: {entrada}")
        return None
    archivos = [a for a in entrada.iterdir()
                if a.is_file() and a.suffix.lower() in config.EXTENSIONES_LOTE and not a.name.startswith("~$")]
    if not archivos:
        print("  No hay archivos nuevos en la carpeta de entrada; se usan los lotes que ya existen.")
        return None
    fecha = time.strftime("%Y%m%d")
    lote = config.LOTES / f"{fecha}_semanal"
    n = 2
    while lote.exists():
        lote = config.LOTES / f"{fecha}_semanal{n}"
        n += 1
    lote.mkdir(parents=True)
    procesados = entrada / "procesados" / lote.name
    procesados.mkdir(parents=True, exist_ok=True)
    for archivo in archivos:
        shutil.copy2(archivo, lote / archivo.name)
        shutil.move(str(archivo), procesados / archivo.name)
        print(f"  {archivo.name}")
    print(f"  Lote nuevo: {lote.name}, con {len(archivos)} archivos. Originales en procesados.")
    return lote


def copiar_web():
    """Copia la página con sus datos nuevos a la carpeta del servidor web interno."""
    import shutil
    if not config.CARPETA_WEB:
        print("  No hay carpeta web configurada (variable PLUZ_CARPETA_WEB): la página no se copia.")
        return
    destino = Path(config.CARPETA_WEB)
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ("index.html", ".nojekyll"):
        if (config.REPO / nombre).exists():
            shutil.copy2(config.REPO / nombre, destino / nombre)
    for carpeta in ("css", "js", "assets"):
        shutil.copytree(config.REPO / carpeta, destino / carpeta, dirs_exist_ok=True)
    shutil.copytree(config.DATA_WEB, destino / "data", dirs_exist_ok=True)
    print(f"  Página copiada a {destino}")


def semanal():
    """Lo que corre la tarea de cada lunes: recibir, actualizar y copiar la página."""
    paso("Recibiendo el lote de la semana")
    recibir()
    corrida(publicar=True)
    paso("Copiando la página al servidor web interno")
    copiar_web()


def ver(puerto=8000):
    """Sirve el repositorio en local y abre la página."""
    import functools
    import http.server
    # Sirve la carpeta de la página: el repositorio, o la página propia del modo demostración.
    manejador = functools.partial(http.server.SimpleHTTPRequestHandler,
                                  directory=str(config.DATA_WEB.parent))
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), manejador)
    url = f"http://127.0.0.1:{puerto}/"
    print(f"Página en {url}. Cierre con Ctrl y C.")
    webbrowser.open(url)
    servidor.serve_forever()


def subir():
    """Publica data/ en GitHub: git add, commit y push, previa confirmación."""
    reporte = config.SALIDAS / "reporte.json"
    if not reporte.exists():
        print("Primero hay que correr la actualización completa.")
        return
    corte = json.loads(reporte.read_text(encoding="utf-8"))["corte"]
    git = lambda *a: subprocess.run(["git", *a], cwd=config.REPO, check=True)  # noqa: E731
    subprocess.run(["git", "status", "--short", "data", "index.html"], cwd=config.REPO)
    if input(f"¿Publicar los datos del corte {corte} en GitHub? Escriba si: ").strip().lower() \
            not in ("si", "sí"):
        print("No se publicó nada.")
        return
    git("add", "data", "index.html")
    git("commit", "-m", f"Datos al corte {corte}")
    git("push")
    print("Publicado. GitHub Pages tarda uno o dos minutos en mostrar la versión nueva.")


def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else "completa"
    if orden not in ORDENES:
        print(__doc__)
        sys.exit(1)
    if orden == "instalar":
        # «instalar base» agrega las bibliotecas para PostgreSQL; SQLite no necesita nada.
        archivo = ("requirements_base_de_datos.txt" if sys.argv[2:3] == ["base"]
                   else "requirements.txt")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r",
                        str(PIPELINE / archivo)], check=True)
    elif orden == "geografia":
        from etapas import geografia
        geografia.descargar()
    elif orden == "ver":
        ver()
    elif orden == "recibir":
        recibir()
    elif orden == "semanal":
        semanal()
    elif orden == "benchmark":
        benchmark()
    elif orden == "mlflow":
        abrir_mlflow()
    elif orden == "subir":
        subir()
    elif orden == "validar":
        corrida(publicar=None)
    else:
        corrida(publicar=orden != "calcular", forzar=orden == "forzar",
                reentrenar=orden == "reentrenar")


if __name__ == "__main__":
    main()
