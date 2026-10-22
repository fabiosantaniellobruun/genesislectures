#!/usr/bin/env python3
"""Backup di genesislectures.com via WordPress REST API: Markdown + media originali.

Uso: python3 -I export.py [cartella_output]   (default: la cartella dello script)
Rieseguibile: i media già scaricati vengono saltati.
"""
import base64, html, json, re, sys, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

SITE = 'https://www.genesislectures.com'
API = SITE + '/wp-json/wp/v2/'
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent).resolve()
UA = {'User-Agent': 'Mozilla/5.0 (genesislectures backup)'}
CANCELLED = {'2020'}  # rimandata e poi annullata per il COVID-19: sul sito non risulta


def get(url):
    url = urllib.parse.quote(url, safe=':/?&=%#+,')
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read(), r.headers


def fetch_all(kind):
    items, page = [], 1
    while True:
        body, h = get(f'{API}{kind}?per_page=100&page={page}')
        items += json.loads(body)
        if page >= int(h.get('X-WP-TotalPages') or 1):
            return items
        page += 1


# --- HTML -> Markdown (copre solo i tag usati sul sito) ---------------------

INLINE = {'strong': '**', 'b': '**', 'em': '*', 'i': '*'}
BR = '\x00'  # segnaposto per <br>, diventa "  \n" (a capo forzato) alla fine


def img_md(alt, path):
    alt = re.sub(r'\s+', ' ', alt).replace('[', '\\[').replace(']', '\\]')
    if re.search(r'[\s()<>]', path):
        path = f'<{path}>'
    return f'![{alt}]({path})'


class MD(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = [['', None, {}]]  # [testo, tag, attributi] per tag che avvolgono

    def out(self, s):
        self.stack[-1][0] += s

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in INLINE or tag in ('a', 'blockquote'):
            self.stack.append(['', tag, a])
        elif tag in ('p', 'div', 'ul', 'ol'):
            self.out('\n\n')
        elif re.fullmatch(r'h[1-6]', tag):
            self.out('\n\n' + '#' * int(tag[1]) + ' ')
        elif tag == 'li':
            self.out('\n- ')
        elif tag == 'br':
            self.out(BR + '\n')
        elif tag == 'hr':
            self.out('\n\n---\n\n')
        elif tag == 'img':
            self.out(img_md(a.get('alt') or '', a.get('src') or ''))
        elif tag == 'iframe':
            self.out('\n\n' + self.get_starttag_text() + '</iframe>\n\n')

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if re.fullmatch(r'h[1-6]|p|div|ul|ol', tag):
            return self.out('\n\n')
        if self.stack[-1][1] != tag:  # tag sbilanciati (wpautop + shortcode rimossi): ignora
            return
        text, _, a = self.stack.pop()
        if tag == 'blockquote':
            lines = re.sub(r'\n{3,}', '\n\n', text.strip()).split('\n')
            return self.out('\n\n' + '\n'.join('> ' + l.strip() for l in lines) + '\n\n')
        core = text.strip()
        if not core:
            return self.out(text)
        lead, trail = text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]
        core = f'[{core}]({a.get("href", "")})' if tag == 'a' else INLINE[tag] + core + INLINE[tag]
        self.out(lead + core + trail)

    def handle_data(self, d):
        self.out(re.sub(r'\s+', ' ', d))

    def handle_comment(self, c):
        self.out(f'\n\n<!--{c}-->\n\n')

    def result(self):
        self.close()
        while len(self.stack) > 1:
            t = self.stack.pop()[0]
            self.out(t)
        s = '\n'.join(l.strip() for l in self.stack[0][0].split('\n'))
        s = re.sub(BR + r'(?=\n\n|\n*$)', '', s).replace(BR, '  ')
        return re.sub(r'\n{3,}', '\n\n', s).strip()


def to_md(h):
    p = MD()
    p.feed(h)
    return p.result()


def text(h):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h or ''))).strip()


# --- shortcode WPBakery/Uncode ----------------------------------------------

SC = r'\[(/?)((?:vc|uncode)_\w+)([^\]]*)\]'


def attrs(s):
    # wptexturize ha trasformato le virgolette degli attributi in ” e ″
    return dict(re.findall(r'(\w+)=["“”″]([^"“”″]*)["“”″]', html.unescape(s)))


def media_path(x):
    """Percorso locale (relativo a OUT) dell'originale, None per i video."""
    if x['mime_type'] == 'oembed/svg':
        return f'media/svg/{x["slug"]}.svg'
    if x['mime_type'].startswith('oembed'):
        return None
    p = urllib.parse.unquote(x['source_url'].split('/wp-content/uploads/', 1)[1])
    orig = (x.get('media_details') or {}).get('original_image')  # file "-scaled": prendi l'originale
    return 'media/' + (p.rsplit('/', 1)[0] + '/' + orig if orig else p)


def render(c, rel, M, meta):
    """Shortcode -> HTML pulito -> Markdown. Raccoglie gallery/video/background in meta."""
    def media_html(mid):
        x = M.get(int(mid)) if mid.strip().isdigit() else None
        if not x:
            return f'<!-- media {mid} non presente nella media library -->'
        title = text(x['title']['rendered'])
        if x['mime_type'] == 'oembed/youtube':
            url = html.unescape(x['source_url'])
            meta.setdefault('video', url)
            return f'<p><a href="{html.escape(url)}">Video: {html.escape(title)}</a></p>'
        alt = x['alt_text'] or text(x['caption']['rendered']) or title
        return f'<p><img src="{html.escape(rel + media_path(x))}" alt="{html.escape(alt)}"></p>'

    def raw_html(m):
        return urllib.parse.unquote(base64.b64decode(re.sub(r'<[^>]+>|\s', '', m.group(1))).decode())

    def button(m):
        url = urllib.parse.unquote(attrs(m.group(1)).get('link', '').split('|')[0].removeprefix('url:'))
        return f'<p><a href="{html.escape(url)}">{m.group(2)}</a></p>'

    def sc(m):
        close, name, a = m.group(1), m.group(2), attrs(m.group(3))
        if close:
            return '<div></div>'
        if 'back_image' in a and int(a['back_image']) in M:
            meta.setdefault('background', rel + media_path(M[int(a['back_image'])]))
        if name == 'vc_gallery':
            ids = [i for i in a.get('medias', '').split(',') if i.strip()]
            meta.setdefault('gallery', []).extend(
                rel + media_path(M[int(i)]) for i in ids if int(i) in M and media_path(M[int(i)]))
            return ''.join(media_html(i) for i in ids)
        if name == 'vc_single_image':
            return media_html(a.get('media', ''))
        if name == 'vc_separator':
            return '<hr>'
        if name == 'uncode_index':
            return f'<!-- griglia articoli (uncode_index): {a.get("loop", "")} -->'
        return '<div></div>'

    # Uncode: X_visibility="yes" = nascosta su X; le righe nascoste su desktop sono i doppioni mobile
    c = re.sub(r'\[(vc_row(?:_inner)?)(\s[^\]]*desktop_visibility[^\]]*)\].*?\[/\1\]',
               lambda m: '' if attrs(m.group(2)).get('desktop_visibility') == 'yes' else m.group(0), c, flags=re.S)
    c = re.sub(r'\[vc_raw_html[^\]]*\](.*?)\[/vc_raw_html\]', raw_html, c, flags=re.S)
    c = re.sub(r'\[vc_button([^\]]*)\](.*?)\[/vc_button\]', button, c, flags=re.S)
    return to_md(re.sub(SC, sc, c))


def event_info(c, year):
    """Estrae il box laterale (data / luogo) dei post e lo toglie dal corpo."""
    for m in re.finditer(r'\[vc_custom_heading([^\]]*)\](.*?)\[/vc_custom_heading\]', c, re.S):
        if attrs(m.group(1)).get('text_size') == 'h5':
            parts = to_md(m.group(2)).split('---')
            lines = [[l.strip() for l in p.split('\n') if l.strip()] for p in parts]
            when = ', '.join(l for l in lines[0] if l != year)
            where = ', '.join(sum(lines[1:], []))
            return c[:m.start()] + c[m.end():], when, where
    return c, '', ''


# --- scrittura file ------------------------------------------------------------

def yaml_value(v):
    return json.dumps(v, ensure_ascii=False)  # JSON è YAML valido


def write_md(path, front, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = '\n'.join(f'{k}: {yaml_value(v)}' for k, v in front.items() if v not in (None, '', []))
    path.write_text(f'---\n{fm}\n---\n\n{body}\n', encoding='utf-8')


def download(job):
    url, dest = job
    if dest.exists() and dest.stat().st_size:
        return dest, 'skip', None
    try:
        body, _ = get(url)
    except urllib.error.HTTPError as e:
        return dest, 'error', e.code
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    tmp.write_bytes(body)
    tmp.rename(dest)  # niente file a metà se lo script si interrompe
    return dest, 'ok', len(body)


def main():
    raw = {k: fetch_all(k) for k in ('posts', 'pages', 'media', 'categories', 'tags', 'uncodeblock')}
    raw['site'] = json.loads(get(SITE + '/wp-json/')[0])
    raw['site'] = {k: raw['site'].get(k) for k in ('name', 'description', 'url', 'home', 'gmt_offset', 'timezone_string')}
    (OUT / 'raw').mkdir(parents=True, exist_ok=True)
    for k, v in raw.items():
        (OUT / 'raw' / f'{k}.json').write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding='utf-8')

    M = {x['id']: x for x in raw['media']}
    cats = {c['id']: c['name'] for c in raw['categories']}
    tags = {t['id']: t['name'] for t in raw['tags']}
    by_id = {p['id']: p for p in raw['posts'] + raw['pages'] + raw['uncodeblock']}

    # media: originali in media/AAAA/MM/, SVG salvati inline -> file, video -> solo link
    jobs, problems = [], []
    for x in raw['media']:
        p = media_path(x)
        if x['mime_type'] == 'oembed/svg':
            m = re.search(r'<svg.*</svg>', html.unescape(x['description']['rendered']), re.S)
            svg = re.sub(r'</?p>|<br ?/?>', '', m.group()) if m else ''
            try:
                ET.fromstring(svg)
            except ET.ParseError as e:
                problems.append(f'SVG {x["slug"]} non valido ({e}): salvato comunque')
            (OUT / p).parent.mkdir(parents=True, exist_ok=True)
            (OUT / p).write_text(svg, encoding='utf-8')
        elif p:
            jobs.append((SITE + '/wp-content/uploads/' + p.removeprefix('media/'), OUT / p))
            if re.search(r'-e\d{13}(?=\.\w+$)', p):  # immagine modificata in WP: tieni anche il file caricato
                p = re.sub(r'-e\d{13}(?=\.\w+$)', '', p)
                jobs.append((SITE + '/wp-content/uploads/' + p.removeprefix('media/'), OUT / p))
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(download, jobs))
    problems += [f'download fallito ({code}): {d.relative_to(OUT)}' for d, st, code in results if st == 'error']

    media_index = [{
        'id': x['id'],
        'file': media_path(x),
        'url': html.unescape(x['source_url']) if x['mime_type'] == 'oembed/youtube' else None,
        'mime': x['mime_type'],
        'title': text(x['title']['rendered']),
        'alt': x['alt_text'],
        'caption': text(x['caption']['rendered']),
        'description': text(x['description']['rendered']) if not x['mime_type'].startswith('oembed') else '',
        'date': x['date'],
        'attached_to': by_id[x['post']]['slug'] if x['post'] in by_id else x['post'],
        'width': (x.get('media_details') or {}).get('width'),
        'height': (x.get('media_details') or {}).get('height'),
        'original_url': html.unescape(x['source_url']),
    } for x in raw['media']]
    (OUT / 'media.json').write_text(json.dumps(media_index, ensure_ascii=False, indent=2), encoding='utf-8')

    lectures = []
    for p in raw['posts']:
        cat_names = [cats[c] for c in p['categories'] if c in cats]
        year = next((c for c in cat_names if c.isdigit()), p['date'][:4])
        content, when, where = event_info(p['content']['rendered'], year)
        meta = {}
        body = render(content, '../../', M, meta)
        fm = M.get(p['featured_media'])
        front = {
            'title': text(p['title']['rendered']), 'slug': p['slug'], 'year': int(year),
            'cancelled': year in CANCELLED or None, 'categories': cat_names, 'tags': sorted((tags[t] for t in p['tags'] if t in tags), key=str.lower),  # l'API non ha un ordine stabile
            'when': when, 'where': where, 'excerpt': text(p['excerpt']['rendered']),
            'published': p['date'], 'modified': p['modified'], 'url': p['link'], 'wp_id': p['id'],
            'cover': '../../' + media_path(fm) if fm and media_path(fm) else None,
            'background': meta.get('background'), 'video': meta.get('video'), 'gallery': meta.get('gallery'),
        }
        path = OUT / 'lectures' / year / f'{p["slug"]}.md'
        write_md(path, front, f'# {front["title"]}\n\n{body}')
        lectures.append((front, path))

    for kind, folder in (('pages', 'pages'), ('uncodeblock', 'blocks')):
        for p in raw[kind]:
            meta = {}
            body = render(p['content']['rendered'], '../', M, meta)
            fm = M.get(p.get('featured_media'))
            front = {
                'title': text(p['title']['rendered']), 'slug': p['slug'], 'published': p['date'],
                'modified': p['modified'], 'url': p['link'], 'wp_id': p['id'],
                'cover': '../' + media_path(fm) if fm and media_path(fm) else None,
                'gallery': meta.get('gallery'),
            }
            write_md(OUT / folder / f'{p["slug"]}.md', front, f'# {front["title"]}\n\n{body}')

    # immagini usate dal sito ma fuori dalla media library (slider, opzioni del tema)
    have = {str(d.relative_to(OUT)) for _, d in jobs}
    pages_html = [get(u)[0].decode('utf-8', 'replace') for u in {p['link'] for p in raw['posts'] + raw['pages']}]
    extra = set()
    for h in pages_html:
        for u in re.findall(r'wp-content/uploads/([^"\'\s)?]+\.(?:jpe?g|png|gif|svg|webp|mp4|pdf))', h, re.I):
            u = urllib.parse.unquote(html.unescape(u))
            base = re.sub(r'-scaled(?=\.\w+$)', '', re.sub(r'(-uai)?-\d+x\d+(?=\.\w+$)', '', u))
            if 'media/' + base not in have and 'media/' + u not in have:
                extra.add(base)
    extra_res = list(ThreadPoolExecutor(8).map(download, [(SITE + '/wp-content/uploads/' + u, OUT / 'media' / u) for u in sorted(extra)]))
    problems += [f'extra non scaricabile ({c}): {d.relative_to(OUT)}' for d, st, c in extra_res if st == 'error']
    extras_ok = [str(d.relative_to(OUT)) for d, st, _ in extra_res if st != 'error']

    # README con indice
    lines = [f'# {raw["site"]["name"]} — backup', '',
             f'{raw["site"]["description"]}', '',
             f'Backup di {SITE} fatto il {date.today().isoformat()} dalla REST API di WordPress (tema Uncode + WPBakery).',
             'Rigenerabile con `python3 -I export.py`.', '',
             '## Struttura', '',
             '- `lectures/<anno>/<slug>.md`: una conferenza per file. Frontmatter: anno (= categoria WP), `cancelled` '
             '(edizione 2020, rimandata e poi annullata per il COVID-19), tag, `when`/`where` '
             '(data e luogo dal box laterale), `excerpt`, date di pubblicazione/modifica, `cover` (immagine in evidenza), '
             '`background` (sfondo della testata), `gallery`, `video` (YouTube).',
             '- `pages/`: le pagine (la home è `gl2k19.md`; la pagina Venue era vuota, il suo contenuto sta in `blocks/venue.md`).',
             '- `blocks/`: blocchi Uncode riusati nel layout (footer con le descrizioni delle edizioni, testata home, venue…).',
             '  Dove il sito aveva una versione desktop e una mobile dello stesso blocco è tenuta solo quella desktop.',
             '- `media/AAAA/MM/`: tutti gli originali della media library (stessi percorsi di `wp-content/uploads`, '
             'senza le miniature generate da WordPress). `media/svg/`: loghi che il tema salvava come SVG inline.',
             '- `media.json`: metadati di ogni media (titolo, alt, didascalia, data, contenuto a cui è collegato, dimensioni).',
             '- `raw/`: risposte grezze dell\'API (contenuti originali con gli shortcode), come rete di sicurezza.', '',
             '## Licenza', '',
             'Testi (team di Genesis Lectures) e grafiche (Fabio Santaniello Bruun) sono CC BY-NC 4.0: ripubblicabili '
             'citando la fonte, non per scopi commerciali.Le immagini dei progetti restano © degli studi e dei fotografi, `export.py` è MIT. '
             'Dettagli in [LICENSE.md](LICENSE.md).', '',
             '## Conferenze', '']
    for y in sorted({f['year'] for f, _ in lectures}, reverse=True):
        lines.append(f'### {y}' + (' — edizione annullata (COVID-19)' if str(y) in CANCELLED else '') + '\n')
        for f, path in sorted((l for l in lectures if l[0]['year'] == y), key=lambda l: l[0]['published']):
            info = ' — '.join(s for s in (f['when'] or f['excerpt'], f['where']) if s)
            lines.append(f'- [{f["title"]}]({path.relative_to(OUT)})' + (f' — {info}' if info else ''))
        lines.append('')
    if extras_ok:
        lines += ['## Immagini fuori dalla media library', '', 'Usate nel sito (slider, opzioni del tema) ma non registrate come media:', '']
        lines += [f'- `{e}`' for e in extras_ok] + ['']
    if problems:
        lines += ['## Problemi', ''] + [f'- {p}' for p in problems] + ['']
    (OUT / 'README.md').write_text('\n'.join(lines), encoding='utf-8')

    n_ok = sum(st == 'ok' for _, st, _ in results)
    print(f'post {len(raw["posts"])}, pagine {len(raw["pages"])}, blocchi {len(raw["uncodeblock"])}, '
          f'media {len(raw["media"])} (scaricati ora {n_ok}, già presenti {sum(st == "skip" for _, st, _ in results)}), '
          f'extra {len(extras_ok)}')
    for p in problems:
        print('!', p)


if __name__ == '__main__':
    main()
