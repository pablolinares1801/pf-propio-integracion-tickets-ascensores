# Runbook — despliegue por consola web de AWS (sin CLI)

Todo esto se hace clickeando en la consola de AWS dentro del Learner Lab,
región **us-east-1** (la única habilitada), con el rol **LabRole** ya
asignado por defecto. No hace falta CloudShell ni PowerShell para esta
parte — solo para verificar logs si algo falla (opcional).

Nombres acordados (usarlos tal cual para que coincidan con el código):
- Bucket S3: `pf-propio-integracion-784989636429`
- Función Lambda: `pf-propio-validador-tickets`
- Crawler de Glue: `pf-propio-crawler-validos`
- Base de datos de Glue: `pf_propio_tickets_db`

---

## 0. Antes de empezar

1. Iniciar el Learner Lab (botón **Start Lab**) y esperar el círculo verde.
2. Abrir **AWS Management Console** (botón naranja arriba a la izquierda del
   panel del lab).
3. Verificar arriba a la derecha que la región sea **N. Virginia (us-east-1)**.

---

## 1. Crear el bucket S3

1. Buscar **S3** en la barra de búsqueda de servicios → **Create bucket**.
2. Nombre: `pf-propio-integracion-784989636429` (los nombres de bucket son
   globales; si ya existe, agregar un sufijo propio).
3. Dejar **Block all public access** activado (por defecto).
4. En **Default encryption**, activar **Server-side encryption with Amazon
   S3 managed keys (SSE-S3)** — mismo criterio de seguridad que usamos en
   Reto 2.
5. Crear el bucket.
6. Dentro del bucket, crear las "carpetas" (prefijos) subiendo los archivos
   directamente con su ruta completa, o con el botón **Create folder**:
   - `raw/llamadas/`
   - `raw/whatsapp/`
   - `raw/correo/`
7. Subir los tres archivos generados en `data/raw/` de este repo, cada uno a
   su carpeta correspondiente:
   - `data/raw/llamadas/export_callcenter_2026.csv` → `raw/llamadas/`
   - `data/raw/whatsapp/whatsapp_business_export.json` → `raw/whatsapp/`
   - `data/raw/correo/buzon_soporte_2026.csv` → `raw/correo/`
8. **Captura de evidencia**: pantalla del bucket mostrando los 3 archivos
   subidos (región y fecha visibles en la lista de objetos).

---

## 2. Crear la función Lambda

1. Buscar **Lambda** → **Create function**.
2. **Author from scratch**.
3. Nombre de la función: `pf-propio-validador-tickets`.
4. Runtime: **Python 3.12**.
5. Architecture: x86_64 (por defecto).
6. En **Change default execution role** → **Use an existing role** →
   seleccionar **LabRole** (no se puede crear un rol nuevo en el Learner Lab).
7. Crear la función.
8. En la pestaña **Code**, abrir `lambda_function.py` en el editor en línea,
   borrar el contenido de ejemplo y pegar el contenido completo de
   `infra/lambda_handler.py` de este repo.
9. Click **Deploy**.
10. Ir a **Configuration → Environment variables** → **Edit** → **Add
    environment variable**:
    - `BUCKET` = `pf-propio-integracion-784989636429`
    - `PREFIJO_RAW` = `raw/`
    - `PREFIJO_PROCESADOS` = `procesados/`
11. En **Configuration → General configuration**, subir **Timeout** a
    **30 segundos** (de sobra para este volumen de datos).
12. **Captura de evidencia**: pantalla de configuración mostrando runtime,
    rol (LabRole) y variables de entorno.

### Probar la Lambda (caso feliz)

1. Pestaña **Test** → **Create new event** → nombre `prueba-caso-feliz` →
   Event JSON: `{}` → **Save** → **Test**.
2. Verificar en la respuesta que `statusCode` sea `200` y que el cuerpo
   muestre `"total_registros": 42, "total_validos": 31, "total_invalidos": 11`
   (mismos números ya verificados localmente con moto).
3. **Captura de evidencia**: resultado de la ejecución de prueba.
4. Ir a **S3** → bucket → confirmar que aparecieron:
   - `procesados/validos/validos.csv`
   - `procesados/invalidos/invalidos.csv`
   - `procesados/indicadores.json`
5. **Captura de evidencia**: listado de `procesados/` en el bucket.

### Probar el caso de error (para la defensa en vivo)

1. En S3, eliminar temporalmente (o renombrar) el objeto
   `raw/whatsapp/whatsapp_business_export.json`.
2. Volver a ejecutar el test de Lambda.
3. Verificar que `fuentes_fallidas` contenga `"whatsapp"` y que
   `total_registros` baje a `28` (solo llamadas + correo).
4. **Captura de evidencia**: resultado de la ejecución + el log de
   CloudWatch mostrando la línea `[ERROR] fuente 'whatsapp' fallo...`.
5. Volver a subir el archivo de WhatsApp para dejar el bucket en estado
   consistente antes de seguir.

### Revisar CloudWatch

1. Pestaña **Monitor → View CloudWatch logs** → abrir el log stream más
   reciente.
2. **Captura de evidencia**: logs mostrando al menos una ejecución exitosa y
   una con `fuentes_fallidas`.

---

## 3. Crear el Glue Crawler

1. Buscar **AWS Glue** → en el menú izquierdo, **Crawlers** → **Create
   crawler**.
2. Nombre: `pf-propio-crawler-validos`.
3. **Data source**: S3 → ruta
   `s3://pf-propio-integracion-784989636429/procesados/validos/`.
4. **IAM role**: usar **LabRole** (seleccionar un rol existente; el Learner
   Lab no permite crear roles nuevos para Glue tampoco).
5. **Output**: crear una base de datos nueva llamada `pf_propio_tickets_db`
   (botón **Add database** dentro del mismo asistente).
6. Frecuencia: **On demand** (para no dejar nada corriendo solo, cuidando el
   presupuesto).
7. Crear el crawler y darle **Run**.
8. Esperar a que el estado pase a **Completed** (toma 1–2 minutos).
9. **Captura de evidencia**: pantalla del crawler en estado "Completed" y la
   tabla creada en **Glue → Databases → pf_propio_tickets_db → Tables**.

---

## 4. Consultar con Athena

1. Buscar **Athena** → **Query editor**.
2. Si es la primera vez, configurar **Settings → Manage** → ubicación de
   resultados de consulta: `s3://pf-propio-integracion-784989636429/athena-results/`.
3. Seleccionar la base de datos `pf_propio_tickets_db` en el panel izquierdo;
   debería aparecer una tabla (nombre autogenerado por el crawler, algo como
   `validos`).
4. Ejecutar las consultas de ejemplo (ver `infra/consultas_athena.sql` en
   este repo):
   - Tickets válidos por canal.
   - Tickets por sucursal.
   - Tickets por marca de ascensor.
5. **Captura de evidencia**: cada consulta ejecutada con resultados visibles
   (región y fecha visibles en la consola).

---

## 5. Captura de consumo del Learner Lab (Sección 6 del informe)

1. Volver al panel del Learner Lab (no la consola de AWS) → botón
   **AWS Details** o el panel de créditos, según la vista del curso.
2. **Captura de evidencia**: consumo acumulado de crédito en el momento de
   la prueba.

---

## 6. Limpieza de recursos (antes de terminar la sesión)

1. **Athena**: no requiere apagar nada (serverless).
2. **Glue**: eliminar el crawler `pf-propio-crawler-validos` (Crawlers →
   seleccionar → Delete) y, si se quiere, la base de datos del catálogo.
3. **Lambda**: eliminar la función `pf-propio-validador-tickets` (o dejarla,
   no genera costo en reposo, pero mejor limpiar para el checklist final).
4. **S3**: vaciar el bucket (**Empty**) y eliminarlo, o dejarlo si se
   necesita para la defensa en vivo y eliminarlo recién al final del curso.
5. **Captura de evidencia**: pantalla confirmando que los recursos fueron
   eliminados/detenidos (para la Sección 8 "Conclusiones y limpieza").
