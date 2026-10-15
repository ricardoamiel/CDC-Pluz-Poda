# -*- coding: utf-8 -*-
"""Genera los diagramas de arquitectura en SVG: python docs/diagramas.py

Estilo de draw.io: cada componente es una tarjeta con su ícono arriba. Los íconos de AWS
siguen el lenguaje de sus íconos de arquitectura, un cuadrado del color de la categoría
del servicio con un símbolo blanco; el resto usa el color de cada herramienta. Se dibujan
aquí mismo, sin archivos externos, para que el SVG quede liviano y editable. Los textos
siguen las reglas de redacción del repositorio.
"""
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TINTA, GRIS, BORDE, FONDO = "#131a26", "#4e5a6e", "#c2cee2", "#f6f8fc"
AZUL = "#395aa1"

# Colores de categoría de AWS y de cada herramienta.
COLOR = {
    "almacenamiento": "#7AA116", "computo": "#ED7100", "analitica": "#8C4FFF",
    "aprendizaje": "#01A88D", "integracion": "#E7157B", "seguridad": "#DD344C",
    "excel": "#217346", "nube_ms": "#0364B8", "windows": "#0078D4", "python": "#3776AB",
    "mlflow": "#0194E2", "postgres": "#336791", "powerbi": "#E8B300", "pluz": AZUL,
    "personas": "#4e5a6e",
}

B = 'fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"'
L = 'fill="#fff"'

# Símbolos en una rejilla de 48 por 48, dibujados en blanco sobre el color del ícono.
SIMBOLOS = {
    "balde": f'<path d="M12 15 L36 15 L33 36 Q24 40 15 36 Z" {B}/><ellipse cx="24" cy="15" rx="12" ry="4" {B}/>',
    "lambda": f'<path d="M14 36 L22 22 M17 12 L21 12 L34 36 L37 36" {B}/>',
    "lupa_tabla": f'<rect x="10" y="11" width="20" height="16" rx="2" {B}/><path d="M10 17 H30 M17 11 V27" {B}/>'
                  f'<circle cx="30" cy="30" r="7" {B}/><path d="M35 35 L39 39" {B}/>',
    "catalogo": f'<path d="M12 12 H32 V37 H12 Z M17 12 V37 M21 19 H28 M21 24 H28" {B}/>',
    "red_neuronal": f'<circle cx="13" cy="15" r="3.5" {B}/><circle cx="13" cy="33" r="3.5" {B}/>'
                    f'<circle cx="35" cy="24" r="3.5" {B}/><circle cx="24" cy="24" r="3.5" {B}/>'
                    f'<path d="M16 16 L21 22 M16 32 L21 26 M27.5 24 H31.5" {B}/>',
    "bus": f'<circle cx="24" cy="24" r="5" {B}/><path d="M24 9 V17 M24 31 V39 M9 24 H17 M31 24 H39 M13 13 L18 18 M35 35 L30 30" {B}/>',
    "flujo": f'<rect x="18" y="8" width="12" height="9" rx="2" {B}/><rect x="8" y="31" width="12" height="9" rx="2" {B}/>'
             f'<rect x="28" y="31" width="12" height="9" rx="2" {B}/><path d="M24 17 V24 H14 V31 M24 24 H34 V31" {B}/>',
    "campana": f'<path d="M15 31 V22 Q15 13 24 13 Q33 13 33 22 V31 L36 34 H12 Z M21 37 Q24 40 27 37" {B}/>',
    "medidor": f'<path d="M10 32 A14 14 0 1 1 38 32" {B}/><path d="M24 30 L31 19" {B}/><circle cx="24" cy="30" r="2" {L}/>',
    "globo": f'<circle cx="24" cy="24" r="13" {B}/><ellipse cx="24" cy="24" rx="6" ry="13" {B}/><path d="M11 24 H37" {B}/>',
    "usuario": f'<circle cx="24" cy="17" r="6" {B}/><path d="M12 37 Q12 26 24 26 Q36 26 36 37" {B}/>',
    "personas": f'<circle cx="18" cy="17" r="5" {B}/><circle cx="31" cy="19" r="4" {B}/>'
                f'<path d="M8 36 Q8 26 18 26 Q28 26 28 36 M27 27 Q38 26 39 35" {B}/>',
    "escudo": f'<path d="M24 9 L37 14 V23 Q37 34 24 40 Q11 34 11 23 V14 Z M18 24 L22 28 L30 19" {B}/>',
    "cargar": f'<path d="M12 30 V36 H36 V30 M24 30 V12 M17 19 L24 12 L31 19" {B}/>',
    "hoja": f'<rect x="10" y="10" width="28" height="28" rx="2" {B}/><path d="M10 19 H38 M10 28 H38 M19 10 V38 M28 10 V38" {B}/>',
    "carpeta": f'<path d="M9 16 V35 H39 V19 H24 L21 15 H9 Z" {B}/>',
    "calendario": f'<rect x="10" y="12" width="28" height="25" rx="3" {B}/><path d="M10 19 H38 M17 9 V14 M31 9 V14" {B}/>'
                  f'<circle cx="24" cy="28" r="5" {B}/><path d="M24 26 V28 L26 29" {B}/>',
    "codigo": f'<path d="M18 15 L9 24 L18 33 M30 15 L39 24 L30 33 M27 12 L21 36" {B}/>',
    "tendencia": f'<path d="M9 36 H39 M9 36 V10" {B}/><path d="M12 31 L20 22 L26 27 L36 14" {B}/><circle cx="36" cy="14" r="2.4" {L}/>',
    "cilindro": f'<ellipse cx="24" cy="13" rx="12" ry="4.5" {B}/><path d="M12 13 V35 Q24 41 36 35 V13 M12 24 Q24 30 36 24" {B}/>',
    "barras": f'<path d="M13 37 V26 M21 37 V18 M29 37 V22 M37 37 V12" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/>',
    "navegador": f'<rect x="8" y="11" width="32" height="26" rx="3" {B}/><path d="M8 18 H40" {B}/>'
                 f'<circle cx="13" cy="14.5" r="1.2" {L}/><circle cx="17" cy="14.5" r="1.2" {L}/><path d="M14 31 L20 25 L25 29 L33 22" {B}/>',
    "verificar": f'<rect x="11" y="9" width="26" height="30" rx="3" {B}/><path d="M16 17 L19 20 L24 14 M16 29 L19 32 L24 26 M27 17 H32 M27 29 H32" {B}/>',
    "tabla": f'<rect x="9" y="11" width="30" height="26" rx="2" {B}/><path d="M9 19 H39 M9 28 H39 M20 11 V37" {B}/>',
    "rayo": f'<path d="M27 8 L14 27 H23 L20 40 L34 20 H25 Z" {B}/>',
    "ranking": f'<path d="M11 14 H31 M11 22 H26 M11 30 H21 M11 38 H16" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/>',
    "documento": f'<path d="M14 8 H29 L36 15 V40 H14 Z M29 8 V15 H36 M19 23 H31 M19 29 H31 M19 35 H27" {B}/>',
    "etiqueta": f'<path d="M10 24 L24 10 H38 V24 L24 38 Z" {B}/><circle cx="31" cy="17" r="2.5" {L}/>',
}


class Lienzo:
    def __init__(self, ancho, alto, titulo, subtitulo):
        self.w, self.h = ancho, alto
        self.partes = [f'<rect width="{ancho}" height="{alto}" fill="#ffffff"/>',
                       f'<text x="28" y="38" font-size="22" font-weight="700" fill="{TINTA}">{titulo}</text>',
                       f'<text x="28" y="62" font-size="13.5" fill="{GRIS}">{subtitulo}</text>']

    def icono(self, cx, cy, simbolo, color, tam=46):
        x, y, e = cx - tam / 2, cy - tam / 2, tam / 48
        self.partes.append(f'<g transform="translate({x},{y})"><rect width="{tam}" height="{tam}" rx="{tam * 0.18}" '
                           f'fill="{COLOR[color]}"/><g transform="scale({e})">{SIMBOLOS[simbolo]}</g></g>')

    def tarjeta(self, x, y, w, titulo, lineas=(), iconos=(), numero=None, alto=None, discontinua=False):
        """Tarjeta al estilo draw.io: uno o dos íconos arriba, título y descripción debajo."""
        h = alto or (96 + 15 * len(lineas))
        borde = f'stroke="{BORDE}" stroke-width="1.2"' + (' stroke-dasharray="5 4"' if discontinua else "")
        self.partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff" {borde}/>')
        n = len(iconos)
        for i, (simbolo, color) in enumerate(iconos):
            cx = x + w / 2 + (i - (n - 1) / 2) * 54
            self.icono(cx, y + 32, simbolo, color)
        if numero is not None:
            self.partes.append(f'<circle cx="{x + 16}" cy="{y + 16}" r="10" fill="{AZUL}"/>'
                               f'<text x="{x + 16}" y="{y + 20}" font-size="11" font-weight="700" fill="#fff" '
                               f'text-anchor="middle">{numero}</text>')
        self.partes.append(f'<text x="{x + w / 2}" y="{y + 72}" font-size="13" font-weight="700" fill="{TINTA}" '
                           f'text-anchor="middle">{titulo}</text>')
        for i, linea in enumerate(lineas):
            self.partes.append(f'<text x="{x + w / 2}" y="{y + 90 + 15 * i}" font-size="11.5" fill="{GRIS}" '
                               f'text-anchor="middle">{linea}</text>')
        return h

    def grupo(self, x, y, w, h, titulo, simbolo=None, color="pluz"):
        self.partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{FONDO}" '
                           f'stroke="{COLOR[color]}" stroke-width="1.6" stroke-dasharray="7 5"/>')
        tx = x + 14
        if simbolo:
            self.icono(x + 26, y + 22, simbolo, color, tam=28)
            tx = x + 48
        self.partes.append(f'<text x="{tx}" y="{y + 27}" font-size="13" font-weight="700" fill="{COLOR[color]}">{titulo}</text>')

    def flecha(self, puntos, etiqueta=None, punteada=False, dx=0, dy=-7):
        d = "M" + " L".join(f"{x},{y}" for x, y in puntos)
        trazo = ' stroke-dasharray="6 4"' if punteada else ""
        self.partes.append(f'<path d="{d}" fill="none" stroke="{GRIS}" stroke-width="1.7"{trazo} marker-end="url(#punta)"/>')
        if etiqueta:
            i = len(puntos) // 2
            (x1, y1), (x2, y2) = puntos[i - 1], puntos[i]
            x, y = (x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy
            ancho = 6.4 * len(etiqueta) + 10
            self.partes.append(f'<rect x="{x - ancho / 2}" y="{y - 12}" width="{ancho}" height="17" rx="4" fill="#fff"/>'
                               f'<text x="{x}" y="{y + 1}" font-size="11" fill="{GRIS}" text-anchor="middle">{etiqueta}</text>')

    def guardar(self, nombre):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
               f'height="{self.h}" font-family="Arial, Helvetica, sans-serif">'
               f'<defs><marker id="punta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
               f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GRIS}"/></marker></defs>'
               + "".join(self.partes) + "</svg>")
        (AQUI / nombre).write_text(svg, encoding="utf-8")
        print("Escrito", AQUI / nombre)


def en_las_instalaciones():
    c = Lienzo(1340, 790, "Propuesta 1. En las instalaciones de Pluz",
               "Lote semanal, un modelo estable que se monitorea cada semana, una base PostgreSQL y la página dentro de la red")
    W = 196
    c.tarjeta(28, 96, W, "Áreas de Pluz", ["Excel semanal de interrupciones,", "poda, guía y ranking"],
              iconos=[("personas", "personas"), ("hoja", "excel")])
    c.tarjeta(252, 96, W, "Carpeta compartida", ["OneDrive, SharePoint o red;", "una carpeta por lote"],
              iconos=[("carpeta", "nube_ms")])
    c.tarjeta(476, 96, W, "Programador de tareas", ["de Windows, cada lunes", "a primera hora"],
              iconos=[("calendario", "windows")])
    c.flecha([(224, 152), (250, 152)])
    c.flecha([(448, 152), (474, 152)])
    c.flecha([(672, 152), (708, 152)])

    c.grupo(710, 86, 602, 474, "Pipeline en Python, en un servidor de Pluz", "codigo", "python")
    G = 182
    c.tarjeta(726, 126, G, "Validar el lote", ["contrato de archivos", "y columnas"], iconos=[("verificar", "pluz")], numero=1)
    c.tarjeta(920, 126, G, "Base analítica", ["alimentador y mes,", "con sus variables"], iconos=[("tabla", "pluz")], numero=2)
    c.tarjeta(1114, 126, G, "Inferencia semanal", ["riesgo a 3 meses con", "el modelo vigente"], iconos=[("rayo", "pluz")], numero=3)
    c.tarjeta(726, 270, G, "Monitoreo y calibración", ["meses nuevos frente a", "la regla por historial"],
              iconos=[("medidor", "pluz")], numero=4)
    c.tarjeta(920, 270, G, "Índice por distrito", ["dos niveles y plan", "del trimestre"], iconos=[("ranking", "pluz")], numero=5)
    c.tarjeta(1114, 270, G, "MLflow", ["seguimiento semanal", "y benchmark"], iconos=[("tendencia", "mlflow")])
    c.tarjeta(920, 414, 376, "Salidas", ["datos de la página, plan en Excel", "y reporte de la corrida"],
              iconos=[("documento", "pluz")], numero=6)
    c.tarjeta(726, 414, G, "Reentrenar", ["solo si el monitoreo", "lo recomienda"], iconos=[("red_neuronal", "python")],
              discontinua=True)
    c.flecha([(908, 172), (918, 172)])
    c.flecha([(1102, 172), (1112, 172)])
    c.flecha([(1205, 252), (1205, 262), (817, 262), (817, 268)])
    c.flecha([(908, 318), (918, 318)])
    c.flecha([(1102, 318), (1112, 318)])
    c.flecha([(1011, 396), (1011, 412)])
    c.flecha([(817, 396), (817, 412)], punteada=True)

    c.tarjeta(710, 600, 602, "PostgreSQL con PostGIS",
              ["Se reemplazan: interrupciones, poda, guía, ranking y base analítica.",
               "Se acumulan: predicciones, índice y corridas, el historial para medir aciertos.",
               "Alternativa equivalente: SQL Server Express."],
              iconos=[("cilindro", "postgres")])
    c.flecha([(1180, 524), (1180, 598)], "escribe", dx=30)

    c.tarjeta(28, 600, W, "Página interna", ["la misma herramienta, en", "IIS, nginx o SharePoint"],
              iconos=[("navegador", "pluz")], alto=126)
    c.tarjeta(252, 600, W, "Plan en Excel", ["para programar las", "cuadrillas del mes"],
              iconos=[("hoja", "excel")], alto=126)
    c.tarjeta(476, 600, W, "Excel y Power BI", ["conectados a la base", "para cruzar planillas"],
              iconos=[("barras", "powerbi"), ("hoja", "excel")], alto=126)
    c.flecha([(708, 663), (674, 663)])
    c.flecha([(1000, 524), (1000, 572), (126, 572), (126, 598)], "publica")
    c.flecha([(980, 524), (980, 582), (350, 582), (350, 598)])
    c.guardar("arquitectura_en_las_instalaciones.svg")


def en_aws():
    c = Lienzo(1400, 920, "Propuesta 2. En AWS",
               "Mismo flujo con piezas administradas: sin servidores encendidos, inferencia semanal y reentrenamiento solo a pedido")
    W = 204
    c.tarjeta(28, 96, W, "Áreas de Pluz", ["Excel y CSV semanales"], iconos=[("personas", "personas"), ("hoja", "excel")])
    c.tarjeta(262, 96, W, "Página de carga", ["enlace firmado de S3,", "acceso con Cognito"],
              iconos=[("cargar", "pluz"), ("usuario", "seguridad")])
    c.tarjeta(496, 96, W, "S3, zona cruda", ["archivos tal como llegan,", "versionados por lote"], iconos=[("balde", "almacenamiento")])
    c.tarjeta(730, 96, W, "EventBridge", ["llegada de un archivo o", "calendario de cada lunes"], iconos=[("bus", "integracion")])
    c.flecha([(232, 152), (260, 152)])
    c.flecha([(466, 152), (494, 152)])
    c.flecha([(700, 152), (728, 152)])
    c.flecha([(934, 152), (1000, 152), (1000, 262)], "inicia")

    c.grupo(28, 264, 1344, 420, "AWS Step Functions orquesta cada corrida y se detiene si algo falla", "flujo", "integracion")
    G, y1, y2 = 206, 308, 480
    xs = [48, 270, 492, 714, 936, 1158]
    c.tarjeta(xs[0], y1, G, "Validar y convertir", ["Lambda: contrato de datos,", "de Excel a Parquet"],
              iconos=[("lambda", "computo")], numero=1)
    c.tarjeta(xs[1], y1, G, "S3 curada y Glue", ["Parquet por fuente y lote,", "catálogo de datos"],
              iconos=[("balde", "almacenamiento"), ("catalogo", "analitica")], numero=2)
    c.tarjeta(xs[2], y1, G, "Tabla de variables", ["Athena; la calcula el mismo", "código en Processing"],
              iconos=[("lupa_tabla", "analitica")], numero=3)
    c.tarjeta(xs[3], y1, G, "Inferencia semanal", ["SageMaker Batch Transform", "con el modelo aprobado"],
              iconos=[("red_neuronal", "aprendizaje")], numero=4)
    c.tarjeta(xs[4], y1, G, "Tabla de inferencia", ["Athena: probabilidad por", "alimentador y corte"],
              iconos=[("lupa_tabla", "analitica")], numero=5)
    c.tarjeta(xs[5], y1, G, "Índice y salidas", ["Lambda: índice por distrito,", "plan en Excel y reporte"],
              iconos=[("lambda", "computo")], numero=6)
    for a, b in zip(xs, xs[1:]):
        c.flecha([(a + G, y1 + 52), (b - 2, y1 + 52)])

    c.tarjeta(xs[3], y2, G, "Monitoreo y calibración", ["Model Monitor frente a la", "regla; recalibra si hace falta"],
              iconos=[("medidor", "aprendizaje")], numero=7)
    c.tarjeta(xs[1], y2, 428, "Reentrenamiento a pedido", ["SageMaker Training con benchmark; Model Registry", "aprueba solo si pasa el freno; MLflow administrado"],
              iconos=[("red_neuronal", "aprendizaje"), ("etiqueta", "aprendizaje"), ("tendencia", "mlflow")],
              discontinua=True)
    c.tarjeta(xs[5], y2, G, "Avisos", ["SNS envía el reporte;", "CloudWatch alerta fallas"],
              iconos=[("campana", "integracion"), ("medidor", "integracion")])
    c.flecha([(xs[3] + G / 2, y1 + 126), (xs[3] + G / 2, y2 - 2)])
    c.flecha([(xs[3] - 2, y2 + 52), (xs[1] + 430, y2 + 52)], punteada=True)
    c.partes.append(f'<text x="{xs[3] - 16}" y="{y2 + 76}" font-size="11" fill="{GRIS}" text-anchor="end">solo si lo pide</text>')
    c.flecha([(xs[1] + 214, y2 - 2), (xs[1] + 214, y2 - 20), (xs[3] + 40, y2 - 20), (xs[3] + 40, y1 + 128)],
             "modelo aprobado", punteada=True, dy=-8)
    c.flecha([(xs[5] + G / 2, y1 + 126), (xs[5] + G / 2, y2 - 2)])

    y3 = 730
    c.tarjeta(28, y3, 420, "Seguridad y costo", ["buckets privados con KMS, IAM mínimo y CloudTrail;",
                                                  "sin endpoints encendidos: se paga por minuto de corrida"],
              iconos=[("escudo", "seguridad")], alto=140)
    c.tarjeta(494, y3, 400, "La página", ["S3 y CloudFront, con acceso por Cognito", "o limitado a las IP de Pluz"],
              iconos=[("balde", "almacenamiento"), ("globo", "analitica"), ("usuario", "seguridad")], alto=140)
    c.tarjeta(940, y3, 432, "Consumo", ["Subgerencia: página y plan en Excel;", "analistas: Athena desde Excel o Power BI"],
              iconos=[("personas", "personas"), ("hoja", "excel"), ("barras", "powerbi")], alto=140)
    c.flecha([(xs[5] + G, y1 + 90), (1388, y1 + 90), (1388, 706), (694, 706), (694, y3 - 2)])
    c.partes.append(f'<rect x="1000" y="693" width="60" height="17" rx="4" fill="#fff"/>'
                    f'<text x="1030" y="706" font-size="11" fill="{GRIS}" text-anchor="middle">publica</text>')
    c.flecha([(894, y3 + 70), (938, y3 + 70)])
    c.guardar("arquitectura_aws.svg")


if __name__ == "__main__":
    en_las_instalaciones()
    en_aws()
