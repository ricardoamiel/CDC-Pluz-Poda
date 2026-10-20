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


def asignar_postes(postes, guia):
    """Asigna cada poste de media tensión a la subestación aérea más cercana.

    La base de postes no trae alimentador ni subestación. La subestación más cercana, si está
    a menos de config.DISTANCIA_POSTE_SED_M, es una aproximación suficiente para ubicar en
    la calle la zona de una unidad del plan; no se usa para nada que entre al índice.
    """
    from scipy.spatial import cKDTree

    aer = guia[guia["aerea"]].dropna(subset=["lon", "lat"])
    escala = np.array([111320 * np.cos(np.radians(-12)), 110574])   # metros por grado en Lima
    arbol = cKDTree(aer[["lon", "lat"]].to_numpy() * escala)
    dist, i = arbol.query(postes[["lon", "lat"]].to_numpy() * escala)
    cerca = dist <= config.DISTANCIA_POSTE_SED_M
    postes = postes.copy()
    postes["sed"] = np.where(cerca, aer["SED"].to_numpy()[i], None)
    postes["alim"] = np.where(cerca, aer["ALIM"].to_numpy()[i], None)
    return postes


def _sed_de_circuito(circuito):
    """Primer código de subestación dentro del circuito de poda («02574A_15380A» da 02574A)."""
    m = re.search(r"\d{5}[A-Z]", str(circuito))
    return m.group(0) if m else None


def construir_distritos(tablas, operativo, modelo, corte, periodo_datos, motivos_fn=None, solo=None,
                        nombre_modelo="Regresión logística sin SAIDI ni clientes"):
    guia, poda, saidi = tablas["guia"], tablas["poda"], tablas["saidi_ltm"]
    alim_distrito = alimentadores_por_distrito(guia)
    operativo = operativo.copy()
    operativo["saidi_ltm"] = operativo["alimentador"].map(saidi)
    serie_poda = poda.groupby(["ALIMENTADOR", "periodo"]).size()
    anio_capacidad = corte.year - 1   # último año completo de registro de poda

    # Interrupciones probables de vegetación del último año, separadas en las dos partes que
    # agrupa el piloto: árbol (crecimiento o tala) y no ubicada en red aérea.
    fallas = tablas["fallas"]
    ultimo_anio = (fallas["periodo"] > corte - 12) & (fallas["periodo"] <= corte)
    arbol = fallas["Causa"].isin(config.CAUSAS_VEGETACION)
    no_ubicada = fallas["veg_ampliada"] & ~arbol
    veg_detalle = pd.DataFrame({
        "veg_arbol_12m": fallas[ultimo_anio & arbol].groupby("Alimentador").size(),
        "no_ubicada_12m": fallas[ultimo_anio & no_ubicada].groupby("Alimentador").size(),
    }).fillna(0)

    # Un alimentador puede llegar a varios distritos. Para las cifras de cada distrito se le
    # atribuye la parte que corresponde a sus subestaciones en ese distrito, así la suma de
    # los distritos no cuenta dos veces el mismo evento.
    sed_por_alim = guia.groupby("ALIM")["SED"].nunique()

    # Podas del último año. El circuito trae casi siempre el código de una subestación, que
    # fija el distrito; si no lo trae, se reparte por la cuota del alimentador.
    poda_anio = poda[(poda["periodo"] > corte - 12) & (poda["periodo"] <= corte)].copy()
    poda_anio["sed"] = poda_anio["CIRCUITO"].map(_sed_de_circuito)
    distrito_de_sed = guia.drop_duplicates("SED").set_index("SED")["DISTRITO"]
    poda_anio["distrito"] = poda_anio["sed"].map(distrito_de_sed)

    postes = tablas.get("postes")
    if postes is not None:
        postes = asignar_postes(postes, guia)
    salida_postes = {}
    proporcion_piloto = None
    salida = {}

    # El piloto va primero: su capacidad fija la proporción de los demás.
    orden = [config.PILOTO] + [d for d in config.DISTRITOS if d != config.PILOTO]
    if solo:
        orden = [d for d in orden if d in solo]
    motivos_fn = motivos_fn or (lambda datos: motivos(modelo, datos))
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
        alim["motivos"] = motivos_fn(alim)

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
        cuota = todos["alimentador"].map(gd.groupby("ALIM")["SED"].nunique() / sed_por_alim).fillna(0)
        en_cuota = lambda col: float((todos[col] * cuota).sum())   # noqa: E731
        sin_sed = poda_anio[poda_anio["distrito"].isna()]
        cuota_alim = gd.groupby("ALIM")["SED"].nunique() / sed_por_alim
        podas_12m = int((poda_anio["distrito"] == distrito).sum() +
                        round(sin_sed["ALIMENTADOR"].map(cuota_alim).fillna(0).sum()))
        resumen = {
            "sed_total": int(gd["SED"].nunique()), "sed_aereas": int(len(sed)),
            "alimentadores": int(len(alim)), "alimentadores_total": int(gd["ALIM"].nunique()),
            "clientes_expuestos": int(alim["clientes"].sum()),
            "riesgo_medio": _r(alim["probabilidad"].mean(), 4),
            "saidi_ltm": _r(en_cuota("saidi_ltm"), 2),
            "interrupciones_12m": int(round(en_cuota("eventos_12m"))),
            "interrupciones_hist": int(round(en_cuota("eventos_hist"))),
            "cortes_vegetacion": int(round(en_cuota("veg_hist"))),
            "cortes_vegetacion_12m": int(round(en_cuota("veg_12m"))),
            "cortes_veg_por_100_sed": int(round(100 * en_cuota("veg_hist") / max(1, len(sed)))),
            "podas_12m": podas_12m,
            "postes_mt": int((postes["DISTRITO"] == distrito).sum()) if postes is not None else None,
            "meses_sin_poda_mediana": _r(alim["meses_sin_poda"].median(), 0),
            "plan_clientes_share": _r(alim.head(k_alim)["clientes"].sum() /
                                      max(1, alim["clientes"].sum()), 4),
        }
        meta = {
            "distrito": nombre, "codigo": codigo, "corte": str(corte),
            "ventana": ventana(corte), "horizonte_meses": config.HORIZONTE_MESES,
            "periodo_datos": periodo_datos,
            # Último día con interrupciones registradas: es la fecha que lee el usuario.
            "fecha_datos": str(tablas["fallas"]["Inicio"].max().date()),
            "pesos": config.PESOS, "nombres_componentes": dict(config.COMPONENTES),
            "capacidad_mes": capacidad, "capacidad_registro_poda": capacidad_registro,
            "capacidad_regla": regla, "k_alimentadores": k_alim,
            "modelo": nombre_modelo,
            "variables_modelo": [config.NOMBRES_VARIABLES[v] for v in config.VARIABLES],
            "generado": pd.Timestamp.today().strftime("%Y-%m-%d"),
            "n_alimentadores": int(len(alim)), "n_subestaciones": int(len(sed)),
            "n_no_expuestas": int((~gd["aerea"]).sum()), "resumen": resumen,
        }
        alim = alim.merge(veg_detalle, left_on="alimentador", right_index=True, how="left").fillna(
            {"veg_arbol_12m": 0, "no_ubicada_12m": 0})
        n_postes = (postes.groupby("sed").size() if postes is not None else pd.Series(dtype=int))
        sed["postes_mt"] = sed["SED"].map(n_postes).fillna(0)
        alim["postes_mt"] = alim["alimentador"].map(sed.groupby("ALIM")["postes_mt"].sum()).fillna(0)
        if postes is not None:
            pd_ = postes[postes["DISTRITO"] == distrito]
            salida_postes[codigo] = [[f.poste, _r(f.lon, 5), _r(f.lat, 5), f.sed]
                                     for f in pd_.itertuples()]
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
                "eventos_12m": int(f.veg_12m), "veg_arbol_12m": int(f.veg_arbol_12m),
                "no_ubicada_12m": int(f.no_ubicada_12m), "interrupciones_12m": int(f.eventos_12m),
                "interrupciones_hist": int(f.eventos_hist), "postes_mt": int(f.postes_mt),
                "lon": _r(f.lon, 5), "lat": _r(f.lat, 5), "motivos": f.motivos,
            } for f in alim.itertuples()],
            "subestaciones": [{
                "id": f.SED, "alimentador": f.ALIM, "puesto": int(f.puesto),
                "indice": _r(f.indice, 1), "probabilidad": _r(f.probabilidad, 4),
                "componentes": {n: _r(getattr(f, c), 1) for c, n in comp},
                "clientes": int(f.clientes), "kva": _r(f.kva, 0),
                "meses_sin_poda": _r(f.meses_sin_poda, 0),
                "sin_registro_poda": bool(f.sin_registro_poda), "saidi_ltm": _r(f.saidi_ltm, 2),
                "eventos_12m": int(f.veg_12m), "interrupciones_12m": int(f.eventos_12m),
                "interrupciones_hist": int(f.eventos_hist), "postes_mt": int(f.postes_mt),
                "direccion": str(f.DIRECCION)[:60], "lon": _r(f.lon, 5), "lat": _r(f.lat, 5),
            } for f in sed.itertuples()],
            "no_expuestas": [{"lon": _r(f.lon, 5), "lat": _r(f.lat, 5)}
                             for f in gd[~gd["aerea"]].dropna(subset=["lon", "lat"]).itertuples()],
        }
    return salida, salida_postes


def _escribir(nombre, variable, contenido):
    texto = json.dumps(contenido, ensure_ascii=False, separators=(",", ":"))
    (config.DATA_WEB / f"{nombre}.json").write_text(texto, encoding="utf-8")
    (config.DATA_WEB / f"{nombre}.js").write_text(f"window.{variable} = {texto};\n",
                                                  encoding="utf-8")
    return round(len(texto.encode()) / 1024)


def publicar_alterno(distritos_alterno):
    """Escribe el piloto calculado con el modelo alternativo, para el selector de la página."""
    codigo = config.DISTRITOS[config.PILOTO][0]
    return {"criticidad_los_olivos_alterno": _escribir("criticidad_los_olivos_alterno",
                                                       "DATOS_PLUZ_ALTERNO", distritos_alterno[codigo])}


def publicar_postes(postes):
    """Postes de media tensión por distrito: código, longitud, latitud y subestación."""
    if not postes:
        return {}
    return {"postes_mt": _escribir("postes_mt", "POSTES_MT",
                                   {"campos": ["poste", "lon", "lat", "sed"], "distritos": postes})}


def publicar(distritos):
    """Escribe en data/ los tres archivos que carga la página. Devuelve sus tamaños en kB."""
    codigo_piloto = config.DISTRITOS[config.PILOTO][0]
    orden = [config.DISTRITOS[d][0] for d in config.DISTRITOS]

    # La comparación no abre la ficha completa de cada subestación: basta con lo que se
    # muestra al pasar el puntero, y así el archivo baja a la mitad.
    campos_sed = ("id", "alimentador", "puesto", "indice", "probabilidad", "clientes",
                  "meses_sin_poda", "sin_registro_poda", "saidi_ltm", "eventos_12m",
                  "interrupciones_12m", "direccion", "lon", "lat")
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
    pagina = config.DATA_WEB.parent / "index.html"
    if pagina.exists():
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
