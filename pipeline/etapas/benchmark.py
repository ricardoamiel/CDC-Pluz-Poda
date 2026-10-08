# -*- coding: utf-8 -*-
"""Benchmark de modelos para el riesgo de interferencia de vegetación a 3 meses.

Compara, con la misma partición temporal que usa el pipeline, la regla por historial, la
regresión logística vigente y sus alternativas: regresión logística ponderada, refuerzo de
gradiente de histograma (el que ya se había probado en la fase 4), Random Forest, XGBoost,
LightGBM y SVM. Todos usan solo las variables de config.VARIABLES, es decir, ninguna de
las que el índice de criticidad ya cuenta por su lado.

Partición:
    entrenamiento interno  cortes antiguos, para elegir hiperparámetros y umbral
    validación interna     últimos 2 cortes del entrenamiento, tras 3 meses de embargo
    entrenamiento          todos los cortes previos al embargo de la prueba
    prueba                 últimos 5 cortes con ventana completa, nunca usados para elegir

Escribe en salidas/benchmark: el reporte interactivo, los resultados en JSON y, si MLflow
está instalado, una corrida por modelo en salidas/mlflow.db.
"""
import json
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, fbeta_score, log_loss, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score, roc_curve)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

import config
from etapas.modelo import _cobertura

warnings.filterwarnings("ignore")

KS = [20, 40, 80]
K_OPERATIVO = 40          # lista mensual con la que se clasifican los ejemplos
EPS = 1e-6

NOMBRE_NEGOCIO = {
    "log_veg_hist": "Historial de vegetación (log)",
    "log_veg_12m": "Vegetación, 12 meses (log)",
    "log_eventos_12m": "Interrupciones, 12 meses (log)",
    "mes_sin": "Ciclo anual, seno",
    "mes_cos": "Ciclo anual, coseno",
    "meses_sin_poda": "Meses sin poda (índice)",
    "saidi_ltm": "SAIDI último año (índice)",
    "clientes": "Clientes (índice)",
    "kva": "Potencia instalada (índice)",
}


# --------------------------------------------------------------------------- particiones

def particiones(panel, inicio):
    etiq = panel[(panel["periodo"] >= inicio) & panel["objetivo"].notna()].copy()
    etiq["objetivo"] = etiq["objetivo"].astype(int)
    cortes = sorted(etiq["periodo"].unique())
    prueba_ini = cortes[-config.MESES_PRUEBA]
    entrena_fin = prueba_ini - (config.MESES_EMBARGO + 1)
    entrena = etiq[etiq["periodo"] <= entrena_fin]
    cortes_ent = sorted(entrena["periodo"].unique())
    val_ini = cortes_ent[-2]
    interno_fin = val_ini - (config.MESES_EMBARGO + 1)
    return {
        "interno": entrena[entrena["periodo"] <= interno_fin],
        "validacion": entrena[entrena["periodo"] >= val_ini],
        "entrena": entrena,
        "prueba": etiq[etiq["periodo"] >= prueba_ini].copy(),
    }


# --------------------------------------------------------------------------- modelos

def _xgb(**p):
    from xgboost import XGBClassifier
    return XGBClassifier(n_estimators=p.get("n", 1000), learning_rate=0.05,
                         max_depth=p["max_depth"], min_child_weight=p["min_child_weight"],
                         subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                         eval_metric="logloss", random_state=config.SEMILLA, n_jobs=4)


def _lgbm(**p):
    from lightgbm import LGBMClassifier
    return LGBMClassifier(n_estimators=p.get("n", 1000), learning_rate=0.05,
                          num_leaves=p["num_leaves"], min_child_samples=p["min_child_samples"],
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                          random_state=config.SEMILLA, verbose=-1, n_jobs=4)


CANDIDATOS = {
    "Regresión logística": {
        "rejilla": [{"C": c} for c in (0.01, 0.05, 0.2, 1.0)],
        "crear": lambda p: Pipeline([("esc", StandardScaler()),
                                     ("m", LogisticRegression(C=p["C"], max_iter=3000))]),
        "tipo": "lineal"},
    "Regresión logística ponderada": {
        "rejilla": [{"C": c} for c in (0.01, 0.05, 0.2, 1.0)],
        "crear": lambda p: Pipeline([("esc", StandardScaler()),
                                     ("m", LogisticRegression(C=p["C"], max_iter=3000,
                                                              class_weight="balanced"))]),
        "tipo": "lineal"},
    "Refuerzo de gradiente": {
        "rejilla": [{"max_depth": d, "min_samples_leaf": h} for d in (2, 3) for h in (40, 80)],
        "crear": lambda p: HistGradientBoostingClassifier(
            max_iter=p.get("n", 600), learning_rate=0.05, max_depth=p["max_depth"],
            min_samples_leaf=p["min_samples_leaf"], l2_regularization=1.0,
            early_stopping=False, random_state=config.SEMILLA),
        "tipo": "boosting_hgb"},
    "Random Forest": {
        "rejilla": [{"max_depth": d, "min_samples_leaf": h} for d in (4, 6, None) for h in (20, 50)],
        "crear": lambda p: RandomForestClassifier(
            n_estimators=400, max_depth=p["max_depth"], min_samples_leaf=p["min_samples_leaf"],
            max_features="sqrt", n_jobs=4, random_state=config.SEMILLA),
        "tipo": "bosque"},
    "XGBoost": {
        "rejilla": [{"max_depth": d, "min_child_weight": w} for d in (2, 3, 4) for w in (5, 20)],
        "crear": lambda p: _xgb(**p),
        "tipo": "boosting_xgb"},
    "LightGBM": {
        "rejilla": [{"num_leaves": n, "min_child_samples": c} for n in (4, 8, 16) for c in (40, 100)],
        "crear": lambda p: _lgbm(**p),
        "tipo": "boosting_lgbm"},
    "SVM": {
        "rejilla": [{"C": c} for c in (0.3, 1.0, 3.0)],
        "crear": lambda p: Pipeline([("esc", StandardScaler()),
                                     ("m", SVC(C=p["C"], kernel="rbf", gamma="scale",
                                               probability=True, random_state=config.SEMILLA))]),
        "tipo": "lineal"},
}


def _proba(m, X):
    return np.clip(m.predict_proba(X)[:, 1], EPS, 1 - EPS)


def _curva_iteraciones(nombre, modelo, conjuntos):
    """Pérdida logarítmica por iteración o por árbol en cada conjunto. Vacío si no aplica."""
    tipo = CANDIDATOS[nombre]["tipo"]
    curvas = {}
    for etiqueta, d in conjuntos.items():
        X, y = d[config.VARIABLES], d["objetivo"]
        if tipo == "boosting_hgb":
            serie = [log_loss(y, np.clip(p[:, 1], EPS, 1 - EPS))
                     for p in modelo.staged_predict_proba(X)]
        elif tipo == "boosting_xgb":
            n = modelo.get_booster().num_boosted_rounds()
            paso = max(1, n // 120)
            serie = [log_loss(y, np.clip(modelo.predict_proba(X, iteration_range=(0, i))[:, 1],
                                         EPS, 1 - EPS)) for i in range(1, n + 1, paso)]
        elif tipo == "boosting_lgbm":
            n = modelo.booster_.num_trees()
            paso = max(1, n // 120)
            serie = [log_loss(y, np.clip(modelo.predict_proba(X, num_iteration=i)[:, 1],
                                         EPS, 1 - EPS)) for i in range(1, n + 1, paso)]
        elif tipo == "bosque":
            arboles = np.array([a.predict_proba(X.values)[:, 1] for a in modelo.estimators_])
            acumulado = np.cumsum(arboles, axis=0) / np.arange(1, len(arboles) + 1)[:, None]
            serie = [log_loss(y, np.clip(acumulado[i], EPS, 1 - EPS))
                     for i in range(0, len(arboles), 5)]
        else:
            return {}
        curvas[etiqueta] = [float(v) for v in serie]
    return curvas


def _mejor_iteracion(nombre, p, interno, val):
    """Para los modelos por iteraciones, cuántas iteraciones minimizan la pérdida interna."""
    tipo = CANDIDATOS[nombre]["tipo"]
    if not tipo.startswith("boosting"):
        return None
    m = CANDIDATOS[nombre]["crear"](p).fit(interno[config.VARIABLES], interno["objetivo"])
    curva = _curva_iteraciones(nombre, m, {"v": val})["v"]
    mejor = int(np.argmin(curva))
    if tipo == "boosting_hgb":
        return mejor + 1
    n = (m.get_booster().num_boosted_rounds() if tipo == "boosting_xgb" else m.booster_.num_trees())
    return min(n, mejor * max(1, n // 120) + 1)


def elegir(nombre, part):
    """Elige hiperparámetros con la mejor precisión media en la validación interna."""
    interno, val = part["interno"], part["validacion"]
    mejor = None
    for p in CANDIDATOS[nombre]["rejilla"]:
        p = dict(p)
        n = _mejor_iteracion(nombre, p, interno, val)
        if n:
            p["n"] = max(20, n)
        m = CANDIDATOS[nombre]["crear"](p).fit(interno[config.VARIABLES], interno["objetivo"])
        s = _proba(m, val[config.VARIABLES])
        ap = average_precision_score(val["objetivo"], s)
        if mejor is None or ap > mejor[0]:
            mejor = (ap, p, s)
    ap, p, s_val = mejor
    # Umbral: el que maximiza F2 en la validación interna, porque un falso negativo cuesta
    # más que un falso positivo (ver la justificación en el reporte).
    prec, rec, umbrales = precision_recall_curve(val["objetivo"], s_val)
    f2 = 5 * prec * rec / np.maximum(4 * prec + rec, EPS)
    umbral = float(umbrales[np.argmax(f2[:-1])]) if len(umbrales) else 0.5
    return p, umbral, float(ap)


# --------------------------------------------------------------------------- métricas

def metricas(y, s, umbral, datos, probabilistico=True):
    pred = (s >= umbral).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    m = {
        "roc_auc": float(roc_auc_score(y, s)),
        "pr_auc": float(average_precision_score(y, s)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "f2": float(fbeta_score(y, pred, beta=2, zero_division=0)),
        "especificidad": float(tn / max(1, tn + fp)),
        "exactitud": float((tp + tn) / len(y)),
        "umbral": float(umbral),
        "matriz": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    if probabilistico:
        m["brier"] = float(brier_score_loss(y, s))
        m["log_loss"] = float(log_loss(y, np.clip(s, EPS, 1 - EPS)))
    for k in KS:
        m[f"cobertura_{k}"] = _cobertura(datos, s, k)
        d = datos[["periodo", "objetivo"]].assign(p=s)
        el = d.groupby("periodo", group_keys=False).apply(lambda g: g.nlargest(k, "p"))
        m[f"precision_{k}"] = float(el["objetivo"].mean())
    return m


def lista_operativa(datos, s, k=K_OPERATIVO):
    """Marca 1 en los k alimentadores de mayor puntaje de cada mes: el plan que se ejecutaría."""
    d = datos[["periodo"]].assign(p=s)
    d["puesto"] = d.groupby("periodo")["p"].rank(ascending=False, method="first")
    return (d["puesto"] <= k).astype(int).values, d["puesto"].values


def bootstrap_contra(prueba, s_ref, s_mod, reps=300):
    """Diferencia de cobertura con lista de 40 y de precisión media, remuestreando alimentadores."""
    rng = np.random.default_rng(config.SEMILLA)
    unidades = prueba["alimentador"].unique()
    idx = {a: np.where(prueba["alimentador"].values == a)[0] for a in unidades}
    d_cob, d_ap = [], []
    for _ in range(reps):
        filas = np.concatenate([idx[a] for a in rng.choice(unidades, len(unidades))])
        sub = prueba.iloc[filas]
        if sub["objetivo"].sum() == 0:
            continue
        d_cob.append(_cobertura(sub, s_mod[filas], 40) - _cobertura(sub, s_ref[filas], 40))
        d_ap.append(average_precision_score(sub["objetivo"], s_mod[filas]) -
                    average_precision_score(sub["objetivo"], s_ref[filas]))
    resumen = lambda v: {"media": float(np.mean(v)), "li": float(np.percentile(v, 2.5)),  # noqa: E731
                         "ls": float(np.percentile(v, 97.5))}
    return {"cobertura_40": resumen(d_cob), "pr_auc": resumen(d_ap)}


def curva_aprendizaje(nombre, p, part):
    """Pérdida en entrenamiento y en prueba según cuántos cortes se usan para entrenar."""
    ent, prueba = part["entrena"], part["prueba"]
    cortes = sorted(ent["periodo"].unique())
    salida = []
    for n in range(3, len(cortes) + 1, 2) if len(cortes) > 3 else [len(cortes)]:
        sub = ent[ent["periodo"] <= cortes[n - 1]]
        m = CANDIDATOS[nombre]["crear"](p).fit(sub[config.VARIABLES], sub["objetivo"])
        salida.append({"cortes": n, "filas": int(len(sub)),
                       "entrenamiento": float(log_loss(sub["objetivo"], _proba(m, sub[config.VARIABLES]))),
                       "prueba": float(log_loss(prueba["objetivo"], _proba(m, prueba[config.VARIABLES])))})
    return salida


# --------------------------------------------------------------------------- redundancia

def redundancia(panel, operativo):
    """Correlación de Spearman entre las variables del modelo y las del índice."""
    # La estacionalidad es constante dentro de un mismo corte y no tiene correlación que medir.
    cols = [c for c in config.VARIABLES + config.VARIABLES_DEL_INDICE
            if c in operativo.columns and operativo[c].nunique() > 1]
    corr = operativo[cols].corr(method="spearman").fillna(0)
    presentes = [v for v in config.VARIABLES_DEL_INDICE if v in config.VARIABLES]
    return {"variables": cols, "matriz": corr.round(3).values.tolist(),
            "del_indice_en_el_modelo": presentes}


BLOQUES = {
    "Vegetación: historial y últimos 12 meses": ["log_veg_hist", "log_veg_12m"],
    "Interrupciones de los últimos 12 meses": ["log_eventos_12m"],
    "Estacionalidad": ["mes_sin", "mes_cos"],
}


def aporte_variables(part):
    """Quita un bloque de variables a la vez de la regresión logística y mide el cambio.

    Se mide por bloques y no variable por variable porque las variables de un mismo bloque
    se sustituyen entre sí: quitar solo el historial de vegetación no cambia nada, porque la
    vegetación de 12 meses lleva casi la misma información. Si quitar un bloque no cambia la
    cobertura de forma distinguible, ese bloque no aporta información propia.
    """
    ent, prueba = part["entrena"], part["prueba"].reset_index(drop=True)
    crear = CANDIDATOS["Regresión logística"]["crear"]
    p = {"C": config.C_REGULARIZACION}
    completo = _proba(crear(p).fit(ent[config.VARIABLES], ent["objetivo"]), prueba[config.VARIABLES])
    salida = []
    for nombre, quitar in BLOQUES.items():
        resto = [x for x in config.VARIABLES if x not in quitar]
        if len(resto) == len(config.VARIABLES):
            continue
        s = _proba(crear(p).fit(ent[resto], ent["objetivo"]), prueba[resto])
        b = bootstrap_contra(prueba, s, completo, reps=200)
        salida.append({"nombre": nombre, "variables": quitar,
                       "cobertura_40_sin": _cobertura(prueba, s, 40),
                       "aporte_cobertura_40": b["cobertura_40"], "aporte_pr_auc": b["pr_auc"]})
    return salida


# --------------------------------------------------------------------------- ejemplos

def ejemplos(panel, prueba, s, nombre_modelo, n=4):
    """Casos concretos de la prueba con el plan de 40 por mes: aciertos y errores."""
    en_lista, puesto = lista_operativa(prueba, s)
    d = prueba[["alimentador", "periodo", "objetivo", "veg_12m", "veg_hist",
                "eventos_12m"]].copy()
    d["probabilidad"], d["en_lista"], d["puesto"] = s, en_lista, puesto
    # Verdad de campo: cuántos eventos tuvo cada alimentador en cada uno de los 3 meses.
    ev = panel.set_index(["alimentador", "periodo"])["eventos_veg"]
    for k in range(1, config.HORIZONTE_MESES + 1):
        d[f"ev_mes_{k}"] = [int(ev.get((a, p + k), 0)) for a, p in zip(d["alimentador"], d["periodo"])]
    d["tipo"] = np.select([(d.en_lista == 1) & (d.objetivo == 1), (d.en_lista == 1) & (d.objetivo == 0),
                           (d.en_lista == 0) & (d.objetivo == 1)], ["VP", "FP", "FN"], "VN")
    elegidos = []
    for tipo, orden in (("VP", False), ("FP", False), ("VN", True)):
        elegidos.append(d[d["tipo"] == tipo].sort_values("probabilidad", ascending=orden).head(n))
    # Falsos negativos de dos clases: los que quedaron justo fuera de la lista y los que no
    # tenían ningún antecedente, que son el punto ciego de cualquier modelo por historial.
    fn = d[d["tipo"] == "FN"].sort_values("probabilidad")
    elegidos += [fn.tail(n // 2).iloc[::-1], fn.head(n - n // 2)]
    salida = pd.concat(elegidos)
    salida["periodo"] = salida["periodo"].astype(str)
    salida["modelo"] = nombre_modelo
    return salida.round(4).to_dict(orient="records")


# --------------------------------------------------------------------------- MLflow

def registrar_mlflow(resultados, reporte):
    try:
        import mlflow
    except ImportError:
        return None
    uri = f"sqlite:///{config.SALIDAS / 'mlflow.db'}"
    mlflow.set_tracking_uri(uri)
    nombre = "pluz_vegetacion_benchmark"
    if mlflow.get_experiment_by_name(nombre) is None:
        mlflow.create_experiment(nombre, artifact_location=(config.SALIDAS / "mlruns").as_uri())
    mlflow.set_experiment(nombre)
    with mlflow.start_run(run_name=f"benchmark {resultados['fecha']}"):
        mlflow.log_params({"corte": resultados["corte"], "variables": ", ".join(config.VARIABLES),
                           "prueba": " a ".join(resultados["particion"]["prueba"])})
        mlflow.log_artifact(str(reporte))
        for nombre_m, r in resultados["modelos"].items():
            with mlflow.start_run(run_name=nombre_m, nested=True):
                mlflow.log_params({k: str(v) for k, v in r["hiperparametros"].items()})
                mlflow.log_metrics({k: v for k, v in r["prueba"].items()
                                    if isinstance(v, float)})
                mlflow.set_tag("elegido", str(nombre_m == resultados["decision"]["modelo"]))
    return uri


# --------------------------------------------------------------------------- orquestación

def ejecutar(panel, inicio, corte, operativo):
    part = particiones(panel, inicio)
    prueba = part["prueba"]
    y = prueba["objetivo"].values
    res = {"fecha": time.strftime("%Y%m%d %H:%M"), "corte": str(corte),
           "variables": config.VARIABLES,
           "particion": {k: [str(v["periodo"].min()), str(v["periodo"].max())]
                         for k, v in part.items()},
           "filas": {k: int(len(v)) for k, v in part.items()},
           "positivos": {k: int(v["objetivo"].sum()) for k, v in part.items()},
           "modelos": {}, "curvas": {}, "aprendizaje": {}}

    # Regla por historial: lo que Pluz podría hacer hoy sin modelo.
    regla = lambda d: (d["veg_12m"] + 0.01 * d["veg_hist"]).values  # noqa: E731
    s_regla_val = regla(part["validacion"])
    prec, rec, umb = precision_recall_curve(part["validacion"]["objetivo"], s_regla_val)
    f2 = 5 * prec * rec / np.maximum(4 * prec + rec, EPS)
    umbral_regla = float(umb[np.argmax(f2[:-1])])
    puntajes = {"Regla por historial": regla(prueba)}
    res["modelos"]["Regla por historial"] = {
        "hiperparametros": {"puntaje": "eventos de 12 meses más 0,01 por el historial"},
        "prueba": metricas(y, puntajes["Regla por historial"], umbral_regla, prueba, False)}

    for nombre in CANDIDATOS:
        t0 = time.time()
        p, umbral, ap_val = elegir(nombre, part)
        modelo = CANDIDATOS[nombre]["crear"](p).fit(part["entrena"][config.VARIABLES],
                                                    part["entrena"]["objetivo"])
        s = _proba(modelo, prueba[config.VARIABLES])
        puntajes[nombre] = s
        res["modelos"][nombre] = {"hiperparametros": p, "pr_auc_validacion": ap_val,
                                  "prueba": metricas(y, s, umbral, prueba),
                                  "segundos": round(time.time() - t0, 1)}
        res["curvas"][nombre] = _curva_iteraciones(nombre, modelo, {
            "Entrenamiento": part["entrena"], "Prueba": prueba})
        res["aprendizaje"][nombre] = curva_aprendizaje(nombre, p, part)
        print(f"    {nombre}: PR AUC {res['modelos'][nombre]['prueba']['pr_auc']:.3f}, "
              f"cobertura 40 {res['modelos'][nombre]['prueba']['cobertura_40']:.3f}")

    ref = puntajes["Regresión logística"]
    for nombre, s in puntajes.items():
        if nombre != "Regresión logística":
            res["modelos"][nombre]["contra_logistica"] = bootstrap_contra(prueba, ref, s)

    # Decisión: se cambia la regresión logística solo si otro modelo la supera con un
    # intervalo que no cruza el cero en la métrica operativa. En empate se queda la más
    # simple, calibrada y explicable.
    mejores = [(n, r["contra_logistica"]["cobertura_40"]) for n, r in res["modelos"].items()
               if "contra_logistica" in r and n != "Regla por historial"]
    ganadores = [n for n, b in mejores if b["li"] > 0]
    elegido = max(ganadores, key=lambda n: res["modelos"][n]["prueba"]["cobertura_40"]) \
        if ganadores else "Regresión logística"
    res["decision"] = {"modelo": elegido, "supera_con_intervalo": ganadores}

    # Curvas ROC, precisión y exhaustividad, y calibración para el reporte.
    res["roc"], res["pr"], res["calibracion"] = {}, {}, {}
    for nombre, s in puntajes.items():
        fpr, tpr, _ = roc_curve(y, s)
        pr, rc, _ = precision_recall_curve(y, s)
        paso = max(1, len(fpr) // 300)
        res["roc"][nombre] = {"x": fpr[::paso].round(4).tolist(), "y": tpr[::paso].round(4).tolist()}
        paso = max(1, len(pr) // 300)
        res["pr"][nombre] = {"x": rc[::paso].round(4).tolist(), "y": pr[::paso].round(4).tolist()}
        if nombre != "Regla por historial":
            fo, mp = calibration_curve(y, s, n_bins=10, strategy="quantile")
            res["calibracion"][nombre] = {"x": mp.round(4).tolist(), "y": fo.round(4).tolist()}

    res["redundancia"] = redundancia(panel, operativo)
    res["aporte_variables"] = aporte_variables(part)
    res["ejemplos"] = (ejemplos(panel, prueba, puntajes[elegido], elegido) +
                       (ejemplos(panel, prueba, puntajes["XGBoost"], "XGBoost")
                        if elegido != "XGBoost" else []))
    return res
