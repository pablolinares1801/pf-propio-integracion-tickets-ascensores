"""Lambda de integracion/validacion de tickets multicanal (Proyecto Final, proyecto propio).

Pensado para pegarse directo en el editor en linea de la consola de Lambda
(un solo archivo, sin dependencias externas mas alla de boto3, que ya viene
incluido en el runtime de Lambda -- no hace falta armar un zip con librerias
como tuve que hacer en Reto 2 con TF-IDF).

Logica identica a scripts/validar_e_integrar.py (probada localmente primero,
la misma leccion que me llevo de Reto 2: verificar la logica de negocio en mi
maquina antes de depender de CloudWatch para debuggear). La unica diferencia
real es que aqui leo y escribo contra S3 en vez del filesystem local, y que
envuelvo cada fuente en su propio try/except: si un canal falla (archivo
ausente, JSON corrupto, etc.) lo reporto como fuente_fallida en los
indicadores y SIGO procesando las otras dos -- ese es el "caso de error"
controlado que pienso mostrar en vivo en la defensa, en vez de dejar que la
funcion truene entera por un solo archivo roto.

Variables de entorno esperadas (se configuran en la consola de Lambda):
  BUCKET              -> nombre del bucket (ej. pf-propio-integracion-784989636429)
  PREFIJO_RAW          -> prefijo de la zona cruda (default: raw/)
  PREFIJO_PROCESADOS   -> prefijo de salida (default: procesados/)
"""
import csv
import io
import json
import os
from datetime import datetime

import boto3

s3 = boto3.client("s3")

BUCKET = os.environ.get("BUCKET", "pf-propio-integracion-784989636429")
PREFIJO_RAW = os.environ.get("PREFIJO_RAW", "raw/")
PREFIJO_PROCESADOS = os.environ.get("PREFIJO_PROCESADOS", "procesados/")

CANALES_VALIDOS = {"llamada", "whatsapp", "correo"}
CAMPOS_CANONICOS = [
    "id_ticket", "canal", "fecha_reporte", "sucursal",
    "marca_ascensor", "texto_ticket", "fuente_archivo", "fila_origen",
]

CLAVE_LLAMADAS = PREFIJO_RAW + "llamadas/export_callcenter_2026.csv"
CLAVE_WHATSAPP = PREFIJO_RAW + "whatsapp/whatsapp_business_export.json"
CLAVE_CORREO = PREFIJO_RAW + "correo/buzon_soporte_2026.csv"


# ---------- helpers de lectura desde S3 ----------

def _leer_texto_s3(clave):
    obj = s3.get_object(Bucket=BUCKET, Key=clave)
    return obj["Body"].read().decode("utf-8")


# ---------- paso 1 y 2: lectura + mapeo de cada fuente a esquema canonico ----------
# (mismo mapeo que en el prototipo local; cada fuente tiene su propio esquema
#  de columnas a proposito, para que la "integracion" sea real)

def leer_llamadas():
    texto = _leer_texto_s3(CLAVE_LLAMADAS)
    registros = []
    for i, fila in enumerate(csv.DictReader(io.StringIO(texto)), start=1):
        registros.append({
            "id_ticket": f"LLM-{fila['id_llamada']}".strip() if fila.get("id_llamada") else "",
            "canal": "llamada",
            "fecha_reporte": fila.get("fecha", ""),
            "sucursal": fila.get("sucursal", ""),
            "marca_ascensor": fila.get("marca", ""),
            "texto_ticket": fila.get("resumen_llamada", ""),
            "fuente_archivo": CLAVE_LLAMADAS,
            "fila_origen": i,
        })
    return registros


def leer_whatsapp():
    datos = json.loads(_leer_texto_s3(CLAVE_WHATSAPP))
    registros = []
    for i, reg in enumerate(datos, start=1):
        timestamp = reg.get("timestamp", "")
        fecha = timestamp.split(" ")[0] if timestamp else ""
        tid = reg.get("ticket_id", "")
        registros.append({
            "id_ticket": f"WA-{tid}".strip() if tid else "",
            "canal": "whatsapp",
            "fecha_reporte": fecha,
            "sucursal": reg.get("sede", ""),
            "marca_ascensor": reg.get("modelo_equipo", ""),
            "texto_ticket": reg.get("mensaje", ""),
            "fuente_archivo": CLAVE_WHATSAPP,
            "fila_origen": i,
        })
    return registros


def leer_correos():
    texto = _leer_texto_s3(CLAVE_CORREO)
    registros = []
    for i, fila in enumerate(csv.DictReader(io.StringIO(texto)), start=1):
        asunto = fila.get("asunto", "").strip()
        cuerpo = fila.get("cuerpo_mensaje", "").strip()
        texto_unido = f"{asunto}: {cuerpo}".strip(": ").strip() if cuerpo else ""
        registros.append({
            "id_ticket": f"COR-{fila['id_correo']}".strip() if fila.get("id_correo") else "",
            "canal": "correo",
            "fecha_reporte": fila.get("fecha_envio", ""),
            "sucursal": fila.get("sucursal_destino", ""),
            "marca_ascensor": fila.get("marca_reportada", ""),
            "texto_ticket": texto_unido,
            "fuente_archivo": CLAVE_CORREO,
            "fila_origen": i,
        })
    return registros


LECTORES_POR_CANAL = {
    "llamada": leer_llamadas,
    "whatsapp": leer_whatsapp,
    "correo": leer_correos,
}


# ---------- paso 3: validacion como post-proceso explicito ----------

def _fecha_parseable(valor):
    if not valor:
        return False
    try:
        datetime.strptime(valor, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validar_registro(reg, ids_vistos):
    if not reg["id_ticket"]:
        return False, "id_ticket_vacio"
    if reg["id_ticket"] in ids_vistos:
        return False, "id_duplicado"
    if reg["canal"] not in CANALES_VALIDOS:
        return False, "canal_desconocido"
    if not _fecha_parseable(reg["fecha_reporte"]):
        return False, "fecha_invalida"
    if not reg["marca_ascensor"]:
        return False, "marca_vacia"
    if not reg["texto_ticket"] or len(reg["texto_ticket"]) < 5:
        return False, "texto_vacio"
    return True, None


# ---------- helpers de escritura a S3 ----------

def _escribir_csv_s3(clave, filas, campos):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=campos)
    w.writeheader()
    w.writerows(filas)
    s3.put_object(Bucket=BUCKET, Key=clave, Body=buf.getvalue().encode("utf-8"))


def _escribir_json_s3(clave, datos):
    s3.put_object(
        Bucket=BUCKET, Key=clave,
        Body=json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8"),
    )


def lambda_handler(event, context):
    todos = []
    fuentes_fallidas = {}

    # leo cada canal en su propio try/except: si uno falla (archivo ausente,
    # JSON corrupto, columna faltante) lo registro y sigo con los demas --
    # este es el comportamiento que quiero demostrar como "caso de error"
    # en la defensa en vivo, en vez de dejar que una sola fuente rota tumbe
    # el procesamiento completo del batch.
    for canal, lector in LECTORES_POR_CANAL.items():
        try:
            todos.extend(lector())
        except Exception as e:  # noqa: BLE001 - quiero capturar cualquier fallo de una fuente y seguir
            fuentes_fallidas[canal] = f"{type(e).__name__}: {e}"
            print(f"[ERROR] fuente '{canal}' fallo y se omite del batch: {fuentes_fallidas[canal]}")

    validos, invalidos = [], []
    ids_vistos = set()
    conteo_por_canal = {c: {"validos": 0, "invalidos": 0} for c in CANALES_VALIDOS}
    conteo_por_motivo = {}

    for reg in todos:
        es_valido, motivo = validar_registro(reg, ids_vistos)
        if es_valido:
            ids_vistos.add(reg["id_ticket"])
            validos.append(reg)
            conteo_por_canal[reg["canal"]]["validos"] += 1
        else:
            reg_invalido = dict(reg)
            reg_invalido["motivo_rechazo"] = motivo
            invalidos.append(reg_invalido)
            if reg["canal"] in conteo_por_canal:
                conteo_por_canal[reg["canal"]]["invalidos"] += 1
            conteo_por_motivo[motivo] = conteo_por_motivo.get(motivo, 0) + 1

    _escribir_csv_s3(PREFIJO_PROCESADOS + "validos/validos.csv", validos, CAMPOS_CANONICOS)
    _escribir_csv_s3(PREFIJO_PROCESADOS + "invalidos/invalidos.csv", invalidos, CAMPOS_CANONICOS + ["motivo_rechazo"])

    indicadores = {
        "total_registros": len(todos),
        "total_validos": len(validos),
        "total_invalidos": len(invalidos),
        "por_canal": conteo_por_canal,
        "por_motivo_rechazo": conteo_por_motivo,
        "fuentes_fallidas": fuentes_fallidas,
    }
    _escribir_json_s3(PREFIJO_PROCESADOS + "indicadores.json", indicadores)

    print(json.dumps(indicadores, ensure_ascii=False, indent=2))

    return {
        "statusCode": 200,
        "body": json.dumps(indicadores, ensure_ascii=False),
    }
