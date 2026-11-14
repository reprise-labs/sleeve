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
import argparse, json, math, os, re, subprocess, sys, tempfile
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = sys.executable
DECISIONS = '.sleeve-beslissingen.json'
ROTATE = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def step(text):
    """Wat er nu gebeurt, voor de voortgang in de app (via de bridge)."""
    print('SLEEVE_STEP ' + text, file=sys.stderr, flush=True)


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


def release_data(discogs):
    """De release van Discogs (via scan_net: één keer opgehaald, daarna uit het geheugen), of None
    zonder link. Lukt het ophalen niet, dan komt de fout omhoog; de aanroeper meldt hem."""
    import scan_naam as N
    m = re.search(r'/(release|master)/(\d+)', discogs or '')
    if not m:
        return None
    r = N.get(f'https://api.discogs.com/{"masters" if m[1] == "master" else "releases"}/{m[2]}')
    if m[1] == 'master':
        r = N.get(f'https://api.discogs.com/releases/{r["main_release"]}')
    return r


def release_words(discogs):
    """Bekende tekst van de release: artiest, titel, tracks, labels (feit voor rechtop)."""
    r = release_data(discogs)
    if not r:
        return []
    return ([a['name'] for a in r.get('artists', [])] + [r.get('title', '')] +
            [t['title'] for t in r.get('tracklist', []) if t.get('title')] + [l['name'] for l in r.get('labels', [])])


def release_format(discogs):
    """Feit (Discogs): cd of vinyl."""
    r = release_data(discogs)
    if not r:
        return None
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
    return (img, {'mm': [round(w_mm, 1), round(h_mm, 1)], 'dpi': dpi, 'dpi_from_size': inferred, 'transparent': bool(cut_out)}) if ok else None


def discogs_orientation(img, discogs, disc=False):
    """Feit: de Discogs-foto's van deze release laten zien hoe het onderdeel staat.
    Overeenkomende punten (SIFT, draaiingsvrij) tussen ons beeld en elke foto; de
    draaiing van de best passende foto is de stand. Hoes: op een kwartslag afgerond.
    Geeft (graden met de klok mee, aantal punten) of None als niets duidelijk past."""
    import scan_discogs as SD
    try:
        _, photos = SD.release_images(discogs)
    except Exception:
        return None
    if not photos:
        return None
    base = img[:, :, :3] if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.ndim == 3 and img.shape[2] == 4:
        a_ = img[:, :, 3:4] / 255.0
        base = (img[:, :, :3] * a_ + 255 * (1 - a_)).astype(np.uint8)
    k = 1200 / max(base.shape[:2])
    small = cv2.resize(base, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else base
    found = SD.matches(small, photos)
    if not found:
        return None
    inliers, _, M = found[0]
    if inliers < 40 or (len(found) > 1 and found[1][0] > .8 * inliers and abs(
            math.degrees(math.atan2(found[1][2][1, 0], found[1][2][0, 0])) - math.degrees(math.atan2(M[1, 0], M[0, 0]))) > 10):
        return None                                        # te weinig, of twee foto's die het oneens zijn
    ang = math.degrees(math.atan2(M[1, 0], M[0, 0]))       # draaiing ons -> foto (beeldcoördinaten: met de klok mee)
    ang = ang % 360
    if not disc:
        q = round(ang / 90) * 90 % 360
        if abs(((ang - q + 180) % 360) - 180) > 12:
            return None                                    # hoes ligt niet op een kwartslag: niet vertrouwen
        ang = q
    return ang, inliers


def choices_for(why):
    """Welke keuzes horen bij een twijfel."""
    out = ['keep']
    for w in why:
        if w.startswith('not square'):
            out.append('square')
    return out


def backing_mask(L, lab, pm):
    """Feit: buiten het onderdeel ligt de klep of het vel dat erachter gelegd is: effen, en te zien
    langs de rand van de scan. Geeft de pixels met die kleur, of None als de rand van de scan niet
    effen is (dan loopt het onderdeel zelf tot de rand). L in 0-100, lab zoals OpenCV het geeft."""
    b = max(2, int(1.5 * pm))
    q = np.dstack([L, lab[:, :, 1] - 128, lab[:, :, 2] - 128])
    strip = np.concatenate([q[:b].reshape(-1, 3), q[-b:].reshape(-1, 3), q[:, :b].reshape(-1, 3), q[:, -b:].reshape(-1, 3)])
    med = np.median(strip, 0)
    if (np.linalg.norm(strip - med, axis=1) < 12).mean() < .7:
        return None
    return np.linalg.norm(q - med, axis=2) < 12, med


def print_outside(raw, facts):
    """Ligt er tussen de gevonden snede en de beeldrand (aan minstens één zijde, strook van
    minstens 0,3 mm) duidelijk drukwerk in plaats van effen lichte deksel?"""
    im = cv2.imread(raw, cv2.IMREAD_UNCHANGED)
    if im is None:
        return False
    dpi = facts.get('dpi') or 300.0
    k = min(1.0, 300.0 / dpi); pm = dpi * k / 25.4
    im = cv2.resize(im[:, :, :3], None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else im[:, :, :3]
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[:, :, 0] * 100 / 255; C = np.hypot(lab[:, :, 1] - 128, lab[:, :, 2] - 128)
    lid = (L > 85) & (C < 10)
    back = backing_mask(L, lab, pm)                        # ook een donker of gekleurd vel achter het onderdeel is geen drukwerk
    if back is not None:
        lid |= back[0]
    x, y, w, h = (facts.get('precise_mm') or facts.get('box_mm'))[:4]
    H, W = lid.shape; m = int(.3 * pm)
    x0, y0, x1, y1 = int(x * pm), int(y * pm), int((x + w) * pm), int((y + h) * pm)
    bands = [lid[y0:y1, :max(0, x0 - 1)], lid[y0:y1, min(W, x1 + 1):], lid[:max(0, y0 - 1), x0:x1], lid[min(H, y1 + 1):, x0:x1]]
    for b in bands:
        if b.size and min(b.shape) >= m and (~b).mean() > .5:
            return True
    return False


def colour_extent(raw, dpi, cut, fmt, part):
    """Feit: alles wat gekleurd is, hoort bij het kaartje; het kaartje is nooit kleiner dan zijn
    gekleurde vlak. Steekt het gekleurde vlak duidelijk (>= 2 mm) buiten de gevonden snede en past
    het zelf op een maat van deze verpakking, dan is de snede een drukrand: snij op het gekleurde
    vlak. (Places To Go: geel kader tot vlak bij de beeldrand, oranje vlak erbinnen.)
    Wit kaartje op witte deksel: alleen de bedrukking is gekleurd en die ligt binnen de snede."""
    import scan_feiten as SF
    full = cv2.imread(raw, cv2.IMREAD_UNCHANGED)
    if full is None:
        return None
    if full.ndim == 2:
        full = cv2.cvtColor(full, cv2.COLOR_GRAY2BGR)
    bgr = full[:, :, :3]
    k = min(1.0, 300.0 / dpi)
    small = cv2.resize(bgr, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else bgr
    pm = dpi * k / 25.4
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[:, :, 0] * 100 / 255; C = np.hypot(lab[:, :, 1] - 128, lab[:, :, 2] - 128)
    mask = (C > 18) | (L < 60)                                      # duidelijk gekleurd of donker
    back = backing_mask(L, lab, pm)
    if back is not None and back[1][0] < 45 and np.hypot(back[1][1], back[1][2]) < 15:
        mask &= ~back[0]                                            # feit: een donker vel achter het onderdeel is geen kaartje
    mask = mask.astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((max(3, int(pm)),) * 2, np.uint8))
    n, lab_, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n < 2:
        return None
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    pts = cv2.findNonZero((lab_ == big).astype(np.uint8))
    (cx, cy), (rw, rh), ang = cv2.minAreaRect(pts)
    if ang > 45:
        ang -= 90; rw, rh = rh, rw
    wm, hm = rw / pm, rh / pm
    cw, ch = cut.shape[1] / dpi * 25.4, cut.shape[0] / dpi * 25.4
    if not (min(wm, hm) >= min(cw, ch) + 2 and max(wm, hm) >= max(cw, ch) + 2):
        return None
    for f in [fmt] + [x for x in ('cd', 'cd-slimjewel', 'cd-cardsleeve', 'cd-digipak') if x != fmt]:
        spec = SF.SHAPES[f].get(part)
        if spec and spec[0] == 'rect':
            (wl, wh), (hl, hh) = spec[1], spec[2]
            if (wl - 1 <= wm <= wh + 1 and hl - 1 <= hm <= hh + 1) or (wl - 1 <= hm <= wh + 1 and hl - 1 <= wm <= hh + 1):
                break
    else:
        return None
    s = 1 / k                                                        # terug naar volle resolutie
    R = cv2.getRotationMatrix2D((cx * s, cy * s), ang, 1.0)
    W, H = int(round(rw * s)), int(round(rh * s))
    R[0, 2] += W / 2 - cx * s; R[1, 2] += H / 2 - cy * s
    out = cv2.warpAffine(full, R, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return out, (wm, hm)


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
    # zelfde veilige tekstherkenning als bij rechtop zetten (nauwkeurig hooguit 8 s, anders snel;
    # vroeger 4 x 120 s wachten, en bij hangen viel de hele kant om: 'maar 1 LP gedaan')
    import scan_rechtop as R
    try:
        out = '\n'.join(l['text'] for l in R.ocr_lines(lab))
    except Exception:
        out = ''
    return side_letter(out)


SIDE_WORDS = {'one': 'a', 'two': 'b', 'three': 'c', 'four': 'd', '1': 'a', '2': 'b', '3': 'c', '4': 'd'}
SIDE_PATTERNS = (r'\b(?:side|kant|seite)\s*([abcd]|one|two|three|four|[1-4])\b',   # SIDE A, Side One, Side 1, Kant A, Seite 2
                 r'\b([abcd])-side\b')                                               # A-Side


def side_letter(text):
    """De kant zoals hij op een label gedrukt staat (a-d), of None. Alleen schrijfwijzen die echt
    een kant aanwijzen; een losse letter of een woord uit een titel telt niet."""
    for line in text.splitlines():
        for pattern in SIDE_PATTERNS:
            m = re.search(pattern, line, re.I)
            if m:
                v = m[1].lower(); return SIDE_WORDS.get(v, v)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('scans', nargs='+'); p.add_argument('--part', required=True)
    p.add_argument('--discogs', default=''); p.add_argument('--out', required=True); p.add_argument('--work', required=True)
    p.add_argument('--decision', default=''); p.add_argument('--variant', default=''); p.add_argument('--format', default=''); p.add_argument('--release-dpi', type=float, default=0.0); p.add_argument('--year', default='')
    a = p.parse_args()
    folder = os.path.dirname(os.path.abspath(a.scans[0]))
    decision = json.loads(a.decision) if a.decision else load_decisions(folder).get(key_for(a.scans), {}).get('decision', {})
    if a.decision:
        save_decision(folder, a.scans, a.part, decision)
    import scan_feiten as SF
    fmt_note = None
    fmt = a.format
    if not fmt and a.discogs:
        try:
            fmt = release_format(a.discogs)
        except Exception as e:                             # Discogs niet bereikbaar: het vak bepaalt het formaat, met een melding
            fmt_note = f'the format (cd or vinyl) could not be read from Discogs ({e}); taken from the slot'
    fmt = fmt or ('cd' if a.part.startswith('cd') else 'vinyl')
    feit_part = a.part if a.part in SF.SHAPES[fmt] else ('insert' if a.part.startswith('insert') else 'front')
    result_fmt = fmt
    os.makedirs(a.work, exist_ok=True)
    raw = os.path.join(a.work, f'{a.part}_raw.png'); crop = os.path.join(a.work, f'{a.part}_crop.png')
    up = os.path.join(a.work, f'{a.part}_up.png')
    for f in (raw, raw + '.scans.json', crop, crop + '.feiten.json', up):   # nooit een oud tussenbestand gebruiken
        if os.path.exists(f):
            os.remove(f)
    result = {'part': a.part, 'scans': a.scans, 'verdict': 'GOED', 'why': [fmt_note] if fmt_note else [], 'choices': [], 'decision': decision}
    already = already_cut(a.scans[0], SF.SHAPES[fmt][feit_part], a.release_dpi) if len(a.scans) == 1 else None
    # Feit: alleen transparantie rondom bewijst dat een beeld al uitgesneden is. Een gewone scan
    # met de juiste buitenmaat kan nog deksel rondom hebben (wit hoesje op witte deksel, scheef
    # gelegd): eerst echt randen zoeken; vindt dat niets, dan pas 'al uitgesneden'.
    opaque_fallback = None
    if already and not already[1].get('transparent'):
        opaque_fallback, already = already, None
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
        scans_in = a.scans
        import scan_dpi
        d0 = scan_resolution(a.scans[0], a.release_dpi)
        from PIL import Image as _PI
        _PI.MAX_IMAGE_PIXELS = None
        total_px = 0
        for f in a.scans:
            with _PI.open(f) as im_:
                total_px += im_.size[0] * im_.size[1]
        if total_px > 700e6:                               # samen meer dan ±700 Mpx (bv. uitklap, 6 x 1200 dpi): past niet in het geheugen
            # veel scans op 1200 dpi (uitklap): samen te groot voor het geheugen. Rekenen op
            # kopieën van 600 dpi; het eindbeeld wordt dan 600 dpi (melding in het resultaat).
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            scans_in = []
            for i, f in enumerate(a.scans):
                q = os.path.join(a.work, f'half_{i}_' + os.path.splitext(os.path.basename(f))[0] + '.png')
                with Image.open(f) as im:
                    im.reduce(2).save(q, dpi=(d0 / 2, d0 / 2))
                scans_in.append(q)
            result['why_note'] = f'{len(a.scans)} scans ({total_px / 1e6:.0f} Mpx) do not fit in memory together; made at {d0 / 2:.0f} dpi'
        step(f'merging {len(scans_in)} scans')
        is_disc = SF.SHAPES.get(fmt, SF.SHAPES['vinyl']).get(feit_part, ('rect',))[0] == 'disc'
        st = subprocess.run([PY, os.path.join(HERE, 'scan_stitch.py'), raw] + scans_in + ['--vorm', 'ruw'] + (['--plaat-onderdeel'] if is_disc else []), capture_output=True, text=True)
        for q in scans_in:
            if q not in a.scans and os.path.exists(q):
                os.remove(q)
    # Wat het samenvoegen over losse deelscans meldt, hoort de gebruiker te weten (nooit stil weglaten).
    for line in (st.stdout or '').splitlines():
        if line.startswith('NOTE: left out'):
            name = line.rsplit(': ', 1)[-1]
            result['why'].append(f'{name} was left out: it shares no print with the other scans and its paper edges are not visible. '
                                 'Scan that corner with a contrasting sheet behind it.')
        elif line.startswith('NOTE: placed on its paper edges') or line.startswith('NOTE: aligned on faint print'):
            result['applied'] = (result.get('applied', '') + ' ' + line[6:]).strip()
    if not already and st.returncode == 0 and os.path.exists(raw + '.scans.json') and a.release_dpi:
        meta = json.load(open(raw + '.scans.json'))
        if not meta.get('dpi'):                            # samengevoegd zonder betrouwbare resolutie: die van de release
            meta['dpi'] = a.release_dpi; json.dump(meta, open(raw + '.scans.json', 'w'))
    if not already and (st.returncode != 0 or not os.path.exists(raw)):
        result.update(verdict='FOUT', why=[(st.stderr or st.stdout).strip().splitlines()[-1] if (st.stderr or st.stdout).strip() else 'merging failed'])
        print(json.dumps(result)); return
    if not already:
        step('finding the edges and cutting out')
    fe = subprocess.run([PY, os.path.join(HERE, 'scan_feiten.py'), raw, feit_part, '--format', fmt, '--out', crop], capture_output=True, text=True) if not already else subprocess.CompletedProcess([], 0, '', '')
    try:
        facts = json.load(open(crop + '.feiten.json'))
    except (OSError, ValueError):
        facts = None
    # Feit: een cd-onderdeel heeft de maat van zijn verpakking. Past het niet bij de jewel case
    # (bv. de 'back' is een vierkant kaartje zonder zijflappen, zoals bij een promo), dan bepaalt
    # de gemeten vorm welke verpakking het is: slim jewel (kaartje ±121), kartonnen hoesje (±127),
    # digipak. En: de echte rand is de buitenste. Een drukrand binnen een groter kaartje (Places
    # To Go: geel kader om een oranje vlak) kan toevallig op de jewel-maat passen; vindt een andere
    # cd-maat een rand die er duidelijk omheen ligt, dan is dat de echte rand.
    def box_of(f):
        b = (f or {}).get('precise_mm') or (f or {}).get('box_mm')
        return (b[2], b[3]) if b and len(b) >= 4 else None
    if not already and fmt == 'cd' and SF.SHAPES['cd'][feit_part][0] == 'rect':
        first = box_of(facts) if facts and facts.get('verdict') != 'FOUT' else None
        # vierkante delen zoeken al zelf tot 131 mm (buitenste rand); alleen als niets gevonden is
        # de andere maten proberen. Niet-vierkante delen (achterkaart 150 mm) wel altijd vergelijken.
        if first and SF.SHAPES['cd'][feit_part][3]:
            first = 'keep'
        if first and first != 'keep':
            os.replace(crop, crop + '.jewel.png'); os.replace(crop + '.feiten.json', crop + '.jewel.json')
        chosen = None
        for alt in ([] if first == 'keep' else ('cd-slimjewel', 'cd-cardsleeve', 'cd-digipak')):
            if feit_part not in SF.SHAPES[alt] or SF.SHAPES[alt][feit_part] == SF.SHAPES['cd'].get(feit_part):
                continue
            step('measuring against other CD packagings')
            subprocess.run([PY, os.path.join(HERE, 'scan_feiten.py'), raw, feit_part, '--format', alt, '--out', crop], capture_output=True, text=True)
            try:
                f2 = json.load(open(crop + '.feiten.json'))
            except (OSError, ValueError):
                continue
            b2 = box_of(f2)
            outside = first is None or (b2 is not None and min(b2) >= min(first) + 2 and max(b2) >= max(first) + 2)
            if f2.get('verdict') != 'FOUT' and outside:
                chosen = alt; facts, fmt = f2, alt
                label = {'cd-slimjewel': 'a square card of a slim jewel case (no side flaps)', 'cd-cardsleeve': 'a cardboard sleeve or larger card',
                         'cd-digipak': 'a digipak panel'}[alt]
                result['applied'] = (result.get('applied', '') + f' measured as {label}, not a jewel case part').strip()
                break
        if first and first != 'keep':
            if chosen is None:                             # de jewel-maat bleef de buitenste echte rand
                os.replace(crop + '.jewel.png', crop); os.replace(crop + '.jewel.json', crop + '.feiten.json')
                facts = json.load(open(crop + '.feiten.json'))
            else:
                os.remove(crop + '.jewel.png'); os.remove(crop + '.jewel.json')
    def fits_cd(wh):
        # past deze maat op een cd-verpakking voor dit onderdeel (±1 mm)?
        for f in ('cd', 'cd-slimjewel', 'cd-cardsleeve', 'cd-digipak'):
            sp = SF.SHAPES[f].get(feit_part)
            if sp and sp[0] == 'rect':
                (wl, wh_), (hl, hh) = sp[1], sp[2]
                W, H = wh
                if (wl - 1 <= W <= wh_ + 1 and hl - 1 <= H <= hh + 1) or (wl - 1 <= H <= wh_ + 1 and hl - 1 <= W <= hh + 1):
                    return True
        return False
    if opaque_fallback is None and len(a.scans) == 1 and fmt.startswith('cd') and SF.SHAPES['cd'].get(feit_part, ('',))[0] == 'rect':
        # het hele beeld tegen alle cd-maten (niet alleen de gekozen verpakking)
        for f in ('cd', 'cd-slimjewel', 'cd-cardsleeve', 'cd-digipak'):
            if feit_part in SF.SHAPES[f]:
                got = already_cut(a.scans[0], SF.SHAPES[f][feit_part], a.release_dpi)
                if got and not got[1].get('transparent'):
                    opaque_fallback = got; break
    # Feit: past de gevonden snede op geen enkele cd-maat, maar het hele beeld wel, dan is het beeld
    # al uitgesneden (wit kaartje tot de beeldrand: Dominique-achterkant 121 mm, snede op 115 mm).
    if (opaque_fallback and fmt.startswith('cd') and facts and facts.get('verdict') != 'FOUT'
            and box_of(facts) and not fits_cd(box_of(facts))):
        facts = {'verdict': 'FOUT'}
    # Feit: buiten het kaartje ligt de deksel (effen en licht). Ligt er tussen de gevonden snede en
    # de beeldrand nog drukwerk, dan loopt het kaartje door tot de beeldrand: het beeld was al
    # uitgesneden (Deena-boekje 119,7 mm: de snede viel in de foto).
    if (opaque_fallback and fmt.startswith('cd') and facts and facts.get('verdict') != 'FOUT'
            and (facts.get('precise_mm') or facts.get('box_mm')) and print_outside(raw, facts)):
        facts = {'verdict': 'FOUT'}
    if opaque_fallback and (facts is None or facts.get('verdict') == 'FOUT'):
        # geen rand gevonden en de hele scan heeft al de maat van dit onderdeel: al uitgesneden
        img0, note = opaque_fallback
        cv2.imwrite(crop, img0)
        facts = {'verdict': 'GOED', 'why': [], 'dpi': note['dpi'], 'already_cut': note}
        json.dump(facts, open(crop + '.feiten.json', 'w'))
        result['applied'] = f'already cut ({note["mm"][0]} x {note["mm"][1]} mm matches the facts, no edge found inside); not cropped again'
    if facts is None:
        result.update(verdict='FOUT', why=[fe.stderr.strip().splitlines()[-1] if fe.stderr.strip() else 'cropping failed'])
        print(json.dumps(result)); return
    if facts.get('verdict') == 'FOUT' and a.part == 'inside' and fmt == 'vinyl' and not already:
        # Feit: een opengeklapte hoes is twee panelen (±62 x 31 cm). Past dat niet in deze scans, maar een
        # los vel wel, dan is het een los vel: de gemeten vorm bepaalt het (zoals bij cd-verpakkingen).
        step('no opened gatefold in these scans; measuring as a single sheet')
        subprocess.run([PY, os.path.join(HERE, 'scan_feiten.py'), raw, 'insert', '--format', fmt, '--out', crop], capture_output=True, text=True)
        try:
            sheet = json.load(open(crop + '.feiten.json'))
        except (OSError, ValueError):
            sheet = None
        if sheet and sheet.get('verdict') != 'FOUT':
            facts = sheet; feit_part = 'insert'
            result['applied'] = (result.get('applied', '') + ' measured as a single sheet, not an opened gatefold (for a loose sheet or booklet page use the Insert slot)').strip()
        else:
            facts = {'verdict': 'FOUT', 'why': ['this is not an opened gatefold sleeve (two panels, about 62 x 31 cm), and no single sheet was found either. '
                                               'Inside is only for a gatefold; put a loose sheet or a booklet page in an Insert slot, with all scans of that one side.']}
    if facts.get('verdict') == 'FOUT':
        result.update(verdict='FOUT', why=facts.get('why', ['not found']))
        print(json.dumps(result)); return
    dpi = facts.get('dpi') or 300.0
    why = result['why'] + list(facts.get('why', []))
    if facts.get('message'):
        result['message'] = facts['message']
    img = cv2.imread(crop, cv2.IMREAD_UNCHANGED)
    if not already and fmt.startswith('cd') and SF.SHAPES[fmt][feit_part][0] == 'rect' and img is not None:
        better = colour_extent(raw, dpi, img, fmt, feit_part)
        if better is not None:
            img, mm = better
            cv2.imwrite(crop, img)
            why = [w for w in why if not w.startswith('not square')]
            result['applied'] = (result.get('applied', '') + f' cut on the outer edge of the coloured card ({mm[0]:.1f} x {mm[1]:.1f} mm): the found edge lay inside the print').strip()
    if why and decision.get('crop') == 'square' and 'sides' in facts:
        img, weak = square_up(img, facts['sides'])
        why = [w for w in why if not w.startswith('not square')]
        result['applied'] = f'square ({weak} side moved in)'
        cv2.imwrite(crop, img)
    # Feit: de gemeten maat moet bij de verpakking passen (de randen kunnen na het grove zoeken
    # nog naar binnen schuiven). Past hij niet, dan klopt de verpakkingskeuze of de rand niet.
    spec = SF.SHAPES[fmt][feit_part]
    if spec[0] == 'rect' and img is not None:
        wm, hm = img.shape[1] / dpi * 25.4, img.shape[0] / dpi * 25.4
        (wl, wh), (hl, hh) = spec[1], spec[2]
        fits = lambda W, H: wl - 1 <= W <= wh + 1 and hl - 1 <= H <= hh + 1
        if not (fits(wm, hm) or fits(hm, wm)):
            why.append(f'measured {wm:.1f} x {hm:.1f} mm, but this packaging is {wl}-{wh} x {hl}-{hh} mm: check the packaging choice')
    # rechtop
    words_note = None
    try:
        words = release_words(a.discogs) if a.discogs else []
    except Exception as e:                                 # het uitsnijden is klaar: dat gooien we niet weg om een haperende verbinding
        words, words_note = [], f'which way is up: the text of the release could not be fetched from Discogs ({e})'
    disc = SF.SHAPES[fmt][feit_part][0] == 'disc'
    if words:
        args = [PY, os.path.join(HERE, 'scan_rechtop.py'), crop, '--words', os.path.join(a.work, 'words.json'), '--out', up]
        json.dump(words, open(os.path.join(a.work, 'words.json'), 'w'))
        if disc:
            args += ['--disc', '--dpi', str(dpi)]
        import scan_rechtop as _R
        step('macOS text recognition is not answering: setting it upright with the Discogs photo' if _R.ocr_unavailable()
             else 'reading text to set it upright (macOS text recognition)' + (' and straightening the label' if disc else ''))
        ro = subprocess.run(args, capture_output=True, text=True)
        try:
            upright = json.loads(ro.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            upright = {'verdict': 'TWIJFEL'}
        result['upright'] = {k: upright.get(k) for k in ('rotate_clockwise', 'verdict', 'read_upright')}
        turned = cv2.imread(up, cv2.IMREAD_UNCHANGED) if os.path.exists(up) else None
        if upright.get('verdict') == 'GOED':
            if turned is not None:
                img = turned
        else:
            # Geen duidelijke stand: Sleeve gokt niet. Het beeld blijft zoals het uitgesneden is, behalve
            # een label dat op de titel recht gezet is (dat is gemeten, alleen niet zeker): dat zie jij
            # recht gezet. Jouw draaiing geldt voor precies het beeld dat jij zag.
            base = cv2.imread(crop, cv2.IMREAD_UNCHANGED)
            title_only = 'title only' in (upright.get('read_upright') or [])
            shown = turned if (title_only and turned is not None) else base
            img = shown
            if not title_only:
                result['upright']['rotate_clockwise'] = 0   # er is niets gedraaid
            if decision.get('rotate') in ROTATE or decision.get('rotate') == 0:
                img = cv2.rotate(shown, ROTATE[decision['rotate']]) if decision['rotate'] else shown
                result['applied'] = (result.get('applied', '') + f' rotated {decision["rotate"]}').strip()
            elif title_only:
                why.append('which way is up: the label was set straight on the title only (no tracklist read); a title can be printed at an angle')
            else:
                # geen bekende tekst: de Discogs-foto van deze release bepaalt de stand
                got = discogs_orientation(base, a.discogs, disc) if a.discogs else None
                if got:
                    ang_d, nk = got
                    if disc:
                        hh, ww = base.shape[:2]
                        Rm = cv2.getRotationMatrix2D((ww / 2, hh / 2), -ang_d, 1.0)
                        img = cv2.warpAffine(base, Rm, (ww, hh), flags=cv2.INTER_CUBIC, borderValue=(0, 0, 0, 0))
                    else:
                        img = cv2.rotate(base, ROTATE[int(ang_d)]) if int(ang_d) else base
                    result['upright'] = {'rotate_clockwise': round(ang_d, 1), 'verdict': 'GOED', 'read_upright': [f'Discogs photo ({nk} matching points)']}
                    result['applied'] = (result.get('applied', '') + ' upright from the Discogs photo').strip()
                elif upright.get('verdict') == 'LEESBAAR':
                    # feit: andere tekst op dit onderdeel leest duidelijk in één stand
                    if turned is not None:
                        img = turned
                    result['upright'] = {'rotate_clockwise': upright.get('rotate_clockwise'), 'verdict': 'GOED', 'read_upright': upright.get('read_upright')}
                    result['applied'] = (result.get('applied', '') + ' upright from readable text').strip()
                else:
                    why.append('which way is up: no text could be read clearly, and no Discogs photo matches clearly')
    else:
        why.append(words_note or 'which way is up: no Discogs release, so no known text to read')
    # kant op het label (feit) tegen het vak
    if disc and feit_part.startswith('side'):
        letter = side_on_label(img, dpi)
        result['side_on_label'] = letter
        if letter and a.part.startswith('side') and a.part != 'side' + letter:
            why.append(f'the label says side {letter.upper()}, the slot says {a.part[4:].upper()}')
    if why and decision.get('crop') == 'keep':
        result['applied'] = (result.get('applied', '') + ' kept as it is').strip()
        why = []                                           # jouw beslissing 'zo laten' = klaar
    if why:
        result['verdict'] = 'TWIJFEL'; result['why'] = why; result['choices'] = choices_for(why)
        if any(w.startswith('which way is up') for w in why):
            result['choices'] += ['rotate90', 'rotate180', 'rotate270']
    # uitklap: in twee panelen splitsen (feit: twee gelijke helften naast elkaar)
    panels = [(a.part, img)]
    if a.part == 'inside' and fmt == 'vinyl' and img.shape[1] > 1.7 * img.shape[0]:
        half = img.shape[1] // 2
        panels = [('insert_left', img[:, :half]), ('insert_right', img[:, half:])]
    elif a.part == 'inside' and fmt == 'vinyl' and img.shape[0] > 1.7 * img.shape[1]:
        half = img.shape[0] // 2
        panels = [('insert_left', img[:half]), ('insert_right', img[half:])]
    if len(panels) > 1:
        paths = []
        for kant, pimg in panels:
            nm = None
            if a.discogs:
                try:
                    import scan_naam as N
                    nm = N.naam(a.discogs, kant, a.variant, a.year)
                except Exception:
                    pass
            nm = nm or f'{os.path.splitext(os.path.basename(a.scans[0]))[0]}_{kant}'
            os.makedirs(a.out, exist_ok=True)
            pth = os.path.join(a.out, nm + '.png'); n = 2
            while os.path.exists(pth) and not a.decision:
                pth = os.path.join(a.out, f'{nm}_{n}.png'); n += 1
            cv2.imwrite(pth, pimg)
            try:
                from PIL import Image
                with Image.open(pth) as im:
                    im.load(); im.save(pth, dpi=(dpi, dpi))
            except Exception:
                pass
            paths.append({'path': pth, 'part': kant, 'size_mm': [round(pimg.shape[1] / dpi * 25.4, 1), round(pimg.shape[0] / dpi * 25.4, 1)]})
        result['path'] = paths[0]['path']; result['panels'] = paths; result['dpi'] = dpi
        if result.get('why_note'):
            result['applied'] = (result.get('applied', '') + ' ' + result['why_note']).strip()
        result['size_mm'] = [round(img.shape[1] / dpi * 25.4, 1), round(img.shape[0] / dpi * 25.4, 1)]
        for f in (raw, raw + '.scans.json', crop, crop + '.feiten.json', up):
            if os.path.exists(f):
                os.remove(f)
        print(json.dumps(result, ensure_ascii=False)); return
    # naam
    name = None
    if a.discogs:
        try:
            import scan_naam as N
            name = N.naam(a.discogs, a.part, a.variant, a.year)
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
    if result.get('why_note'):
        result['applied'] = (result.get('applied', '') + ' ' + result['why_note']).strip()
    result['size_mm'] = [round(img.shape[1] / dpi * 25.4, 1), round(img.shape[0] / dpi * 25.4, 1)]
    for f in (raw, raw + '.scans.json', crop, crop + '.feiten.json', up):   # tussenbestanden opruimen (1200 dpi: ±1,5 GB)
        if os.path.exists(f):
            os.remove(f)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
