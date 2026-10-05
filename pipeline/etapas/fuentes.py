# -*- coding: utf-8 -*-
"""Etapa 1. Localizar, validar y cargar las fuentes de los lotes de Pluz.

Un lote es una carpeta con lo que la empresa envía en una entrega. No hace falta que cada
lote traiga todas las fuentes: para cada una se busca el archivo en los lotes, del más
reciente al más antiguo, y se aplica la regla de su modo (ver config.FUENTES).
"""
import fnmatch
import unicodedata
import warnings

import pandas as pd

import config

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


class ErrorDeLote(Exception):
    """Un lote no cumple el contrato de datos. El mensaje dice qué falta y dónde."""


def _normalizar(texto):
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.lower()


def lotes():
    """Carpetas de lote, de la más antigua a la más reciente."""
    if not config.LOTES.exists():
        raise ErrorDeLote(f"No existe la carpeta de lotes: {config.LOTES}")
    carpetas = sorted(p for p in config.LOTES.iterdir() if p.is_dir())
    if not carpetas:
        raise ErrorDeLote(f"No hay ningún lote en {config.LOTES}")
    return carpetas


def archivos_de(fuente):
    """Archivos de una fuente en todos los lotes, ordenados del más antiguo al más reciente."""
    patrones = [_normalizar(p) for p in config.FUENTES[fuente]["patrones"]]
    encontrados = []
    for lote in lotes():
        for archivo in sorted(lote.iterdir()):
            nombre = _normalizar(archivo.name)
            if archivo.is_file() and not nombre.startswith("~$") and \
                    any(fnmatch.fnmatch(nombre, p) for p in patrones):
                encontrados.append(archivo)
    return encontrados


def _fila_de_encabezado(archivo, hoja, columnas):
    """Busca la fila de títulos: la primera que contiene las dos primeras columnas pedidas."""
    crudo = pd.read_excel(archivo, sheet_name=hoja, header=None, nrows=20)
    for i, fila in crudo.iterrows():
        valores = {str(v).strip() for v in fila.values}
        if all(c in valores for c in columnas[:2]):
            return i
    raise ErrorDeLote(f"{archivo.name}: no se encontró la fila de títulos con {columnas[:2]}")


def _leer(archivo, especificacion):
    hoja = especificacion.get("hoja", 0)
    encabezado = especificacion.get("encabezado", 0)
    columnas = especificacion["columnas"]
    if hoja is not None and not isinstance(hoja, int):
        hojas = pd.ExcelFile(archivo).sheet_names
        if hoja not in hojas:
            raise ErrorDeLote(f"{archivo.parent.name}/{archivo.name}: no tiene la hoja «{hoja}». "
                              f"Hojas del archivo: {hojas}")
    if encabezado == "auto":
        encabezado = _fila_de_encabezado(archivo, hoja, columnas)
    if hoja is None:
        partes = pd.read_excel(archivo, sheet_name=None, header=encabezado)
        tabla = pd.concat([d.assign(_hoja=nombre) for nombre, d in partes.items()],
                          ignore_index=True)
    else:
        tabla = pd.read_excel(archivo, sheet_name=hoja, header=encabezado)
    tabla.columns = [str(c).strip() for c in tabla.columns]
    faltan = [c for c in columnas if c not in tabla.columns]
    if faltan:
        raise ErrorDeLote(f"{archivo.parent.name}/{archivo.name}: faltan las columnas {faltan}")
    tabla["_archivo"] = f"{archivo.parent.name}/{archivo.name}"
    return tabla


def cargar(fuente, registro):
    """Carga una fuente según su modo y deja constancia en el registro de la corrida."""
    esp = config.FUENTES[fuente]
    archivos = archivos_de(fuente)
    if not archivos:
        if esp["obligatoria"]:
            raise ErrorDeLote(f"Ningún lote trae la fuente «{fuente}». Patrones buscados: "
                              f"{esp['patrones']}")
        registro[fuente] = {"archivos": [], "filas": 0}
        return None

    if esp["modo"] == "foto":
        tabla = _leer(archivos[-1], esp)
        usados = [archivos[-1]]
    else:
        # Los archivos de un mismo lote se suman entre sí (la poda de 2025 y la de 2026
        # pueden llegar juntas). Entre lotes, del más reciente al más antiguo, cada lote
        # aporta solo lo anterior a lo que ya cubren los más recientes. Así un lote nuevo
        # reemplaza su periodo completo, y uno que solo trae la última semana se suma sin
        # duplicar.
        por_lote = {}
        for archivo in archivos:
            por_lote.setdefault(archivo.parent, []).append(archivo)
        partes, desde, usados = [], None, []
        for lote in sorted(por_lote, reverse=True):
            t = pd.concat([_leer(a, esp) for a in por_lote[lote]], ignore_index=True)
            t[esp["fecha"]] = pd.to_datetime(t[esp["fecha"]], errors="coerce")
            t = t[t[esp["fecha"]].notna()]
            if desde is not None:
                t = t[t[esp["fecha"]] < desde]
            if len(t):
                partes.append(t)
                usados.extend(por_lote[lote])
                inicio = t[esp["fecha"]].min()
                desde = inicio if desde is None else min(desde, inicio)
        tabla = pd.concat(partes, ignore_index=True)

    registro[fuente] = {"archivos": [f"{a.parent.name}/{a.name}" for a in usados],
                        "filas": int(len(tabla))}
    return tabla


def cargar_todo():
    """Carga y normaliza todas las fuentes. Devuelve un diccionario de tablas y el registro."""
    registro = {"lotes": [p.name for p in lotes()]}
    t = {f: cargar(f, registro) for f in config.FUENTES}

    fallas = t["interrupciones"]
    fallas["Inicio"] = pd.to_datetime(fallas["Inicio"], errors="coerce")
    fallas["Alimentador"] = fallas["Alimentador"].astype(str).str.strip()
    fallas["Localización"] = fallas["Localización"].astype(str).str.strip()
    fallas["Causa"] = fallas["Causa"].astype(str).str.strip()
    fallas["periodo"] = fallas["Inicio"].dt.to_period("M")
    fallas["veg_ampliada"] = (fallas["Causa"].isin(config.CAUSAS_VEGETACION) |
                              ((fallas["Causa"] == config.CAUSA_NO_UBICADA) &
                               (fallas["Localización"] == config.LOCALIZACION_AEREA)))

    poda = t["poda"]
    poda["ALIMENTADOR"] = poda["ALIMENTADOR"].astype(str).str.strip()
    poda["periodo"] = poda["FECHA"].dt.to_period("M")
    poda = poda.drop_duplicates(subset=["FECHA", "ALIMENTADOR", "CIRCUITO",
                                        "DIRECCION DE TRABAJO"])

    ranking = t["ranking_saidi"]
    ranking = ranking[ranking["Alimentador"].notna()].copy()
    ranking["Alimentador"] = ranking["Alimentador"].astype(str).str.strip()
    saidi_ltm = pd.to_numeric(ranking["SAIDI LTM"], errors="coerce").groupby(
        ranking["Alimentador"]).first()

    guia = t["guia_sed"]
    guia = guia[guia["SED"].notna()].copy()
    if "ESTADO" in guia.columns:
        guia = guia[guia["ESTADO"].astype(str).str.strip() != "Retirado"]
    guia["SED"] = guia["SED"].astype(str).str.strip()
    guia["ALIM"] = guia["ALIM"].astype(str).str.strip()
    guia["DISTRITO"] = guia["DISTRITO"].astype(str).str.strip().str.upper()
    guia["lon"] = pd.to_numeric(guia["UTM\nX LONG"], errors="coerce")
    guia["lat"] = pd.to_numeric(guia["UTM\nY LAT"], errors="coerce")
    guia["kva"] = pd.to_numeric(guia["KVA"], errors="coerce")
    guia["clientes"] = pd.to_numeric(guia["Clientes BT Cantidad Referencial"], errors="coerce")
    guia["aerea"] = guia["TIPO DE CONSTRUCCIÓN"].astype(str).str.contains("Aérea")
    guia["DIRECCION"] = guia["DIRECCION"].astype(str).str.strip()

    # Avisos que no detienen la corrida pero que alguien tiene que mirar.
    avisos = []
    dic = t["diccionario_causas"]
    if dic is not None:
        conocidas = set(dic["Causa (según la base)"].dropna().astype(str).str.strip())
        nuevas = sorted(set(fallas["Causa"]) - conocidas - {"nan"})
        if nuevas:
            avisos.append(f"Causas que no están en el diccionario: {nuevas}")
    sin_guia = sorted(set(fallas.loc[fallas["veg_ampliada"], "Alimentador"]) - set(guia["ALIM"]))
    if sin_guia:
        avisos.append(f"{len(sin_guia)} alimentadores con eventos de vegetación no figuran "
                      f"en la guía de subestaciones")
    faltantes = [d for d in config.DISTRITOS if d not in set(guia["DISTRITO"])]
    if faltantes:
        raise ErrorDeLote(f"La guía de subestaciones no trae los distritos {faltantes}")
    registro["avisos"] = avisos
    registro["periodo_interrupciones"] = [str(fallas["Inicio"].min().date()),
                                          str(fallas["Inicio"].max().date())]
    registro["periodo_poda"] = [str(poda["FECHA"].min().date()),
                                str(poda["FECHA"].max().date())]

    return {"fallas": fallas, "poda": poda, "saidi_ltm": saidi_ltm, "guia": guia}, registro
