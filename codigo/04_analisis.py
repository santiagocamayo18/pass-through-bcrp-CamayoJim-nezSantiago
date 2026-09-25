# Autor: Santiago Piero Camayo Jiménez
# Código de matrícula: 2024200488G
# Tema N.º 6: Traspaso (pass-through) de la tasa de referencia del BCRP a las tasas del sistema financiero
# Fecha de extracción: 2026-09-24
"""
04_analisis.py - Etapa 3: descriptivos, diagnósticos y estimación del traspaso.

Entrada : datos_procesados/datos_procesados_<matricula>.csv
Salidas : salidas/fig1_series.png              -> las cuatro tasas, 2003-2025
          salidas/fig2_spreads.png             -> márgenes activo y pasivo
          salidas/fig3_traspaso.png            -> traspaso acumulado mes a mes
          salidas/tabla1_descriptivas.csv      -> estadísticas descriptivas
          salidas/tabla2_raiz_unitaria.csv     -> pruebas ADF en niveles y diferencias
          salidas/tabla3_cointegracion.csv     -> Engle-Granger y relación de largo plazo
          salidas/tabla4_traspaso.csv          -> MODELO PRINCIPAL (en variaciones)
          salidas/tabla5_robustez_niveles.csv  -> ajuste parcial en niveles (robustez)
          log_ejecucion.txt                    -> registro de esta ejecución
Ejecución: python codigo/04_analisis.py   (después de 03_limpieza_datos.py)

Estrategia (decidida a partir del diagnóstico de las tablas 2 y 3):
  - Tres series son estacionarias en niveles y la TAMN no lo es; solo la
    interbancaria está cointegrada con la referencia. Un modelo de corrección
    de errores no es aplicable de forma uniforme.
  - El modelo en niveles da un traspaso de largo plazo inestable para la TAMN
    (persistencia cercana a 1), coherente con su raíz unitaria.
  - Por eso el modelo principal se estima en VARIACIONES para las tres tasas:
    es válido sea la serie estacionaria o no, y deja resultados comparables.
"""

import sys
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_breusch_godfrey
from statsmodels.tsa.stattools import adfuller, coint

# =============================================================================
# 1. PARÁMETROS
# =============================================================================
CODIGO_MATRICULA = "2024200488G"

VARIABLE_POLITICA = "tasa_referencia"
SERIES_DEPENDIENTES = {
    "tasa_interbancaria": "Tasa interbancaria",
    "tamn": "TAMN (activa)",
    "tipmn": "TIPMN (pasiva)",
}
ETIQUETAS = {VARIABLE_POLITICA: "Tasa de referencia BCRP", **SERIES_DEPENDIENTES}
SPREADS = {"spread_activo": "TAMN - referencia", "spread_pasivo": "TIPMN - referencia"}

NIVEL = 0.05      # nivel de significancia de las pruebas
REZAGOS_HAC = 4   # rezagos para errores estándar robustos (Newey-West) y prueba de autocorrelación
HORIZONTE = 12    # meses simulados en la figura de traspaso acumulado
REZAGOS_POLITICA = 2  # meses de rezago de la variación de la tasa de referencia
FUENTE = "Fuente: elaboración propia con datos de BCRPData (BCRP)."

# =============================================================================
# 2. RUTAS RELATIVAS
# =============================================================================
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
ARCHIVO_PROCESADO = (CARPETA_PROYECTO / "datos_procesados" /
                     f"datos_procesados_{CODIGO_MATRICULA}.csv")
CARPETA_SALIDAS = CARPETA_PROYECTO / "salidas"
ARCHIVO_LOG = CARPETA_PROYECTO / "log_ejecucion.txt"


class ErrorAnalisis(Exception):
    """Problema que impide generar los resultados."""


def registrar(mensaje, log):
    """Muestra el mensaje en consola y lo acumula para escribirlo en el log."""
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}"
    print(linea)
    log.append(linea)


# =============================================================================
# 3. LECTURA
# =============================================================================
def leer_procesado(log):
    """Carga el archivo procesado y lo ordena por la llave común."""
    if not ARCHIVO_PROCESADO.exists():
        raise ErrorAnalisis(f"No se encuentra {ARCHIVO_PROCESADO.name}. "
                            f"Ejecute primero 03_limpieza_datos.py")
    datos = pd.read_csv(ARCHIVO_PROCESADO).sort_values("fecha").reset_index(drop=True)
    # El eje temporal se construye aquí, no en el archivo: el procesado guarda AAAA-MM.
    datos["periodo"] = pd.PeriodIndex(datos["fecha"], freq="M").to_timestamp()
    registrar(f"Procesado leído: {len(datos)} meses de {datos['fecha'].iloc[0]} "
              f"a {datos['fecha'].iloc[-1]}", log)
    return datos


# =============================================================================
# 4. FIGURAS
# =============================================================================
def figura_series(datos, log):
    """Las cuatro tasas en un mismo gráfico: muestra el fenómeno a simple vista."""
    figura, eje = plt.subplots(figsize=(10, 5))
    for columna, etiqueta in ETIQUETAS.items():
        ancho = 2.0 if columna == VARIABLE_POLITICA else 1.2
        eje.plot(datos["periodo"], datos[columna], label=etiqueta, linewidth=ancho)
    eje.set_title("Tasa de referencia del BCRP y tasas del sistema financiero, 2003-2025")
    eje.set_xlabel("Periodo (mensual)")
    eje.set_ylabel("Tasa de interés (% anual)")
    eje.legend()
    eje.grid(alpha=0.3)
    figura.text(0.01, 0.01, FUENTE, fontsize=8)
    ruta = CARPETA_SALIDAS / "fig1_series.png"
    figura.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(figura)
    registrar(f"Figura guardada: {ruta.relative_to(CARPETA_PROYECTO)}", log)


def figura_spreads(datos, log):
    """Los márgenes respecto de la referencia: un margen inestable sugiere traspaso incompleto."""
    figura, eje = plt.subplots(figsize=(10, 5))
    for columna, etiqueta in SPREADS.items():
        eje.plot(datos["periodo"], datos[columna], label=etiqueta, linewidth=1.3)
    eje.axhline(0, color="gray", linewidth=0.8)
    eje.set_title("Márgenes respecto de la tasa de referencia, 2003-2025")
    eje.set_xlabel("Periodo (mensual)")
    eje.set_ylabel("Diferencia (puntos porcentuales)")
    eje.legend()
    eje.grid(alpha=0.3)
    figura.text(0.01, 0.01, FUENTE, fontsize=8)
    ruta = CARPETA_SALIDAS / "fig2_spreads.png"
    figura.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(figura)
    registrar(f"Figura guardada: {ruta.relative_to(CARPETA_PROYECTO)}", log)


# =============================================================================
# 5. TABLA 1: DESCRIPTIVAS
# =============================================================================
def tabla_descriptivas(datos, log):
    """Media, desviación, mínimo y máximo de cada serie."""
    columnas = list(ETIQUETAS) + list(SPREADS)
    resumen = datos[columnas].describe().T[["count", "mean", "std", "min", "max"]]
    resumen.columns = ["N", "Media", "Desv. est.", "Mínimo", "Máximo"]
    resumen = resumen.round(2).reset_index().rename(columns={"index": "Variable"})
    resumen["Variable"] = resumen["Variable"].map({**ETIQUETAS, **SPREADS})
    ruta = CARPETA_SALIDAS / "tabla1_descriptivas.csv"
    resumen.to_csv(ruta, index=False, encoding="utf-8", lineterminator="\n")
    registrar(f"Tabla guardada: {ruta.relative_to(CARPETA_PROYECTO)}", log)
    return resumen


# =============================================================================
# 6. TABLA 2: RAÍZ UNITARIA (ADF)
# =============================================================================
def prueba_adf(serie):
    """Prueba de Dickey-Fuller aumentada.

    H0: la serie tiene raíz unitaria (no es estacionaria).
    Si el p-valor es menor al nivel de significancia, se rechaza H0.
    """
    with warnings.catch_warnings():  # adfuller avisa de un cambio de formato futuro
        warnings.simplefilter("ignore", FutureWarning)
        resultado = adfuller(serie.dropna(), autolag="AIC")
    estadistico, p_valor, rezagos, observaciones = resultado[:4]
    return {"Estadístico ADF": round(estadistico, 3), "p-valor": round(p_valor, 4),
            "Rezagos": rezagos, "N": observaciones,
            "Conclusión": "Estacionaria" if p_valor < NIVEL else "No estacionaria"}


def tabla_raiz_unitaria(datos, log):
    """Aplica ADF en niveles y en primeras diferencias a las cuatro tasas."""
    filas = []
    for columna, etiqueta in ETIQUETAS.items():
        filas.append({"Variable": etiqueta, "Transformación": "Nivel",
                      **prueba_adf(datos[columna])})
        filas.append({"Variable": etiqueta, "Transformación": "Primera diferencia",
                      **prueba_adf(datos[columna].diff())})
    tabla = pd.DataFrame(filas)
    ruta = CARPETA_SALIDAS / "tabla2_raiz_unitaria.csv"
    tabla.to_csv(ruta, index=False, encoding="utf-8", lineterminator="\n")
    registrar(f"Tabla guardada: {ruta.relative_to(CARPETA_PROYECTO)}", log)
    for fila in filas:
        registrar(f"ADF {fila['Variable']} ({fila['Transformación']}): "
                  f"p={fila['p-valor']} -> {fila['Conclusión']}", log)
    return tabla


# =============================================================================
# 7. TABLA 3: COINTEGRACIÓN (ENGLE-GRANGER)
# =============================================================================
def tabla_cointegracion(datos, log):
    """Para cada tasa, relación de largo plazo con la referencia y prueba de cointegración.

    Paso 1: regresión de largo plazo  tasa = a + b * referencia.
            El coeficiente b es el traspaso de largo plazo (1 = traspaso completo).
    Paso 2: prueba de Engle-Granger sobre esa relación.
            H0: NO hay cointegración. Si p < nivel, sí la hay.
    """
    politica = datos[VARIABLE_POLITICA]
    filas = []
    for columna, etiqueta in SERIES_DEPENDIENTES.items():
        modelo = sm.OLS(datos[columna], sm.add_constant(politica)).fit()
        beta = modelo.params[VARIABLE_POLITICA]
        _, p_valor, _ = coint(datos[columna], politica, trend="c", autolag="aic")
        hay_cointegracion = p_valor < NIVEL
        filas.append({
            "Variable": etiqueta,
            "Constante": round(modelo.params["const"], 3),
            "Traspaso largo plazo": round(beta, 3),
            "Error estándar": round(modelo.bse[VARIABLE_POLITICA], 3),
            "R2": round(modelo.rsquared, 3),
            "p-valor Engle-Granger": round(p_valor, 4),
            "Conclusión": "Cointegradas" if hay_cointegracion else "Sin cointegración",
        })
        registrar(f"Largo plazo {etiqueta}: beta={beta:.3f} | "
                  f"Engle-Granger p={p_valor:.4f} -> "
                  f"{'cointegradas' if hay_cointegracion else 'SIN cointegración'}", log)

    tabla = pd.DataFrame(filas)
    ruta = CARPETA_SALIDAS / "tabla3_cointegracion.csv"
    tabla.to_csv(ruta, index=False, encoding="utf-8", lineterminator="\n")
    registrar(f"Tabla guardada: {ruta.relative_to(CARPETA_PROYECTO)}", log)
    return tabla


# =============================================================================
# 8. TABLA 4: MODELO PRINCIPAL EN VARIACIONES
# =============================================================================
def preparar_variaciones(datos, columna):
    """Arma las variables del modelo: variaciones mensuales y sus rezagos."""
    marco = pd.DataFrame({"dy": datos[columna].diff(),
                          "dx": datos[VARIABLE_POLITICA].diff()})
    for rezago in range(1, REZAGOS_POLITICA + 1):
        marco[f"dx_l{rezago}"] = marco["dx"].shift(rezago)
    marco["dy_l1"] = marco["dy"].shift(1)
    return marco.dropna()


def respuesta_acumulada(coef_politica, c, horizonte):
    """Traspaso acumulado tras una subida permanente de 1 punto en la referencia.

    Mes 0: la tasa cambia b0. Mes h: cambia b_h (si existe) más c veces lo que
    cambió el mes anterior. La suma de esos cambios es el traspaso acumulado.
    """
    cambios = []
    for h in range(horizonte + 1):
        b_h = coef_politica[h] if h < len(coef_politica) else 0.0
        anterior = cambios[-1] if cambios else 0.0
        cambios.append(b_h + c * anterior)
    return np.cumsum(cambios)


def estimar_traspaso(datos, columna):
    """Estima por MCO:

        dy_t = a + b0*dx_t + b1*dx_(t-1) + b2*dx_(t-2) + c*dy_(t-1) + e_t

    b0                 -> traspaso inmediato (mismo mes)
    (b0+b1+b2)/(1-c)   -> traspaso total de largo plazo
    Traspaso completo  <=> b0 + b1 + b2 + c = 1 (se prueba esa hipótesis)
    Errores estándar robustos (Newey-West).
    """
    marco = preparar_variaciones(datos, columna)
    regresores = ["dx"] + [f"dx_l{r}" for r in range(1, REZAGOS_POLITICA + 1)] + ["dy_l1"]
    modelo = sm.OLS(marco["dy"], sm.add_constant(marco[regresores])).fit(
        cov_type="HAC", cov_kwds={"maxlags": REZAGOS_HAC})

    coef_politica = [modelo.params[r] for r in regresores[:-1]]
    c = modelo.params["dy_l1"]
    largo_plazo = sum(coef_politica) / (1 - c)

    # H0: traspaso completo. Si p < 0.05, el traspaso es significativamente distinto de 1.
    prueba = modelo.t_test(" + ".join(regresores) + " = 1")
    p_completo = float(np.squeeze(prueba.pvalue))

    trayectoria = respuesta_acumulada(coef_politica, c, HORIZONTE)
    alcanzado = np.where(trayectoria >= 0.5 * largo_plazo)[0] if largo_plazo > 0 else []
    meses_mitad = int(alcanzado[0]) if len(alcanzado) > 0 else "n.a."

    with warnings.catch_warnings():  # la prueba avisa de un cambio de formato futuro
        warnings.simplefilter("ignore", FutureWarning)
        p_autocorr = acorr_breusch_godfrey(modelo, nlags=REZAGOS_HAC)[1]

    resultado = {
        "Traspaso inmediato": round(coef_politica[0], 3),
        "Error estándar": round(modelo.bse["dx"], 3),
        "Traspaso largo plazo": round(largo_plazo, 3),
        "p-valor H0: traspaso completo": round(p_completo, 4),
        "Conclusión": "Completo" if p_completo >= NIVEL else "Incompleto",
        "Meses hasta 50%": meses_mitad,
        "R2": round(modelo.rsquared, 3),
        "p-valor autocorrelación": round(p_autocorr, 4),
        "N": int(modelo.nobs),
    }
    return resultado, trayectoria


def tabla_traspaso(datos, log):
    """Aplica el modelo principal a las tres tasas y guarda la tabla."""
    filas, trayectorias = [], {}
    for columna, etiqueta in SERIES_DEPENDIENTES.items():
        resultado, trayectoria = estimar_traspaso(datos, columna)
        trayectorias[etiqueta] = trayectoria
        filas.append({"Variable": etiqueta, **resultado})
        registrar(f"Traspaso {etiqueta}: inmediato={resultado['Traspaso inmediato']} | "
                  f"largo plazo={resultado['Traspaso largo plazo']} | "
                  f"H0 completo p={resultado['p-valor H0: traspaso completo']} -> "
                  f"{resultado['Conclusión']} | 50% en {resultado['Meses hasta 50%']} meses", log)
        if resultado["p-valor autocorrelación"] < NIVEL:
            registrar(f"Nota: {etiqueta} presenta autocorrelación residual "
                      f"(p={resultado['p-valor autocorrelación']}); los errores estándar "
                      f"robustos (Newey-West) la tienen en cuenta", log)

    tabla = pd.DataFrame(filas)
    ruta = CARPETA_SALIDAS / "tabla4_traspaso.csv"
    tabla.to_csv(ruta, index=False, encoding="utf-8", lineterminator="\n")
    registrar(f"Tabla guardada: {ruta.relative_to(CARPETA_PROYECTO)}", log)
    return trayectorias


# =============================================================================
# 9. TABLA 5: ROBUSTEZ CON EL AJUSTE PARCIAL EN NIVELES
# =============================================================================
def tabla_robustez_niveles(datos, tabla_adf, log):
    """Estima  tasa_t = a + b*referencia_t + c*tasa_(t-1)  como contraste.

    Solo es interpretable si la serie es estacionaria en niveles (tabla 2);
    la columna 'Válido según ADF' lo deja indicado.
    """
    niveles = tabla_adf[tabla_adf["Transformación"] == "Nivel"].set_index("Variable")
    filas = []
    for columna, etiqueta in SERIES_DEPENDIENTES.items():
        marco = pd.DataFrame({"y": datos[columna], "x": datos[VARIABLE_POLITICA],
                              "y_l1": datos[columna].shift(1)}).dropna()
        modelo = sm.OLS(marco["y"], sm.add_constant(marco[["x", "y_l1"]])).fit(
            cov_type="HAC", cov_kwds={"maxlags": REZAGOS_HAC})
        b, c = modelo.params["x"], modelo.params["y_l1"]
        valido = niveles.loc[etiqueta, "Conclusión"] == "Estacionaria"
        filas.append({
            "Variable": etiqueta,
            "Traspaso inmediato": round(b, 3),
            "Persistencia (c)": round(c, 3),
            "Traspaso largo plazo": round(b / (1 - c), 3),
            "Válido según ADF": "Sí" if valido else "No (serie no estacionaria)",
            "N": int(modelo.nobs),
        })
        registrar(f"Robustez en niveles {etiqueta}: largo plazo={round(b / (1 - c), 3)} "
                  f"({'válido' if valido else 'NO interpretable: serie no estacionaria'})", log)

    tabla = pd.DataFrame(filas)
    ruta = CARPETA_SALIDAS / "tabla5_robustez_niveles.csv"
    tabla.to_csv(ruta, index=False, encoding="utf-8", lineterminator="\n")
    registrar(f"Tabla guardada: {ruta.relative_to(CARPETA_PROYECTO)}", log)


# =============================================================================
# 10. FIGURA 3: TRASPASO ACUMULADO
# =============================================================================
def figura_traspaso(trayectorias, log):
    """Traspaso acumulado, mes a mes, según el modelo principal."""
    meses = np.arange(0, HORIZONTE + 1)
    figura, eje = plt.subplots(figsize=(10, 5))
    for etiqueta, trayectoria in trayectorias.items():
        eje.plot(meses, trayectoria, marker="o", markersize=3, label=etiqueta)
    eje.axhline(1, color="gray", linestyle="--", linewidth=0.8, label="Traspaso completo")
    eje.set_title("Traspaso acumulado ante un aumento de 1 punto en la tasa de referencia")
    eje.set_xlabel("Meses transcurridos")
    eje.set_ylabel("Variación acumulada de la tasa (puntos porcentuales)")
    eje.set_ylim(bottom=0)
    eje.legend()
    eje.grid(alpha=0.3)
    figura.text(0.01, 0.01, FUENTE, fontsize=8)
    ruta = CARPETA_SALIDAS / "fig3_traspaso.png"
    figura.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(figura)
    registrar(f"Figura guardada: {ruta.relative_to(CARPETA_PROYECTO)}", log)


# =============================================================================
# 11. PROGRAMA PRINCIPAL
# =============================================================================
def main():
    log = []
    estado = "ERROR"
    registrar("===== INICIO DE ANÁLISIS (04_analisis.py) =====", log)

    try:
        datos = leer_procesado(log)
        CARPETA_SALIDAS.mkdir(exist_ok=True)

        figura_series(datos, log)
        figura_spreads(datos, log)
        tabla_descriptivas(datos, log)
        tabla_adf = tabla_raiz_unitaria(datos, log)
        tabla = tabla_cointegracion(datos, log)

        cointegradas = (tabla["Conclusión"] == "Cointegradas").sum()
        registrar(f"Diagnóstico: {cointegradas} de {len(tabla)} tasas cointegradas con la "
                  f"tasa de referencia al {int(NIVEL * 100)}%", log)

        trayectorias = tabla_traspaso(datos, log)
        tabla_robustez_niveles(datos, tabla_adf, log)
        figura_traspaso(trayectorias, log)
        estado = "OK"

    except ErrorAnalisis as error:
        registrar(f"ERROR: {error}", log)
    except Exception as error:
        registrar(f"ERROR INESPERADO: {type(error).__name__}: {error}", log)
    finally:
        registrar(f"===== FIN. Estado: {estado} =====", log)
        with open(ARCHIVO_LOG, "a", encoding="utf-8") as archivo_log:
            archivo_log.write("\n".join(log) + "\n\n")

    if estado == "ERROR":
        sys.exit(1)


if __name__ == "__main__":
    main()
