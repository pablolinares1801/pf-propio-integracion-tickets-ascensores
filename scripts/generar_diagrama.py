"""Genera docs/arquitectura.png con el diagrama de componentes y flujo de
datos del proyecto. Lo hago con matplotlib (cajas + flechas) porque no tengo
graphviz instalado localmente y no quiero depender de una herramienta externa
para un diagrama que en el fondo es simple: 3 fuentes -> S3 raw -> Lambda ->
S3 procesados -> Glue Crawler -> Data Catalog -> Athena.
"""
import os

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

RUTA_SALIDA = os.path.join(os.path.dirname(__file__), "..", "docs", "arquitectura.png")


def caja(ax, xy, w, h, texto, color="#dbe9f7", borde="#2b5f8a", fontsize=9, fontweight="normal"):
    x, y = xy
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.4, edgecolor=borde, facecolor=color,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center",
             fontsize=fontsize, fontweight=fontweight, wrap=True)
    return (x, y, w, h)


def flecha(ax, origen, destino, texto=None, color="#444444", lado_texto="arriba", desplazar_texto=0.0):
    (x0, y0, w0, h0) = origen
    (x1, y1, w1, h1) = destino
    p0 = (x0 + w0 / 2, y0 + h0 / 2)
    p1 = (x1 + w1 / 2, y1 + h1 / 2)
    arrow = FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14,
                             linewidth=1.3, color=color, shrinkA=28, shrinkB=28,
                             connectionstyle="arc3,rad=0.0")
    ax.add_patch(arrow)
    if texto:
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        if lado_texto == "arriba":
            ax.text(mx, my + 0.22 + desplazar_texto, texto, ha="center", va="bottom", fontsize=7, color=color)
        elif lado_texto == "abajo":
            ax.text(mx, my - 0.22 - desplazar_texto, texto, ha="center", va="top", fontsize=7, color=color)
        elif lado_texto == "izquierda":
            ax.text(mx - 0.15, my, texto, ha="right", va="center", fontsize=7, color=color)
        else:
            ax.text(mx + 0.15, my, texto, ha="left", va="center", fontsize=7, color=color)


def main():
    fig, ax = plt.subplots(figsize=(13, 8.5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8.5)
    ax.axis("off")
    ax.set_title(
        "Arquitectura - Integración de tickets de soporte multicanal (Proyecto propio)",
        fontsize=13, fontweight="bold", pad=16,
    )

    # --- fuentes (izquierda, fila superior) ---
    f_llamadas = caja(ax, (0.3, 6.7), 2.1, 0.8, "Call center\n(CSV)", color="#fdeedd", borde="#b5651d", fontsize=9)
    f_whatsapp = caja(ax, (0.3, 5.6), 2.1, 0.8, "WhatsApp Business\n(JSON)", color="#fdeedd", borde="#b5651d", fontsize=9)
    f_correo = caja(ax, (0.3, 4.5), 2.1, 0.8, "Buzón de correo\n(CSV)", color="#fdeedd", borde="#b5651d", fontsize=9)

    # --- S3 zona cruda ---
    s3_raw = caja(ax, (3.4, 5.3), 2.6, 2.1,
                  "Amazon S3 - zona cruda\n/raw/llamada/\n/raw/whatsapp/\n/raw/correo/\n(originales intactos)",
                  color="#dbe9f7", borde="#2b5f8a", fontsize=8)

    flecha(ax, f_llamadas, s3_raw, "export\ndiario", lado_texto="arriba")
    flecha(ax, f_whatsapp, s3_raw, None)
    flecha(ax, f_correo, s3_raw, "export\ndiario", lado_texto="abajo")

    # --- Lambda ---
    lam = caja(ax, (6.9, 5.3), 2.6, 2.1,
               "AWS Lambda\npf-propio-validador-tickets\n\nmapeo a esquema canónico\n+ validación válidos/inválidos",
               color="#e3f0df", borde="#3b7a3b", fontsize=8)
    flecha(ax, s3_raw, lam, "lee 3\narchivos", lado_texto="arriba")

    # --- S3 procesados ---
    s3_proc = caja(ax, (10.1, 5.6), 2.5, 1.6,
                   "Amazon S3 - procesados\n/procesados/validos/\n/procesados/invalidos/\n/procesados/indicadores.json",
                   color="#dbe9f7", borde="#2b5f8a", fontsize=7.5)
    flecha(ax, lam, s3_proc, "escribe salida\n+ indicadores", lado_texto="arriba")

    # --- Glue Crawler ---
    crawler = caja(ax, (6.9, 2.6), 2.6, 1.1,
                   "AWS Glue Crawler\npf-propio-crawler-validos",
                   color="#f3e3f7", borde="#6a2b8a", fontsize=8.5)
    flecha(ax, s3_proc, crawler, "cataloga\n/validos/", lado_texto="derecha")

    # --- Data Catalog ---
    catalogo = caja(ax, (3.6, 2.6), 2.6, 1.1,
                     "Glue Data Catalog\npf_propio_tickets_db",
                     color="#f3e3f7", borde="#6a2b8a", fontsize=8.5)
    flecha(ax, crawler, catalogo, "crea/actualiza\ntabla", lado_texto="arriba")

    # --- Athena ---
    athena = caja(ax, (0.3, 2.6), 2.6, 1.1,
                   "Amazon Athena\nconsultas SQL",
                   color="#fdf3d0", borde="#9a7d00", fontsize=8.5)
    flecha(ax, catalogo, athena, "consulta", lado_texto="arriba")

    # --- CloudWatch (observabilidad, conectado a Lambda) ---
    cw = caja(ax, (6.9, 0.4), 2.6, 1.1,
              "Amazon CloudWatch\nLogs de ejecución\n(éxitos y fuentes fallidas)",
              color="#f7dbdb", borde="#8a2b2b", fontsize=8)
    flecha(ax, lam, cw, "logs", lado_texto="derecha")

    # --- IAM / LabRole (seguridad, nota aparte) ---
    ax.text(10.1, 0.95,
            "Permisos: todo corre bajo\nel rol LabRole del\nAWS Academy Learner Lab\n(sin usuarios/roles propios)",
            fontsize=7.5, ha="left", va="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#f2f2f2", edgecolor="#999999"))

    os.makedirs(os.path.dirname(RUTA_SALIDA), exist_ok=True)
    plt.tight_layout()
    plt.savefig(RUTA_SALIDA, dpi=170)
    print(f"Diagrama guardado en {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
