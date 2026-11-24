"""

utils.py — Módulo central de rutas y funciones compartidas


Uso en cualquier notebook del curso:

    import os, sys
    sys.path.append(os.path.abspath('../Utilidades'))   # desde Codigos/
    from utils import PROYECTO_BASE . .. (otras rutas y funciones)

    
Funciones disponibles:

    Inspección   : inspeccionar_dataset(), listar_tablas()
    Serving      : ver_serving(), tamano_mb()
    Apoyo        : ruta_relativa()


    Este archivo se actualiza en la medida en que nuevos notebooks necesitan nuevas rutas o funciones compartidas

"""

# ── Librerías ─────────────────────────────────────────────────────────────────

import os
import json
import sqlite3
import pandas as pd
from datetime import datetime


# ==============================================================================

# RUTAS DEL PROYECTO

# La raíz del repositorio se calcula a partir de la ubicación de este archivo
# (Utilidades/utils.py → carpeta padre), así funciona en cualquier equipo
# sin escribir rutas absolutas personales.

PROYECTO_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace(os.sep, '/')


# ── Carpeta privada (en .gitignore: credenciales y todo lo que no se sube) ──

PRIVADO_PATH = f'{PROYECTO_BASE}/Privado'



# ── Capa de ingesta ────────────────────────────────────────────────

DATASETS_RAW_PATH = f'{PROYECTO_BASE}/Ingesta_de_Datos/Datasets_raw'
DB_PATH           = f'{PROYECTO_BASE}/Ingesta_de_Datos/Base_de_datos/base_datos.db'


# ── Capa de extracción ─────────────────────────────────────────────

EXTRACCION_PATH = f'{PROYECTO_BASE}/Extraccion_de_Datos'
EXTRACCION_LOGS = f'{EXTRACCION_PATH}/Logs'               # cdc_<etiqueta>.json y extraccion_log.jsonl
EXPORTS_PATH    = f'{EXTRACCION_PATH}/Exportaciones'      # comparación de formatos (se regenera, no se sube)


# ── Capa de transformación ─────────────────────────────────────────

TRANSFORMACION_PATH     = f'{PROYECTO_BASE}/Transformacion_de_Datos'
PROCESSED_PATH          = f'{TRANSFORMACION_PATH}/Processed'      # transformed_<etiqueta>.parquet
TRANSFORMACION_LOGS     = f'{TRANSFORMACION_PATH}/Logs'           # transformacion_log.jsonl y lineage
TRANSFORMACION_REPORTES = f'{TRANSFORMACION_PATH}/Reportes'       # bitácora y calidad antes vs. después


# ── Capa de modelado (SERVING) ─────────────────────────────────────

MODELADO_PATH          = f'{PROYECTO_BASE}/Modelado_de_Datos'
SERVING_DB             = f'{MODELADO_PATH}/serving.db'            # los tres esquemas estrella
PRUEBAS_PATH           = f'{MODELADO_PATH}/Pruebas'               # archivos de la prueba de carga (se pueden borrar)
MODELADO_REPORTES_PATH = f'{MODELADO_PATH}/Reportes'              # mediciones_<etiqueta>.csv


# ==============================================================================
# FUNCIONES DE INSPECCIÓN


def inspeccionar_dataset(df, nombre='Dataset'):

    """

    Muestra un perfil básico de un DataFrame:
    dimensiones, tipos de datos, valores nulos y primeras filas.

    Parámetros:

        df     : DataFrame a inspeccionar
        nombre : etiqueta descriptiva para el encabezado

    """


    # Encabezado con el nombre del dataset
    print(f'\n{"=" * 55}')
    print(f'  DATASET: {nombre}')
    print(f'{"=" * 55}')

    # Dimensiones: df.shape = (filas, columnas)
    print(f'  Filas    : {df.shape[0]:,}')
    print(f'  Columnas : {df.shape[1]}')
    print(f'\n  Tipos de datos y valores nulos:')

    # Por cada columna: su tipo, cuántos nulos tiene y qué porcentaje del total representan
    for col, dtype in df.dtypes.items():
        nulos = df[col].isna().sum()
        pct = nulos / len(df) * 100
        print(f'    {col:<28} {str(dtype):<12} nulos: {nulos} ({pct:.1f}%)')

    # Muestra de las primeras filas
    print(f'\n  Primeras 3 filas:')
    try:
        # En un notebook, display() muestra la tabla con formato
        from IPython.display import display
        display(df.head(3))
    except ImportError:
        # Fuera de un notebook (sin IPython) se imprime como texto plano
        print(df.head(3).to_string())
    print()




def listar_tablas(db_path=None):

    """
    Lista todas las tablas del archivo .db clasificadas por capa
    (raw_, extracted_, transformed_, serving_).

    Parámetros:
        db_path : ruta al archivo .db (usa DB_PATH por defecto)

    Retorna:
        Lista con los nombres de las tablas encontradas
    """

    # Si no se indica otra ruta, se usa la base de la capa de ingesta (base_datos.db)
    if db_path is None:
        db_path = DB_PATH

    # Conexión a SQLite y lectura del catálogo interno (sqlite_master),
    # que guarda el nombre de cada tabla de la base
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tablas = [row[0] for row in cursor.fetchall()]

    # Encabezado de la tabla que se imprime
    print(f'\n  Tablas en: {os.path.basename(db_path)}\n')
    print(f'  {"TABLA":<35} {"CAPA":<15} {"FILAS":>8} {"COLS":>6}')
    print(f'  {"-"*35} {"-"*15} {"-"*8} {"-"*6}')

    for tabla in tablas:
        # Se carga la tabla completa para contar filas y columnas
        df_t = pd.read_sql_query(f'SELECT * FROM "{tabla}"', conn)
        # La capa se deduce del prefijo del nombre (raw_, extracted_, ...);
        # si el nombre no tiene "_", se marca como 'otra'
        capa = tabla.split('_')[0] + '_' if '_' in tabla else 'otra'
        print(f'  {tabla:<35} {capa:<15} {df_t.shape[0]:>8,} {df_t.shape[1]:>6}')

    # Se cierra la conexión y se regresa la lista de nombres
    conn.close()
    return tablas





# ==============================================================================
# FUNCIONES DE LA CAPA SERVING


def ver_serving(ruta=None):

    """
    Muestra las tablas y vistas de un archivo .db de DuckDB (serving.db),
    con su número de filas y columnas.

    Parámetros:
        ruta : ruta al archivo .db (usa SERVING_DB por defecto)
    """

    import duckdb

    # Si no se indica otra ruta, se usa la base de la capa SERVING
    if ruta is None:
        ruta = SERVING_DB

    if not os.path.exists(ruta):
        print(f'  No existe todavía: {ruta}')
        return

    # Catálogo de DuckDB: tablas (duckdb_tables) y vistas creadas por el usuario (duckdb_views)
    con = duckdb.connect(ruta)
    objetos = con.sql('''
        SELECT table_name AS nombre, 'tabla' AS tipo FROM duckdb_tables()
        UNION ALL
        SELECT view_name, 'vista' FROM duckdb_views() WHERE NOT internal
        ORDER BY tipo, nombre''').fetchall()

    print(f'\n  DuckDB: {os.path.basename(ruta)}\n')
    print(f'  {"NOMBRE":<30} {"TIPO":<8} {"FILAS":>10} {"COLS":>6}')
    print(f'  {"-"*30} {"-"*8} {"-"*10} {"-"*6}')

    for nombre, tipo in objetos:
        filas = con.sql(f'SELECT COUNT(*) FROM "{nombre}"').fetchall()[0][0]
        cols = len(con.sql(f'SELECT * FROM "{nombre}" LIMIT 0').columns)
        print(f'  {nombre:<30} {tipo:<8} {filas:>10,} {cols:>6}')

    con.close()




def tamano_mb(ruta):

    """
    Regresa el tamaño de un archivo en megabytes (MB).

    Parámetros:
        ruta : ruta al archivo
    """

    return os.path.getsize(ruta) / 1024 / 1024




# ==============================================================================
# FUNCIONES DE APOYO


def ruta_relativa(ruta):

    """
    Regresa la ruta relativa a la raíz del proyecto (PROYECTO_BASE).

    Se usa al imprimir rutas en los notebooks: así los resultados no muestran
    carpetas personales de la computadora donde se ejecutaron.

    Parámetros:
        ruta : ruta absoluta de un archivo o carpeta del proyecto

    Ejemplo:
        ruta_relativa(DB_PATH)  →  'Ingesta_de_Datos/Base_de_datos/base_datos.db'
    """

    return os.path.relpath(ruta, PROYECTO_BASE).replace(os.sep, '/')
