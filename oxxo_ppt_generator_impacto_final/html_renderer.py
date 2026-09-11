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
        return '$ {:,.1f}'.format(float(value)).replace(',', 'X').replace('.', ',').replace('X', '.')
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


def table_html(df, classes="data-table"):
    if df is None or df.empty:
        return '<div class="empty-note">Sin registros para el filtro seleccionado.</div>'

    df_display = df.copy()

    for column in ["Ventas último mes", "Renta último mes", "Costo m²"]:
        if column in df_display.columns:
            df_display[column] = df_display[column].apply(money)

    return df_display.to_html(
        index=False,
        classes=classes,
        border=0,
        justify="left",
        na_rep=""
    )

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

    cols = [c for c in ['NAME', 'SEG26', 'MESOP_NUM', 'VENTAS OUM_NUM', 'RENTA UM_NUM', 'COSTO M2_NUM'] if c in d]
    rename = {
        'NAME': 'Tienda',
        'SEG26': 'Segmento',
        'MESOP_NUM': 'Mesop',
        'VENTAS OUM_NUM': 'Ventas último mes',
        'RENTA UM_NUM': 'Renta último mes',
        'COSTO M2_NUM': 'Costo m²',
    }
    tmc = d[d['TIE27'].astype(str).str.upper().str.contains('TMCB', na=False)] if 'TIE27' in d else d.iloc[0:0]
    exp = d[d['TIE27'].astype(str).str.upper().str.contains('EXP', na=False)] if 'TIE27' in d else d.iloc[0:0]
    combined = pd.concat([tmc, exp], ignore_index=True)

    def avg(df, column):
        return df[column].mean() if column in df and not df.empty else None

    project_area = float(fields.get('project_area', 0) or 0)
    project_rent = float(fields.get('project_rent', 0) or 0)
    calculated_rent_m2 = round(project_rent / project_area, 1) if project_area else 0
    commercial = pd.DataFrame([
        ['Renta', money(avg(d[d['SEG26'].astype(str).str.upper() == segment], 'RENTA UM_NUM')), money(project_rent) if project_rent else ''],
        ['Renta / m²', money(avg(d[d['SEG26'].astype(str).str.upper() == segment], 'RENTA UM_NUM') / avg(d[d['SEG26'].astype(str).str.upper() == segment], 'AREA_NUM')) if avg(d[d['SEG26'].astype(str).str.upper() == segment], 'AREA_NUM') else '', money(calculated_rent_m2) if calculated_rent_m2 else ''],
        ['Área (m²)', '', number(project_area) if project_area else ''],
        ['Vigencia', '15', fields.get('commercial_vigencia', '')],
        ['Permanencia', 'NO', fields.get('commercial_permanencia', '')],
        ['Periodo de gracia (Dias)', '60', fields.get('commercial_gracia', '')],
        ['Pre Operativos', '0', fields.get('commercial_preop', '')],
        ['IPC', 'PLANO', fields.get('commercial_ipc', '')],
        ['Operación 24 Hrs', 'SI', fields.get('commercial_operacion', '')],
        ['Venta de alcohol', 'SI', fields.get('commercial_alcohol', '')],
        ['Prima', 'NO', fields.get('commercial_prima', '')],
        ['Anticipo', 'NO', fields.get('commercial_anticipo', '')],
        ['Cláusulas Especiales', 'NO', fields.get('commercial_clausulas', '')],
        ['Restricciones', 'NO', fields.get('commercial_restricciones', '')],
    ], columns=['Condiciones de negocio', 'Estándar', 'Nombre del proyecto'])
    dates = pd.DataFrame([
        ['Firma', fields.get('signature', '')],
        ['Entrega de local', fields.get('delivery_date', '')],
        ['Apertura', fields.get('opening_date', '')],
    ], columns=['Hito', 'Fecha'])

    def build_generator_cards(group, fallback_images=False):
        source = fields.get(f'generator_{group}_cards', [])
if not isinstance(source, list):
            source = []
    if not source:
    source = fields.get("generator_cards", []) if isinstance(fields.get('generator_cards', []), list) else []
        cards_out = []
        for index, card in enumerate(source[:4], start=1):
            image_key = f'generator_{group}_image_{index}'
            if fallback_images:
                image_key = f'generator_image_{index}'
            cards_out.append(
                f'<div class="generator-card">'
                f'{media(images.get(image_key), "generator-img", "Sin foto", f"Generador {index}")}'
                f'<div class="generator-copy"><span class="generator-name">{text(card.get("name", ""), f"Generador {index}")}</span>'
                f'<span class="generator-type">{text(card.get("type", "Residencial"))}</span>'
                f'<strong>{number(card.get("value", 0))}</strong><span class="generator-unit">aprox.</span></div></div>'
            )
        return ''.join(cards_out) or '<div class="empty-note">Registra generadores para visualizarlos aquí.</div>'

    housing_cards = build_generator_cards('housing', fallback_images=False)
    employment_cards = build_generator_cards('employment')
    links = ' <span class="link-separator">|</span> '.join(filter(None, [
        link('Ubicación', fields.get('location_link') or fields.get('maps_link')),
        link('Video tráfico', fields.get('traffic_video_link')),
        link('Street View', fields.get('streetview_link')),
    ]))

    city_name = text(fields.get('new_city', 'Ciudad') if city == 'Ciudad nueva' else city or fields.get('new_city', 'Ciudad'))
    upz_name = text(fields.get('new_upz', 'UPZ / comuna') if upz == 'UPZ / comuna nueva' else upz or fields.get('new_upz', 'UPZ / comuna'))
    analyzed_count = len(d)
    total_market = (fields.get('housing_300', 0) or 0) + (fields.get('jobs_300', 0) or 0)
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
                <p class="address">{('<b>' + text(fields.get('address', '')) + '</b> ') if fields.get('address') else ''}{link('Ver en Maps', fields.get('maps_link'))}</p>
                <p class="tag">{text(fields.get('regional', 'Centro'))} <span>·</span> Segmento {text(fields.get('segment', 'Base'))}</p>
                <p class="meta">Especialista: {text(fields.get('specialist', ''))}<br>Creada: {text(fields.get('created_at', date.today().strftime('%d/%m/%Y')))}</p>
            </div>
            <div class="cover-art"><div class="cover-art-ring"></div><div class="cover-art-mark">OXXO</div><div class="cover-art-line"></div></div>
        </div>
    ''', number=1, cover=True))

    slides.append(slide('General', f'''
        <div class="context-row">
            <div><span>Ciudad / municipio</span><strong>{city_name}</strong></div>
            <div><span>UPZ / comuna</span><strong>{upz_name}</strong></div>
            <div><span>Tiendas analizadas</span><strong>{number(analyzed_count)}</strong></div>
        </div>
        <div class="general-layout">
            <div class="visual-card environment-visual">
                {media(images.get('general_environment_image'), 'environment-photo', 'Carga una foto de entorno', 'Entorno general')}
                <div class="visual-caption"><b>Lectura del entorno</b><span>Imagen principal del área de influencia</span></div>
            </div>
            <div class="general-right">
                <div class="panel-kicker">MEZCLA DE MERCADO</div>{table_html(pct_df, 'data-table compact-table')}
                <div class="general-tables"><div class="table-card red-accent"><h3>Tiendas TMCB</h3>{table_html(tmc[cols].head(4).rename(columns=rename), 'data-table compact-table')}</div><div class="table-card blue-accent"><h3>Tiendas EXP</h3>{table_html(exp[cols].head(4).rename(columns=rename), 'data-table compact-table')}</div></div>
                <div class="general-kpis"><div><span>Venta promedio</span><strong>{money(avg(combined, 'VENTAS OUM_NUM'))}</strong></div><div><span>Renta promedio</span><strong>{money(avg(combined, 'RENTA UM_NUM'))}</strong></div><div><span>Costo m² promedio</span><strong>{money(avg(combined, 'COSTO M2_NUM'))}</strong></div></div>
            </div>
        </div>
        <div class="general-conventions"><div class="panel-kicker">CONVENCIONES DE TIENDA</div>{conventions}</div>
    ''', number=2))

    for title, cards in [('Entorno | Generadores Vivienda', housing_cards), ('Entorno | Generadores Empleo', employment_cards)]:
        slides.append(slide(title, f'''
            <div class="generator-only-layout">
                <div class="generator-grid generator-grid-large">{cards}</div>
            </div>
        ''', number=None))

    slides.append(slide('Expansión | Mercado y Tráfico', f'''
        <div class="expansion-main-layout">
            <div class="visual-card expansion-main-photo">{media(images.get('expansion_intelligence'), 'expansion-main-image', 'Carga la foto de expansión', 'Foto de expansión')}</div>
            <div class="expansion-main-panel">
                <div class="kpi-grid">
                    <div><span>Viviendas 300 m</span><strong>{number(fields.get('housing_300', 0))}</strong><small>{percentage(fields.get('housing_300', 0), total_market)} del mercado</small></div>
                    <div><span>Empleos 300 m</span><strong>{number(fields.get('jobs_300', 0))}</strong><small>{percentage(fields.get('jobs_300', 0), total_market)} del mercado</small></div>
                    <div class="accent-kpi"><span>Mercado total</span><strong>{number(total_market)}</strong><small>Viviendas + empleos</small></div>
                </div>
                <div class="traffic-strip"><span>TRÁFICO / 15 MIN</span><b>Peatonal {text(fields.get('pedestrian_15', '—'))}</b><b>Vehicular {text(fields.get('vehicle_15', '—'))}</b><b>Motos {text(fields.get('motorcycle_15', '—'))}</b></div>
                <div class="market-share"><div><span>Viviendas / mercado total</span><strong>{percentage(fields.get('housing_300', 0), total_market)}</strong></div><div><span>Empleos / mercado total</span><strong>{percentage(fields.get('jobs_300', 0), total_market)}</strong></div></div>
            </div>
        </div>
    ''', number=None))

    slides.append(slide('Tienda Hermana', f'''
        <div class="sister-layout">
            <div class="store-card sister-photo"><div class="store-label">FOTO TIENDA HERMANA</div>{media(images.get('similar_image'), 'store-image', 'Carga la foto de la tienda espejo', 'Tienda espejo')}</div>
            <div class="sister-name-card"><span>TIENDA HERMANA SELECCIONADA</span><strong>{text(fields.get('book_store', 'Pendiente'))}</strong><p>{text(fields.get('similar_comments', ''), 'Sin comentarios adicionales')}</p></div>
        </div>
    ''', number=8))

    slides.append(slide('Condiciones comerciales', f'''
        <div class="commercial"><div>{table_html(commercial)}</div><div><h3>Hitos del proyecto</h3>{table_html(dates)}<p>{text(fields.get('commercial_comments', ''), '')}</p></div></div>
    ''', number=10))

    css = '''
@page { size: 13.333in 7.5in; margin: 0; }
:root { --red:#B00000; --blue:#17457A; --orange:#F29100; --ink:#252525; --cream:#FBF8F1; --muted:#6E6E6E; --line:#E6E1D8; }
* { box-sizing: border-box; }
html { background:#121212; }
body { margin:0; background:#121212; color:var(--ink); font-family:Aptos, Arial, Helvetica, sans-serif; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.slide { width:13.333in; height:7.5in; position:relative; overflow:hidden; padding:.47in .55in .38in; page-break-after:always; break-after:page; break-inside:avoid; page-break-inside:avoid; background:radial-gradient(circle at 92% 0%, #ffffff 0, #ffffff 38%, var(--cream) 100%); }
.slide:before { content:''; position:absolute; right:-1.15in; top:.78in; width:2.25in; height:2.25in; border:18px solid rgba(176,0,0,.055); border-radius:50%; pointer-events:none; }
.slide > * { position:relative; z-index:1; }
.topline { position:absolute; z-index:3; top:0; left:0; right:0; height:.1in; background:linear-gradient(90deg,var(--red),#D7281F 60%,var(--orange)); }
.footline { position:absolute; z-index:3; bottom:0; left:0; right:0; height:.12in; background:linear-gradient(90deg,var(--red),var(--orange)); }
.eyebrow { margin:0 0 .055in; color:var(--muted); font-size:7.3pt; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
h1 { margin:.01in 0 .16in; color:var(--red); font-size:25pt; line-height:1.02; letter-spacing:-.025em; }
h2 { margin:.18in 0 .16in; color:var(--ink); font-size:31pt; line-height:1.02; letter-spacing:-.03em; }
h3 { margin:.08in 0 .07in; color:var(--red); font-size:13pt; line-height:1.05; }
p { margin:.08in 0; }
a { color:var(--red); font-weight:800; text-decoration:none; }
.cover { padding:.72in; background:linear-gradient(110deg,#FBF8F1 0 58%,#B00000 58% 100%); }
.cover:before { right:-.5in; top:-.6in; width:4.1in; height:4.1in; border:1px solid rgba(255,255,255,.22); }
.cover-grid { display:grid; grid-template-columns:58% 42%; align-items:center; height:100%; }
.cover-copy { padding-right:.35in; }
.brand { color:var(--red); font-size:31pt; font-weight:900; letter-spacing:-.04em; }
.cover-kicker { margin-top:.28in; color:var(--red); font-size:10pt; font-weight:900; letter-spacing:.15em; }
.cover .sub { color:var(--muted); font-size:17pt; }
.cover .sub span, .cover .tag span { color:var(--orange); }
.cover .address { min-height:.25in; margin:.14in 0; font-size:11pt; }
.cover .tag { color:var(--red); font-size:12pt; font-weight:900; }
.cover .meta { margin-top:.82in; color:#4f4f4f; font-size:10pt; line-height:1.45; }
.cover-art { position:relative; height:5.7in; overflow:hidden; }
.cover-art:before { content:''; position:absolute; inset:.48in .12in .25in .42in; border:1px solid rgba(255,255,255,.45); border-radius:50% 50% 45% 55%; transform:rotate(-15deg); }
.cover-art-ring { position:absolute; width:3.55in; height:3.55in; right:.1in; top:.48in; border:26px solid rgba(255,255,255,.18); border-radius:50%; }
.cover-art-mark { position:absolute; right:.23in; top:2.0in; color:#fff; font-size:35pt; font-weight:900; letter-spacing:-.05em; transform:rotate(-7deg); }
.cover-art-line { position:absolute; right:.5in; bottom:1.05in; width:2.1in; height:.12in; background:var(--orange); transform:rotate(-7deg); }
.context-row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:.16in; margin:-.02in 0 .17in; }
.context-row > div { min-height:.57in; padding:.1in .14in; background:#fff; border-left:4px solid var(--red); box-shadow:0 6px 16px rgba(82,16,0,.1); }
.context-row span, .kpi-grid span, .plan-kpis span, .store-footer span { display:block; color:var(--muted); font-size:7pt; font-weight:800; letter-spacing:.09em; text-transform:uppercase; }
.context-row strong { display:block; margin-top:.035in; color:var(--ink); font-size:12.5pt; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .environment-layout { display:grid; grid-template-columns:61% 39%; gap:.25in; height:5.52in; }
    .general-layout { display:grid; grid-template-columns:43% 57%; gap:.22in; height:4.35in; }
    .general-layout .environment-visual { height:4.35in; }
    .general-layout .environment-photo { height:3.73in; }
    .general-right { min-width:0; }
    .general-tables { display:grid; grid-template-columns:1fr 1fr; gap:.12in; margin-top:.10in; }
    .general-kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:.08in; margin-top:.10in; }
    .general-kpis > div { min-width:0; padding:.06in .07in; background:linear-gradient(135deg,#fff,#FBF8F1); border-left:3px solid var(--red); box-shadow:0 4px 10px rgba(82,32,0,.08); }
    .general-kpis span { display:block; color:var(--muted); font-size:5.8pt; font-weight:900; letter-spacing:.045em; line-height:1.05; text-transform:uppercase; }
    .general-kpis strong { display:block; margin-top:.025in; color:var(--red); font-size:11pt; line-height:1; white-space:nowrap; }
    .general-conventions { margin-top:.12in; padding:.045in .06in .04in; background:#fff; border-top:2px solid var(--orange); box-shadow:0 4px 10px rgba(82,32,0,.06); }
    .general-conventions .panel-kicker { margin:0 0 .03in; }
    .general-conventions .convention-legend { grid-template-columns:repeat(8, minmax(0, 1fr)); gap:.035in; }
    .general-conventions .convention-item { padding:.012in .02in .016in; }
    .general-conventions .convention-item span { font-size:4.8pt; }
    .general-conventions .convention-swatch { height:.13in; }

.visual-card, .plan-map-card, .asset-card, .store-card { position:relative; overflow:hidden; background:#fff; border-radius:.11in; box-shadow:0 11px 24px rgba(70,25,0,.14); }
.environment-visual { height:5.52in; }
.environment-photo { display:block; width:100%; height:4.9in; object-fit:cover; object-position:center; }
.visual-caption { position:absolute; left:0; right:0; bottom:0; min-height:.62in; padding:.13in .17in; color:#fff; background:linear-gradient(90deg,rgba(32,12,0,.88),rgba(32,12,0,.55)); }
.visual-caption b { display:block; font-size:11pt; }
.visual-caption span { display:block; margin-top:.02in; font-size:8.5pt; color:#F9E9D8; }
.insight-panel { display:flex; flex-direction:column; min-width:0; padding:.1in .04in .05in .02in; }
.panel-kicker { margin:.01in 0 .07in; color:var(--red); font-size:7pt; font-weight:900; letter-spacing:.13em; }
.data-table { width:100%; border-collapse:separate; border-spacing:0; overflow:hidden; background:#fff; border-radius:.08in; box-shadow:0 7px 16px rgba(82,32,0,.1); font-size:7.9pt; }
.data-table th { padding:.085in .07in; background:linear-gradient(110deg,var(--red),#D7281F); color:#fff; text-align:left; font-size:7.2pt; letter-spacing:.025em; }
.data-table td { padding:.075in .07in; border-bottom:1px solid var(--line); line-height:1.12; }
.data-table tr:nth-child(even) td { background:#FCFAF5; }
.data-table tr:last-child td { border-bottom:0; }
.compact-table { font-size:7.35pt; }
.compact-table th { font-size:6.8pt; padding:.07in .055in; }
.compact-table td { padding:.062in .055in; }
.legend-block { margin-top:.19in; padding-top:.13in; border-top:1px solid var(--line); }
.legend { display:flex; flex-wrap:wrap; gap:.095in .12in; font-size:8.4pt; }
.convention-legend { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:.035in; }
    .convention-item { display:grid; grid-template-columns:1fr; grid-template-rows:.235in auto; min-width:0; align-items:center; padding:.018in .025in .025in; background:rgba(255,255,255,.7); border:1px solid #EFEAE2; border-radius:.035in; text-align:center; }
    .convention-swatch { display:block; width:100%; height:.16in; border-radius:.025in; box-shadow:inset 0 0 0 1px rgba(0,0,0,.08); }

.convention-item span { color:var(--muted); font-size:5.2pt; font-weight:900; letter-spacing:.045em; line-height:1; text-transform:uppercase; }
.convention-legend.strip { grid-template-columns:repeat(8, minmax(0, 1fr)); gap:.035in; }
.convention-legend.strip .convention-item { grid-template-rows:.19in auto; padding:.014in .02in .02in; }
    .convention-legend.strip .convention-swatch { height:.13in; }

.convention-legend.strip .convention-item span { font-size:4.6pt; }
.convention-band { margin-top:.08in; padding:.035in .05in .04in; background:#fff; border-top:2px solid var(--orange); box-shadow:0 4px 10px rgba(82,32,0,.06); }
.convention-band .panel-kicker { margin:0 0 .04in .02in; }
.generators-conventions { margin-top:.12in; }
.dot { display:inline-block; width:.13in; height:.13in; margin-right:.04in; border-radius:50%; vertical-align:-.018in; }
.red { background:var(--red); } .blue { background:var(--blue); } .lightblue { background:var(--lightblue); } .purple { background:var(--purple); } .orange { background:var(--orange); }
.insight-callout { margin-top:auto; padding:.13in .14in; background:linear-gradient(135deg,#FFF2D8,#FFE0B4); border-left:5px solid var(--orange); }
.insight-callout span { display:block; color:#8A4A00; font-size:7pt; font-weight:900; letter-spacing:.1em; text-transform:uppercase; }
.insight-callout strong { display:block; margin-top:.02in; color:var(--red); font-size:18pt; }
.insight-callout small { color:#704817; font-size:8pt; }
.plan-layout { display:grid; grid-template-columns:34% 66%; gap:.25in; height:4.18in; }
.plan-map-card { height:4.18in; padding:.14in; }
.map-image { display:block; width:100%; height:3.2in; object-fit:contain; background:#F4F1EA; border-radius:.07in; }
.map-caption { padding:.1in .02in 0; color:var(--muted); font-size:8.5pt; line-height:1.25; }
.plan-tables { display:grid; grid-template-columns:1fr 1fr; gap:.16in; min-width:0; }
.table-card { min-width:0; padding:.09in; background:#fff; border-radius:.1in; box-shadow:0 8px 18px rgba(82,32,0,.1); }
.table-card h3 { margin:.01in .03in .08in; font-size:11pt; }
.table-card h3 span { color:var(--muted); font-size:7pt; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.red-accent { border-top:5px solid var(--red); } .blue-accent { border-top:5px solid var(--blue); }
.blue-accent h3 { color:var(--blue); }
.plan-footer { margin-top:.16in; }
.plan-kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:.13in; }
.plan-kpis > div { padding:.1in .13in; background:linear-gradient(135deg,#fff,#FBF8F1); border-left:4px solid var(--red); box-shadow:0 6px 14px rgba(82,32,0,.1); }
.plan-kpis strong { display:block; margin-top:.025in; color:var(--red); font-size:16pt; }
.note { color:var(--muted); font-size:8pt; }
.note b { color:var(--ink); }
.two-photos { display:grid; grid-template-columns:1fr 1fr; gap:.25in; }
.solution-photos .photo-large { height:4.25in; }
.photo-large { display:block; width:100%; height:3.65in; object-fit:cover; border-radius:.1in; box-shadow:0 12px 24px rgba(0,0,0,.22); }
.description { margin-top:.16in; padding:.12in .16in; background:#fff; border-left:5px solid var(--orange); box-shadow:0 6px 14px rgba(82,32,0,.08); font-size:10pt; }
.description h3 { display:inline-block; margin:0 .2in 0 0; }
.description p { display:inline; line-height:1.3; }
.links { margin-top:.06in; }
.links a { margin-right:.08in; text-decoration:underline; }
.link-separator { color:var(--orange); }
.generators-layout { display:grid; grid-template-columns:36% 64%; gap:.25in; height:4.72in; }
.intelligence-card { height:4.72in; }
.intelligence-photo { display:block; width:100%; height:4.1in; object-fit:cover; }
.market-panel { min-width:0; padding:.02in 0 0; }
.kpi-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:.11in; }
.kpi-grid > div { min-height:.7in; padding:.11in .12in; background:#fff; border-top:4px solid var(--red); box-shadow:0 6px 14px rgba(82,32,0,.09); }
.kpi-grid strong { display:block; margin-top:.04in; color:var(--red); font-size:18pt; line-height:1; }
.kpi-grid .accent-kpi { background:linear-gradient(135deg,var(--red),#D7281F); border-top-color:var(--orange); }
.kpi-grid .accent-kpi span, .kpi-grid .accent-kpi strong { color:#fff; }
.traffic-strip { display:flex; align-items:center; gap:.14in; margin:.15in 0 .13in; padding:.1in .12in; background:#F2EEE5; color:var(--ink); font-size:8pt; }
.traffic-strip span { margin-right:auto; color:var(--red); font-size:7pt; font-weight:900; letter-spacing:.09em; }
.traffic-strip b { white-space:nowrap; }
.market-share { display:grid; grid-template-columns:1fr 1fr; gap:.11in; padding:.1in .13in; background:linear-gradient(100deg,#FFF1D8,#fff); border-left:5px solid var(--orange); }
.market-share > div { min-width:0; }
.market-share span { display:block; color:#925000; font-size:6.4pt; font-weight:900; letter-spacing:.045em; line-height:1.1; text-transform:uppercase; }
.market-share strong { display:block; margin-top:.035in; color:var(--red); font-size:14pt; line-height:1; }
    .generator-page-layout { display:grid; grid-template-columns:38% 62%; gap:.25in; height:5.55in; }
    .generator-only-layout { height:5.95in; padding-top:.02in; }
    .generator-page-panel { min-width:0; padding:.02in 0; }
    .generator-grid-large { grid-template-columns:1fr 1fr; gap:.2in; margin-top:0; }
    .generator-grid-large .generator-card { min-height:2.82in; grid-template-columns:3.15in 1fr; gap:.18in; padding:.14in; }
    .generator-grid-large .generator-img { width:3.15in; height:2.52in; }
    .generator-grid-large .generator-name { font-size:12pt; white-space:normal; }
    .generator-grid-large .generator-type { font-size:9pt; }
    .generator-grid-large .generator-copy strong { font-size:22pt; }
    .expansion-main-layout { display:grid; grid-template-columns:38% 62%; gap:.28in; height:5.65in; }
    .expansion-main-photo { height:5.65in; }
    .expansion-main-image { display:block; width:100%; height:100%; object-fit:contain; object-position:center; background:#F4F1EA; }
    .expansion-main-panel { min-width:0; padding:.02in 0; }
    .expansion-main-panel .kpi-grid { gap:.14in; }
    .expansion-main-panel .kpi-grid > div { min-height:1.18in; padding:.16in .18in; }
    .expansion-main-panel .kpi-grid span { font-size:9pt; letter-spacing:.08em; }
    .expansion-main-panel .kpi-grid strong { margin-top:.08in; font-size:30pt; line-height:1; }
    .expansion-main-panel small { display:block; margin-top:.06in; color:var(--muted); font-size:9pt; }
    .expansion-main-panel .traffic-strip { margin:.22in 0 .18in; padding:.16in .18in; font-size:10pt; }
    .expansion-main-panel .traffic-strip span { font-size:9pt; }
    .expansion-main-panel .traffic-strip b { font-size:16pt; }
    .expansion-main-panel .market-share { padding:.16in .18in; gap:.16in; }
    .expansion-main-panel .market-share span { font-size:8pt; }
    .expansion-main-panel .market-share strong { margin-top:.06in; font-size:23pt; }
    .generator-page-heading { display:flex; justify-content:space-between; align-items:end; margin-bottom:.12in; padding-bottom:.08in; border-bottom:2px solid var(--orange); }
    .generator-page-heading span { color:var(--muted); font-size:7pt; font-weight:900; letter-spacing:.12em; }
    .generator-page-heading strong { color:var(--red); font-size:12pt; }
    .generator-page-panel .generator-grid { margin-top:0; }
    .generator-page-panel .traffic-strip { margin-top:.2in; }
    .generator-grid { display:grid; grid-template-columns:1fr 1fr; gap:.11in; margin-top:.16in; }
.generator-card { display:grid; grid-template-columns:1.34in 1fr; min-height:.82in; gap:.1in; align-items:center; padding:.07in; background:#fff; border:1px solid #ECE5DA; box-shadow:0 5px 12px rgba(82,32,0,.07); }
    .generator-img { display:block; width:1.34in; height:.68in; object-fit:contain; object-position:center; border-radius:.055in; background:#F0ECE4; }
.generator-copy { min-width:0; }
    .generator-name { display:block; overflow:hidden; color:var(--ink); font-size:8.5pt; font-weight:900; text-overflow:ellipsis; white-space:nowrap; }
    .generator-type { display:block; overflow:hidden; margin-top:.02in; color:var(--muted); font-size:7.2pt; font-weight:800; text-overflow:ellipsis; text-transform:uppercase; white-space:nowrap; }

.generator-copy strong { display:inline-block; margin-top:.035in; color:var(--red); font-size:15pt; line-height:1; }
.generator-unit { display:inline-block; margin-left:.04in; color:var(--muted); font-size:7.5pt; }
    .capex-layout { display:grid; grid-template-columns:1fr 1fr; gap:.25in; height:5.35in; }
    .single-asset-layout { display:flex; justify-content:center; height:5.35in; }
    .single-asset-card { width:78%; }
    .asset-card { height:5.35in; padding:.16in; }

.asset-card:after { content:''; position:absolute; inset:0; pointer-events:none; border:1px solid rgba(255,255,255,.7); border-radius:.11in; }
.capex-card { background:#F2EEE5; }
.asset-label, .store-label { position:absolute; z-index:2; top:.14in; left:.16in; padding:.055in .09in; background:var(--red); color:#fff; font-size:7pt; font-weight:900; letter-spacing:.12em; }
.capex-card .asset-label { background:var(--blue); }
.asset-image { display:block; width:100%; height:4.95in; object-fit:contain; object-position:center; background:#fff; border-radius:.07in; }
.comment-ribbon { display:flex; align-items:center; gap:.2in; margin-top:.14in; padding:.09in .14in; background:linear-gradient(90deg,#3E2117,#5A3021); color:#fff; }
.comment-ribbon span { color:#FFC16D; font-size:7pt; font-weight:900; letter-spacing:.1em; white-space:nowrap; }
.comment-ribbon p { margin:0; font-size:8.5pt; }
    .full-photo { display:block; width:calc(100% + 1.1in); height:6.05in; margin-left:-.55in; object-fit:contain; object-position:center; background:#F4F1EA; box-shadow:0 15px 30px rgba(0,0,0,.26); }
.full-bleed-slide { margin:0 -.55in; }
.store-pair { display:grid; grid-template-columns:1fr 1fr; gap:.25in; height:5.35in; }
.store-card { height:5.35in; padding:.12in; background:#fff; }
    .store-image { display:block; width:100%; height:5.11in; object-fit:contain; object-position:center; background:#F4F1EA; border-radius:.07in; }
    .store-footer { display:grid; grid-template-columns:38% 62%; gap:.18in; align-items:center; margin-top:.14in; padding:.1in .14in; background:#fff; border-left:5px solid var(--orange); box-shadow:0 6px 14px rgba(82,32,0,.08); }
    .sister-layout { display:grid; grid-template-columns:48% 52%; gap:.25in; height:5.55in; }
    .sister-photo { height:5.55in; }
    .sister-name-card { display:flex; flex-direction:column; justify-content:center; padding:.32in; background:linear-gradient(135deg,#fff,#FBF8F1); border-left:7px solid var(--orange); box-shadow:0 11px 24px rgba(70,25,0,.12); }
    .sister-name-card span { color:var(--muted); font-size:8pt; font-weight:900; letter-spacing:.13em; }
    .sister-name-card strong { margin-top:.15in; color:var(--red); font-size:27pt; line-height:1.05; overflow-wrap:anywhere; }
    .sister-name-card p { margin-top:.25in; color:var(--muted); font-size:10pt; line-height:1.35; }

.store-footer strong { display:block; margin-top:.025in; color:var(--red); font-size:11pt; }
.store-footer p { margin:0; color:var(--muted); font-size:8.5pt; }
    .commercial { display:grid; grid-template-columns:64% 36%; gap:.3in; }
    .commercial .data-table { font-size:8.2pt; }
    .financial-layout { height:5.68in; }
    .financial-photo-card { height:5.68in; padding:.14in; background:#fff; border-radius:.11in; box-shadow:0 11px 24px rgba(70,25,0,.14); }
    .financial-image { display:block; width:100%; height:5.25in; object-fit:contain; object-position:center; background:#F4F1EA; border-radius:.07in; }

.commercial p { font-size:9pt; line-height:1.35; }
.empty-note { padding:.16in; color:#999; font-size:8pt; }
.image-placeholder { display:flex; align-items:center; justify-content:center; min-height:1in; color:#9A8D7D; background:repeating-linear-gradient(135deg,#F4F0E8 0,#F4F0E8 10px,#EEE8DD 10px,#EEE8DD 20px); font-size:8pt; font-weight:800; letter-spacing:.06em; text-transform:uppercase; }

    .micro-grid { display:grid; grid-template-columns:repeat(3,1fr); grid-auto-rows:2.55in; gap:.14in; height:5.7in; }
    .micro-grid.count-1 { grid-template-columns:1fr; }
    .micro-grid.count-2 { grid-template-columns:repeat(2,1fr); }
    .micro-grid.count-4 { grid-template-columns:repeat(2,1fr); }
    .micro-grid.count-5 { grid-template-columns:repeat(3,1fr); }
    .micro-photo { display:block; width:100%; height:100%; min-height:0; object-fit:cover; border-radius:.08in; box-shadow:0 8px 18px rgba(70,25,0,.15); }
    .pilot-grid { display:grid; grid-template-columns:1fr 1fr; gap:.25in; height:5.65in; }
    .pilot-card { min-width:0; overflow:hidden; background:#fff; border-radius:.1in; box-shadow:0 11px 24px rgba(70,25,0,.14); }
    .pilot-photo { display:block; width:100%; height:5.65in; object-fit:cover; }

@media screen {
    body { padding:28px 0; }
    .slide { margin:0 auto 28px; box-shadow:0 22px 55px rgba(0,0,0,.35); }
    .slide:last-child { margin-bottom:0; }
}
@media print {
    html, body { background:#fff; }
    .slide { margin:0; box-shadow:none; break-after:page; page-break-after:always; break-inside:avoid; page-break-inside:avoid; }
    .slide:last-child { break-after:auto !important; page-break-after:auto !important; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior:auto !important; } }
'''

    return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OXXO | Presentación de expansión</title><style>' + css + '</style></head><body>' + ''.join(slides) + '</body></html>'



def render_expansion(fields, images):
    """Render the additional one-page expansion summary requested by the user."""
    housing = float(fields.get('housing_300', 0) or 0)
    jobs = float(fields.get('jobs_300', 0) or 0)
    total = housing + jobs
    project = text(fields.get('project_name', 'Nombre del punto'))
    image = media(images.get('expansion_intelligence'), 'expansion-summary-image', 'Carga la foto de expansión', 'Foto de expansión')
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OXXO | Expansión</title><style>
@page{{size:13.333in 7.5in;margin:0}}*{{box-sizing:border-box}}body{{margin:0;background:#121212;font-family:Aptos,Arial,sans-serif;color:#252525}}.page{{width:13.333in;height:7.5in;padding:.55in 
'''
