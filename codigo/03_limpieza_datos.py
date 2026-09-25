# Autor: Santiago Piero Camayo Jiménez
# Código de matrícula: 2024200488G
# Tema N.º 6: Traspaso (pass-through) de la tasa de referencia del BCRP a las tasas del sistema financiero
# Fecha de extracción: 2026-09-24
"""
03_limpieza_datos.py - Etapa 2: depuración y generación del archivo procesado.

Entrada : datos_crudos/datos_crudos_<matricula>.csv  (no se modifica)
Salidas : datos_procesados/datos_procesados_<matricula>.csv
          log_ejecucion.txt  (se añade el registro de esta ejecución)
Ejecución: python codigo/03_limpieza_datos.py   (después de 01_extraccion_api.py)

Llave común declarada: fecha (mes-año), en formato AAAA-MM.
Fuentes: una sola vía (API de BCRPData), conforme a la Unidad I. No hay unión
entre fuentes; la llave queda declarada para la etapa de análisis.
"""

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# =============================================================================
# 1. PARÁMETROS
# =============================================================================
FECHA_INICIO = "2003-09"
FECHA_CORTE = "2025-12"

CODIGO_MATRICULA = "2024200488G"

# Variables extraídas de la fuente (deben venir del archivo crudo).
VARIABLES = ["tasa_referencia", "tasa_interbancaria", "tamn", "tipmn"]

# Variables derivadas: márgenes bancarios respecto de la tasa de política.
SPREADS = {
    "spread_activo": ("tamn", "tasa_referencia"),
    "spread_pasivo": ("tipmn", "tasa_referencia"),
}

DECIMALES_SPREAD = 2   # las tasas de la fuente traen 2 decimales
UMBRAL_OUTLIER = 3     # nº de desviaciones estándar para reportar una variación inusual

# =============================================================================
# 2. RUTAS RELATIVAS
# =============================================================================
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
ARCHIVO_CRUDO = CARPETA_PROYECTO / "datos_crudos" / f"datos_crudos_{CODIGO_MATRICULA}.csv"
CARPETA_PROCESADOS = CARPETA_PROYECTO / "datos_procesados"
ARCHIVO_PROCESADO = CARPETA_PROCESADOS / f"datos_procesados_{CODIGO_MATRICULA}.csv"
ARCHIVO_LOG = CARPETA_PROYECTO / "log_ejecucion.txt"


class ErrorLimpieza(Exception):
    """Problema que impide generar el archivo procesado."""


# =============================================================================
# 3. FUNCIONES AUXILIARES
# =============================================================================
def registrar(mensaje, log):
    """Muestra el mensaje en consola y lo acumula para escribirlo en el log."""
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}"
    print(linea)
    log.append(linea)


def sha256(archivo):
    """Huella digital del archivo: si cambia un solo byte, cambia el hash."""
    return hashlib.sha256(archivo.read_bytes()).hexdigest()


def respaldar_si_existe(archivo, log):
    """Si ya existe un archivo con el mismo nombre, lo mueve a una subcarpeta respaldos/."""
    if archivo.exists():
        carpeta_respaldo = archivo.parent / "respaldos"
        carpeta_respaldo.mkdir(exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = carpeta_respaldo / f"{archivo.stem}_{marca}{archivo.suffix}"
        contador = 1
        while destino.exists():
            destino = carpeta_respaldo / f"{archivo.stem}_{marca}_{contador}{archivo.suffix}"
            contador += 1
        shutil.move(str(archivo), str(destino))
        registrar(f"Archivo anterior movido a {destino.relative_to(CARPETA_PROYECTO)}", log)


# =============================================================================
# 4. LECTURA Y TIPIFICACIÓN
# =============================================================================
def leer_crudo(log):
    """Lee el archivo crudo como texto. El crudo nunca se modifica."""
    if not ARCHIVO_CRUDO.exists():
        raise ErrorLimpieza(f"No se encuentra {ARCHIVO_CRUDO.relative_to(CARPETA_PROYECTO)}. "
                            f"Ejecute primero 01_extraccion_api.py")
    crudo = pd.read_csv(ARCHIVO_CRUDO, dtype=str)
    registrar(f"Crudo leído: {ARCHIVO_CRUDO.relative_to(CARPETA_PROYECTO)} "
              f"({len(crudo)} filas, SHA-256 {sha256(ARCHIVO_CRUDO)})", log)

    faltantes = [c for c in ["fecha"] + VARIABLES if c not in crudo.columns]
    if faltantes:
        raise ErrorLimpieza(f"Al crudo le faltan columnas: {faltantes}")
    return crudo


def tipificar(crudo, log):
    """Convierte las tasas de texto a número. Si alguna conversión falla, se detiene."""
    datos = pd.DataFrame({"fecha": crudo["fecha"].str.strip()})
    for variable in VARIABLES:
        numeros = pd.to_numeric(crudo[variable], errors="coerce")
        fallidos = crudo.loc[numeros.isna(), ["fecha", variable]]
        if len(fallidos) > 0:
            raise ErrorLimpieza(f"{variable}: {len(fallidos)} valores no convertibles a número. "
                                f"Primeros casos: {fallidos.head(3).to_dict('records')}")
        datos[variable] = numeros
    registrar(f"Tipificación: {len(VARIABLES)} series convertidas a número, sin valores perdidos", log)
    return datos


# =============================================================================
# 5. CONTROLES DE INTEGRIDAD (detienen el script si fallan)
# =============================================================================
def verificar_integridad(datos, log):
    """Comprueba cobertura, unicidad y continuidad de la llave común."""
    esperadas = pd.period_range(FECHA_INICIO, FECHA_CORTE, freq="M").strftime("%Y-%m")

    duplicadas = datos.loc[datos["fecha"].duplicated(), "fecha"].tolist()
    if duplicadas:
        raise ErrorLimpieza(f"Fechas repetidas en la llave común: {duplicadas}")

    faltan = sorted(set(esperadas) - set(datos["fecha"]))
    sobran = sorted(set(datos["fecha"]) - set(esperadas))
    if faltan:
        raise ErrorLimpieza(f"Faltan {len(faltan)} meses del periodo declarado: {faltan[:5]}")
    if sobran:
        raise ErrorLimpieza(f"Hay {len(sobran)} meses fuera del periodo declarado: {sobran[:5]}")

    registrar(f"Integridad: {len(datos)} meses continuos de {FECHA_INICIO} a {FECHA_CORTE}, "
              f"sin duplicados ni huecos", log)


# =============================================================================
# 6. REVISIONES QUE SOLO INFORMAN (no modifican los datos)
# =============================================================================
def revisar_valores(datos, log):
    """Reporta rangos, coherencia económica y variaciones inusuales, sin alterar nada."""
    for variable in VARIABLES:
        serie = datos[variable]
        registrar(f"Rango {variable}: min {serie.min():.2f} ({datos.loc[serie.idxmin(), 'fecha']}) | "
                  f"max {serie.max():.2f} ({datos.loc[serie.idxmax(), 'fecha']}) | "
                  f"media {serie.mean():.2f}", log)
        if (serie < 0).any():
            registrar(f"ADVERTENCIA: {variable} tiene {(serie < 0).sum()} valores negativos", log)

    # Coherencia esperada: los bancos cobran (TAMN) más de lo que pagan (TIPMN).
    invertidos = datos.loc[datos["tamn"] <= datos["tipmn"], "fecha"].tolist()
    if invertidos:
        registrar(f"ADVERTENCIA: {len(invertidos)} meses con TAMN <= TIPMN: {invertidos[:5]}", log)
    else:
        registrar("Coherencia: TAMN > TIPMN en todos los meses", log)


def reportar_outliers(datos, log):
    """Identifica variaciones mensuales inusuales y las deja constancia SIN modificarlas.

    Criterio: variación mensual que se aleja más de UMBRAL_OUTLIER desviaciones
    estándar de la variación media de esa misma serie. En tasas de política
    monetaria un valor extremo no es un error de medición, sino una decisión
    del banco central, por eso se conserva.
    """
    for variable in VARIABLES:
        variacion = datos[variable].diff()
        desviacion = variacion.std()
        if not desviacion or pd.isna(desviacion):
            registrar(f"Outliers {variable}: serie sin variación, no aplica el criterio", log)
            continue
        limite = UMBRAL_OUTLIER * desviacion
        extremos = datos.loc[(variacion - variacion.mean()).abs() > limite, "fecha"]
        detalle = [f"{f} ({variacion[i]:+.2f})" for i, f in extremos.items()]
        registrar(f"Outliers {variable}: {len(detalle)} variaciones fuera de "
                  f"{UMBRAL_OUTLIER} desviaciones (limite {limite:.2f} pp). "
                  f"Se conservan: {detalle[:6]}", log)


# =============================================================================
# 7. VARIABLES DERIVADAS
# =============================================================================
def agregar_spreads(datos, log):
    """Calcula los márgenes respecto de la tasa de referencia.

    spread_activo = TAMN - tasa de referencia  -> margen de las tasas activas
    spread_pasivo = TIPMN - tasa de referencia -> margen de las tasas pasivas
    Si el traspaso fuera completo, estos márgenes serían estables ante cambios
    de la tasa de política; su movimiento es evidencia de traspaso incompleto.
    """
    for nombre, (variable, referencia) in SPREADS.items():
        datos[nombre] = (datos[variable] - datos[referencia]).round(DECIMALES_SPREAD)
        registrar(f"Derivada {nombre} = {variable} - {referencia} | "
                  f"media {datos[nombre].mean():.2f} pp | "
                  f"min {datos[nombre].min():.2f} | max {datos[nombre].max():.2f}", log)
    return datos


# =============================================================================
# 8. PROGRAMA PRINCIPAL
# =============================================================================
def main():
    log = []
    estado = "ERROR"
    registrar("===== INICIO DE LIMPIEZA (03_limpieza_datos.py) =====", log)
    registrar("Llave común: fecha (AAAA-MM). Fuente única: API de BCRPData (Unidad I), "
              "por lo que no corresponde unión entre fuentes", log)

    try:
        crudo = leer_crudo(log)
        datos = tipificar(crudo, log)
        datos = datos.sort_values("fecha").reset_index(drop=True)
        verificar_integridad(datos, log)
        revisar_valores(datos, log)
        reportar_outliers(datos, log)
        datos = agregar_spreads(datos, log)

        CARPETA_PROCESADOS.mkdir(exist_ok=True)
        respaldar_si_existe(ARCHIVO_PROCESADO, log)
        datos.to_csv(ARCHIVO_PROCESADO, index=False, encoding="utf-8", lineterminator="\n")

        sustantivas = len(VARIABLES) + len(SPREADS)
        registrar(f"Filas: {len(datos)} | Columnas: {datos.shape[1]} {list(datos.columns)} "
                  f"({sustantivas} sustantivas)", log)
        registrar(f"Guardado: {ARCHIVO_PROCESADO.relative_to(CARPETA_PROYECTO)} "
                  f"(SHA-256 {sha256(ARCHIVO_PROCESADO)})", log)
        registrar("HASH PARA EL README (archivo procesado): "
                  f"{sha256(ARCHIVO_PROCESADO)}", log)
        estado = "OK"

    except ErrorLimpieza as error:
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
