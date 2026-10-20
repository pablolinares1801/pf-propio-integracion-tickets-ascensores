"""Generador de datos sinteticos para el Proyecto Final (Proyecto propio).

Razono el problema asi: hoy la empresa recibe tickets de soporte de ascensores
por tres canales (call center, WhatsApp Business, correo), cada uno exportado
con su propio esquema de columnas. Para demostrar que el pipeline de
integracion funciona de verdad (y no solo "limpia un CSV ya bonito"), genero
tres archivos crudos con nombres de campo DISTINTOS entre si -- la funcion de
mapeo en validar_e_integrar.py es la que hace el trabajo real de unificarlos.

Tambien siembro a proposito casos invalidos (fechas corruptas, marca vacia,
texto vacio, duplicados cruzando canales) porque la prueba de aceptacion del
proyecto exige demostrar que el sistema separa validos/invalidos con
indicadores verificables, no solo que procesa el caso feliz.

No uso librerias externas (csv/json/random/datetime de la stdlib) para que
este script corra igual en mi maquina y en CloudShell sin pip install.
"""
import csv
import json
import os
import random

random.seed(7)  # fijo la semilla para que el dataset sea reproducible entre corridas

CARPETA_SALIDA = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

SUCURSALES = [
    "Santa Cruz - Equipetrol",
    "Santa Cruz - Centro",
    "Santa Cruz - Norte",
    "Santa Cruz - Sur",
    "Montero",
]
MARCAS = ["Orona", "BLT", "Hyundai", "Hidral", "Otro"]

TEXTOS_VALIDOS = [
    "El ascensor se detuvo entre pisos 3 y 4, hay un pasajero atrapado.",
    "Se escucha un ruido metalico fuerte al abrir las puertas.",
    "La cabina no nivela bien con el piso, queda un escalon de varios cm.",
    "El boton del piso 5 no enciende, el resto funciona normal.",
    "Mantenimiento preventivo mensual, sin incidentes reportados.",
    "Las puertas no cierran completamente y se reabren solas.",
    "Olor a quemado en el cuarto de maquinas, se corto la energia por seguridad.",
    "El ascensor funciona pero hace un frenado muy brusco al llegar a planta baja.",
    "Se solicita revision de la velocidad de la cabina, parece mas lenta de lo normal.",
    "Falla de frenado reportada por el guardia de seguridad del edificio.",
    "Luz de cabina parpadea intermitentemente, posible falla electrica menor.",
    "Consulta de garantia por ruido en motor, equipo instalado hace 8 meses.",
]


def _fecha_aleatoria_iso():
    mes = random.randint(1, 10)
    dia = random.randint(1, 28)
    return f"2026-{mes:02d}-{dia:02d}"


def generar_llamadas(n=16):
    """Exporta el formato del sistema de telefonia: columnas en espanol, sin tiempo."""
    filas = []
    for i in range(1, n + 1):
        filas.append({
            "id_llamada": f"{1000 + i}",
            "fecha": _fecha_aleatoria_iso(),
            "sucursal": random.choice(SUCURSALES),
            "marca": random.choice(MARCAS),
            "resumen_llamada": random.choice(TEXTOS_VALIDOS),
            "duracion_seg": random.randint(45, 420),
        })

    # --- casos invalidos sembrados a proposito ---
    filas[2]["fecha"] = "32/13/2026"  # fecha imposible -> no parseable
    filas[5]["marca"] = ""  # marca vacia
    filas[8]["resumen_llamada"] = ""  # texto vacio
    filas[11]["id_llamada"] = filas[0]["id_llamada"]  # duplicado dentro del mismo canal

    ruta = os.path.join(CARPETA_SALIDA, "llamadas", "export_callcenter_2026.csv")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_llamada", "fecha", "sucursal", "marca", "resumen_llamada", "duracion_seg"])
        w.writeheader()
        w.writerows(filas)
    return ruta, len(filas)


def generar_whatsapp(n=14):
    """Exporta el formato de WhatsApp Business: JSON, nombres de campo distintos,
    fecha con hora incluida (timestamp), para forzar un parseo distinto al de llamadas."""
    registros = []
    for i in range(1, n + 1):
        registros.append({
            "ticket_id": f"WA{500 + i}",
            "timestamp": f"{_fecha_aleatoria_iso()} {random.randint(7,20):02d}:{random.randint(0,59):02d}",
            "telefono_cliente": f"+5917{random.randint(1000000,9999999)}",
            "sede": random.choice(SUCURSALES),
            "modelo_equipo": random.choice(MARCAS),
            "mensaje": random.choice(TEXTOS_VALIDOS),
        })

    # --- casos invalidos sembrados a proposito ---
    registros[1]["timestamp"] = "no-disponible"  # fecha no parseable
    registros[4]["mensaje"] = "ok"[:0]  # texto vacio (string vacio)
    registros[7]["modelo_equipo"] = ""  # marca vacia
    registros[10]["ticket_id"] = ""  # id_ticket vacio

    ruta = os.path.join(CARPETA_SALIDA, "whatsapp", "whatsapp_business_export.json")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)
    return ruta, len(registros)


def generar_correos(n=12):
    """Exporta el formato del buzon de correo: columnas distintas otra vez,
    y el texto util esta repartido entre 'asunto' y 'cuerpo_mensaje'."""
    filas = []
    for i in range(1, n + 1):
        texto = random.choice(TEXTOS_VALIDOS)
        filas.append({
            "id_correo": f"COR-{i:03d}",
            "fecha_envio": _fecha_aleatoria_iso(),
            "remitente": f"cliente{i}@correo.com",
            "asunto": "Reporte de falla de ascensor",
            "cuerpo_mensaje": texto,
            "sucursal_destino": random.choice(SUCURSALES),
            "marca_reportada": random.choice(MARCAS),
        })

    # --- casos invalidos sembrados a proposito ---
    filas[3]["fecha_envio"] = ""  # fecha faltante
    filas[6]["cuerpo_mensaje"] = ""  # texto vacio (y el asunto solo no basta, se valida el cuerpo)
    # duplicado CRUZANDO canales: mismo numero de ticket logico que uno de WhatsApp,
    # para probar que la deduplicacion es sobre el id_ticket ya unificado (con prefijo
    # de canal no deberia chocar en este caso -- lo dejo como comentario/evidencia de
    # que el prefijo por canal evita falsos positivos de duplicado entre fuentes).
    filas[9]["id_correo"] = filas[0]["id_correo"]  # duplicado dentro del mismo canal

    ruta = os.path.join(CARPETA_SALIDA, "correo", "buzon_soporte_2026.csv")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_correo", "fecha_envio", "remitente", "asunto", "cuerpo_mensaje", "sucursal_destino", "marca_reportada"])
        w.writeheader()
        w.writerows(filas)
    return ruta, len(filas)


if __name__ == "__main__":
    r1, n1 = generar_llamadas()
    r2, n2 = generar_whatsapp()
    r3, n3 = generar_correos()
    print(f"Generado {r1} ({n1} filas)")
    print(f"Generado {r2} ({n2} registros)")
    print(f"Generado {r3} ({n3} filas)")
    print(f"Total registros crudos: {n1 + n2 + n3}")
