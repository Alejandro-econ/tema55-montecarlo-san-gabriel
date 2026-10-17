# Autor: Alejandro Soto Antezana
# Código de matrícula: 2024200531K
# Tema 55: Riesgo del proyecto: simulación de Monte Carlo sobre precio, demanda y tipo de cambio
# Fecha de extracción: se registra automáticamente en log_ejecucion.txt al ejecutar
"""
VÍA 1 — EXTRACCIÓN POR API
---------------------------
Este script descarga, sin ninguna intervención manual:
  (a) 4 series DIARIAS del BCRP mediante su API REST pública (BCRPData).
  (b) El fondo de oro SPDR Gold Shares (ticker GLD) desde Yahoo Finance (librería yfinance).
Cada respuesta se guarda TAL COMO LLEGA en la carpeta datos_crudos/ (no se edita nunca).
"""

# ------------------------------------------------------------------
# BLOQUE 1. Librerías
# ------------------------------------------------------------------
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

# ------------------------------------------------------------------
# BLOQUE 2. Parámetros congelados (numeral 2.4.5 de la consigna)
#   Las fechas son constantes; nunca se usa "hoy".
# ------------------------------------------------------------------
CODIGO = "2024200531K"
FECHA_INICIO = "2004-11-18"   # primer día de cotización del fondo GLD (inicio de la serie de demanda)
FECHA_CORTE = "2026-08-31"    # último día del periodo de estudio

# Series diarias del BCRP: código -> nombre corto de la variable
SERIES_BCRP = {
    "PD04704XD": "precio_oro",   # Oro (Londres, US$ por onza troy)
    "PD04638PD": "tc",           # Tipo de cambio interbancario venta (S/ por US$)
    "PD04719XD": "ust10",        # Bonos del Tesoro de EE. UU. a 10 años (%)
    "PD04709XD": "embig_peru",   # Spread EMBIG Perú (puntos básicos)
}
URL_BCRP = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{codigo}/json/{inicio}/{fin}"

TICKER_YAHOO = "GLD"  # SPDR Gold Shares: mayor fondo de oro físico del mundo
USER_AGENT = "Investigacion academica UNCP - Alejandro Soto Antezana (e_2024200531K@uncp.edu.pe)"

# ------------------------------------------------------------------
# BLOQUE 3. Rutas relativas a la carpeta del proyecto (sin C:\Users\...)
# ------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos_crudos"
CRUDOS.mkdir(exist_ok=True)
LOG = RAIZ / "log_ejecucion.txt"


def registrar(script, url, http, filas, mensaje=""):
    """Escribe una línea en log_ejecucion.txt: fecha y hora de Lima, URL, código HTTP y filas."""
    ahora = datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{ahora} (Lima) | {script} | HTTP {http} | filas={filas} | {url} | {mensaje}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


# ------------------------------------------------------------------
# BLOQUE 4. Descarga del BCRP (una solicitud por serie, con pausa de 1 s)
# ------------------------------------------------------------------
def descargar_bcrp(codigo, nombre):
    url = URL_BCRP.format(codigo=codigo, inicio=FECHA_INICIO, fin=FECHA_CORTE)
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
        texto = r.text
        # 4.1 Se guarda la respuesta original, sin tocarla
        (CRUDOS / f"datos_crudos_{CODIGO}_bcrp_{codigo}.json").write_text(texto, encoding="utf-8")
        datos = json.loads(texto)
        periodos = datos.get("periods", [])
        # 4.2 Versión tabular "tal como sale": fecha y valor como TEXTO (incluye los "n.d.")
        tabla = pd.DataFrame(
            {"fecha_bcrp": [p["name"] for p in periodos],
             "valor_texto": [p["values"][0] for p in periodos]}
        )
        tabla.to_csv(CRUDOS / f"datos_crudos_{CODIGO}_bcrp_{codigo}.csv", index=False, encoding="utf-8")
        nombre_serie = datos.get("config", {}).get("series", [{}])[0].get("name", "")
        registrar("01_extraccion_api", url, r.status_code, len(tabla), f"{nombre}: {nombre_serie}")
    except Exception as e:  # un error se registra y el script continúa con la siguiente serie
        registrar("01_extraccion_api", url, "ERROR", 0, f"{nombre}: {e}")


for codigo, nombre in SERIES_BCRP.items():
    descargar_bcrp(codigo, nombre)
    time.sleep(1)  # pausa mínima de 1 segundo entre solicitudes

# ------------------------------------------------------------------
# BLOQUE 5. Descarga de Yahoo Finance (GLD: precio y volumen diario)
#   yfinance no incluye el día final, por eso se suma un día a FECHA_CORTE.
# ------------------------------------------------------------------
fin_yahoo = (datetime.strptime(FECHA_CORTE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
try:
    gld = yf.download(TICKER_YAHOO, start=FECHA_INICIO, end=fin_yahoo,
                      auto_adjust=False, progress=False, actions=True)
    # Las versiones nuevas de yfinance devuelven columnas de dos niveles: se deja solo el primero
    if isinstance(gld.columns, pd.MultiIndex):
        gld.columns = gld.columns.get_level_values(0)
    gld.to_csv(CRUDOS / f"datos_crudos_{CODIGO}_yahoo_{TICKER_YAHOO}.csv", encoding="utf-8")
    registrar("01_extraccion_api", f"yfinance.download('{TICKER_YAHOO}', {FECHA_INICIO}, {fin_yahoo})",
              200 if len(gld) else "SIN_DATOS", len(gld), "Yahoo Finance GLD (Open, High, Low, Close, Adj Close, Volume)")
except Exception as e:
    registrar("01_extraccion_api", f"yfinance {TICKER_YAHOO}", "ERROR", 0, str(e))

print("\nListo. Revise la carpeta datos_crudos/ y el archivo log_ejecucion.txt")
