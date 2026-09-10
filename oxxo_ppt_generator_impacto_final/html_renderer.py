from base64 import b64encode
from datetime import date
from html import escape
from io import BytesIO

import pandas as pd
from PIL import Image


RED = '#B00000'
BLUE = '#17457A'
LIGHTBLUE = '#8FBEDA'
PURPLE = '#7E3E96'
ORANGE = '#F29100'
INK = '#252525'
CREAM = '#FBF8F1'
MUTED = '#6E6E6E'

CONVENTION_COLORS = [
    ('TMCB', '#B00000'),
    ('EXP', '#17457A'),
    ('OBRA', '#8FBEDA'),
    ('PPT: PUNTO POTENCIAL', '#7E3E96'),
    ('PR: PLAN RECTOR', '#D8B4FE'),
    ('NF: NUEVOS FORMATOS', '#FACC15'),
    ('CERRADA', '#808080'),
    ('FIRMADA', '#000000'),
]


def convention_legend(images=None, variant='compact'):
    """Render the convention key with semantic color swatches only."""
    items = []
    for label, color in CONVENTION_COLORS:
        items.append(
            f'<div class="convention-item">'
            f'<span class="convention-swatch" style="background:{color}"></span>'
            f'<span>{escape(label)}</span></div>'
        )
    return f'<div class="convention-legend {variant}">' + ''.join(items) + '</div>'


def image_src(data):
    """Return a browser-safe data URL, preserving the uploaded image format."""
    if not data:
        return ''
    mime = 'image/png'
    try:
        with Image.open(BytesIO(data)) as image:
            fmt = (image.format or 'PNG').upper()
        mime = {
            'JPG': 'image/jpeg',
            'JPEG': 'image/jpeg',
            'PNG': 'image/png',
            'WEBP': 'image/webp',
            'GIF': 'image/gif',
            'BMP': 'image/bmp',
            'TIFF': 'image/tiff',
        }.get(fmt, mime)
    except Exception:
        # The upload is still embedded even when Pillow cannot identify it.
        pass
    return f'data:{mime};base64,' + b64encode(data).decode('ascii')


def img(data, cls='photo', alt='Imagen de la presentación'):
    src = image_src(data)
    return f'<img class="{cls}" src="{src}" alt="{escape(alt, quote=True)}">' if src else ''


def media(data, cls, label, alt):
    """Keep the visual frame stable even when the user has not uploaded an image."""
    image = img(data, cls, alt)
    if image:
        return image
    return f'<div class="{cls} image-placeholder"><span>{escape(label)}</span></div>'


def money(value):
    try:
        return '$ {:,.0f}'.format(float(value)).replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return '—'


def number(value):
    try:
        return '{:,.0f}'.format(float(value)).replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return '—'


def percentage(part, total):
    try:
        total = float(total)
        if total == 0:
            return '—'
        return '{:,.1f}%'.format(float(part) / total * 100).replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return '—'


def text(value, fallback='—'):
    value = '' if value is None else str(value).strip()
    return escape(value if value else fallback)


def table_html(df, classes='data-table'):
    if df is None or df.empty:
        return '<div class="empty-note">Sin registros para el filtro seleccionado.</div>'
    return df.to_html(index=False, classes=classes, border=0, justify='left', na_rep='—', escape=True)


def link(label, url):
    if not url:
        return ''
    return f'<a href="{escape(str(url), quote=True)}" target="_blank" rel="noopener">{escape(label)}</a>'


def slide(title, body, number=None, cover=False):
    index = ''
    if cover:
        return (
            f'<section class="slide cover">{index}<div class="topline"></div>'
            f'{body}<div class="footline"></div></section>'
        )
    return (
        f'<section class="slide">{index}<div class="topline"></div>'
        f'<h1>{escape(title)}</h1>{body}<div class="footline"></div></section>'
    )


def financial_slide(data):
    """Financial slide with the regular presentation frame and an optional image."""
    return slide('Viabilidad financiera', f'''
        <div class="financial-layout">
            <div class="financial-photo-card">
                <div class="panel-kicker">SOPORTE DE VIABILIDAD</div>
                {media(data, 'financial-image', 'Carga la foto de viabilidad financiera', 'Viabilidad financiera')}
            </div>
        </div>
    ''', number=11)


def render(fields, sheets, images):
    jun = sheets.get('JUN', pd.DataFrame()).copy()
    city = fields.get('city', '')
    upz = fields.get('upz', '')
    segment = str(fields.get('segment', '')).upper()

    city_df = jun[jun['MUNICIPIO'].astype(str).str.strip() == city] if city and 'MUNICIPIO' in jun else jun
    upz_df = city_df[city_df['UPZ/COMUNA'].astype(str).str.strip() == upz] if upz and 'UPZ/COMUNA' in city_df else city_df
    d = upz_df if not upz_df.empty else city_df if not city_df.empty else jun

    def pct(df):
        return (
            df['SEG26'].astype(str).str.upper().value_counts(normalize=True) * 100
            if 'SEG26' in df and not df.empty
            else pd.Series(dtype=float)
        )

    cp, p = pct(city_df), pct(upz_df)

    pct_df = pd.DataFrame([
        {
            'Segmento': value.title(),
            'Ciudad': f'{cp.get(value, 0):.1f}%',
            'UPZ / comuna': f'{p.get(value, 0):.1f}%',
        }
        for value in ['RECESO', 'BASE', 'HOGAR']
    ])

    cols = [
        c for c in [
            'NAME',
            'SEG26',
            'MESOP_NUM',
            'VENTAS OUM_NUM',
            'RENTA UM_NUM',
            'COSTO M2_NUM',
        ]
        if c in d
    ]

    rename = {
        'NAME': 'Tienda',
        'SEG26': 'Segmento',
        'MESOP_NUM': 'Mes op.',
        'VENTAS OUM_NUM': 'Ventas último mes',
        'RENTA UM_NUM': 'Renta último mes',
        'COSTO M2_NUM': 'Costo m²',
    }

    def format_general_store_table(df):
        """
        Formatea las métricas de las tablas de tiendas
        que aparecen en la diapositiva General.
        """
        if df is None or df.empty:
            return df

        result = df.copy()

        if 'Mes op.' in result.columns:
            result['Mes op.'] = pd.to_numeric(
                result['Mes op.'],
                errors='coerce'
            ).map(
                lambda value: f'{value:.2f}'
                if pd.notna(value)
                else '—'
            )

        for column in [
            'Ventas último mes',
            'Renta último mes',
            'Costo m²',
        ]:
            if column in result.columns:
                result[column] = pd.to_numeric(
                    result[column],
                    errors='coerce'
                ).map(
                    lambda value: f'$ {value:,.2f}'
                    if pd.notna(value)
                    else '—'
                )

        return result

    tmc = (
        d[
            d['TIE27']
            .astype(str)
            .str.upper()
            .str.contains('TMCB', na=False)
        ]
        if 'TIE27' in d
        else d.iloc[0:0]
    )

    exp = (
        d[
            d['TIE27']
            .astype(str)
            .str.upper()
            .str.contains('EXP', na=False)
        ]
        if 'TIE27' in d
        else d.iloc[0:0]
    )

    combined = pd.concat([tmc, exp], ignore_index=True)

    def avg(df, column):
        return (
            df[column].mean()
            if column in df and not df.empty
            else None
        )

    project_area = float(fields.get('project_area', 0) or 0)
    project_rent = float(fields.get('project_rent', 0) or 0)

    calculated_rent_m2 = (
        project_rent / project_area
        if project_area
        else 0
    )

    commercial = pd.DataFrame([
        [
            'Renta',
            money(
                avg(
                    d[
                        d['SEG26']
                        .astype(str)
                        .str.upper()
                        == segment
                    ],
                    'RENTA UM_NUM'
                )
            ),
            money(project_rent) if project_rent else '',
        ],
        [
            'Renta / m²',
            money(
                avg(
                    d[
                        d['SEG26']
                        .astype(str)
                        .str.upper()
                        == segment
                    ],
                    'RENTA UM_NUM'
                )
                /
                avg(
                    d[
                        d['SEG26']
                        .astype(str)
                        .str.upper()
                        == segment
                    ],
                    'AREA_NUM'
                )
            )
            if avg(
                d[
                    d['SEG26']
                    .astype(str)
                    .str.upper()
                    == segment
                ],
                'AREA_NUM'
            )
            else '',
            money(calculated_rent_m2)
            if calculated_rent_m2
            else '',
        ],
        [
            'Área (m²)',
            '',
            number(project_area) if project_area else '',
        ],
        [
            'Vigencia',
            '15',
            fields.get('commercial_vigencia', ''),
        ],
        [
            'Permanencia',
            'NO',
            fields.get('commercial_permanencia', ''),
        ],
        [
            'Periodo de gracia (Dias)',
            '60',
            fields.get('commercial_gracia', ''),
        ],
        [
            'Pre Operativos',
            '0',
            fields.get('commercial_preop', ''),
        ],
        [
            'IPC',
            'PLANO',
            fields.get('commercial_ipc', ''),
        ],
        [
            'Operación 24 Hrs',
            'SI',
            fields.get('commercial_operacion', ''),
        ],
        [
            'Venta de alcohol',
            'SI',
            fields.get('commercial_alcohol', ''),
        ],
        [
            'Prima',
            'NO',
            fields.get('commercial_prima', ''),
        ],
        [
            'Anticipo',
            'NO',
            fields.get('commercial_anticipo', ''),
        ],
        [
            'Cláusulas Especiales',
            'NO',
            fields.get('commercial_clausulas', ''),
        ],
        [
            'Restricciones',
            'NO',
            fields.get('commercial_restricciones', ''),
        ],
    ], columns=[
        'Condiciones de negocio',
        'Estándar',
        'Nombre del proyecto',
    ])

    dates = pd.DataFrame([
        ['Firma', fields.get('signature', '')],
        ['Entrega de local', fields.get('delivery_date', '')],
        ['Apertura', fields.get('opening_date', '')],
    ], columns=['Hito', 'Fecha'])

    def build_generator_cards(group, fallback_images=False):
        source = fields.get(
            f'generator_{group}_cards',
            []
        )

        if not isinstance(source, list):
            source = []

        if not source and group == 'housing':
            source = fields.get(
                'generator_cards',
                []
            )

            if not isinstance(source, list):
                source = []

        cards_out = []

        for index, card in enumerate(source[:4], start=1):
            image_key = f'generator_{group}_image_{index}'

            if fallback_images:
                image_key = f'generator_image_{index}'

            cards_out.append(
                f'<div class="generator-card">'
                f'{media(images.get(image_key), "generator-img", "Sin foto", f"Generador {index}")}'
                f'<div class="generator-copy">'
                f'<span class="generator-name">'
                f'{text(card.get("name", ""), f"Generador {index}")}'
                f'</span>'
                f'<span class="generator-type">'
                f'{text(card.get("type", "Residencial"))}'
                f'</span>'
                f'<strong>{number(card.get("value", 0))}</strong>'
                f'<span class="generator-unit">aprox.</span>'
                f'</div>'
                f'</div>'
            )

        return ''.join(cards_out) or (
            '<div class="empty-note">'
            'Registra generadores para visualizarlos aquí.'
            '</div>'
        )

    housing_cards = build_generator_cards(
        'housing',
        fallback_images=True
    )

    employment_cards = build_generator_cards(
        'employment'
    )

    links = ' <span class="link-separator">|</span> '.join(
        filter(None, [
            link(
                'Ubicación',
                fields.get('location_link')
                or fields.get('maps_link')
            ),
            link(
                'Video tráfico',
                fields.get('traffic_video_link')
            ),
            link(
                'Street View',
                fields.get('streetview_link')
            ),
        ])
    )

    city_name = text(
        fields.get('new_city', 'Ciudad')
        if city == 'Ciudad nueva'
        else city or fields.get('new_city', 'Ciudad')
    )

    upz_name = text(
        fields.get('new_upz', 'UPZ / comuna')
        if upz == 'UPZ / comuna nueva'
        else upz or fields.get('new_upz', 'UPZ / comuna')
    )

    analyzed_count = len(d)

    total_market = (
        fields.get('housing_300', 0) or 0
    ) + (
        fields.get('jobs_300', 0) or 0
    )

    conventions = convention_legend(images, 'compact')
    conventions_strip = convention_legend(images, 'strip')

    slides = []

    slides.append(slide('', f'''
        <div class="cover-grid">
            <div class="cover-copy">
                <div class="brand">OXXO</div>
                <div class="cover-kicker">PRESENTACIÓN DE EXPANSIÓN</div>
                <h2>OXXO {text(fields.get('project_name', 'Nombre del punto'))}</h2>
                <p class="sub">{city_name} <span>·</span> {upz_name}</p>
                <p class="address">
                    {('<b>' + text(fields.get('address', '')) + '</b> ')
                    if fields.get('address')
                    else ''}
                    {link('Ver en Maps', fields.get('maps_link'))}
                </p>
                <p class="tag">
                    {text(fields.get('regional', 'Centro'))}
                    <span>·</span>
                    Segmento {text(fields.get('segment', 'Base'))}
                </p>
                <p class="meta">
                    Especialista: {text(fields.get('specialist', ''))}
                    <br>
                    Creada: {text(fields.get('created_at', date.today().strftime('%d/%m/%Y')))}
                </p>
            </div>
            <div class="cover-art">
                <div class="cover-art-ring"></div>
                <div class="cover-art-mark">OXXO</div>
                <div class="cover-art-line"></div>
            </div>
        </div>
    ''', number=1, cover=True))

    slides.append(slide('General', f'''
        <div class="context-row">
            <div>
                <span>Ciudad / municipio</span>
                <strong>{city_name}</strong>
            </div>
            <div>
                <span>UPZ / comuna</span>
                <strong>{upz_name}</strong>
            </div>
            <div>
                <span>Tiendas analizadas</span>
                <strong>{number(analyzed_count)}</strong>
            </div>
        </div>

        <div class="general-layout">
            <div class="visual-card environment-visual">
                {media(
                    images.get('general_environment_image'),
                    'environment-photo',
                    'Carga una foto de entorno',
                    'Entorno general'
                )}
                <div class="visual-caption">
                    <b>Lectura del entorno</b>
                    <span>Imagen principal del área de influencia</span>
                </div>
            </div>

            <div class="general-right">
                <div class="panel-kicker">MEZCLA DE MERCADO</div>
                {table_html(pct_df, 'data-table compact-table')}

                <div class="general-tables">
                    <div class="table-card red-accent">
                        <h3>Tiendas TMCB</h3>
                        {table_html(
                            format_general_store_table(
                                tmc[cols]
                                .head(4)
                                .rename(columns=rename)
                            ),
                            'data-table compact-table'
                        )}
                    </div>

                    <div class="table-card blue-accent">
                        <h3>Tiendas EXP</h3>
                        {table_html(
                            format_general_store_table(
                                exp[cols]
                                .head(4)
                                .rename(columns=rename)
                            ),
                            'data-table compact-table'
                        )}
                    </div>
                </div>

                <div class="general-kpis">
                    <div>
                        <span>Venta promedio</span>
                        <strong>{money(avg(combined, 'VENTAS OUM_NUM'))}</strong>
                    </div>
                    <div>
                        <span>Renta promedio</span>
                        <strong>{money(avg(combined, 'RENTA UM_NUM'))}</strong>
                    </div>
                    <div>
                        <span>Costo m² promedio</span>
                        <strong>{money(avg(combined, 'COSTO M2_NUM'))}</strong>
                    </div>
                </div>
            </div>
        </div>

        <div class="general-conventions">
            <div class="panel-kicker">CONVENCIONES DE TIENDA</div>
            {conventions}
        </div>
    ''', number=2))

    slides.append(slide('Solución de imagen', f'''
        <div class="two-photos solution-photos">
            {media(
                images.get('solution_image_1'),
                'photo-large',
                'Sin foto 1',
                'Foto inicial local'
            )}
            {media(
                images.get('solution_image_2'),
                'photo-large',
                'Sin foto 2',
                'Foto solución de imagen'
            )}
        </div>

        <div class="description">
            <h3>Descripción del punto</h3>
            <p>{text(fields.get('point_description', ''), '')}</p>
            <div class="links">{links}</div>
        </div>
    ''', number=4))

    for title, cards in [
        ('Entorno | Generadores Vivienda', housing_cards),
        ('Entorno | Generadores Empleo', employment_cards),
    ]:
        slides.append(slide(title, f'''
            <div class="generator-only-layout">
                <div class="generator-grid generator-grid-large">
                    {cards}
                </div>
            </div>
        ''', number=None))

    slides.append(slide('Expansión | Mercado y Tráfico', f'''
        <div class="expansion-main-layout">
            <div class="visual-card expansion-main-photo">
                {media(
                    images.get('expansion_intelligence'),
                    'expansion-main-image',
                    'Carga la foto de expansión',
                    'Foto de expansión'
                )}
            </div>

            <div class="expansion-main-panel">
                <div class="kpi-grid">
                    <div>
                        <span>Viviendas 300 m</span>
                        <strong>{number(fields.get('housing_300', 0))}</strong>
                        <small>
                            {percentage(fields.get('housing_300', 0), total_market)}
                            del mercado
                        </small>
                    </div>
                    <div>
                        <span>Empleos 300 m</span>
                        <strong>{number(fields.get('jobs_300', 0))}</strong>
                        <small>
                            {percentage(fields.get('jobs_300', 0), total_market)}
                            del mercado
                        </small>
                    </div>
                    <div class="accent-kpi">
                        <span>Mercado total</span>
                        <strong>{number(total_market)}</strong>
                        <small>Viviendas + empleos</small>
                    </div>
                </div>

                <div class="traffic-strip">
                    <span>TRÁFICO / 15 MIN</span>
                    <b>Peatonal {text(fields.get('pedestrian_15', '—'))}</b>
                    <b>Vehicular {text(fields.get('vehicle_15', '—'))}</b>
                    <b>Motos {text(fields.get('motorcycle_15', '—'))}</b>
                </div>

                <div class="market-share">
                    <div>
                        <span>Viviendas / mercado total</span>
                        <strong>
                            {percentage(fields.get('housing_300', 0), total_market)}
                        </strong>
                    </div>
                    <div>
                        <span>Empleos / mercado total</span>
                        <strong>
                            {percentage(fields.get('jobs_300', 0), total_market)}
                        </strong>
                    </div>
                </div>
            </div>
        </div>
    ''', number=None))

    slides.append(slide('Layout · Capex', f'''
        <div class="single-asset-layout">
            <div class="asset-card single-asset-card">
                <div class="asset-label">LAYOUT / CAPEX</div>
                {media(
                    images.get('layout_image'),
                    'asset-image',
                    'Carga la foto de layout / CAPEX',
                    'Layout y CAPEX de tienda'
                )}
            </div>
        </div>

        <div class="comment-ribbon">
            <span>NOTAS DEL PROYECTO</span>
            <p>
                {text(
                    fields.get('capex_comments', ''),
                    'Sin comentarios adicionales'
                )}
            </p>
        </div>
    ''', number=6))

    slides.append(slide('Tienda Hermana', f'''
        <div class="sister-layout">
            <div class="store-card sister-photo">
                <div class="store-label">FOTO TIENDA HERMANA</div>
                {media(
                    images.get('similar_image'),
                    'store-image',
                    'Carga la foto de la tienda espejo',
                    'Tienda espejo'
                )}
            </div>

            <div class="sister-name-card">
                <span>TIENDA HERMANA SELECCIONADA</span>
                <strong>{text(fields.get('book_store', 'Pendiente'))}</strong>
                <p>
                    {text(
                        fields.get('similar_comments', ''),
                        'Sin comentarios adicionales'
                    )}
                </p>
            </div>
        </div>
    ''', number=8))

    slides.append(slide(
        'Networks',
        f'''
        <div class="full-bleed-slide">
            {media(
                images.get('success_criteria_image'),
                'full-photo',
                'Carga la imagen de Networks',
                'Networks'
            )}
        </div>
        ''',
        number=9
    ))

    slides.append(slide('Condiciones comerciales', f'''
        <div class="commercial">
            <div>{table_html(commercial)}</div>
            <div>
                <h3>Hitos del proyecto</h3>
                {table_html(dates)}
                <p>{text(fields.get('commercial_comments', ''), '')}</p>
            </div>
        </div>
    ''', number=10))

    slides.append(
        financial_slide(
            images.get('financial_viability_image')
        )
    )

    if str(fields.get('microsaturation_enabled', 'No')) == 'Sí':
        micro_images = [
            images.get(f'microsaturation_image_{i}')
            for i in range(1, 6)
        ]

        micro_images = [
            image for image in micro_images if image
        ]

        micro_cards = ''.join(
            media(
                image,
                'micro-photo',
                'Foto de microsaturación',
                f'Microsaturación {i + 1}'
            )
            for i, image in enumerate(micro_images)
        )

        slides.append(slide(
            'Microsaturación',
            f'''
            <div class="micro-grid count-{len(micro_images)}">
                {
                    micro_cards
                    or media(
                        None,
                        'micro-photo',
                        'Sube hasta 5 fotos de microsaturación',
                        'Microsaturación'
                    )
                }
            </div>
            ''',
            number=None
        ))

    slides.append(slide('Piloto', f'''
        <div class="pilot-grid">
            <div class="pilot-card">
                {media(
                    images.get('pilot_image_1'),
                    'pilot-photo',
                    'Carga la foto de Piloto 1',
                    'Piloto 1'
                )}
            </div>
            <div class="pilot-card">
                {media(
                    images.get('pilot_image_2'),
                    'pilot-photo',
                    'Carga la foto de Piloto 2',
                    'Piloto 2'
                )}
            </div>
        </div>
    ''', number=12))

    css = '''
    '''

    return (
        '<!doctype html><html><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>OXXO | Presentación de expansión</title>'
        '<style>' + css + '</style>'
        '</head><body>'
        + ''.join(slides)
        + '</body></html>'
    )
def render_expansion(fields, images):
    """Render the additional one-page expansion summary requested by the user."""
    housing = float(fields.get('housing_300', 0) or 0)
    jobs = float(fields.get('jobs_300', 0) or 0)
    total = housing + jobs
    project = text(fields.get('project_name', 'Nombre del punto'))
    image = media(images.get('expansion_intelligence'), 'expansion-summary-image', 'Carga la foto de expansión', 'Foto de expansión')
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OXXO | Expansión</title><style>
@page{{size:13.333in 7.5in;margin:0}}*{{box-sizing:border-box}}body{{margin:0;background:#121212;font-family:Aptos,Arial,sans-serif;color:#252525}}.page{{width:13.333in;height:7.5in;padding:.55in .65in;background:linear-gradient(115deg,#FBF8F1 0 59%,#B00000 59% 100%);position:relative;overflow:hidden}}.page:before{{content:'';position:absolute;right:-.8in;top:-.8in;width:3.3in;height:3.3in;border:22px solid rgba(255,255,255,.16);border-radius:50%}}h1{{margin:0;color:#B00000;font-size:28pt;line-height:1}}.sub{{margin:.08in 0 .22in;color:#6E6E6E;font-size:13pt}}.summary{{display:grid;grid-template-columns:42% 58%;gap:.3in;height:5.65in;position:relative;z-index:1}}.photo{{height:5.65in;background:#F4F1EA;border-radius:.12in;overflow:hidden;box-shadow:0 12px 26px rgba(0,0,0,.16)}}.expansion-summary-image{{display:block;width:100%;height:100%;object-fit:contain;object-position:center}}.panel{{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto auto 1fr;gap:.15in;align-content:start}}.kpi{{padding:.16in;background:#fff;border-top:5px solid #B00000;box-shadow:0 7px 15px rgba(82,32,0,.1)}}.kpi span{{display:block;color:#6E6E6E;font-size:8pt;font-weight:900;letter-spacing:.08em;text-transform:uppercase}}.kpi strong{{display:block;margin-top:.08in;color:#B00000;font-size:24pt}}.kpi.total{{background:#B00000;border-top-color:#F29100}}.kpi.total span,.kpi.total strong{{color:#fff}}.traffic{{grid-column:1 / -1;padding:.14in .16in;background:#F2EEE5;border-left:5px solid #F29100}}.traffic span{{display:block;color:#B00000;font-size:8pt;font-weight:900;letter-spacing:.1em}}.traffic b{{display:inline-block;margin:.1in .22in 0 0;font-size:13pt}}.note{{grid-column:1 / -1;align-self:end;color:#fff;padding:.16in;background:rgba(80,0,0,.28);font-size:11pt;line-height:1.3}}@media print{{body{{background:#fff}}.page{{margin:0}}}}</style></head><body><section class="page"><h1>Expansión | Mercado y Tráfico</h1><div class="sub">OXXO {project}</div><div class="summary"><div class="photo">{image}</div><div class="panel"><div class="kpi"><span>Viviendas 300 m</span><strong>{number(housing)}</strong><small>{percentage(housing,total)} del mercado</small></div><div class="kpi"><span>Empleos 300 m</span><strong>{number(jobs)}</strong><small>{percentage(jobs,total)} del mercado</small></div><div class="kpi total"><span>Mercado total</span><strong>{number(total)}</strong><small>Viviendas + empleos</small></div><div class="traffic"><span>TRÁFICO / 15 MIN</span><b>Peatonal {text(fields.get('pedestrian_15', '—'))}</b><b>Vehicular {text(fields.get('vehicle_15', '—'))}</b><b>Motos {text(fields.get('motorcycle_15', '—'))}</b></div><div class="note">Lectura ejecutiva de expansión para complementar la presentación principal.</div></div></div></section></body></html>'''
