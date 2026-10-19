# Registro de incidencias de las fuentes

Este archivo registra cualquier bloqueo o ajuste de las fuentes (numeral 2.4.3 de la consigna).

| Fecha y hora (Lima) | Fuente y URL | Código HTTP | robots.txt | Qué pasó | Qué se hizo |
|---|---|---|---|---|---|
| 2026-10-17 07:50 | SPDR Gold Shares: `https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv` | 200 | Permitido | La ruta respondió con un PDF de 120 páginas (lista de lingotes del día, «Client Gold Stock Holdings»), no con el historial diario. El script 03 no encontró la columna de toneladas | Se revisó la página oficial `https://www.spdrgoldshares.com/usa/gld/`. El botón «Download» del «Historical Archive» apunta a `https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en` (Excel). Se actualizó el script 02 a esa ruta. Es la misma fuente y el mismo portal, así que no hay sustitución de fuente |

## Ajustes conocidos de las fuentes (no son bloqueos)

1. **BCRP:** los días sin dato aparecen como `n.d.` (feriados en Perú o en Londres). No se rellenan: el script 03 solo usa los días en que todas las fuentes tienen dato real.
2. **Yahoo Finance (GLD):** el precio de cierre (`Close`) no se ajusta por dividendos porque el fondo GLD no reparte dividendos ni ha tenido splits. Se descarga con `auto_adjust=False`.
3. **SPDR (GLD):** el Excel histórico tiene filas marcadas como `US Holiday` sin toneladas. Quedan vacías y no se imputan.
5. **Términos de uso de SPDR:** la hoja «Disclaimer» del Excel prohíbe reproducir o redistribuir el archivo sin permiso. Por eso los archivos de `datos_crudos/` y `datos_procesados/` **no se publican en el repositorio público de GitHub**. Solo se entregan al docente dentro del ZIP para su verificación, y cualquiera puede regenerarlos ejecutando los scripts.
4. **Informe técnico de la SEC:** el informe (fecha efectiva 31/12/2024) presenta pequeñas diferencias internas, por ejemplo una vida de mina de 14.0, 14.2 o 14.6 años según la sección. Se usa el valor que alimenta el análisis económico (14.2 años, sección 1.2.1.1) y se redondea a 14 años de producción.
