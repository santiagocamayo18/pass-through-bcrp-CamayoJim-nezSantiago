# Autor: Santiago Piero Camayo Jiménez
# Código de matrícula: 2024200488G
# Tema N.º 6: Traspaso (pass-through) de la tasa de referencia del BCRP a las tasas del sistema financiero
# Fecha de extracción: 2026-09-24   
"""
01_extraccion_api.py - Etapa 1: extracción automatizada desde la API de BCRPData.

Entrada : ninguna. Consulta la API pública de BCRPData (no requiere clave).
Salidas : datos_crudos/datos_crudos_<matricula>.json  -> respuesta original de la API, byte por byte
          datos_crudos/datos_crudos_<matricula>.csv   -> la misma información en forma de tabla
          log_ejecucion.txt                            -> registro acumulativo de cada ejecución
Ejecución: python codigo/01_extraccion_api.py   (desde la carpeta del proyecto)
"""

import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# =============================================================================
# 1. PARÁMETROS CONGELADOS DE LA CONSULTA (no usar fechas dinámicas)
# =============================================================================
FECHA_INICIO = "2003-09"
FECHA_CORTE = "2025-12"

CODIGO_MATRICULA = "2024200488G"

# Código BCRPData -> (nombre final de la variable, textos que debe contener el nombre oficial).
# Los textos sirven para comprobar que la API devolvió exactamente la serie pedida.
SERIES = {
    "PD04722MM": ("tasa_referencia", ["Referencia"]),
    "PN07819NM": ("tasa_interbancaria", ["Interbancaria", "en MN"]),  # MN = soles
    "PN07807NM": ("tamn", ["TAMN"]),
    "PN07816NM": ("tipmn", ["TIPMN"]),
}

URL_BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
FORMATO = "json"
IDIOMA = "esp"
TIMEOUT_SEGUNDOS = 60
MAX_INTENTOS = 3
PAUSA_SEGUNDOS = 3
USER_AGENT = "Proyecto-FinanzasI-UNCP/1.0 (uso academico; S. Camayo)"

# =============================================================================
# 2. RUTAS RELATIVAS A LA CARPETA DEL PROYECTO
# =============================================================================
# Este archivo está en <proyecto>/codigo/, por eso la carpeta del proyecto es la "abuela".
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_CRUDOS = CARPETA_PROYECTO / "datos_crudos"
ARCHIVO_JSON = CARPETA_CRUDOS / f"datos_crudos_{CODIGO_MATRICULA}.json"
ARCHIVO_CSV = CARPETA_CRUDOS / f"datos_crudos_{CODIGO_MATRICULA}.csv"
ARCHIVO_LOG = CARPETA_PROYECTO / "log_ejecucion.txt"

# La API escribe los meses abreviados en español ("Sep.2003"). "Set" se incluye por precaución.
MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7,
         "Ago": 8, "Sep": 9, "Set": 9, "Oct": 10, "Nov": 11, "Dic": 12}


class ErrorExtraccion(Exception):
    """Problema que impide continuar: la extracción se detiene sin guardar datos."""


# =============================================================================
# 3. FUNCIONES AUXILIARES
# =============================================================================
def registrar(mensaje, log):
    """Muestra el mensaje en consola y lo acumula para escribirlo en el log."""
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}"
    print(linea)
    log.append(linea)


def a_formato_api(fecha):
    """Convierte '2003-09' al formato de periodo de la API: '2003-9'."""
    anio, mes = fecha.split("-")
    return f"{anio}-{int(mes)}"


def construir_url():
    """Arma el endpoint: /api/[códigos]/[formato]/[inicio]/[fin]/[idioma]."""
    codigos = "-".join(SERIES)
    return (f"{URL_BASE}/{codigos}/{FORMATO}/"
            f"{a_formato_api(FECHA_INICIO)}/{a_formato_api(FECHA_CORTE)}/{IDIOMA}")


def convertir_fecha(texto):
    """Convierte 'Sep.2003' en '2003-09'. Falla si el formato no es el esperado."""
    try:
        mes_texto, anio = texto.split(".")
        return f"{int(anio):04d}-{MESES[mes_texto]:02d}"
    except (ValueError, KeyError, AttributeError):
        raise ErrorExtraccion(f"Fecha con formato inesperado: {texto!r}")


def sha256(archivo):
    """Huella digital del archivo: si cambia un solo byte, cambia el hash."""
    return hashlib.sha256(archivo.read_bytes()).hexdigest()


# =============================================================================
# 4. DESCARGA CON REINTENTOS
# =============================================================================
def descargar(url, log):
    """Hace la solicitud GET. Reintenta solo ante fallas de red o errores del servidor (5xx)."""
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            respuesta = requests.get(url, headers={"User-Agent": USER_AGENT},
                                     timeout=TIMEOUT_SEGUNDOS)
        except requests.RequestException as error:
            registrar(f"Intento {intento}: error de red ({type(error).__name__}: {error})", log)
        else:
            registrar(f"Intento {intento}: código HTTP {respuesta.status_code}", log)
            if respuesta.status_code == 200:
                return respuesta
            if respuesta.status_code < 500:  # 4xx: la solicitud está mal, reintentar no sirve
                raise ErrorExtraccion(f"HTTP {respuesta.status_code}. "
                                      f"Inicio de la respuesta: {respuesta.text[:200]!r}")
        if intento < MAX_INTENTOS:
            time.sleep(PAUSA_SEGUNDOS * intento)
    raise ErrorExtraccion(f"No se obtuvo una respuesta válida tras {MAX_INTENTOS} intentos")


# =============================================================================
# 5. LECTURA Y VALIDACIÓN DE LA RESPUESTA
# =============================================================================
def leer_json(texto):
    """Comprueba que la respuesta sea JSON y tenga la estructura documentada."""
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        raise ErrorExtraccion(f"La respuesta no es JSON válido. Inicio: {texto[:200]!r}")
    if not isinstance(datos, dict) or "config" not in datos or "periods" not in datos:
        raise ErrorExtraccion("El JSON no tiene las claves esperadas 'config' y 'periods'")
    if not datos["periods"]:
        raise ErrorExtraccion("La API respondió, pero sin periodos (respuesta vacía)")
    return datos


def emparejar_series(datos, log):
    """Relaciona cada serie devuelta con su código usando el nombre oficial.

    La API no devuelve los códigos ni respeta el orden en que se piden, así que
    el orden de llegada no puede usarse para identificar las series.
    Devuelve los nombres finales en el orden en que llegaron los valores.
    """
    series_api = datos["config"].get("series", [])
    if len(series_api) != len(SERIES):
        raise ErrorExtraccion(f"Se pidieron {len(SERIES)} series y llegaron {len(series_api)}")

    pendientes = dict(SERIES)  # se va vaciando conforme se identifica cada serie
    nombres_en_orden = []
    for serie in series_api:
        nombre_oficial = serie.get("name", "")
        coincidencias = [codigo for codigo, (_, textos) in pendientes.items()
                         if all(t.lower() in nombre_oficial.lower() for t in textos)]
        if len(coincidencias) != 1:
            raise ErrorExtraccion(f"El nombre {nombre_oficial!r} coincide con "
                                  f"{len(coincidencias)} series esperadas {coincidencias}: "
                                  f"no se puede identificar sin ambigüedad")
        codigo = coincidencias[0]
        nombre_final = pendientes.pop(codigo)[0]
        nombres_en_orden.append(nombre_final)
        registrar(f"{codigo} -> {nombre_final}: {nombre_oficial}", log)
    return nombres_en_orden


def construir_tabla(datos, nombres_en_orden):
    """Pasa el JSON a tabla. Los valores se copian como texto, sin convertir ni redondear."""
    filas = []
    for periodo in datos["periods"]:
        valores = periodo.get("values", [])
        if len(valores) != len(SERIES):
            raise ErrorExtraccion(f"El periodo {periodo.get('name')!r} trae "
                                  f"{len(valores)} valores en lugar de {len(SERIES)}")
        fila = {"periodo_bcrp": periodo.get("name"),
                "fecha": convertir_fecha(periodo.get("name"))}
        fila.update(zip(nombres_en_orden, valores))  # cada valor con su serie identificada
        filas.append(fila)

    # Las columnas se ordenan siempre igual, sin importar el orden de la API.
    columnas = ["periodo_bcrp", "fecha"] + [nombre for nombre, _ in SERIES.values()]
    tabla = pd.DataFrame(filas, dtype=str)[columnas]
    if tabla["fecha"].duplicated().any():
        raise ErrorExtraccion("Hay meses repetidos en la respuesta")
    for nombre, _ in SERIES.values():
        if pd.to_numeric(tabla[nombre], errors="coerce").isna().all():
            raise ErrorExtraccion(f"La serie {nombre} llegó vacía (ningún valor numérico)")
    return tabla


def revisar_calidad(tabla):
    """Controles que NO detienen el script: se informan como advertencias en el log."""
    advertencias = []
    esperadas = set(pd.period_range(FECHA_INICIO, FECHA_CORTE, freq="M").strftime("%Y-%m"))
    obtenidas = set(tabla["fecha"])
    if esperadas - obtenidas:
        advertencias.append(f"Faltan meses: {sorted(esperadas - obtenidas)}")
    if obtenidas - esperadas:
        advertencias.append(f"Meses fuera del periodo: {sorted(obtenidas - esperadas)}")

    for nombre, _ in SERIES.values():
        numeros = pd.to_numeric(tabla[nombre], errors="coerce")  # solo para contar, no se guarda
        no_numericos = tabla.loc[numeros.isna(), nombre]
        if len(no_numericos) > 0:
            advertencias.append(f"{nombre}: {len(no_numericos)} valores no numéricos "
                                f"{sorted(set(no_numericos))}")
        if (numeros < 0).any():
            advertencias.append(f"{nombre}: {(numeros < 0).sum()} valores negativos")
    return advertencias


# =============================================================================
# 6. GUARDADO SIN SOBRESCRIBIR EN SILENCIO
# =============================================================================
def respaldar_si_existe(archivo, log):
    """Si ya existe un archivo con el mismo nombre, lo mueve a datos_crudos/respaldos/."""
    if archivo.exists():
        carpeta_respaldo = archivo.parent / "respaldos"
        carpeta_respaldo.mkdir(exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = carpeta_respaldo / f"{archivo.stem}_{marca}{archivo.suffix}"
        contador = 1
        while destino.exists():  # nunca pisar un respaldo previo
            destino = carpeta_respaldo / f"{archivo.stem}_{marca}_{contador}{archivo.suffix}"
            contador += 1
        shutil.move(str(archivo), str(destino))
        registrar(f"Archivo anterior movido a {destino.relative_to(CARPETA_PROYECTO)}", log)


# =============================================================================
# 7. PROGRAMA PRINCIPAL
# =============================================================================
def main():
    log = []
    estado = "ERROR"
    url = construir_url()
    registrar("===== INICIO DE EXTRACCIÓN (01_extraccion_api.py) =====", log)
    registrar(f"Endpoint: {url}", log)
    registrar(f"Periodo solicitado: {FECHA_INICIO} a {FECHA_CORTE}", log)
    registrar(f"Códigos consultados: {', '.join(SERIES)}", log)

    try:
        respuesta = descargar(url, log)
        datos = leer_json(respuesta.text)
        nombres_en_orden = emparejar_series(datos, log)
        tabla = construir_tabla(datos, nombres_en_orden)
        advertencias = revisar_calidad(tabla)

        # Solo se guarda cuando todas las validaciones críticas pasaron.
        CARPETA_CRUDOS.mkdir(exist_ok=True)
        respaldar_si_existe(ARCHIVO_JSON, log)
        respaldar_si_existe(ARCHIVO_CSV, log)
        ARCHIVO_JSON.write_bytes(respuesta.content)  # copia exacta de lo recibido
        tabla.to_csv(ARCHIVO_CSV, index=False, encoding="utf-8", lineterminator="\n")

        registrar(f"Filas: {len(tabla)} | Columnas: {tabla.shape[1]} {list(tabla.columns)}", log)
        registrar(f"Rango obtenido: {tabla['fecha'].iloc[0]} a {tabla['fecha'].iloc[-1]}", log)
        registrar(f"Guardado: {ARCHIVO_JSON.relative_to(CARPETA_PROYECTO)} "
                  f"(SHA-256 {sha256(ARCHIVO_JSON)})", log)
        registrar(f"Guardado: {ARCHIVO_CSV.relative_to(CARPETA_PROYECTO)} "
                  f"(SHA-256 {sha256(ARCHIVO_CSV)})", log)
        for aviso in advertencias:
            registrar(f"ADVERTENCIA: {aviso}", log)
        estado = "OK" if not advertencias else "OK CON ADVERTENCIAS"

    except ErrorExtraccion as error:
        registrar(f"ERROR: {error}", log)
    except Exception as error:  # cualquier falla no prevista también queda en el log
        registrar(f"ERROR INESPERADO: {type(error).__name__}: {error}", log)
    finally:
        registrar(f"===== FIN. Estado: {estado} =====", log)
        with open(ARCHIVO_LOG, "a", encoding="utf-8") as archivo_log:
            archivo_log.write("\n".join(log) + "\n\n")

    if estado == "ERROR":
        sys.exit(1)


if __name__ == "__main__":
    main()
