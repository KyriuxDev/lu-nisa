"""Extrae las oraciones de ejemplo (zapoteco → español) del diccionario de Jaltepec.

El diccionario es de sus autores (Hernández Andrade y López Nicolás, INPI 2022), así que
las oraciones NO se suben al repositorio: cada quien corre este script con su copia del PDF
y el resultado queda en app/data/ejemplos_jaltepec.json (está en .gitignore).

    .venv/bin/pip install pymupdf
    .venv/bin/python scripts/extraer_ejemplos_jaltepec.py ruta/al/Diccionario-zapoteco-San-Juan-Jaltepec.pdf

En el PDF cada entrada es: palabra (negritas 12) · categoría (itálica) · significado ·
ejemplo en zapoteco (negritas 10) · traducción del ejemplo (normal) · formas verbales (itálica).
"""

import json
import re
import sys
from pathlib import Path

import pymupdf

SALIDA = Path(__file__).resolve().parents[1] / "app" / "data" / "ejemplos_jaltepec.json"


def tramos(pdf: pymupdf.Document):
    """(tipo, texto) en orden de lectura: entrada | negrita | italica | normal."""
    for pagina in pdf:
        for bloque in pagina.get_text("dict")["blocks"]:
            for linea in bloque.get("lines", []):
                for s in linea["spans"]:
                    texto = s["text"].strip()
                    if not texto or s["size"] < 8:  # números de acepción en superíndice
                        continue
                    fuente = s["font"]
                    if "Bold" in fuente:
                        yield ("entrada" if s["size"] >= 11.5 else "negrita"), texto
                    elif "Italic" in fuente:
                        yield "italica", texto
                    else:
                        yield "normal", texto


def extraer(ruta_pdf: str) -> list[dict]:
    ejemplos, entrada, estado = [], None, None
    zap, esp = [], []

    def cerrar():
        z = " ".join(zap).strip(" .")
        e = " ".join(esp).strip(" .;")
        # Un ejemplo real: varias palabras en zapoteco y una traducción que empieza con mayúscula
        if entrada and len(z.split()) >= 2 and e[:1].isupper() and len(e.split()) >= 2:
            ejemplos.append({"zapoteco": z, "espanol": e, "entrada": entrada})
        zap.clear()
        esp.clear()

    for tipo, texto in tramos(pymupdf.open(ruta_pdf)):
        if tipo == "entrada":
            cerrar()
            entrada, estado = texto, "definicion"
        elif tipo == "negrita":
            if estado == "traduccion":
                cerrar()
            if estado in ("definicion", "ejemplo", "traduccion"):
                zap.append(texto)
                estado = "ejemplo"
        elif tipo == "italica":
            # Compl.:, Irr.:, Yal.: o la categoría: termina el ejemplo
            if estado in ("ejemplo", "traduccion"):
                cerrar()
                estado = "formas"
        elif tipo == "normal" and estado in ("ejemplo", "traduccion"):
            esp.append(texto)
            estado = "traduccion"
    cerrar()

    # Sin repetidos
    vistos, unicos = set(), []
    for e in ejemplos:
        clave = (e["zapoteco"], e["espanol"])
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(e)
    return unicos


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ejemplos = extraer(sys.argv[1])
    SALIDA.write_text(json.dumps(ejemplos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(ejemplos)} ejemplos → {SALIDA}")
