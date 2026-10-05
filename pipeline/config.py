# -*- coding: utf-8 -*-
"""Configuración del pipeline. Todo lo que puede cambiar sin tocar la lógica vive aquí.

Las rutas son relativas a este archivo, de modo que el pipeline funciona igual en
cualquier equipo que clone el repositorio.
"""
import os
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
REPO = PIPELINE.parent

# Entrada: cada lote que envía Pluz va en su propia carpeta dentro de LOTES, con nombre
# que empiece por la fecha de recepción (AAAAMMDD_descripcion). El orden alfabético de
# las carpetas es el orden cronológico, y el lote más reciente manda.
LOTES = PIPELINE / "datos" / "lotes"

# Salidas técnicas, que no se publican: base analítica, predicción, modelo y reporte.
SALIDAS = PIPELINE / "salidas"

# Salida pública: lo que carga la página.
DATA_WEB = REPO / "data"

# Referencias fijas que sí se versionan: límites de distritos de OpenStreetMap.
REFERENCIA = PIPELINE / "referencia"

# Base de datos opcional. Vacía, el pipeline no la usa. Se puede fijar aquí o con la
# variable de entorno PLUZ_BASE_DE_DATOS, que es lo recomendable para no dejar la clave en
# el código. Ejemplos:
#   sqlite:///pipeline/salidas/pluz.db
#   postgresql://usuario:clave@servidor:5432/pluz
BASE_DE_DATOS = os.environ.get("PLUZ_BASE_DE_DATOS", "")

# Fuentes
# Cada fuente se reconoce por un patrón de nombre de archivo, sin distinguir mayúsculas ni
# tildes, y declara las columnas que tiene que traer. Si un lote trae un archivo con otro
# nombre, basta con ajustar el patrón; si trae otras columnas, la validación lo detiene
# antes de calcular nada.
#
# modo "historico": se juntan todos los lotes, y el archivo más reciente manda sobre el
#                   periodo que cubre. Sirve igual si Pluz manda el histórico completo
#                   cada semana o solo lo nuevo.
# modo "foto":      solo vale el archivo más reciente (catálogos y rankings).
FUENTES = {
    "interrupciones": {
        "patrones": ["*interrupciones*diarias*.xlsx"],
        "hoja": "Falla_Alim",
        "columnas": ["Referencia", "Inicio", "Alimentador", "Causa", "Localización",
                     "SAIDI", "N° Clientes"],
        "fecha": "Inicio",
        "modo": "historico",
        "obligatoria": True,
    },
    "poda": {
        # Formato unificado: una hoja por contratista con fecha, alimentador y circuito.
        "patrones": ["*poda*formato*unificado*.xlsx"],
        "hoja": None,   # todas las hojas
        "columnas": ["FECHA", "ALIMENTADOR", "CIRCUITO", "DIRECCION DE TRABAJO"],
        "fecha": "FECHA",
        "modo": "historico",
        "obligatoria": True,
    },
    "ranking_saidi": {
        "patrones": ["*ranking*saidi*.xlsx"],
        "hoja": "Evolutivo SAIDI",
        "encabezado": 3,
        "columnas": ["Alimentador", "SAIDI LTM"],
        "modo": "foto",
        "obligatoria": True,
    },
    "guia_sed": {
        "patrones": ["guia*.xlsx"],
        "hoja": 0,
        "encabezado": "auto",   # la fila de títulos cambia entre versiones
        "columnas": ["SED", "ALIM", "KVA", "Clientes BT Cantidad Referencial", "DIRECCION",
                     "DISTRITO", "TIPO DE CONSTRUCCIÓN", "UTM\nX LONG", "UTM\nY LAT"],
        "modo": "foto",
        "obligatoria": True,
    },
    "diccionario_causas": {
        "patrones": ["*diccionario*causas*.xlsx"],
        "hoja": 0,
        "encabezado": 2,
        "columnas": ["Causa (según la base)"],
        "modo": "foto",
        "obligatoria": False,   # solo se usa para avisar de causas nuevas
    },
}

# Modelo
CAUSAS_VEGETACION = ["Crecimiento de árbol", "Tala de árbol"]
# Acuerdo de la reunión N°2: la causa no ubicada en red aérea cuenta como interferencia
# probable de vegetación.
CAUSA_NO_UBICADA = "No ubicada"
LOCALIZACION_AEREA = "Red aérea"

HORIZONTE_MESES = 3
CENSURA_PODA = 24.0
MESES_HISTORIA = 12          # meses de historia que necesita la primera ventana móvil
MESES_PRUEBA = 5             # cortes finales reservados para medir fuera de muestra
MESES_EMBARGO = 3            # separación entre entrenamiento y prueba
C_REGULARIZACION = 0.05      # elegido en la fase 4 con validación de origen móvil
SEMILLA = 20261005

# Acuerdo de la reunión N°3: sin SAIDI ni clientes dentro de la probabilidad, porque los
# dos ya entran al índice como componentes propios.
VARIABLES = ["log_veg_hist", "log_veg_12m", "meses_sin_poda", "log_eventos_12m",
             "mes_sin", "mes_cos"]
NOMBRES_VARIABLES = {
    "log_veg_hist": "Historial acumulado de vegetación",
    "log_veg_12m": "Eventos de vegetación, 12 meses",
    "meses_sin_poda": "Meses desde la última poda",
    "log_eventos_12m": "Interrupciones totales, 12 meses",
    "mes_sin": "Ciclo anual, seno",
    "mes_cos": "Ciclo anual, coseno",
}
MOTIVOS = {
    "log_veg_hist": "historial de eventos por vegetación",
    "log_veg_12m": "eventos por vegetación en el último año",
    "meses_sin_poda": "tiempo transcurrido sin poda",
    "log_eventos_12m": "alta frecuencia de interrupciones",
    "mes_sin": "época del año",
    "mes_cos": "época del año",
}

# Índice
PESOS = {"probabilidad": 0.40, "reloj_poda": 0.20, "criticidad": 0.20, "exposicion": 0.20}
COMPONENTES = [("c_probabilidad", "Probabilidad del alimentador"),
               ("c_reloj_poda", "Reloj de poda"),
               ("c_criticidad", "Criticidad por SAIDI"),
               ("c_exposicion", "Exposición")]

# Piloto primero: su capacidad de poda fija la proporción que se usa en los demás.
PILOTO = "LOS OLIVOS"
DISTRITOS = {
    "LOS OLIVOS": ("LOL", "Los Olivos", 1944759),
    "SAN JUAN DE LURIGANCHO": ("SJL", "San Juan de Lurigancho", 1944815),
    "CARABAYLLO": ("CAR", "Carabayllo", 1944701),
    "CALLAO": ("CLL", "Callao", 1944699),
    "PUENTE PIEDRA": ("PPI", "Puente Piedra", 1944788),
    "SAN MARTIN DE PORRES": ("SMP", "San Martín de Porres", 1944821),
    "VENTANILLA": ("VEN", "Ventanilla", 1944857),
    "COMAS": ("COM", "Comas", 1944720),
}
