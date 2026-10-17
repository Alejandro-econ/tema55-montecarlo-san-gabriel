# Diccionario de variables

**Archivo:** `datos_procesados/datos_procesados_2024200531K.csv`. Frecuencia diaria (días hábiles con dato en todas las fuentes).
**Llave común:** `fecha` (AAAA-MM-DD). **Periodo declarado:** del 18/11/2004 al 31/08/2026.

| Variable | Definición | Unidad | Frecuencia | Fuente exacta | URL o endpoint |
|---|---|---|---|---|---|
| fecha | Día de la observación (llave de unión) | AAAA-MM-DD | Diaria | Todas | — |
| precio_oro | Cotización internacional del oro (Londres) | US$ por onza troy | Diaria | BCRP, BCRPData, serie PD04704XD | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04704XD/json/2004-11-18/2026-08-31` |
| tc | Tipo de cambio interbancario, venta | S/ por US$ | Diaria | BCRP, BCRPData, serie PD04638PD | `.../api/PD04638PD/json/2004-11-18/2026-08-31` |
| ust10 | Rendimiento de los bonos del Tesoro de EE. UU. a 10 años | % | Diaria | BCRP, BCRPData, serie PD04719XD | `.../api/PD04719XD/json/2004-11-18/2026-08-31` |
| embig_peru | Spread EMBIG Perú (riesgo país) | Puntos básicos | Diaria | BCRP, BCRPData, serie PD04709XD | `.../api/PD04709XD/json/2004-11-18/2026-08-31` |
| demanda_ton | Oro físico que guarda el fondo SPDR Gold Shares (demanda de inversión en oro) | Toneladas | Diaria | SPDR Gold Shares, archivo histórico GLD | `https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv` |
| gld_cierre | Precio de cierre del fondo GLD | US$ por acción | Diaria | Yahoo Finance (yfinance) | `yfinance.download("GLD", "2004-11-18", "2026-09-01")` |
| gld_volumen | Acciones del fondo GLD negociadas en el día | Número de acciones | Diaria | Yahoo Finance (yfinance) | Ídem |
| gld_monto_musd | Monto negociado del fondo GLD = cierre × volumen / 1 000 000 (respaldo de la demanda) | US$ millones | Diaria | Cálculo propio (Yahoo) | — |
| riesgo_pais_tasa | Tasa de EE. UU. a 10 años + EMBIG Perú / 100 | % | Diaria | Cálculo propio (BCRP) | — |
| r_oro | Rendimiento logarítmico diario del oro: ln(P_t / P_t-1) | Proporción | Diaria | Cálculo propio | — |
| r_tc | Rendimiento logarítmico diario del tipo de cambio | Proporción | Diaria | Cálculo propio | — |
| r_demanda | Rendimiento logarítmico diario de la demanda | Proporción | Diaria | Cálculo propio | — |
| d_riesgo_pais | Cambio diario de riesgo_pais_tasa | Puntos porcentuales | Diaria | Cálculo propio | — |
| atipico_* | 1 si el valor está a más de 5 desviaciones estándar de la media (se marca, no se borra) | 0/1 | Diaria | Cálculo propio | — |

**Archivo:** `datos_procesados/parametros_proyecto_2024200531K.csv`. Parámetros de la mina San Gabriel leídos con código desde el PDF oficial.

| Parámetro | Definición | Unidad | Fuente exacta |
|---|---|---|---|
| van_despues_impuestos_musd | VAN oficial después de impuestos | US$ millones | SLR Consulting (2025). *S-K 1300 Technical Report Summary, San Gabriel Project*. Anexo 96.2 del Form 20-F 2024 de Buenaventura, SEC. `https://www.sec.gov/Archives/edgar/data/1013131/000141057825001056/tmb-20241231xex96d2.pdf` |
| tasa_descuento_pct | WACC usado por la empresa | % | Ídem |
| flujo_antes_impuestos_musd / flujo_despues_impuestos_musd | Flujo neto total sin descontar | US$ millones | Ídem |
| inversion_inicial_musd | Inversión pendiente al 31/12/2024 | US$ millones | Ídem |
| costo_cierre_musd | Costo de cierre de mina | US$ millones | Ídem |
| precio_oro_trs_usd_oz | Precio de largo plazo supuesto por la empresa | US$ por onza | Ídem |
| aisc_usd_oz | Costo total sostenido (AISC), neto de subproductos | US$ por onza | Ídem |
| oro_pagable_koz | Oro pagable en toda la vida de la mina | Miles de onzas | Ídem |
| produccion_media_koz_anio | Producción media anual | Miles de onzas por año | Ídem |
| vida_mina_anios | Vida de la mina | Años | Ídem |
| impuesto_renta_pct | Tasa del impuesto a la renta en el Perú | % | Ídem |

Cada parámetro guarda además la **página del PDF** y la **frase literal** de donde se leyó (archivo `datos_crudos/datos_crudos_2024200531K_sec_trs_parametros.csv`).
