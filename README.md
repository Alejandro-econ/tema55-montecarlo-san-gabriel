# Riesgo del proyecto aurífero San Gabriel: simulación de Monte Carlo sobre el precio del oro, la demanda y el tipo de cambio

| Dato | Detalle |
|---|---|
| Autor | Alejandro Soto Antezana |
| Código de matrícula | 2024200531K |
| Curso | Finanzas I (055D), Facultad de Economía, UNCP, 2026-II |
| Docente | Dr. Ciro Iván Machacuay Meza |
| Tema del temario | N.º 55: Riesgo del proyecto: simulación de Monte Carlo sobre precio, demanda y tipo de cambio |
| Repositorio | https://github.com/Alejandro-econ/tema55-montecarlo-san-gabriel |

## 1. Qué hace este proyecto
Calcula la **distribución del VAN** de la mina de oro San Gabriel (Buenaventura, Moquegua) con **10 000 simulaciones de Monte Carlo**. Los parámetros del proyecto se leen con código del informe técnico oficial presentado a la SEC. El riesgo del precio del oro, de la demanda de inversión en oro, del tipo de cambio y del riesgo país se calibra con **datos diarios reales** (más de 5 000 días por variable).

## 2. Fuentes y vías de extracción
| Vía | Fuente | Endpoint o URL | Variables |
|---|---|---|---|
| 1. API | BCRPData (BCRP) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{código}/json/2004-11-18/2026-08-31` | PD04704XD oro, PD04638PD tipo de cambio, PD04719XD tasa EE. UU. 10 años, PD04709XD EMBIG Perú |
| 1. API | Yahoo Finance (`yfinance`) | `yfinance.download("GLD", start="2004-11-18", end="2026-09-01")` | Precio y volumen del fondo GLD |
| 2. Descarga programática | SEC (EE. UU.) | `https://www.sec.gov/Archives/edgar/data/1013131/000141057825001056/tmb-20241231xex96d2.pdf` | Parámetros del proyecto (PDF leído con `pdfplumber`) |
| 2. Descarga programática | SPDR Gold Shares | `https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en` | Toneladas de oro del fondo GLD (demanda) |

- **Fecha de inicio (parámetro):** 2004-11-18. **Fecha de corte (parámetro):** 2026-08-31.
- **Primera y última fecha con datos reales en la base procesada:** 2004-11-18 a 2026-08-31 (5,221 días).
- **Semilla aleatoria:** 531, tomada de los 4 últimos dígitos del código de matrícula (2024200**531**K → 0531).

## 3. Orden de ejecución
1. Copie `.env.example` con el nombre `.env` y escriba su nombre y correo en `SEC_USER_AGENT`. La SEC exige identificarse para descargar; no se necesita ninguna clave de pago.
2. `pip install -r requirements.txt`
3. `python codigo/01_extraccion_api.py` → datos crudos del BCRP y de Yahoo
4. `python codigo/02_scraping_web.py` → PDF de la SEC, parámetros y archivo SPDR
5. `python codigo/03_limpieza_datos.py` → base procesada, hash y tabla de cotejo
6. `python codigo/04_analisis.py` → todas las tablas y figuras en `salidas/`

También se puede ejecutar todo con el cuaderno `ejecutar_en_colab.ipynb`.

## 4. Versiones
- Python: 3.13.16
- Librerías: ver `requirements.txt`, generado con las versiones exactas usadas: requests==2.32.4, pandas==2.2.3, numpy==2.1.3, yfinance==0.2.66, pdfplumber==0.11.10, statsmodels==0.15.0, scipy==1.16.3, matplotlib==3.10.0, openpyxl==3.1.5, python-dotenv==1.2.3

## 5. Verificación
- **SHA-256 de `datos_procesados/datos_procesados_2024200531K.csv`:** `5f76f03e7199fb95181165c16c8f9969448de893d13bded15025e57245849a95`
- `log_ejecucion.txt`: fecha y hora, URL, código HTTP y filas de cada extracción.
- `salidas/tabla_cotejo_10_datos.csv`: 10 días al azar con su valor crudo y procesado, y el enlace a la web del BCRP para compararlos.
- `incidencias_fuente.md`: ajustes y bloqueos de las fuentes.

## 6. Ética del rastreo
Antes de cada descarga se lee `robots.txt`. Se usa un User-Agent con nombre y correo, y una pausa de 1 segundo entre solicitudes. Solo se descarga información pública, sin datos personales (Ley N.º 29733).
