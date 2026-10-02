"""Genera el lector visual del curso (in_ictu_oculi.html) a partir de los .md.

Uso: python3 build2.py   (requiere: mistune, beautifulsoup4; imágenes en ../img/)
"""
import re, json, html, unicodedata, pathlib
import mistune
from bs4 import BeautifulSoup

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent
OUT = SRC / 'in_ictu_oculi.html'
IMG = SRC / 'img'
md = mistune.create_markdown(plugins=['table', 'strikethrough'], escape=False)

# ---------------------------------------------------------------- imágenes
# clave -> (archivo, crédito, object-position)
CREDITS = json.loads((HERE / 'credits.json').read_text(encoding='utf-8')) if (HERE / 'credits.json').exists() else {}
def img(key, pos='center'):
    if key and (IMG / f'{key}.jpg').exists():
        return {'src': f'img/{key}.jpg', 'thumb': f'img/{key}-s.jpg', 'credit': CREDITS.get(key, ''), 'pos': pos}
    return None

# ---------------------------------------------------------------- marcas
TAGS = {'H': 'Hecho documentado', 'E': 'Evidencia', 'I': 'Interpretación', 'Hi': 'Hipótesis',
        'Es': 'Especulación', 'NS': 'No sabemos', 'C': 'Proyección contemporánea', 'PRENSA': 'Sólo en prensa'}
CODE = r'(?:PRENSA|NS|Hi|Es|H|E|I|C)'
tag_re = re.compile(r'\[(' + CODE + r')((?:\s*/\s*' + CODE + r')*)((?:[:,][^\]\[<]{0,70})?)\]')
def tag_sub(m):
    first, rest, extra = m.group(1), m.group(2) or '', (m.group(3) or '').strip(' ,:')
    codes = [first] + [c.strip() for c in rest.split('/') if c.strip()]
    out = '<span class="tag tag-%s" title="%s">%s</span>' % (first, ' / '.join(TAGS[c] for c in codes), ' / '.join(codes))
    return out + ('<span class="tag-note">%s</span>' % extra if extra else '')

ROUTE_OF_FILE = {'00': 'intro', '01': 'tesis', '02': 'metodo', '03': 'programa', '04': 'rutas-historia',
                 '05': 'proyecto', '06': 'biblio', '07': 'fuentes', '08': 'yucatan'}

def render(text):
    text = text.replace('🔓', '<span class="chip chip-open">acceso libre</span>')
    h = md(text)
    parts = re.split(r'(<pre>.*?</pre>)', h, flags=re.S)
    h = ''.join(p if p.startswith('<pre>') else tag_re.sub(tag_sub, p) for p in parts)
    h = re.sub(r'\[((?:FP|EA|CAT|DIV|REF|INS|ART)[^\]\[<]{0,40})\]', lambda m: '<span class="src" title="Tipo de fuente">%s</span>' % m.group(1), h)
    h = h.replace('✔', '<span class="chip chip-ok" title="Verificado">✔</span>')
    h = h.replace('◐', '<span class="chip chip-part" title="Verificación parcial">◐</span>')
    h = h.replace('✱', '<span class="chip chip-unv" title="No verificado en catálogo">✱</span>')
    h = h.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')
    h = h.replace('<pre>', '<div class="pre-wrap"><pre>').replace('</pre>', '</pre></div>')
    h = re.sub(r'<code>(0\d)_[^<]*?\.md</code>', lambda m: '<a class="xref" href="#%s">%s</a>' % (ROUTE_OF_FILE[m.group(1)], '{{TITLE:%s}}' % ROUTE_OF_FILE[m.group(1)]), h)
    h = re.sub(r'<a href="http', '<a target="_blank" rel="noopener" href="http', h)
    return h

def read(num):
    return next(SRC.glob(num + '_*.md')).read_text(encoding='utf-8')

def strip_h1(text):
    return re.sub(r'^# .*\n', '', text, count=1)

def split_h2(text):
    """Devuelve [(titulo_h2, cuerpo)] incluyendo un bloque inicial con titulo ''."""
    out, cur, buf = [], '', []
    for line in text.split('\n'):
        if line.startswith('## '):
            out.append((cur, '\n'.join(buf))); cur, buf = line[3:].strip(), []
        else:
            buf.append(line)
    out.append((cur, '\n'.join(buf)))
    return out

def plain(s):
    return re.sub(r'[*_`]', '', s).strip()

# ---------------------------------------------------------------- unidades
units = []   # dict(id, part, kind, num, title, kicker, summary, html, image)
def unit(**k): units.append(k); return k

def doc_unit(uid, part, title, body_md, image, kicker, summary):
    unit(id=uid, part=part, kind='doc', title=title, kicker=kicker, summary=summary,
         html=render(body_md), image=image)

# Parte I · Fundamentos
d00 = strip_h1(read('00'))
doc_unit('intro', 'Fundamentos', 'Cómo usar el curso', d00, img('intro'), 'Antes de empezar',
         'Qué contiene el curso, cómo están marcadas las certezas y la regla de oro.')
d01 = split_h2(strip_h1(read('01')))
tesis = re.sub(r'^### ', '## ', '\n'.join(b for t, b in d01 if t.startswith('1.')), flags=re.M)
mapa = re.sub(r'^### ', '## ', '\n'.join(b for t, b in d01 if t.startswith('2.')), flags=re.M)
doc_unit('tesis', 'Fundamentos', 'Tesis central', tesis, img('tesis'), 'Hipótesis de trabajo',
         'Las personas gramaticales de la muerte y las tres inferencias a partir de «vas a morir».')
doc_unit('mapa', 'Fundamentos', 'Mapa conceptual', mapa, img('mapa'), 'Trece conceptos',
         'Memento mori, vanitas, danse macabre, ars moriendi… su gramática, su historia y su uso artístico.')
doc_unit('metodo', 'Fundamentos', 'Método de lectura visual', strip_h1(read('02')), img('metodo'), 'Veo · sé · infiero · interpreto',
         'Siete capas para leer una obra, una fotografía, una ofrenda o un cementerio.')

# Parte II · Lecciones
d03 = strip_h1(read('03'))
sections = split_h2(d03)
arch = next(b for t, b in sections if t == 'Arquitectura')
ruta = next(b for t, b in sections if t.startswith('Ruta intensiva'))
doc_unit('programa', 'Lecciones', 'El programa', '## Arquitectura\n' + arch + '\n## Ruta intensiva\n' + ruta,
         img('programa', 'center 30%'), 'Dieciséis módulos',
         'La arquitectura del curso, las obras que regresan y la ruta intensiva para este otoño.')

MOD_IMG = {1: ('triunfo', 'center 55%'), 2: ('m02', 'center 30%'), 3: ('m03', 'center'), 4: ('m04', 'left center'),
           5: ('m05', 'center 35%'), 6: ('m06', 'center'), 7: ('m07', 'center'), 8: ('m08', 'center 35%'),
           9: ('m09', 'center 40%'), 10: ('m10', 'center 40%'), 11: ('m11', 'center 30%'), 12: ('m12', 'center'),
           13: ('m13', 'center 25%'), 14: ('m14', 'center'), 15: ('m15', 'center 20%'), 16: ('triunfo', 'right 20%')}
block = ''
for t, b in sections:
    if t.startswith('BLOQUE'):
        block = re.sub(r'^BLOQUE\s+[IVX]+\.\s*', '', t).capitalize()
        block = block[0] + block[1:].lower()
        for m in re.finditer(r'^### Módulo (\d+)\. (.*?)\n(.*?)(?=^### |\Z)', b, re.S | re.M):
            n, title, body = int(m.group(1)), m.group(2).strip(), m.group(3)
            unit(id='m%02d' % n, part='Lecciones', kind='module', num=n, title=title, kicker=block,
                 body=body, image=img(*MOD_IMG[n]))

# Parte III · Rutas
d04 = split_h2(strip_h1(read('04')))
def pick(secs, *prefixes):
    return '\n'.join('## %s\n%s' % (t, b) for t, b in secs if any(t.startswith(p) for p in prefixes))
intro04 = d04[0][1]
doc_unit('rutas-historia', 'Rutas', 'Historia y filosofía', intro04 + pick(d04, '7.', '8.'), img('rutas'), 'Rutas 7 y 8',
         'Doce funciones de la imagen de la muerte y veinte filósofos frente a veinte imágenes.')
doc_unit('rutas-mexico', 'Rutas', 'La muerte en México', pick(d04, '9.', 'PARTE IX', 'PARTE X'), img('rutas-mexico'), 'Ruta 9 · Europa y México',
         'Capas históricas, mapa regional y las cuatro preguntas de la comparación.')
doc_unit('rutas-foto', 'Rutas', 'Ruta fotográfica', pick(d04, '10.'), img('proyecto'), 'Ruta 10',
         'Veintiún fotógrafos y la relación que cada uno plantea entre fotografía y muerte.')

# Parte IV · Campo
d05 = split_h2(strip_h1(read('05')))
doc_unit('proyecto', 'Campo', 'El proyecto y el campo', pick(d05, '11.', 'PARTE XIV', 'PARTE XV'), img('campo'), 'Metodología',
         'No fotografiar México para confirmar lo que ya pienso: fases, preguntas de campo y la regla contra el cliché.')
doc_unit('etica', 'Campo', 'Ética de la mirada', pick(d05, '12.'), img('etica'), 'Criterios',
         'Diez reglas para fotografiar el duelo, los rituales y a quienes no conocemos.')
doc_unit('ejercicios', 'Campo', 'Ejercicios y proyecto final', pick(d05, '13.', '14.', 'PARTE XX'), img('ejercicios'), 'Práctica',
         'Veinte ejercicios, cómo criticar tus fotos, la serie, el ensayo y la última fotografía.')
doc_unit('yucatan', 'Campo', 'Yucatán y Campeche 2026', strip_h1(read('08')), img('yucatan'), '27 oct – 3 nov',
         'Pomuch, los pueblos de Valladolid y Mérida: contexto, ética, itinerario y preguntas.')

# Parte V · Referencia
doc_unit('biblio', 'Referencia', 'Bibliografía', strip_h1(read('06')), img('biblio'), 'Verificada',
         'Imprescindibles, recomendadas y especializadas, con su estado de verificación.')
doc_unit('fuentes', 'Referencia', 'Fuentes primarias', strip_h1(read('07')), img('fuentes'), 'Textos de época',
         'De la Vulgata a Rulfo: qué leer directamente y cómo leerlo.')

# ---------------------------------------------------------------- módulos
LABEL_CLASS = {'Pregunta central': 'q', 'Obra ancla': 'anchor', 'Preguntas socráticas': 'socratic',
               'Ejercicio': 'exercise', 'Ejercicios': 'exercise', 'Reflexión final': 'final', 'Lectura visual': 'visual'}
def module_html(u):
    soup = BeautifulSoup(render(u['body']), 'html.parser')
    ol = soup.find('ol')
    items = ol.find_all('li', recursive=False) if ol else []
    question, steps = '', []
    for i, li in enumerate(items, 1):
        st = li.find('strong')
        label = st.get_text().strip().rstrip('.') if st else ''
        if st: st.decompose()
        inner = ''.join(str(c) for c in li.contents).strip()
        inner = re.sub(r'^\s*', '', inner)
        if label == 'Pregunta central':
            question = BeautifulSoup(inner, 'html.parser').get_text().strip(); continue
        if label.startswith('Ejercicio'): label_key = 'Ejercicio'
        else: label_key = label
        steps.append((i, label, LABEL_CLASS.get(label_key, LABEL_CLASS.get(label, '')), inner))
    u['question'] = question
    u['summary'] = question
    nav = ''.join('<button class="stepdot" type="button" data-target="%s-s%02d" title="%s"><span>%02d</span>%s</button>' % (u['id'], n, html.escape(l), n, html.escape(l)) for n, l, c, _ in steps)
    im = u['image']
    def extra(c):
        if c == 'anchor' and im:
            return '<figure class="anchor-fig"><img src="%s" alt="" loading="lazy"><figcaption>%s</figcaption></figure>' % (im['src'], html.escape(im['credit']))
        return ''
    body = ''.join('<article class="step %s" id="%s-s%02d"><header><span class="step-n">%02d</span><h3>%s</h3></header><div class="step-body">%s</div>%s</article>'
                   % (c, u['id'], n, n, html.escape(l), inner, extra(c)) for n, l, c, inner in steps)
    return '<div class="steps-body">%s</div><nav class="steps" aria-label="Apartados de la lección"><p class="steps-title">En esta lección</p>%s</nav>' % (body, nav)

for u in units:
    if u['kind'] == 'module':
        u['html'] = module_html(u)

# ---------------------------------------------------------------- doc TOC chips
for u in units:
    if u['kind'] == 'doc':
        soup = BeautifulSoup(u['html'], 'html.parser')
        chips = []
        for k, h2 in enumerate(soup.find_all('h2'), 1):
            hid = '%s-h%02d' % (u['id'], k); h2['id'] = hid
            chips.append('<button class="chipnav" type="button" data-target="%s">%s</button>' % (hid, html.escape(h2.get_text().strip())))
        u['html'] = ('<nav class="chips" aria-label="En esta lección">%s</nav>' % ''.join(chips) if len(chips) > 1 else '') + str(soup)

# ---------------------------------------------------------------- ensamblado
titles = {u['id']: u['title'] for u in units}
def fix_titles(s):
    return re.sub(r'\{\{TITLE:([\w-]+)\}\}', lambda m: titles.get(m.group(1), m.group(1)), s)

def hero(u, idx):
    im = u['image']
    label = ('Lección %02d · %s' % (u['num'], u['kicker'])) if u['kind'] == 'module' else ('%s · %s' % (u['part'], u['kicker']))
    q = ('<p class="hero-q">%s</p>' % html.escape(u['question'])) if u.get('question') else ('<p class="hero-sum">%s</p>' % html.escape(u['summary']))
    if im:
        media = '<div class="hero-media"><img src="%s" alt="" loading="%s" style="object-position:%s"></div>' % (im['src'], 'eager' if idx < 2 else 'lazy', im['pos'])
        credit = '<p class="credit">%s</p>' % html.escape(im['credit']) if im['credit'] else ''
    else:
        media = '<div class="hero-media hero-type" aria-hidden="true"><span>%s</span></div>' % html.escape(u['title'][:1])
        credit = ''
    return ('<header class="uhero%s">%s<div class="hero-text"><p class="hero-kicker">%s</p><h1 class="hero-title">%s</h1>%s</div></header>%s'
            % ('' if im else ' noimg', media, html.escape(label), md(u['title']).strip()[3:-4], q, credit))

parts_order = ['Fundamentos', 'Lecciones', 'Rutas', 'Campo', 'Referencia']
PART_DESC = {'Fundamentos': 'La tesis, los conceptos y el método para mirar.',
             'Lecciones': 'Dieciséis módulos, de Bruegel a Pomuch. Cada uno con su obra ancla.',
             'Rutas': 'Cuatro recorridos transversales: historia, filosofía, México y fotografía.',
             'Campo': 'El proyecto, la ética y tu temporada en Yucatán y Campeche.',
             'Referencia': 'Bibliografía verificada y fuentes primarias.'}

sections_html = []
for i, u in enumerate(units):
    sections_html.append('<section class="unit" id="u-%s" data-unit="%s" hidden>%s<div class="ubody %s">%s</div><div class="endmark" aria-hidden="true"></div></section>'
                         % (u['id'], u['id'], hero(u, i), u['kind'], fix_titles(u['html'])))

def card(u):
    im = u['image']
    pic = ('<img src="%s" alt="" loading="lazy" style="object-position:%s">' % (im['thumb'], im['pos'])) if im else '<span class="card-type">%s</span>' % html.escape(u['title'][:1])
    num = ('%02d' % u['num']) if u['kind'] == 'module' else ''
    return ('<a class="card" href="#%s" data-card="%s"><span class="card-media">%s<span class="card-read" aria-label="Leída">✓</span></span>'
            '<span class="card-text"><span class="card-kicker">%s%s</span><span class="card-title">%s</span><span class="card-sum">%s</span></span></a>'
            % (u['id'], u['id'], pic, ('Lección ' + num + ' · ') if num else '', html.escape(u['kicker']),
               md(u['title']).strip()[3:-4], html.escape(u['summary'][:150] + ('…' if len(u['summary']) > 150 else ''))))

map_html = ''.join('<section class="part"><header class="part-head"><p class="part-n">Parte %s</p><h2>%s</h2><p>%s</p></header><div class="cards">%s</div></section>'
                   % (['I', 'II', 'III', 'IV', 'V'][k], p, PART_DESC[p], ''.join(card(u) for u in units if u['part'] == p))
                   for k, p in enumerate(parts_order))

drawer_html = ''.join('<li class="dpart">%s</li>%s' % (p, ''.join(
    '<li><a href="#%s" data-nav="%s"><span class="dn">%s</span><span class="dt">%s</span><span class="dcheck" aria-hidden="true"></span></a></li>'
    % (u['id'], u['id'], ('%02d' % u['num']) if u['kind'] == 'module' else '·', md(u['title']).strip()[3:-4]) for u in units if u['part'] == p))
    for p in parts_order)

meta = [{'id': u['id'], 'title': BeautifulSoup(md(u['title']), 'html.parser').get_text().strip(),
         'label': ('Lección %02d' % u['num']) if u['kind'] == 'module' else u['part'],
         'thumb': u['image']['thumb'] if u['image'] else '', 'pos': u['image']['pos'] if u['image'] else 'center'} for u in units]

shell = (HERE / 'shell2.html').read_text(encoding='utf-8')
out = (shell.replace('{{MAP}}', map_html).replace('{{DRAWER}}', drawer_html)
       .replace('{{UNITS}}', '\n'.join(sections_html)).replace('{{META}}', json.dumps(meta, ensure_ascii=False))
       .replace('{{HOMEIMG_TAG}}', '<img src="img/triunfo.jpg" alt="">' if (IMG / 'triunfo.jpg').exists() else '')
       .replace('{{HOMECREDIT}}', html.escape(CREDITS.get('triunfo', ''))))
OUT.write_text(out, encoding='utf-8')
print(OUT, len(out) // 1024, 'KB,', len(units), 'unidades')
