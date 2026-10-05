# -*- coding: utf-8 -*-
"""Límites de los distritos desde OpenStreetMap. Solo hace falta al agregar un distrito.

Se piden a Nominatim por identificador de relación (config.DISTRITOS) y se guardan en
referencia/geografia_distritos.json, que se versiona. La corrida semanal no usa la red.
Datos de OpenStreetMap, bajo licencia ODbL 1.0.
"""
import json
import time
import urllib.parse
import urllib.request

import config

TOLERANCIA = 0.0003   # unos 30 metros, suficiente para el contorno de un distrito


def _area(anillo):
    pares = zip(anillo, anillo[1:] + anillo[:1])
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in pares)) / 2


def descargar():
    salida = {"fuente": "OpenStreetMap vía Nominatim, bajo licencia ODbL 1.0", "distritos": {}}
    for distrito, (_, _, osm_id) in config.DISTRITOS.items():
        url = "https://nominatim.openstreetmap.org/lookup?" + urllib.parse.urlencode({
            "osm_ids": f"R{osm_id}", "format": "json", "polygon_geojson": 1,
            "polygon_threshold": TOLERANCIA})
        pedido = urllib.request.Request(url, headers={"User-Agent": "UTEC-DS5045-Pluz/1.0"})
        geo = json.load(urllib.request.urlopen(pedido, timeout=90))[0]["geojson"]
        poligonos = [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]
        # Solo anillos exteriores, sin islas ni fragmentos menores al 2 % del principal.
        anillos = [[[round(x, 5), round(y, 5)] for x, y in p[0]] for p in poligonos]
        mayor = max(_area(a) for a in anillos)
        salida["distritos"][distrito] = {"osm_relacion": osm_id,
                                         "anillos": [a for a in anillos if _area(a) >= 0.02 * mayor]}
        print(f"  {distrito}: {sum(len(a) for a in salida['distritos'][distrito]['anillos'])} vértices")
        time.sleep(1.2)   # política de uso de Nominatim: una petición por segundo
    destino = config.REFERENCIA / "geografia_distritos.json"
    destino.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
    print("  Escrito", destino)
