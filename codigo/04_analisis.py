# Autor: Alejandro Soto Antezana
# Código de matrícula: 2024200531K
# Tema 55: Riesgo del proyecto: simulación de Monte Carlo sobre precio, demanda y tipo de cambio
# Fecha de extracción: se registra automáticamente en log_ejecucion.txt al ejecutar
"""
ANÁLISIS: PRUEBAS ESTADÍSTICAS + SIMULACIÓN DE MONTE CARLO DEL VAN DE SAN GABRIEL
-------------------------------------------------------------------------------
Genera TODAS las tablas y figuras del artículo en la carpeta salidas/:
  Parte A. Historia diaria (datos reales): descriptivos, ADF, cointegración, correlaciones,
           regresión con errores Newey-West y causalidad de Granger.
  Parte B. Modelo del proyecto: flujo de caja calibrado con el informe técnico oficial (SEC)
           y validación contra el VAN oficial.
  Parte C. Monte Carlo (10 000 simulaciones, semilla 531): bootstrap por bloques de los
           rendimientos diarios reales del oro, la demanda, el tipo de cambio y el riesgo país.
  Parte D. Regresión de sensibilidad del VAN (prueba F y estadísticos t) y contraste de hipótesis.
"""

# ------------------------------------------------------------------
# BLOQUE 1. Librerías, rutas y parámetros fijos
# ------------------------------------------------------------------
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.tsa.stattools import adfuller, coint, grangercausalitytests

RAIZ = Path(__file__).resolve().parent.parent
PROCESADOS = RAIZ / "datos_procesados"
SALIDAS = RAIZ / "salidas"
SALIDAS.mkdir(exist_ok=True)
LOG = RAIZ / "log_ejecucion.txt"

CODIGO = "2024200531K"
SEMILLA = 531          # 4 últimos dígitos del código de matrícula 2024200531K -> 0531
N_SIM = 10_000         # número de simulaciones
LARGO_BLOQUE = 21      # 21 días hábiles = 1 mes (conserva la dependencia de corto plazo)
DIAS_ANIO = 252        # días hábiles por año (12 bloques de 21 días)
ALFA = 0.05            # nivel de significancia

warnings.filterwarnings("ignore", category=FutureWarning)  # avisos de versiones futuras de statsmodels
AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#6b6a64"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6,
                     "figure.dpi": 150, "savefig.bbox": "tight"})


def registrar(mensaje):
    ahora = datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{ahora} (Lima) | 04_analisis | {mensaje}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def guardar(tabla, nombre, decimales=4, indice=False):
    """Guarda cada tabla en CSV (para revisar) y en .tex (para pegar en el artículo LaTeX)."""
    tabla.to_csv(SALIDAS / f"{nombre}.csv", index=indice, encoding="utf-8")
    tabla.to_latex(SALIDAS / f"{nombre}.tex", index=indice, float_format=f"%.{decimales}f", escape=True)
    TABLAS[nombre] = tabla


TABLAS = {}

# ------------------------------------------------------------------
# BLOQUE 2. Carga de la base diaria y de los parámetros del proyecto
# ------------------------------------------------------------------
base = pd.read_csv(PROCESADOS / f"datos_procesados_{CODIGO}.csv", parse_dates=["fecha"])
HAY_SPDR = base["demanda_ton"].notna().any()
VAR_DEMANDA = "demanda_ton" if HAY_SPDR else "gld_monto_musd"
registrar(f"Base: {len(base)} días, de {base['fecha'].min():%Y-%m-%d} a {base['fecha'].max():%Y-%m-%d}; "
          f"demanda medida con '{VAR_DEMANDA}'")

par = pd.read_csv(PROCESADOS / f"parametros_proyecto_{CODIGO}.csv").set_index("parametro")["valor"]
if par.isna().any():
    raise SystemExit("Faltan parámetros del informe técnico (ver salida del script 02). No se inventan valores.")

# ------------------------------------------------------------------
# PARTE A. HISTORIA DIARIA (DATOS REALES)
# ------------------------------------------------------------------
# A.1 Estadística descriptiva de niveles y rendimientos
niveles = {"Precio del oro (US$/oz)": "precio_oro",
           ("Demanda: oro en el fondo GLD (t)" if HAY_SPDR else "Demanda: monto negociado GLD (US$ mm)"): VAR_DEMANDA,
           "Tipo de cambio (S/ por US$)": "tc",
           "Tasa EE. UU. 10 años (%)": "ust10",
           "EMBIG Perú (pbs)": "embig_peru"}
rend = {"Rend. log. oro": "r_oro", "Rend. log. demanda": "r_demanda",
        "Rend. log. tipo de cambio": "r_tc", "Cambio riesgo país (p.p.)": "d_riesgo_pais"}
filas = []
for etiqueta, col in {**niveles, **rend}.items():
    x = base[col].dropna()
    filas.append({"Variable": etiqueta, "N": len(x), "Media": x.mean(), "Desv. est.": x.std(),
                  "Mínimo": x.min(), "Mediana": x.median(), "Máximo": x.max(),
                  "Asimetría": stats.skew(x), "Curtosis": stats.kurtosis(x)})
guardar(pd.DataFrame(filas), "tabla1_descriptivos")

# A.2 Prueba de raíz unitaria ADF (H0: la serie tiene raíz unitaria = no estacionaria)
filas = []
for etiqueta, serie in [("ln oro", np.log(base["precio_oro"])), ("ln demanda", np.log(base[VAR_DEMANDA])),
                        ("ln tipo de cambio", np.log(base["tc"])), ("Riesgo país (%)", base["riesgo_pais_tasa"]),
                        ("Rend. oro", base["r_oro"]), ("Rend. demanda", base["r_demanda"]),
                        ("Rend. tipo de cambio", base["r_tc"]), ("Cambio riesgo país", base["d_riesgo_pais"])]:
    est, p, rezagos, nobs, crit, _ = adfuller(serie.dropna(), autolag="AIC")
    filas.append({"Serie": etiqueta, "Estadístico ADF": est, "Valor p": p, "Rezagos": rezagos, "N": nobs,
                  "Valor crítico 5 %": crit["5%"],
                  "Conclusión": "Estacionaria" if p < ALFA else "Raíz unitaria"})
guardar(pd.DataFrame(filas), "tabla2_adf")

# A.3 Cointegración de Engle-Granger entre ln oro y ln demanda (¿relación de largo plazo?)
est, p, crit = coint(np.log(base["precio_oro"]), np.log(base[VAR_DEMANDA]))
guardar(pd.DataFrame([{"Relación": "ln oro ~ ln demanda", "Estadístico EG": est, "Valor p": p,
                       "Valor crítico 5 %": crit[1],
                       "Conclusión": "Cointegradas" if p < ALFA else "No cointegradas"}]), "tabla3_cointegracion")
COINTEGRADAS = p < ALFA

# A.4 Correlaciones de Pearson entre rendimientos diarios (con valor p)
R = base[["r_oro", "r_demanda", "r_tc", "d_riesgo_pais"]].dropna()
filas = []
nombres = {"r_oro": "Oro", "r_demanda": "Demanda", "r_tc": "Tipo de cambio", "d_riesgo_pais": "Riesgo país"}
cols = list(nombres)
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        r, p = stats.pearsonr(R[cols[i]], R[cols[j]])
        filas.append({"Par": f"{nombres[cols[i]]} - {nombres[cols[j]]}", "Correlación": r, "Valor p": p, "N": len(R)})
guardar(pd.DataFrame(filas), "tabla4_correlaciones")
corr_oro_tc, p_oro_tc = stats.pearsonr(R["r_oro"], R["r_tc"])

# A.5 Regresión diaria: rendimiento del oro explicado por demanda, tipo de cambio y riesgo país
#     En primeras diferencias (rendimientos) y con errores Newey-West (HAC, 5 rezagos)
X = sm.add_constant(R[["r_demanda", "r_tc", "d_riesgo_pais"]])
mod_hist = sm.OLS(R["r_oro"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
dw = sm.stats.durbin_watson(mod_hist.resid)
tabla5 = pd.DataFrame({"Coeficiente": mod_hist.params, "Error est. (NW)": mod_hist.bse,
                       "Estadístico z": mod_hist.tvalues, "Valor p": mod_hist.pvalues})
tabla5.index = ["Constante", "Rend. demanda", "Rend. tipo de cambio", "Cambio riesgo país"]
tabla5.loc["Prueba F (NW)", ["Coeficiente", "Valor p"]] = [float(mod_hist.fvalue), float(mod_hist.f_pvalue)]
tabla5.loc["R cuadrado", "Coeficiente"] = mod_hist.rsquared
tabla5.loc["Durbin-Watson", "Coeficiente"] = dw
tabla5.loc["N", "Coeficiente"] = mod_hist.nobs
guardar(tabla5.reset_index().rename(columns={"index": "Variable"}), "tabla5_regresion_historica")

# A.6 Causalidad de Granger (5 rezagos): ¿la demanda anticipa al oro? ¿y al revés?
filas = []
for causa, efecto in [("r_demanda", "r_oro"), ("r_oro", "r_demanda")]:
    try:   # statsmodels >= 0.15 ya no usa el argumento verbose
        res_g = grangercausalitytests(R[[efecto, causa]], maxlag=5)
    except TypeError:
        res_g = grangercausalitytests(R[[efecto, causa]], maxlag=5, verbose=False)
    g = res_g[5][0]["ssr_ftest"]
    filas.append({"H0": f"{nombres[causa]} NO causa en sentido de Granger a {nombres[efecto]}",
                  "Estadístico F": g[0], "Valor p": g[1], "gl": f"({int(g[2])}, {int(g[3])})",
                  "Decisión": "Se rechaza H0" if g[1] < ALFA else "No se rechaza H0"})
guardar(pd.DataFrame(filas), "tabla6_granger")

# ------------------------------------------------------------------
# PARTE B. MODELO DEL PROYECTO CALIBRADO CON EL INFORME TÉCNICO (SEC)
# ------------------------------------------------------------------
Q_TOTAL = par["oro_pagable_koz"] * 1_000                  # onzas pagables en toda la vida de la mina
N_ANIOS = int(round(par["vida_mina_anios"]))              # años de producción (14.2 -> 14)
Q_ANIO = Q_TOTAL / N_ANIOS                                # perfil uniforme (supuesto declarado)
I0 = par["inversion_inicial_musd"] * 1e6                  # inversión pendiente en el año 0
CIERRE = par["costo_cierre_musd"] * 1e6                   # costo de cierre, al final
K0 = par["tasa_descuento_pct"] / 100                      # WACC usado por Buenaventura
P_TRS = par["precio_oro_trs_usd_oz"]
FC_ANTES = par["flujo_antes_impuestos_musd"] * 1e6
FC_DESP = par["flujo_despues_impuestos_musd"] * 1e6
# Costo unitario implícito: el que hace que el flujo antes de impuestos sea el oficial
C_UNIT = P_TRS - (FC_ANTES + I0 + CIERRE) / Q_TOTAL
# Tasa efectiva de impuestos sobre el flujo operativo (renta, regalías, IEM, participación)
TAU = 1 - (FC_DESP + I0 + CIERRE) / (FC_ANTES + I0 + CIERRE)


def calcular_van(precios, k, tc=None):
    """precios: matriz (simulaciones x años 1..N+1); k: tasa por simulación; tc: matriz (sim x años 0..N+1).
    Devuelve el VAN en US$ y, si se da el tipo de cambio, el VAN en soles."""
    t = np.arange(1, N_ANIOS + 1)
    margen = Q_ANIO * (precios[:, :N_ANIOS] - C_UNIT)
    flujo = margen - TAU * np.maximum(margen, 0)            # impuestos solo si hay ganancia
    desc = (1 + k[:, None]) ** t
    desc_cierre = (1 + k) ** (N_ANIOS + 1)
    van_usd = -I0 + (flujo / desc).sum(axis=1) - CIERRE / desc_cierre
    if tc is None:
        return van_usd, None
    van_pen = (-I0 * tc[:, 0] + (flujo * tc[:, 1:N_ANIOS + 1] / desc).sum(axis=1)
               - CIERRE * tc[:, N_ANIOS + 1] / desc_cierre)
    return van_usd, van_pen


van_base, _ = calcular_van(np.full((1, N_ANIOS + 1), P_TRS), np.array([K0]))
tabla_val = pd.DataFrame([
    ("Oro pagable en la vida de la mina (koz)", par["oro_pagable_koz"], "TRS, Tabla 1-2"),
    ("Vida de la mina (años)", par["vida_mina_anios"], "TRS, sección 1.2"),
    ("Producción anual usada (koz/año)", Q_ANIO / 1000, "Cálculo: oro pagable / años"),
    ("Producción media anual según TRS (koz/año)", par["produccion_media_koz_anio"], "TRS, sección 1.2.2"),
    ("Inversión pendiente (US$ mm)", I0 / 1e6, "TRS, Tabla 1-2"),
    ("Costo de cierre (US$ mm)", CIERRE / 1e6, "TRS, sección 1.2.1.3"),
    ("Precio del oro del TRS (US$/oz)", P_TRS, "TRS, sección 1.2.2"),
    ("AISC del TRS (US$/oz)", par["aisc_usd_oz"], "TRS, sección 1.2.2"),
    ("Costo unitario implícito (US$/oz)", C_UNIT, "Cálculo con flujos del TRS"),
    ("Tasa efectiva de impuestos (%)", TAU * 100, "Cálculo con flujos del TRS"),
    ("Tasa de descuento WACC (%)", K0 * 100, "TRS, Tabla 1-2"),
    ("VAN después de impuestos oficial (US$ mm)", par["van_despues_impuestos_musd"], "TRS, Tabla 1-2"),
    ("VAN del modelo con precio TRS (US$ mm)", van_base[0] / 1e6, "Modelo propio"),
    ("Diferencia modelo vs. oficial (%)", (van_base[0] / 1e6 / par["van_despues_impuestos_musd"] - 1) * 100, "Validación"),
], columns=["Concepto", "Valor", "Fuente"])
guardar(tabla_val, "tabla7_parametros_y_validacion", decimales=2)
registrar(f"Validación: VAN modelo {van_base[0]/1e6:,.1f} vs oficial {par['van_despues_impuestos_musd']:,.1f} US$ mm")

# ------------------------------------------------------------------
# PARTE C. MONTE CARLO: BOOTSTRAP POR BLOQUES DE LOS RENDIMIENTOS REALES
# ------------------------------------------------------------------
# Idea: para fabricar un "año futuro" se pegan 12 meses (bloques de 21 días) elegidos al azar
# de la historia real. Así se respeta la volatilidad, las colas gordas y la correlación
# que tuvieron juntas las 4 variables el MISMO día.
M = R[["r_oro", "r_demanda", "r_tc", "d_riesgo_pais"]].to_numpy()
# Escenario principal "sin tendencia" (martingala): se quita la media de cada rendimiento y, en las
# variables en logaritmos, también la mitad de su varianza, para que el precio ESPERADO futuro sea
# igual al de hoy (no se supone que el oro seguirá subiendo como en el pasado).
M_SIN_TENDENCIA = M - M.mean(axis=0)
M_SIN_TENDENCIA[:, :3] -= 0.5 * M[:, :3].var(axis=0)


def simular_bloques(matriz, anios, rng):
    """Devuelve un arreglo (N_SIM x anios x 4) con la suma anual de rendimientos diarios."""
    T = len(matriz)
    acum = np.vstack([np.zeros(matriz.shape[1]), np.cumsum(matriz, axis=0)])
    bloques_por_anio = DIAS_ANIO // LARGO_BLOQUE
    inicios = rng.integers(0, T - LARGO_BLOQUE, size=(N_SIM, anios, bloques_por_anio))
    sumas = acum[inicios + LARGO_BLOQUE] - acum[inicios]           # suma de cada bloque
    return sumas.sum(axis=2)


def escenario(nombre, matriz, p0, tc0, rng):
    anios = N_ANIOS + 1                                             # +1 para el año de cierre
    s = simular_bloques(matriz, anios, rng)
    precios = p0 * np.exp(np.cumsum(s[:, :, 0], axis=1))
    demanda_idx = np.exp(np.cumsum(s[:, :, 1], axis=1))            # índice (hoy = 1)
    tc = np.hstack([np.full((N_SIM, 1), tc0), tc0 * np.exp(np.cumsum(s[:, :, 2], axis=1))])
    k = np.maximum(K0 + s[:, 0, 3] / 100, 0.01)                     # WACC + cambio del riesgo país en 1 año
    van_usd, van_pen = calcular_van(precios, k, tc)
    return {"nombre": nombre, "precios": precios, "demanda": demanda_idx, "tc": tc, "k": k,
            "van_usd": van_usd / 1e6, "van_pen": van_pen / 1e6, "p0": p0, "tc0": tc0}


rng = np.random.default_rng(SEMILLA)
P_MERCADO = base["precio_oro"].iloc[-1]
TC_MERCADO = base["tc"].iloc[-1]
FECHA_ULT = base["fecha"].iloc[-1].strftime("%Y-%m-%d")
esc_B = escenario(f"B. Precio de mercado al {FECHA_ULT}", M_SIN_TENDENCIA, P_MERCADO, TC_MERCADO, rng)
esc_A = escenario("A. Precio del informe técnico", M_SIN_TENDENCIA, P_TRS, TC_MERCADO, rng)
esc_C = escenario("C. Robustez: B con tendencia histórica", M, P_MERCADO, TC_MERCADO, rng)
registrar(f"Monte Carlo: {N_SIM} simulaciones por escenario, semilla {SEMILLA}, "
          f"bloques de {LARGO_BLOQUE} días, P0 mercado = {P_MERCADO:,.2f} US$/oz, TC0 = {TC_MERCADO:.4f}")


def resumen(v):
    p5 = np.percentile(v, 5)
    return {"Media": v.mean(), "Desv. est.": v.std(ddof=1), "P5 (VaR 95 %)": p5,
            "Mediana": np.median(v), "P95": np.percentile(v, 95),
            "CVaR 95 %": v[v <= p5].mean(), "Prob. VAN < 0 (%)": (v < 0).mean() * 100}


filas = []
for e in [esc_A, esc_B, esc_C]:
    filas.append({"Escenario": e["nombre"], "Moneda": "US$ mm", **resumen(e["van_usd"])})
    filas.append({"Escenario": e["nombre"], "Moneda": "S/ mm", **resumen(e["van_pen"])})
guardar(pd.DataFrame(filas), "tabla8_distribucion_van", decimales=2)
pd.DataFrame({"van_usd_mm_A": esc_A["van_usd"], "van_usd_mm_B": esc_B["van_usd"], "van_pen_mm_B": esc_B["van_pen"],
              "van_usd_mm_C": esc_C["van_usd"], "wacc_B": esc_B["k"]}).to_csv(
    SALIDAS / "simulaciones_van.csv", index=False, float_format="%.4f")

# ------------------------------------------------------------------
# PARTE D. SENSIBILIDAD DEL VAN (PRUEBA F Y t) Y CONTRASTE DE HIPÓTESIS
# ------------------------------------------------------------------
# Cada simulación se resume en 4 "factores" y se regresiona el VAN en soles sobre ellos.
# Los factores se estandarizan (media 0, desv. 1): el coeficiente mide cuántos millones
# cambia el VAN cuando el factor sube 1 desviación estándar -> se pueden comparar entre sí.
fact = pd.DataFrame({
    "Precio del oro": np.log(esc_B["precios"][:, :N_ANIOS]).mean(axis=1),
    "Demanda": np.log(esc_B["demanda"][:, N_ANIOS - 1]),
    "Tipo de cambio": np.log(esc_B["tc"][:, 1:]).mean(axis=1),
    "Riesgo país (WACC)": esc_B["k"],
})
Z = (fact - fact.mean()) / fact.std()
mod_sens = sm.OLS(esc_B["van_pen"], sm.add_constant(Z)).fit(cov_type="HC1")
tabla9 = pd.DataFrame({"Coef. estandarizado (S/ mm)": mod_sens.params, "Error est. (HC1)": mod_sens.bse,
                       "Estadístico t": mod_sens.tvalues, "Valor p": mod_sens.pvalues})
tabla9.loc["Prueba F", ["Coef. estandarizado (S/ mm)", "Valor p"]] = [float(mod_sens.fvalue), float(mod_sens.f_pvalue)]
tabla9.loc["R cuadrado", "Coef. estandarizado (S/ mm)"] = mod_sens.rsquared
tabla9.loc["N", "Coef. estandarizado (S/ mm)"] = mod_sens.nobs
guardar(tabla9.reset_index().rename(columns={"index": "Factor"}), "tabla9_sensibilidad_van", decimales=3)

# Pruebas de las hipótesis
b = mod_sens.params.drop("const")
mayor = b.abs().idxmax()
van_trs = par["van_despues_impuestos_musd"]
t_media = stats.ttest_1samp(esc_B["van_usd"], van_trs, alternative="greater")
negativos = int((esc_B["van_usd"] < 0).sum())
binom = stats.binomtest(negativos, N_SIM, p=0.05, alternative="less")
coef_dem = mod_hist.params["r_demanda"]
p_dem = mod_hist.pvalues["r_demanda"]
p_corr_neg = p_oro_tc / 2 if corr_oro_tc < 0 else 1 - p_oro_tc / 2          # prueba de una cola
cv_usd = esc_B["van_usd"].std() / abs(esc_B["van_usd"].mean())
cv_pen = esc_B["van_pen"].std() / abs(esc_B["van_pen"].mean())

contraste = pd.DataFrame([
    {"Hipótesis": "HG: precio, demanda, TC y riesgo país explican conjuntamente el VAN",
     "Prueba": "F de la regresión de sensibilidad", "Estadístico": float(mod_sens.fvalue),
     "Valor p": float(mod_sens.f_pvalue), "Decisión": "Se rechaza H0" if mod_sens.f_pvalue < ALFA else "No se rechaza H0"},
    {"Hipótesis": "HE1: el precio del oro es el factor de mayor efecto sobre el VAN",
     "Prueba": f"t del coeficiente; mayor |coef.| = {mayor}", "Estadístico": float(mod_sens.tvalues["Precio del oro"]),
     "Valor p": float(mod_sens.pvalues["Precio del oro"]),
     "Decisión": "Se acepta H1" if (mayor == "Precio del oro" and mod_sens.pvalues["Precio del oro"] < ALFA) else "No se acepta H1"},
    {"Hipótesis": "HE2: la demanda de inversión en oro se asocia positivamente con su precio",
     "Prueba": "z (Newey-West) del coef. de demanda, regresión diaria", "Estadístico": float(mod_hist.tvalues["r_demanda"]),
     "Valor p": float(p_dem / 2 if coef_dem > 0 else 1 - p_dem / 2),
     "Decisión": "Se acepta H1" if (coef_dem > 0 and p_dem / 2 < ALFA) else "No se acepta H1"},
    {"Hipótesis": "HE3: el tipo de cambio se mueve en sentido contrario al oro (cobertura natural)",
     "Prueba": f"Correlación de Pearson (una cola); CV VAN S/ = {cv_pen:.3f} vs US$ = {cv_usd:.3f}",
     "Estadístico": corr_oro_tc, "Valor p": p_corr_neg,
     "Decisión": "Se acepta H1" if p_corr_neg < ALFA else "No se acepta H1"},
    {"Hipótesis": "HE4a: el VAN esperado a precios de mercado supera el VAN oficial",
     "Prueba": "t de una muestra (una cola)", "Estadístico": float(t_media.statistic),
     "Valor p": float(t_media.pvalue), "Decisión": "Se acepta H1" if t_media.pvalue < ALFA else "No se acepta H1"},
    {"Hipótesis": "HE4b: la probabilidad de VAN negativo es menor que 5 %",
     "Prueba": f"Binomial: {negativos} de {N_SIM} simulaciones con VAN < 0", "Estadístico": negativos / N_SIM,
     "Valor p": float(binom.pvalue), "Decisión": "Se acepta H1" if binom.pvalue < ALFA else "No se acepta H1"},
])
guardar(contraste, "tabla10_contraste_hipotesis", decimales=4)

# ------------------------------------------------------------------
# BLOQUE FIGURAS
# ------------------------------------------------------------------
# Figura 1: las cuatro variables diarias (paneles separados: cada una con su propia escala)
fig, ax = plt.subplots(2, 2, figsize=(10, 6), sharex=True)
for a, (col, tit) in zip(ax.ravel(), [("precio_oro", "Precio del oro (US$/oz) - BCRP"),
                                      (VAR_DEMANDA, "Demanda: oro en el fondo GLD (t) - SPDR" if HAY_SPDR else "Demanda: monto negociado GLD (US$ mm) - Yahoo"),
                                      ("tc", "Tipo de cambio (S/ por US$) - BCRP"),
                                      ("riesgo_pais_tasa", "Tasa EE. UU. 10 años + EMBIG Perú (%) - BCRP")]):
    a.plot(base["fecha"], base[col], color=AZUL, linewidth=1)
    a.set_title(tit, fontsize=9, loc="left")
fig.tight_layout()
fig.savefig(SALIDAS / "figura1_series_diarias.png")
plt.close(fig)

# Figura 2: histograma del VAN (escenario B) con el VAN oficial como referencia
fig, a = plt.subplots(figsize=(8, 4.5))
a.hist(esc_B["van_usd"], bins=80, color=AZUL, edgecolor="white", linewidth=0.4)
a.axvline(van_trs, color=GRIS, linestyle="--", linewidth=1.5)
a.text(van_trs, a.get_ylim()[1] * 0.92, f"  VAN oficial TRS = {van_trs:,.0f}", color=GRIS, fontsize=9)
a.axvline(0, color="black", linewidth=1)
a.set_xlabel("VAN después de impuestos (US$ millones)")
a.set_ylabel("Número de simulaciones")
a.set_title(f"Distribución del VAN de San Gabriel - {N_SIM:,} simulaciones (escenario B)", loc="left", fontsize=10)
fig.savefig(SALIDAS / "figura2_histograma_van.png")
plt.close(fig)

# Figura 3: función de distribución acumulada, escenario A frente a B
fig, a = plt.subplots(figsize=(8, 4.5))
for e, color in [(esc_A, NARANJA), (esc_B, AZUL)]:
    v = np.sort(e["van_usd"])
    a.plot(v, np.arange(1, len(v) + 1) / len(v), color=color, linewidth=2, label=e["nombre"])
a.axvline(0, color="black", linewidth=1)
a.set_xlabel("VAN después de impuestos (US$ millones)")
a.set_ylabel("Probabilidad acumulada")
a.legend(frameon=False, fontsize=9)
a.set_title("Probabilidad acumulada del VAN: precio del informe técnico frente a precio de mercado", loc="left", fontsize=10)
fig.savefig(SALIDAS / "figura3_distribucion_acumulada.png")
plt.close(fig)

# Figura 4: tornado de sensibilidad (coeficientes estandarizados con IC 95 %)
orden = b.abs().sort_values().index
fig, a = plt.subplots(figsize=(8, 3.8))
a.barh(orden, b[orden], color=[AZUL if v >= 0 else NARANJA for v in b[orden]], height=0.55)
ic = 1.96 * mod_sens.bse[orden]
a.errorbar(b[orden], orden, xerr=ic, fmt="none", ecolor="black", capsize=3, linewidth=1)
a.axvline(0, color="black", linewidth=1)
a.set_xlabel("Cambio del VAN (S/ millones) cuando el factor sube 1 desviación estándar")
a.set_title("Sensibilidad del VAN a cada fuente de riesgo (escenario B)", loc="left", fontsize=10)
fig.savefig(SALIDAS / "figura4_tornado_sensibilidad.png")
plt.close(fig)

# Figura 5: abanico de trayectorias simuladas del precio del oro
anios = np.arange(0, N_ANIOS + 2)
pr = np.hstack([np.full((N_SIM, 1), P_MERCADO), esc_B["precios"]])
fig, a = plt.subplots(figsize=(8, 4.5))
a.fill_between(anios, np.percentile(pr, 5, axis=0), np.percentile(pr, 95, axis=0), color=AZUL, alpha=0.18, label="Percentiles 5-95")
a.fill_between(anios, np.percentile(pr, 25, axis=0), np.percentile(pr, 75, axis=0), color=AZUL, alpha=0.35, label="Percentiles 25-75")
a.plot(anios, np.median(pr, axis=0), color=AZUL, linewidth=2, label="Mediana")
a.axhline(P_TRS, color=GRIS, linestyle="--", linewidth=1.2)
a.text(0.2, P_TRS, f"Precio TRS {P_TRS:,.0f}", color=GRIS, fontsize=9, va="bottom")
a.set_xlabel("Año del proyecto")
a.set_ylabel("US$ por onza")
a.legend(frameon=False, fontsize=9, loc="upper left")
a.set_title("Trayectorias simuladas del precio del oro (escenario B)", loc="left", fontsize=10)
fig.savefig(SALIDAS / "figura5_abanico_precio_oro.png")
plt.close(fig)

# ------------------------------------------------------------------
# BLOQUE FINAL. Excel de presentación (generado por código, no a mano) y resumen en pantalla
# ------------------------------------------------------------------
with pd.ExcelWriter(SALIDAS / "resultados_tema55.xlsx") as xl:
    for nombre, t in TABLAS.items():
        t.to_excel(xl, sheet_name=nombre[:31], index=False)
registrar(f"Tablas: {len(TABLAS)} | Figuras: 5 | Cointegración oro-demanda: {COINTEGRADAS}")
print("\n=== CONTRASTE DE HIPÓTESIS ===")
print(contraste[["Hipótesis", "Estadístico", "Valor p", "Decisión"]].to_string(index=False))
print("\n=== DISTRIBUCIÓN DEL VAN ===")
print(TABLAS["tabla8_distribucion_van"].round(2).to_string(index=False))
