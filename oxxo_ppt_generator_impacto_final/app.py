from base64 import b64decode, b64encode
from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
from pathlib import Path

import streamlit as st

from data_model import read_book, values, filter_jun, summary_table
from html_renderer import render

ROOT = Path(__file__).parent
IMAGE_KEYS = {
    'general_environment_image', 'expansion_map', 'solution_image_1', 'solution_image_2',
    'expansion_intelligence', 'layout_image', 'capex_image', 'internal_image',
    'similar_image', 'similar_image_2', 'operating_store_image', 'success_criteria_image',
    'financial_viability_image',
    'microsaturation_image_1', 'microsaturation_image_2', 'microsaturation_image_3', 'microsaturation_image_4', 'microsaturation_image_5',
    'pilot_image_1', 'pilot_image_2',
    'generator_image_1', 'generator_image_2', 'generator_image_3', 'generator_image_4',
    'generator_housing_image_1', 'generator_housing_image_2', 'generator_housing_image_3', 'generator_housing_image_4',
    'generator_employment_image_1', 'generator_employment_image_2', 'generator_employment_image_3', 'generator_employment_image_4',
}
FORM_WIDGET_PREFIXES = (
    'book_', 's1_', 's2_', 's3_', 's4_', 's5_', 's6_', 's7_', 's8_', 's9_',
    's10_', 's11_', 's12_', 'pilot_',
)

st.set_page_config(page_title='OXXO | Generar presentación', layout='wide')
st.title('OXXO · Generador de presentación expansión')
st.caption('Book.xlsx se carga automáticamente desde el proyecto. Usa JSON para guardar o restaurar la información registrada.')


@st.cache_data
def load_book(source):
    return read_book(source)


def as_bytes(value):
    """Normalize Streamlit uploads and imported image values to raw bytes."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if hasattr(value, 'getvalue'):
        return value.getvalue()
    return None


def json_filename(fields):
    """Build a filesystem-safe JSON filename from the short date and project name."""
    project_name = str(fields.get('project_name', '') or '').strip()
    project_name = re.sub(r'[^\w.-]+', '_', project_name, flags=re.UNICODE).strip('._')
    project_name = project_name or 'sin_nombre'
    short_date = date.today().strftime('%d-%m-%y')
    return f'{short_date}_{project_name}.json'


def json_safe(value):
    """Convert form state to strict JSON-compatible values."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def encode_image(value, filename=''):
    data = as_bytes(value)
    if not data:
        return None
    return {
        'name': filename or 'imagen',
        'data_base64': b64encode(data).decode('ascii'),
    }


def decode_image(value):
    """Decode current, legacy and data-URL image values stored in JSON."""
    if isinstance(value, dict):
        encoded = next(
            (value.get(key) for key in ('data_base64', 'base64', 'data', 'content', 'src') if value.get(key)),
            '',
        )
    else:
        encoded = value
    if not encoded:
        return None
    if isinstance(encoded, bytes):
        return encoded
    if not isinstance(encoded, str):
        return None
    if encoded.startswith('data:') and ',' in encoded:
        encoded = encoded.split(',', 1)[1]
    try:
        compact = ''.join(encoded.split())
        return b64decode(compact.encode('ascii'), validate=True)
    except Exception:
        return None


def build_json_payload(fields, images, image_names):
    exported_images = {}
    has_layout_image = bool(images.get('layout_image'))
    for key, value in images.items():
        # Desde esta versión la slide 6 tiene una sola imagen.
        if key == 'capex_image' and has_layout_image:
            continue
        export_key = 'layout_image' if key == 'capex_image' else key
        encoded = encode_image(value, image_names.get(key, ''))
        if encoded:
            exported_images[export_key] = encoded
    payload = {
        'format': 'oxxo-presentation-data',
        'version': 1,
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'book_source': 'Book.xlsx incluido en el proyecto',
        'fields': json_safe(fields),
        'images': exported_images,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')


def restore_images(imported_images):
    """Restore image bytes and filenames from current or legacy JSON payloads."""
    if not isinstance(imported_images, dict):
        return {}, {}
    restored_images = {}
    restored_image_names = {}
    for key, raw in imported_images.items():
        decoded = decode_image(raw)
        if decoded is None:
            continue
        # Compatibilidad: la antigua foto de CAPEX se conserva como
        # la única imagen de la nueva slide 6 si no hay otra de layout.
        if key == 'capex_image' and 'layout_image' in imported_images:
            continue
        target_key = 'layout_image' if key == 'capex_image' else key
        if key == 'capex_image' and target_key != key:
            image_name = 'imagen de slide 6'
        else:
            image_name = raw.get('name', 'imagen') if isinstance(raw, dict) else 'imagen'
        restored_images[target_key] = decoded
        restored_image_names[target_key] = image_name
    return restored_images, restored_image_names


SPECIALISTS = [
    'ANDRES DUQUE RESTREPO', 'JURY CAROLINA GONZALEZ GOMEZ', 'JENNY ACUNA ROJAS',
    'LINA DIAZ ORTIZ', 'MARTHA LILIANA LOPEZ CANDAMIL', 'JORGE GRANADOS',
    'CARLOS BOLAÑOS DIAZ', 'ALEJANDRA ROJAS ROMERO', 'ELVIA JAIMES VELASQUEZ',
    'LAURA SOFÍA VECINO MARRUGO',
]
GENERATOR_TYPES = ['Administrativo', 'Residencial', 'Comercial', 'Industrial', 'Educativo', 'Salud', 'Transporte masivo']
YES_NO = ['SI', 'NO']
IPC_OPTIONS = ['PLANO', '+1', '+2', '+3']
MONTHS = ['', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']

FORM_WIDGET_DEFAULTS = {
    'book_city': ('city', ''),
    'book_upz': ('upz', ''),
    's1_regional': ('regional', 'Centro'),
    's1_project': ('project_name', ''),
    's1_segment': ('segment', 'Base'),
    's1_specialist': ('specialist', SPECIALISTS[0]),
    's1_address': ('address', ''),
    's1_maps': ('maps_link', ''),
    's2_new_city': ('new_city', ''),
    's2_new_upz': ('new_upz', ''),
    's2_comments': ('plan_comments', ''),
    's3_comments': ('plan_comments', ''),
    's4_desc': ('point_description', ''),
    's4_location': ('location_link', ''),
    's4_street': ('streetview_link', ''),
    's4_video': ('traffic_video_link', ''),
    's5_pedestrian': ('pedestrian_15', ''),
    's5_vehicle': ('vehicle_15', ''),
    's5_motorcycle': ('motorcycle_15', ''),
    's5_generator': ('generator_type', GENERATOR_TYPES[0]),
    's6_comments': ('capex_comments', ''),
    's8_open_store': ('book_store', ''),
    's8_comments': ('similar_comments', ''),
    's10_signature': ('signature', ''),
    's10_delivery': ('delivery_date', ''),
    's10_opening': ('opening_date', ''),
    's10_comments': ('commercial_comments', ''),
    's12_microsaturation_enabled': ('microsaturation_enabled', 'No'),
}

COMMERCIAL_WIDGET_DEFAULTS = {
    's10_commercial_vigencia': ('commercial_vigencia', ''),
    's10_commercial_permanencia': ('commercial_permanencia', ''),
    's10_commercial_gracia': ('commercial_gracia', ''),
    's10_commercial_preop': ('commercial_preop', ''),
    's10_commercial_ipc': ('commercial_ipc', ''),
    's10_commercial_operacion': ('commercial_operacion', ''),
    's10_commercial_alcohol': ('commercial_alcohol', ''),
    's10_commercial_prima': ('commercial_prima', ''),
    's10_commercial_anticipo': ('commercial_anticipo', ''),
    's10_commercial_clausulas': ('commercial_clausulas', ''),
    's10_commercial_restricciones': ('commercial_restricciones', ''),
}

NUMERIC_WIDGET_DEFAULTS = {
    's5_housing_100': 'housing_100',
    's5_housing_300': 'housing_300',
    's5_jobs_100': 'jobs_100',
    's5_jobs_300': 'jobs_300',
    's10_project_rent': 'project_rent',
    's10_project_area': 'project_area',
}


def clear_form_widget_state():
    """Remove prior widget state so an imported presentation can replace it."""
    for key in list(st.session_state.keys()):
        if key.startswith(FORM_WIDGET_PREFIXES):
            del st.session_state[key]


def _nonnegative_float(value, default=0.0, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not math.isfinite(number):
        number = default
    number = max(default, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def populate_form_widget_state(fields):
    """Push imported field values into the exact keys used by Streamlit widgets."""
    fields = fields if isinstance(fields, dict) else {}
    for widget_key, (field_key, default) in FORM_WIDGET_DEFAULTS.items():
        value = fields.get(field_key, default)
        st.session_state[widget_key] = default if value is None else value

    for widget_key, (field_key, default) in COMMERCIAL_WIDGET_DEFAULTS.items():
        value = fields.get(field_key, default)
        st.session_state[widget_key] = default if value is None else value

    for widget_key, field_key in NUMERIC_WIDGET_DEFAULTS.items():
        st.session_state[widget_key] = _nonnegative_float(fields.get(field_key, 0.0))

    legacy_cards = fields.get('generator_cards', []) if isinstance(fields.get('generator_cards', []), list) else []
    groups = [('housing', fields.get('generator_housing_cards', [])), ('employment', fields.get('generator_employment_cards', []))]
    for group, source_cards in groups:
        source_cards = source_cards if isinstance(source_cards, list) else []
        if not source_cards and group == 'housing':
            source_cards = legacy_cards
        for index in range(1, 5):
            card = source_cards[index - 1] if index - 1 < len(source_cards) and isinstance(source_cards[index - 1], dict) else {}
            st.session_state[f's5_{group}_name{index}'] = '' if card.get('name') is None else str(card.get('name', ''))
            st.session_state[f's5_{group}_type{index}'] = card.get('type', 'Residencial')
            st.session_state[f's5_{group}_val{index}'] = _nonnegative_float(card.get('value', 0.0))
            if group == 'housing':
                st.session_state[f's5_name{index}'] = st.session_state[f's5_{group}_name{index}']
                st.session_state[f's5_type{index}'] = st.session_state[f's5_{group}_type{index}']
                st.session_state[f's5_val{index}'] = st.session_state[f's5_{group}_val{index}']

    valid_months = ('', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE')
    for field_key in ('signature', 'delivery_date', 'opening_date'):
        saved_month = str(fields.get(field_key, '') or '').upper()
        st.session_state[f's10_{field_key}'] = saved_month if saved_month in valid_months else ''
    microsaturation = fields.get('microsaturation_enabled', 'No')
    st.session_state['s12_microsaturation_enabled'] = microsaturation if microsaturation in ('No', 'Sí') else 'No'


def image_uploader(label, key, widget_key):
    """Store uploaded images as bytes so they survive JSON export and reruns."""
    uploaded = st.file_uploader(label, type=['png', 'jpg', 'jpeg', 'webp'], key=widget_key)
    if uploaded is not None:
        st.session_state.images[key] = uploaded.getvalue()
        st.session_state.image_names[key] = uploaded.name
    elif key not in st.session_state.images:
        st.session_state.images[key] = None
    if st.session_state.images.get(key):
        image_name = st.session_state.image_names.get(key, 'cargada desde JSON')
        st.caption(f'Imagen registrada: {image_name}')
        st.image(st.session_state.images[key], caption='Vista previa de la imagen recuperada', width='stretch')


if 'fields' not in st.session_state:
    st.session_state.fields = {'created_at': date.today().strftime('%d/%m/%Y')}
if 'images' not in st.session_state:
    st.session_state.images = {}
if 'image_names' not in st.session_state:
    st.session_state.image_names = {}

f = st.session_state.fields
imgs = st.session_state.images
image_names = st.session_state.image_names

with st.sidebar:
    st.header('Restaurar información')
    json_upload = st.file_uploader(
        'Subir JSON de la presentación',
        type=['json'],
        key='json_import',
        help='Carga los campos y las imágenes guardadas anteriormente.',
    )
    if json_upload is not None and st.button('Cargar información del JSON', key='load_json', width='stretch'):
        try:
            payload = json.loads(json_upload.getvalue().decode('utf-8-sig'))
            imported_fields = payload.get('fields')
            if not isinstance(imported_fields, dict):
                raise ValueError('El JSON no contiene un objeto "fields" válido.')
            imported_images = payload.get('images', {})
            if not isinstance(imported_images, dict):
                raise ValueError('El JSON no contiene un objeto "images" válido.')

            st.session_state.fields = imported_fields
            restored_images, restored_image_names = restore_images(imported_images)
            st.session_state.images = restored_images
            st.session_state.image_names = restored_image_names
            st.session_state.json_loaded_name = json_upload.name
            st.session_state.json_loaded_signature = hashlib.sha256(json_upload.getvalue()).hexdigest()
            clear_form_widget_state()
            populate_form_widget_state(imported_fields)
            st.rerun()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            st.error(f'No se pudo cargar el JSON: {exc}')

    if st.session_state.get('json_loaded_name'):
        st.success(f'Información cargada: {st.session_state.json_loaded_name}')

    st.divider()
    st.header('Datos desde Book')
    book_path = ROOT / 'Book.xlsx'
    if book_path.exists():
        sheets = load_book(book_path)
        jun = sheets.get('JUN')
        if jun is not None:
            st.success(f'Book cargado automáticamente · {len(jun):,} tiendas')
    else:
        sheets = {}
        jun = None
        st.warning('No se encontró Book.xlsx dentro del proyecto.')

    open_stores = values(
        jun[jun['ESTADO'].astype(str).str.upper().str.contains('ABIERTA', na=False)],
        'NAME',
    ) if jun is not None and 'ESTADO' in jun else values(jun, 'NAME')
    f['open_stores'] = open_stores

with st.expander('Portada', expanded=True):
    f['regional'] = st.selectbox('Región', ['Centro', 'Nororiente', 'Occidente'], key='s1_regional', index=['Centro', 'Nororiente', 'Occidente'].index(f.get('regional', 'Centro')) if f.get('regional', 'Centro') in ['Centro', 'Nororiente', 'Occidente'] else 0)
    f['project_name'] = st.text_input('Nombre del punto — se imprimirá como OXXO + nombre', f.get('project_name', ''), key='s1_project')
    f['segment'] = st.selectbox('Segmento', ['Receso', 'Base', 'Hogar'], key='s1_segment', index=['Receso', 'Base', 'Hogar'].index(f.get('segment', 'Base')) if f.get('segment', 'Base') in ['Receso', 'Base', 'Hogar'] else 1)
    specialist_default = f.get('specialist', SPECIALISTS[0])
    f['specialist'] = st.selectbox('Especialista', SPECIALISTS, key='s1_specialist', index=SPECIALISTS.index(specialist_default) if specialist_default in SPECIALISTS else 0)
    f['address'] = st.text_input('Dirección', f.get('address', ''), key='s1_address')
    f['maps_link'] = st.text_input('Link de Maps', f.get('maps_link', ''), key='s1_maps')
    st.caption(f"Fecha automática de creación: {f.get('created_at', date.today().strftime('%d/%m/%Y'))}")

with st.expander('General'):
    city_options = [''] + values(jun, 'MUNICIPIO') if jun is not None else ['']
    if 'Ciudad nueva' not in city_options:
        city_options.append('Ciudad nueva')
    city_default = f.get('city', '') if f.get('city', '') in city_options else ''
    city = st.selectbox('Ciudad / municipio', city_options, index=city_options.index(city_default), key='book_city')
    cdf = jun[jun['MUNICIPIO'].astype(str).str.strip() == city] if city and city != 'Ciudad nueva' and jun is not None else jun if city != 'Ciudad nueva' else None
    upz_options = [''] + values(cdf, 'UPZ/COMUNA') if cdf is not None else ['']
    if 'UPZ / comuna nueva' not in upz_options:
        upz_options.append('UPZ / comuna nueva')
    upz_default = f.get('upz', '') if f.get('upz', '') in upz_options else ''
    upz = st.selectbox('UPZ / comuna', upz_options, index=upz_options.index(upz_default), key='book_upz')
    f.update({'city': city, 'upz': upz})
    image_uploader('Foto de entorno general', 'general_environment_image', 's2_img')
    if city == 'Ciudad nueva':
        f['new_city'] = st.text_input('Ciudad nueva / municipio', f.get('new_city', ''), key='s2_new_city')
    else:
        f['new_city'] = f.get('new_city', '')
    if upz == 'UPZ / comuna nueva':
        f['new_upz'] = st.text_input('UPZ / comuna nueva', f.get('new_upz', ''), key='s2_new_upz')
    else:
        f['new_upz'] = f.get('new_upz', '')
    f['plan_comments'] = st.text_area('Comentarios del plan rector', f.get('plan_comments', ''), key='s2_comments')
    st.info('Book genera las tablas TMCB y EXP. La venta promedio combina ambos grupos. Las convenciones muestran los nombres completos.')

with st.expander('Solución de imagen'):
    image_uploader('Foto inicial local', 'solution_image_1', 's4_img1')
    image_uploader('Foto solución de imagen', 'solution_image_2', 's4_img2')
    f['point_description'] = st.text_area('Descripción del punto', f.get('point_description', ''), key='s4_desc')
    f['location_link'] = st.text_input('Ubicación — link de Maps', f.get('location_link', f.get('maps_link', '')), key='s4_location')
    f['traffic_video_link'] = st.text_input('Video tráfico — link', f.get('traffic_video_link', ''), key='s4_video')
    f['streetview_link'] = st.text_input('Street View — link', f.get('streetview_link', ''), key='s4_street')

for group, title in [('housing', 'Entorno | Generadores Vivienda'), ('employment', 'Entorno | Generadores Empleo')]:
    with st.expander(title):
        cards = []
        st.caption('Carga cuatro fotos, indica el tipo de generador y el número aproximado de viviendas o empleos asociados.')
        for i in range(1, 5):
            st.markdown(f'**Generador {i}**')
            a, b, c, d = st.columns([2, 2, 2, 2])
            with a:
                image_uploader(f'Foto {i}', f'generator_{group}_image_{i}', f's5_{group}_img{i}')
            old_cards = f.get(f'generator_{group}_cards', [])
            old_card = old_cards[i - 1] if i - 1 < len(old_cards) and isinstance(old_cards[i - 1], dict) else {}
            with b:
                name = st.text_input('Nombre del generador', old_card.get('name', ''), key=f's5_{group}_name{i}')
            with c:
                typ = st.selectbox('Tipo de generador', GENERATOR_TYPES, index=GENERATOR_TYPES.index(old_card.get('type')) if old_card.get('type') in GENERATOR_TYPES else 0, key=f's5_{group}_type{i}')
            with d:
                val = st.number_input('Número aprox.', min_value=0.0, value=float(old_card.get('value', 0) or 0), key=f's5_{group}_val{i}')
            cards.append({'name': name, 'type': typ, 'value': val})
        f[f'generator_{group}_cards'] = cards
with st.expander('Expansión | Mercado y Tráfico'):
    image_uploader('Imagen de inteligencia de expansión', 'expansion_intelligence', 's5_intel')
    st.caption('Esta imagen aparecerá únicamente en la sección integrada de Expansión | Mercado y Tráfico.')
    st.markdown('**Mercado y vivienda/empleo**')
    for key, label in [('housing_100', 'Viviendas a 100 m'), ('housing_300', 'Viviendas a 300 m'), ('jobs_100', 'Empleos a 100 m'), ('jobs_300', 'Empleos a 300 m')]:
        f[key] = st.number_input(label, min_value=0.0, value=float(f.get(key, 0) or 0), key=f's5_{key}')
    principal_default = f.get('generator_type', GENERATOR_TYPES[0])
    f['generator_type'] = st.selectbox('Tipo de generador principal', GENERATOR_TYPES, index=GENERATOR_TYPES.index(principal_default) if principal_default in GENERATOR_TYPES else 0, key='s5_generator')
    st.markdown('**Tráficos cada 15 minutos**')
    f['pedestrian_15'] = st.text_input('Tráfico peatonal', f.get('pedestrian_15', ''), key='s5_pedestrian')
    f['vehicle_15'] = st.text_input('Tráfico vehicular', f.get('vehicle_15', ''), key='s5_vehicle')
    f['motorcycle_15'] = st.text_input('Tráfico de motos', f.get('motorcycle_15', ''), key='s5_motorcycle')

with st.expander('Layout | Capex'):
    image_uploader('Foto de layout / CAPEX', 'layout_image', 's6_layout')
    f['capex_comments'] = st.text_area('Comentarios adicionales', f.get('capex_comments', ''), key='s6_comments')

with st.expander('Tienda Hermana'):
    image_uploader('Foto Tienda Hermana', 'similar_image', 's8_similar')
    image_uploader('Foto adicional Tienda Hermana', 'similar_image_2', 's8_similar_2')
    open_store_options = [''] + f.get('open_stores', [])
    saved_store = f.get('book_store', '') if f.get('book_store', '') in open_store_options else ''
    f['book_store'] = st.selectbox('Tienda abierta espejo — desde Book', open_store_options, index=open_store_options.index(saved_store), key='s8_open_store') if f.get('open_stores') else ''
    f['similar_comments'] = st.text_area('Comentarios', f.get('similar_comments', ''), key='s8_comments')

with st.expander('Networks'):
    image_uploader('Foto de Networks', 'success_criteria_image', 's9_image')

with st.expander('Condiciones comerciales'):
    st.caption('La columna Estándar se completa automáticamente. La columna Nombre del proyecto queda editable fila por fila.')
    f['commercial_vigencia'] = st.text_input('Vigencia', f.get('commercial_vigencia', ''), key='s10_commercial_vigencia')
    f['commercial_permanencia'] = st.selectbox('Permanencia', YES_NO, index=YES_NO.index(f.get('commercial_permanencia', 'NO').upper()) if str(f.get('commercial_permanencia', 'NO')).upper() in YES_NO else 1, key='s10_commercial_permanencia')
    f['commercial_gracia'] = st.text_input('Periodo de gracia (Dias)', f.get('commercial_gracia', ''), key='s10_commercial_gracia')
    f['commercial_preop'] = st.text_input('Pre Operativos', f.get('commercial_preop', ''), key='s10_commercial_preop')
    f['commercial_ipc'] = st.selectbox('IPC', IPC_OPTIONS, index=IPC_OPTIONS.index(f.get('commercial_ipc', 'PLANO')) if f.get('commercial_ipc', 'PLANO') in IPC_OPTIONS else 0, key='s10_commercial_ipc')
    f['commercial_operacion'] = st.selectbox('Operación 24 Hrs', YES_NO, index=YES_NO.index(f.get('commercial_operacion', 'NO').upper()) if str(f.get('commercial_operacion', 'NO')).upper() in YES_NO else 1, key='s10_commercial_operacion')
    f['commercial_alcohol'] = st.selectbox('Venta de alcohol', YES_NO, index=YES_NO.index(f.get('commercial_alcohol', 'NO').upper()) if str(f.get('commercial_alcohol', 'NO')).upper() in YES_NO else 1, key='s10_commercial_alcohol')
    f['commercial_prima'] = st.selectbox('Prima', YES_NO, index=YES_NO.index(f.get('commercial_prima', 'NO').upper()) if str(f.get('commercial_prima', 'NO')).upper() in YES_NO else 1, key='s10_commercial_prima')
    f['commercial_anticipo'] = st.selectbox('Anticipo', YES_NO, index=YES_NO.index(f.get('commercial_anticipo', 'NO').upper()) if str(f.get('commercial_anticipo', 'NO')).upper() in YES_NO else 1, key='s10_commercial_anticipo')
    f['commercial_clausulas'] = st.selectbox('Cláusulas Especiales', YES_NO, index=YES_NO.index(str(f.get('commercial_clausulas', 'NO')).upper()) if str(f.get('commercial_clausulas', 'NO')).upper() in YES_NO else 1, key='s10_commercial_clausulas')
    f['commercial_restricciones'] = st.selectbox('Restricciones', YES_NO, index=YES_NO.index(str(f.get('commercial_restricciones', 'NO')).upper()) if str(f.get('commercial_restricciones', 'NO')).upper() in YES_NO else 1, key='s10_commercial_restricciones')
    f['project_rent'] = st.number_input('Renta del proyecto', min_value=0.0, value=float(f.get('project_rent', 0) or 0), key='s10_project_rent')
    f['project_area'] = st.number_input('Área (m²)', min_value=0.0, value=float(f.get('project_area', 0) or 0), key='s10_project_area')
    f['project_rent_m2'] = f['project_rent'] / f['project_area'] if f['project_area'] else 0
    f['negotiated_rent'] = f['project_rent']
    signature_default = str(f.get('signature', '') or '').upper()
    delivery_default = str(f.get('delivery_date', '') or '').upper()
    opening_default = str(f.get('opening_date', '') or '').upper()
    f['signature'] = st.selectbox('Firma (mes)', MONTHS, index=MONTHS.index(signature_default) if signature_default in MONTHS else 0, key='s10_signature')
    f['delivery_date'] = st.selectbox('Entrega de local (mes)', MONTHS, index=MONTHS.index(delivery_default) if delivery_default in MONTHS else 0, key='s10_delivery')
    f['opening_date'] = st.selectbox('Apertura (mes)', MONTHS, index=MONTHS.index(opening_default) if opening_default in MONTHS else 0, key='s10_opening')
    f['commercial_comments'] = st.text_area('Comentarios', f.get('commercial_comments', ''), key='s10_comments')

with st.expander('Viabilidad financiera'):
    image_uploader('Foto de viabilidad financiera — se presentará dentro de la slide', 'financial_viability_image', 's11_image')

with st.expander('Microsaturación adicional'):
    micro_options = ['No', 'Sí']
    micro_default = f.get('microsaturation_enabled', 'No') if f.get('microsaturation_enabled', 'No') in micro_options else 'No'
    f['microsaturation_enabled'] = st.radio('¿Hay microsaturación?', micro_options, index=micro_options.index(micro_default), horizontal=True, key='s12_microsaturation_enabled')
    if f['microsaturation_enabled'] == 'Sí':
        st.caption('Puedes subir hasta 5 fotos; la presentación las acomoda automáticamente según la cantidad cargada.')
        for i in range(1, 6):
            image_uploader(f'Foto de microsaturación {i}', f'microsaturation_image_{i}', f's12_micro{i}')
    else:
        for i in range(1, 6):
            imgs[f'microsaturation_image_{i}'] = None

with st.expander('Piloto'):
    image_uploader('Foto de Piloto 1', 'pilot_image_1', 'pilot_img1')
    image_uploader('Foto de Piloto 2', 'pilot_image_2', 'pilot_img2')

if jun is not None:
    st.subheader('Vista previa de Book')
    st.dataframe(summary_table(filter_jun(sheets, city, upz)), width='stretch', hide_index=True)

st.divider()
st.subheader('Acciones')
json_bytes = build_json_payload(f, imgs, image_names)
col_json, col_presentation = st.columns([1, 1])
with col_json:
    st.download_button(
        'Descargar JSON de datos',
        data=json_bytes,
        file_name=json_filename(f),
        mime='application/json',
        width='stretch',
        help='Guarda campos, selecciones e imágenes para restaurarlos después.',
    )
with col_presentation:
    generate = st.button('Generar presentación', type='primary', width='stretch')

if generate:
    image_bytes = {key: as_bytes(value) for key, value in imgs.items()}
    html = render(f, sheets, image_bytes)
    slide_count = 13 if f.get('microsaturation_enabled') == 'Sí' else 12
    st.success(f'Presentación generada con {slide_count} secciones.')
    st.download_button(
        'Descargar presentación principal',
        html.encode('utf-8'),
        file_name='presentacion_oxxo.html',
        mime='text/html',
        width='stretch',
    )
