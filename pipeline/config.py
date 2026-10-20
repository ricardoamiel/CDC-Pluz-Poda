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

# Modo demostración. Con la variable PLUZ_DEMO apuntando a una carpeta, el pipeline trabaja
# solo dentro de ella: sus propios lotes, sus salidas, su página y su carpeta de entrada.
# Así se puede mostrar el flujo semanal sin tocar los datos reales ni la página publicada.
# La carpeta la prepara pipeline/demo/preparar_demo.py.
DEMO = os.environ.get("PLUZ_DEMO", "")
if DEMO:
    _demo = Path(DEMO)
    LOTES, SALIDAS, DATA_WEB = _demo / "lotes", _demo / "salidas", _demo / "web" / "data"

# Base de datos opcional. Vacía, el pipeline no la usa. Se puede fijar aquí o con la
# variable de entorno PLUZ_BASE_DE_DATOS, que es lo recomendable para no dejar la clave en
# el código. Ejemplos:
#   sqlite:///pipeline/salidas/pluz.db
#   postgresql://usuario:clave@servidor:5432/pluz
BASE_DE_DATOS = os.environ.get("PLUZ_BASE_DE_DATOS", "")

# Operación en las instalaciones de Pluz (propuesta 1). Las dos carpetas son opcionales y se
# fijan con variables de entorno para no escribir rutas de un equipo en el código.
# CARPETA_ENTRADA: carpeta compartida donde el área deja el Excel de cada semana. La orden
#   recibir copia lo que haya ahí a un lote nuevo y mueve los originales a procesados.
# CARPETA_WEB: carpeta que sirve el servidor web interno. La orden semanal copia ahí la
#   página con sus datos nuevos al terminar.
CARPETA_ENTRADA = os.environ.get("PLUZ_CARPETA_ENTRADA", "") or (str(Path(DEMO) / "entrada") if DEMO else "")
CARPETA_WEB = os.environ.get("PLUZ_CARPETA_WEB", "")
EXTENSIONES_LOTE = (".xlsx", ".xls", ".csv")

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
    "postes_mt": {
        # Postes de media tensión con coordenadas. No traen alimentador ni subestación, y las
        # interrupciones no registran el poste, así que no entran al modelo: sirven para
        # ubicar en la calle la unidad elegida y para buscar por código de poste.
        "patrones": ["*postes*mt*.xlsx"],
        "hoja": 0,
        "encabezado": "auto",
        "columnas": ["CÓDIGO DE POSTE", "STRUCTURE NODE LONGITUD\nX",
                     "STRUCTURE NODE LATITUD\nY", "DISTRITO"],
        "modo": "foto",
        "obligatoria": False,
    },
}

# Un poste se asigna a la subestación aérea más cercana si está a menos de esta distancia.
# Más lejos, se muestra en el mapa pero sin subestación.
DISTANCIA_POSTE_SED_M = 400

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

# Modelo alternativo que la página permite comparar con el vigente: XGBoost, con los
# hiperparámetros que eligió el benchmark en la validación interna. Se entrena junto con el
# vigente y con los mismos datos; no reemplaza al vigente, sirve para ver cuánto cambiaría el
# ranking con un modelo más complejo.
MODELO_ALTERNO = {"nombre": "XGBoost", "max_depth": 3, "min_child_weight": 20,
                  "n_estimators": 49, "learning_rate": 0.05}

# Monitoreo del modelo vigente. El modelo no se reentrena por calendario: se mide cada semana
# en los meses que ya tienen su ventana completa y que no vio al entrenarse.
MESES_MINIMOS_MONITOREO = 3      # meses nuevos necesarios para decidir algo
BANDA_CALIBRACION = (0.8, 1.25)  # frecuencia observada sobre probabilidad media aceptable
EVENTOS_MINIMOS_CALIBRACION = 50 # eventos necesarios para recalibrar con confianza
MARGEN_PR_AUC = 0.03             # caída de PR AUC frente a la regla que pide reentrenar
MARGEN_COBERTURA = 0.10          # caída de cobertura con lista de 40 que pide reentrenar
SEMILLA = 20261005

# Acuerdos de la reunión N°3: la probabilidad no usa ninguna de las tres variables que el
# índice ya cuenta por su lado (reloj de poda, SAIDI y exposición por clientes y potencia),
# para no contar dos veces el mismo criterio. Sí usa el número de interrupciones del
# alimentador, que Pluz pidió como indicador principal. Los meses desde la última poda
# salieron en la segunda revisión; en la fase 4 su aporte incremental ya era nulo.
VARIABLES = ["log_veg_hist", "log_veg_12m", "log_eventos_12m", "mes_sin", "mes_cos"]

# Variables del índice que no pueden entrar al modelo. El benchmark comprueba que ninguna
# esté en VARIABLES y mide su correlación con las que sí están.
VARIABLES_DEL_INDICE = ["meses_sin_poda", "saidi_ltm", "clientes", "kva"]
NOMBRES_VARIABLES = {
    "log_veg_hist": "Historial acumulado de vegetación",
    "log_veg_12m": "Eventos de vegetación, 12 meses",
    "log_eventos_12m": "Interrupciones totales, 12 meses",
    "mes_sin": "Ciclo anual, seno",
    "mes_cos": "Ciclo anual, coseno",
}
# Nombres de las variables candidatas que evalúa la ablación del benchmark.
NOMBRES_CANDIDATAS = {
    "meses_desde_veg": "Meses desde el último evento de vegetación",
    "sin_evento_previo": "Sin evento previo de vegetación",
    "log_veg_3m": "Eventos de vegetación, 3 meses",
    "log_eventos_3m": "Interrupciones totales, 3 meses",
}

# El punto de operación del modelo es cuántos alimentadores se marcan en alerta cada mes.
# Se elige en la validación interna: el menor número de alertas que alcanza esta fracción
# del F2 máximo. Pasado ese punto, cada alerta adicional agrega casi solo falsos positivos.
FRACCION_F2_MAXIMO = 0.99

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
