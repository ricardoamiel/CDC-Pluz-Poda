# -*- coding: utf-8 -*-
"""Etapa 3. Modelo de riesgo a 3 meses: un modelo vigente estable, monitoreado cada semana.

El modelo no se reentrena por calendario. Se entrena una vez, se guarda como modelo vigente
con su ficha, y cada corrida semanal hace tres cosas:

1. Predice el último corte con el modelo vigente.
2. Lo monitorea en los meses que ya tienen su ventana de tres meses completa y que el modelo
   no vio al entrenarse: compara su ordenamiento con la regla por historial y su
   probabilidad promedio con la frecuencia observada.
3. Si la probabilidad se descalibra, la recalibra: ajusta solo la escala, de modo que el
   orden del ranking y el índice no cambian. Si el ordenamiento cae frente a la regla,
   recomienda reentrenar; el reentrenamiento se hace con una orden explícita, nunca solo.

Al entrenar, el modelo se mide fuera de muestra con una partición temporal y embargo, y
esa medición queda en la ficha como línea base del monitoreo.
"""
import json
import time

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


VIGENTE = config.SALIDAS / "modelo_vigente.joblib"
FICHA = config.SALIDAS / "modelo_vigente.json"


def entrenar_vigente(etiquetados, validacion):
    """Entrena con todos los cortes etiquetados y guarda el modelo vigente con su ficha."""
    import joblib
    modelo = _nuevo_modelo().fit(etiquetados[config.VARIABLES], etiquetados["objetivo"])
    ficha = {
        "entrenado": time.strftime("%Y%m%d %H:%M"),
        "variables": list(config.VARIABLES), "C": config.C_REGULARIZACION,
        "entrenado_hasta": str(etiquetados["periodo"].max()),
        "filas": int(len(etiquetados)), "positivos": int(etiquetados["objetivo"].sum()),
        "validacion": validacion, "calibracion": None, "historial_calibraciones": [],
    }
    config.SALIDAS.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, VIGENTE)
    FICHA.write_text(json.dumps(ficha, ensure_ascii=False, indent=1), encoding="utf-8")
    return modelo, ficha


def cargar_vigente():
    """Devuelve el modelo vigente y su ficha, o nada si no existe o usa otras variables."""
    import joblib
    if not (VIGENTE.exists() and FICHA.exists()):
        return None, None
    ficha = json.loads(FICHA.read_text(encoding="utf-8"))
    if ficha.get("variables") != list(config.VARIABLES):
        print("  El modelo vigente usa otras variables que las de config.py: se entrena uno nuevo.")
        return None, None
    return joblib.load(VIGENTE), ficha


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def predecir(modelo, ficha, datos):
    """Probabilidad del modelo vigente, con la recalibración aplicada si existe."""
    p = modelo.predict_proba(datos[config.VARIABLES])[:, 1]
    cal = ficha.get("calibracion")
    if cal:
        p = 1 / (1 + np.exp(-(cal["pendiente"] * _logit(p) + cal["intercepto"])))
    return p


def monitorear(modelo, ficha, panel):
    """Desempeño del modelo vigente en los meses etiquetados que no vio al entrenarse."""
    desde = pd.Period(ficha["entrenado_hasta"], freq="M")
    nuevos = panel[(panel["periodo"] > desde) & panel["objetivo"].notna()].copy()
    meses = int(nuevos["periodo"].nunique())
    salida = {"meses_nuevos": meses, "desde": str(desde + 1) if meses else None,
              "hasta": str(nuevos["periodo"].max()) if meses else None,
              "recalibrar": False, "reentrenamiento_recomendado": False}
    if meses == 0 or nuevos["objetivo"].sum() == 0:
        salida["lectura"] = "Todavía no hay meses con la ventana completa después del entrenamiento."
        return salida, nuevos
    nuevos["objetivo"] = nuevos["objetivo"].astype(int)
    p = predecir(modelo, ficha, nuevos)
    regla = (nuevos["veg_12m"] + 0.01 * nuevos["veg_hist"]).values
    y = nuevos["objetivo"].values
    salida.update({
        "eventos": int(y.sum()),
        "pr_auc_modelo": float(average_precision_score(y, p)),
        "pr_auc_regla": float(average_precision_score(y, regla)),
        "cobertura_40_modelo": _cobertura(nuevos, p, 40),
        "cobertura_40_regla": _cobertura(nuevos, regla, 40),
        "probabilidad_media": float(p.mean()), "frecuencia_observada": float(y.mean()),
    })
    razon = salida["frecuencia_observada"] / max(1e-6, salida["probabilidad_media"])
    salida["razon_observado_esperado"] = float(razon)
    suficiente = meses >= config.MESES_MINIMOS_MONITOREO
    bajo, alto = config.BANDA_CALIBRACION
    salida["recalibrar"] = bool(suficiente and not bajo <= razon <= alto)
    salida["reentrenamiento_recomendado"] = bool(suficiente and (
        salida["pr_auc_modelo"] < salida["pr_auc_regla"] - config.MARGEN_PR_AUC or
        salida["cobertura_40_regla"] - salida["cobertura_40_modelo"] > config.MARGEN_COBERTURA))
    return salida, nuevos


def recalibrar(modelo, ficha, nuevos):
    """Ajusta la escala de la probabilidad con los meses nuevos; el orden no cambia.

    Es una recalibración logística sobre el logit de la probabilidad original: una pendiente
    y un intercepto. Como la pendiente queda positiva, el ranking y el índice se conservan.
    """
    if nuevos["objetivo"].sum() < config.EVENTOS_MINIMOS_CALIBRACION:
        return ficha, False
    crudo = modelo.predict_proba(nuevos[config.VARIABLES])[:, 1]
    ajuste = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(crudo).reshape(-1, 1),
                                                          nuevos["objetivo"].astype(int))
    pendiente, intercepto = float(ajuste.coef_[0][0]), float(ajuste.intercept_[0])
    if pendiente <= 0:
        return ficha, False
    ficha["calibracion"] = {"pendiente": pendiente, "intercepto": intercepto,
                            "fecha": time.strftime("%Y%m%d %H:%M"),
                            "meses": [str(nuevos["periodo"].min()), str(nuevos["periodo"].max())]}
    ficha["historial_calibraciones"].append(ficha["calibracion"])
    FICHA.write_text(json.dumps(ficha, ensure_ascii=False, indent=1), encoding="utf-8")
    return ficha, True


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


def registrar_mlflow(rep):
    """Registra cada corrida semanal en MLflow, para seguir el modelo vigente en el tiempo.

    Usa la misma base de MLflow que el benchmark, en un experimento aparte. Cada corrida
    queda con el corte, el estado del modelo y las métricas de monitoreo, de modo que en la
    interfaz se pueden graficar semana a semana la PR AUC frente a la regla y la razón entre
    frecuencia observada y probabilidad media.
    """
    try:
        import mlflow
    except ImportError:
        return False
    mlflow.set_tracking_uri(f"sqlite:///{config.SALIDAS / 'mlflow.db'}")
    nombre = "pluz_modelo_vigente"
    if mlflow.get_experiment_by_name(nombre) is None:
        mlflow.create_experiment(nombre, artifact_location=(config.SALIDAS / "mlruns").as_uri())
    mlflow.set_experiment(nombre)
    vig, mon, val = rep["modelo_vigente"], rep.get("monitoreo") or {}, rep["validacion"]
    with mlflow.start_run(run_name=f"corte {rep['corte']}, corrida {rep['fecha']}"):
        mlflow.set_tags({"corte": rep["corte"], "entrenado": vig["entrenado"],
                         "entrenado_hasta": vig["entrenado_hasta"],
                         "calibrado": str(bool(vig["calibracion"])),
                         "publicado": str(rep["publicado"]),
                         "reentrenamiento_recomendado": str(mon.get("reentrenamiento_recomendado", False))})
        mlflow.log_params({"variables": ", ".join(config.VARIABLES), "C": config.C_REGULARIZACION})
        metricas = {"validacion_cobertura_40_modelo": val["modelo"]["cobertura_40"],
                    "validacion_cobertura_40_regla": val["regla"]["cobertura_40"],
                    "validacion_pr_auc_modelo": val["modelo"]["ap"],
                    "meses_nuevos_monitoreados": float(mon.get("meses_nuevos", 0))}
        for clave in ("pr_auc_modelo", "pr_auc_regla", "cobertura_40_modelo", "cobertura_40_regla",
                      "razon_observado_esperado", "probabilidad_media", "frecuencia_observada"):
            if clave in mon:
                metricas["monitoreo_" + clave] = mon[clave]
        mlflow.log_metrics(metricas)
        reporte = config.SALIDAS / "reporte.md"
        if reporte.exists():
            mlflow.log_artifact(str(reporte))
    return True
