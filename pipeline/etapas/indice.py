# -*- coding: utf-8 -*-
"""Etapa 4. Índice de criticidad por distrito y escritura de los datos de la página.

El índice combina cuatro componentes, cada uno como percentil dentro del distrito, con los
pesos de config.PESOS. Se calcula en dos niveles con los mismos componentes: alimentador,
para programar el mes, y subestación aérea, para despachar la cuadrilla.
"""
import json
import re

import numpy as np
import pandas as pd

import config
from etapas.modelo import motivos

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "setiembre", "octubre", "noviembre", "diciembre"]


def nombre_mes(periodo):
    return f"{MESES[periodo.month - 1]} de {periodo.year}"


def ventana(corte):
    """Texto de los tres meses que predice el corte: «setiembre a noviembre de 2026»."""
    a, b = corte + 1, corte + config.HORIZONTE_MESES
    if a.year == b.year:
        return f"{MESES[a.month - 1]} a {MESES[b.month - 1]} de {b.year}"
    return f"{nombre_mes(a)} a {nombre_mes(b)}"


def _pctl(serie):
    return serie.rank(pct=True) * 100


def calcular_indice(d):
    d = d.copy()
    d["c_probabilidad"] = _pctl(d["probabilidad"])
    d["c_reloj_poda"] = _pctl(d["meses_sin_poda"])
    d["c_criticidad"] = _pctl(d["saidi_ltm"])
    d["c_exposicion"] = _pctl(0.5 * _pctl(d["clientes"]) + 0.5 * _pctl(d["kva"]))
    d["indice"] = sum(config.PESOS[k] * d["c_" + k] for k in config.PESOS)
    d = d.sort_values("indice", ascending=False).reset_index(drop=True)
    d["puesto"] = np.arange(1, len(d) + 1)
    return d


def _r(v, dec=3):
    return None if pd.isna(v) else round(float(v), dec)


def alimentadores_por_distrito(guia):
    return {d: sorted(set(guia.loc[(guia["DISTRITO"] == d) & guia["aerea"], "ALIM"]))
            for d in config.DISTRITOS}


def construir_distritos(tablas, operativo, modelo, corte, periodo_datos):
    guia, poda, saidi = tablas["guia"], tablas["poda"], tablas["saidi_ltm"]
    alim_distrito = alimentadores_por_distrito(guia)
    operativo = operativo.copy()
    operativo["saidi_ltm"] = operativo["alimentador"].map(saidi)
    serie_poda = poda.groupby(["ALIMENTADOR", "periodo"]).size()
    anio_capacidad = corte.year - 1   # último año completo de registro de poda
    proporcion_piloto = None
    salida = {}

    # El piloto va primero: su capacidad fija la proporción de los demás.
    orden = [config.PILOTO] + [d for d in config.DISTRITOS if d != config.PILOTO]
    for distrito in orden:
        codigo, nombre, _ = config.DISTRITOS[distrito]
        gd = guia[guia["DISTRITO"] == distrito]
        aer = gd[gd["aerea"]].dropna(subset=["lon", "lat"])
        op = operativo[operativo["alimentador"].isin(alim_distrito[distrito])].copy()
        op["saidi_ltm"] = op["saidi_ltm"].fillna(op["saidi_ltm"].median())

        sed = aer.merge(op, left_on="ALIM", right_on="alimentador", how="inner")
        sed["clientes"] = sed["clientes"].fillna(0)
        sed["kva"] = sed["kva"].fillna(sed["kva"].median())
        sed = calcular_indice(sed)

        expo = aer.groupby("ALIM").agg(clientes=("clientes", "sum"), kva=("kva", "sum"),
                                       sed_aereas=("SED", "nunique"),
                                       lon=("lon", "mean"), lat=("lat", "mean")).reset_index()
        alim = calcular_indice(op.merge(expo, left_on="alimentador", right_on="ALIM"))
        alim["motivos"] = motivos(modelo, alim)

        # Capacidad del plan por subestación: la mediana mensual de podas registradas el
        # último año completo en los alimentadores del distrito. Fuera del piloto el
        # registro está muy incompleto, y ahí se usa la misma proporción que el piloto.
        reg = serie_poda[serie_poda.index.get_level_values(0).isin(set(gd["ALIM"]))]
        reg = reg[reg.index.get_level_values(1).year == anio_capacidad].groupby(level=1).sum()
        reg = reg.reindex(pd.period_range(f"{anio_capacidad}-01", f"{anio_capacidad}-12",
                                          freq="M"), fill_value=0)
        capacidad_registro = int(np.median(reg.values))
        if distrito == config.PILOTO:
            capacidad = int(min(len(sed), capacidad_registro))
            proporcion_piloto = capacidad / max(1, len(sed))
            regla = f"registro de poda {anio_capacidad}"
        else:
            capacidad = int(round(len(sed) * proporcion_piloto))
            regla = "misma proporción que el piloto"
        k_alim = max(5, int(round(len(alim) / 3)))

        todos = operativo[operativo["alimentador"].isin(set(gd["ALIM"]))]
        resumen = {
            "sed_total": int(gd["SED"].nunique()), "sed_aereas": int(len(sed)),
            "alimentadores": int(len(alim)), "alimentadores_total": int(gd["ALIM"].nunique()),
            "clientes_expuestos": int(alim["clientes"].sum()),
            "riesgo_medio": _r(alim["probabilidad"].mean(), 4),
            "saidi_ltm": _r(todos["saidi_ltm"].sum(), 2),
            "interrupciones_12m": int(todos["eventos_12m"].sum()),
            "interrupciones_hist": int(todos["eventos_hist"].sum()),
            "cortes_vegetacion": int(todos["veg_hist"].sum()),
            "cortes_vegetacion_12m": int(todos["veg_12m"].sum()),
            "cortes_veg_por_100_sed": _r(100 * todos["veg_hist"].sum() / max(1, len(sed)), 1),
            "meses_sin_poda_mediana": _r(alim["meses_sin_poda"].median(), 0),
            "plan_clientes_share": _r(alim.head(k_alim)["clientes"].sum() /
                                      max(1, alim["clientes"].sum()), 4),
        }
        meta = {
            "distrito": nombre, "codigo": codigo, "corte": str(corte),
            "ventana": ventana(corte), "horizonte_meses": config.HORIZONTE_MESES,
            "periodo_datos": periodo_datos,
            "pesos": config.PESOS, "nombres_componentes": dict(config.COMPONENTES),
            "capacidad_mes": capacidad, "capacidad_registro_poda": capacidad_registro,
            "capacidad_regla": regla, "k_alimentadores": k_alim,
            "modelo": "Regresión logística sin SAIDI ni clientes",
            "variables_modelo": [config.NOMBRES_VARIABLES[v] for v in config.VARIABLES],
            "generado": pd.Timestamp.today().strftime("%Y-%m-%d"),
            "n_alimentadores": int(len(alim)), "n_subestaciones": int(len(sed)),
            "n_no_expuestas": int((~gd["aerea"]).sum()), "resumen": resumen,
        }
        comp = config.COMPONENTES
        salida[codigo] = {
            "meta": meta,
            "alimentadores": [{
                "id": f.alimentador, "puesto": int(f.puesto), "indice": _r(f.indice, 1),
                "probabilidad": _r(f.probabilidad, 4),
                "componentes": {n: _r(getattr(f, c), 1) for c, n in comp},
                "clientes": int(f.clientes), "kva": _r(f.kva, 0),
                "sed_aereas": int(f.sed_aereas), "meses_sin_poda": _r(f.meses_sin_poda, 0),
                "sin_registro_poda": bool(f.sin_registro_poda),
                "saidi_ltm": _r(f.saidi_ltm, 2), "eventos_historicos": int(f.veg_hist),
                "eventos_12m": int(f.veg_12m), "interrupciones_12m": int(f.eventos_12m),
                "interrupciones_hist": int(f.eventos_hist),
                "lon": _r(f.lon, 5), "lat": _r(f.lat, 5), "motivos": f.motivos,
            } for f in alim.itertuples()],
            "subestaciones": [{
                "id": f.SED, "alimentador": f.ALIM, "puesto": int(f.puesto),
                "indice": _r(f.indice, 1), "probabilidad": _r(f.probabilidad, 4),
                "componentes": {n: _r(getattr(f, c), 1) for c, n in comp},
                "clientes": int(f.clientes), "kva": _r(f.kva, 0),
                "meses_sin_poda": _r(f.meses_sin_poda, 0),
                "sin_registro_poda": bool(f.sin_registro_poda), "saidi_ltm": _r(f.saidi_ltm, 2),
                "interrupciones_12m": int(f.eventos_12m),
                "interrupciones_hist": int(f.eventos_hist),
                "direccion": str(f.DIRECCION)[:60], "lon": _r(f.lon, 5), "lat": _r(f.lat, 5),
            } for f in sed.itertuples()],
            "no_expuestas": [{"lon": _r(f.lon, 5), "lat": _r(f.lat, 5)}
                             for f in gd[~gd["aerea"]].dropna(subset=["lon", "lat"]).itertuples()],
        }
    return salida, alim_distrito


def _escribir(nombre, variable, contenido):
    texto = json.dumps(contenido, ensure_ascii=False, separators=(",", ":"))
    (config.DATA_WEB / f"{nombre}.json").write_text(texto, encoding="utf-8")
    (config.DATA_WEB / f"{nombre}.js").write_text(f"window.{variable} = {texto};\n",
                                                  encoding="utf-8")
    return round(len(texto.encode()) / 1024)


def publicar(distritos):
    """Escribe en data/ los tres archivos que carga la página. Devuelve sus tamaños en kB."""
    codigo_piloto = config.DISTRITOS[config.PILOTO][0]
    orden = [config.DISTRITOS[d][0] for d in config.DISTRITOS]

    # La comparación no abre la ficha completa de cada subestación: basta con lo que se
    # muestra al pasar el puntero, y así el archivo baja a la mitad.
    campos_sed = ("id", "alimentador", "puesto", "indice", "probabilidad", "clientes",
                  "meses_sin_poda", "sin_registro_poda", "saidi_ltm", "interrupciones_12m",
                  "direccion", "lon", "lat")
    ligeros = {c: {**v, "subestaciones": [{k: s[k] for k in campos_sed}
                                         for s in v["subestaciones"]]}
               for c, v in distritos.items()}

    geo = json.loads((config.REFERENCIA / "geografia_distritos.json").read_text(encoding="utf-8"))
    limites = {config.DISTRITOS[d][0]: geo["distritos"][d]["anillos"] for d in config.DISTRITOS}
    # Para el piloto se conserva su límite más detallado, el que ya usa la pestaña principal.
    lo = json.loads((config.DATA_WEB / "geografia_los_olivos.json").read_text(encoding="utf-8"))
    limites[codigo_piloto] = [lo["limite"]]

    # La versión en la dirección de cada archivo de datos obliga al navegador a bajar los
    # nuevos tras cada actualización, en lugar de mostrar los de la semana anterior.
    version = pd.Timestamp.today().strftime("%Y%m%d%H%M")
    pagina = config.REPO / "index.html"
    html = pagina.read_text(encoding="utf-8")
    html = re.sub(r'(src="data/[a-z_]+\.js)(\?v=[0-9]+)?"', rf'\1?v={version}"', html)
    pagina.write_text(html, encoding="utf-8")

    return {
        "criticidad_los_olivos": _escribir("criticidad_los_olivos", "DATOS_PLUZ",
                                           distritos[codigo_piloto]),
        "distritos": _escribir("distritos", "DATOS_DISTRITOS",
                               {"orden": orden, "distritos": ligeros}),
        "geografia_distritos": _escribir("geografia_distritos", "GEO_DISTRITOS",
                                         {"fuente": geo["fuente"], "limites": limites}),
    }
