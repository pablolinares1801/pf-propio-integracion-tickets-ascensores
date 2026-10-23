# Integración de tickets de soporte multicanal — Proyecto Final (Proyecto propio)

**Autor:** Pablo Andrés Linares Ruiz — pablo.linares@ucb.edu.bo
**Curso:** Computación en la Nube · Maestría en Ciencia de Datos e IA Aplicada · UCB "San Pablo"
**Modalidad:** Proyecto propio (inspirado en el tema de referencia "Integración y análisis de datos")

## Problema de negocio

Una distribuidora de ascensores (marcas Orona, BLT, Hyundai, Hidral) en Santa
Cruz de la Sierra recibe tickets de soporte técnico por tres canales
distintos — exports CSV del call center, exports JSON de WhatsApp Business y
CSV de un buzón de correo — cada uno con su propio esquema de columnas. Hoy
no existe ninguna capa que los consolide: no se puede analizar el volumen
total de tickets, y tampoco se puede alimentar con datos limpios un futuro
clasificador automático de urgencia (ver nota de alcance más abajo).

Este proyecto construye esa **capa de integración de datos** ("Capa 0"):
ingesta cruda a S3 → normalización a un esquema único + validación
(separación válidos/inválidos con trazabilidad) → catálogo con AWS Glue →
consultas analíticas con Amazon Athena.

> **Nota de alcance:** este proyecto NO clasifica la urgencia de los tickets
> ni recomienda soluciones — eso corresponde a la tesis de maestría (Capas 1 y 2, fuera del alcance de este curso). Aquí el foco es
> exclusivamente la integración/calidad de datos: el insumo que ese otro
> trabajo necesitaría como entrada limpia.

## Arquitectura

Ver [`docs/arquitectura.md`](docs/arquitectura.md) (diagrama completo +
justificación de cada servicio elegido y su alternativa descartada).

Resumen: **3 fuentes heterogéneas → S3 (zona cruda) → AWS Lambda (mapeo a
esquema canónico + validación) → S3 (zona procesada: válidos / inválidos /
indicadores) → AWS Glue Crawler (catálogo) → Amazon Athena (consultas SQL)**,
con logs en Amazon CloudWatch. Todo bajo el rol `LabRole` del AWS Academy
Learner Lab (sin usuarios ni roles IAM propios — restricción del lab).

## Prueba de aceptación

1. Cargar un batch con los tres archivos de origen (`data/raw/`), que
   contiene una mezcla deliberada de registros válidos e inválidos
   (duplicados, fechas corruptas, marca de ascensor vacía, texto vacío,
   id vacío).
2. Ejecutar el proceso de integración (Lambda en AWS, o el script local
   equivalente).
3. Verificar que:
   - Los archivos originales permanecen intactos en `/raw/` (trazabilidad).
   - Los registros quedan separados correctamente en válidos/inválidos,
     cada inválido con su motivo de rechazo.
   - Se generan indicadores verificables: total, por canal, por motivo de
     rechazo (`indicadores.json`).
   - Los válidos quedan catalogados y son consultables por Athena.
4. Caso de error: si una de las tres fuentes falla (archivo ausente o
   corrupto), el proceso debe seguir integrando las otras dos fuentes y
   reportar la falla de forma explícita, no caerse por completo.

Resultado verificado localmente (ver sección siguiente):
**42 registros totales → 31 válidos / 11 inválidos**, con 5 motivos de
rechazo distintos cubiertos, y comportamiento correcto ante la fuente
caída (whatsapp ausente → 28 registros procesados, resto sigue).

## Estructura del repositorio

```
/data/raw/            # datos de prueba sintéticos (3 esquemas distintos)
/data/procesados/     # salida del prototipo local (validos/invalidos/indicadores)
/scripts/             # generador de datos, prototipo local, prueba con S3 simulado (moto)
/infra/               # lambda_handler.py (listo para pegar en consola) + consultas_athena.sql
/docs/                # diagrama de arquitectura, justificación de servicios, runbook de consola
/evidencias/          # capturas y logs de las pruebas en AWS real (se llenan durante el despliegue)
```

## Requisitos

- Python 3.9+ (solo para correr los scripts locales de generación/prueba).
- Cuenta de AWS Academy Learner Lab activa, región `us-east-1`.
- Sin dependencias externas en la Lambda real (usa `boto3`, incluido en el
  runtime de AWS Lambda). Para las pruebas locales con S3 simulado:
  `pip install boto3 moto`.

## Cómo generar los datos de prueba y correr el prototipo localmente

```bash
cd scripts
python3 generar_datos_sinteticos.py   # crea data/raw/{llamadas,whatsapp,correo}/
python3 validar_e_integrar.py         # corre la integración localmente -> data/procesados/
python3 probar_lambda_local.py        # corre infra/lambda_handler.py contra un S3 simulado (moto)
python3 generar_diagrama.py           # regenera docs/arquitectura.png si se edita el script
```

## Cómo desplegar en AWS (Learner Lab)

Seguir el instructivo paso a paso en
[`docs/runbook_consola.md`](docs/runbook_consola.md) — creación del bucket
S3, la función Lambda (pegar `infra/lambda_handler.py`), el Glue Crawler y
las consultas de Athena, todo por consola web (sin CLI).

## Limitaciones y trabajo futuro

- Pensado para volumen batch pequeño/mediano; con miles de registros diarios
  convendría migrar la transformación de Lambda a un Glue Job.
- La deduplicación es exacta por `id_ticket`, no semántica.
- No incluye clasificación de urgencia ni recomendación — ver nota de
  alcance arriba.
