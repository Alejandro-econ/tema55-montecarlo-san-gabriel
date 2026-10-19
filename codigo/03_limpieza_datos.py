# Autor: Alejandro Soto Antezana
# Código de matrícula: 2024200531K
# Tema 55: Riesgo del proyecto: simulación de Monte Carlo sobre precio, demanda y tipo de cambio
# Fecha de extracción: se registra automáticamente en log_ejecucion.txt al ejecutar
"""
LIMPIEZA Y UNIÓN DE LAS FUENTES
-------------------------------
Lee los archivos de datos_crudos/ (sin modificarlos), convierte fechas y números,
une todas las fuentes por la LLAVE COMÚN "fecha" (día) y genera:
  - datos_procesados/datos_procesados_2024200531K.csv   (base diaria para el análisis)
  - datos_procesados/parametros_proyecto_2024200531K.csv (parámetros de la mina San Gabriel)
  - salidas/tabla_cotejo_10_datos.csv (10 datos al azar para verificar contra la fuente)
  - el hash SHA-256 del archivo procesado (se imprime y se guarda en salidas/hash_sha256.txt)
Reglas: no se imputan valores; los atípicos se MARCAN pero no se borran.
"""

# ------------------------------------------------------------------
# BLOQUE 1. Librerías, rutas y constantes
# ------------------------------------------------------------------
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos_crudos"
PROCESADOS = RAIZ / "datos_procesados"
SALIDAS = RAIZ / "salidas"
PROCESADOS.mkdir(exist_ok=True)
SALIDAS.mkdir(exist_ok=True)
LOG = RAIZ / "log_ejecucion.txt"

CODIGO = "2024200531K"
SEMILLA = 531              # 4 últimos dígitos del código de matrícula (0531)
FECHA_INICIO = "2004-11-18"
FECHA_CORTE = "2026-08-31"
SERIES_BCRP = {"PD04704XD": "precio_oro", "PD04638PD": "tc",
               "PD04709XD": "embig_peru"}
MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7,
         "Ago": 8, "Set": 9, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12}


def registrar(mensaje, filas=""):
    ahora = datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{ahora} (Lima) | 03_limpieza_datos | filas={filas} | {mensaje}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


# ------------------------------------------------------------------
# BLOQUE 2. BCRP: fechas tipo "02.Ene.97" y valores "n.d."
# ------------------------------------------------------------------
def fecha_bcrp(texto):
    """'02.Ene.97' -> 1997-01-02 ; '03.Set.25' -> 2025-09-03"""
    dia, mes, anio = texto.split(".")
    anio = int(anio)
    anio = anio + 1900 if anio >= 90 else anio + 2000
    return pd.Timestamp(anio, MESES[mes], int(dia))


tablas = []
for codigo, nombre in SERIES_BCRP.items():
    datos = json.loads((CRUDOS / f"datos_crudos_{CODIGO}_bcrp_{codigo}.json").read_text(encoding="utf-8"))
    s = pd.DataFrame({
        "fecha": [fecha_bcrp(p["name"]) for p in datos["periods"]],
        nombre: pd.to_numeric([p["values"][0] for p in datos["periods"]], errors="coerce"),  # "n.d." -> vacío
    }).set_index("fecha")
    registrar(f"BCRP {codigo} ({nombre}): {s[nombre].notna().sum()} datos reales de {len(s)} fechas", len(s))
    tablas.append(s)

# ------------------------------------------------------------------
# BLOQUE 3. Yahoo Finance: precio y volumen del fondo GLD
# ------------------------------------------------------------------
gld = pd.read_csv(CRUDOS / f"datos_crudos_{CODIGO}_yahoo_GLD.csv")
gld = gld[pd.to_datetime(gld.iloc[:, 0], errors="coerce").notna()]   # quita filas de encabezado extra
gld["fecha"] = pd.to_datetime(gld.iloc[:, 0])
gld = gld.set_index("fecha")
yahoo = pd.DataFrame({
    "gld_cierre": pd.to_numeric(gld["Close"], errors="coerce"),
    "gld_volumen": pd.to_numeric(gld["Volume"], errors="coerce"),
})
registrar(f"Yahoo GLD: {yahoo['gld_cierre'].notna().sum()} días", len(yahoo))
tablas.append(yahoo)

# ------------------------------------------------------------------
# BLOQUE 4. FRED: tasa del Tesoro de EE. UU. a 10 años (los días sin dato vienen como "." o vacíos)
# ------------------------------------------------------------------
fred = pd.read_csv(CRUDOS / f"datos_crudos_{CODIGO}_fred_DGS10.csv", dtype=str)
fred = pd.DataFrame({
    "fecha": pd.to_datetime(fred.iloc[:, 0], errors="coerce"),
    "ust10": pd.to_numeric(fred.iloc[:, 1], errors="coerce"),
}).dropna(subset=["fecha"]).set_index("fecha")
registrar(f"FRED DGS10 (ust10): {fred['ust10'].notna().sum()} datos reales de {len(fred)} fechas", len(fred))
tablas.append(fred)

# ------------------------------------------------------------------
# BLOQUE 5. Unión por la llave común "fecha" y recorte al periodo declarado
# ------------------------------------------------------------------
base = pd.concat(tablas, axis=1).sort_index()
base = base.loc[FECHA_INICIO:FECHA_CORTE]
# Demanda de inversión en oro: monto negociado diario del fondo GLD (US$ millones) = precio x volumen
base["gld_monto_musd"] = base["gld_cierre"] * base["gld_volumen"] / 1e6
base["riesgo_pais_tasa"] = base["ust10"] + base["embig_peru"] / 100   # % = tasa EE. UU. + spread EMBIG

VARIABLES_NUCLEO = ["precio_oro", "tc", "ust10", "embig_peru", "gld_monto_musd"]
antes = len(base)
base = base.dropna(subset=VARIABLES_NUCLEO)   # solo días en que TODAS las fuentes tienen dato real
registrar(f"Unión: {antes} fechas -> {len(base)} días con las 5 variables núcleo completas", len(base))

# ------------------------------------------------------------------
# BLOQUE 6. Rendimientos logarítmicos diarios y marca de atípicos (|z| > 5)
# ------------------------------------------------------------------
var_demanda = "gld_monto_musd"
base["r_oro"] = np.log(base["precio_oro"]).diff()
base["r_tc"] = np.log(base["tc"]).diff()
base["r_demanda"] = np.log(base[var_demanda]).diff()
base["d_riesgo_pais"] = base["riesgo_pais_tasa"].diff()
for col in ["r_oro", "r_tc", "r_demanda", "d_riesgo_pais"]:
    z = (base[col] - base[col].mean()) / base[col].std()
    base[f"atipico_{col}"] = (z.abs() > 5).astype(int)
    registrar(f"Atípicos marcados (|z|>5) en {col}: {int(base[f'atipico_{col}'].sum())}")

base.index.name = "fecha"
base = base.reset_index()
base["fecha"] = base["fecha"].dt.strftime("%Y-%m-%d")

archivo_proc = PROCESADOS / f"datos_procesados_{CODIGO}.csv"
base.to_csv(archivo_proc, index=False, encoding="utf-8", float_format="%.6f")
registrar(f"Primera fecha con datos: {base['fecha'].iloc[0]} | última: {base['fecha'].iloc[-1]}", len(base))

# ------------------------------------------------------------------
# BLOQUE 7. Parámetros del proyecto (desde el PDF oficial de la SEC)
# ------------------------------------------------------------------
param = pd.read_csv(CRUDOS / f"datos_crudos_{CODIGO}_sec_trs_parametros.csv")
param.to_csv(PROCESADOS / f"parametros_proyecto_{CODIGO}.csv", index=False, encoding="utf-8")
if param["valor"].isna().any():
    registrar("AVISO: faltan parámetros del TRS: " + ", ".join(param.loc[param["valor"].isna(), "parametro"]))

# ------------------------------------------------------------------
# BLOQUE 8. Hash SHA-256 del archivo procesado (huella digital del archivo)
# ------------------------------------------------------------------
sha = hashlib.sha256(archivo_proc.read_bytes()).hexdigest()
(SALIDAS / "hash_sha256.txt").write_text(f"{archivo_proc.name}  {sha}\n", encoding="utf-8")
registrar(f"SHA-256 de {archivo_proc.name}: {sha}", len(base))

# ------------------------------------------------------------------
# BLOQUE 9. Tabla de cotejo: 10 días al azar para verificar contra la web del BCRP
# ------------------------------------------------------------------
rng = np.random.default_rng(SEMILLA)
muestra = base.iloc[rng.choice(len(base), size=10, replace=False)].sort_values("fecha")
crudo_oro = pd.read_csv(CRUDOS / f"datos_crudos_{CODIGO}_bcrp_PD04704XD.csv")
crudo_oro["fecha"] = crudo_oro["fecha_bcrp"].map(fecha_bcrp).dt.strftime("%Y-%m-%d")
crudo_tc = pd.read_csv(CRUDOS / f"datos_crudos_{CODIGO}_bcrp_PD04638PD.csv")
crudo_tc["fecha"] = crudo_tc["fecha_bcrp"].map(fecha_bcrp).dt.strftime("%Y-%m-%d")
cotejo = (muestra[["fecha", "precio_oro", "tc"]]
          .merge(crudo_oro[["fecha", "fecha_bcrp", "valor_texto"]].rename(columns={"valor_texto": "oro_crudo"}), on="fecha")
          .merge(crudo_tc[["fecha", "valor_texto"]].rename(columns={"valor_texto": "tc_crudo"}), on="fecha"))
cotejo["web_oro"] = "https://estadisticas.bcrp.gob.pe/estadisticas/series/diarias/resultados/PD04704XD/html"
cotejo["web_tc"] = "https://estadisticas.bcrp.gob.pe/estadisticas/series/diarias/resultados/PD04638PD/html"
cotejo.to_csv(SALIDAS / "tabla_cotejo_10_datos.csv", index=False, encoding="utf-8")
print("\nTabla de cotejo (compare con la web del BCRP):")
print(cotejo[["fecha", "fecha_bcrp", "oro_crudo", "precio_oro", "tc_crudo", "tc"]].to_string(index=False))

print("\nObservaciones reales por variable en la base procesada:")
print(base[["precio_oro", "tc", "ust10", "embig_peru", "gld_monto_musd",
            "gld_cierre", "gld_volumen"]].notna().sum().to_string())
