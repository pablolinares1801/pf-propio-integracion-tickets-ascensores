"""Prueba el lambda_handler real (infra/lambda_handler.py) contra un S3
simulado con moto, sin tocar AWS. La idea: si esto pasa aqui, cuando lo
pegue en la consola de Lambda deberia comportarse igual -- la unica
diferencia es que ahi el S3 es de verdad.

Tambien pruebo el "caso de error" (fuente whatsapp ausente) para confirmar
que el try/except por canal funciona como quiero mostrarlo en la defensa.
"""
import json
import os
import sys

import boto3
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "infra"))

BUCKET = "pf-propio-integracion-784989636429"
RAIZ_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def _subir_raw(s3):
    archivos = {
        "raw/llamadas/export_callcenter_2026.csv": os.path.join(RAIZ_DATA, "llamadas", "export_callcenter_2026.csv"),
        "raw/whatsapp/whatsapp_business_export.json": os.path.join(RAIZ_DATA, "whatsapp", "whatsapp_business_export.json"),
        "raw/correo/buzon_soporte_2026.csv": os.path.join(RAIZ_DATA, "correo", "buzon_soporte_2026.csv"),
    }
    for clave, ruta in archivos.items():
        with open(ruta, "rb") as f:
            s3.put_object(Bucket=BUCKET, Key=clave, Body=f.read())
    return archivos


@mock_aws
def probar_caso_feliz():
    os.environ["BUCKET"] = BUCKET
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    _subir_raw(s3)

    import lambda_handler
    import importlib
    importlib.reload(lambda_handler)  # por si el modulo quedo cacheado de una corrida previa

    resultado = lambda_handler.lambda_handler({}, None)
    print("=== CASO FELIZ (3 fuentes OK) ===")
    print(json.dumps(json.loads(resultado["body"]), ensure_ascii=False, indent=2))

    # reviso que los objetos de salida quedaron escritos en el S3 simulado
    objetos = s3.list_objects_v2(Bucket=BUCKET, Prefix="procesados/")
    claves = [o["Key"] for o in objetos.get("Contents", [])]
    print("\nObjetos escritos en procesados/:", claves)
    assert "procesados/validos/validos.csv" in claves
    assert "procesados/invalidos/invalidos.csv" in claves
    assert "procesados/indicadores.json" in claves
    print("OK: objetos de salida presentes")


@mock_aws
def probar_caso_error():
    os.environ["BUCKET"] = BUCKET
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    archivos = _subir_raw(s3)
    # simulo la fuente whatsapp ausente/corrupta borrando su objeto
    s3.delete_object(Bucket=BUCKET, Key="raw/whatsapp/whatsapp_business_export.json")

    import lambda_handler
    import importlib
    importlib.reload(lambda_handler)

    resultado = lambda_handler.lambda_handler({}, None)
    indicadores = json.loads(resultado["body"])
    print("\n=== CASO DE ERROR (whatsapp ausente) ===")
    print(json.dumps(indicadores, ensure_ascii=False, indent=2))

    assert "whatsapp" in indicadores["fuentes_fallidas"], "deberia reportar whatsapp como fuente fallida"
    assert indicadores["total_registros"] == 16 + 12, "deberia seguir procesando llamadas + correo (28 registros)"
    print("OK: la funcion sobrevivio a una fuente rota y siguio con las otras dos")


if __name__ == "__main__":
    probar_caso_feliz()
    probar_caso_error()
    print("\nTODO OK: el lambda_handler real se comporta igual que el prototipo local.")
