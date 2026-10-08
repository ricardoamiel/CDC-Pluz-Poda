# -*- coding: utf-8 -*-
"""Genera los diagramas de arquitectura en SVG: python docs/diagramas.py

Se escriben a mano, sin bibliotecas, para que el SVG quede limpio, liviano y editable. La
paleta es la de Pluz y los textos siguen las reglas de redacción del repositorio.
"""
from pathlib import Path

AQUI = Path(__file__).resolve().parent
AZUL, AZUL_CL, AZUL_OS = "#395aa1", "#e8eef8", "#1d2f55"
VERDE, VERDE_CL = "#3f7d33", "#e6f2e5"
AMBAR, AMBAR_CL = "#ac5700", "#fdf0d6"
GRIS, GRIS_CL, BORDE, TINTA = "#4e5a6e", "#f4f7fc", "#c2cee2", "#131a26"


class Lienzo:
    def __init__(self, ancho, alto, titulo, subtitulo):
        self.w, self.h, self.partes = ancho, alto, []
        self.partes.append(
            f'<text x="24" y="34" font-size="20" font-weight="700" fill="{TINTA}">{titulo}</text>'
            f'<text x="24" y="56" font-size="13" fill="{GRIS}">{subtitulo}</text>')

    def grupo(self, x, y, w, h, titulo, color=AZUL):
        self.partes.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="none" stroke="{color}" '
            f'stroke-width="1.5" stroke-dasharray="6 5"/>'
            f'<text x="{x + 14}" y="{y + 20}" font-size="12" font-weight="700" fill="{color}">{titulo}</text>')

    def caja(self, x, y, w, h, titulo, lineas=(), relleno=AZUL_CL, borde=AZUL, numero=None):
        self.partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
                           f'fill="{relleno}" stroke="{borde}" stroke-width="1.3"/>')
        tx = x + 12
        if numero is not None:
            self.partes.append(f'<circle cx="{x + 18}" cy="{y + 19}" r="10" fill="{borde}"/>'
                               f'<text x="{x + 18}" y="{y + 23}" font-size="11" font-weight="700" '
                               f'fill="#fff" text-anchor="middle">{numero}</text>')
            tx = x + 34
        self.partes.append(f'<text x="{tx}" y="{y + 23}" font-size="13" font-weight="700" '
                           f'fill="{TINTA}">{titulo}</text>')
        for i, linea in enumerate(lineas):
            self.partes.append(f'<text x="{x + 12}" y="{y + 42 + 15 * i}" font-size="11.5" '
                               f'fill="{GRIS}">{linea}</text>')

    def flecha(self, puntos, etiqueta=None, color=GRIS, punteada=False, pos=0.5, dy=-6):
        d = "M" + " L".join(f"{x},{y}" for x, y in puntos)
        trazo = ' stroke-dasharray="5 4"' if punteada else ""
        self.partes.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"{trazo} '
                           f'marker-end="url(#punta)"/>')
        if etiqueta:
            (x1, y1), (x2, y2) = puntos[0], puntos[-1]
            if len(puntos) > 2:
                (x1, y1), (x2, y2) = puntos[1], puntos[2]
            x, y = x1 + (x2 - x1) * pos, y1 + (y2 - y1) * pos + dy
            self.partes.append(f'<text x="{x}" y="{y}" font-size="11" fill="{color}" '
                               f'text-anchor="middle" font-style="normal">{etiqueta}</text>')

    def guardar(self, nombre):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
               f'width="{self.w}" height="{self.h}" font-family="Arial, Helvetica, sans-serif">'
               f'<defs><marker id="punta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
               f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GRIS}"/></marker></defs>'
               f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>'
               + "".join(self.partes) + "</svg>")
        (AQUI / nombre).write_text(svg, encoding="utf-8")
        print("Escrito", AQUI / nombre)


def en_las_instalaciones():
    c = Lienzo(1220, 600, "Propuesta 1. En las instalaciones de Pluz",
               "Lotes semanales con el mismo pipeline del repositorio, una base PostgreSQL y la página dentro de la red")
    c.caja(24, 90, 200, 96, "Áreas de Pluz", ["Excel semanal de interrupciones,", "poda, guía de subestaciones", "y ranking de SAIDI"],
           relleno=GRIS_CL, borde=GRIS)
    c.caja(264, 90, 200, 96, "Carpeta compartida", ["OneDrive, SharePoint o", "unidad de red; una carpeta", "por lote, AAAAMMDD"],
           relleno=GRIS_CL, borde=GRIS)
    c.caja(504, 90, 200, 96, "Programador de tareas", ["de Windows, cada lunes", "a primera hora"], relleno=GRIS_CL, borde=GRIS)
    c.flecha([(224, 138), (262, 138)])
    c.flecha([(464, 138), (502, 138)])
    c.flecha([(704, 138), (742, 138)])

    c.grupo(744, 76, 452, 330, "Pipeline en un servidor o PC de la Subgerencia")
    c.caja(762, 106, 200, 60, "Validar el lote", ["contrato de columnas y archivos"], numero=1)
    c.caja(978, 106, 200, 60, "Base analítica", ["alimentador y mes, variables"], numero=2)
    c.caja(762, 182, 200, 60, "Inferencia semanal", ["riesgo a 3 meses por alimentador"], numero=3)
    c.caja(978, 182, 200, 60, "Entrenamiento mensual", ["con freno frente a la regla"], numero=4,
           relleno=AMBAR_CL, borde=AMBAR)
    c.caja(762, 258, 200, 60, "Índice por distrito", ["dos niveles, plan del trimestre"], numero=5)
    c.caja(978, 258, 200, 60, "MLflow", ["métricas y versiones de modelos"], relleno=AMBAR_CL, borde=AMBAR)
    c.caja(762, 334, 416, 56, "Salidas", ["data de la página, plan en Excel, reporte de la corrida"], numero=6)
    c.flecha([(962, 136), (976, 136)])
    c.flecha([(862, 166), (862, 180)])
    c.flecha([(1078, 166), (1078, 180)])
    c.flecha([(976, 212), (964, 212)], punteada=True)
    c.flecha([(862, 242), (862, 256)])
    c.flecha([(1078, 242), (1078, 256)], punteada=True)
    c.flecha([(862, 318), (862, 332)])

    c.caja(744, 450, 452, 110, "PostgreSQL con PostGIS",
           ["Tablas que se reemplazan: interrupciones, poda, guía, ranking, base analítica.",
            "Tablas que se acumulan: predicciones, índice por alimentador y por",
            "subestación, y registro de corridas. Es el historial para medir aciertos.",
            "Alternativa equivalente: SQL Server Express."], relleno=VERDE_CL, borde=VERDE)
    c.flecha([(970, 390), (970, 448)], "escribe")

    c.caja(24, 450, 200, 110, "Página interna", ["la misma herramienta,", "servida en IIS, nginx", "o SharePoint"],
           relleno=AZUL_CL, borde=AZUL_OS)
    c.caja(264, 450, 200, 110, "Plan en Excel", ["para programar las", "cuadrillas del mes"], relleno=AZUL_CL, borde=AZUL_OS)
    c.caja(504, 450, 200, 110, "Excel y Power BI", ["conectados a la base", "para cruzar con sus", "propias planillas"],
           relleno=AZUL_CL, borde=AZUL_OS)
    c.flecha([(742, 505), (706, 505)])
    c.flecha([(860, 390), (860, 420), (124, 420), (124, 448)], "publica", pos=0.5)
    c.flecha([(760, 390), (760, 412), (364, 412), (364, 448)])
    c.guardar("arquitectura_en_las_instalaciones.svg")


def en_aws():
    c = Lienzo(1240, 700, "Propuesta 2. En AWS",
               "Mismo flujo con piezas administradas: sin servidores encendidos y pago por uso")
    c.caja(24, 90, 190, 86, "Áreas de Pluz", ["Excel y CSV semanales"], relleno=GRIS_CL, borde=GRIS)
    c.caja(244, 90, 210, 86, "Página de carga", ["enlace firmado de S3,", "acceso con Cognito"], relleno=GRIS_CL, borde=GRIS)
    c.caja(484, 90, 220, 86, "S3, zona cruda", ["archivos tal como llegan,", "versionados, por lote"], relleno=VERDE_CL, borde=VERDE)
    c.caja(734, 90, 220, 86, "EventBridge", ["llegada de un archivo", "o calendario de cada lunes"], relleno=GRIS_CL, borde=GRIS)
    c.flecha([(214, 133), (242, 133)])
    c.flecha([(454, 133), (482, 133)])
    c.flecha([(704, 133), (732, 133)])
    c.flecha([(954, 133), (1000, 133), (1000, 214)], "inicia")

    c.grupo(24, 216, 1192, 300, "AWS Step Functions orquesta cada corrida y se detiene si algo falla", color=AZUL)
    c.caja(44, 250, 220, 86, "Lambda: validar y convertir", ["contrato de datos; de Excel", "a Parquet"], numero=1)
    c.caja(294, 250, 230, 86, "S3, zona curada", ["Parquet por fuente y lote,", "catálogo de AWS Glue"], numero=2,
           relleno=VERDE_CL, borde=VERDE)
    c.caja(554, 250, 230, 86, "Athena: tabla de variables", ["ingeniería de variables por", "alimentador y mes, en SQL"], numero=3)
    c.caja(814, 250, 380, 86, "SageMaker: entrenamiento mensual", ["benchmark y reentrenamiento; Model Registry aprueba",
                                                                    "solo si supera el freno; MLflow administrado"],
           numero=4, relleno=AMBAR_CL, borde=AMBAR)
    c.caja(44, 400, 300, 86, "SageMaker: inferencia semanal", ["Batch Transform o Processing,", "por lotes, con el modelo aprobado"], numero=5)
    c.caja(374, 400, 260, 86, "Athena: tabla de inferencia", ["probabilidad por alimentador", "y corte, con historial"], numero=6)
    c.caja(664, 400, 260, 86, "Lambda: índice y salidas", ["índice por distrito, plan", "en Excel, reporte"], numero=7)
    c.caja(954, 400, 240, 86, "SNS y CloudWatch", ["correo con el reporte,", "alarmas si una etapa falla"],
           relleno=GRIS_CL, borde=GRIS)
    c.flecha([(264, 293), (292, 293)])
    c.flecha([(524, 293), (552, 293)])
    c.flecha([(784, 293), (812, 293)], punteada=True)
    c.flecha([(669, 336), (669, 372), (194, 372), (194, 398)])
    c.flecha([(1004, 336), (1004, 356), (300, 356), (300, 398)], punteada=True)
    c.flecha([(344, 443), (372, 443)])
    c.flecha([(634, 443), (662, 443)])
    c.flecha([(924, 443), (952, 443)])

    c.caja(484, 560, 330, 100, "S3 y CloudFront: la página", ["sitio estático con acceso restringido", "por Cognito o por las IP de Pluz;",
                                                              "datos de la herramienta en JSON"], relleno=AZUL_CL, borde=AZUL_OS)
    c.caja(844, 560, 350, 100, "Consumo", ["Subgerencia: página y plan en Excel;", "analistas: Athena desde Excel o",
                                           "Power BI con el conector ODBC"], relleno=AZUL_CL, borde=AZUL_OS)
    c.caja(24, 560, 430, 100, "Seguridad y costo", ["buckets privados con cifrado KMS, IAM mínimo,",
                                                     "registro con CloudTrail; sin endpoints encendidos:",
                                                     "se paga solo por los minutos de cada corrida"],
           relleno=GRIS_CL, borde=GRIS)
    c.flecha([(794, 486), (794, 520), (649, 520), (649, 558)], "publica", pos=0.5)
    c.flecha([(814, 610), (842, 610)])
    c.guardar("arquitectura_aws.svg")


if __name__ == "__main__":
    en_las_instalaciones()
    en_aws()
