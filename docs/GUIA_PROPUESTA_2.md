# Guía de la propuesta 2: operación en AWS

Paso a paso para montar en AWS el mismo flujo de la propuesta 1 y cómo se operaría cada semana. El diseño y su comparación con la propuesta 1 están en ARQUITECTURA.md.

Esta propuesta **no está construida**: es el plan de implementación. Lo que sí está listo es el código que cada pieza reutiliza, el del pipeline de este repositorio, de modo que el trabajo consiste en empaquetarlo y conectarlo, no en reescribirlo.


## 1. Qué se necesita

* Una cuenta de AWS de Pluz, con la aprobación de su área de sistemas y de su política de datos. AWS no tiene una región en el Perú: los datos quedarían en la región de São Paulo o en Norte de Virginia.
* Una persona con permisos de administración para crear los recursos la primera vez.
* Docker en el equipo de quien construye las imágenes, para empaquetar el pipeline.
* De preferencia, todo descrito como infraestructura como código, con CloudFormation o Terraform, para poder crearlo, revisarlo y reproducirlo sin pasos manuales.


## 2. Construcción, una sola vez

### 2.1 Almacenamiento

1. **Tres buckets de S3**, privados, con cifrado KMS y versionado activado:
   * **Zona cruda.** Recibe los Excel y CSV tal como llegan, en una carpeta por lote con la fecha, AAAAMMDD. El versionado permite reconstruir cualquier corrida.
   * **Zona curada.** Guarda el Parquet validado, particionado por fuente y por lote, y las tablas de variables, inferencia, índice y corridas.
   * **Sitio.** Guarda la página: index.html, css, js, assets y la carpeta data.
2. **Una base de datos en el catálogo de AWS Glue**, por ejemplo pluz_vegetacion, donde se registran las tablas de la zona curada para que Athena las consulte.

### 2.2 Empaquetar el pipeline

1. **Una imagen de contenedor** con el contenido de la carpeta pipeline y las bibliotecas de pipeline/requirements.txt, publicada en Amazon ECR. La misma imagen sirve para Lambda y para los trabajos de SageMaker; solo cambia qué función se llama.
2. Correspondencia entre el código actual y cada pieza:
   * Validar y convertir usa etapas/fuentes.py.
   * La tabla de variables usa etapas/base_analitica.py.
   * La inferencia, el monitoreo y la recalibración usan etapas/modelo.py.
   * El reentrenamiento y el benchmark usan etapas/modelo.py y etapas/benchmark.py.
   * El índice y las salidas usan etapas/indice.py y etapas/salidas.py.

### 2.3 Las etapas

1. **Lambda de validación y conversión.** Lee el lote nuevo de la zona cruda, valida el contrato de datos con las mismas reglas de config.py y escribe cada fuente en Parquet en la zona curada. Si el lote no cumple, falla con el mismo mensaje que hoy da la orden validar.
2. **Trabajo de SageMaker Processing para la tabla de variables.** Corre la base analítica y escribe la tabla de variables por alimentador y mes en la zona curada, registrada en Glue. Athena la consulta como una tabla más.
3. **Modelo vigente en SageMaker Model Registry.** Se registra el modelo actual, el mismo que hoy está en modelo_vigente.joblib, como versión aprobada.
4. **SageMaker Batch Transform para la inferencia semanal.** Predice el último corte con la versión aprobada y escribe la tabla de inferencia.
5. **Monitoreo y calibración.** Un trabajo de Processing, o SageMaker Model Monitor con las métricas de calidad del modelo, compara el modelo vigente con la regla por historial en los meses nuevos con resultado. Si la probabilidad se descalibró, guarda la recalibración. Si el ordenamiento cayó, publica un aviso.
6. **Lambda de índice y salidas.** Calcula el índice por distrito, escribe la carpeta data en el bucket del sitio, el plan en Excel en la zona curada y el reporte de la corrida.
7. **Reentrenamiento a pedido.** Un trabajo de SageMaker Training que corre el benchmark y el reentrenamiento. Solo se dispara cuando el monitoreo lo recomienda o cuando alguien lo pide. El modelo nuevo queda en Model Registry como pendiente y solo pasa a aprobado si supera el freno frente a la regla por historial. Las métricas van al MLflow administrado de SageMaker.

### 2.4 Orquestación

1. **Una máquina de estados de AWS Step Functions** con las etapas en orden: validar y convertir, tabla de variables, inferencia, monitoreo y calibración, índice y salidas. Cada estado reintenta dos veces ante un fallo transitorio y, si vuelve a fallar, detiene la corrida y avisa.
2. **Una regla de Amazon EventBridge** que inicia la máquina de estados los lunes a las 10:00 de Lima, que son las 15:00 en hora universal. La expresión es cron(0 15 ? * MON *). Se puede agregar una segunda regla que la inicie apenas llega un archivo a la zona cruda.
3. **Un tema de Amazon SNS** con los correos de la Subgerencia, que recibe el reporte al final de cada corrida, y **alarmas de CloudWatch** que avisan si una etapa falla.

### 2.5 Acceso

1. **La página**, servida desde el bucket del sitio con Amazon CloudFront, con acceso por Amazon Cognito o limitado a las direcciones IP de Pluz.
2. **Una página de carga** para el área, con enlaces firmados de S3, de modo que nadie de Pluz tenga que entrar a la consola de AWS para subir el Excel.
3. **Permisos de IAM mínimos** por servicio y **registro de CloudTrail** de todos los accesos.


## 3. La corrida de cada semana

Lo que hace la gente:

1. El área sube el Excel de la semana en la página de carga.
2. El lunes, la Subgerencia recibe el correo con el reporte y abre la página.

Lo que pasa solo:

1. EventBridge inicia la máquina de estados el lunes a las 10:00, o al llegar el archivo.
2. La Lambda valida el lote y lo convierte a Parquet. Si no cumple el contrato, la corrida se detiene y llega un aviso.
3. Processing actualiza la tabla de variables.
4. Batch Transform predice con el modelo aprobado.
5. El monitoreo compara el modelo con la regla en los meses nuevos y recalibra si hace falta.
6. La Lambda de salidas actualiza la página, el plan en Excel y el reporte.
7. SNS envía el reporte por correo.


## 4. Cuándo hay que intervenir

* **Llega un aviso de lote inválido.** Pluz cambió un archivo o una columna: se ajusta config.py, se reconstruye la imagen y se vuelve a correr.
* **El reporte recomienda reentrenar.** Alguien revisa qué cambió en los datos y lanza el trabajo de reentrenamiento. El modelo nuevo solo se aprueba si pasa el freno.
* **Una alarma de CloudWatch avisa de un fallo.** El detalle está en los registros de la ejecución de Step Functions.


## 5. Costo

No hay servidores ni endpoints encendidos: Lambda, Step Functions, Athena y los trabajos de SageMaker se pagan por uso. Con este volumen, la inferencia y el monitoreo de cada semana duran minutos, Athena consulta megabytes y el entrenamiento solo ocurre cuando el monitoreo lo pide, de modo que el costo mensual es bajo. Los cargos fijos son el almacenamiento en S3, centavos con este volumen, y CloudFront según las visitas a la página.
