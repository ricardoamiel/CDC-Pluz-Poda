# -*- coding: utf-8 -*-
"""Arma los archivos de prueba de la carga semanal a partir de los lotes reales.

Uso, desde la raíz del repositorio:

    python pipeline/demo/archivos_de_prueba.py

Los deja en pipeline/datos/prueba, que no se publica. Cada uno simula un caso de la guía
docs/GUIA_CARGA_SEMANAL.md:

    PRUEBA_misma_semana.csv          la última semana ya cargada, tal cual: «Sin cambios»
    PRUEBA_semana_nueva.csv          la última semana corrida 7 días: fechas nuevas. FICTICIA
    PRUEBA_correccion_1fila.csv      la última semana con una fila de más: corrección
    PRUEBA_semana_vieja.csv          una semana de un mes antes: borraría lo posterior
    PRUEBA_poda_misma_semana.csv     la última semana de poda ya cargada: «Sin cambios»

La semana nueva es inventada: si se confirma en la herramienta real, hay que deshacerla con
«Restaurar» y no publicarla.
"""
import sys
from pathlib import Path

import pandas as pd

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from etapas import fuentes  # noqa: E402

DESTINO = PIPELINE / "datos" / "prueba"


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    i = fuentes.cargar("interrupciones", {})
    cols = [c for c in i.columns if not c.startswith("_")]
    i = i[cols]
    fin = i["Inicio"].max().normalize()
    ultima = i[i["Inicio"] >= fin - pd.Timedelta(days=6)]
    ultima.to_csv(DESTINO / "PRUEBA_misma_semana.csv", index=False)
    nueva = ultima.copy()
    nueva["Inicio"] += pd.Timedelta(days=7)
    nueva.to_csv(DESTINO / "PRUEBA_semana_nueva.csv", index=False)
    extra = ultima.iloc[[len(ultima) // 2]].copy()
    extra["Alimentador"] = "ZZ-99"
    pd.concat([ultima, extra]).to_csv(DESTINO / "PRUEBA_correccion_1fila.csv", index=False)
    inicio_vieja = fin - pd.Timedelta(days=50)
    vieja = i[(i["Inicio"] >= inicio_vieja) & (i["Inicio"] < inicio_vieja + pd.Timedelta(days=7))]
    vieja.to_csv(DESTINO / "PRUEBA_semana_vieja.csv", index=False)

    p = fuentes.cargar("poda", {})
    pcols = ["FECHA", "ALIMENTADOR", "CIRCUITO", "DIRECCION DE TRABAJO"]
    pfin = p["FECHA"].max().normalize()
    p[p["FECHA"] >= pfin - pd.Timedelta(days=6)][pcols].to_csv(
        DESTINO / "PRUEBA_poda_misma_semana.csv", index=False)

    print(f"Archivos de prueba en {DESTINO}:")
    for f in sorted(DESTINO.glob("PRUEBA_*.csv")):
        print(f"  {f.name}: {sum(1 for _ in f.open(encoding='utf-8')) - 1} filas")
    print(f"Semana nueva (ficticia): del {(fin + pd.Timedelta(days=1)).date()} al "
          f"{(fin + pd.Timedelta(days=7)).date()}")


if __name__ == "__main__":
    main()
