#!/usr/bin/env python3
"""Release-gegevens van Discogs voor het bevestigingsvenster in de app.

Haalt de release op en vat samen wat Sleeve nodig heeft: artiest, titel, jaar, land,
label, catalogusnummer, formaat (cd/vinyl), aantal schijven, kleur, verpakking en de
kanten uit de tracklist. Daaruit volgen de vakken die bij deze uitgave horen.

Verpakking (feit van Discogs, uit de formaatomschrijving en de notities):
  jewel        Jewel Case (gewone cd-doos)
  slimjewel    Slim Jewel Case
  superjewel   Super Jewel Box
  digipak      Digipak / Digipack / Digifile
  cardsleeve   Cardboard / Card / Paper Sleeve (kartonnen hoesje)
  gatefold     Gatefold (uitklaphoes, vinyl)
  sleeve       gewone platenhoes (vinyl, geen uitklap)
  unknown      niet vermeld: de gebruiker kiest
"""
import json, re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import scan_naam as N

PACKAGING = [  # (sleutel, woorden waarop Discogs hem noemt) - volgorde: specifiek eerst
    ('superjewel', ['super jewel']),
    ('slimjewel', ['slim jewel', 'slimline']),
    ('digipak', ['digipak', 'digipack', 'digifile', 'digisleeve']),
    ('cardsleeve', ['cardboard sleeve', 'card sleeve', 'paper sleeve', 'cardsleeve', 'card wallet', 'cardboard wallet']),
    ('jewel', ['jewel case', 'jewelcase', 'jewel box']),
    ('gatefold', ['gatefold']),
]
LABELS = {'jewel': 'Jewel case', 'slimjewel': 'Slim jewel case', 'superjewel': 'Super Jewel Box',
          'digipak': 'Digipak', 'cardsleeve': 'Cardboard sleeve', 'gatefold': 'Gatefold sleeve',
          'sleeve': 'Sleeve', 'unknown': 'Unknown'}


def release_id(url):
    m = re.search(r'/(release|master)/(\d+)', url or '')
    if not m:
        raise ValueError('This is not a Discogs release link.')
    if m[1] == 'master':
        return N.get(f'https://api.discogs.com/masters/{m[2]}')['main_release']
    return int(m[2])


def packaging_of(fmt_names, texts):
    blob = ' '.join(texts).lower()
    for key, words in PACKAGING:
        if any(w in blob for w in words):
            return key
    if 'vinyl' in fmt_names:
        return 'sleeve'
    return 'unknown'


def slots_for(fmt, qty, packaging, sides):
    """Vakken die bij deze uitgave horen (feit: formaat, aantal schijven, verpakking, kanten)."""
    if fmt == 'vinyl':
        out = ['front', 'back']
        if packaging == 'gatefold':
            out.append('inside')
        # feit: elke plaat heeft twee kanten (ook een kant zonder tracks, bv. een etched of picture disc)
        n = max(len(sides), 2 * qty)
        out += ['side' + c for c in 'abcdefghijkl'[:n]]
        return out
    if fmt == 'cd':
        discs = ['cd'] if qty <= 1 else [f'cd{i}' for i in range(1, qty + 1)]
        if packaging in ('jewel', 'superjewel', 'unknown'):
            return ['front', 'back', 'inlay'] + discs + ['insert']
        if packaging == 'slimjewel':
            return ['front', 'back'] + discs
        return ['front', 'back', 'inside'] + discs   # kartonnen hoesje, digipak
    return ['front', 'back']


def info(url):
    rid = release_id(url)
    r = N.get(f'https://api.discogs.com/releases/{rid}')
    formats = r.get('formats') or []
    names = {(f.get('name') or '').lower() for f in formats}
    fmt = 'cd' if names & {'cd', 'cdr'} else ('vinyl' if 'vinyl' in names else (sorted(names)[0] if names else ''))
    qty = sum(int(f.get('qty') or 1) for f in formats if (f.get('name') or '').lower() in ({'cd', 'cdr'} if fmt == 'cd' else {'vinyl'})) or 1
    texts = [d for f in formats for d in (f.get('descriptions') or [])] + [f.get('text') or '' for f in formats] + [r.get('notes') or '']
    packaging = packaging_of(names, texts)
    sides = sorted({(t.get('position') or ' ')[0].lower() for t in r.get('tracklist', []) if (t.get('position') or ' ')[0].isalpha()}) if fmt == 'vinyl' else []
    colour = ''
    try:
        name = N.naam(f'https://www.discogs.com/release/{rid}', 'front')
        colour = next((k for k in N.KLEUREN if f'_{k}_' in name + '_'), '')
    except Exception:
        pass
    images = [im.get('uri150') or im.get('uri') for im in (r.get('images') or [])][:4]
    return {
        'id': rid, 'url': f'https://www.discogs.com/release/{rid}',
        'artist': ', '.join(a.get('name', '') for a in r.get('artists', [])),
        'title': r.get('title', ''), 'year': str(r.get('year') or ''), 'country': r.get('country') or '',
        'label': ', '.join(sorted({l.get('name', '') for l in r.get('labels', [])})),
        'catno': ', '.join(sorted({l.get('catno', '') for l in r.get('labels', []) if l.get('catno')})),
        'format': fmt, 'formatText': ', '.join(f'{f.get("qty", "1")} x {f.get("name", "")}' + (', ' + ', '.join(f.get('descriptions') or []) if f.get('descriptions') else '') + (f' ({f["text"]})' if f.get('text') else '') for f in formats),
        'qty': qty, 'colour': colour, 'packaging': packaging, 'packagingLabel': LABELS[packaging],
        'packagingFromDiscogs': packaging not in ('unknown', 'sleeve') or fmt == 'vinyl',
        'sides': [s.upper() for s in sides], 'slots': slots_for(fmt, qty, packaging, sides), 'images': images,
    }


if __name__ == '__main__':
    print(json.dumps(info(sys.argv[1]), ensure_ascii=False, indent=1))
