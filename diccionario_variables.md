# Diccionario de variables

**Proyecto:** Traspaso (pass-through) de la tasa de referencia del BCRP a las tasas del sistema financiero
**Autor:** Santiago Piero Camayo Jiménez · Código de matrícula: 2024200488G
**Asignatura:** Finanzas I (055D) · UNCP · Unidad I · Tema N.º 6
**Periodo:** 2003-09 a 2025-12 (268 observaciones mensuales)
**Fecha de extracción:** 2026-09-24

---

## 1. Fuente y vía de extracción

| Elemento | Detalle |
|---|---|
| Institución | Banco Central de Reserva del Perú (BCRP) |
| Base de datos | BCRPData — Base de datos de estadísticas del BCRP |
| Vía | API REST pública (no requiere clave de acceso) |
| Endpoint base | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/` |
| Consulta empleada | `.../api/PD04722MM-PN07819NM-PN07807NM-PN07816NM/json/2003-9/2025-12/esp` |
| Frecuencia | Mensual |
| Llave común | `fecha` (mes-año, formato AAAA-MM) |

---

## 2. Variables extraídas de la fuente

| Variable | Código BCRP | Definición | Unidad | Frecuencia | Cuadro oficial de origen |
|---|---|---|---|---|---|
| `tasa_referencia` | PD04722MM | Tasa de referencia de la política monetaria fijada por el BCRP | % anual | Mensual | Tasas de interés del Banco Central de Reserva — Tasa de Referencia de la Política Monetaria |
| `tasa_interbancaria` | PN07819NM | Tasa promedio de los préstamos entre bancos en moneda nacional | % efectivo anual | Mensual | Tasas de interés activas y pasivas promedio de las empresas bancarias en MN (términos efectivos anuales) — Tasa Interbancaria Promedio |
| `tamn` | PN07807NM | Tasa activa promedio en moneda nacional: lo que cobran los bancos por sus créditos, calculada sobre saldos | % efectivo anual | Mensual | Tasas de interés activas y pasivas promedio de las empresas bancarias en MN (términos efectivos anuales) — Activas — TAMN |
| `tipmn` | PN07816NM | Tasa pasiva promedio en moneda nacional: lo que pagan los bancos por los depósitos | % efectivo anual | Mensual | Tasas de interés activas y pasivas promedio de las empresas bancarias en MN (términos efectivos anuales) — Pasivas — TIPMN |

**URL de verificación de cada serie** (sustituir `<CODIGO>` por el código correspondiente):
`https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/<CODIGO>/html`

**Nota sobre la TAMN.** Se calcula a partir del promedio de las tasas aplicadas sobre los **saldos** de crédito vigentes, por lo que incorpora operaciones pactadas en periodos anteriores. Esta característica se considera en la discusión de los resultados, ya que atenúa el traspaso observado.

**Nota sobre PN07819NM.** En BCRPData existe otra serie titulada igualmente «Tasa Interbancaria Promedio» (PN07839NM), correspondiente a **moneda extranjera**. Se utiliza PN07819NM porque la cadena de transmisión estudiada es en moneda nacional. El script `01_extraccion_api.py` verifica que el nombre oficial de la serie recibida contenga «en MN».

---

## 3. Variables derivadas (generadas en `03_limpieza_datos.py`)

| Variable | Definición | Cálculo | Unidad |
|---|---|---|---|
| `fecha` | Mes de referencia de la observación; llave común del proyecto | Conversión del periodo original del BCRP (p. ej. «Sep.2003») a formato AAAA-MM | Texto (AAAA-MM) |
| `spread_activo` | Margen de la tasa activa respecto de la tasa de política | `tamn - tasa_referencia` | Puntos porcentuales |
| `spread_pasivo` | Margen de la tasa pasiva respecto de la tasa de política | `tipmn - tasa_referencia` | Puntos porcentuales |

Los spreads miden el margen bancario: si el traspaso fuese completo, se mantendrían estables ante cambios de la tasa de referencia.

---

## 4. Archivos de datos

| Archivo | Contenido | Columnas |
|---|---|---|
| `datos_crudos/datos_crudos_2024200488G.json` | Respuesta original de la API, sin modificación alguna | Estructura JSON de BCRPData (`config`, `periods`) |
| `datos_crudos/datos_crudos_2024200488G.csv` | Misma información en forma de tabla, valores conservados como texto | `periodo_bcrp`, `fecha`, y las 4 series |
| `datos_procesados/datos_procesados_2024200488G.csv` | Base depurada para el análisis | `fecha` + 6 variables sustantivas |

**Observaciones:** 268 · **Valores faltantes:** ninguno · **Columnas sustantivas:** 6 (4 extraídas y 2 derivadas).

---

## 5. Cita de la fuente en APA 7.ª edición

Banco Central de Reserva del Perú. (2026). *BCRPData: series estadísticas mensuales de tasas de interés* [Conjunto de datos]. Recuperado el 24 de septiembre de 2026, de https://estadisticas.bcrp.gob.pe/estadisticas/series/api/
