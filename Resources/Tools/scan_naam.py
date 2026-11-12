#!/usr/bin/env python3
"""Bestandsnaam volgens het collectieschema uit een Discogs-link.

  python3 scan_naam.py <discogs-link> <kant> [variant]  -> bv. 2016_graduated_fool_vinyl_musiconvinyl_silver_sidea
  variant (optioneel, vóór de kant): bv. remixes, radio, v2 — als twee uitgaven anders dezelfde naam krijgen

Schema: jaar_titel_formaat_label_land[_variant]_kant
  - jaar = jaar van deze uitgave, land voluit (usa mag); vinyl krijgt geen land
  - variant = kleur van het vinyl (uit de formaatomschrijving), of promo
"""
import json, re, sys, unicodedata, urllib.request

UA = 'Sleeve/0.3.1'
LANDEN = {'US': 'usa', 'USA': 'usa', 'UK': 'uk', 'Europe': 'europe', 'Netherlands': 'netherlands',
          'Germany': 'germany', 'Belgium': 'belgium', 'France': 'france', 'Japan': 'japan'}
KLEUREN = ['black', 'white', 'red', 'orange', 'yellow', 'gold', 'silver', 'green', 'blue', 'pink', 'purple',
           'magenta', 'clear', 'transparent', 'grey', 'gray', 'brown', 'turquoise', 'cream', 'marbled', 'splatter']


def slug(t):
    t = t or ''                                       # Discogs geeft soms null (bv. geen land)
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode().lower()
    t = re.sub(r"['’]", '', t)
    return re.sub(r'[^a-z0-9]+', '_', t).strip('_')


def get(url):
    return json.loads(fetch(url))


def fetch(url):
    """Ophalen via scan_net: één keer per adres, onthouden, opnieuw proberen bij 'te veel aanvragen'."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import scan_net
    return scan_net.fetch(url)


def naam(url, kant, extra='', year=''):
    m = re.search(r'/release/(\d+)', url)
    if not m:
        mm = re.search(r'/master/(\d+)', url)
        if not mm:
            sys.exit('no Discogs release in the link')
        rid = get(f'https://api.discogs.com/masters/{mm.group(1)}')['main_release']
    else:
        rid = m.group(1)
    r = get(f'https://api.discogs.com/releases/{rid}')
    formats = {(item.get('name') or '').lower() for item in r.get('formats',[])}
    if kant.startswith('cd') and 'vinyl' in formats and not formats.intersection({'cd','cdr'}):
        raise ValueError('This Discogs link is for vinyl, but the scan is a CD. Use the link of the CD release.')
    if kant.startswith('side') and formats.intersection({'cd','cdr'}) and 'vinyl' not in formats:
        raise ValueError('This Discogs link is for a CD, but the scan is vinyl. Use the link of the vinyl release.')
    jaar = str(year).strip() if str(year or '').strip().isdigit() else str(r.get('year') or (r.get('released') or '0000')[:4])   # jaartal kan de gebruiker verbeteren
    titel = slug(r.get('title'))
    fm = (r.get('formats') or [{}])[0]
    fname = (fm.get('name') or '').lower()
    desc = [(d or '').lower() for d in (fm.get('descriptions') or [])] + [w.lower() for w in re.split(r'[\s,/]+', fm.get('text') or '')]
    if fname == 'vinyl':
        formaat = 'vinyl'
    elif fname in ('cd', 'cdr'):
        formaat = 'cdsingle' if 'single' in desc else ('maxicd' if 'maxi-single' in desc else 'cd')
    else:
        formaat = slug(fname) or 'unknown'
    labels = [slug((l.get('name') or '').split('(')[0]).replace('_', '') for l in (r.get('labels') or [])]
    voorkeur = ['musiconvinyl', 'goldilox', 'dino', 'emi', 'bmg', 'sony', 'columbia']   # labels uit het schema
    label = next((v for v in voorkeur if any(v in l for l in labels)), labels[0] if labels else '')
    if label.startswith('universal') and jaar.isdigit() and int(jaar) >= 2009 and any((a.get('name') or '').split('(')[0].strip().casefold()=='anouk' for a in r.get('artists',[])):
        label = 'goldilox'                              # Anouk bij Universal = eigen label Goldilox
    land = '' if formaat == 'vinyl' else (LANDEN.get(r.get('country') or '', slug(r.get('country'))) or 'netherlands')   # leeg = netherlands
    kleur = next((k for k in KLEUREN if k in desc), '')
    if formaat == 'vinyl' and not kleur:
        kleur = 'black'
    promo = 'promo' in desc
    if promo and formaat in ('cd', 'cdsingle', 'maxicd', 'cdr'):
        formaat, promo = 'promocd', False               # zoals in de bestaande namen
    variant = '_'.join(x for x in [kleur, 'promo' if promo else ''] if x)
    delen = [jaar, titel, formaat, label, land, variant, slug(extra), kant]
    return '_'.join(x for x in delen if x)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    print(naam(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''))
