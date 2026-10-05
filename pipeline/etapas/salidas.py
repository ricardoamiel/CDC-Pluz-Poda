# -*- coding: utf-8 -*-
"""Etapa 5. Salidas para la operación: el plan en Excel y, si se configura, la base de datos.

El Excel existe porque es la herramienta con la que Pluz trabaja hoy: el plan de cada
distrito llega en el mismo formato en que se programa la poda.

La base de datos es opcional. Si config.BASE_DE_DATOS está vacía, esta etapa no hace nada.
Acepta dos tipos de dirección:

    sqlite:///ruta/al/archivo.db                      un archivo local, sin instalar nada
    postgresql://usuario:clave@servidor:5432/pluz     un servidor PostgreSQL

Las tablas de fuentes y la base analítica se reemplazan en cada corrida, porque son la
versión consolidada vigente. Las predicciones, el índice y el registro de corridas se
acumulan con la fecha de la corrida, porque son el historial con el que más adelante se
medirá si el plan acertó.
"""
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

import config


def escribir_excel(distritos, corte, destino):
    """Un libro con el resumen de los distritos y el plan de cada uno en dos niveles."""
    resumen = pd.DataFrame([{"Distrito": d["meta"]["distrito"], **d["meta"]["resumen"]}
                            for d in distritos.values()])
    with pd.ExcelWriter(destino) as libro:
        resumen.to_excel(libro, sheet_name="Resumen", index=False)
        for codigo, d in distritos.items():
            meta = d["meta"]
            alim = pd.DataFrame(d["alimentadores"]).drop(columns=["componentes", "lon", "lat"])
            alim["motivos"] = alim["motivos"].apply(", ".join)
            alim["en_el_plan"] = alim["puesto"] <= meta["k_alimentadores"]
            sed = pd.DataFrame(d["subestaciones"]).drop(columns=["componentes"])
            sed["en_el_plan"] = sed["puesto"] <= meta["capacidad_mes"]
            alim.to_excel(libro, sheet_name=f"{codigo} alimentadores", index=False)
            sed.to_excel(libro, sheet_name=f"{codigo} subestaciones", index=False)
    return destino


def _columna(nombre):
    limpio = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^0-9a-zA-Z]+", "_", limpio).strip("_").lower()
    return limpio or "columna"


def _conexion(direccion):
    if direccion.startswith("sqlite:///"):
        ruta = Path(direccion.replace("sqlite:///", "", 1))
        if not ruta.is_absolute():
            ruta = config.REPO / ruta
        ruta.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(ruta)
    try:
        from sqlalchemy import create_engine
    except ImportError as error:
        raise RuntimeError("Para PostgreSQL hace falta correr: "
                           "python pipeline/actualizar.py instalar base") from error
    return create_engine(direccion)


def guardar_en_base(tablas, panel, operativo, distritos, corrida):
    """Escribe fuentes, base analítica, predicción, índice y registro de la corrida."""
    if not config.BASE_DE_DATOS:
        return False
    conexion = _conexion(config.BASE_DE_DATOS)
    sello = {"fecha_corrida": corrida["fecha"], "corte": corrida["corte"]}

    def texto(df):
        # Los periodos mensuales se guardan como texto AAAAMM, que cualquier motor entiende.
        # Los nombres de columna pasan a minúsculas sin espacios ni tildes, que es lo cómodo
        # para consultar en SQL; si dos quedan iguales, como KVA y kva, se conserva la primera.
        df = df.copy()
        for c in df.columns:
            if isinstance(df[c].dtype, pd.PeriodDtype):
                df[c] = df[c].dt.strftime("%Y%m")
        df.columns = [_columna(c) for c in df.columns]
        return df.loc[:, ~pd.Index(df.columns).duplicated()]

    reemplazar = {
        "interrupciones": tablas["fallas"].drop(columns=["_archivo"], errors="ignore"),
        "poda": tablas["poda"].drop(columns=["_archivo", "_hoja"], errors="ignore"),
        "guia_sed": tablas["guia"].drop(columns=["_archivo"], errors="ignore"),
        "ranking_saidi": tablas["saidi_ltm"].rename("saidi_ltm").reset_index(),
        "base_analitica": panel,
    }
    for nombre, df in reemplazar.items():
        df = texto(df)
        df.to_sql(nombre, conexion, if_exists="replace", index=False)

    acumular = {
        "historial_predicciones": operativo[["alimentador", "probabilidad"]].assign(**sello),
        "historial_indice_alimentador": pd.concat([
            pd.DataFrame(d["alimentadores"]).drop(columns=["componentes", "motivos"])
            .assign(distrito=d["meta"]["distrito"], **sello) for d in distritos.values()]),
        "historial_indice_subestacion": pd.concat([
            pd.DataFrame(d["subestaciones"]).drop(columns=["componentes"])
            .assign(distrito=d["meta"]["distrito"], **sello) for d in distritos.values()]),
        "corridas": pd.DataFrame([{
            **sello, "publicado": corrida["publicado"],
            "cobertura_40_modelo": corrida["validacion"]["modelo"]["cobertura_40"],
            "cobertura_40_regla": corrida["validacion"]["regla"]["cobertura_40"],
            "lotes": ", ".join(corrida["fuentes"]["lotes"])}]),
    }
    for nombre, df in acumular.items():
        texto(df).to_sql(nombre, conexion, if_exists="append", index=False)
    if isinstance(conexion, sqlite3.Connection):
        conexion.close()
    return True
