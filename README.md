# Proyecto final — Fundamentos de Ingeniería de Datos

Pipeline completo **RAW → EXTRACTED → TRANSFORMED → SERVING** con datos de autos usados, más una app de Streamlit que usa esos datos.

> Este README es la bitácora del proyecto: aquí se documentan las decisiones y dónde está la evidencia de cada capa para armar el reporte. Se actualiza al terminar cada capa.

---

## 1. Propósito

| Elemento | Definición |
|---|---|
| **Pregunta** | ¿Cuánto vale un carro según sus características? |
| **Quién la usa** | Un agente de ventas que valúa autos, o una persona común que quiere saber cuánto vale su carro o el que piensa comprar |
| **Forma de respuesta** | **Las dos opciones** en una sola app: **Modelo** ("¿Cuánto vale mi carro?": formulario → precio estimado + métricas) y **Tablero** ("¿Cuánto vale el carro que quiero comprar?": gráficas con filtros) |
| **Variable objetivo** | `price` (precio en USD) |

## 2. Fuente de datos

| Etiqueta | Nombre | URL | Formato | Licencia |
|---|---|---|---|---|
| `autos` | Used Cars Dataset (Cars.com) | <https://www.kaggle.com/datasets/andreinovikov/used-cars-dataset> | CSV | CC0-1.0 |

**Por qué sirve:** son anuncios reales de venta al público (2023), con 762 091 filas de 30 marcas. Trae el precio y las características que determinan el valor de un auto: marca, modelo, año, millaje, motor, transmisión, tracción, combustible, rendimiento, accidentes, si tuvo un solo dueño y si fue de uso personal.

**Cómo se eligió:** [Codigos/BUSQUEDA.ipynb](Codigos/BUSQUEDA.ipynb).
- Primero se buscó en México y Latinoamérica, y se descartó: hay pocas filas, falta el kilometraje o son precios de referencia.
- Después se buscó en EE. UU. y se compararon 4 candidatos.

## 3. Decisiones de diseño

| Decisión | Justificación | Dónde |
|---|---|---|
| Muestra de **200 000 filas** | El CSV completo (unos 140 MB) supera el límite de 100 MB por archivo de GitHub. 200 000 filas bastan para el modelo y el tablero | INGESTA, PASO 2 |
| Muestra **estratificada por marca** con el método del mayor residuo | Cada marca conserva su proporción del mercado (diferencia máxima: 0.001 puntos porcentuales) | INGESTA, PASO 4 |
| Semilla fija `random_state=42` | La muestra es reproducible: siempre salen las mismas filas | INGESTA, PASO 4 |
| La muestra **no limpia nada** | RAW debe quedar crudo. La limpieza va en TRANSFORMACION | INGESTA, PASO 4 (verificación) |
| El CSV completo no se sube | Está en `.gitignore`. INGESTA lo vuelve a descargar de Kaggle si no existe | `.gitignore` |
| Control de cambios por **huella SHA-256** de cada fila | `raw_autos` no tiene fecha de publicación, así que no se puede usar marca de agua. La huella detecta filas nuevas o modificadas | EXTRACCION, PASOS 2 y 3 |
| Carga con `append` (no `replace`) | Conserva los lotes anteriores. El CDC evita duplicar filas | EXTRACCION, PASO 3 |
| `Exportaciones/` no se sube | El JSON de la comparación de formatos pesa 115 MB. EXTRACCION lo regenera | `.gitignore` |

## 4. Mapa del flujo

```
Kaggle (andreinovikov/used-cars-dataset)
  │
  ▼  INGESTA.ipynb ................................................ RAW
  │    Datasets_raw/andreinovikov_used-cars-dataset/cars.csv            (completo, solo local)
  │    Datasets_raw/andreinovikov_used-cars-dataset/cars_muestra.csv    (200k filas)
  │    Base_de_datos/base_datos.db → raw_autos
  │
  ▼  EXTRACCION.ipynb ............................................. EXTRACTED
  │    Base_de_datos/base_datos.db → extracted_autos
  │    Extraccion_de_Datos/Logs/cdc_autos.json · Extraccion_de_Datos/Logs/extraccion_log.jsonl
  │
  ▼  TRANSFORMACION.ipynb ......................................... TRANSFORMED (pendiente)
  │    Processed/transformed_autos.parquet · lineage · bitácora · calidad antes vs. después
  │
  ▼  MODELADO.ipynb ............................................... SERVING     (pendiente)
  │    Modelado_de_Datos/serving.db (esquema estrella)
  │
  ▼  streamlit/app.py ............................................. USO         (pendiente)
       tablero + modelo.joblib
```

## 5. Evidencias por capa

### RAW — [Codigos/INGESTA.ipynb](Codigos/INGESTA.ipynb) ✅

| Evidencia | Valor | Dónde |
|---|---|---|
| Tabla de metadatos de la fuente | Etiqueta, nombre, URL, formato y licencia | PASO 2 |
| Filas y columnas del dataset completo | 762 091 × 20 | PASO 3 |
| Filas y columnas ingestadas (muestra) | **200 000 × 20** | PASOS 5 y 6 |
| Proporción por marca: completo vs. muestra | Diferencia máxima de 0.001 puntos porcentuales | PASO 4 |
| La muestra es una copia fiel | Mismas columnas, mismos tipos y filas idénticas a su original | PASO 4 |
| La tabla en SQLite es igual al CSV | Mismas 200 000 filas y 20 columnas | PASO 6 |
| Tamaño de `cars_muestra.csv` | 36.6 MB | PASO 4 |
| Tamaño de `base_datos.db` (solo `raw_autos`) | 35.6 MB | PASO 6 |

**Problemas de calidad detectados en RAW**, que se tratarán en TRANSFORMACION:
- Precios imposibles: desde 1 USD hasta más de 2 millones.
- Años desde 1915.
- Columnas con muchos nulos: `price_drop` (46 %), `seller_rating` (28 %) y `mpg` (18.5 %).
- Texto sin estandarizar en `transmission`, `fuel_type` y los colores.
- La versión del auto viene mezclada en `model` (por ejemplo, "ILX Hybrid 1.5L").

### EXTRACTED — [Codigos/EXTRACCION.ipynb](Codigos/EXTRACCION.ipynb) ✅

| Evidencia | Valor | Dónde |
|---|---|---|
| Filas RAW vs. EXTRACTED | **200 000 = 200 000** (extracción completa) | PASO 5 |
| Columnas | 20 originales + 4 de metadatos (`_batch_id`, `_extracted_at`, `_source_table`, `_row_hash`) = **24** | PASO 5 |
| Control de cambios, 1.ª ejecución | `full_load`: 200 000 filas leídas, **200 000 nuevas**, lote 1 | PASO 4.1 |
| Control de cambios, 2.ª ejecución | `incremental`: 200 000 filas leídas, **0 nuevas**. La tabla no crece | PASO 4.2 |
| Estado del CDC | `Extraccion_de_Datos/Logs/cdc_autos.json` | PASO 4 |
| Log de auditoría | `Extraccion_de_Datos/Logs/extraccion_log.jsonl`, 2 operaciones exitosas | PASO 6 |
| Metadatos completos | 0 nulos en los 4 metadatos | PASO 5 |
| Tamaño de `base_datos.db` (raw + extracted) | 80.9 MB | PASO 5 |
| Comparación de formatos | CSV 45.9 MB · JSON 115 MB · **Parquet 7.7 MB**. Solo Parquet conserva todos los tipos de dato | PASO 7 |

**Hallazgo para TRANSFORMACION:** hay 199 388 huellas distintas en 200 000 filas. Es decir, **612 filas son duplicados exactos** (610 anuncios repetidos).
### TRANSFORMED — pendiente
### SERVING — pendiente
### Uso de los datos (Streamlit) — pendiente

## 6. Estructura del repositorio

```
├── Codigos/
│   ├── BUSQUEDA.ipynb          ← selección del dataset
│   ├── INGESTA.ipynb           ← RAW
│   ├── EXTRACCION.ipynb        ← EXTRACTED
│   ├── TRANSFORMACION.ipynb    ← TRANSFORMED
│   ├── MODELADO.ipynb          ← SERVING
│   ├── ALMACENAMIENTO.ipynb    ← (actividad anterior, por confirmar con el profesor)
│   └── SQL_CONSULTAS.ipynb     ← (actividad anterior, por confirmar con el profesor)
├── Utilidades/utils.py         ← rutas y funciones compartidas
├── Ingesta_de_Datos/
│   ├── Datasets_raw/andreinovikov_used-cars-dataset/cars_muestra.csv
│   └── Base_de_datos/base_datos.db     ← raw_autos, extracted_autos
├── Extraccion_de_Datos/
│   ├── Logs/cdc_autos.json
│   ├── Logs/extraccion_log.jsonl
│   └── Exportaciones/              ← comparación de formatos (no se sube)
├── Privado/                    ← credenciales (no se sube)
└── requirements.txt
```

## 7. Cómo ejecutar

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

1. Copia tu `kaggle.json` a `Privado/` (ver [Privado/LEEME.md](Privado/LEEME.md)).
2. Ejecuta los notebooks de `Codigos/` en orden: INGESTA → EXTRACCION → TRANSFORMACION → MODELADO.
   - `BUSQUEDA.ipynb` es opcional: solo documenta cómo se eligió el dataset.
