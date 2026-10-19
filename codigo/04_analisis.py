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
VAR_DEMANDA = "gld_monto_musd"   # demanda de inversión: monto negociado diario del fondo de oro GLD
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
           "Demanda: monto negociado del fondo GLD (US$ mm)": VAR_DEMANDA,
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

# Precio del oro de equilibrio: el precio constante que hace VAN = 0. Mientras el margen sea positivo,
# el VAN es una línea recta en el precio, así que basta evaluar dos precios y despejar.
_p1, _p2 = C_UNIT + 100, C_UNIT + 1000
_v1 = calcular_van(np.full((1, N_ANIOS + 1), _p1), np.array([K0]))[0][0]
_v2 = calcular_van(np.full((1, N_ANIOS + 1), _p2), np.array([K0]))[0][0]
P_EQUILIBRIO = _p1 - _v1 * (_p2 - _p1) / (_v2 - _v1)
P_MERCADO = base["precio_oro"].iloc[-1]
TC_MERCADO = base["tc"].iloc[-1]
FECHA_ULT = base["fecha"].iloc[-1].strftime("%Y-%m-%d")
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
    ("Precio del oro de equilibrio, VAN = 0 (US$/oz)", P_EQUILIBRIO, "Cálculo con el modelo"),
    (f"Precio de mercado al {FECHA_ULT} (US$/oz)", P_MERCADO, "BCRP, serie PD04704XD"),
    ("Margen de seguridad del precio (%)", (1 - P_EQUILIBRIO / P_MERCADO) * 100, "Cálculo: 1 - equilibrio / mercado"),
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
# La demanda (monto negociado) no es un precio: solo se le quita la media.
M_SIN_TENDENCIA = M - M.mean(axis=0)
for col in (0, 2):   # 0 = oro, 2 = tipo de cambio
    M_SIN_TENDENCIA[:, col] -= 0.5 * M[:, col].var()


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
    # Choque acumulado de demanda (en logaritmos, sin exponenciar): mide si en esa simulación
    # el monto negociado del fondo de oro terminó por encima (+) o por debajo (-) de lo normal
    demanda_idx = np.cumsum(s[:, :, 1], axis=1)
    tc = np.hstack([np.full((N_SIM, 1), tc0), tc0 * np.exp(np.cumsum(s[:, :, 2], axis=1))])
    k = np.maximum(K0 + s[:, 0, 3] / 100, 0.01)                     # WACC + cambio del riesgo país en 1 año
    van_usd, van_pen = calcular_van(precios, k, tc)
    return {"nombre": nombre, "precios": precios, "demanda": demanda_idx, "tc": tc, "k": k,
            "van_usd": van_usd / 1e6, "van_pen": van_pen / 1e6, "p0": p0, "tc0": tc0}


rng = np.random.default_rng(SEMILLA)
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
    "Demanda": esc_B["demanda"][:, N_ANIOS - 1],
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
# BLOQUE FIGURAS (estilo de revista: paneles con letra, colores validados para daltonismo,
# etiquetas directas, sin títulos dentro de la imagen; el título y la nota van en LaTeX, APA 7)
# Cada figura se guarda en PNG (300 dpi, para Word/Beamer) y en PDF vectorial (para LaTeX).
# ------------------------------------------------------------------
import logging
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter, PercentFormatter
import matplotlib.dates as mdates

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
TINTA, TINTA2, REJILLA = "#1f1f1d", "#5f5e5a", "#e6e5e0"
AZUL, NARANJA, AQUA, AMARILLO, ROJO = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948"
AZUL_CLARO, NARANJA_CLARO = "#cde2fb", "#fbd9c8"
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Lato", "Source Sans 3", "Source Sans Pro", "Liberation Sans", "Arial", "DejaVu Sans"],
    "font.size": 8.5, "axes.labelsize": 8.5, "axes.titlesize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.edgecolor": TINTA2, "axes.labelcolor": TINTA, "axes.linewidth": 0.7, "text.color": TINTA,
    "xtick.color": TINTA2, "ytick.color": TINTA2, "xtick.major.size": 3, "ytick.major.size": 3,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": REJILLA, "grid.linewidth": 0.6,
    "legend.frameon": False, "legend.fontsize": 8, "figure.dpi": 150,
    "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.05,
    "pdf.fonttype": 42, "axes.formatter.use_locale": False,
})
def num(x, dec=0, signo=False):
    """Número con separador de miles fino y signo menos tipográfico (estilo editorial)."""
    t = f"{x:+,.{dec}f}" if signo else f"{x:,.{dec}f}"
    return t.replace(",", "\u2009").replace("-", "\u2212")


miles = FuncFormatter(lambda x, _: num(x))   # 4 437 con separador fino


# Borra figuras de versiones anteriores del script que ya no se generan
(SALIDAS / "figura2_histograma_van.png").unlink(missing_ok=True)


def guardar_figura(fig, nombre):
    fig.savefig(SALIDAS / f"{nombre}.png")
    fig.savefig(SALIDAS / f"{nombre}.pdf")
    plt.close(fig)


def letra(ax, texto, titulo):
    """Letra del panel (a, b, ...) en negrita y subtítulo, alineados a la izquierda."""
    ax.text(0, 1.04, texto, transform=ax.transAxes, fontsize=10, fontweight="bold", color=TINTA, va="bottom")
    ax.text(0.045, 1.04, titulo, transform=ax.transAxes, fontsize=8, color=TINTA, va="bottom")


def nota_valor(ax, x, y, texto, color, dx=8, dy=0, ha="left"):
    ax.scatter([x], [y], s=16, color=color, zorder=5, edgecolor="white", linewidth=0.8)
    ax.annotate(texto, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=7.5,
                color=TINTA, ha=ha, va="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85))


CRISIS = [("2008-09-15", "2009-03-31", "Crisis financiera\nglobal"), ("2020-03-01", "2020-06-30", "COVID-19")]

# ---- Figura 1: las cuatro variables diarias (paneles con su propia escala; nunca doble eje) ----
fig, ax = plt.subplots(2, 2, figsize=(7.2, 4.8), sharex=True)
paneles = [("precio_oro", "a", "Precio del oro (US$ por onza) · BCRP", AZUL, False),
           (VAR_DEMANDA, "b", "Demanda: monto negociado GLD (US$ mm, log.) · Yahoo", AQUA, True),
           ("tc", "c", "Tipo de cambio (S/ por US$) · BCRP", NARANJA, False),
           ("riesgo_pais_tasa", "d", "Tasa EE. UU. 10 años + EMBIG Perú (%) · FRED, BCRP", ROJO, False)]
for i, (a, (col, l, tit, color, logy)) in enumerate(zip(ax.ravel(), paneles)):
    for ini, fin, etiqueta in CRISIS:
        a.axvspan(pd.Timestamp(ini), pd.Timestamp(fin), color="#f0efec", zorder=0)
        if i == 0:
            a.text(pd.Timestamp(ini), 1.0, " " + etiqueta, transform=a.get_xaxis_transform(),
                   fontsize=6.5, color=TINTA2, va="top", ha="left")
    serie = base.set_index("fecha")[col]
    if logy:
        a.plot(serie.index, serie, color=color, linewidth=0.35, alpha=0.35)
        a.plot(serie.index, serie.rolling(63).mean(), color=color, linewidth=1.3, label="Media móvil 3 meses")
        a.set_yscale("log")
        a.legend(loc="upper left", fontsize=7)
    else:
        a.plot(serie.index, serie, color=color, linewidth=0.9)
    nota_valor(a, serie.index[-1], serie.iloc[-1], num(serie.iloc[-1], 2), color, dx=-6, dy=10, ha="right")
    if not logy:
        a.yaxis.set_major_formatter(miles if serie.max() > 100 else FuncFormatter(lambda x, _: f"{x:.1f}"))
    letra(a, l, tit)
    a.xaxis.set_major_locator(mdates.YearLocator(4))
    a.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.tight_layout(h_pad=2.2, w_pad=2.0)
guardar_figura(fig, "figura1_series_diarias")

# ---- Figura 2: distribución del VAN, escenario A frente a B (densidades con zona de pérdida) ----
fig, a = plt.subplots(figsize=(7.2, 3.6))
x = np.linspace(min(esc_A["van_usd"].min(), -900), np.percentile(esc_B["van_usd"], 99.7), 800)
a.axvspan(x.min(), 0, color="#fbe3e2", zorder=0)
a.text(x.min() + 40, 0.97, "Zona de pérdida\n(VAN < 0)", transform=a.get_xaxis_transform(),
       fontsize=7, color=ROJO, va="top", fontweight="bold")
caja = []
for e, color, claro, etiqueta in [(esc_A, NARANJA, NARANJA_CLARO, "A · Precio del informe técnico (US$ 2\u2009172/oz)"),
                                   (esc_B, AZUL, AZUL_CLARO, f"B · Precio de mercado (US$ {P_MERCADO:,.0f}/oz)".replace(",", "\u2009"))]:
    v = e["van_usd"]
    dens = stats.gaussian_kde(v)(x)
    a.fill_between(x, dens, color=claro, alpha=0.75, linewidth=0)
    a.plot(x, dens, color=color, linewidth=1.6)
    i_max = dens.argmax()
    a.annotate(etiqueta, (x[i_max], dens[i_max]), xytext=(45, -55) if color == NARANJA else (70, 22), textcoords="offset points",
               fontsize=7.5, color=color, fontweight="bold", va="center",
               arrowprops=dict(arrowstyle="-", color=color, linewidth=0.6))
    media = v.mean()
    a.plot([media, media], [0, stats.gaussian_kde(v)(media)[0]], color=color, linewidth=1, linestyle=(0, (3, 2)))
    r = resumen(v)
    caja.append(f"{etiqueta[0]}:  E[VAN] {num(r['Media'])}  ·  VaR 95 % {num(r['P5 (VaR 95 %)'])}  ·  "
                f"P(VAN<0) {r['Prob. VAN < 0 (%)']:.1f} %")
a.axvline(van_trs, color=TINTA2, linewidth=1, linestyle=(0, (1, 2)))
a.text(van_trs, 0.55, f" VAN oficial\n del informe\n técnico: {num(van_trs)}", transform=a.get_xaxis_transform(),
       fontsize=7, color=TINTA2, va="top", bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1))
a.axvline(0, color=TINTA, linewidth=0.8)
a.text(0.99, 0.97, "US$ millones\n" + "\n".join(caja), transform=a.transAxes, ha="right", va="top", fontsize=7,
       bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor=REJILLA))
a.set_xlim(x.min(), x.max())
a.set_ylim(bottom=0)
a.set_yticks([])
a.spines["left"].set_visible(False)
a.xaxis.set_major_formatter(miles)
a.set_xlabel("VAN después de impuestos (US$ millones) · 10\u2009000 simulaciones por escenario · línea discontinua = media")
guardar_figura(fig, "figura2_distribucion_van")

# ---- Figura 3: probabilidad acumulada del VAN con la probabilidad de pérdida marcada ----
fig, a = plt.subplots(figsize=(7.2, 3.4))
for e, color, etiqueta in [(esc_A, NARANJA, "A · Precio del informe técnico"), (esc_B, AZUL, "B · Precio de mercado")]:
    v = np.sort(e["van_usd"])
    p = np.arange(1, len(v) + 1) / len(v)
    a.plot(v, p, color=color, linewidth=1.8, label=etiqueta)
    p0 = (v < 0).mean()
    a.scatter([0], [p0], s=18, color=color, zorder=5, edgecolor="white", linewidth=0.8)
    a.annotate(f"P(VAN < 0) = {p0*100:.1f} %", (0, p0), xytext=(60, 30) if color == AZUL else (-40, 14),
               textcoords="offset points", ha="left" if color == AZUL else "right", fontsize=7.5, fontweight="bold", color=color,
               arrowprops=dict(arrowstyle="-", color=color, linewidth=0.6))
    for q in (0.05, 0.95):
        xq = np.percentile(v, q * 100)
        a.scatter([xq], [q], s=12, color=color, zorder=4)
a.axvline(0, color=TINTA, linewidth=0.8)
a.set_xlim(min(esc_A["van_usd"].min(), -900) * 1.6, np.percentile(esc_B["van_usd"], 99.5))
a.axhline(0.05, color=REJILLA, linewidth=0.8)
a.axhline(0.95, color=REJILLA, linewidth=0.8)
a.text(a.get_xlim()[1], 0.05, "P5 ", ha="right", va="bottom", fontsize=7, color=TINTA2)
a.text(a.get_xlim()[1], 0.95, "P95 ", ha="right", va="bottom", fontsize=7, color=TINTA2)
a.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
a.xaxis.set_major_formatter(miles)
a.set_xlabel("VAN después de impuestos (US$ millones)")
a.set_ylabel("Probabilidad acumulada")
a.legend(loc="center right")
guardar_figura(fig, "figura3_distribucion_acumulada")

# ---- Figura 4: tornado de sensibilidad con intervalos de confianza al 95 % ----
nombres_factor = {"Precio del oro": "Precio del oro", "Tipo de cambio": "Tipo de cambio (S/ por US$)",
                  "Riesgo país (WACC)": "Tasa de descuento (riesgo país)", "Demanda": "Demanda de inversión (GLD)"}
orden = b.abs().sort_values().index
fig, a = plt.subplots(figsize=(7.2, 3.0))
colores = [AZUL if v >= 0 else ROJO for v in b[orden]]
a.barh([nombres_factor[o] for o in orden], b[orden], color=colores, height=0.58, zorder=3)
ic = 1.96 * mod_sens.bse[orden]
a.errorbar(b[orden], range(len(orden)), xerr=ic, fmt="none", ecolor=TINTA, capsize=2.5, linewidth=0.8, zorder=4)
for y, (o, v) in enumerate(b[orden].items()):
    extremo = v + (ic[o] if v >= 0 else -ic[o])
    a.text(extremo + (0.015 if v >= 0 else -0.015) * abs(b).max(), y, num(v, signo=True), va="center",
           ha="left" if v >= 0 else "right", fontsize=7.5, fontweight="bold", color=TINTA)
a.axvline(0, color=TINTA, linewidth=0.8)
a.grid(axis="y", visible=False)
a.grid(axis="x", visible=True)
lim = max(abs(b).max() + ic.max(), 1) * 1.25
a.set_xlim(min(b.min() - ic.max(), 0) * 1.6 - 0.12 * abs(b).max(), lim)
a.xaxis.set_major_formatter(miles)
a.set_xlabel("Cambio del VAN en soles (S/ millones) cuando el factor sube una desviación estándar")
a.text(0.99, 0.06, f"R² = {mod_sens.rsquared:.3f}   ·   F = {num(mod_sens.fvalue)} (p < 0.001)   ·   N = {num(mod_sens.nobs)}   ·   barras = IC 95 %",
       transform=a.transAxes, ha="right", fontsize=7, color=TINTA2)
guardar_figura(fig, "figura4_tornado_sensibilidad")

# ---- Figura 5: historia del oro + abanico de 10 000 trayectorias simuladas ----
fig, a = plt.subplots(figsize=(7.2, 3.8))
hist = base.set_index("fecha")["precio_oro"].loc["2014-01-01":].resample("ME").mean()
a.plot(hist.index, hist, color=TINTA, linewidth=1.2, label="Observado (promedio mensual, BCRP)")
t0 = base["fecha"].iloc[-1]
fechas_fut = pd.DatetimeIndex([t0 + pd.DateOffset(years=k) for k in range(0, N_ANIOS + 2)])
pr = np.hstack([np.full((N_SIM, 1), P_MERCADO), esc_B["precios"]])
for q_inf, q_sup, alfa in [(5, 95, 0.22), (25, 75, 0.45)]:
    a.fill_between(fechas_fut, np.percentile(pr, q_inf, axis=0), np.percentile(pr, q_sup, axis=0),
                   color=AZUL, alpha=alfa, linewidth=0, label=f"Simulado: percentiles {q_inf}–{q_sup}")
idx = np.random.default_rng(SEMILLA).choice(N_SIM, 18, replace=False)
for i in idx:
    a.plot(fechas_fut, pr[i], color=AZUL, linewidth=0.3, alpha=0.3)
a.plot(fechas_fut, np.median(pr, axis=0), color=AZUL, linewidth=1.8, label="Simulado: mediana")
a.axvline(t0, color=TINTA2, linewidth=0.8, linestyle=(0, (3, 2)))
a.text(t0, 0.98, f" Fecha de corte: {t0:%d/%m/%Y}", transform=a.get_xaxis_transform(), fontsize=7, color=TINTA2, va="top")
a.axhline(P_TRS, color=NARANJA, linewidth=1, linestyle=(0, (4, 2)))
a.text(hist.index[0], P_TRS * 1.03, f"Precio supuesto en el informe técnico: US$ {num(P_TRS)}",
       fontsize=7, color=NARANJA, va="bottom", fontweight="bold",
       bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1))
a.axhline(P_EQUILIBRIO, color=ROJO, linewidth=1, linestyle=(0, (1, 2)))
a.text(hist.index[0], P_EQUILIBRIO * 0.97, f"Precio de equilibrio (VAN = 0): US$ {num(P_EQUILIBRIO)}",
       fontsize=7, color=ROJO, va="top", fontweight="bold",
       bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1))
for q in (95, 50, 5):
    yq = np.percentile(pr[:, -1], q)
    nota_valor(a, fechas_fut[-1], yq, f"P{q}: {num(yq)}", AZUL, dx=6)
a.set_yscale("log")
a.yaxis.set_major_formatter(miles)
a.yaxis.set_minor_formatter(FuncFormatter(lambda x, _: ""))
a.set_ylabel("US$ por onza (escala logarítmica)")
a.legend(loc="upper left", fontsize=7, ncol=1)
a.set_xlim(hist.index[0], fechas_fut[-1] + pd.DateOffset(years=2))
a.set_ylim(min(hist.min(), np.percentile(pr[:, -1], 5)) * 0.55, np.percentile(pr[:, -1], 95) * 1.6)
guardar_figura(fig, "figura5_abanico_precio_oro")

# ---- Figura 6: cada simulación como un punto: VAN frente al precio medio del oro ----
fig, a = plt.subplots(figsize=(7.2, 3.8))
for e, color, etiqueta in [(esc_A, NARANJA, "A · Precio del informe técnico"), (esc_B, AZUL, "B · Precio de mercado")]:
    precio_medio = e["precios"][:, :N_ANIOS].mean(axis=1)
    a.scatter(precio_medio, e["van_usd"], s=2.5, color=color, alpha=0.18, linewidths=0, rasterized=True, label=etiqueta)
a.axhline(0, color=TINTA, linewidth=0.8)
a.axvline(P_EQUILIBRIO, color=ROJO, linewidth=1, linestyle=(0, (1, 2)))
a.text(P_EQUILIBRIO, 0.97, f" Precio de equilibrio\n US$ {num(P_EQUILIBRIO)}/oz",
       transform=a.get_xaxis_transform(), fontsize=7, color=ROJO, va="top", fontweight="bold")
a.set_xscale("log")
a.xaxis.set_major_formatter(miles)
a.xaxis.set_minor_formatter(FuncFormatter(lambda x, _: ""))
a.yaxis.set_major_formatter(miles)
a.set_xlabel("Precio medio simulado del oro durante la vida de la mina (US$ por onza, escala log.)")
a.set_ylabel("VAN (US$ millones)")
leg = a.legend(loc="lower right", markerscale=5, ncol=2, bbox_to_anchor=(1, 0.01))
for h in leg.legend_handles:
    h.set_alpha(1)
guardar_figura(fig, "figura6_van_vs_precio")

# ---- Figura 7: matriz de correlaciones de los rendimientos diarios (paleta divergente) ----
etiquetas = ["Oro", "Demanda", "Tipo de\ncambio", "Riesgo\npaís"]
C = R[["r_oro", "r_demanda", "r_tc", "d_riesgo_pais"]].corr().to_numpy()
mapa = LinearSegmentedColormap.from_list("divergente", [ROJO, "#f0efec", AZUL])
fig, a = plt.subplots(figsize=(3.8, 3.2))
sub = C[1:, :3]                                    # filas: demanda, TC, riesgo; columnas: oro, demanda, TC
mascara = np.triu(np.ones_like(sub, dtype=bool), k=1)
im = a.imshow(np.ma.array(sub, mask=mascara), cmap=mapa, vmin=-0.5, vmax=0.5)
n = len(R)
for i in range(3):
    for j in range(i + 1):
        r = sub[i, j]
        p = 2 * stats.t.sf(abs(r) * np.sqrt((n - 2) / (1 - r ** 2)), n - 2)
        estrellas = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
        a.text(j, i, num(r, 3, signo=True) + estrellas, ha="center", va="center", fontsize=7.5,
               fontweight="bold", color="white" if abs(r) > 0.3 else TINTA)
a.set_xticks(range(3), etiquetas[:3], fontsize=7)
a.set_yticks(range(3), etiquetas[1:], fontsize=7)
a.tick_params(length=0)
a.grid(False)
for sp in a.spines.values():
    sp.set_visible(False)
cb = fig.colorbar(im, ax=a, fraction=0.046, pad=0.04)
cb.outline.set_visible(False)
cb.ax.tick_params(labelsize=7, length=0)
cb.set_label("Correlación de Pearson", fontsize=7)
fig.text(0.02, -0.02, f"Rendimientos diarios · N = {num(n)} días · *** p < 0.01  ** p < 0.05  * p < 0.10",
         fontsize=6.5, color=TINTA2)
guardar_figura(fig, "figura7_correlaciones")

# ------------------------------------------------------------------
# BLOQUE FINAL. Excel de presentación (generado por código, no a mano) y resumen en pantalla
# ------------------------------------------------------------------
with pd.ExcelWriter(SALIDAS / "resultados_tema55.xlsx") as xl:
    for nombre, t in TABLAS.items():
        t.to_excel(xl, sheet_name=nombre[:31], index=False)
registrar(f"Tablas: {len(TABLAS)} | Figuras: 7 (PNG 300 dpi + PDF) | Cointegración oro-demanda: {COINTEGRADAS}")
print("\n=== CONTRASTE DE HIPÓTESIS ===")
print(contraste[["Hipótesis", "Estadístico", "Valor p", "Decisión"]].to_string(index=False))
print("\n=== DISTRIBUCIÓN DEL VAN ===")
print(TABLAS["tabla8_distribucion_van"].round(2).to_string(index=False))
