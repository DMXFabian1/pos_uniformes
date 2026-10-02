import re, unicodedata, html, mistune, pathlib
SRC = pathlib.Path(__file__).resolve().parent.parent
OUT = SRC/'in_ictu_oculi.html'
DOCS = [
 ('00','Cómo usar el curso'),('01','Tesis y mapa conceptual'),('02','Método de lectura visual'),
 ('03','Programa: 16 módulos'),('04','Rutas'),('05','Proyecto Día de Muertos'),
 ('06','Bibliografía'),('07','Fuentes primarias'),('08','Yucatán y Campeche 2026')]
md = mistune.create_markdown(plugins=['table','strikethrough'], escape=False)

TAGS = {'H':'Hecho documentado','E':'Evidencia','I':'Interpretación','Hi':'Hipótesis',
        'Es':'Especulación','NS':'No sabemos','C':'Proyección contemporánea','PRENSA':'Sólo en prensa'}
CODE = r'(?:PRENSA|NS|Hi|Es|H|E|I|C)'
tag_re = re.compile(r'\[(' + CODE + r')((?:\s*/\s*' + CODE + r')*)((?:[:,][^\]\[<]{0,70})?)\]')
def tag_sub(m):
    first = m.group(1); rest = m.group(2) or ''; extra = (m.group(3) or '').strip(' ,:')
    codes = [first] + [c.strip() for c in rest.split('/') if c.strip()]
    title = ' / '.join(TAGS[c] for c in codes)
    out = '<span class="tag tag-%s" title="%s">%s</span>' % (first, title, ' / '.join(codes))
    if extra: out += '<span class="tag-note">%s</span>' % extra
    return out

def slug(s):
    s = unicodedata.normalize('NFKD', re.sub('<[^>]+>','',s)).encode('ascii','ignore').decode()
    s = re.sub(r'[^A-Za-z0-9]+','-',s).strip('-').lower()
    return s[:60] or 'x'

def process(num, text):
    text = text.replace('🔓', '<span class="chip chip-open">acceso libre</span>')
    h = md(text)
    # demote the document's h1 (we render our own header)
    m = re.search(r'<h1>(.*?)</h1>', h, re.S)
    title = m.group(1).strip() if m else ''
    h = re.sub(r'<h1>.*?</h1>\s*', '', h, count=1, flags=re.S)
    nav, seen = [], set()
    def head(mm):
        lvl, inner = mm.group(1), mm.group(2)
        base = 'd%s-%s' % (num, slug(inner)); sid = base; i = 2
        while sid in seen: sid = '%s-%d' % (base, i); i += 1
        seen.add(sid)
        if lvl == '2' or (lvl == '3' and num == '03'):
            nav.append((lvl, sid, re.sub('<[^>]+>','',inner)))
        return '<h%s id="%s">%s</h%s>' % (lvl, sid, inner, lvl)
    h = re.sub(r'<h([234])>(.*?)</h\1>', head, h, flags=re.S)
    # epistemic tags (outside of pre)
    parts = re.split(r'(<pre>.*?</pre>)', h, flags=re.S)
    parts = [p if p.startswith('<pre>') else tag_re.sub(tag_sub, p) for p in parts]
    h = ''.join(parts)
    h = re.sub(r'\[((?:FP|EA|CAT|DIV|REF|INS|ART)[^\]\[<]{0,40})\]', lambda mm: '<span class="src" title="Tipo de fuente">%s</span>' % mm.group(1), h)
    h = h.replace('✔', '<span class="chip chip-ok" title="Verificado">✔</span>')
    h = h.replace('◐', '<span class="chip chip-part" title="Verificación parcial">◐</span>')
    h = h.replace('✱', '<span class="chip chip-unv" title="No verificado en catálogo">✱</span>')
    h = re.sub(r'<table>', '<div class="table-wrap"><table>', h)
    h = re.sub(r'</table>', '</table></div>', h)
    h = re.sub(r'<pre>', '<div class="pre-wrap"><pre>', h); h = re.sub(r'</pre>', '</pre></div>', h)
    # cross-links to other documents
    h = re.sub(r'<code>(0\d)_([^<]*?)\.md</code>', lambda mm: '<a class="xref" href="#doc-%s">%s</a>' % (mm.group(1), dict(DOCS)[mm.group(1)]), h)
    h = re.sub(r'<a href="http', '<a target="_blank" rel="noopener" href="http', h)
    return title, h, nav

sections, navhtml = [], []
for num, label in DOCS:
    f = next(SRC.glob(num + '_*.md'))
    title, body, nav = process(num, f.read_text(encoding='utf-8'))
    sections.append('<section class="doc" id="doc-%s" aria-labelledby="t-%s">\n<header class="doc-head"><p class="doc-num">Documento %s</p><h1 class="doc-title" id="t-%s">%s</h1></header>\n%s\n</section>' % (num, num, num, num, label, body))
    items = ''.join('<li class="lv%s"><a href="#%s">%s</a></li>' % (l, sid, html.escape(t)) for l, sid, t in nav)
    navhtml.append('<li class="navdoc"><details%s><summary><a href="#doc-%s"><span class="n">%s</span> %s</a></summary><ol class="sub">%s</ol></details></li>' % (' open' if num=='00' else '', num, num, label, items))

shell = pathlib.Path(__file__).with_name('shell.html').read_text(encoding='utf-8')
out = shell.replace('{{NAV}}', '\n'.join(navhtml)).replace('{{CONTENT}}', '\n'.join(sections))
OUT.write_text(out, encoding='utf-8')
print(OUT, len(out)//1024, 'KB')
