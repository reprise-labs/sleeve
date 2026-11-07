#!/usr/bin/env python3
"""Scans van cd's en hoesjes klaarmaken voor de site, in dezelfde stijl als de
bestaande scans van muziekuitgaven.

CD / DVD (modus "cd"):
  - zoekt de schijf in de scan (cirkel-fit op de rand van de schijf; valt terug
    op het omsluitende kader als de schijf slecht afsteekt tegen de achtergrond,
    bv. een witte schijf op een lichtgrijze scanner)
  - haalt de doorzichtige buitenring weg: knipt af op de bedrukte rand
  - schijf vult het hele vierkant (standaard 1200x1200)
  - achtergrond en middengat transparant (gat = 13,8% van de diameter, gemeten
    op de bestaande cd's van de site)
  - optioneel draaien met --angle (graden, tegen de klok in) zodat de tekst
    recht staat

Vinyl (modus "vinyl"):
  - zoekt de buitenrand van de hele plaat (dus niet het label)
  - plaat vult het vierkant, achtergrond transparant, klein asgat (2,6%)
  - 7" met groot middengat: --gat 0.217

Hoes (modus "cover"):
  - zet een scheef gescande hoes automatisch recht (tot 8 graden)
  - snijdt de scannerachtergrond weg rond de hoes
  - let op: een witte hoes op een witte scanner herkent hij niet

Gebruik:
  python3 scan_cutout.py cd    scan.png  uit.png  [--angle 90]
  python3 scan_cutout.py vinyl scan.png  uit.png  [--angle 0] [--gat 0.217]
  python3 scan_cutout.py cover scan.png  uit.png  [--niet-rechtzetten]
  python3 scan_cutout.py map   <invoermap> <uitvoermap> [--angles hoeken.json]
      verwerkt een hele map: bestanden die op _cd / _cd1 / _cd2 / _dvd eindigen
      als schijf, de rest als hoes. hoeken.json = {"bestandsnaam_zonder_ext": graden}

De app bewaart afzonderlijke resultaatbestanden.
"""
import argparse, json, os, re, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
Image.MAX_IMAGE_PIXELS = None

HOLE = 0.138        # cd/dvd: gatdiameter / schijfdiameter, zoals op de site
HOLE_VINYL = 0.026  # lp/7": klein asgat, zoals op de site (7" met groot gat: --gat 0.217)
SWEEP_MARGIN = 1.2     # leesstand-zoektocht: de winnaar moet 20% meer echte woorden halen dan de rest
LABEL_REFINE_MIN = 1.5 # graden: kleinere bijstellingen zijn ruis van het labelontwerp (gemeten tot 1,3)
LABEL_REFINE = 8.0     # graden: fijnbijstelling op de tekstregels na de grove meting (en na de leesstand-zoektocht in stappen van 15)
MAX_LABEL_SKEW = 12.0  # graden: grotere fijne scheefstand van een label is eerder een meetfout
SIZE = None       # None = volle resolutie (de site-versie maakt een andere Quick Action)


def content_mask(im, thr=30):
    """Alles wat duidelijk afwijkt van de achtergrondkleur (mediaan van de rand)."""
    a = np.asarray(im).astype(int)
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(edge, axis=0)
    return np.abs(a - bg).sum(axis=2) > thr


def fit_circle(mask):
    """Kleinste-kwadraten cirkel door de rand van de vorm, met uitschieters eruit."""
    m = Image.fromarray((mask * 255).astype('uint8')).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(9))
    a = np.asarray(m) > 128
    er = np.asarray(Image.fromarray((a * 255).astype('uint8')).filter(ImageFilter.MinFilter(5))) > 128
    ys, xs = np.where(a & ~er)
    cx = cy = r = 0
    for _ in range(4):
        A = np.c_[2 * xs, 2 * ys, np.ones(len(xs))]
        b = xs ** 2 + ys ** 2
        cx, cy, c = np.linalg.lstsq(A, b, rcond=None)[0]
        r = np.sqrt(c + cx ** 2 + cy ** 2)
        d = np.abs(np.hypot(xs - cx, ys - cy) - r)
        keep = d < np.percentile(d, 80)
        xs, ys = xs[keep], ys[keep]
    return cx, cy, r


def find_disc(im):
    cx, cy, r = fit_circle(content_mask(im))
    # controle via het omsluitende kader; bij twijfel (lage contrast) dat gebruiken
    for thr in (30, 15, 8):
        ys, xs = np.where(content_mask(im, thr))
        if len(xs) == 0:
            continue
        bx0, bx1 = np.percentile(xs, [0.5, 99.5]); by0, by1 = np.percentile(ys, [0.5, 99.5])
        bcx, bcy, br = (bx0 + bx1) / 2, (by0 + by1) / 2, min(bx1 - bx0, by1 - by0) / 2
        if br > 0.35 * min(im.size):
            break
    if abs(r - br) > 0.05 * br or np.hypot(cx - bcx, cy - bcy) > 0.05 * br:
        cx, cy, r = bcx, bcy, br
    return cx, cy, r


def refine_circle(im, cx, cy, r, lo=0.9, hi=1.08, alpha=None):
    """Cirkel nauwkeurig op de buitenrand: langs 720 stralen de sterkste
    overgang zoeken (rand van de schijf tegen het deksel) en daar robuust een
    cirkel door leggen. Werkt ook bij witte cd's op een wit deksel."""
    import cv2
    g = cv2.GaussianBlur(np.asarray(im.convert('L')).astype(np.float32), (0, 0), 2)
    H, W = g.shape
    t = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    rr = np.arange(r * lo, r * hi, 1.0)
    X = cx + np.outer(np.cos(t), rr); Y = cy + np.outer(np.sin(t), rr)
    ok = (X >= 0) & (X < W - 1) & (Y >= 0) & (Y < H - 1)
    P = cv2.remap(g, X.astype(np.float32), Y.astype(np.float32), cv2.INTER_LINEAR)
    D = np.abs(np.diff(P, axis=1)); D[~ok[:, 1:]] = 0
    if alpha is not None:
        # rand van het transparante gebied (samengevoegde scan) is niet de plaatrand
        al = cv2.erode(np.asarray(alpha), np.ones((15, 15), np.uint8)).astype(np.float32)
        A = cv2.remap(al, X.astype(np.float32), Y.astype(np.float32), cv2.INTER_NEAREST)
        D[A[:, 1:] < 250] = 0
    # buitenste duidelijke overgang (de rand), niet de sterkste (dat kan tekst zijn)
    mx = D.max(axis=1, keepdims=True)
    strong = D >= 0.5 * mx
    k = D.shape[1] - 1 - np.argmax(strong[:, ::-1], axis=1)
    strength = D[np.arange(len(t)), k]
    sel = strength > np.percentile(strength, 30)
    px = X[np.arange(len(t)), k][sel]; py = Y[np.arange(len(t)), k][sel]
    if len(px) < 50:
        return cx, cy, r
    for _ in range(4):
        A = np.column_stack([px, py, np.ones_like(px)]); bvec = -(px ** 2 + py ** 2)
        c, *_ = np.linalg.lstsq(A, bvec, rcond=None)
        ncx, ncy = -c[0] / 2, -c[1] / 2; nr = np.sqrt(ncx ** 2 + ncy ** 2 - c[2])
        res = np.abs(np.hypot(px - ncx, py - ncy) - nr); keep = res < max(2.5 * np.median(res), 2)
        px, py = px[keep], py[keep]
    if abs(nr - r) > 0.08 * r or np.hypot(ncx - cx, ncy - cy) > 0.08 * r:
        return cx, cy, r
    return float(ncx), float(ncy), float(nr)


def find_record(im, seed=1):
    """Grootste goed-ondersteunde cirkel in de randen van de scan (RANSAC).
    Werkt ook als de achtergrond niet egaal is (samengestelde scans, zwarte hoeken)."""
    small = im.convert('L').copy(); scale = 700 / max(im.size); small = small.resize((int(im.width * scale), int(im.height * scale)))
    a = np.asarray(small).astype(float)
    gx = np.zeros_like(a); gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]; gy[1:-1, :] = a[2:, :] - a[:-2, :]
    g = np.hypot(gx, gy); ys, xs = np.where(g > max(40, np.percentile(g, 92)))
    rng = np.random.default_rng(seed); n = len(xs); best = None
    mind = min(a.shape); tol = 2.5
    for _ in range(4000):
        i = rng.choice(n, 3, replace=False)
        (x1, y1), (x2, y2), (x3, y3) = zip(xs[i], ys[i])
        d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        if abs(d) < 1e-6: continue
        ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
        uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
        r = np.hypot(x1 - ux, y1 - uy)
        if not (0.25 * mind < r < 0.6 * mind): continue
        inl = np.abs(np.hypot(xs - ux, ys - uy) - r) < tol
        # dekking = hoeveel van de omtrek echt rand heeft
        ang = np.floor((np.arctan2(ys[inl] - uy, xs[inl] - ux) + np.pi) / (2 * np.pi) * 180).astype(int)
        cov = len(np.unique(ang)) / 180
        if cov < 0.6: continue
        key = (round(r / 4), cov)          # grootste cirkel eerst, dan beste dekking
        if best is None or key > best[0]: best = (key, ux, uy, r)
    if best is None:
        return find_disc(im)
    _, ux, uy, r = best
    return ux / scale, uy / scale, r / scale


def printed_radius(im, cx, cy, r):
    """Straal waar de bedrukking ophoudt en de doorzichtige buitenring begint."""
    a = np.asarray(im.convert('L')).astype(float)
    rs = np.linspace(0.90, 1.0, 60); prof = []
    ang = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    for f in rs:
        x = (cx + f * r * np.cos(ang)).astype(int); y = (cy + f * r * np.sin(ang)).astype(int)
        ok = (x >= 0) & (y >= 0) & (x < a.shape[1]) & (y < a.shape[0])
        prof.append(np.median(a[y[ok], x[ok]]))
    g = np.abs(np.diff(prof))
    if g[:-3].max() > 12:
        i = int(np.argmax(g[:-3]))
        if rs[i] > 0.93:
            return rs[i] * r * 0.995
    return 0.975 * r


def to_srgb(im):
    """Eigen kleurprofiel van de scan (bv. 'Generic RGB') omzetten naar sRGB.
    Een alfakanaal dat (vrijwel) overal ondoorzichtig is (VueScan-png) telt niet als transparant."""
    import io
    from PIL import ImageCms
    icc = im.info.get('icc_profile')
    has_alpha = im.mode in ('RGBA', 'LA') or 'transparency' in im.info
    out = im.convert('RGBA' if has_alpha else 'RGB')
    if icc:
        p = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        if 'srgb' not in ImageCms.getProfileDescription(p).lower():
            out = ImageCms.profileToProfile(out, p, ImageCms.createProfile('sRGB'), outputMode=out.mode)
    return out


def load_rgb(src):
    """RGB + alfa (of None). Samengevoegde scans (scan_stitch.py) hebben
    transparantie: die wordt wit (zoals het deksel) voor het zoeken, en de alfa
    gaat mee in het eindmasker zodat lege randjes niet zwart worden."""
    raw = to_srgb(Image.open(src))
    if raw.mode != 'RGBA':
        return raw, None
    rgba = raw; alpha = rgba.getchannel('A')
    im = Image.new('RGB', rgba.size, (255, 255, 255)); im.paste(rgba, mask=alpha)
    return im, alpha


def label_line_refine(label):
    """Laatste paar graden: draai zo dat de tekstregels zo scherp mogelijk
    horizontaal liggen (rijprofiel). Alleen binnen ±LABEL_REFINE graden, na de
    grove meting; licht en donker drukwerk tellen allebei."""
    import cv2
    g = np.asarray(label.convert('L').resize((1200, 1200))).astype(np.float32)
    n = 1200
    yy, xx = np.ogrid[:n, :n]
    d = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
    ring = (d < .75) & (d > .15)
    ink = ((np.abs(g - np.median(g[ring])) > 45) & ring).astype(np.float32)
    if ink.mean() < .002:
        return 0.0
    best = max((float(cv2.warpAffine(ink, cv2.getRotationMatrix2D((n / 2, n / 2), a, 1), (n, n)).sum(1).var()), a)
               for a in np.arange(-LABEL_REFINE, LABEL_REFINE + .01, .1))
    if abs(best[1]) >= LABEL_REFINE - .05 or abs(best[1]) < LABEL_REFINE_MIN:
        return 0.0          # op de rand: geen duidelijke regels; klein: ruis van het ontwerp
    return float(best[1])


def disc_text_angle(sq, vinyl=False):
    """Hoek (graden, tegen de klok in) waarmee de rechte tekst op een cd/label
    horizontaal komt te staan. Ronde randtekst geeft geen voorkeursrichting,
    rechte regels wel. Daarna: liggen de regels horizontaal (rijen tekst) of
    verticaal? Zo blijft alleen 'goed' of 'ondersteboven' over."""
    import cv2
    a = np.asarray(sq.convert('L')).astype(np.float32)
    n = a.shape[0]; yy, xx = np.mgrid[0:n, 0:n]; rr = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
    ring = (rr > 0.07) & (rr < 0.33) if vinyl else (rr > 0.2) & (rr < 0.86)
    g = cv2.GaussianBlur(a, (0, 0), 1.0)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)
    mag = np.hypot(gx, gy); ang = ((np.degrees(np.arctan2(gy, gx)) + 45) % 90) - 45
    m = ring & (mag > np.percentile(mag[ring], 85))
    bins = np.arange(-45, 45.01, 0.25)
    h, _ = np.histogram(ang[m], bins=bins, weights=mag[m])
    h = np.convolve(np.r_[h[-20:], h, h[:20]], np.exp(-0.5 * (np.arange(-12, 13) / 3) ** 2), 'same')[20:-20]
    if h.max() < 1.6 * np.median(h):
        return None                                    # geen duidelijke rechte tekst
    a0 = float(bins[np.argmax(h)] + 0.125)
    # rijen of kolommen? na rechtzetten: tekstregels geven een gestreept rijprofiel
    best = None
    for extra in (0, 90):
        r = np.asarray(sq.convert('L').rotate(a0 + extra, resample=Image.BILINEAR, fillcolor=255)).astype(np.float32)
        b = (r < np.percentile(r[ring], 15)) & ring
        p = b.sum(axis=1).astype(float)
        sc = np.var(np.diff(p))
        if best is None or sc > best[0]:
            best = (sc, a0 + extra)
    return ((best[1] + 180) % 360) - 180


def ocr_tool():
    """Klein Swift-programmaatje (Apple Vision tekstherkenning); wordt bij het
    eerste gebruik gecompileerd naast dit script. None als dat niet lukt."""
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, 'sleeve_ocr.swift'); exe = os.path.join(here, 'sleeve_ocr')
    if os.path.exists(exe) and os.path.getmtime(exe) >= os.path.getmtime(src):
        return exe
    r = subprocess.run(['swiftc', '-O', src, '-o', exe], capture_output=True)
    return exe if r.returncode == 0 else None


_WORDS = None


def _words():
    global _WORDS
    if _WORDS is None:
        _WORDS = set()
        for p in ('/usr/share/dict/words', '/usr/share/dict/web2'):
            if os.path.exists(p):
                _WORDS |= {w.strip().lower() for w in open(p, errors='ignore') if len(w.strip()) >= 3}
        _WORDS |= {'anouk', 'anoukurbansolitude', 'side', 'kant', 'goldilox', 'universal', 'music', 'vinyl', 'records', 'dino',
                   'emi', 'bmg', 'sony', 'promotional', 'reserved', 'rights', 'stemra', 'biem', 'the', 'and'}
    return _WORDS


def reading_sweep(img):
    """Terugval als de hoek- en leesrichtingmeting het opgeven: draai het label in
    stappen van 15 graden (met de vier standen van de tekstherkenning samen de hele
    cirkel) en neem de stand waarin de meeste echte woorden gelezen worden.
    Geeft de hoek (tegen de klok in) of None als geen stand duidelijk wint."""
    import subprocess, tempfile
    exe = ocr_tool()
    if exe is None:
        return None
    W = _words(); score = {}
    for extra in range(0, 90, 15):
        rotated = img.rotate(extra, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            rotated.convert('RGB').save(f.name)
            try:
                out = subprocess.run([exe, f.name], capture_output=True, text=True, timeout=90).stdout
            except subprocess.TimeoutExpired:
                continue
        for ln in out.strip().split('\n'):
            p = ln.split('\t', 2)
            if len(p) < 3:
                continue
            total = (extra - int(p[0])) % 360
            for tok in re.findall(r"[A-Za-z]{3,}", p[2]):
                if tok.lower() in W:
                    score[total] = score.get(total, 0.0) + len(tok) * float(p[1])
    if not score:
        return None
    best = max(score, key=score.get)
    rest = max([v for a, v in score.items() if min(abs(a - best), 360 - abs(a - best)) > 15] or [0.0])
    if score[best] < 8 or score[best] < SWEEP_MARGIN * rest:
        return None
    return float(((best + 180) % 360) - 180)


def reading_quadrant(img):
    """Welke kant is boven? Apple's tekstherkenning leest de tekst in alle vier
    de standen; de stand met de meeste echte woorden wint. Geeft 0/90/180/270
    (graden tegen de klok in) of None als het niet duidelijk is."""
    import subprocess, tempfile
    exe = ocr_tool()
    if exe is None:
        return None
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        bg = Image.new('RGB', img.size, 'white'); bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
        bg.save(f.name)
        try:
            out = subprocess.run([exe, f.name], capture_output=True, text=True, timeout=90).stdout
        except subprocess.TimeoutExpired:
            return None
    W = _words(); score = {0: 0.0, 90: 0.0, 180: 0.0, 270: 0.0}
    for ln in out.strip().split('\n'):
        p = ln.split('\t', 2)
        if len(p) < 3:
            continue
        for tok in re.findall(r"[A-Za-z]{3,}", p[2]):
            if tok.lower() in W:
                score[int(p[0])] += len(tok) * float(p[1])
    best = max(score, key=score.get); rest = sorted(score.values())[-2]
    if score[best] < 6 or score[best] < 1.5 * rest:
        return None
    # stand o = beeld zo draaien dat het rechtop leest; terug als hoek tegen de klok in
    return {0: 0, 90: 90, 180: 180, 270: 270}[best]


def clean_radius(im, cx, cy, r, alpha=None):
    """Straal waarbinnen de plaat overal zijn eigen kleur heeft: de lichte
    afgeschuinde rand (en schaduw) van de plaat valt erbuiten. Per richting de
    buitenste straal met plaatkleur; het kleinste deel (5%) bepaalt de cirkel."""
    import cv2
    a = np.asarray(im).astype(np.float32)
    lab = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2LAB).astype(np.float32)
    t = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    rr = np.arange(r * 0.90, r * 1.01, 0.5)
    X = (cx + np.outer(np.cos(t), rr)).astype(np.float32); Y = (cy + np.outer(np.sin(t), rr)).astype(np.float32)
    P = np.stack([cv2.remap(lab[..., k], X, Y, cv2.INTER_LINEAR) for k in range(3)], -1)
    ok = np.ones(P.shape[:2], bool)
    if alpha is not None:
        ok = cv2.remap(np.asarray(alpha).astype(np.float32), X, Y, cv2.INTER_NEAREST) > 250
    inner = rr < r * 0.95
    ref = np.median(P[:, inner].reshape(-1, 3), axis=0)
    d = np.sqrt(((P - ref) ** 2).sum(-1))
    # tolerantie: wat de plaat zelf aan variatie heeft (groeven, licht)
    tol = max(14.0, float(np.percentile(d[:, inner], 95)) * 1.3)
    good = (d < tol) & ok
    out = []
    for g in good:
        bad = np.where(~g & (rr >= r * 0.95))[0]
        out.append(rr[bad[0]] if len(bad) else rr[-1])
    out = np.array(out)
    R = float(np.percentile(out, 5)) - 1.5
    return min(R, r)


def already_cut(alpha):
    """Is dit een al uitgeknipte schijf (ronde alfa met een transparant gat in
    het midden)? Dan (cx, cy, r) van die alfa, anders None."""
    import cv2
    if alpha is None:
        return None
    a = np.asarray(alpha) > 128
    H, W = a.shape
    if a[H // 2 - 3:H // 2 + 4, W // 2 - 3:W // 2 + 4].any():   # geen gat in het midden
        return None
    n, lab, st, _ = cv2.connectedComponentsWithStats(a.astype(np.uint8))
    if n < 2:
        return None
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    (cx, cy), r = cv2.minEnclosingCircle(cv2.findNonZero((lab == k).astype(np.uint8)))
    filled = cv2.findNonZero((lab == k).astype(np.uint8)).shape[0]
    holes = np.pi * r * r - filled
    # schijf: bijna de hele cirkel gevuld, op het gat na (max ~25% van de oppervlakte)
    if not (0.0 <= holes / (np.pi * r * r) < 0.25) or r < 0.4 * min(H, W):
        return None
    return float(cx), float(cy), float(r)


def clean_cd_circle(im,cx,cy,r):
    """Fit the printed surface, then centre a safe circular crop on circular type.
    Silver rings and their shadows are excluded; no artwork is warped."""
    import cv2
    scale = min(1.,1600/max(im.size))
    small = im.resize((round(im.width*scale),round(im.height*scale)),Image.LANCZOS) if scale<1 else im
    gray = np.asarray(small.convert('L'))
    # Detect at one fixed scale: fitting at different resolutions must not alter the crop.
    ex,ey,er = find_disc(small)
    ex,ey,er = refine_circle(small,ex,ey,er)
    angles = np.linspace(0,2*np.pi,1440,endpoint=False)
    radii = np.arange(.92*er,1.04*er,.25)
    X = (ex+np.cos(angles[:,None])*radii).astype(np.float32)
    Y = (ey+np.sin(angles[:,None])*radii).astype(np.float32)
    smooth = cv2.GaussianBlur(gray.astype(np.float32),(0,0),.8)
    polar = cv2.remap(smooth,X,Y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    polar = cv2.blur(polar,(1,41),borderType=cv2.BORDER_REFLECT)
    derivative = -np.diff(polar,axis=1)
    band = (radii[:-1]>.94*er)&(radii[:-1]<.992*er)
    points = []
    for i,d in enumerate(derivative):
        d = np.where(band,d,0)
        candidates = np.flatnonzero((d>max(.4,.15*d.max()))&band)
        if len(candidates):
            first = candidates[0]; k = first+int(np.argmax(d[first:first+20]))
            points.append((X[i,k],Y[i,k]))
    points = np.asarray(points,np.float32)
    if len(points)<1000:
        raise ValueError('Bedrukte cd-rand niet betrouwbaar gevonden; origineel behouden.')
    keep = np.ones(len(points),bool)
    for _ in range(6):
        ellipse = cv2.fitEllipse(points[keep])
        (px,py),(width,height),angle = ellipse
        phi = np.radians(angle); R = np.array([[np.cos(phi),np.sin(phi)],[-np.sin(phi),np.cos(phi)]])
        local = (points-[px,py])@R.T
        error = np.abs(np.hypot(local[:,0]/(width/2),local[:,1]/(height/2))-1)*min(width,height)/2
        keep = error<max(1.5,3*np.median(error))
    if keep.mean()<.65 or max(width,height)/min(width,height)>1.04:
        raise ValueError('Cd-rand wijkt te veel af van een cirkel; controle nodig.')
    # Glyph centroids on circular copyright text provide an independent centre.
    yy,xx = np.indices(gray.shape); distance = np.hypot(xx-ex,yy-ey)
    ink = ((gray<110)&(distance>.84*er)&(distance<.99*er)).astype(np.uint8)
    n,labels,stats,centroids = cv2.connectedComponentsWithStats(ink)
    glyphs = np.array([centroids[i] for i in range(1,n) if 8<stats[i,cv2.CC_STAT_AREA]<220 and max(stats[i,cv2.CC_STAT_WIDTH],stats[i,cv2.CC_STAT_HEIGHT])<30])
    centre = np.array([px,py]); best = None
    if len(glyphs)>=40:
        rng = np.random.default_rng(0)
        for _ in range(1200):
            pts = glyphs[rng.choice(len(glyphs),3,replace=False)]
            try: model = np.linalg.solve(np.c_[2*pts,np.ones(3)],(pts*pts).sum(1))
            except np.linalg.LinAlgError: continue
            radius2 = model[2]+(model[:2]**2).sum()
            if radius2<=0: continue
            radius = np.sqrt(radius2)
            if not .84*er<radius<.97*er or np.linalg.norm(model[:2]-centre)>.04*er: continue
            residual = np.abs(np.linalg.norm(glyphs-model[:2],axis=1)-radius)
            k = residual<2.5
            if best is None or k.sum()>best.sum(): best=k
        if best is not None and best.sum()>=40:
            pts=glyphs[best]; model=np.linalg.lstsq(np.c_[2*pts,np.ones(len(pts))],(pts*pts).sum(1),rcond=None)[0]
            coverage = np.ptp(np.unwrap(np.sort(np.arctan2(pts[:,1]-model[1],pts[:,0]-model[0]))))
            if coverage>np.pi/2:
                centre=model[:2]
                print(f'cd-midden gecontroleerd op {len(pts)} letters langs de rand')
    # Circle centred on the type, completely within the fitted printed surface.
    q = R@(centre-[px,py]); dirs = np.stack([np.cos(angles),np.sin(angles)],1)@R.T
    axes = np.array([width/2,height/2]); A=((dirs/axes)**2).sum(1); B=2*(dirs*q/(axes**2)).sum(1); C=((q/axes)**2).sum()-1
    reach = (-B+np.sqrt(B*B-4*A*C))/(2*A)
    radius = float(np.min(reach)-2)
    print(f'bedrukte rand: middelpunt {centre[0]/scale:.1f}, {centre[1]/scale:.1f}; straal {radius/scale:.1f}')
    return float(centre[0]/scale),float(centre[1]/scale),radius/scale


def cut_disc(src, dst, angle=0, size=None, vinyl=False, hole=None, auto=False, allow_incomplete=False):
    """Schijf uitknippen. size=None: volle resolutie (zo groot als de schijf in de scan)."""
    import cv2
    with Image.open(src) as original:
        current_cut = original.info.get('sleeve_disc_cut',original.info.get('anouk_disc_cut')) in ('2','3')
    from scan_progress import progress
    progress('Schijf op volle resolutie openen')
    im, alpha = load_rgb(src)
    progress('Buitenrand en middelpunt bepalen')
    if allow_incomplete and alpha is None: alpha = Image.new("L",im.size,255)
    # zoeken op een werkkopie (snel, weinig geheugen), knippen uit het origineel
    k = min(1.0, 4000 / max(im.size))
    ws = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS) if k < 1 else im
    wa = alpha.resize(ws.size, Image.BILINEAR) if (alpha is not None and k < 1) else alpha
    done = already_cut(wa)
    if done is not None:
        # al eerder uitgeknipt (transparant rondom én gat in het midden): die rand
        # is al goed; alleen opnieuw draaien/opslaan, niet nog eens bijsnijden
        cx, cy, r = done; R = r
        # Already-cut images cannot restore a previously cropped rim; preserve their geometry.
    else:
        cx, cy, r = find_record(ws) if vinyl else find_disc(ws)
        cx, cy, r = refine_circle(ws, cx, cy, r, alpha=wa)
        # vinyl: de hele plaat (binnen de lichte schuine rand), niet het label; cd: tot de bedrukte rand
        R = clean_radius(ws, cx, cy, r, wa) if vinyl else printed_radius(ws, cx, cy, r)
        if not vinyl:
            face = np.asarray(ws.convert('RGB'))
            neutral = (face.max(2)-face.min(2)<45) & (face.mean(2)>140)
            if neutral.mean()>.5:
                cx, cy, R = clean_cd_circle(ws,cx,cy,R)
    cx, cy, R = cx / k, cy / k, R / k
    if min(cx-R, cy-R, im.width-(cx+R), im.height-(cy+R)) < -max(2, .002*R) and not allow_incomplete:
        raise ValueError('De schijf valt buiten deze scan. Selecteer alle deelscans samen via Sleeve · Scans verwerken.')
    hole = hole if hole is not None else (HOLE_VINYL if vinyl else HOLE)
    n = int(round(2 * R)); x0, y0 = int(round(cx - R)), int(round(cy - R))
    box = (x0, y0, x0 + n, y0 + n)
    size = size or n
    sq = im.crop(box)
    im.close()
    if size != n:
        sq = sq.resize((size, size), Image.LANCZOS)
    if auto:
        progress('Tekst op het etiket recht draaien')
        skew_rejected = False
        small = sq.resize((1200, 1200), Image.LANCZOS) if size > 1200 else sq
        if vinyl:                                        # alleen het label lezen, groot genoeg
            lb = int(size * 0.18); c0 = size // 2
            lab_im = sq.crop((c0 - lb, c0 - lb, c0 + lb, c0 + lb)).resize((1600, 1600), Image.LANCZOS)
            # Hoek op het label zelf meten: op de hele plaat (1200 px) is de
            # labeltekst te klein en bleef een scheef label scheef.
            ta = disc_text_angle(lab_im) or 0.0
            if abs(((ta + 45) % 90) - 45) > MAX_LABEL_SKEW:
                print(f'tekst: rechtzethoek {ta:+.1f} graden onwaarschijnlijk, alleen kwartslagen')
                ta = 0.0; skew_rejected = True
            else:
                ta += label_line_refine(lab_im.rotate(ta, resample=Image.BICUBIC, fillcolor=(255, 255, 255)))
            t1 = lab_im.rotate(ta, resample=Image.BICUBIC, fillcolor=(255, 255, 255)) if ta else lab_im
        else:
            ta = disc_text_angle(small, vinyl) or 0.0
            t1 = small.rotate(ta, resample=Image.BICUBIC, fillcolor=(255, 255, 255)) if ta else small
        q = reading_quadrant(t1)                         # rechtop, op z'n kant of ondersteboven?
        # sterk scheef label of geen duidelijke leesrichting: dan is ook de gewone
        # kwartslag onbetrouwbaar (TGHT) en beslist de leesstand-zoektocht
        swept = reading_sweep(lab_im) if vinyl and (q is None or skew_rejected) else None
        if q is not None and swept is None:
            ta = ta - q
            angle = ((ta + angle + 180) % 360) - 180
            print(f'tekst rechtop gezet: {ta:+.1f} graden')
        elif swept is not None:
            # Label met een misleidend ontwerp (schuine titel, strepen): de stand
            # waarin de meeste echte woorden leesbaar zijn, in stappen van 15 graden
            swept += label_line_refine(lab_im.rotate(swept, resample=Image.BICUBIC, fillcolor=(255, 255, 255)))
            angle = ((swept + angle + 180) % 360) - 180
            print(f'tekst rechtop gezet via leesstand: {swept:+.1f} graden')
        elif ta and not skew_rejected:
            # Leesrichting onbekend, scheefstand wel gemeten: die alvast rechtzetten;
            # de kwartslag volgt uit de Discogs-foto of de gebruiker (DEENA A op 600 dpi).
            angle = ((ta + angle + 180) % 360) - 180
            print(f'tekst: geen duidelijke leesrichting, alleen scheefstand rechtgezet: {ta:+.1f} graden')
        else:
            print('tekst: geen duidelijke leesrichting gevonden, niet gedraaid')
    if angle:
        sq = sq.rotate(angle, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    m = np.zeros((size, size), np.uint8)                 # schijf met gat, zachte randen
    c16 = int(round(size / 2 * 16))
    cv2.circle(m, (c16, c16), int(size / 2 * 16) - 8, 255, -1, cv2.LINE_AA, shift=4)
    cv2.circle(m, (c16, c16), int(size * hole / 2 * 16), 0, -1, cv2.LINE_AA, shift=4)
    if alpha is not None:
        progress('Uitsnede op ontbrekende delen controleren')
        al = alpha.crop(box)
        if size != n:
            al = al.resize((size, size), Image.LANCZOS)
        if angle:
            al = al.rotate(angle, resample=Image.BICUBIC, fillcolor=0)
        aa = np.asarray(al, np.uint8)
        expected = m > 250
        # Ignore antialiasing at the perimeter, but reject real missing scan areas.
        interior = cv2.erode(expected.astype(np.uint8), np.ones((7,7), np.uint8)) > 0
        missing = interior & (aa < 128)
        if missing.sum() > 0.002 * max(1, interior.sum()) and not allow_incomplete:
            raise ValueError(f'Onvolledige schijf: {100*missing.sum()/max(1,interior.sum()):.1f}% ontbreekt. Selecteer alle deelscans samen.')
        m = np.minimum(m, aa)
        del aa,expected,interior,missing
        al.close();alpha.close()
    from PIL.PngImagePlugin import PngInfo
    metadata = PngInfo(); metadata.add_text('sleeve_disc_cut','3')
    out = sq.convert('RGBA'); sq.close(); out.putalpha(Image.fromarray(m))
    # Clear hidden pixels in place; avoid another full RGBA copy on 8 GB Macs.
    transparent = Image.fromarray(m).point([255]+[0]*255)
    out.paste((0,0,0,0),(0,0,size,size),transparent)
    progress('Uitgesneden schijf opslaan')
    out.save(dst, compress_level=1, pnginfo=metadata)
    print(f'uitgeknipt: {size}x{size} px')


def _bbox_area(mask_img):
    a = np.asarray(mask_img) > 128
    rows = np.where(a.mean(axis=1) > 0.02)[0]; cols = np.where(a.mean(axis=0) > 0.02)[0]
    if not len(rows) or not len(cols):
        return 1e18
    return (rows[-1] - rows[0]) * (cols[-1] - cols[0])


def skew_angle(im, maxdeg=8.0, mask=None):
    """Hoek waarbij de hoes het kleinste rechte kader heeft = recht."""
    if mask is None:
        small = im.copy(); small.thumbnail((600, 600))
        mask = content_mask(small)
    else:
        mask = np.asarray(Image.fromarray((mask * 255).astype('uint8')).resize(
            (max(1, im.width * 600 // max(im.size)), max(1, im.height * 600 // max(im.size))))) > 128
    m = Image.fromarray((mask * 255).astype('uint8'))
    def area(a): return _bbox_area(m.rotate(a, resample=Image.NEAREST, expand=True, fillcolor=0))
    best = min(np.arange(-maxdeg, maxdeg + 0.01, 0.5), key=area)
    best = min(np.arange(best - 0.5, best + 0.51, 0.1), key=area)
    return float(best) if abs(best) >= 0.3 and area(best) < 0.995 * area(0) else 0.0


def dominant_angle(rgb, valid, maxdeg=8.0):
    """Hoek om recht te zetten uit de hoofdrichting van alle randen in de hoes
    (tekst, drukwerk, hoesranden). Randen naast niet-gescande (transparante)
    delen tellen niet: een kaarsrechte scanrand zou de hoek scheef trekken."""
    import cv2
    s = 1600 / max(rgb.shape[:2])
    small = cv2.resize(rgb, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    v = cv2.resize(valid.astype(np.uint8), (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
    v = cv2.erode(v, np.ones((9, 9), np.uint8)) > 0
    g = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.2)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy); a = ((np.degrees(np.arctan2(gy, gx)) + 45) % 90) - 45
    m = v & (mag > np.percentile(mag[v], 90)) & (np.abs(a) <= maxdeg)
    bins = np.arange(-maxdeg, maxdeg + 0.05, 0.05)
    h, _ = np.histogram(a[m], bins=bins, weights=mag[m])
    h = np.convolve(h, np.exp(-0.5 * (np.arange(-20, 21) / 6) ** 2), 'same')
    if h.max() < 2.2 * np.median(h):                   # geen duidelijke richting (geen tekst): niet draaien
        return 0.0
    return float(bins[np.argmax(h)] + 0.025)


def cover_rect(im):
    """Kleinste gedraaide rechthoek om de hoes, op volle schaal: ((cx, cy), (w, h), hoek).
    Deksel = egale kleur van de scanrand; de hoes = grootste aaneengesloten vlak
    dat daar duidelijk van afwijkt (stofjes en schaduwlijntjes vallen weg)."""
    import cv2
    a = np.asarray(im)
    s = 1500 / max(a.shape[:2])
    sm = cv2.resize(a, None, fx=s, fy=s, interpolation=cv2.INTER_AREA).astype(np.int32)
    edge = np.concatenate([sm[2], sm[-3], sm[:, 2], sm[:, -3]])
    lid = np.median(edge, axis=0)
    m = (np.abs(sm - lid).sum(axis=2) > 24).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2:
        return None
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    if st[k, cv2.CC_STAT_AREA] < 0.2 * m.size:
        return None
    pts = cv2.findNonZero((lab == k).astype(np.uint8))
    (cx, cy), (w, h), ang = cv2.minAreaRect(pts)
    if ang > 45: ang -= 90; w, h = h, w
    if ang < -45: ang += 90; w, h = h, w
    return (cx / s, cy / s), (w / s, h / s), ang


def edge_rect(im):
    """Voor witte hoezen op het witte deksel (kleur zegt dan niets): de hoes
    zoeken aan zijn snijranden, die als dunne lichte of donkere lijn te zien
    zijn. Per zijde de buitenste lange rechte lijn in de buitenste 12%.
    Geeft ((cx, cy), (w, h), hoek) zoals cover_rect, of None."""
    import cv2
    g0 = np.asarray(im.convert('L'))
    s = 1600 / max(g0.shape)
    g = cv2.resize(g0, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    H, W = g.shape
    # hoek uit de lange rechte lijnen in de buitenste band (de snijranden zelf)
    e0 = cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 8, 24)
    L = cv2.HoughLinesP(e0, 1, np.pi / 3600, 150, minLineLength=int(0.4 * min(H, W)), maxLineGap=25)
    phi = 0.0
    if L is not None:
        L = np.asarray(L).reshape(-1, 4).astype(float)
        ang = np.degrees(np.arctan2(L[:, 3] - L[:, 1], L[:, 2] - L[:, 0])); ang = ((ang + 45) % 90) - 45
        mx = (L[:, 0] + L[:, 2]) / 2; my = (L[:, 1] + L[:, 3]) / 2
        band = (np.minimum(mx, W - mx) < 0.12 * W) | (np.minimum(my, H - my) < 0.12 * H)
        ok = band & (np.abs(ang) < 6)
        if ok.any():
            ln = np.hypot(L[:, 2] - L[:, 0], L[:, 3] - L[:, 1])
            phi = float(np.median(np.repeat(ang[ok], (ln[ok] / 10).astype(int) + 1)))
    R = cv2.getRotationMatrix2D((W / 2, H / 2), phi, 1.0)          # recht leggen
    gr = cv2.warpAffine(g, R, (W, H), borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    inside = cv2.warpAffine(np.ones_like(g), R, (W, H), flags=cv2.INTER_NEAREST)
    e = 4                                              # scanrand zelf niet meetellen
    inside = cv2.erode(inside, np.ones((2 * e + 1, 2 * e + 1), np.uint8)) > 0
    # mediaanhelderheid per kolom/rij over het middendeel: tekst telt niet mee,
    # de snijrand (ook een zachte) is een stap in dat profiel
    gm = np.where(inside, gr, np.nan)
    with np.errstate(all='ignore'):
        colp = np.nanmedian(gm[int(H * .2):int(H * .8)], axis=0)
        rowp = np.nanmedian(gm[:, int(W * .2):int(W * .8)], axis=1)
    def outer(p, lo, hi, from_end):
        p = np.asarray(p, float); k = 3
        step = np.full(len(p), np.nan)
        step[k:-k] = np.abs(p[2 * k:] - p[:-2 * k])
        rng = range(hi - 1, lo - 1, -1) if from_end else range(lo, hi)
        for i in rng:
            if np.isfinite(step[i]) and step[i] >= 4:
                # de snijrand is een dun schaduwlijntje (dal) of lichtrandje (top)
                # vlak na de eerste stap; neem dat, niet een rand van het drukwerk
                win = int(0.025 * len(p))
                a_, b_ = (max(lo, i - win), i + 1) if from_end else (i, min(hi, i + win + 1))
                seg = np.nan_to_num(p[a_:b_], nan=np.nanmedian(p))
                outside = np.nanmedian(p[max(0, i - 8):i]) if not from_end else np.nanmedian(p[i + 1:i + 9])
                if not np.isfinite(outside):
                    outside = seg[-1] if from_end else seg[0]
                q = seg[::-1] if from_end else seg           # van buiten naar binnen
                ext = None
                for j0 in range(len(q)):
                    if q[j0] <= outside - 10:                    # schaduwlijn (dal)?
                        jm = j0
                        while jm + 1 < len(q) and q[jm + 1] <= q[jm]:
                            jm += 1
                        if jm + 1 < len(q) and q[jm + 1:jm + 16].max() - q[jm] >= 10:
                            ext = jm
                        break
                    if q[j0] >= outside + 8:                     # lichtrandje (top)?
                        jm = j0
                        while jm + 1 < len(q) and q[jm + 1] >= q[jm]:
                            jm += 1
                        ext = jm
                        break
                if ext is not None:
                    return (b_ - 1 - ext - 1) if from_end else (a_ + ext + 1)
                seg2 = np.nan_to_num(step[a_:b_], nan=0.0)
                return a_ + int(np.argmax(seg2))
        return None
    l = outer(colp, 0, int(W * .12), False); r = outer(colp, int(W * .88), W, True)
    t = outer(rowp, 0, int(H * .12), False); b = outer(rowp, int(H * .88), H, True)
    if sum(v is None for v in (l, t, r, b)) > 1:          # minstens 3 snijranden zichtbaar
        return None
    # zijde zonder lijn: hoes loopt tot de scanrand
    l = 0 if l is None else l; t = 0 if t is None else t
    r = W - 1 if r is None else r; b = H - 1 if b is None else b
    if (r - l) < 0.5 * W or (b - t) < 0.5 * H:
        return None
    cxr, cyr = (l + r) / 2, (t + b) / 2
    Ri = cv2.invertAffineTransform(R)
    cx, cy = Ri @ np.array([cxr, cyr, 1.0])
    return (cx / s, cy / s), ((r - l) / s, (b - t) / s), phi


def good_rect(im):
    """cover_rect, maar alleen als de hoes helemaal op de scan ligt (deksel
    rondom), het grootste deel van de scan vult en niet erg scheef ligt."""
    rect = cover_rect(im)
    if rect is None:
        return None
    (cx, cy), (rw, rh), ang = rect
    W, H = im.size; rad = np.radians(abs(ang))
    bw = rw * np.cos(rad) + rh * np.sin(rad); bh = rw * np.sin(rad) + rh * np.cos(rad)
    margin = min(cx - bw / 2, cy - bh / 2, W - cx - bw / 2, H - cy - bh / 2)
    if rw < rh * 0.5 or rh < rw * 0.5 or abs(ang) > 6 or margin < 0.002 * max(W, H) or rw * rh < 0.35 * W * H:
        return None
    return rect


def print_frame(g):
    """Gedrukt kader (lange rechte lijnen bij de rand)? Zoekt per zijde in de
    buitenste 22% de sterkste rechte lijn over (bijna) de hele lengte.
    Geeft (links, boven, rechts, onder) in pixels of None."""
    import cv2
    gf = cv2.GaussianBlur(g.astype(np.float32), (0, 0), 1.5)
    gx = np.abs(cv2.Sobel(gf, cv2.CV_32F, 1, 0)); gy = np.abs(cv2.Sobel(gf, cv2.CV_32F, 0, 1))
    H, W = g.shape[:2]
    # een lijn telt alleen als hij over het middendeel doorloopt
    px = (gx[int(H * .15):int(H * .85)] > 25).mean(axis=0); py = (gy[:, int(W * .15):int(W * .85)] > 25).mean(axis=1)
    def peak(p, lo, hi, from_end=False):
        # buitenste sterke lijn (de buitenkant van het kader), niet de sterkste
        seg = p[lo:hi]; idx = np.where(seg >= 0.6)[0]
        if not len(idx):
            i = lo + int(np.argmax(seg)); return i, p[i]
        i = lo + (idx[-1] if from_end else idx[0])
        j = i                                              # top van die piek
        while 0 < j < len(p) - 1 and p[j + (-1 if from_end else 1)] > p[j]:
            j += (-1 if from_end else 1)
        return j, p[j]
    l, sl = peak(px, int(W * .01), int(W * .22)); r, sr = peak(px, int(W * .78), int(W * .99), True)
    t, st_ = peak(py, int(H * .01), int(H * .22)); bt, sb = peak(py, int(H * .78), int(H * .99), True)
    if min(sl, sr, st_, sb) < 0.6:
        return None
    return l, t, r, bt


def border_depths(rgb):
    """Effen gekleurde rand rondom (bv. groene of gele hoesrand)? Per zijde: hoe
    ver loopt de kleur van de buitenkant naar binnen door (mediaan over het
    middendeel van die zijde, zodat losse tekst niet telt). Geeft
    (links, boven, rechts, onder) in pixels of None."""
    import cv2
    a = np.asarray(rgb).astype(np.uint8)
    H, W = a.shape[:2]
    lab = cv2.cvtColor(cv2.GaussianBlur(a, (0, 0), 2), cv2.COLOR_RGB2LAB).astype(np.float32)
    lim = int(0.2 * min(H, W)); e = 6
    profs = {'l': np.median(lab[int(H * .2):int(H * .8), :lim], axis=0),
             't': np.median(lab[:lim, int(W * .2):int(W * .8)], axis=1),
             'r': np.median(lab[int(H * .2):int(H * .8), W - lim:][:, ::-1], axis=0),
             'b': np.median(lab[H - lim:, int(W * .2):int(W * .8)][::-1], axis=1)}
    out = {}
    for k, p in profs.items():
        ref = np.median(p[e:e + 20], axis=0)
        d = np.sqrt(((p - ref) ** 2).sum(axis=1))
        idx = np.where(d[e:] > 18)[0]
        if not len(idx):
            return None
        out[k] = e + int(idx[0])
    # de rand moet effen zijn over de hele zijde (geen foto die toevallig donker is)
    strips = {'l': lab[int(H * .1):int(H * .9), e:e + 15], 't': lab[e:e + 15, int(W * .1):int(W * .9)],
              'r': lab[int(H * .1):int(H * .9), W - e - 15:W - e], 'b': lab[H - e - 15:H - e, int(W * .1):int(W * .9)]}
    for k, st in strips.items():
        ref = np.median(st.reshape(-1, 3), axis=0)
        if (np.sqrt(((st.reshape(-1, 3) - ref) ** 2).sum(axis=1)) < 12).mean() < 0.9:
            return None
    refs = [np.median(profs[k][e:e + 20], axis=0) for k in 'ltrb']
    if max(np.linalg.norm(r - refs[0]) for r in refs) > 15:   # niet overal dezelfde randkleur
        return None
    return out['l'], out['t'], W - 1 - out['r'], H - 1 - out['b']


def frame_angle(g):
    """Hoek van de lange rechte drukwerk-lijnen (graden, tegen de klok in om recht te zetten) of None."""
    import cv2
    s = 1600 / max(g.shape)
    sm = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    e = cv2.Canny(cv2.GaussianBlur(sm, (5, 5), 0), 30, 90)
    L = cv2.HoughLinesP(e, 1, np.pi / 3600, 200, minLineLength=int(0.4 * min(sm.shape)), maxLineGap=8)
    if L is None:
        return None
    L = np.asarray(L).reshape(-1, 4)
    ang = np.degrees(np.arctan2(L[:, 3] - L[:, 1], L[:, 2] - L[:, 0])); ang = ((ang + 45) % 90) - 45
    ln = np.hypot(L[:, 2] - L[:, 0], L[:, 3] - L[:, 1])
    ok = np.abs(ang) < 6
    if ln[ok].sum() < 0.8 * min(sm.shape):
        return None
    return float(np.average(ang[ok], weights=ln[ok]))


def crop_single_cover(im, dst, rect, straighten=True, extra=0.0):
    """Losse hoes-scan. Recht op het drukwerk als er een gedrukt kader/lange
    rechte lijnen zijn (anders op de gesneden randen), en bij een kader zo
    bijsnijden dat de rand rondom even breed is."""
    (cx, cy), (rw, rh), ang = rect
    g = np.asarray(im.convert('L'))
    fa = frame_angle(g) if straighten else None
    a = ((fa if fa is not None else ang) if straighten else 0.0) + extra   # zelfde richting als cv2 (omlaag-rechts = +)
    bg = tuple(int(v) for v in np.median(np.concatenate([np.asarray(im)[0], np.asarray(im)[-1]]), axis=0))
    big = im.rotate(a, resample=Image.BICUBIC, expand=True, fillcolor=bg)
    # hoesmasker meedraaien en het grootste rechte kader dat helemaal hoes is
    import cv2
    m = Image.fromarray(np.zeros(g.shape, np.uint8))
    d = ImageDraw.Draw(m)
    box = cv2.boxPoints(((cx, cy), (rw, rh), ang))
    d.polygon([tuple(p) for p in box], fill=255)
    mm = np.asarray(m.rotate(a, resample=Image.NEAREST, expand=True, fillcolor=0)) > 128
    rows = np.where(mm.mean(axis=1) > 0)[0]; cols = np.where(mm.mean(axis=0) > 0)[0]
    t, b, l, r = rows[0], rows[-1], cols[0], cols[-1]
    for _ in range(4000):
        fr = {'t': mm[t, l:r + 1].mean(), 'b': mm[b, l:r + 1].mean(), 'l': mm[t:b + 1, l].mean(), 'r': mm[t:b + 1, r].mean()}
        k = min(fr, key=fr.get)
        if fr[k] >= 0.999:
            break
        if k == 't': t += 1
        elif k == 'b': b -= 1
        elif k == 'l': l += 1
        else: r -= 1
    inset = int(0.006 * max(r - l, b - t)) + 2           # schaduw/rafel van de snijrand
    l, t, r, b = l + inset, t + inset, r - inset, b - inset
    crop = big.crop((l, t, r + 1, b + 1))
    fr = border_depths(crop.convert('RGB'))
    if fr is not None:
        fl, ft, frr, fb = fr; W, H = crop.size
        ms = [fl, ft, W - 1 - frr, H - 1 - fb]
        if max(ms) - min(ms) > 0.04 * max(W, H) or min(ms) < 0.005 * max(W, H):
            fr = None                                      # geen echt kader (of erg scheef gedrukt)
    if fr is not None:
        mrg = min(ms)                                      # zelfde rand rondom
        crop = crop.crop((fl - mrg, ft - mrg, frr + mrg + 1, fb + mrg + 1))
        print(f'kader gevonden: rand rondom {mrg} px')
    crop.save(dst)
    return a


def crop_cover(src, dst, straighten=True, extra=0.0):
    """extra: handmatige bijdraai (graden, tegen de klok in) bovenop de automatische hoek."""
    raw = to_srgb(Image.open(src))
    if raw.mode == 'RGBA' and (np.asarray(raw.getchannel('A')) < 128).mean() < 0.01 \
            and (good_rect(raw.convert('RGB')) is not None or edge_rect(raw.convert('RGB')) is not None):
        raw = raw.convert('RGB')                       # VueScan-png: alfa (vrijwel) overal dicht, gewone scan
    if raw.mode == 'RGBA':
        # samengevoegde scan (scan_stitch.py): transparant = geen scan. Restjes
        # scannerdeksel zijn smalle reepjes; de hoes is waar rijen/kolommen
        # grotendeels gevuld zijn.
        rgba = raw.convert('RGBA')
        im = Image.new('RGB', rgba.size, (255, 255, 255)); im.paste(rgba, mask=rgba.split()[3])
        alpha = np.asarray(rgba.split()[3]) > 128
        valid = alpha.copy()
        a = dominant_angle(np.asarray(im), alpha) if straighten else 0.0
        a = (a if abs(a) >= 0.1 else 0.0) + extra
        if a:
            im = im.rotate(a, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
            valid = np.asarray(Image.fromarray((valid * 255).astype('uint8')).rotate(a, resample=Image.NEAREST, expand=True, fillcolor=0)) > 128
        rows = np.where(valid.mean(axis=1) > 0.85 * valid.mean(axis=1).max())[0]
        cols = np.where(valid.mean(axis=0) > 0.85 * valid.mean(axis=0).max())[0]
        t, b, l, r = rows[0], rows[-1], cols[0], cols[-1]
        # kader naar binnen tot elke rand (bijna) helemaal hoes is: geen witte
        # hoekjes waar geen scan was of die door het draaien leeg zijn
        for _ in range(2000):
            fr = {'t': valid[t, l:r + 1].mean(), 'b': valid[b, l:r + 1].mean(),
                  'l': valid[t:b + 1, l].mean(), 'r': valid[t:b + 1, r].mean()}
            k = min(fr, key=fr.get)
            if fr[k] >= 0.985 or b - t < 100 or r - l < 100:
                break
            if k == 't': t += 1
            elif k == 'b': b -= 1
            elif k == 'l': l += 1
            else: r -= 1
        ix = int((r - l) * 0.006); iy = int((b - t) * 0.006)
        im.crop((l + ix, t + iy, r + 1 - ix, b + 1 - iy)).save(dst)
        return a
    im = raw.convert('RGB')
    rect = good_rect(im)
    if rect is None:
        rect = edge_rect(im)                            # witte hoes op wit deksel
    if rect is not None:
        return crop_single_cover(im, dst, rect, straighten, extra)
    a = (skew_angle(im) if straighten else 0.0) + extra
    if a:
        edge = np.concatenate([np.asarray(im)[0], np.asarray(im)[-1]]); bg = tuple(int(v) for v in np.median(edge, axis=0))
        im = im.rotate(a, resample=Image.BICUBIC, expand=True, fillcolor=bg)
    m = content_mask(im)
    rows = np.where(m.mean(axis=1) > 0.02)[0]; cols = np.where(m.mean(axis=0) > 0.02)[0]
    # 0,4% naar binnen: geen randje achtergrond/schaduw langs de kant
    ix = int((cols[-1] - cols[0]) * 0.004) if a else 0; iy = int((rows[-1] - rows[0]) * 0.004) if a else 0
    im.crop((cols[0] + ix, rows[0] + iy, cols[-1] + 1 - ix, rows[-1] + 1 - iy)).save(dst)
    return a


def main():
    from scan_memory import MemoryLease
    with MemoryLease(48,phase='Beeld uitsnijden'):return main_with_memory()


def main_with_memory():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('modus', choices=['cd', 'vinyl', 'cover', 'map'])
    p.add_argument('invoer'); p.add_argument('uitvoer')
    p.add_argument('--angle', type=float, default=0, help='cd/vinyl: draaiing; hoes: extra bijdraai bovenop de automatische')
    p.add_argument('--gat', type=float, help='gatdiameter als fractie van de schijf (bv. 0.217 voor 7" met groot gat)')
    p.add_argument('--niet-rechtzetten', action='store_true', help='hoes niet automatisch rechtzetten')
    p.add_argument('--angles', help='json met hoeken per bestand (modus map)')
    p.add_argument('--onvolledig-toestaan',action='store_true',help='alleen voor een proef: ontbrekende delen transparant laten')
    p.add_argument('--auto', action='store_true', help='cd/vinyl: rechte tekst automatisch horizontaal (--angle komt erbovenop, bv. 180)')
    a = p.parse_args()
    if a.modus in ('cd', 'vinyl'):
        cut_disc(a.invoer, a.uitvoer, a.angle, vinyl=(a.modus == 'vinyl'), hole=a.gat, auto=a.auto, allow_incomplete=a.onvolledig_toestaan)
    elif a.modus == 'cover':
        hoek = crop_cover(a.invoer, a.uitvoer, not a.niet_rechtzetten, a.angle)
        if hoek: print(f'rechtgezet: {hoek:+.1f} graden')
    else:
        angles = json.load(open(a.angles)) if a.angles else {}
        os.makedirs(a.uitvoer, exist_ok=True)
        for f in sorted(os.listdir(a.invoer)):
            b, ext = os.path.splitext(f)
            if ext.lower() not in ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'):
                continue
            src = os.path.join(a.invoer, f); dst = os.path.join(a.uitvoer, b + '.png')
            if re.search(r'_(side[a-d]|sideone|sidetwo|lp\d?|vinyl)$', b):
                cut_disc(src, dst, angles.get(b, 0), vinyl=True); print('vinyl ', b)
            elif re.search(r'_(cd|cd\d|dvd|dvd\d|disc\d?)$', b):
                cut_disc(src, dst, angles.get(b, 0)); print('schijf', b)
            else:
                crop_cover(src, dst); print('hoes  ', b)


if __name__ == '__main__':
    main()
