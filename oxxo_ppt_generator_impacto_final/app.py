from base64 import b64decode, b64encode
from datetime import date, datetime, timezone
import hashlib
import hmac
import io
import json
import math
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
import requests
import streamlit as st

from data_model import read_book, values, filter_jun, summary_table
from html_renderer import (
    render_with_info, parse_coordinates, find_coordinate_columns,
    parse_hambre_export, available_months, hambre_window_average, build_hambre_lookup,
    count_hambre_matches, month_label, optimize_image,
)

ROOT = Path(__file__).parent
IMAGE_KEYS = {
    'general_environment_image', 'expansion_map', 'solution_image_1', 'solution_image_2',
    'expansion_intelligence', 'layout_image', 'capex_image', 'internal_image',
    'similar_image', 'similar_image_2', 'operating_store_image', 'success_criteria_image',
    'financial_viability_image',
    'microsaturation_image_1', 'microsaturation_image_2', 'microsaturation_image_3', 'microsaturation_image_4', 'microsaturation_image_5',
    'pilot_image_1', 'pilot_image_2',  # legado, ya no se usa en el formulario
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
    'CARLOS BOLAÑOS DIAZ', 'ALEJANDRA ROJAS ROMERO',
    'LAURA SOFÍA VECINO MARRUGO', 'TATIANA NIÑO CRUZ', 'DANIEL FELIPE ALVAREZ',
    'STEFANIA BABATIVA MORENO', 'SEBASTIAN APONTE CARVAJAL', 'VALENTINA VALENCIA',
    'JAIME GUTIERREZ PEREZ', 'CRISTIAN FORERO', 'DIANA BAUTISTA',
    'LINA PARRA', 'MATEO RIOS', 'FELIPE VASQUEZ', 'DEERLY CALDERON',
]
# Especialistas del formato Andatti (ventas solo de HAMBRE): ven el bloque «Formato Andatti» y necesitan la clave.
ANDATTI_SPECIALISTS = ('LAURA SOFÍA VECINO MARRUGO', 'DEERLY CALDERON')
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
    's2_coords': ('project_coordinates', ''),
    's2_nearest_count': ('nearest_count', 5),
    's2_fill_upz': ('fill_other_upz', False),
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
    's8_link': ('similar_store_link', ''),
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
    """Guarda las imágenes subidas como bytes (para que sobrevivan al JSON y a las recargas). Al subirlas se reducen sin que se note."""
    uploaded = st.file_uploader(label, type=['png', 'jpg', 'jpeg', 'webp'], key=widget_key)
    if uploaded is not None:
        raw = uploaded.getvalue()
        signature = (uploaded.name, len(raw), hashlib.sha1(raw).hexdigest())
        if st.session_state.image_sources.get(key) != signature:  # solo cuando es una imagen nueva, no en cada recarga
            optimized, report = optimize_image(raw)
            st.session_state.images[key] = optimized
            st.session_state.image_names[key] = uploaded.name
            st.session_state.image_sources[key] = signature
            st.session_state.image_savings[key] = (report['before'], report['after'])
    elif key not in st.session_state.images:
        st.session_state.images[key] = None
    if st.session_state.images.get(key):
        image_name = st.session_state.image_names.get(key, 'cargada desde JSON')
        before, after = st.session_state.image_savings.get(key, (0, 0))
        note = f' ({before / 1e6:.1f} MB → {after / 1e6:.1f} MB)' if before and after and after < before * 0.95 else ''
        st.caption(f'Imagen registrada: {image_name}{note}')
        st.image(st.session_state.images[key], caption='Vista previa de la imagen recuperada', width='stretch')


def andatti_key_status(entered):
    """'ok', 'wrong' o 'not_configured'. La clave vive en los Secrets de Streamlit Cloud (andatti_key), NUNCA en el código."""
    try:
        expected = st.secrets.get('andatti_key')
    except Exception:  # no hay secrets configurados
        expected = None
    if not expected:
        return 'not_configured'
    return 'ok' if hmac.compare_digest(str(entered or '').encode('utf-8'), str(expected).encode('utf-8')) else 'wrong'


def hambre_url_from_secrets():
    """Enlace compartido del Excel de HAMBRE (clave «hambre_url» en los Secrets de Streamlit Cloud, NO en el código)."""
    try:
        url = st.secrets.get('hambre_url')
    except Exception:  # no hay secrets configurados
        url = None
    return str(url).strip() if url else ''


def sharepoint_download_url(url):
    """Agrega download=1 al enlace compartido para que SharePoint entregue el archivo y no la página de vista previa."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != 'download']
    query.append(('download', '1'))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@st.cache_data(ttl=900, show_spinner='Descargando las ventas de HAMBRE…')
def download_hambre(url):
    """Descarga el Excel del enlace compartido (se vuelve a descargar cada 15 minutos). Lanza ValueError con un mensaje claro si no se puede."""
    try:
        response = requests.get(sharepoint_download_url(url), timeout=40, allow_redirects=True,
                                headers={'User-Agent': 'Mozilla/5.0 (generador-presentaciones-oxxo)'})
    except requests.RequestException as exc:
        raise ValueError(f'No hubo conexión con el enlace ({type(exc).__name__}).') from exc
    if response.status_code != 200:
        raise ValueError(f'El enlace respondió con error {response.status_code}. ¿Venció o dejó de ser público?')
    data = response.content
    if len(data) > 60_000_000:
        raise ValueError('El archivo del enlace es demasiado grande.')
    if not data.startswith(b'PK'):  # un .xlsx es un archivo zip
        raise ValueError('El enlace devolvió una página web en vez del Excel. ¿Pide iniciar sesión o ya no es público?')
    return data


def project_hambre_file():
    """Archivo de ventas de HAMBRE guardado junto a app.py (como el Book.xlsx), si existe."""
    for name in ('Hambre.xlsx', 'Hambre.csv'):
        path = ROOT / name
        if path.exists():
            return path
    return None


@st.cache_data(show_spinner=False)
def read_hambre_file(name, data):
    """Lee el Excel (.xlsx) o CSV exportado de Power BI como tabla cruda, sin encabezado."""
    buffer = io.BytesIO(data)
    if str(name).lower().endswith('.csv'):
        last_error = None
        for encoding in ('utf-8-sig', 'latin-1'):
            try:
                buffer.seek(0)
                return pd.read_csv(buffer, header=None, sep=None, engine='python', encoding=encoding, dtype=object)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f'No pude leer el CSV: {last_error}')
    return pd.read_excel(buffer, header=None, dtype=object)


if 'fields' not in st.session_state:
    st.session_state.fields = {'created_at': date.today().strftime('%d/%m/%Y')}
if 'images' not in st.session_state:
    st.session_state.images = {}
if 'image_names' not in st.session_state:
    st.session_state.image_names = {}
if 'image_sources' not in st.session_state:
    st.session_state.image_sources = {}
if 'image_savings' not in st.session_state:
    st.session_state.image_savings = {}

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
            size_before = sum(len(value) for value in restored_images.values())
            with st.spinner('Optimizando las imágenes del JSON (se reducen sin que se note)…'):
                restored_images = {image_key: optimize_image(image_bytes)[0] for image_key, image_bytes in restored_images.items()}
            size_after = sum(len(value) for value in restored_images.values())
            st.session_state.images = restored_images
            st.session_state.image_names = restored_image_names
            st.session_state.image_sources = {}
            st.session_state.image_savings = {}
            st.session_state.json_images_note = (f'Imágenes optimizadas: {size_before / 1e6:.0f} MB → {size_after / 1e6:.0f} MB.'
                                                 if size_after < size_before * 0.95 else '')
            st.session_state.json_loaded_name = json_upload.name
            st.session_state.json_loaded_signature = hashlib.sha256(json_upload.getvalue()).hexdigest()
            clear_form_widget_state()
            populate_form_widget_state(imported_fields)
            st.rerun()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            st.error(f'No se pudo cargar el JSON: {exc}')

    if st.session_state.get('json_loaded_name'):
        st.success(f'Información cargada: {st.session_state.json_loaded_name}')
        if st.session_state.get('json_images_note'):
            st.caption(st.session_state.json_images_note)

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
    f['project_coordinates'] = st.text_input(
        'Coordenadas del punto (latitud, longitud) *',
        f.get('project_coordinates', ''),
        key='s2_coords',
        placeholder='Ej: 4.7229, -74.044754',
        help='OBLIGATORIO. Cópialas desde Google Maps (clic derecho sobre el punto). Sirven con punto o con coma decimal. '
             'Con ellas, las tablas TMCB y EXP muestran las tiendas más cercanas al punto (máximo 5 por tabla).',
    )
    coords_text = (f['project_coordinates'] or '').strip()
    coords_ok = parse_coordinates(coords_text) is not None
    if not coords_text:
        st.warning('Obligatorio: escribe las coordenadas del punto. Sin ellas no se puede generar la presentación.')
    elif not coords_ok:
        st.warning('No pude leer las coordenadas. Usa el formato: 4.7229, -74.044754 (latitud, longitud).')
    elif jun is not None:
        coord_lat_col, coord_lon_col = find_coordinate_columns(jun)
        if coord_lat_col is None:
            st.warning('No encontré las columnas de coordenadas en el Book, así que las tablas no se ordenarán por cercanía.')
        else:
            st.caption(f'Cercanía calculada con las columnas «{coord_lat_col}» (latitud) y «{coord_lon_col}» (longitud) del Book.')

    fill_allowed = False
    andatti_active = False
    andatti_payload = None
    andatti_blocker = ''
    if f.get('specialist') in ANDATTI_SPECIALISTS:
        st.divider()
        st.markdown('**Formato Andatti — ventas solo de HAMBRE**')
        andatti_key = st.text_input('Clave del formato Andatti', type='password', key='s2_andatti_key')
        key_status = andatti_key_status(andatti_key)
        if key_status == 'ok':  # las opciones de MÁS tiendas por tabla son solo para quienes tienen el formato Andatti (con su clave)
            fill_allowed = True
            f['nearest_count'] = st.slider(
                'Tiendas por tabla (TMCB y EXP más cercanas al punto)',
                min_value=5, max_value=10, step=1, key='s2_nearest_count',
                value=min(10, max(5, int(f.get('nearest_count') or 5))),
                help='Mínimo 5 y máximo 10. Con más de 5 tiendas, las tablas de la diapositiva General se muestran en modo compacto.',
            )
            f['fill_other_upz'] = st.checkbox(
                'Si la UPZ tiene menos tiendas, completar con las más cercanas de otras UPZ',
                value=bool(f.get('fill_other_upz', False)), key='s2_fill_upz',
                help='Normalmente las tablas solo muestran tiendas de la UPZ del punto. Si la UPZ tiene menos tiendas de las que pides, esta opción agrega '
                     'las más cercanas de otras UPZ de la misma ciudad y las marca con un asterisco (*).',
            )
        if key_status == 'not_configured':
            st.info('El formato Andatti todavía no está habilitado: falta configurar la clave «andatti_key» en los Secrets de Streamlit Cloud.')
        elif key_status == 'wrong':
            if andatti_key:
                st.error('Clave incorrecta.')
            else:
                st.caption('Escribe la clave para usar el formato Andatti. Sin ella, la presentación sale en formato tradicional (ventas totales).')
        elif st.checkbox('Presentación de formato Andatti (ventas solo HAMBRE)', value=True, key='s2_andatti_on'):
            project_file = project_hambre_file()
            hambre_url = hambre_url_from_secrets()
            source_name, source_bytes, source_label = None, None, ''
            if hambre_url:  # el Excel de Power BI se lee SOLO desde el enlace guardado en los Secrets (ya no se sube a mano)
                try:
                    source_name, source_bytes, source_label = 'Hambre.xlsx', download_hambre(hambre_url), 'enlace de SharePoint'
                except ValueError as exc:
                    st.warning(f'No pude descargar el archivo del enlace de SharePoint. {exc}'
                               + (' Uso el archivo del proyecto.' if project_file is not None else ''))
            if source_bytes is None and project_file is not None:
                source_name, source_bytes, source_label = project_file.name, project_file.read_bytes(), f'archivo del proyecto ({project_file.name})'
            if source_bytes is None:
                if not hambre_url and project_file is None:
                    andatti_blocker = ('No está configurado el archivo de ventas de HAMBRE (falta «hambre_url» en los Secrets). '
                                       'Desactiva el formato Andatti o avisa a quien administra la app.')
                else:
                    andatti_blocker = ('No se pudo leer el archivo de ventas de HAMBRE (mira el aviso de arriba). '
                                       'Intenta de nuevo en unos minutos o desactiva el formato Andatti.')
            else:
                try:
                    hambre_table, hambre_info = parse_hambre_export(read_hambre_file(source_name, source_bytes))
                except Exception as exc:
                    st.error(f'No pude leer el {source_label}. {exc}')
                    andatti_blocker = f'El {source_label} de Power BI no se pudo leer.'
                else:
                    if hambre_info['stores'] < 10:
                        st.warning(f"El archivo trae solo {hambre_info['stores']} tienda(s). Si deberían ser muchas, revisa que la tabla dinámica no tenga un filtro de tienda puesto.")
                    this_year = date.today().year
                    month_options = available_months(hambre_table, this_year)
                    cutoff = None
                    if month_options:
                        previous = (this_year, date.today().month - 1) if date.today().month > 1 else (this_year - 1, 12)
                        cutoff = st.selectbox(
                            'Mes de corte (se promedian ese mes y los 2 anteriores)', month_options,
                            index=month_options.index(previous) if previous in month_options else len(month_options) - 1,
                            format_func=month_label, key='s2_andatti_cutoff',
                        )
                        if cutoff == (this_year, date.today().month):
                            st.warning('El mes de corte es el mes en curso y está incompleto.')
                    averaged, period = hambre_window_average(hambre_table, cutoff, window=3, default_year=this_year)
                    hambre_lookup = build_hambre_lookup(averaged)
                    matched, total, similar_count = count_hambre_matches(hambre_lookup, jun) if jun is not None else (0, 0, 0)
                    similar_note = f' ({similar_count} por similitud de nombre)' if similar_count else ''
                    data_until = f' Datos hasta {month_label(month_options[-1])}.' if month_options else ''
                    st.caption(
                        f"Fuente: {source_label}. Tiendas en «{hambre_info['store_column']}», ventas en «{hambre_info['value_column']}».{data_until} "
                        f"Periodo: {period}. {matched} de {total} tiendas del Book tienen venta de HAMBRE{similar_note}."
                    )
                    if jun is not None and matched == 0:
                        andatti_blocker = 'Ninguna tienda del archivo de Power BI coincide con las tiendas del Book. Revisa que sea el reporte correcto.'
                    else:
                        andatti_payload = {'lookup': hambre_lookup, 'period_label': period}
                        andatti_active = True
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
    f['similar_store_link'] = st.text_input('Link de tienda hermana — de ubicación (Maps)', f.get('similar_store_link', ''), key='s8_link')

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

if jun is not None:
    st.subheader('Vista previa de Book')
    st.dataframe(summary_table(filter_jun(sheets, city, upz)), width='stretch', hide_index=True)

st.divider()
st.subheader('Acciones')
def build_json_now():
    """El JSON (con todas las imágenes en base64) se arma SOLO al pulsar «Descargar JSON». Antes se armaba en cada recarga
    de la página (cada foto subida, cada cambio) y, con muchas imágenes, la app se quedaba «cargando»."""
    return build_json_payload(f, imgs, image_names)


total_image_mb = sum(len(as_bytes(value) or b'') for value in imgs.values()) / 1e6
if total_image_mb > 40:
    st.warning(f'Las imágenes cargadas pesan {total_image_mb:.0f} MB. Con más de unos 40 MB la app puede ir lenta o reiniciarse: '
               'usa fotos o pantallazos más livianos.')
col_json, col_presentation = st.columns([1, 1])
with col_json:
    json_button = dict(file_name=json_filename(f), mime='application/json', width='stretch',
                       help='Guarda campos, selecciones e imágenes para restaurarlos después.')
    try:
        st.download_button('Descargar JSON de datos', data=build_json_now, **json_button)
    except Exception:  # versiones de Streamlit sin descarga diferida
        st.download_button('Descargar JSON de datos', data=build_json_now(), **json_button)
with col_presentation:
    generate = st.button('Generar presentación', type='primary', width='stretch', disabled=(not coords_ok) or bool(andatti_blocker))
if andatti_blocker:
    st.error(andatti_blocker)
if f.get('specialist') in ANDATTI_SPECIALISTS:
    st.caption('Modo de la presentación: **formato Andatti — ventas solo HAMBRE**.' if andatti_active else 'Modo de la presentación: formato tradicional (ventas totales).')
if not coords_ok:
    st.error('Falta la coordenada del punto (sección General → «Coordenadas del punto»). Es obligatoria para generar la presentación.')

if generate:
    image_bytes = {key: as_bytes(value) for key, value in imgs.items()}
    render_fields = {**f, 'fill_other_upz': bool(f.get('fill_other_upz')) and fill_allowed,
                     'nearest_count': (f.get('nearest_count') or 5) if fill_allowed else 5}  # los demás especialistas siempre las 5 más cercanas
    if andatti_active:
        render_fields['andatti'] = andatti_payload
    html, render_info = render_with_info(render_fields, sheets, image_bytes)
    slide_count = 13 if f.get('microsaturation_enabled') == 'Sí' else 12
    st.success(f'Presentación generada con {slide_count} secciones.')
    missing_hambre = render_info.get('hambre_missing') or []
    if missing_hambre:
        suggestions = render_info.get('hambre_suggestions') or {}
        detail = [name + (' (¿será «' + '» o «'.join(suggestions[name]) + '»?)' if suggestions.get(name) else '') for name in missing_hambre]
        st.warning('Estas tiendas de las tablas no tienen venta de HAMBRE en el archivo y salen con «—»: ' + '; '.join(detail) + '.')
    similar_found = render_info.get('similar_matches') or []
    if similar_found:
        st.info('Emparejadas por similitud de nombre (revísalas): ' + '; '.join(f'{book_name} ↔ {file_name}' for book_name, file_name in similar_found) + '.')
    requested = render_info.get('requested') or 0
    if render_info.get('tmcb_shown', 0) < requested or render_info.get('exp_shown', 0) < requested:
        st.info(
            f"En la UPZ del punto hay {render_info.get('tmcb_in_upz', 0)} tienda(s) TMCB y {render_info.get('exp_in_upz', 0)} EXP en el Book, y pediste {requested} por tabla. "
            + ('Aun completando con otras UPZ de la ciudad no hay más tiendas.' if (fill_allowed and f.get('fill_other_upz'))
               else ('Para ver más, marca «Si la UPZ tiene menos tiendas, completar con las más cercanas de otras UPZ».' if fill_allowed else ''))
        )
    st.download_button(
        'Descargar presentación principal',
        html.encode('utf-8'),
        file_name='presentacion_oxxo.html',
        mime='text/html',
        width='stretch',
    )
