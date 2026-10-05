# -*- coding: utf-8 -*-
"""Etapa 2. Base analítica: una fila por alimentador y mes, con variables y objetivo.

Todas las variables usan información disponible hasta el mes de corte inclusive. El
objetivo vale 1 si el alimentador registra al menos un evento de interferencia probable de
vegetación en alguno de los tres meses siguientes; si esos meses todavía no ocurrieron, el
objetivo queda vacío y la fila solo sirve para predecir.
"""
import numpy as np
import pandas as pd

import config


def _meses_desde(serie):
    """Meses desde el último mes con al menos un suceso; vacío si nunca ocurrió."""
    contador, salida = np.nan, []
    for valor in serie.values:
        if valor > 0:
            contador = 0
        elif not np.isnan(contador):
            contador += 1
        salida.append(contador)
    return pd.Series(salida, index=serie.index)


def construir(tablas):
    fallas, poda, guia = tablas["fallas"], tablas["poda"], tablas["guia"]

    # El panel incluye los alimentadores de los distritos aunque no tengan interrupciones:
    # un alimentador sin eventos es información, no un dato ausente.
    en_distritos = guia[guia["DISTRITO"].isin(config.DISTRITOS) & guia["aerea"]]["ALIM"]
    alimentadores = sorted(set(fallas["Alimentador"]) | set(en_distritos))
    corte = fallas["periodo"].max()
    meses = pd.period_range(fallas["periodo"].min(), corte, freq="M")

    panel = pd.MultiIndex.from_product([alimentadores, meses],
                                       names=["alimentador", "periodo"]).to_frame(index=False)
    fuentes = [
        fallas[fallas["veg_ampliada"]].groupby(["Alimentador", "periodo"]).size()
        .rename("eventos_veg"),
        fallas.groupby(["Alimentador", "periodo"]).size().rename("eventos_tot"),
        poda.groupby(["ALIMENTADOR", "periodo"]).size().rename("podas"),
    ]
    for fuente in fuentes:
        panel = panel.merge(fuente, how="left", left_on=["alimentador", "periodo"],
                            right_index=True)
    panel[["eventos_veg", "eventos_tot", "podas"]] = \
        panel[["eventos_veg", "eventos_tot", "podas"]].fillna(0)
    panel = panel.sort_values(["alimentador", "periodo"]).reset_index(drop=True)
    g = panel.groupby("alimentador", group_keys=False)

    h = config.HORIZONTE_MESES
    futuro = sum(g["eventos_veg"].shift(-k) for k in range(1, h + 1))
    completa = g["eventos_veg"].shift(-h).notna()
    panel["objetivo"] = np.where(completa, (futuro.fillna(0) > 0).astype(float), np.nan)

    panel["veg_12m"] = g["eventos_veg"].transform(lambda s: s.rolling(12, min_periods=1).sum())
    panel["veg_hist"] = g["eventos_veg"].cumsum()
    panel["eventos_12m"] = g["eventos_tot"].transform(lambda s: s.rolling(12, min_periods=1).sum())
    panel["eventos_hist"] = g["eventos_tot"].cumsum()
    # Cero significa que hubo poda registrada en el mismo mes del corte. Un alimentador sin
    # ninguna poda registrada no tiene reloj: se le asigna el tope de 24 meses para el
    # modelo y se marca aparte, para que la página no lo muestre como si fuera un dato.
    bruto = g["podas"].transform(_meses_desde)
    panel["sin_registro_poda"] = bruto.isna()
    panel["meses_sin_poda"] = bruto.fillna(config.CENSURA_PODA).clip(upper=config.CENSURA_PODA)
    for c in ("veg_12m", "veg_hist", "eventos_12m"):
        panel["log_" + c] = np.log1p(panel[c])
    panel["mes_sin"] = np.sin(2 * np.pi * panel["periodo"].dt.month / 12)
    panel["mes_cos"] = np.cos(2 * np.pi * panel["periodo"].dt.month / 12)

    # Primer corte utilizable: con un año de historia para las ventanas móviles y con
    # registro de poda, para que el reloj de poda esté definido.
    inicio = max(meses[0] + config.MESES_HISTORIA, poda["periodo"].min())
    return panel, corte, inicio
