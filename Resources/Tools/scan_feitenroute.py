#!/usr/bin/env python3
"""Eén onderdeel door de feitenroute: samenvoegen, uitsnijden op feiten, rechtop,
beslissing van de gebruiker toepassen, naam geven.

Uitkomst per onderdeel: GOED, of TWIJFEL met de reden en de keuzes. Bij TWIJFEL gokt
Sleeve niet; de gebruiker kiest, en die keuze wordt per onderdeel onthouden
(.sleeve-beslissingen.json in de map met de scans) en de volgende keer toegepast.

Gebruik (vanuit studio_bridge.py):
  scan_feitenroute.py --part sidea --discogs <link> --out <map> --work <tijdelijke map> scan1 scan2 ...
  [--decision '{"crop":"square","rotate":90}']
Schrijft op stdout één JSON-regel met de uitkomst.
"""
import argparse, json, os, re, subprocess, sys, tempfile
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = sys.executable
DECISIONS = '.sleeve-beslissingen.json'
ROTATE = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def key_for(scans):
    """Een onderdeel herken je aan zijn scans (namen, gesorteerd)."""
    return '|'.join(sorted(os.path.basename(s) for s in scans))


def load_decisions(folder):
    try:
        return json.load(open(os.path.join(folder, DECISIONS)))
    except (OSError, ValueError):
        return {}


def save_decision(folder, scans, part, decision):
    data = load_decisions(folder)
    data[key_for(scans)] = {'part': part, 'decision': decision}
    try:
        json.dump(data, open(os.path.join(folder, DECISIONS), 'w'), indent=1, ensure_ascii=False)
    except OSError:
        pass                                               # alleen-lezen map: dan niet onthouden


def release_words(discogs):
    """Bekende tekst van de release: artiest, titel, tracks, labels (feit voor rechtop)."""
    import scan_naam as N
    m = re.search(r'/(release|master)/(\d+)', discogs or '')
    if not m:
        return []
    r = N.get(f'https://api.discogs.com/{"masters" if m[1] == "master" else "releases"}/{m[2]}')
    if m[1] == 'master':
        r = N.get(f'https://api.discogs.com/releases/{r["main_release"]}')
    return ([a['name'] for a in r.get('artists', [])] + [r.get('title', '')] +
            [t['title'] for t in r.get('tracklist', []) if t.get('title')] + [l['name'] for l in r.get('labels', [])])


def release_format(discogs):
    """Feit (Discogs): cd of vinyl."""
    import scan_naam as N
    m = re.search(r'/(release|master)/(\d+)', discogs or '')
    if not m:
        return None
    r = N.get(f'https://api.discogs.com/{"masters" if m[1] == "master" else "releases"}/{m[2]}')
    if m[1] == 'master':
        r = N.get(f'https://api.discogs.com/releases/{r["main_release"]}')
    names = {(f.get('name') or '').lower() for f in r.get('formats', [])}
    return 'cd' if names & {'cd', 'cdr'} else ('vinyl' if 'vinyl' in names else None)


def scan_resolution(path, release_dpi=0.0):
    """Feit: de resolutie uit het bestand (EXIF/JFIF, zie scan_dpi); staat die er niet
    betrouwbaar in, dan die van de andere scans van deze release (zelfde scanner)."""
    import scan_dpi
    return scan_dpi.read(path) or (release_dpi if release_dpi and 50 < release_dpi < 5000 else 0.0)


def already_cut(path, spec, release_dpi=0.0):
    """Is dit beeld al uitgesneden? Het zichtbare deel (niet-transparant) heeft dan al de
    maat die de feiten voor dit onderdeel geven. Geeft (beeld, notitie) of None."""
    dpi = scan_resolution(path, release_dpi)
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cut_out = False
    if img.shape[2] == 4:
        ys, xs = np.nonzero(img[:, :, 3] > 0)
        if not len(xs):
            return None
        cut_out = (img[:, :, 3] == 0).any()                # transparant eromheen: al uitgesneden
        img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    inferred = False
    if not dpi and cut_out:
        # Geen resolutie in het bestand, maar wel al uitgesneden: de bekende maat van het
        # onderdeel (feit) geeft de resolutie, als de verhouding past.
        h_px, w_px = img.shape[:2]
        if spec[0] == 'disc':
            if abs(w_px - h_px) <= .015 * w_px:
                dpi = w_px / (sum(spec[1]) / 2 / 25.4); inferred = True
        else:
            (wl, wh), (hl, hh) = spec[1], spec[2]
            for W_, H_ in ((w_px, h_px), (h_px, w_px)):
                lo_d = max(W_ / (wh / 25.4), H_ / (hh / 25.4)); hi_d = min(W_ / (wl / 25.4), H_ / (hl / 25.4))
                if lo_d <= hi_d:
                    dpi = (lo_d + hi_d) / 2; inferred = True; break
    if not dpi:
        return None
    w_mm, h_mm = img.shape[1] / dpi * 25.4, img.shape[0] / dpi * 25.4
    if spec[0] == 'disc':
        ok = spec[1][0] - 1 <= w_mm <= spec[1][1] + 1 and abs(w_mm - h_mm) < 1.5
    else:
        (wl, wh), (hl, hh) = spec[1], spec[2]
        ok = (wl <= w_mm <= wh and hl <= h_mm <= hh) or (wl <= h_mm <= wh and hl <= w_mm <= hh)
    return (img, {'mm': [round(w_mm, 1), round(h_mm, 1)], 'dpi': dpi, 'dpi_from_size': inferred}) if ok else None


def choices_for(why):
    """Welke keuzes horen bij een twijfel."""
    out = ['keep']
    for w in why:
        if w.startswith('not square'):
            out.append('square')
    return out


def square_up(img, sides):
    """Beslissing 'vierkant': de zijde met het zwakste randbewijs schuift in."""
    h, w = img.shape[:2]; k = abs(h - w)
    long_sides = ('top', 'bottom') if h > w else ('left', 'right')
    weak = min(long_sides, key=lambda s: sides[s]['cover'])
    sl = {'top': (slice(k, None), slice(None)), 'bottom': (slice(0, h - k), slice(None)),
          'left': (slice(None), slice(k, None)), 'right': (slice(None), slice(0, w - k))}[weak]
    return img[sl], weak


def side_on_label(img, dpi):
    """Kantletter zoals op het label gedrukt (SIDE A / SIDE ONE ...), of None."""
    h, w = img.shape[:2]; r = int(52 / 25.4 * dpi)
    lab = img[max(0, h // 2 - r):h // 2 + r, max(0, w // 2 - r):w // 2 + r, :3]
    s = 1600 / max(lab.shape[:2])
    if s < 1:
        lab = cv2.resize(lab, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'l.png'); cv2.imwrite(p, lab)
        out = ''
        for attempt in range(4):                           # Vision geeft soms niets terug: opnieuw
            out = subprocess.run([os.path.join(HERE, 'sleeve_ocr'), p, '--boxes'], capture_output=True, text=True, timeout=120).stdout
            if out.strip():
                break
            import time; time.sleep(0.3 * (attempt + 1))
    words = {'one': 'a', 'two': 'b', 'three': 'c', 'four': 'd'}
    for line in out.splitlines():
        m = re.search(r'\bside\s*([abcd]|one|two|three|four)\b', line.split('\t')[1] if '\t' in line else line, re.I)
        if m:
            v = m[1].lower(); return words.get(v, v)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('scans', nargs='+'); p.add_argument('--part', required=True)
    p.add_argument('--discogs', default=''); p.add_argument('--out', required=True); p.add_argument('--work', required=True)
    p.add_argument('--decision', default=''); p.add_argument('--variant', default=''); p.add_argument('--format', default=''); p.add_argument('--release-dpi', type=float, default=0.0)
    a = p.parse_args()
    folder = os.path.dirname(os.path.abspath(a.scans[0]))
    decision = json.loads(a.decision) if a.decision else load_decisions(folder).get(key_for(a.scans), {}).get('decision', {})
    if a.decision:
        save_decision(folder, a.scans, a.part, decision)
    import scan_feiten as SF
    fmt = a.format or (release_format(a.discogs) if a.discogs else None) or ('cd' if a.part.startswith('cd') else 'vinyl')
    feit_part = a.part if a.part in SF.SHAPES[fmt] else ('insert' if a.part.startswith('insert') else 'front')
    result_fmt = fmt
    os.makedirs(a.work, exist_ok=True)
    raw = os.path.join(a.work, f'{a.part}_raw.png'); crop = os.path.join(a.work, f'{a.part}_crop.png')
    up = os.path.join(a.work, f'{a.part}_up.png')
    for f in (raw, raw + '.scans.json', crop, crop + '.feiten.json', up):   # nooit een oud tussenbestand gebruiken
        if os.path.exists(f):
            os.remove(f)
    result = {'part': a.part, 'scans': a.scans, 'verdict': 'GOED', 'why': [], 'choices': [], 'decision': decision}
    already = already_cut(a.scans[0], SF.SHAPES[fmt][feit_part], a.release_dpi) if len(a.scans) == 1 else None
    if already:
        # Feit: dit beeld heeft al precies de maat van dit onderdeel: het is al uitgesneden.
        img0, note = already
        cv2.imwrite(crop, img0)
        json.dump({'verdict': 'GOED', 'why': [], 'dpi': note['dpi'], 'already_cut': note}, open(crop + '.feiten.json', 'w'))
        result['applied'] = f'already cut ({note["mm"][0]} x {note["mm"][1]} mm matches the facts); not cropped again' + (' (no resolution in the file: taken from the known size)' if note.get('dpi_from_size') else '')
        st = subprocess.CompletedProcess([], 0, '', '')
    elif len(a.scans) == 1:
        # één scan: niets samen te voegen; de scan zelf is het hele beeld
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        dpi0 = scan_resolution(a.scans[0], a.release_dpi)
        with Image.open(a.scans[0]) as im:
            w0, h0 = im.size
            im.convert('RGBA').save(raw)
        json.dump({'scale': 1, 'dpi': dpi0 or 300.0, 'scans': [{'scan': os.path.basename(a.scans[0]),
                   'corners': [[0, 0], [w0, 0], [w0, h0], [0, h0]]}]}, open(raw + '.scans.json', 'w'))
        st = subprocess.CompletedProcess([], 0, '', '')
        if not dpi0:
            result['why'].append('the scan has no resolution (dpi) stored; 300 dpi assumed for the size facts')
    else:
        st = subprocess.run([PY, os.path.join(HERE, 'scan_stitch.py'), raw] + a.scans + ['--vorm', 'ruw'], capture_output=True, text=True)
    if not already and st.returncode == 0 and os.path.exists(raw + '.scans.json') and a.release_dpi:
        meta = json.load(open(raw + '.scans.json'))
        if not meta.get('dpi'):                            # samengevoegd zonder betrouwbare resolutie: die van de release
            meta['dpi'] = a.release_dpi; json.dump(meta, open(raw + '.scans.json', 'w'))
    if not already and (st.returncode != 0 or not os.path.exists(raw)):
        result.update(verdict='FOUT', why=[(st.stderr or st.stdout).strip().splitlines()[-1] if (st.stderr or st.stdout).strip() else 'merging failed'])
        print(json.dumps(result)); return
    fe = subprocess.run([PY, os.path.join(HERE, 'scan_feiten.py'), raw, feit_part, '--format', fmt, '--out', crop], capture_output=True, text=True) if not already else subprocess.CompletedProcess([], 0, '', '')
    try:
        facts = json.load(open(crop + '.feiten.json'))
    except (OSError, ValueError):
        result.update(verdict='FOUT', why=[fe.stderr.strip().splitlines()[-1] if fe.stderr.strip() else 'cropping failed'])
        print(json.dumps(result)); return
    if facts.get('verdict') == 'FOUT':
        result.update(verdict='FOUT', why=facts.get('why', ['not found']))
        print(json.dumps(result)); return
    dpi = facts.get('dpi') or 300.0
    why = result['why'] + list(facts.get('why', []))
    if facts.get('message'):
        result['message'] = facts['message']
    img = cv2.imread(crop, cv2.IMREAD_UNCHANGED)
    if why and decision.get('crop') == 'square' and 'sides' in facts:
        img, weak = square_up(img, facts['sides'])
        why = [w for w in why if not w.startswith('not square')]
        result['applied'] = f'square ({weak} side moved in)'
        cv2.imwrite(crop, img)
    # rechtop
    words = release_words(a.discogs) if a.discogs else []
    disc = SF.SHAPES[fmt][feit_part][0] == 'disc'
    if words:
        args = [PY, os.path.join(HERE, 'scan_rechtop.py'), crop, '--words', os.path.join(a.work, 'words.json'), '--out', up]
        json.dump(words, open(os.path.join(a.work, 'words.json'), 'w'))
        if disc:
            args += ['--disc', '--dpi', str(dpi)]
        ro = subprocess.run(args, capture_output=True, text=True)
        try:
            upright = json.loads(ro.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            upright = {'verdict': 'TWIJFEL'}
        result['upright'] = {k: upright.get(k) for k in ('rotate_clockwise', 'verdict', 'read_upright')}
        if os.path.exists(up):
            img = cv2.imread(up, cv2.IMREAD_UNCHANGED)
        if upright.get('verdict') != 'GOED':
            if decision.get('rotate') in ROTATE or decision.get('rotate') == 0:
                base = cv2.imread(crop, cv2.IMREAD_UNCHANGED)
                img = cv2.rotate(base, ROTATE[decision['rotate']]) if decision['rotate'] else base
                result['applied'] = (result.get('applied', '') + f' rotated {decision["rotate"]}').strip()
            elif 'title only' in (upright.get('read_upright') or []):
                why.append('which way is up: the label was set straight on the title only (no tracklist read); a title can be printed at an angle')
            else:
                why.append('which way is up: no known text of the release could be read')
    else:
        why.append('which way is up: no Discogs release, so no known text to read')
    # kant op het label (feit) tegen het vak
    if disc and feit_part.startswith('side'):
        letter = side_on_label(img, dpi)
        result['side_on_label'] = letter
        if letter and a.part.startswith('side') and a.part != 'side' + letter:
            why.append(f'the label says side {letter.upper()}, the slot says {a.part[4:].upper()}')
    if why and decision.get('crop') == 'keep':
        result['applied'] = (result.get('applied', '') + ' kept as it is').strip()
        why = [w for w in why if w.startswith('which way is up') or w.startswith('the label says')]
    if why:
        result['verdict'] = 'TWIJFEL'; result['why'] = why; result['choices'] = choices_for(why)
        if any(w.startswith('which way is up') for w in why):
            result['choices'] += ['rotate90', 'rotate180', 'rotate270']
    # naam
    name = None
    if a.discogs:
        try:
            import scan_naam as N
            name = N.naam(a.discogs, a.part, a.variant)
        except Exception as e:                             # geen verbinding e.d.: neutrale naam
            result['name_note'] = str(e)
    name = name or f'{os.path.splitext(os.path.basename(a.scans[0]))[0]}_{a.part}'
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, name + '.png'); n = 2
    while os.path.exists(path) and not a.decision:
        path = os.path.join(a.out, f'{name}_{n}.png'); n += 1
    cv2.imwrite(path, img)
    try:                                                   # dpi in het bestand zetten
        from PIL import Image
        with Image.open(path) as im:
            im.load(); im.save(path, dpi=(dpi, dpi))
    except Exception:
        pass
    result['path'] = path; result['dpi'] = dpi
    result['size_mm'] = [round(img.shape[1] / dpi * 25.4, 1), round(img.shape[0] / dpi * 25.4, 1)]
    for f in (raw, raw + '.scans.json', crop, crop + '.feiten.json', up):   # tussenbestanden opruimen (1200 dpi: ±1,5 GB)
        if os.path.exists(f):
            os.remove(f)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
