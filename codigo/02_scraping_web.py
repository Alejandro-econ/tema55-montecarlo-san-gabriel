# Autor: Alejandro Soto Antezana
# Código de matrícula: 2024200531K
# Tema 55: Riesgo del proyecto: simulación de Monte Carlo sobre precio, demanda y tipo de cambio
# Fecha de extracción: se registra automáticamente en log_ejecucion.txt al ejecutar
"""
VÍA 2 — DESCARGA PROGRAMÁTICA (numeral 2.4.3 de la consigna)
-------------------------------------------------------------
(a) SEC (EE. UU.): descarga el PDF oficial del "Technical Report Summary" de la mina San Gabriel
    (Buenaventura, Moquegua) y lee con pdfplumber los parámetros del proyecto:
    inversión, producción, costo, vida útil, tasa de descuento y VAN oficial.
(b) FRED (Banco de la Reserva Federal de St. Louis): descarga el archivo CSV oficial con el
    rendimiento diario del bono del Tesoro de EE. UU. a 10 años (serie DGS10), insumo de la tasa
    de descuento (tasa libre de riesgo + riesgo país).
Antes de cada descarga se lee robots.txt, se usa un User-Agent identificable y se pausa 1 s.
Los archivos originales quedan intactos en datos_crudos/.
"""

# ------------------------------------------------------------------
# BLOQUE 1. Librerías y configuración
# ------------------------------------------------------------------
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import pandas as pd
import pdfplumber
import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos_crudos"
CRUDOS.mkdir(exist_ok=True)
LOG = RAIZ / "log_ejecucion.txt"
load_dotenv(RAIZ / ".env")

CODIGO = "2024200531K"
# La SEC exige un User-Agent con nombre y correo. Se lee desde .env (ver .env.example)
USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()
if not USER_AGENT:
    raise SystemExit("Falta SEC_USER_AGENT en el archivo .env (ver .env.example).")

# Documento oficial: Exhibit 96.2 del Form 20-F 2024 de Buenaventura (S-K 1300, fecha efectiva 31/12/2024)
URL_TRS = "https://www.sec.gov/Archives/edgar/data/1013131/000141057825001056/tmb-20241231xex96d2.pdf"
PAGINAS_A_LEER = 60  # el resumen ejecutivo (sección 1) contiene todos los parámetros que se usan

# Archivo histórico del fondo GLD publicado por su patrocinador
# Archivo CSV oficial de FRED (no requiere clave). robots.txt de FRED permite /graph/fredgraph.csv
FECHA_INICIO = "2004-11-18"
FECHA_CORTE = "2026-08-31"
URL_FRED = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd={FECHA_INICIO}&coed={FECHA_CORTE}"


def registrar(script, url, http, filas, mensaje=""):
    """Escribe una línea en log_ejecucion.txt: fecha y hora de Lima, URL, código HTTP y filas."""
    ahora = datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{ahora} (Lima) | {script} | HTTP {http} | filas={filas} | {url} | {mensaje}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def permitido_por_robots(url):
    """Lee robots.txt del portal (con nuestro User-Agent) y responde si la ruta está permitida."""
    partes = urlparse(url)
    url_robots = f"{partes.scheme}://{partes.netloc}/robots.txt"
    try:
        r = requests.get(url_robots, headers={"User-Agent": USER_AGENT}, timeout=30)
        rp = RobotFileParser()
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        ok = rp.can_fetch(USER_AGENT, url)
        registrar("02_scraping_web", url_robots, r.status_code, 0, f"robots.txt -> permitido={ok}")
        return ok
    except Exception as e:
        registrar("02_scraping_web", url_robots, "ERROR", 0, f"robots.txt no leído: {e}")
        return False


# ------------------------------------------------------------------
# BLOQUE 2. (a) SEC: descarga del PDF y lectura de parámetros
# ------------------------------------------------------------------
def numero(texto):
    """Convierte '1,547' o '33,6' o '2,172.00' en número."""
    texto = texto.strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", texto):  # separador de miles con coma
        texto = texto.replace(",", "")
    else:                                                 # coma decimal (ej. 33,6)
        texto = texto.replace(",", ".")
    return float(texto)


# Cada parámetro se busca con una expresión regular construida a partir del texto literal del PDF
PATRONES = {
    "van_despues_impuestos_musd": r"After-Tax NPV at [\d.]+% US\$ million \(?([\d,]+)\)?",
    "tasa_descuento_pct":        r"After-Tax NPV at ([\d.]+)%",
    "flujo_antes_impuestos_musd": r"Pre-Tax Net Cash Flow US\$ million \(?([\d,]+)\)?",
    "flujo_despues_impuestos_musd": r"After-Tax Cash Flow US\$ million \(?([\d,]+)\)?",
    "inversion_inicial_musd":    r"Initial Capital US\$ million \(?([\d,]+)\)?",
    "costo_cierre_musd":         r"closure costs total US\$([\d.,]+) million",
    "precio_oro_trs_usd_oz":     r"long term metal prices of US\$([\d,]+(?:\.\d+)?)/oz Au",
    "aisc_usd_oz":               r"\(AISC\) of US\$([\d,]+)/oz Au",
    "oro_pagable_koz":           r"Payable Metal.{0,400}?Au koz ([\d,]+)",
    "produccion_media_koz_anio": r"average annual gold production during operation is ([\d,]+) koz",
    "vida_mina_anios":           r"Mine Life: ([\d.]+) years",
    "impuesto_renta_pct":        r"Corporate income tax rate in Peru is ([\d.]+)%",
}

archivo_pdf = CRUDOS / f"datos_crudos_{CODIGO}_sec_trs_san_gabriel.pdf"
if permitido_por_robots(URL_TRS):
    time.sleep(1)
    try:
        r = requests.get(URL_TRS, headers={"User-Agent": USER_AGENT}, timeout=180)
        registrar("02_scraping_web", URL_TRS, r.status_code, 0, f"PDF descargado: {len(r.content):,} bytes")
        if r.status_code == 200:
            archivo_pdf.write_bytes(r.content)  # original intacto
    except Exception as e:
        registrar("02_scraping_web", URL_TRS, "ERROR", 0, str(e))
else:
    registrar("02_scraping_web", URL_TRS, "NO_PERMITIDO", 0, "robots.txt no permite la ruta: ver incidencias_fuente.md")

if archivo_pdf.exists():
    # 2.1 Se extrae el texto de las primeras páginas y se guarda como evidencia
    with pdfplumber.open(archivo_pdf) as pdf:
        n_total = len(pdf.pages)
        paginas = [pdf.pages[i].extract_text() or "" for i in range(min(PAGINAS_A_LEER, n_total))]
    (CRUDOS / f"datos_crudos_{CODIGO}_sec_trs_texto.txt").write_text(
        "\n\n=== PÁGINA SIGUIENTE ===\n\n".join(paginas), encoding="utf-8")

    # 2.2 Se busca cada parámetro; se guarda la página y la frase exacta para poder verificarlo
    filas = []
    for nombre, patron in PATRONES.items():
        hallado = None
        for n_pag, txt in enumerate(paginas, start=1):
            plano = re.sub(r"\s+", " ", txt)          # une saltos de línea
            m = re.search(patron, plano, flags=re.IGNORECASE)
            if m:
                inicio = max(m.start() - 60, 0)
                hallado = {"parametro": nombre, "valor": numero(m.group(1)), "pagina_pdf": n_pag,
                           "frase_literal": plano[inicio:m.end() + 20]}
                break
        if hallado is None:  # nunca se inventa un valor: se deja vacío y se avisa
            hallado = {"parametro": nombre, "valor": None, "pagina_pdf": None, "frase_literal": "NO ENCONTRADO"}
        filas.append(hallado)
        print(f"{nombre:32s} -> {hallado['valor']}  (pág. {hallado['pagina_pdf']})")

    parametros = pd.DataFrame(filas)
    parametros.to_csv(CRUDOS / f"datos_crudos_{CODIGO}_sec_trs_parametros.csv", index=False, encoding="utf-8")
    faltan = parametros["valor"].isna().sum()
    registrar("02_scraping_web", URL_TRS, "PARSEO", len(parametros) - faltan,
              f"parámetros encontrados {len(parametros) - faltan}/{len(parametros)} (PDF de {n_total} páginas)")

# ------------------------------------------------------------------
# BLOQUE 3. (b) FRED: tasa del Tesoro de EE. UU. a 10 años (DGS10), archivo CSV diario
# ------------------------------------------------------------------
time.sleep(1)
if permitido_por_robots(URL_FRED):
    time.sleep(1)
    try:
        r = requests.get(URL_FRED, headers={"User-Agent": USER_AGENT}, timeout=120)
        if r.status_code == 200 and b"DGS10" in r.content[:200]:
            (CRUDOS / f"datos_crudos_{CODIGO}_fred_DGS10.csv").write_bytes(r.content)  # original intacto
            n_filas = r.content.count(b"\n") - 1
            registrar("02_scraping_web", URL_FRED, r.status_code, n_filas, "FRED DGS10 (CSV) guardado")
        else:
            registrar("02_scraping_web", URL_FRED, r.status_code, 0,
                      "La respuesta no es el CSV esperado: documentar en incidencias_fuente.md")
    except Exception as e:
        registrar("02_scraping_web", URL_FRED, "ERROR", 0, str(e))
else:
    registrar("02_scraping_web", URL_FRED, "NO_PERMITIDO", 0, "robots.txt no permite la ruta")

print("\nListo. Revise datos_crudos/ y log_ejecucion.txt")
