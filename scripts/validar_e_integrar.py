"""Prototipo local del paso de integracion/validacion (Capa 0 de datos).

La idea es probar la logica aqui, en mi maquina, ANTES de subirla como Lambda
al Learner Lab -- la leccion que me llevo de Reto 2 es que conviene verificar
el comportamiento con datos conocidos localmente primero, porque un error de
logica (no de AWS) se detecta mucho mas rapido fuera de CloudWatch.

Flujo:
  1. Leo los tres archivos crudos (cada uno con su propio esquema de columnas).
  2. Mapeo cada fuente al esquema canonico unico:
     id_ticket, canal, fecha_reporte, sucursal, marca_ascensor, texto_ticket,
     fuente_archivo, fila_origen
  3. Valido cada registro canonico con reglas de negocio fijas (igual que hice
     en la tesis con las reglas de negocio de urgencia: la validacion va COMO
     post-proceso explicito, no escondida dentro del mapeo).
  4. Separo validos/invalidos SIN tocar los archivos originales (quedan intactos
     en data/raw -- esa es la trazabilidad que pide la prueba de aceptacion).
  5. Escribo los indicadores verificables (conteos totales, por canal, por
     motivo de rechazo) a un JSON, que es lo que mostraria en CloudWatch/el
     informe como evidencia de la Seccion 5 (Pruebas y resultados).
"""
import csv
import json
import os
from datetime import datetime

CARPETA_RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
CARPETA_PROCESADOS = os.path.join(os.path.dirname(__file__), "..", "data", "procesados")

CANALES_VALIDOS = {"llamada", "whatsapp", "correo"}
CAMPOS_CANONICOS = [
    "id_ticket", "canal", "fecha_reporte", "sucursal",
    "marca_ascensor", "texto_ticket", "fuente_archivo", "fila_origen",
]


# ---------- paso 1 y 2: lectura + mapeo de cada fuente a esquema canonico ----------

def leer_llamadas():
    ruta = os.path.join(CARPETA_RAW, "llamadas", "export_callcenter_2026.csv")
    registros = []
    with open(ruta, encoding="utf-8") as f:
        for i, fila in enumerate(csv.DictReader(f), start=1):
            registros.append({
                "id_ticket": f"LLM-{fila['id_llamada']}".strip() if fila.get("id_llamada") else "",
                "canal": "llamada",
                "fecha_reporte": fila.get("fecha", ""),
                "sucursal": fila.get("sucursal", ""),
                "marca_ascensor": fila.get("marca", ""),
                "texto_ticket": fila.get("resumen_llamada", ""),
                "fuente_archivo": os.path.basename(ruta),
                "fila_origen": i,
            })
    return registros


def leer_whatsapp():
    ruta = os.path.join(CARPETA_RAW, "whatsapp", "whatsapp_business_export.json")
    registros = []
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    for i, reg in enumerate(datos, start=1):
        # el timestamp de whatsapp trae hora; a la capa canonica solo le interesa la fecha
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
            "fuente_archivo": os.path.basename(ruta),
            "fila_origen": i,
        })
    return registros


def leer_correos():
    ruta = os.path.join(CARPETA_RAW, "correo", "buzon_soporte_2026.csv")
    registros = []
    with open(ruta, encoding="utf-8") as f:
        for i, fila in enumerate(csv.DictReader(f), start=1):
            asunto = fila.get("asunto", "").strip()
            cuerpo = fila.get("cuerpo_mensaje", "").strip()
            # uno asunto + cuerpo porque en el correo el contenido util esta repartido
            texto = f"{asunto}: {cuerpo}".strip(": ").strip() if cuerpo else ""
            registros.append({
                "id_ticket": f"COR-{fila['id_correo']}".strip() if fila.get("id_correo") else "",
                "canal": "correo",
                "fecha_reporte": fila.get("fecha_envio", ""),
                "sucursal": fila.get("sucursal_destino", ""),
                "marca_ascensor": fila.get("marca_reportada", ""),
                "texto_ticket": texto,
                "fuente_archivo": os.path.basename(ruta),
                "fila_origen": i,
            })
    return registros


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
    """Devuelve (es_valido, motivo). Se evalua en orden fijo y el primer
    problema encontrado es el motivo de rechazo reportado (mantiene el
    indicador simple de leer, igual que las reglas de negocio de la tesis)."""
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


def integrar():
    todos = leer_llamadas() + leer_whatsapp() + leer_correos()

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
            # ojo: si el canal es desconocido no deberia pasar con estos datos,
            # pero protejo el conteo igual para no reventar con KeyError
            if reg["canal"] in conteo_por_canal:
                conteo_por_canal[reg["canal"]]["invalidos"] += 1
            conteo_por_motivo[motivo] = conteo_por_motivo.get(motivo, 0) + 1

    os.makedirs(CARPETA_PROCESADOS, exist_ok=True)

    with open(os.path.join(CARPETA_PROCESADOS, "validos.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CANONICOS)
        w.writeheader()
        w.writerows(validos)

    with open(os.path.join(CARPETA_PROCESADOS, "invalidos.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CANONICOS + ["motivo_rechazo"])
        w.writeheader()
        w.writerows(invalidos)

    indicadores = {
        "total_registros": len(todos),
        "total_validos": len(validos),
        "total_invalidos": len(invalidos),
        "por_canal": conteo_por_canal,
        "por_motivo_rechazo": conteo_por_motivo,
    }
    with open(os.path.join(CARPETA_PROCESADOS, "indicadores.json"), "w", encoding="utf-8") as f:
        json.dump(indicadores, f, ensure_ascii=False, indent=2)

    return indicadores


if __name__ == "__main__":
    indicadores = integrar()
    print(json.dumps(indicadores, ensure_ascii=False, indent=2))
