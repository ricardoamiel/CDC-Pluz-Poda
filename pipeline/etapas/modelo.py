# -*- coding: utf-8 -*-
"""Etapa 3. Validación, entrenamiento e inferencia del modelo de riesgo a 3 meses.

En cada corrida:
1. Se mide el modelo fuera de muestra: entrena con los cortes antiguos, deja un embargo de
   tres meses y prueba con los últimos cortes que ya tienen su ventana completa. Se compara
   contra la regla por historial, que es lo que Pluz podría hacer hoy sin modelo.
2. Se reentrena con todos los cortes etiquetados, que es el modelo que predice.
3. Se predice el último corte, cuya ventana de tres meses todavía no ocurrió.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import config

KS = [20, 40, 80]


def _nuevo_modelo():
    return Pipeline([("esc", StandardScaler()),
                     ("lr", LogisticRegression(C=config.C_REGULARIZACION, max_iter=2000))])


def _cobertura(datos, puntaje, k):
    """Proporción de los eventos capturada por la lista de los k primeros de cada mes."""
    d = datos[["periodo", "objetivo"]].copy()
    d["p"] = np.asarray(puntaje)
    elegidos = d.groupby("periodo", group_keys=False).apply(lambda gr: gr.nlargest(k, "p"))
    return float(elegidos["objetivo"].sum() / max(1, d["objetivo"].sum()))


def validar(panel, inicio, alim_distrito):
    """Desempeño fuera de muestra. Devuelve el reporte técnico de la corrida."""
    etiquetados = panel[(panel["periodo"] >= inicio) & panel["objetivo"].notna()].copy()
    etiquetados["objetivo"] = etiquetados["objetivo"].astype(int)
    cortes = sorted(etiquetados["periodo"].unique())
    prueba_ini = cortes[-config.MESES_PRUEBA]
    entrena_fin = prueba_ini - (config.MESES_EMBARGO + 1)
    entrena = etiquetados[etiquetados["periodo"] <= entrena_fin]
    prueba = etiquetados[etiquetados["periodo"] >= prueba_ini].copy()

    modelo = _nuevo_modelo().fit(entrena[config.VARIABLES], entrena["objetivo"])
    prueba["p"] = modelo.predict_proba(prueba[config.VARIABLES])[:, 1]
    prueba["regla"] = prueba["veg_12m"] + 0.01 * prueba["veg_hist"]

    reporte = {
        "cortes_etiquetados": [str(cortes[0]), str(cortes[-1])],
        "entrenamiento": [str(cortes[0]), str(entrena_fin)],
        "prueba": [str(prueba_ini), str(cortes[-1])],
        "filas_entrenamiento": int(len(entrena)), "filas_prueba": int(len(prueba)),
        "prevalencia_prueba": float(prueba["objetivo"].mean()),
        "modelo": {f"cobertura_{k}": _cobertura(prueba, prueba["p"], k) for k in KS},
        "regla": {f"cobertura_{k}": _cobertura(prueba, prueba["regla"], k) for k in KS},
    }
    for nombre, col in (("modelo", "p"), ("regla", "regla")):
        reporte[nombre]["ap"] = float(average_precision_score(prueba["objetivo"], prueba[col]))
        reporte[nombre]["auc"] = float(roc_auc_score(prueba["objetivo"], prueba[col]))
    reporte["modelo"]["brier"] = float(brier_score_loss(prueba["objetivo"], prueba["p"]))

    # Remuestreo por alimentador de la diferencia con la regla, con la lista de 40.
    rng = np.random.default_rng(config.SEMILLA)
    unidades = prueba["alimentador"].unique()
    indice_de = {a: prueba.index[prueba["alimentador"] == a] for a in unidades}
    difs = []
    for _ in range(300):
        filas = np.concatenate([indice_de[a] for a in rng.choice(unidades, len(unidades))])
        d = prueba.loc[filas]
        difs.append(_cobertura(d, d["p"], 40) - _cobertura(d, d["regla"], 40))
    reporte["diferencia_con_regla_lista_40"] = {
        "media": float(np.mean(difs)), "li": float(np.percentile(difs, 2.5)),
        "ls": float(np.percentile(difs, 97.5))}

    por_distrito = []
    for distrito, alims in alim_distrito.items():
        sub = prueba[prueba["alimentador"].isin(alims)]
        if not len(sub) or sub["objetivo"].sum() == 0:
            continue
        k = max(5, round(len(alims) / 3))
        por_distrito.append({
            "distrito": config.DISTRITOS[distrito][1], "alimentadores": len(alims), "lista": k,
            "eventos_prueba": int(sub["objetivo"].sum()),
            "cobertura_modelo": _cobertura(sub, sub["p"], k),
            "cobertura_regla": _cobertura(sub, sub["regla"], k)})
    reporte["por_distrito"] = por_distrito
    return reporte, etiquetados


def entrenar_y_predecir(panel, etiquetados, corte):
    """Reentrena con todos los cortes etiquetados y predice el corte operativo."""
    modelo = _nuevo_modelo().fit(etiquetados[config.VARIABLES], etiquetados["objetivo"])
    operativo = panel[panel["periodo"] == corte].copy()
    operativo["probabilidad"] = modelo.predict_proba(operativo[config.VARIABLES])[:, 1]
    return modelo, operativo


def motivos(modelo, datos, n=3):
    """Las n razones que más empujan hacia arriba el riesgo de cada fila."""
    aportes = (modelo.named_steps["esc"].transform(datos[config.VARIABLES]) *
               modelo.named_steps["lr"].coef_[0])
    salida = []
    for fila in aportes:
        razones = []
        for j in np.argsort(-fila):
            if fila[j] <= 0 or len(razones) == n:
                break
            texto = config.MOTIVOS[config.VARIABLES[j]]
            if texto not in razones:
                razones.append(texto)
        salida.append(razones)
    return salida
