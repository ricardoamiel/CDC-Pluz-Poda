# Literatura que respalda el método

Pluz pidió en la reunión N°3 reforzar el sustento de la metodología: los criterios, las variables y las ponderaciones del índice de criticidad, y si están respaldados por literatura técnica, referencias académicas o modelos previos. Esta carpeta reúne esa literatura y, para cada decisión del proyecto, dice qué fuente la respalda y qué tomamos de ella.

Los PDF de acceso abierto se guardan en esta carpeta solo en el equipo local: el repositorio es público y varias licencias no permiten redistribuirlos. Aquí queda la referencia completa con su enlace, de modo que cualquiera puede descargarlos.


## Decisiones del proyecto y su respaldo

### 1. Predecir por alimentador y por mes a partir del historial de cortes

El modelo estima, para cada alimentador y cada mes, la probabilidad de al menos un corte por vegetación en los tres meses siguientes, con el historial de vegetación, las interrupciones del último año y la estacionalidad.

* **Doostan, Sohrabi y Chowdhury (2019).** Predicen el número mensual de cortes por vegetación de una distribuidora de Estados Unidos con sus registros de cortes, y separan los cortes por crecimiento de los cortes por clima. Respaldan la unidad mensual, el uso del historial de cortes como insumo principal y la estacionalidad. Archivo 01.
* **Melagoda y otros (2021).** Estiman la probabilidad de un corte por vegetación en un horizonte fijo, de catorce días, y con ella dibujan un mapa de riesgo de los alimentadores. Es el mismo planteamiento del proyecto: una probabilidad en un horizonte que se lleva a un mapa para priorizar.
* **Radmer, Kuntz, Christie, Venkata y Fletcher (2002).** Trabajo clásico sobre la predicción de tasas de falla por vegetación en alimentadores aéreos de distribución. Confirma que el alimentador es la unidad habitual de este análisis.

### 2. Agrupar vegetación y no ubicadas en red aérea

El piloto cuenta como evento probable de vegetación el crecimiento de árbol, la tala de árbol y la causa no ubicada en red aérea, como confirmó Pluz en la reunión N°3.

* **Doostan, Sohrabi y Chowdhury (2019).** Distinguen los cortes por crecimiento de los ocasionados por clima, porque responden a causas distintas. En nuestros datos la causa no ubicada en red aérea es la mayor parte de los eventos agrupados (1.110 de 1.328), y el diccionario de causas de Pluz la define como una falla transitoria cuyo origen no se encontró en la inspección, que es el comportamiento típico de un contacto con ramas. Archivo 01.

### 3. Reloj de poda: el tiempo desde la última poda importa

El índice incluye los meses desde la última poda registrada del alimentador.

* **Guikema, Davidson y Liu (2006).** Con datos de Duke Power y modelos lineales generalizados (binomial negativo y mixto de Poisson) encuentran un efecto significativo de la poda sobre los cortes en condiciones normales de operación.
* **Pan (2021).** Con cinco años de cortes y el historial de mantenimiento de vegetación de una distribuidora del medio oeste de Estados Unidos, ajusta modelos de conteo y concluye que el efecto de la poda depende del tiempo transcurrido, con un ciclo óptimo cercano a seis años en ese caso. Archivo 03.

### 4. Índice de criticidad: probabilidad por consecuencia y un plan con capacidad fija

El índice suma la probabilidad del modelo (peso 0,40) y tres componentes de consecuencia y exposición: reloj de poda, SAIDI del último año y exposición por clientes y potencia (0,20 cada uno). El plan toma las unidades de mayor índice hasta la capacidad de las cuadrillas.

* **Dokic y Kezunovic (2019).** Calculan un estado de riesgo por sección de alimentador como el producto de la probabilidad de la amenaza por la vulnerabilidad de la red, tratan el impacto económico por separado y arman un programa de poda que minimiza el riesgo total con un presupuesto fijo. Es la misma lógica del índice: probabilidad de que ocurra, combinada con cuánto afecta, para priorizar con una capacidad dada. Archivo 02.
* **Arunraj y Maiti (2007).** Revisión del mantenimiento basado en riesgo: priorizar las intervenciones por la combinación de probabilidad de falla y consecuencia, en lugar de un calendario fijo. Es el marco del lema del proyecto: de podar por calendario a podar por riesgo.
* **Correa Tamayo, Arias Londoño y Granada Echeverri (2019).** Modelo de gestión óptima de la poda en redes aéreas de distribución de Colombia: decide cuándo, dónde y con qué cuadrillas podar, con la capacidad de las cuadrillas y las metas regulatorias de confiabilidad como restricciones. Es un antecedente latinoamericano del mismo problema. Archivo 04.

### 5. Normalizar cada componente como percentil dentro del distrito

Cada componente del índice se convierte en percentil dentro del distrito antes de ponderar.

* **OCDE y Centro Común de Investigación de la Comisión Europea (2008).** Manual de referencia para construir indicadores compuestos. Presenta la normalización por posición como la más simple y no afectada por valores extremos, con la advertencia de que pierde los niveles absolutos. Por eso el índice ordena dentro del distrito y la pestaña Comparar distritos muestra aparte las cifras absolutas. El mismo manual recomienda analizar la sensibilidad del ranking a las decisiones del método, que es lo que hace la comparación entre el modelo vigente y el de contraste. Archivo 06.
* **Spearman (1904).** Correlación de orden, la medida que usamos para decir cuánto cambia el ranking entre modelos (0,96 por alimentador y 0,98 por subestación).

### 6. SAIDI como medida de consecuencia

* **IEEE 1366 (2012).** Guía de índices de confiabilidad de distribución: define el SAIDI como la duración total de las interrupciones de los clientes dividida entre los clientes atendidos.
* **Norma Técnica de Calidad de los Servicios Eléctricos, Decreto Supremo N° 020-97-EM, y su supervisión por Osinergmin.** Marco peruano de calidad de suministro que da peso regulatorio a la duración y la frecuencia de las interrupciones.

### 7. Métrica de decisión: área bajo la curva de precisión y exhaustividad

Los eventos son poco frecuentes frente a los meses sin evento, y el modelo se usa para ordenar una lista.

* **Saito y Rehmsmeier (2015).** Muestran que con clases desbalanceadas la curva de precisión y exhaustividad informa mejor que la curva ROC, porque la especificidad se ve alta solo por la abundancia de negativos. Respalda elegir el PR AUC como métrica que decide el benchmark. Archivo 05.
* **Van Rijsbergen (1979).** Origen de la medida F con peso, de la que sale el F2 usado para fijar el punto de operación en 270 alertas por mes, porque un corte no previsto cuesta más que una poda adelantada.

### 8. Validación temporal

* **Cerqueira, Torgo y Mozetič (2020).** Comparan formas de estimar el desempeño en series de tiempo y encuentran que, con series no estacionarias, la validación fuera de muestra que respeta el orden del tiempo es la más confiable. Respalda entrenar con el pasado y probar en los meses siguientes, de enero a mayo de 2026, con un mes de separación. Archivo 09.

### 9. Probabilidades calibradas

El índice suma la probabilidad con otros componentes, así que tiene que significar lo que dice: un 30 % debe ser 30 de cada 100.

* **Niculescu Mizil y Caruana (2005).** Comparan qué tan bien calibrados salen distintos algoritmos y proponen corregirlos con escalado de Platt o regresión isotónica. Respalda la recalibración del modelo vigente sin cambiar su orden.
* **Brier (1950).** Puntaje de Brier, la medida de calibración que reportamos (0,122).

### 10. Modelos comparados en el benchmark

* **Hosmer, Lemeshow y Sturdivant (2013).** Regresión logística aplicada: el modelo vigente, elegido por simple, calibrado y explicable.
* **Breiman (2001).** Random Forest.
* **Chen y Guestrin (2016).** XGBoost, el modelo de contraste de la herramienta. Archivo 07.
* **Ke y otros (2017).** LightGBM. Archivo 08.
* **Cortes y Vapnik (1995).** Máquinas de vectores de soporte.


## Referencias

* Arunraj, N. S. y Maiti, J. (2007). Risk based maintenance: techniques and applications. Journal of Hazardous Materials, 142(3), 653 a 661.
* Breiman, L. (2001). Random forests. Machine Learning, 45, 5 a 32. https://doi.org/10.1023/A:1010933404324
* Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. Monthly Weather Review, 78(1), 1 a 3.
* Cerqueira, V., Torgo, L. y Mozetič, I. (2020). Evaluating time series forecasting models: an empirical study on performance estimation methods. Machine Learning, 109. https://doi.org/10.1007/s10994-020-05910-7 Versión abierta: https://arxiv.org/abs/1905.11744
* Chen, T. y Guestrin, C. (2016). XGBoost: a scalable tree boosting system. Proceedings of the 22nd ACM SIGKDD Conference. https://arxiv.org/abs/1603.02754
* Correa Tamayo, J. S., Arias Londoño, A. y Granada Echeverri, M. (2019). Optimal management of vegetation maintenance and the associated costs of its implementation in overhead power distribution systems. TecnoLógicas, 22(45), 91 a 107. https://doi.org/10.22430/22565337.1173
* Cortes, C. y Vapnik, V. (1995). Support vector networks. Machine Learning, 20, 273 a 297.
* Dokic, T. y Kezunovic, M. (2019). Predictive risk management for dynamic tree trimming scheduling for distribution networks. IEEE Transactions on Smart Grid, 10(5), 4776 a 4785. https://doi.org/10.1109/TSG.2018.2868457
* Doostan, M., Sohrabi, R. y Chowdhury, B. (2019). A data driven approach for predicting vegetation related outages in power distribution systems. https://arxiv.org/abs/1807.06180
* Guikema, S. D., Davidson, R. A. y Liu, H. (2006). Statistical models of the effects of tree trimming on power system outages. IEEE Transactions on Power Delivery, 21(3), 1549 a 1557. https://doi.org/10.1109/TPWRD.2005.860238
* Hosmer, D. W., Lemeshow, S. y Sturdivant, R. X. (2013). Applied Logistic Regression, tercera edición. Wiley.
* IEEE (2012). IEEE Std 1366: IEEE Guide for Electric Power Distribution Reliability Indices.
* Ke, G. y otros (2017). LightGBM: a highly efficient gradient boosting decision tree. Advances in Neural Information Processing Systems 30. https://proceedings.neurips.cc/paper/2017/file/6449f44a102fde848669bdd9eb6b76fa-Paper.pdf
* Melagoda, A. U., Karunarathna, T. D. L. P., Nisaharan, G., Amarasinghe, P. A. G. M. y Abeygunawardane, S. K. (2021). Application of machine learning algorithms for predicting vegetation related outages in power distribution systems. 3rd International Conference on Electrical Engineering, IEEE, 31 a 36. https://dl.lib.uom.lk/items/5726ff57-0d23-4d0d-a98b-2abd153526b6
* Niculescu Mizil, A. y Caruana, R. (2005). Predicting good probabilities with supervised learning. Proceedings of the 22nd International Conference on Machine Learning, 625 a 632. https://doi.org/10.1145/1102351.1102430
* OCDE y Centro Común de Investigación (2008). Handbook on Constructing Composite Indicators: Methodology and User Guide. OECD Publishing. https://knowledge4policy.ec.europa.eu/sites/default/files/jrc47008_handbook_final.pdf
* Pan, J. (2021). Statistical modeling for the effects of vegetative growth on power distribution system reliability. Frontiers in Applied Mathematics and Statistics, 7, 769355. https://doi.org/10.3389/fams.2021.769355
* Radmer, D. T., Kuntz, P. A., Christie, R. D., Venkata, S. S. y Fletcher, R. H. (2002). Predicting vegetation related failure rates for overhead distribution feeders. IEEE Transactions on Power Delivery, 17(4), 1170 a 1175. https://doi.org/10.1109/TPWRD.2002.804006
* Saito, T. y Rehmsmeier, M. (2015). The precision recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. PLOS ONE, 10(3), e0118432. https://doi.org/10.1371/journal.pone.0118432
* Spearman, C. (1904). The proof and measurement of association between two things. American Journal of Psychology, 15(1), 72 a 101.
* Van Rijsbergen, C. J. (1979). Information Retrieval, segunda edición. Butterworths.


## Archivos de esta carpeta

* 01. Doostan, Sohrabi y Chowdhury (2019), versión de arXiv.
* 02. Dokic y Kezunovic (2019), versión aceptada que publica el autor.
* 03. Pan (2021), Frontiers, acceso abierto.
* 04. Correa Tamayo y otros (2019), TecnoLógicas, licencia Creative Commons.
* 05. Saito y Rehmsmeier (2015), PLOS ONE, acceso abierto.
* 06. OCDE y Centro Común de Investigación (2008).
* 07. Chen y Guestrin (2016), versión de arXiv.
* 08. Ke y otros (2017), actas de NeurIPS.
* 09. Cerqueira y otros (2020), versión de arXiv.
