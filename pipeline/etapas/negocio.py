# -*- coding: utf-8 -*-
"""Respaldo del plan: ¿un plan de K alimentadores ordenado por el índice prioriza donde hay que podar?

Para la página. En los meses de prueba se reconstruye el índice de criticidad del piloto tal
como lo calcula la herramienta, con información disponible en cada mes:

  * probabilidad: un modelo con la misma receta del vigente, entrenado solo con los meses
    anteriores a la prueba (con el embargo de config.MESES_EMBARGO), como en modelo.validar;
  * reloj de poda: los meses sin poda del panel en ese mes;
  * criticidad por SAIDI: el SAIDI de los 12 meses anteriores, sumado desde las interrupciones
    (el ranking de Pluz es una sola foto y no sirve para meses pasados);
  * exposición: clientes y potencia de la guía, que son infraestructura.

Para cada tamaño de plan K se cuenta qué parte de los minutos de SAIDI por vegetación y de los
cortes por vegetación de los tres meses siguientes cayó en los K primeros. El azar captura en
promedio K de N. Los intervalos del 95 % salen de remuestrear alimentadores.
"""
import numpy as np
import pandas as pd

import config
from etapas import indice, modelo

REPETICIONES = 1000


def curva_plan(tablas, panel, inicio):
    h = config.HORIZONTE_MESES
    guia, fallas = tablas["guia"], tablas["fallas"]
    piloto = set(indice.alimentadores_por_distrito(guia)[config.PILOTO])

    # Misma partición que modelo.validar.
    etiq = panel[(panel["periodo"] >= inicio) & panel["objetivo"].notna()].copy()
    cortes = sorted(etiq["periodo"].unique())
    prueba_ini = cortes[-config.MESES_PRUEBA]
    entrena_fin = prueba_ini - (config.MESES_EMBARGO + 1)
    entrena = etiq[etiq["periodo"] <= entrena_fin]
    m = modelo._nuevo_modelo().fit(entrena[config.VARIABLES], entrena["objetivo"].astype(int))

    # Lo que pasó después: cortes y SAIDI por vegetación de los tres meses siguientes.
    p = panel.sort_values(["alimentador", "periodo"]).copy()
    g = p.groupby("alimentador")
    p["fut_ev"] = sum(g["eventos_veg"].shift(-k) for k in range(1, h + 1))
    p["fut_saidi"] = sum(g["saidi_veg"].shift(-k) for k in range(1, h + 1))

    # SAIDI de todas las causas de los 12 meses anteriores, por alimentador y mes.
    saidi_mes = pd.to_numeric(fallas["SAIDI"], errors="coerce").groupby(
        [fallas["Alimentador"], fallas["periodo"]]).sum()
    saidi_mes.index.names = ["alimentador", "periodo"]
    p = p.merge(saidi_mes.rename("saidi_mes"), how="left", left_on=["alimentador", "periodo"],
                right_index=True)
    p["saidi_mes"] = p["saidi_mes"].fillna(0)
    p["saidi_ltm"] = p.groupby("alimentador")["saidi_mes"].transform(
        lambda s: s.rolling(12, min_periods=1).sum())

    gd = guia[(guia["DISTRITO"] == config.PILOTO) & guia["aerea"]].dropna(subset=["lon", "lat"])
    expo = gd.groupby("ALIM").agg(clientes=("clientes", "sum"), kva=("kva", "sum")).reset_index()

    meses = [c for c in cortes if c >= prueba_ini]
    filas = []
    for mes in meses:
        op = p[(p["periodo"] == mes) & p["alimentador"].isin(piloto)].copy()
        op["probabilidad"] = m.predict_proba(op[config.VARIABLES])[:, 1]
        op["saidi_ltm"] = op["saidi_ltm"].fillna(op["saidi_ltm"].median())
        d = indice.calcular_indice(op.merge(expo, left_on="alimentador", right_on="ALIM"))
        filas.append(d[["alimentador", "periodo", "puesto", "fut_ev", "fut_saidi"]])
    d = pd.concat(filas, ignore_index=True).fillna({"fut_ev": 0, "fut_saidi": 0})

    n = int(d.groupby("periodo").size().min())
    alims, idx = np.unique(d["alimentador"].values, return_inverse=True)
    puesto = d["puesto"].values

    def por_alim(v):
        return np.bincount(idx, weights=v, minlength=len(alims))

    tot_ev, tot_saidi = por_alim(d["fut_ev"].values), por_alim(d["fut_saidi"].values)
    rng = np.random.default_rng(config.SEMILLA)
    muestras = rng.integers(0, len(alims), size=(REPETICIONES, len(alims)))
    den_saidi = tot_saidi[muestras].sum(axis=1)
    validas = den_saidi > 0

    salida = {"k": [], "captura_saidi": [], "captura_eventos": [], "aciertos": [],
              "ic_saidi": [], "azar": []}
    for k in range(1, n + 1):
        en_plan = (puesto <= k).astype(float)
        sel_ev = por_alim(d["fut_ev"].values * en_plan)
        sel_saidi = por_alim(d["fut_saidi"].values * en_plan)
        cap_boot = sel_saidi[muestras].sum(axis=1)[validas] / den_saidi[validas]
        salida["k"].append(k)
        salida["captura_saidi"].append(round(float(sel_saidi.sum() / tot_saidi.sum()), 4))
        salida["captura_eventos"].append(round(float(sel_ev.sum() / tot_ev.sum()), 4))
        salida["aciertos"].append(round(float(((d["fut_ev"] > 0) & (puesto <= k)).sum() /
                                              (k * len(meses))), 4))
        salida["ic_saidi"].append([round(float(np.percentile(cap_boot, 2.5)), 4),
                                   round(float(np.percentile(cap_boot, 97.5)), 4)])
        salida["azar"].append(round(k / n, 4))
    salida.update({
        "meses": [str(meses[0]), str(meses[-1])], "alimentadores": n,
        "eventos_totales": int(d["fut_ev"].sum()), "saidi_total": round(float(d["fut_saidi"].sum()), 3),
        "nota": "Índice reconstruido en cada mes de prueba con un modelo entrenado antes de ese periodo",
    })
    return salida
