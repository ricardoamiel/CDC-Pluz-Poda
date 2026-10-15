# -*- coding: utf-8 -*-
"""Prepara una demostración del flujo semanal con datos reales, sin tocar la operación real.

Uso, desde la raíz del repositorio:

    python pipeline/demo/preparar_demo.py            arma la demostración desde cero
    python pipeline/demo/preparar_demo.py siguiente  deja en la carpeta de entrada el Excel
                                                     de la semana siguiente, como lo haría Pluz
    python pipeline/demo/preparar_demo.py borrar     borra toda la demostración

La demostración vive en pipeline/datos/demo, que no se sube a git. Es una repetición con los
datos reales: el estado inicial tiene las interrupciones solo hasta julio de 2026, y las de
agosto se reparten en tres Excel semanales que se van entregando uno por uno. Cada vez que se
corre la semana se ve cómo cambian el corte, la ventana, el plan y el monitoreo del modelo.
"""
import shutil
import sys
from pathlib import Path

import pandas as pd

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
ORIGEN = PIPELINE / "datos" / "lotes"
DEMO = PIPELINE / "datos" / "demo"
PENDIENTES = DEMO / "pendientes"
INICIO_AGOSTO = pd.Timestamp("2026-08-01")
SEMANAS = [("semana_1", "2026-08-01", "2026-08-08"),
           ("semana_2", "2026-08-08", "2026-08-15"),
           ("semana_3", "2026-08-15", "2026-09-01")]


def armar():
    if DEMO.exists():
        shutil.rmtree(DEMO)
    for carpeta in ("lotes", "entrada", "pendientes", "salidas", "web"):
        (DEMO / carpeta).mkdir(parents=True)

    # Lotes históricos: los mismos de la operación, salvo que las interrupciones llegan
    # solo hasta julio de 2026. Se guarda solo la hoja que usa el pipeline.
    for lote in sorted(p for p in ORIGEN.iterdir() if p.is_dir()):
        destino = DEMO / "lotes" / lote.name
        destino.mkdir()
        for archivo in lote.iterdir():
            if "interrupciones diarias" in archivo.name.lower():
                fallas = pd.read_excel(archivo, sheet_name="Falla_Alim")
                fallas["Inicio"] = pd.to_datetime(fallas["Inicio"], errors="coerce")
                with pd.ExcelWriter(destino / archivo.name) as libro:
                    fallas[fallas["Inicio"] < INICIO_AGOSTO].to_excel(libro, sheet_name="Falla_Alim", index=False)
                for nombre, desde, hasta in SEMANAS:
                    semana = fallas[(fallas["Inicio"] >= desde) & (fallas["Inicio"] < hasta)]
                    with pd.ExcelWriter(PENDIENTES / f"Interrupciones diarias UTEC {nombre}.xlsx") as libro:
                        semana.to_excel(libro, sheet_name="Falla_Alim", index=False)
                    print(f"  Excel de la {nombre.replace('_', ' ')}: {len(semana)} interrupciones")
            elif archivo.is_file():
                shutil.copy2(archivo, destino / archivo.name)

    # Página propia de la demostración, para no tocar la publicada.
    for nombre in ("index.html", ".nojekyll"):
        shutil.copy2(REPO / nombre, DEMO / "web" / nombre)
    for carpeta in ("css", "js", "data", "assets"):
        shutil.copytree(REPO / carpeta, DEMO / "web" / carpeta)
    print(f"\nDemostración armada en {DEMO}")
    print("Siguiente: correr el estado inicial y luego entregar la primera semana.")


def siguiente():
    pendientes = sorted(PENDIENTES.glob("*.xlsx"))
    if not pendientes:
        print("Ya se entregaron las tres semanas. Para empezar de nuevo, corra el script sin orden.")
        return
    archivo = pendientes[0]
    shutil.move(str(archivo), DEMO / "entrada" / archivo.name)
    print(f"Pluz dejó en la carpeta de entrada: {archivo.name}")


def borrar():
    """La demostración nunca toca los datos reales: borrarla deja todo como estaba."""
    if DEMO.exists():
        shutil.rmtree(DEMO)
        print(f"Demostración borrada: {DEMO}")
    else:
        print("No había ninguna demostración armada.")


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else "armar"
    {"armar": armar, "siguiente": siguiente, "borrar": borrar}[orden]()
