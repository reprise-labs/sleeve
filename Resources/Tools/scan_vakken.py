#!/usr/bin/env python3
"""Vakken vooraf invullen. Eerst stapels: welke deelscans horen bij één onderdeel. Dan per stapel de
naam, alleen op feiten. Een stapel zonder vaststaande naam komt als naamloos vak ('unknown'): jij kiest
het onderdeel met één klik in plaats van elke scan apart te slepen.

Stapels (feiten, gemeten op de 17 releases van de vaste toets, 14 nov):
  - deelscans van één onderdeel delen drukwerk (overlap, op schaal 1: zelfde scanner, zelfde dpi);
    zonder overlap met de lopende stapel begint een nieuw onderdeel
  - de scans worden in bestandsvolgorde gelopen (jij scant onderdeel na onderdeel)
  - een scan die op dezelfde plek ligt als een scan uit de lopende stapel (< 12 mm, < 20 graden),
    is een volgend onderdeel met hetzelfde drukwerk (kant B na kant A, twee gelijke inserts)
  - een scan die veel zwakker overeenkomt (< 0,35 x wat binnen de stapel gewoon is) ook: hetzelfde
    drukwerk in een ander onderdeel (de hoes herhaald op een insert)
  - een scan met een cd van 120 mm hoort nooit bij een scan zonder cd

Namen:
  back   de scan bevat de barcode van deze release (Discogs-barcode, cijfer voor cijfer)
  front  de scan komt aantoonbaar overeen met de hoesfoto van Discogs (type 'primary'),
         of, zonder primary, de eerste foto die Discogs als hoes toont; en met geen
         andere Discogs-foto beter (genoeg overeenkomende punten)
  cd     (cd-uitgave, één schijf) er ligt een cirkel van 120 mm in de scan, gemeten
         met de resolutie uit het bestand
  kant   (vinyl) de stapel toont de doorlopende rand van een plaat van ±30 cm; de kanten krijgen
         A, B, C, D in scanvolgorde. Dat is een voorstel: na het verwerken leest Sleeve de letter op
         het label en twijfelt als die niet klopt.
  front/back komen maar één keer voor: twee stapels met hetzelfde feit zijn één onderdeel (opnieuw gescand).

Gebruik: scan_vakken.py <discogs-url> <cd|vinyl> <vakken,komma> <scan> ...
Uitvoer: één JSON-regel {"groups": [{"part": ..., "files": [...]}], "why": {scan: reden}}
"""
import json, os, re, subprocess, sys, tempfile, math, statistics
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import scan_dpi
import scan_discogs as D

OCR = os.path.join(HERE, 'sleeve_ocr')
THUMB = 1600
MIN_FRONT = 30          # overeenkomende punten met de hoesfoto
PXMM = 2.0              # stapels: kleine beelden op 2 px/mm (genoeg drukwerk, snel)
MIN_LINK = 15           # zoveel overeenkomende punten = overlap
SAME_PLACE_MM, SAME_PLACE_DEG = 12.0, 20.0
WEAK = 0.35
RECORD_RIM = 0.21       # deel van de cirkel (r 147-151 mm) dat als doorlopende rand te zien is (mediaan van de stapel)
SIDES = ['sidea', 'sideb', 'sidec', 'sided']


def thumb(path, work):
    """Kleine versie via ImageIO (snel, ook bij grote png's); geeft beeld en schaal t.o.v. het origineel."""
    out = os.path.join(work, os.path.basename(path) + '.jpg')
    subprocess.run(['/usr/bin/sips', '-Z', str(THUMB), '-s', 'format', 'jpeg', path, '--out', out], capture_output=True)
    im = cv2.imread(out)
    if im is None:
        return None, 0
    w = int(subprocess.run(['/usr/bin/sips', '-g', 'pixelWidth', path], capture_output=True, text=True).stdout.split()[-1])
    return im, im.shape[1] / max(1, w)


def barcodes(path):
    try:
        r = subprocess.run([OCR, path, '--identify'], capture_output=True, text=True, timeout=20)
        return [re.sub(r'\D', '', c) for c in json.loads(r.stdout).get('barcodes', [])]
    except Exception:
        return []


def same_barcode(a, b):
    a, b = a.lstrip('0'), b.lstrip('0')
    return len(a) >= 8 and a == b


def has_cd(im, px_mm):
    """Cirkel van 120 mm (±2 mm) met een duidelijke rand rondom."""
    if px_mm <= 0:
        return False
    g = cv2.medianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), 5)
    r0 = 60 * px_mm
    c = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1, minDist=r0, param1=80, param2=40,
                         minRadius=int(58 * px_mm), maxRadius=int(62 * px_mm) + 1)
    if c is None:
        return False
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1); mag = np.hypot(gx, gy)
    h, w = g.shape
    for x, y, r in c[0][:3]:
        hits = n = 0
        for k in range(144):
            t = 2 * math.pi * k / 144
            xs = int(round(x + r * math.cos(t))); ys = int(round(y + r * math.sin(t)))
            if 1 <= xs < w - 1 and 1 <= ys < h - 1:
                n += 1
                hits += mag[ys - 1:ys + 2, xs - 1:xs + 2].max() > 40
        if n >= 120 and hits / n >= 0.85:
            return True
    return False


def number_key(path):
    """Bestandsvolgorde zoals de scanner nummert en de Finder sorteert: 'Scan' voor 'Scan 1' voor 'Scan 2'
    voor 'Scan 10' ('00.jpeg' is de eerste, daarna '00 1.jpeg'; voorheen kwam '00.jpeg' als laatste)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r'^(.*\S)\s+(\d+)$', stem)
    base, n = (m.group(1), int(m.group(2))) if m else (stem, 0)
    return ([int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', base)], n)


def small(path, work):
    """Kleine grijze versie op PXMM pixels per mm (via de resolutie uit het bestand)."""
    dpi = scan_dpi.read(path) or 300.0
    try:
        w = int(subprocess.run(['/usr/bin/sips', '-g', 'pixelWidth', path], capture_output=True, text=True).stdout.split()[-1])
    except (ValueError, IndexError):
        return None
    out = os.path.join(work, f'{abs(hash(path))}_s.png')
    subprocess.run(['/usr/bin/sips', '--resampleWidth', str(max(64, int(round(w / dpi * 25.4 * PXMM)))), '-s', 'format', 'png', path, '--out', out], capture_output=True)
    return cv2.imread(out)


SIFT = cv2.SIFT_create(nfeatures=4000)
BF = cv2.BFMatcher(cv2.NORM_L2)


def features(im):
    g = cv2.createCLAHE(2.0, (8, 8)).apply(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    k, d = SIFT.detectAndCompute(g, None)
    return (np.float32([p.pt for p in k]) if k else np.zeros((0, 2), np.float32), d, g.shape)


def link(a, b):
    """Overlap tussen twee scans: (aantal overeenkomende punten, verschuiving in mm, draaiing in graden).
    Alleen op schaal 1 (zelfde scanner, zelfde dpi); anders geen overlap."""
    (pa, da, sa), (pb, db, sb) = a, b
    if da is None or db is None or len(da) < 10 or len(db) < 10:
        return 0, 0.0, 0.0
    m = [x[0] for x in BF.knnMatch(da, db, k=2) if len(x) == 2 and x[0].distance < .75 * x[1].distance]
    if len(m) < 8:
        return 0, 0.0, 0.0
    M, inl = cv2.estimateAffinePartial2D(pa[[x.queryIdx for x in m]], pb[[x.trainIdx for x in m]],
                                         method=cv2.RANSAC, ransacReprojThreshold=3.0, maxIters=3000)
    if M is None or abs(float(np.hypot(M[0, 0], M[1, 0])) - 1) > .04:
        return 0, 0.0, 0.0
    moved = M @ np.array([sa[1] / 2, sa[0] / 2, 1.0]) - np.array([sb[1] / 2, sb[0] / 2])
    ang = abs((np.degrees(np.arctan2(M[1, 0], M[0, 0])) + 180) % 360 - 180)
    LINKS[id(a), id(b)] = M                                  # voor de maat van de hele stapel (extent)
    return int(inl.sum()), float(np.hypot(*moved) / PXMM), float(ang)


LINKS = {}


def extent_mm(g, feats):
    """Breedte en hoogte (mm) van wat de deelscans van een stapel samen bedekken: elke scan op zijn plek via
    de overlap met een eerdere scan uit de stapel. Een opengeklapte hoes is ±62 cm breed, een vel ±30 cm."""
    T = {g[0]: np.eye(3)}
    for s in g[1:]:
        best = None
        for x in T:
            M = LINKS.get((id(feats[s]), id(feats[x])))
            if M is not None and (best is None or True):
                best = (x, M); break
        if best is None:
            return None
        x, M = best
        T[s] = T[x] @ np.vstack([M, [0, 0, 1]])
    pts = []
    for s, t in T.items():
        h, w = feats[s][2]
        c = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], np.float64).T
        pts.append((t @ c)[:2].T)
    P = np.vstack(pts)
    return float((P[:, 0].max() - P[:, 0].min()) / PXMM), float((P[:, 1].max() - P[:, 1].min()) / PXMM)


def record_rim(im):
    """Deel van een cirkel van een lp (straal 147-151 mm) dat als doorlopende rand in de scan staat, ook als
    het middelpunt buiten de scan ligt. Stemmen langs de gradiënt; dan de rand natellen: loodrecht op de
    straal en in stukken van ten minste 10 graden (een plaatrand loopt door, drukwerk niet)."""
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.0).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1); mag = np.hypot(gx, gy)
    h, w = g.shape
    ys, xs = np.nonzero(mag > max(20.0, np.percentile(mag, 90)))
    if len(xs) > 60000:
        sel = np.random.default_rng(0).choice(len(xs), 60000, replace=False); ys, xs = ys[sel], xs[sel]
    if not len(xs):
        return 0.0
    nx = gx[ys, xs] / mag[ys, xs]; ny = gy[ys, xs] / mag[ys, xs]
    t = np.linspace(0, 2 * np.pi, 720, endpoint=False); best = 0.0
    for rmm in (147, 149, 151):
        r = rmm * PXMM; pad = int(r) + 4
        acc = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
        for sgn in (1, -1):
            np.add.at(acc, (np.round(ys + sgn * ny * r).astype(int) + pad, np.round(xs + sgn * nx * r).astype(int) + pad), 1)
        cy, cx = np.unravel_index(np.argmax(cv2.GaussianBlur(acc, (0, 0), 1.5)), acc.shape); cy -= pad; cx -= pad
        px = np.round(cx + r * np.cos(t)).astype(int); py = np.round(cy + r * np.sin(t)).astype(int)
        inside = (px >= 2) & (px < w - 2) & (py >= 2) & (py < h - 2)
        if inside.sum() < 60:
            continue
        hits = np.zeros(720, bool)
        for k in np.nonzero(inside)[0]:
            y1, x1 = max(0, py[k] - 3), max(0, px[k] - 3)
            win = mag[y1:py[k] + 4, x1:px[k] + 4]
            j = np.unravel_index(np.argmax(win), win.shape); yy, xx = y1 + j[0], x1 + j[1]
            if mag[yy, xx] >= 40:
                hits[k] = abs((gx[yy, xx] * np.cos(t[k]) + gy[yy, xx] * np.sin(t[k])) / mag[yy, xx]) > .92
        good = run = 0
        for k in range(720):
            run = run + 1 if hits[k] else 0
            if run and (k == 719 or not hits[k + 1]) and run >= 20:
                good += run
        best = max(best, good / 720.0)
    return best


def is_sticker(scan, work):
    """Feit: een sticker is een kleine gesloten vorm met afgeronde hoeken (of een cirkel) op een verder lege scan
    (zijn plastic hoes). Een cd-boekje of kaartje heeft scherpe hoeken; een cd is een cirkel van 120 mm."""
    out = os.path.join(work, 'sticker_probe.png')
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'scan_sticker.py'), scan, '--out', out], capture_output=True, text=True, timeout=180)
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError, subprocess.TimeoutExpired, OSError):
        return None
    if res.get('verdict') == 'FOUT' or not res.get('area_frac') or res['area_frac'] > .15:
        return None
    dpi = res.get('dpi') or 0
    if res.get('shape') == 'circle':
        d = (res.get('size_mm') or [0])[0]
        if dpi and 112 <= d <= 125:
            return None                                     # een cd, geen sticker
        return 'a round sticker'
    if dpi and res.get('corner_px', 0) / dpi * 25.4 < 1.5:
        return None                                         # scherpe hoeken: een kaartje of boekje
    return 'a small card with rounded corners (a sticker)'


def card_size(scan, work):
    """Maat (mm) van het kaartje op één cd-scan, gemeten zoals bij het uitsnijden (scan_feiten, als achterkaart
    van een jewelcase: 136-154 x 114-120 mm). Geeft (breedte, hoogte) of None als zo'n kaart er niet in ligt."""
    import shutil as _sh
    d = tempfile.mkdtemp(dir=work); src = os.path.join(d, 'scan' + os.path.splitext(scan)[1])
    try:
        os.symlink(os.path.abspath(scan), src)
        dpi = scan_dpi.read(scan)
        if not dpi:
            return None
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(scan) as im:
            w, h = im.size
            im.convert('RGBA').save(os.path.join(d, 'raw.png'))
        json.dump({'scale': 1, 'dpi': dpi, 'scans': [{'scan': 'scan', 'corners': [[0, 0], [w, 0], [w, h], [0, h]]}]}, open(os.path.join(d, 'raw.png.scans.json'), 'w'))
        r = subprocess.run([sys.executable, os.path.join(HERE, 'scan_feiten.py'), os.path.join(d, 'raw.png'), 'back', '--format', 'cd'], capture_output=True, text=True, timeout=300)
        try:
            res = json.loads(r.stdout[r.stdout.index('{'):r.stdout.rindex('}') + 1]) if '{' in r.stdout else {}
        except ValueError:
            res = {}
        box = res.get('precise_mm') or res.get('box_mm')
        if res.get('verdict') == 'FOUT' or not box or len(box) < 4:
            return None
        return box[2], box[3]
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        _sh.rmtree(d, ignore_errors=True)


def real(M):
    """Een echte overeenkomst met een Discogs-foto heeft een schaal; schaal 0 is een ontaarde oplossing."""
    return M is not None and float(np.hypot(M[0, 0], M[1, 0])) > .05


def background(sm):
    """Achtergrond langs de scanrand: 'lid' (witte klep: licht en kleurloos) of 'sheet' (gekleurd of donker vel)."""
    h, w = sm.shape[:2]; b = max(3, int(.03 * min(h, w)))
    lab = cv2.cvtColor(sm, cv2.COLOR_BGR2LAB).astype(np.float32)
    ring = np.concatenate([lab[:b].reshape(-1, 3), lab[-b:].reshape(-1, 3), lab[:, :b].reshape(-1, 3), lab[:, -b:].reshape(-1, 3)])
    white = (ring[:, 0] * 100 / 255 > 80) & (np.hypot(ring[:, 1] - 128, ring[:, 2] - 128) < 10)
    return 'lid' if white.mean() > .25 else 'sheet'


def complete(g, feats):
    """Bedekt deze stapel al een hele hoes (minstens 305 mm in beide richtingen)? Zo niet, dan mag een zwakke maar
    echte overlap erbij: een hoes die halverwege een halve slag is gedraaid, deelt weinig drukwerk tussen de twee
    helften (US wit voorkant: 39 punten tegen 151 binnen een helft) - maar alleen als de stapel daardoor een hele
    hoes wordt. Een insert met de hoes erop komt na een complete hoes-stapel en blijft apart; twee boekjespagina's
    van 29 cm worden samen geen hoes en blijven ook apart (US groen)."""
    e = extent_mm(g, feats) if len(g) > 1 else None
    return e is not None and min(e) >= 305


def stacks(scans, feats, discs):
    """Deelscans in bestandsvolgorde tot stapels: zie de feiten bovenaan."""
    order = sorted(scans, key=number_key)
    groups, strengths = [[order[0]]], [[]]
    for s in order[1:]:
        g = groups[-1]
        links = {x: link(feats[s], feats[x]) for x in g} if feats.get(s) and all(feats.get(x) for x in g) else {}
        best = max([v[0] for v in links.values()] or [0])
        new = (best < MIN_LINK
               or discs.get(s) != discs.get(g[0])
               or any(v[0] >= MIN_LINK and v[1] < SAME_PLACE_MM and v[2] < SAME_PLACE_DEG for v in links.values())
               or (strengths[-1] and best < WEAK * statistics.median(strengths[-1]) and (complete(g, feats) or not complete(g + [s], feats))))
        if new:
            groups.append([s]); strengths.append([])
        else:
            g.append(s); strengths[-1].append(best)
    return groups


def main():
    url, fmt, slots = sys.argv[1], sys.argv[2], [s for s in sys.argv[3].split(',') if s]
    scans = sys.argv[4:]
    codes, imgs, roles = [], [], []
    if url:
        rid = re.search(r'/release/(\d+)', url); mid = re.search(r'/master/(\d+)', url)
        if not rid and mid:                                # master-link: de hoofduitgave daarvan
            main_ = json.loads(D.get(f'https://api.discogs.com/masters/{mid.group(1)}')).get('main_release')
            rid = re.search(r'/release/(\d+)', f'/release/{main_}') if main_ else None
        rel = json.loads(D.get(f'https://api.discogs.com/releases/{rid.group(1)}')) if rid else {}
        if not fmt:
            fmt = 'cd' if any((f.get('name') or '').lower() == 'cd' for f in rel.get('formats', [])) else 'vinyl'
        codes = [re.sub(r'\D', '', i.get('value', '')) for i in rel.get('identifiers', []) if i.get('type') == 'Barcode']
        for im in rel.get('images', []):
            try:
                arr = cv2.imdecode(np.frombuffer(D.get(im['uri']), np.uint8), cv2.IMREAD_COLOR)
                if arr is not None:
                    imgs.append(arr); roles.append(im.get('type', 'secondary'))
            except Exception:
                pass
    # Discogs' eigen hoesfoto: type 'primary'; zonder primary toont Discogs de eerste foto als hoes
    primary = roles.index('primary') if 'primary' in roles else (0 if imgs else None)
    # Discogs-foto's van de hoes: de hoofdfoto en de foto's die er duidelijk op lijken (vaak twee hoesfoto's)
    front_photos = set()
    if primary is not None:
        front_photos = {primary} | {n for k, n, M in D.matches(imgs[primary], imgs) if k >= 40 and real(M)}
    facts, why, feats, discs, rims, photo, backs = {}, {}, {}, {}, {}, {}, {}
    with tempfile.TemporaryDirectory() as work:
        for n, s in enumerate(scans):
            print(f'SLEEVE_STEP looking at scan {n + 1} of {len(scans)}', file=sys.stderr, flush=True)
            sm = small(s, work)
            if sm is not None:
                feats[s] = features(sm)
                backs[s] = background(sm)
                if fmt != 'cd':
                    rims[s] = record_rim(sm)
            found = []
            if codes and any(same_barcode(b, c) for b in barcodes(s) for c in codes):
                found.append(('back', 'the release barcode is on this scan'))
            im, scale = thumb(s, work)
            if im is None:
                continue
            if imgs:
                m = [x for x in D.matches(im, imgs) if real(x[2])]
                if m:
                    photo[s] = (m[0][1], m[0][0])          # de Discogs-foto die het best op deze scan past
                if m and m[0][1] in front_photos and m[0][0] >= MIN_FRONT:
                    found.append(('front', f'matches the Discogs cover photo ({m[0][0]} points)'))
            if fmt == 'cd':
                dpi = scan_dpi.read(s)
                if dpi and has_cd(im, dpi * scale / 25.4):
                    discs[s] = True
                    found.append(('cd', 'a 120 mm disc lies on this scan'))
            if len(found) == 1:            # twee feiten die elkaar tegenspreken: niet kiezen
                facts[s] = found[0]
            elif found:
                why[s] = 'conflicting facts: ' + ', '.join(p for p, _ in found)
    usable = [s for s in scans if s in feats] or scans
    # alleen scans van een plaat (de rand van een lp is te zien): optie A bestaat alleen bij vinyl. Een hoes kan
    # toevallig scans met en zonder witte klep langs de rand hebben (Deena inside).
    rec = [s for s in usable if rims.get(s, 0.0) >= RECORD_RIM]
    lids = [s for s in rec if backs.get(s) == 'lid']; sheets = [s for s in rec if backs.get(s) == 'sheet']
    if len(lids) >= 2 and len(sheets) >= 2:
        # Optie A (doorschijnend vinyl): per positie een scan met de witte klep en een met een vel op de plaat. Een
        # vel-scan ligt op dezelfde plek als zijn klep-scan: eerst de klep-scans tot stapels, dan elke vel-scan bij de
        # stapel waar hij het best op past. (Anders begon bij elke vel-scan een nieuwe stapel: 'zelfde plek'.)
        groups = stacks(lids, feats, discs)
        rest = [s for s in usable if s not in lids and s not in sheets]
        for sh in sorted(sheets, key=number_key):
            best = max(((link(feats[sh], feats[x])[0], gi) for gi, g in enumerate(groups) for x in g), default=(0, None))
            if best[0] >= MIN_LINK:
                groups[best[1]].append(sh)
            else:
                groups.append([sh])
        groups += stacks(rest, feats, discs) if rest else []
        groups.sort(key=lambda g: min(number_key(x) for x in g))       # scanvolgorde (kant A voor kant B)
    else:
        groups = stacks(usable, feats, discs) if scans else []
    def best_photo(g):
        got = [photo[s] for s in g if s in photo]
        return max(got, key=lambda x: x[1]) if got else (None, 0)
    named = []
    for g in groups:
        parts = {facts[s][0] for s in g if s in facts}
        if 'back' in parts and 'front' in parts:
            # Feit: een barcode staat alleen op de achterkant; een achterkant kan wel de hoes klein afbeelden
            parts = {'back'}
        part, reason, score = 'unknown', 'no fact for this part yet: choose it', 0
        if fmt != 'cd' and g and statistics.median(rims.get(s, 0.0) for s in g) >= RECORD_RIM:
            # de rand van een plaat weegt zwaarder dan een Discogs-foto: een label toont vaak de hoes
            part, reason = 'side', 'the rim of a 30 cm record is on these scans'
        elif len(parts) == 1:
            part = parts.pop(); src = next(s for s in g if s in facts and facts[s][0] == part); reason = facts[src][1] + f' ({os.path.basename(src)})'
            score = best_photo(g)[1]
        elif len(parts) > 1:
            reason = 'conflicting facts: ' + ', '.join(sorted(parts))
        named.append([part, g, reason, score])
    # Feit: de stapel met de barcode is de back; daarmee is ook bekend welke Discogs-foto de back toont.
    # Een andere stapel die het best op diezelfde foto past (opnieuw gescand) is ook de back.
    backs = [x for x in named if x[0] == 'back']
    bps = {best_photo(x[1])[0] for x in backs}
    if len(bps) == 1:                                       # alle stapels met de barcode passen op dezelfde foto
        bp = bps.pop()
        for x in named:
            if x[0] == 'unknown' and bp is not None and best_photo(x[1])[0] == bp and bp not in front_photos and best_photo(x[1])[1] >= MIN_FRONT:
                x[0], x[2] = 'back', f'matches the Discogs photo of the back, like the scan with the barcode'
    # De hoes bestaat één keer, maar een insert of poster kan precies dezelfde afbeelding dragen. Lijken
    # meer stapels op de hoes, dan is niet vast te stellen welke de hoes is: geen naam (jij kiest).
    fronts = [x for x in named if x[0] == 'front']
    if len(fronts) > 1 and fmt != 'cd':
        # Feit: een lp-hoes is minstens 305 mm in beide richtingen. Wat de scans van een stapel samen bedekken,
        # moet dan ook minstens zo groot zijn; is het in één richting kleiner, dan is het niet de hoes maar een
        # kleiner vel met de hoes erop (Urban Solitude groen: een afdruk van de hoes in 2 scans).
        for x in fronts:
            e = extent_mm(x[1], feats)
            if e is not None and min(e) < 305:
                x[0], x[2] = 'unknown', f'looks like the cover, but these scans cover only {min(e):.0f} mm one way: smaller than a sleeve (305 mm)'
        fronts = [x for x in named if x[0] == 'front']
    if len(fronts) > 1:
        for x in fronts:
            x[0], x[2] = 'unknown', f'{len(fronts)} stacks look like the cover (a print of it on an insert?): choose which is the front'
    # De back (barcode) bestaat één keer. Opeenvolgende back-stapels: opnieuw gescand, één onderdeel.
    # Niet opeenvolgend: de sterkste overeenkomst houdt de naam.
    for part in ('back',):
        i = 0
        while i < len(named) - 1:
            if named[i][0] == part and named[i + 1][0] == part:
                named[i][1] += named[i + 1][1]; named[i][3] = max(named[i][3], named[i + 1][3]); del named[i + 1]
            else:
                i += 1
        same = [x for x in named if x[0] == part]
        if len(same) > 1:
            keep = max(same, key=lambda x: x[3])
            for x in same:
                if x is not keep:
                    x[0], x[2] = 'unknown', f'also looks like the {part}, but {os.path.basename(keep[1][0])} matches better: choose it'
    # Een release heeft één front en één back. Zijn beide gevonden, dan is elk ander vel (geen plaat, geen cd)
    # een insert, of de binnenkant van een uitklaphoes als het samen breder is dan 45 cm (±62 x 31 cm).
    # De maat is wat de deelscans samen bedekken (glas, dus ruimer dan het vel): een vel van 30 cm in 4 delen
    # 330-460 mm, een opengeklapte hoes ±670 mm (gemeten op de vaste toets). Ligt er een binnenkant in de
    # release, dan krijgt geen andere stapel 'insert': een los stuk van die binnenkant zou anders insert heten.
    if fmt != 'cd' and any(x[0] == 'front' for x in named) and any(x[0] == 'back' for x in named):
        open_ = [x for x in named if x[0] == 'unknown' and (x[2].startswith('no fact') or 'smaller than a sleeve' in x[2])]
        size = {id(x): extent_mm(x[1], feats) for x in open_}
        for x in open_:
            if size[id(x)] and max(size[id(x)]) > 580:
                x[0], x[2] = 'inside', f'front and back are found; these scans cover {max(size[id(x)]):.0f} mm: the inside of a gatefold'
        if not any(x[0] == 'inside' for x in named):
            for x in open_:
                if x[0] == 'unknown' and size[id(x)] and max(size[id(x)]) < 520:
                    x[0], x[2] = 'insert', 'front and back are found and this is another sheet: an insert'
    # Cd (jewelcase): er zijn precies twee delen van ±150 mm breed, de achterkaart en het inlay (de twee kanten van
    # het kaartje in de lade). Is de achterkaart gevonden, dan is een andere losse scan met zo'n kaart het inlay.
    # Een vierkant kaartje van 120 mm kan insert, inside of de achterkant van een promo zijn: geen naam.
    if fmt == 'cd' and any(x[0] == 'back' for x in named) and not any(x[0] == 'inlay' for x in named):
        wide = []
        with tempfile.TemporaryDirectory() as work2:
            for x in named:
                if x[0] == 'unknown' and len(x[1]) == 1:
                    sz = card_size(x[1][0], work2)
                    if sz and 145 <= max(sz) <= 154 and 114 <= min(sz) <= 120:   # ±150 x 118 (een boekje van 120 mm kwam op de ondergrens 136 uit)
                        wide.append((x, sz))
        if len(wide) == 1:
            x, sz = wide[0]
            x[0], x[2] = 'inlay', f'the back is found; this card is {max(sz):.0f} x {min(sz):.0f} mm, the other card of that size in a jewel case: the inlay'
    # Sticker: een losse scan met een kleine gesloten vorm met afgeronde hoeken of een cirkel (zijn plastic hoes eromheen)
    if not any(x[0] == 'sticker' for x in named):
        with tempfile.TemporaryDirectory() as work3:
            for x in named:
                if x[0] == 'unknown' and len(x[1]) == 1:
                    why_ = is_sticker(x[1][0], work3)
                    if why_:
                        x[0], x[2] = 'sticker', f'{why_} lies on this scan'
    named = [x[:3] for x in named]
    if fmt == 'cd':                       # één cd-schijf: meer stapels met een cd is geen feit meer
        cds = [x for x in named if x[0] == 'cd']
        if len(cds) > 1:
            for x in cds:
                x[0], x[2] = 'unknown', 'more than one scan has a disc'
    k = 0
    for x in named:                       # kanten in scanvolgorde (na het verwerken controleert het label)
        if x[0] == 'side':
            if k < len(SIDES):
                x[0] = SIDES[k]; x[2] += f'; side {SIDES[k][-1].upper()} by scan order (the label is checked after processing)'
            else:
                x[0] = 'unknown'
            k += 1
    for part, g, reason in named:
        for s in g:
            why.setdefault(s, reason)
    print(json.dumps({'groups': [{'part': p, 'files': g, 'why': r} for p, g, r in named], 'why': why}, ensure_ascii=False))


if __name__ == '__main__':
    main()
