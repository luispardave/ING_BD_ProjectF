"""
app.py — ¿Cuánto vale mi carro?

Valuador y explorador de autos usados (anuncios de Cars.com, EE. UU.).

  · Pestaña 1 — ¿Cuánto vale mi carro?          → modelo de regresión lineal (modelo.joblib)
  · Pestaña 2 — ¿Cuánto vale el que quiero comprar? → tablero sobre serving.db (esquema estrella)
  · Pestaña 3 — Sobre el modelo                  → métricas y efecto de cada variable

Ejecutar desde esta carpeta:

    streamlit run app.py

Todos los archivos se leen con rutas relativas a esta carpeta.
"""

import json
from pathlib import Path

import altair as alt
import duckdb
import joblib
import pandas as pd
import streamlit as st


# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

CARPETA = Path(__file__).parent                       # la carpeta de la app (rutas relativas a ella)

SERVING_DB      = CARPETA / 'serving.db'
MODELO_PATH     = CARPETA / 'modelo.joblib'
INFO_PATH       = CARPETA / 'modelo_info.json'
BANNER          = CARPETA / 'banner.png'
BANNER_PROFESOR = CARPETA / 'banner_profesor.png'
GRAFICA_MODELO  = CARPETA / 'real_vs_predicho.png'

KM_POR_MILLA = 1.609344
TIPO_CAMBIO  = 18.50                      # MXN por 1 USD (referencia; el usuario lo puede ajustar)
# Tonos del banner, aclarados para que se lean sobre el fondo oscuro
AZUL, MAGENTA = '#6F93F0', '#EC5C95'

# Los datos están en inglés; la interfaz los muestra en español
TRADUCCION = {
    'Automatic': 'Automática', 'Manual': 'Manual', 'CVT': 'CVT',
    'FWD': 'Delantera (FWD)', 'RWD': 'Trasera (RWD)', 'AWD': 'Integral (AWD)', '4WD': '4x4 (4WD)',
    'Gasoline': 'Gasolina', 'Hybrid': 'Híbrido', 'Plug-In Hybrid': 'Híbrido enchufable', 'Diesel': 'Diésel',
    'Flex Fuel': 'Flex (E85)', 'Electric': 'Eléctrico', 'Other': 'Otro', 'Unknown': 'Desconocido',
    'Luxury': 'Lujo', 'Mainstream': 'Masiva',
    'Black': 'Negro', 'White': 'Blanco', 'Gray': 'Gris', 'Silver': 'Plata', 'Blue': 'Azul', 'Red': 'Rojo',
    'Green': 'Verde', 'Brown': 'Café', 'Beige': 'Beige', 'Gold': 'Dorado', 'Yellow': 'Amarillo',
    'Orange': 'Naranja', 'Purple': 'Morado',
    'USA': 'EE. UU.', 'Japan': 'Japón', 'Germany': 'Alemania', 'South Korea': 'Corea del Sur',
    'UK': 'Reino Unido', 'Sweden': 'Suecia',
}

def es(valor):
    """Traduce un valor del dataset para mostrarlo en la interfaz."""
    return TRADUCCION.get(valor, valor)


st.set_page_config(page_title='¿Cuánto vale mi carro?', page_icon='🚗', layout='wide')

# Fondo con degradado en los tonos del banner (el tema oscuro base está en .streamlit/config.toml)
st.markdown('''
<style>
.stApp {
    background: linear-gradient(135deg, #2B1438 0%, #1A2150 45%, #10204A 100%);
    background-attachment: fixed;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #3A1543 0%, #1B2556 100%); }
.tarjeta {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 12px;
    padding: 14px 18px;
    height: 100%;
}
.tarjeta .titulo  { font-size: 0.9rem; opacity: 0.8; margin-bottom: 4px; }
.tarjeta .valor   { font-size: clamp(1.25rem, 2.1vw, 1.9rem); font-weight: 700; line-height: 1.25; }
.tarjeta .valor span { white-space: nowrap; }      /* los números no se parten; el renglón corta entre ellos */
.tarjeta .detalle { font-size: 0.85rem; opacity: 0.75; margin-top: 4px; }
</style>
''', unsafe_allow_html=True)


# ==============================================================================
# DATOS Y MODELO
# ==============================================================================

@st.cache_resource
def conexion():
    """Conexión de solo lectura a serving.db (se abre una sola vez)."""
    return duckdb.connect(str(SERVING_DB), read_only=True)


@st.cache_data(show_spinner=False)
def consulta(sql, params=()):
    """Ejecuta una consulta SQL sobre serving.db y regresa un DataFrame (con caché)."""
    return conexion().cursor().execute(sql, list(params)).df()


@st.cache_resource
def cargar_modelo():
    with open(INFO_PATH, encoding='utf-8') as f:
        info = json.load(f)
    return joblib.load(MODELO_PATH), info


modelo, info = cargar_modelo()


# Anuncios con sus dimensiones: base de todas las consultas del tablero (hechos + dimensiones)
ANUNCIOS = '''
    SELECT f.listing_id, f.price, f.price_drop, f.mileage_km, f.seller_rating,
           y.year, y.age,
           v.manufacturer, v.base_model, v.model, v.brand_segment, v.brand_country,
           p.fuel_type, p.transmission, p.drivetrain,
           h.accidents_or_damage, h.one_owner,
           s.seller_name
    FROM fact_listings AS f
    JOIN dim_vehicle    AS v USING (vehicle_id)
    JOIN dim_year       AS y USING (year)
    JOIN dim_powertrain AS p USING (powertrain_id)
    JOIN dim_history    AS h USING (history_id)
    JOIN dim_seller     AS s USING (seller_id)
'''


def grafica(chart):
    st.altair_chart(chart, width='stretch')


def dinero(x):
    return f'${x:,.0f}'


def tarjeta(col, titulo, partes, detalle=''):
    """Tarjeta de resultado: cada parte del valor se mantiene completa y el texto salta de renglón entre partes
    (en lugar de cortarse con «…» como st.metric)."""
    valor = ''.join(f'<span>{p}</span>' if i % 2 == 0 else p for i, p in enumerate(partes))
    html = (f'<div class="tarjeta"><div class="titulo">{titulo}</div><div class="valor">{valor}</div>'
            f'<div class="detalle">{detalle}</div></div>')
    col.markdown(html.replace('$', '&#36;'), unsafe_allow_html=True)   # &#36; evita que «$» se lea como LaTeX


def a_numero(valor):
    """Convierte una opción de lista o un texto escrito («25000», «$25,000», «25k») a entero; None si no se puede."""
    if isinstance(valor, (int, float)):
        return int(valor)
    texto = str(valor).lower().replace(',', '').replace('$', '').replace(' ', '')
    mult = 1_000 if texto.endswith('k') else 1
    try:
        return int(float(texto.rstrip('k')) * mult)
    except ValueError:
        return None


def caja(etiqueta, opciones, inicial, formato, key):
    """Lista con opciones predefinidas en la que también se puede escribir un valor propio."""
    return a_numero(st.selectbox(etiqueta, opciones, index=opciones.index(inicial), format_func=formato,
                                 accept_new_options=True, key=key,
                                 help='Elige una opción o escribe una cantidad (p. ej. 25000 o 25k)'))


TODOS = 'Todos'

def botones_con_todos(etiqueta, opciones, key):
    """Botones seleccionables con la opción «Todos». Regresa [] cuando aplica a todos (sin filtro)."""
    if key not in st.session_state:
        st.session_state[key] = [TODOS]
        st.session_state[f'{key}_previo'] = [TODOS]

    def ajustar():
        actual, previo = st.session_state[key] or [], st.session_state[f'{key}_previo']
        if TODOS in actual and TODOS not in previo:            # se acaba de elegir «Todos»: limpia lo demás
            nuevo = [TODOS]
        else:                                                  # se eligió otra opción: quita «Todos»
            nuevo = [v for v in actual if v != TODOS]
        if not nuevo or set(nuevo) == set(opciones):           # nada o todas marcadas = «Todos»
            nuevo = [TODOS]
        st.session_state[key] = st.session_state[f'{key}_previo'] = nuevo

    elegidos = st.pills(etiqueta, [TODOS] + opciones, selection_mode='multi', format_func=es,
                        key=key, on_change=ajustar)
    return [] if TODOS in elegidos else elegidos


# ==============================================================================
# ENCABEZADO
# ==============================================================================

if BANNER_PROFESOR.exists():
    st.image(str(BANNER_PROFESOR), width='stretch')
st.image(str(BANNER), width='stretch')

tab_valuar, tab_comprar, tab_modelo = st.tabs(
    ['🚗  ¿Cuánto vale mi carro?', '🔎  ¿Cuánto vale el carro que quiero comprar?', '📊  Sobre el modelo'])


# ==============================================================================
# PESTAÑA 1 — ¿CUÁNTO VALE MI CARRO? (MODELO)
# ==============================================================================

with tab_valuar:
    st.subheader('Calcula el valor de tu auto')
    st.write('Elige tu auto y su estado. El modelo estima su precio de venta en EE. UU. '
             'a partir de casi 190 mil anuncios reales.')

    marcas = consulta('SELECT DISTINCT manufacturer FROM dim_vehicle ORDER BY manufacturer')['manufacturer'].tolist()

    c1, c2, c3 = st.columns(3)
    marca = c1.selectbox('Marca', marcas, index=marcas.index('Toyota'))

    modelos = consulta('''
        SELECT DISTINCT v.base_model
        FROM fact_listings AS f JOIN dim_vehicle AS v USING (vehicle_id)
        WHERE v.manufacturer = ?
        ORDER BY v.base_model
    ''', (marca,))['base_model'].tolist()
    modelo_base = c2.selectbox('Modelo', modelos,
                               index=modelos.index('RAV4') if marca == 'Toyota' and 'RAV4' in modelos else 0)

    anios = consulta('''
        SELECT DISTINCT f.year
        FROM fact_listings AS f JOIN dim_vehicle AS v USING (vehicle_id)
        WHERE v.manufacturer = ? AND v.base_model = ?
        ORDER BY f.year DESC
    ''', (marca, modelo_base))['year'].tolist()
    anio_inicial = min(range(len(anios)), key=lambda i: abs(anios[i] - 2019))   # arranca en el año más cercano a 2019
    anio = c3.selectbox('Año', anios, index=anio_inicial)

    c4, c5, c6, c7 = st.columns(4)
    km = c4.number_input('Kilometraje (km)', min_value=0, max_value=800_000, value=70_000, step=5_000)
    accidente = c5.radio('¿Ha tenido accidentes o daños?', ['No', 'Sí'], horizontal=True) == 'Sí'
    un_dueno  = c6.radio('¿Un solo dueño?', ['Sí', 'No'], horizontal=True) == 'Sí'
    personal  = c7.radio('¿Solo uso personal?', ['Sí', 'No'], horizontal=True) == 'Sí'

    # Características más comunes de ese modelo y año (para prellenar las opciones avanzadas)
    comun = consulta('''
        SELECT MODE(p.engine_liters) AS engine_liters, MODE(p.cylinders) AS cylinders, MODE(p.turbo) AS turbo,
               MODE(p.transmission) AS transmission, MODE(p.drivetrain) AS drivetrain, MODE(p.fuel_type) AS fuel_type,
               MEDIAN(f.mpg_city) AS mpg_city, MEDIAN(f.mpg_highway) AS mpg_highway,
               MODE(ce.color) AS exterior_color, MODE(ci.color) AS interior_color,
               ANY_VALUE(v.brand_country) AS brand_country, ANY_VALUE(v.brand_segment) AS brand_segment,
               ANY_VALUE(y.age) AS age
        FROM fact_listings AS f
        JOIN dim_vehicle    AS v  USING (vehicle_id)
        JOIN dim_powertrain AS p  USING (powertrain_id)
        JOIN dim_year       AS y  USING (year)
        JOIN dim_color      AS ce ON ce.color_id = f.exterior_color_id
        JOIN dim_color      AS ci ON ci.color_id = f.interior_color_id
        WHERE v.manufacturer = ? AND v.base_model = ? AND f.year = ?
    ''', (marca, modelo_base, anio)).iloc[0]

    opciones = consulta('''
        SELECT LIST(DISTINCT transmission ORDER BY transmission) AS transmission,
               LIST(DISTINCT drivetrain   ORDER BY drivetrain)   AS drivetrain,
               LIST(DISTINCT fuel_type    ORDER BY fuel_type)    AS fuel_type
        FROM dim_powertrain
    ''').iloc[0]
    colores = consulta('SELECT color FROM dim_color ORDER BY color')['color'].tolist()

    sufijo = f'{marca}_{modelo_base}_{anio}'        # al cambiar de auto, las opciones avanzadas se reinician
    with st.expander('⚙️  Opciones avanzadas (prellenadas con lo más común de este modelo)'):
        a1, a2, a3, a4 = st.columns(4)
        transmision = a1.selectbox('Transmisión', list(opciones['transmission']), format_func=es, key=f't_{sufijo}',
                                   index=list(opciones['transmission']).index(comun['transmission']))
        traccion    = a2.selectbox('Tracción', list(opciones['drivetrain']), format_func=es, key=f'd_{sufijo}',
                                   index=list(opciones['drivetrain']).index(comun['drivetrain']))
        combustible = a3.selectbox('Combustible', list(opciones['fuel_type']), format_func=es, key=f'f_{sufijo}',
                                   index=list(opciones['fuel_type']).index(comun['fuel_type']))
        turbo       = a4.checkbox('Turbo', value=bool(comun['turbo']), key=f'tu_{sufijo}')

        b1, b2, b3, b4 = st.columns(4)
        litros    = b1.number_input('Cilindrada (litros)', 0.0, 8.5, float(comun['engine_liters']), 0.1, key=f'l_{sufijo}')
        cilindros = b2.number_input('Cilindros', 0, 16, int(comun['cylinders']), 1, key=f'c_{sufijo}')
        mpg_city  = b3.number_input('Rendimiento ciudad (mpg)', 5.0, 150.0, float(comun['mpg_city']), 1.0, key=f'mc_{sufijo}')
        mpg_hwy   = b4.number_input('Rendimiento carretera (mpg)', 5.0, 150.0, float(comun['mpg_highway']), 1.0, key=f'mh_{sufijo}')

        d1, d2 = st.columns(2)
        color_ext = d1.selectbox('Color exterior', colores, format_func=es, key=f'ce_{sufijo}',
                                 index=colores.index(comun['exterior_color']))
        color_int = d2.selectbox('Color interior', colores, format_func=es, key=f'ci_{sufijo}',
                                 index=colores.index(comun['interior_color']))
        st.caption(f'1 mpg ≈ {KM_POR_MILLA / 3.785411784:.2f} km/l')

    # Entrada del modelo (mismas columnas y nombres con los que se entrenó)
    edad   = int(comun['age'])
    millas = km / KM_POR_MILLA
    entrada = pd.DataFrame([{
        'manufacturer': marca, 'base_model': modelo_base,
        'brand_country': comun['brand_country'], 'brand_segment': comun['brand_segment'],
        'transmission': transmision, 'drivetrain': traccion, 'fuel_type': combustible,
        'exterior_color': color_ext, 'interior_color': color_int,
        'age': edad, 'mileage': millas, 'mileage_per_year': round(millas / max(edad, 1)),
        'engine_liters': litros, 'cylinders': cilindros, 'mpg_city': mpg_city, 'mpg_highway': mpg_hwy,
        'turbo': int(turbo), 'accidents_or_damage': int(accidente), 'one_owner': int(un_dueno),
        'personal_use_only': int(personal),
    }])[info['categoricas'] + info['numericas'] + info['booleanas']]

    precio = float(modelo.predict(entrada)[0])
    mape   = info['metricas_prueba']['MAPE'] / 100

    st.divider()

    # Moneda de los precios (solo los textos; las gráficas siguen en USD)
    m1, m2 = st.columns([1, 1])
    en_mxn = m1.toggle('💱 Ver precios en pesos mexicanos (MXN)', key='en_mxn')
    if en_mxn:
        tipo_cambio = m2.number_input('Tipo de cambio (MXN por 1 USD)', min_value=1.0, max_value=50.0,
                                      value=TIPO_CAMBIO, step=0.10, format='%.2f', key='tipo_cambio')
    moneda, factor = ('MXN', tipo_cambio) if en_mxn else ('USD', 1.0)

    def precio_txt(x):
        return dinero(x * factor)

    r1, r2, r3 = st.columns([1, 1.2, 1])
    tarjeta(r1, 'Precio estimado', [precio_txt(precio)], moneda)
    tarjeta(r2, 'Rango probable (± error promedio)',
            [precio_txt(precio * (1 - mape)), ' – ', precio_txt(precio * (1 + mape))],
            f'{moneda} · ± {mape * 100:.0f} %')
    tarjeta(r3, 'Antigüedad / kilometraje anual', [f'{edad} años', ' · ', f'{km / max(edad, 1):,.0f} km/año'],
            f'{km:,.0f} km en total')
    if en_mxn:
        st.caption(f'Conversión con 1 USD = {tipo_cambio:.2f} MXN. Son precios de EE. UU. convertidos a pesos, '
                   'no precios del mercado mexicano. Las gráficas siguen en dólares.')
    st.write('')

    # Anuncios reales parecidos: mismo modelo, año ±1 y kilometraje ±30 %
    parecidos = consulta(f'''
        WITH a AS ({ANUNCIOS})
        SELECT year, model, mileage_km, price, accidents_or_damage
        FROM a
        WHERE manufacturer = ? AND base_model = ? AND year BETWEEN ? AND ?
    ''', (marca, modelo_base, anio - 1, anio + 1))

    cercanos = parecidos[parecidos['mileage_km'].between(km * 0.7, km * 1.3 + 5_000)]
    if len(cercanos) >= 3:
        st.info(f'**{len(cercanos)} anuncios reales parecidos** ({modelo_base} {anio - 1}–{anio + 1}, '
                f'kilometraje similar) tienen un precio mediano de **{precio_txt(cercanos["price"].median())} {moneda}** '
                f'(la mitad entre {precio_txt(cercanos["price"].quantile(0.25))} y '
                f'{precio_txt(cercanos["price"].quantile(0.75))}).')
    else:
        st.info('Hay pocos anuncios reales con un kilometraje parecido: la estimación se apoya en el modelo.')

    if len(parecidos):
        puntos = alt.Chart(parecidos.sample(min(len(parecidos), 3000), random_state=42)).mark_circle(
            size=25, opacity=0.35, color=AZUL).encode(
            x=alt.X('mileage_km:Q', title='Kilometraje (km)'),
            y=alt.Y('price:Q', title='Precio (USD)', axis=alt.Axis(format='$,.0f')),
            tooltip=[alt.Tooltip('model:N', title='Versión'), alt.Tooltip('year:O', title='Año'),
                     alt.Tooltip('mileage_km:Q', title='Km', format=',.0f'),
                     alt.Tooltip('price:Q', title='Precio', format='$,.0f')])
        tu_auto = alt.Chart(pd.DataFrame({'mileage_km': [km], 'price': [precio]})).mark_point(
            shape='diamond', size=350, filled=True, color=MAGENTA).encode(
            x='mileage_km:Q', y='price:Q', tooltip=[alt.Tooltip('price:Q', title='Tu auto (estimado)', format='$,.0f')])
        st.markdown(f'**Tu auto (◆) frente a los anuncios reales de {marca} {modelo_base} {anio - 1}–{anio + 1}**')
        grafica((puntos + tu_auto).properties(height=380))


# ==============================================================================
# PESTAÑA 2 — ¿CUÁNTO VALE EL CARRO QUE QUIERO COMPRAR? (TABLERO)
# ==============================================================================

with st.sidebar:
    st.header('🔎 Filtros del tablero')
    st.caption('Aplican a la pestaña «¿Cuánto vale el carro que quiero comprar?»')

    st.markdown('**Presupuesto (USD)**')
    montos = [1_000, 5_000, 10_000, 15_000, 20_000, 25_000, 30_000, 40_000, 50_000, 60_000,
              75_000, 100_000, 150_000, 200_000]
    p1, p2 = st.columns(2)
    with p1:
        precio_min = caja('Desde', montos, 10_000, dinero, 'precio_min')
    with p2:
        precio_max = caja('Hasta', montos, 40_000, dinero, 'precio_max')
    precio_min = 1_000 if precio_min is None else precio_min
    precio_max = 200_000 if precio_max is None else precio_max
    presupuesto = (min(precio_min, precio_max), max(precio_min, precio_max))

    st.markdown('**Año**')
    lista_anios = list(range(2023, 1999, -1))
    y1, y2 = st.columns(2)
    anio_desde = y1.selectbox('Desde', lista_anios, index=lista_anios.index(2015), key='anio_desde')
    anio_hasta = y2.selectbox('Hasta', lista_anios, index=lista_anios.index(2023), key='anio_hasta')
    rango_anios = (min(anio_desde, anio_hasta), max(anio_desde, anio_hasta))

    SIN_LIMITE = 10_000_000
    kms = [20_000, 50_000, 80_000, 100_000, 150_000, 200_000, 250_000, 300_000, 400_000, SIN_LIMITE]
    km_max = caja('Kilometraje máximo (km)', kms, 150_000,
                  lambda k: 'Sin límite' if k == SIN_LIMITE else f'{k:,} km', 'km_max')
    km_max = SIN_LIMITE if km_max is None else km_max

    if precio_min > precio_max or anio_desde > anio_hasta:
        st.caption('ℹ️ «Desde» era mayor que «Hasta»: se intercambiaron.')

    segmentos = botones_con_todos('Segmento de la marca', ['Mainstream', 'Luxury'], 'segmentos')
    marcas_f  = st.multiselect('Marcas (vacío = todas)', marcas)
    combustibles = consulta('SELECT DISTINCT fuel_type FROM dim_powertrain ORDER BY fuel_type')['fuel_type'].tolist()
    combustibles_f = botones_con_todos('Combustible', combustibles, 'combustibles')


def filtro_sql():
    """Arma el WHERE del tablero con parámetros (?) a partir de los filtros de la barra lateral."""
    condiciones = ['price BETWEEN ? AND ?', 'year BETWEEN ? AND ?', 'mileage_km <= ?']
    params = [*presupuesto, *rango_anios, km_max]
    for columna, valores in [('brand_segment', segmentos), ('manufacturer', marcas_f), ('fuel_type', combustibles_f)]:
        if valores:
            condiciones.append(f'{columna} IN ({", ".join("?" * len(valores))})')
            params += valores
    return 'WHERE ' + ' AND '.join(condiciones), tuple(params)


with tab_comprar:
    st.subheader('Explora los precios antes de comprar')
    st.write('Usa los filtros de la barra lateral (presupuesto, años, kilometraje, marcas…) '
             'y compara lo que cuestan los autos que te interesan.')

    where, params = filtro_sql()
    FILTRADOS = f'WITH filtrados AS (SELECT * FROM ({ANUNCIOS}) {where})'

    kpi = consulta(f'''{FILTRADOS}
        SELECT COUNT(*) AS anuncios, MEDIAN(price) AS precio, MEDIAN(mileage_km) AS km,
               AVG(CASE WHEN price_drop > 0 THEN 1.0 ELSE 0 END) AS con_rebaja,
               COUNT(DISTINCT base_model) AS modelos
        FROM filtrados''', params).iloc[0]

    if kpi['anuncios'] == 0:
        st.warning('No hay anuncios con estos filtros. Amplía el presupuesto, los años o el kilometraje.')
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric('Anuncios encontrados', f"{int(kpi['anuncios']):,}", f"{int(kpi['modelos'])} modelos", delta_color='off')
        k2.metric('Precio mediano', dinero(kpi['precio']))
        k3.metric('Kilometraje mediano', f"{kpi['km']:,.0f} km")
        k4.metric('Anuncios con rebaja', f"{kpi['con_rebaja'] * 100:.0f} %")

        # ── Gráfica 1: depreciación ───────────────────────────────────────────────
        st.markdown('#### 1. ¿Cuánto pierde de valor un auto con los años?')
        por_marca = 1 <= len(marcas_f) <= 6
        grupo     = 'manufacturer' if por_marca else 'brand_segment'
        depreciacion = consulta(f'''{FILTRADOS}
            SELECT age, {grupo} AS grupo, MEDIAN(price) AS precio, COUNT(*) AS anuncios
            FROM filtrados GROUP BY age, {grupo} HAVING COUNT(*) >= 10 ORDER BY age''', params)
        depreciacion['grupo'] = depreciacion['grupo'].map(es)
        grafica(alt.Chart(depreciacion).mark_line(point=True).encode(
            x=alt.X('age:Q', title='Antigüedad (años)'),
            y=alt.Y('precio:Q', title='Precio mediano (USD)', axis=alt.Axis(format='$,.0f')),
            color=alt.Color('grupo:N', title='Marca' if por_marca else 'Segmento'),
            tooltip=[alt.Tooltip('grupo:N', title='Grupo'), alt.Tooltip('age:Q', title='Antigüedad'),
                     alt.Tooltip('precio:Q', title='Precio mediano', format='$,.0f'),
                     alt.Tooltip('anuncios:Q', title='Anuncios', format=',')]).properties(height=330))
        st.caption('Elige de 1 a 6 marcas en la barra lateral para comparar marcas en lugar de segmentos.')

        # ── Gráfica 2: top de modelos ─────────────────────────────────────────────
        st.markdown('#### 2. Los modelos más ofrecidos dentro de tus filtros')
        top_modelos = consulta(f'''{FILTRADOS}
            SELECT manufacturer || ' ' || base_model AS modelo, COUNT(*) AS anuncios,
                   MEDIAN(price) AS precio, MEDIAN(mileage_km) AS km
            FROM filtrados GROUP BY manufacturer, base_model ORDER BY anuncios DESC LIMIT 12''', params)
        grafica(alt.Chart(top_modelos).mark_bar().encode(
            y=alt.Y('modelo:N', sort='-x', title=None),
            x=alt.X('anuncios:Q', title='Anuncios'),
            color=alt.Color('precio:Q', title='Precio mediano', scale=alt.Scale(range=['#F3B6CF', MAGENTA, AZUL]),
                            legend=alt.Legend(format='$,.0f')),
            tooltip=[alt.Tooltip('modelo:N', title='Modelo'), alt.Tooltip('anuncios:Q', title='Anuncios', format=','),
                     alt.Tooltip('precio:Q', title='Precio mediano', format='$,.0f'),
                     alt.Tooltip('km:Q', title='Km mediano', format=',.0f')]).properties(height=360))

        # ── Gráfica 3: precio según kilometraje de un modelo ──────────────────────
        st.markdown('#### 3. ¿Cuánto baja el precio de un modelo con el kilometraje?')
        modelo_elegido = st.selectbox('Modelo', top_modelos['modelo'].tolist(), key='modelo_km')
        por_km = consulta(f'''{FILTRADOS}
            SELECT FLOOR(mileage_km / 20000) * 20000 AS km_desde, MEDIAN(price) AS precio, COUNT(*) AS anuncios
            FROM filtrados WHERE manufacturer || ' ' || base_model = ?
            GROUP BY km_desde HAVING COUNT(*) >= 3 ORDER BY km_desde''', params + (modelo_elegido,))
        por_km['tramo'] = por_km['km_desde'].map(lambda k: f'{k / 1000:,.0f}k–{(k + 20000) / 1000:,.0f}k')
        grafica(alt.Chart(por_km).mark_bar(color=AZUL).encode(
            x=alt.X('tramo:N', sort=por_km['tramo'].tolist(), title='Kilometraje (km)'),
            y=alt.Y('precio:Q', title='Precio mediano (USD)', axis=alt.Axis(format='$,.0f')),
            tooltip=[alt.Tooltip('tramo:N', title='Kilometraje'), alt.Tooltip('precio:Q', title='Precio mediano', format='$,.0f'),
                     alt.Tooltip('anuncios:Q', title='Anuncios')]).properties(height=300))

        # ── Gráfica 4: historial ──────────────────────────────────────────────────
        st.markdown('#### 4. ¿Cuánto influyen los accidentes y el número de dueños?')
        historial = consulta(f'''{FILTRADOS}
            SELECT CASE WHEN accidents_or_damage THEN 'Con accidentes' ELSE 'Sin accidentes' END AS accidentes,
                   CASE WHEN one_owner THEN 'Un dueño' ELSE 'Varios dueños' END AS duenos,
                   MEDIAN(price) AS precio, COUNT(*) AS anuncios, MEDIAN(age) AS antiguedad
            FROM filtrados GROUP BY accidentes, duenos''', params)
        grafica(alt.Chart(historial).mark_bar().encode(
            x=alt.X('accidentes:N', title=None, sort=['Sin accidentes', 'Con accidentes']),
            xOffset=alt.XOffset('duenos:N', sort=['Un dueño', 'Varios dueños']),
            y=alt.Y('precio:Q', title='Precio mediano (USD)', axis=alt.Axis(format='$,.0f')),
            color=alt.Color('duenos:N', title='Dueños', scale=alt.Scale(range=[AZUL, MAGENTA])),
            tooltip=[alt.Tooltip('accidentes:N', title='Historial'), alt.Tooltip('duenos:N', title='Dueños'),
                     alt.Tooltip('precio:Q', title='Precio mediano', format='$,.0f'),
                     alt.Tooltip('antiguedad:Q', title='Antigüedad mediana (años)'),
                     alt.Tooltip('anuncios:Q', title='Anuncios', format=',')]).properties(height=300))
        st.caption('Ojo: los autos con accidentes o varios dueños también suelen ser más viejos (ver antigüedad en el tooltip).')

        # ── Tabla informativa: vendedores ─────────────────────────────────────────
        st.markdown('#### 5. Vendedores mejor calificados que ofrecen estos autos')
        vendedores = consulta(f'''{FILTRADOS}
            SELECT seller_name AS vendedor, COUNT(*) AS anuncios,
                   ROUND(AVG(seller_rating), 1) AS calificacion, MEDIAN(price) AS precio_mediano
            FROM filtrados
            WHERE seller_rating IS NOT NULL AND seller_name <> 'Unknown'
            GROUP BY seller_name HAVING COUNT(*) >= 5
            ORDER BY calificacion DESC, anuncios DESC LIMIT 10''', params)
        st.dataframe(vendedores, hide_index=True, width='stretch', column_config={
            'vendedor': 'Vendedor', 'anuncios': 'Anuncios',
            'calificacion': st.column_config.NumberColumn('Calificación (1–5)', format='%.1f ⭐'),
            'precio_mediano': st.column_config.NumberColumn('Precio mediano', format='$%d')})
        st.caption('Información de referencia: la calificación del vendedor no se usa para calcular precios.')


# ==============================================================================
# PESTAÑA 3 — SOBRE EL MODELO
# ==============================================================================

with tab_modelo:
    st.subheader('¿Qué tan confiable es la estimación?')
    m = info['metricas_prueba']
    st.write(f"El modelo es una **{info['modelo'].lower()}**, entrenada con {info['filas_entrenamiento']:,} anuncios "
             f"y evaluada con {info['filas_prueba']:,} anuncios que **nunca vio**.")

    q1, q2, q3, q4 = st.columns(4)
    q1.metric('R²', f"{m['R2']:.3f}", help='Qué parte de la variación del precio explica el modelo (1 = todo)')
    q2.metric('Error promedio (MAE)', dinero(m['MAE']), help='Por cuántos dólares se equivoca en promedio')
    q3.metric('Error porcentual (MAPE)', f"{m['MAPE']:.1f} %", help='Por qué porcentaje del precio se equivoca en promedio')
    q4.metric('RMSE', dinero(m['RMSE']), help='Como el MAE, pero castiga más los errores grandes')

    g1, g2 = st.columns(2)
    with g1:
        st.markdown('**Precio real vs. predicho (autos de prueba)**')
        st.image(str(GRAFICA_MODELO), width='stretch')
    with g2:
        st.markdown('**¿Cuánto mueve el precio cada característica?**')
        nombres = {'age': 'Antigüedad', 'mileage': 'Kilometraje', 'mileage_per_year': 'Km por año',
                   'engine_liters': 'Cilindrada', 'cylinders': 'Cilindros', 'mpg_city': 'Rendimiento ciudad',
                   'mpg_highway': 'Rendimiento carretera', 'turbo': 'Turbo', 'accidents_or_damage': 'Accidentes',
                   'one_owner': 'Un solo dueño', 'personal_use_only': 'Uso personal'}
        efecto = pd.DataFrame({'variable': [nombres.get(k, k) for k in info['efecto_pct']],
                               'efecto': list(info['efecto_pct'].values())})
        grafica(alt.Chart(efecto).mark_bar().encode(
            y=alt.Y('variable:N', sort='x', title=None),
            x=alt.X('efecto:Q', title='Cambio en el precio (%)'),
            color=alt.condition(alt.datum.efecto > 0, alt.value(AZUL), alt.value(MAGENTA)),
            tooltip=[alt.Tooltip('variable:N', title='Variable'),
                     alt.Tooltip('efecto:Q', title='Cambio (%)', format='+.1f')]).properties(height=380))
        st.caption('Numéricas: efecto de subir una desviación estándar. Sí/No: efecto de tener la característica.')

    st.markdown('''
**Cómo funciona**

- Usa 20 características del auto: marca, modelo, país y segmento de la marca, antigüedad, kilometraje, motor, transmisión,
  tracción, combustible, rendimiento, colores e historial (accidentes, dueños, uso).
- No usa datos del vendedor, rebajas ni el precio publicado: el usuario no los conoce o le darían la respuesta al modelo.
- Se eligió una regresión lineal en lugar de un árbol de decisión: es un poco menos precisa, pero **siempre responde de forma
  lógica** (más kilometraje o un accidente nunca suben el precio) y su efecto se explica en porcentajes.

**Limitaciones**

- Precios de anuncios de 2023 en EE. UU., en dólares: no son precios de México.
- Autos de 2000 a 2023 con precios entre $1,000 y $200,000.
- El estado real del auto (mecánica, interiores, equipamiento) no está en los datos.
''')


st.divider()
st.caption('Datos: Used Cars Dataset (Cars.com) en Kaggle — andreinovikov/used-cars-dataset (CC0). '
           'Pipeline RAW → EXTRACTED → TRANSFORMED → SERVING. Proyecto de Fundamentos de Ingeniería de Datos — LIACD.')
