# Traspaso (pass-through) de la tasa de referencia del BCRP a las tasas del sistema financiero

Base de datos y código de extracción, limpieza y análisis del artículo de aplicación.

| Dato | Detalle |
|---|---|
| **Autor** | Santiago Piero Camayo Jiménez |
| **Código de matrícula** | 2024200488G |
| **Asignatura** | Finanzas I (055D) · Escuela Profesional de Economía · UNCP |
| **Unidad** | Unidad I · Tema N.º 6 del temario |
| **Repositorio** | https://github.com/santiagocamayo18/pass-through-bcrp-CamayoJim-nezSantiago |

---

## 1. Objetivo

Medir la magnitud y la velocidad con que los cambios en la tasa de referencia del BCRP se trasladan a las tasas del sistema financiero peruano, siguiendo la cadena de transmisión: tasa de referencia → tasa interbancaria → tasas activas (TAMN) y pasivas (TIPMN).

## 2. Fuente de datos y vía de extracción

| Elemento | Detalle |
|---|---|
| Institución | Banco Central de Reserva del Perú (BCRP) |
| Base de datos | BCRPData |
| Vía de extracción | API REST pública (Unidad I: una vía automatizada) |
| Endpoint base | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/` |
| Consulta completa | `.../api/PD04722MM-PN07819NM-PN07807NM-PN07816NM/json/2003-9/2025-12/esp` |
| Autenticación | **No requiere clave.** La API de BCRPData es de acceso público |

### Series utilizadas

| Código | Variable | Descripción |
|---|---|---|
| PD04722MM | `tasa_referencia` | Tasa de referencia de la política monetaria |
| PN07819NM | `tasa_interbancaria` | Tasa interbancaria promedio en moneda nacional |
| PN07807NM | `tamn` | Tasa activa promedio en moneda nacional |
| PN07816NM | `tipmn` | Tasa pasiva promedio en moneda nacional |

El detalle completo está en `diccionario_variables.md`.

## 3. Periodo y fecha de corte

| Parámetro | Valor |
|---|---|
| `FECHA_INICIO` | 2003-09 (primer mes disponible de la tasa de referencia) |
| `FECHA_CORTE` | 2025-12 |
| Observaciones | 268 meses |
| Fecha de extracción | 2026-09-24 |

Ambos parámetros están declarados como constantes en los scripts, no como fechas dinámicas.

## 4. Orden de ejecución

Desde la carpeta raíz del proyecto:

```
python codigo/01_extraccion_api.py    # descarga y guarda los datos crudos
python codigo/03_limpieza_datos.py    # genera datos_procesados
python codigo/04_analisis.py          # genera tablas y figuras en salidas/
```

No existe `02_scraping_web.py`: la Unidad I exige al menos una vía automatizada, y este proyecto utiliza la vía API.

Cada ejecución añade su registro a `log_ejecucion.txt`, con fecha y hora, endpoint, código de respuesta HTTP, número de filas y hashes de los archivos generados.

## 5. Verificación de integridad (SHA-256)

| Archivo | Hash |
|---|---|
| `datos_crudos/datos_crudos_2024200488G.json` | `0f2c460a296672d2a9846fdf97640f40738cc40a2912683a0874c210ceb794b7` |
| `datos_crudos/datos_crudos_2024200488G.csv` | `8ef6d7c4219a7297dba58890f61ce5caa46c72c411d78f7bbf9ce39323b359d1` |
| **`datos_procesados/datos_procesados_2024200488G.csv`** | **`9c4c2ad49d6a69795121e0a6ef74510591b3a09c54095653f296b1da7399ae91`** |

Para comprobarlos en Windows:

```
certutil -hashfile datos_procesados\datos_procesados_2024200488G.csv SHA256
```

**Nota sobre reproducibilidad.** El script se ejecutó dos veces en momentos distintos (2026-09-23 y 2026-09-24) y produjo archivos crudos idénticos byte por byte. Si una reejecución posterior arrojara un hash distinto, se debería a una revisión oficial de las series por parte del BCRP; el `log_ejecucion.txt` acredita la fecha y hora de la extracción original.

## 6. Entorno y versiones

| Componente | Versión |
|---|---|
| Python | 3.11.16 |
| Sistema operativo de desarrollo | Windows 11 |
| Gestor de entorno | Anaconda (entorno `finanzas_pt`) |

Librerías utilizadas (las mismas que recoge `requirements.txt`):

| Librería | Versión | Uso en el proyecto |
|---|---|---|
| requests | 2.34.2 | Consumo de la API de BCRPData (`01`) |
| pandas | 3.0.6 | Manejo de las series y de los archivos CSV (`01`, `03`, `04`) |
| numpy | 2.4.6 | Cálculo del traspaso acumulado (`04`) |
| matplotlib | 3.11.2 | Generación de las figuras (`04`) |
| statsmodels | 0.15.0 | Pruebas ADF, Engle-Granger y estimación por MCO (`04`) |

Para reproducir el entorno:

```
conda create -n finanzas_pt python=3.11
conda activate finanzas_pt
pip install -r requirements.txt
```

## 7. Estructura de la carpeta

```
.
├── codigo/
│   ├── 01_extraccion_api.py      # consumo de la API de BCRPData
│   ├── 03_limpieza_datos.py      # depuración y datos_procesados
│   └── 04_analisis.py            # tablas y figuras del artículo
├── datos_crudos/                 # respuesta original de la API (no editar)
├── datos_procesados/             # base depurada
├── salidas/                      # tablas y figuras generadas por 04_analisis.py
├── diccionario_variables.md
├── log_ejecucion.txt
├── requirements.txt
├── .env.example
├── .gitattributes
└── README.md
```

## 8. Resultados generados por `04_analisis.py`

| Archivo | Contenido |
|---|---|
| `fig1_series.png` | Las cuatro tasas, 2003-2025 |
| `fig2_spreads.png` | Márgenes activo y pasivo respecto de la referencia |
| `fig3_traspaso.png` | Traspaso acumulado ante un alza de 1 punto |
| `tabla1_descriptivas.csv` | Estadísticas descriptivas |
| `tabla2_raiz_unitaria.csv` | Pruebas ADF en niveles y primeras diferencias |
| `tabla3_cointegracion.csv` | Engle-Granger y relación de largo plazo |
| `tabla4_traspaso.csv` | **Modelo principal:** traspaso inmediato, de largo plazo y prueba de traspaso completo |
| `tabla5_robustez_niveles.csv` | Modelo de ajuste parcial en niveles (contraste) |

## 9. Nota metodológica

Las pruebas ADF indican que la tasa de referencia, la interbancaria y la TIPMN son estacionarias en niveles, mientras que la TAMN no lo es; la prueba de Engle-Granger solo encuentra cointegración entre la referencia y la interbancaria. En ese escenario, un modelo de corrección de errores no es aplicable de manera uniforme, y el modelo en niveles arroja un traspaso de largo plazo inestable para la TAMN. Por ello el modelo principal se estima en variaciones para las tres tasas, con rezagos de la variación de la tasa de referencia y errores estándar robustos (Newey-West). El modelo en niveles se conserva como análisis de robustez, indicando en qué series es interpretable.

## 10. Ética y uso de IA

- Los datos provienen íntegramente de la ejecución de los scripts de este repositorio. No se emplearon descargas manuales, datasets de terceros ni datos transcritos.
- Los datos crudos se conservan tal como salieron de la fuente, sin edición.
- Se utilizó asistencia de IA para la redacción y depuración del código, bajo revisión y comprensión del autor, conforme a lo permitido en la consigna del curso.

## 11. Cita de la fuente (APA 7.ª edición)

Banco Central de Reserva del Perú. (2026). *BCRPData: series estadísticas mensuales de tasas de interés* [Conjunto de datos]. Recuperado el 24 de septiembre de 2026, de https://estadisticas.bcrp.gob.pe/estadisticas/series/api/
