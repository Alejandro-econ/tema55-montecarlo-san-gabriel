# Registro de incidencias de las fuentes

Este archivo registra cualquier bloqueo o ajuste de las fuentes (numeral 2.4.3 de la consigna).

| Fecha y hora (Lima) | Fuente y URL | Código HTTP | robots.txt | Qué pasó | Qué se hizo |
|---|---|---|---|---|---|
| (completar solo si ocurre una incidencia) | | | | | |

## Ajustes conocidos de las fuentes (no son bloqueos)

1. **BCRP:** los días sin dato aparecen como `n.d.` (feriados en Perú o en Londres). No se rellenan: el script 03 solo usa los días en que todas las fuentes tienen dato real.
2. **Yahoo Finance (GLD):** el precio de cierre (`Close`) no se ajusta por dividendos porque el fondo GLD no reparte dividendos ni ha tenido splits. Se descarga con `auto_adjust=False`.
3. **SPDR (GLD):** el archivo histórico tiene filas marcadas como feriado (`HOLIDAY`) sin toneladas. Quedan vacías y no se imputan.
4. **Informe técnico de la SEC:** el informe (fecha efectiva 31/12/2024) presenta pequeñas diferencias internas, por ejemplo una vida de mina de 14.0, 14.2 o 14.6 años según la sección. Se usa el valor que alimenta el análisis económico (14.2 años, sección 1.2.1.1) y se redondea a 14 años de producción.
