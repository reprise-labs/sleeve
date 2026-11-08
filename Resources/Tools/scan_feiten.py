#!/usr/bin/env python3
"""Uitsnijden op feiten, zonder regels.

Invoer: een samengevoegd beeld met de hele scans erin (scan_stitch.py --vorm ruw)
plus het bijbehorende .scans.json (waar elke scan ligt en de dpi).

Feiten (geen afspraken, maar hoe een plaat nu eenmaal is):
  - een flatbed rekt niet: 1 mm is overal even veel pixels (dpi);
  - een LP-hoes is een vierkant van ±307-317 mm, een insert ±290-306 mm;
  - een 12"-plaat is rond, ±290-304 mm (inclusief de afgeronde rand);
  - de rand van een scan is geen rand van de hoes.

Werkwijze: zoek de vorm van de juiste maat waarvan de omtrek het best op randen
in het beeld ligt. Per zijde (of rondom, bij de plaat) wordt gemeten welk deel van
de omtrek echt op een zichtbare rand ligt. Overal duidelijk zichtbaar: GOED.
Ergens niet: TWIJFEL, met een voorstel; de gebruiker beslist.
"""
import argparse, json, math, sys
import numpy as np, cv2

FACTS_MM = {                     # (kleinste, grootste) maat in mm
    'sleeve': (307.0, 317.0),
    'insert': (290.0, 306.0),
    'disc': (290.0, 304.0),
}
PART_SHAPE = {'front': 'sleeve', 'back': 'sleeve', 'inside': 'sleeve', 'insert': 'insert',
              'sidea': 'disc', 'sideb': 'disc', 'sidec': 'disc', 'sided': 'disc'}
WORK_PX_MM = 2.0                 # rekenschaal voor het zoeken
ON_CIRCLE = 0.9                  # zoveel van de gemeten richtingen moet op de cirkel liggen
DISC_EDGE_MM = 1.0               # feit: de rand van een plaat is afgerond, ±1 mm breed; de scanner
                                 # toont die als glans of schaduw. Gesneden wordt op de vlakke plaat.
HOLE_12_MM = 7.24                # feit (norm): het middengat van een 12"-plaat is 7,24 mm
ANALYSIS_DPI = 300.0              # rekenen op deze resolutie; het eindbeeld komt op de volle resolutie
SCAN_EDGE_MM = 0.6               # feit: de schaduw van de scannerrand is ±0,5 mm breed; daarbinnen is een rand geen bewijs
RIM_CUT_MM = 0.25                # net binnen de binnenkant van de afgeronde rand snijden
ROUND_MM = 0.75                  # een plaat is rond: geen richting wijkt meer af dan dit
SQUARE_MM = 1.5                  # een hoes is vierkant: breedte en hoogte verschillen hooguit zoveel
SEEN = 0.5                       # zoveel van een zijde op een zichtbare rand = die zijde is gezien


def load(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        sys.exit('cannot read ' + path)
    alpha = im[:, :, 3] > 0 if im.shape[2] == 4 else np.ones(im.shape[:2], bool)
    return im[:, :, :3], alpha


def scan_border_mask(meta, shape, scale, width_px):
    """Pixels vlak bij de rand van een scan (op rekenschaal): daar is een rand geen bewijs."""
    m = np.zeros(shape, np.uint8)
    for s in meta['scans']:
        cor = np.array(s['corners'], np.float32) * scale
        cv2.polylines(m, [np.round(cor).astype(np.int32)], True, 1, int(width_px))
    return m > 0


def edge_maps(bgr, alpha, border, ):
    """Randpixels per richting. Een rand is waar de helderheid in één richting
    duidelijk verspringt (meer dan de ruis van het papier) en veel sterker dan in
    de andere richting (tekst springt in alle richtingen)."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 0.8)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)
    inside = cv2.erode(alpha.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    valid = inside & ~border
    mag = np.hypot(gx, gy)
    noise = float(np.median(mag[valid])) + 1e-3
    t = 3.0 * noise
    eh = (np.abs(gy) > t) & (np.abs(gy) > 2 * np.abs(gx)) & valid      # horizontale rand
    ev = (np.abs(gx) > t) & (np.abs(gx) > 2 * np.abs(gy)) & valid      # verticale rand
    k = np.ones((3, 3), np.uint8)
    eh = cv2.dilate(eh.astype(np.uint8), k) > 0                         # halve pixel speling
    ev = cv2.dilate(ev.astype(np.uint8), k) > 0
    return eh, ev, valid, mag, t


def seg_sums(a, S, axis):
    """Som van a over segmenten van lengte S langs axis, voor elk beginpunt."""
    c = np.cumsum(np.pad(a.astype(np.float32), [(1, 0), (0, 0)] if axis == 0 else [(0, 0), (1, 0)]), axis=axis)
    return (c[S:] - c[:-S]) if axis == 0 else (c[:, S:] - c[:, :-S])


def side_cover(eh, ev, valid, x0, y0, Sx, Sy):
    """Per zijde: deel van de gescande omtrek dat op een rand ligt, en hoeveel gescand is."""
    out = {}
    for name, edge, sl in (('top', eh, (y0, slice(x0, x0 + Sx))), ('bottom', eh, (y0 + Sy, slice(x0, x0 + Sx))),
                           ('left', ev, (slice(y0, y0 + Sy), x0)), ('right', ev, (slice(y0, y0 + Sy), x0 + Sx))):
        v = valid[sl]; e = edge[sl] & v
        out[name] = {'cover': float(e.sum() / max(v.sum(), 1)), 'scanned': float(v.mean()) if v.size else 0.0}
    return out


def find_rect(eh0, ev0, valid0, lo, hi, angles):
    """Vierkant met zijde tussen lo en hi px dat het best op randen ligt (grof)."""
    h, w = eh0.shape; c = (w / 2, h / 2); best = None
    for ang in angles:
        R = cv2.getRotationMatrix2D(c, ang, 1.0)
        rot = lambda a: cv2.warpAffine(a.astype(np.uint8), R, (w, h), flags=cv2.INTER_NEAREST) > 0
        eh, ev, valid = rot(eh0), rot(ev0), rot(valid0)
        for S in range(int(lo), int(hi) + 1):
            if S >= min(w, h):
                break
            th = seg_sums(eh & valid, S, 1) / np.maximum(seg_sums(valid, S, 1), 1)   # [y, x0]
            tv = seg_sums(ev & valid, S, 0) / np.maximum(seg_sums(valid, S, 0), 1)   # [y0, x]
            ny, nx = h - S, w - S
            score = th[:ny, :nx] + th[S:S + ny, :nx] + tv[:ny, :nx] + tv[:ny, S:S + nx]
            i = int(np.argmax(score)); y0, x0 = divmod(i, nx)
            if best is None or score[y0, x0] > best[0]:
                best = (float(score[y0, x0]), ang, x0, y0, S)
    return best


def refine_sides(eh, ev, valid, x0, y0, S, lo, hi, reach):
    """Elke zijde apart iets verschuiven (hoes hoeft niet precies vierkant), binnen de feiten."""
    def best_line(edge, fixed_range, positions, horizontal):
        scores = []
        for p in positions:
            if horizontal:
                v = valid[p, fixed_range]; e = edge[p, fixed_range] & v
            else:
                v = valid[fixed_range, p]; e = edge[fixed_range, p] & v
            scores.append(e.sum() / max(v.sum(), 1))
        return positions[int(np.argmax(scores))]
    h, w = eh.shape
    xs = slice(x0, x0 + S); ys = slice(y0, y0 + S)
    top = best_line(eh, xs, list(range(max(0, y0 - reach), min(h, y0 + reach + 1))), True)
    bottom = best_line(eh, xs, list(range(max(0, y0 + S - reach), min(h, y0 + S + reach + 1))), True)
    left = best_line(ev, ys, list(range(max(0, x0 - reach), min(w, x0 + reach + 1))), False)
    right = best_line(ev, ys, list(range(max(0, x0 + S - reach), min(w, x0 + S + reach + 1))), False)
    if not (lo <= bottom - top <= hi):
        top, bottom = y0, y0 + S
    if not (lo <= right - left <= hi):
        left, right = x0, x0 + S
    return left, top, right - left, bottom - top


def find_disc(bgr, alpha, border, lo, hi):
    """Cirkel met diameter tussen lo en hi px waarvan de omtrek het best op een rand
    ligt (ook de dunne scheidingsrand van wit vinyl op het witte deksel)."""
    g = cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 0.8)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)
    mag = np.hypot(gx, gy)
    valid = (cv2.erode(alpha.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0) & ~border
    t = 3.0 * (float(np.median(mag[valid])) + 1e-3)
    edge = ((mag > t) & valid).astype(np.float32)
    best = None
    for d in range(int(lo), int(hi) + 1, 1):
        r = d / 2.0; size = int(math.ceil(r)) * 2 + 3
        ring = np.zeros((size, size), np.float32)
        cv2.circle(ring, (size // 2, size // 2), int(round(r)), 1.0, 1)
        n = ring.sum()
        cov = cv2.filter2D(edge, -1, ring / n, borderType=cv2.BORDER_CONSTANT)
        scanned = cv2.filter2D(valid.astype(np.float32), -1, ring / n, borderType=cv2.BORDER_CONSTANT)
        score = cov / np.maximum(scanned, 1e-3) * (scanned > .5)
        i = int(np.argmax(score)); cy, cx = divmod(i, score.shape[1])
        if best is None or score[cy, cx] > best[0]:
            best = (float(score[cy, cx]), cx, cy, r, float(scanned[cy, cx]))
    # rondom: in welke richtingen ligt de omtrek op een rand (36 sectoren van 10 graden)
    _, cx, cy, r, _ = best
    sectors = []
    for k in range(36):
        a = np.radians(np.arange(k * 10, k * 10 + 10, 0.25))
        x = np.clip(np.round(cx + r * np.cos(a)).astype(int), 0, edge.shape[1] - 1)
        y = np.clip(np.round(cy + r * np.sin(a)).astype(int), 0, edge.shape[0] - 1)
        e = cv2.dilate(edge, np.ones((3, 3), np.uint8))[y, x]; v = valid[y, x]
        sectors.append(None if v.mean() < .5 else float((e * v).sum() / max(v.sum(), 1)))
    return best, sectors


def precise_circle(img, alpha, cx, cy, r, reach, round_px, n=72, inner=False, fixed_centre=False):
    """De plaat precies, op volle resolutie. In n richtingen het gemiddelde
    helderheidsverloop langs de straal; de rand van de plaat is daar de sterkste
    sprong. Door die punten de best passende cirkel (een plaat is rond). Geeft
    (cx, cy, r, afwijking per richting in px, of None waar niet gescand)."""
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
    H, W = g.shape
    radii = np.arange(r - reach, r + reach, 0.5)
    pts, idx = [], []
    for k in range(n):
        angs = np.radians(np.linspace(k * 360 / n, (k + 1) * 360 / n, 9, endpoint=False))
        xs = cx + np.outer(np.cos(angs), radii); ys = cy + np.outer(np.sin(angs), radii)
        ok = (xs >= 0) & (xs < W - 1) & (ys >= 0) & (ys < H - 1)
        xi = np.clip(xs, 0, W - 2).astype(np.float32); yi = np.clip(ys, 0, H - 2).astype(np.float32)
        vals = cv2.remap(g, xi, yi, cv2.INTER_LINEAR)
        av = cv2.remap(alpha.astype(np.float32), xi, yi, cv2.INTER_NEAREST) > 0
        good = ok & av
        if good.mean() < .9:
            continue
        prof = (vals * good).sum(0) / np.maximum(good.sum(0), 1)
        d = np.abs(np.diff(prof)); d[:2] = 0; d[-2:] = 0
        if inner:
            # binnenkant van de afgeronde rand: de eerste duidelijke sprong vanaf het vlakke vinyl
            strong = np.nonzero(d >= .5 * d.max())[0]
            i = int(strong.min()) if len(strong) else int(np.argmax(d))
        else:
            i = int(np.argmax(d))
        rr = radii[i] + 0.25; a = np.radians((k + .5) * 360 / n)
        pts.append((cx + rr * np.cos(a), cy + rr * np.sin(a))); idx.append(k)
    P = np.array(pts)
    if len(P) < 3:                                         # rand nergens te meten: niets bij te stellen
        return cx, cy, r, [None] * n
    if fixed_centre:                                       # zelfde midden, alleen de straal meten (mediaan: krassen tellen niet)
        d_all = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
        # overal binnen het vlakke vinyl: de kleinste afstand (5e percentiel, zodat één kras niet telt)
        return cx, cy, float(np.percentile(d_all, 5)), [None] * n
    def fit(Q):
        # kleinste kwadraten: x^2+y^2 + D x + E y + F = 0
        A = np.c_[Q, np.ones(len(Q))]; bvec = -(Q ** 2).sum(1)
        D, E, F = np.linalg.lstsq(A, bvec, rcond=None)[0]
        return -D / 2, -E / 2, math.sqrt(D * D / 4 + E * E / 4 - F)
    # Een kras of veeg vlak bij de rand kan in een richting sterker zijn dan de rand;
    # zo'n punt ligt dan niet op de cirkel. Zonder die punten opnieuw passen.
    use = np.ones(len(P), bool)
    for _ in range(5):
        ncx, ncy, nr = fit(P[use])
        new_use = np.abs(np.hypot(P[:, 0] - ncx, P[:, 1] - ncy) - nr) <= round_px
        if new_use.sum() < 3 or (new_use == use).all():
            break
        use = new_use
    dev = [None] * n
    for k, (x, y) in zip(idx, P):
        dev[k] = float(math.hypot(x - ncx, y - ncy) - nr)
    return ncx, ncy, nr, dev


def find_hole(img, r, reach):
    """Het middengat: de cirkel met de straal van het gat (feit) binnen 'reach' van
    het midden van de plaat waarvan de omtrek het best op een rand ligt.
    Geeft (x, y, deel van de omtrek op een rand)."""
    h, w = img.shape[:2]; c = w // 2
    lo, hi = int(c - reach - r - 4), int(c + reach + r + 4)
    g = cv2.GaussianBlur(cv2.cvtColor(img[lo:hi, lo:hi], cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
    mag = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    edge = (mag > 3.0 * (np.median(mag) + 1e-3)).astype(np.float32)
    edge = cv2.dilate(edge, np.ones((3, 3), np.uint8))
    size = int(np.ceil(r)) * 2 + 3; ring = np.zeros((size, size), np.float32)
    cv2.circle(ring, (size // 2, size // 2), int(round(r)), 1.0, 1)
    cov = cv2.filter2D(edge, -1, ring / ring.sum(), borderType=cv2.BORDER_CONSTANT)
    m = np.zeros_like(cov); cc = (hi - lo) // 2
    cv2.circle(m, (cc, cc), int(reach), 1, -1)
    cov = cov * m
    y, x = divmod(int(np.argmax(cov)), cov.shape[1])
    return lo + x, lo + y, float(cov[y, x])


def hole_outline(img, hx, hy, r, n=72):
    """Het echte gat zoals het gescand is (kan uitgesleten of niet helemaal rond
    zijn): in n richtingen vanuit het midden van het gat de sterkste sprong tussen
    0,7 en 1,6 keer de normstraal. Geeft de omtrek als punten."""
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
    radii = np.arange(.7 * r, 1.6 * r, .5); pts = []
    for k in range(n):
        a = 2 * np.pi * (k + .5) / n
        xs = (hx + radii * np.cos(a)).astype(np.float32); ys = (hy + radii * np.sin(a)).astype(np.float32)
        prof = cv2.remap(g, xs.reshape(1, -1), ys.reshape(1, -1), cv2.INTER_LINEAR).ravel()
        d = np.abs(np.diff(np.convolve(prof, np.ones(3) / 3, 'same'))); d[:1] = 0; d[-1:] = 0
        rr = radii[int(np.argmax(d)) + 1]
        pts.append((rr, a))
    rs = np.array([p[0] for p in pts])
    rs = np.maximum(rs, np.median(rs) - .15 * r)            # een losse kras binnenin trekt de rand niet naar binnen
    return np.array([[hx + q * np.cos(a), hy + q * np.sin(a)] for q, (_, a) in zip(rs, pts)], np.float32)


def precise_edges(img, alpha, L, T, R, B, reach, segments=False):
    """Elke zijde precies op de papierrand, op volle resolutie. Per zijde het
    gemiddelde helderheidsverloop dwars op de rand (middelste 80% van de zijde,
    alleen gescande pixels). De papierrand is de binnenste duidelijke sprong: een
    schaduw valt altijd buiten het papier, nooit erbinnen."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    def profile(horizontal, pos, a0, a1, whole=False):
        lo, hi = int(round(pos - reach)), int(round(pos + reach))
        span = slice(int(a0), int(a1)) if whole else slice(int(a0 + .1 * (a1 - a0)), int(a1 - .1 * (a1 - a0)))
        if horizontal:
            band, ok = g[lo:hi, span], alpha[lo:hi, span]
            cnt = ok.sum(1); prof = (band * ok).sum(1) / np.maximum(cnt, 1)
        else:
            band, ok = g[span, lo:hi], alpha[span, lo:hi]
            cnt = ok.sum(0); prof = (band * ok).sum(0) / np.maximum(cnt, 1)
        full = band.shape[1] if horizontal else band.shape[0]
        # waar minder dan de helft van de zijde gescand (en bruikbaar) is, telt die positie niet
        weak = cnt < .5 * max(full, 1)
        prof = np.convolve(prof, np.ones(3) / 3, 'same')
        return lo, np.where(weak, np.nan, prof)
    def edge(horizontal, pos, a0, a1, inward, whole=False):
        lo, prof = profile(horizontal, pos, a0, a1, whole)
        d = np.abs(np.diff(prof)); d = np.nan_to_num(d, nan=0.0); d[:2] = 0; d[-2:] = 0
        if d.max() <= 0 or np.isnan(prof).mean() > .5:
            return pos                                     # niets te meten: het grove kader blijft staan
        peaks = [i for i in range(1, len(d) - 1) if d[i] >= d[i - 1] and d[i] >= d[i + 1] and d[i] >= .5 * d.max()]
        i = max(peaks) if inward > 0 else min(peaks)          # binnenste sprong
        return lo + i + 1 if inward > 0 else lo + i + 1
    if segments:
        # helling per zijde: de rand in 10 stukken meten en er een rechte lijn door leggen
        slopes = []
        for horizontal, pos, a0, a1, inward in ((False, L, T, B, +1), (True, T, L, R, +1), (False, R, T, B, -1), (True, B, L, R, -1)):
            cuts = np.linspace(a0 + .1 * (a1 - a0), a1 - .1 * (a1 - a0), 11)
            mids = (cuts[:-1] + cuts[1:]) / 2
            pts = np.array([edge(horizontal, pos, c0, c1, inward, True) for c0, c1 in zip(cuts[:-1], cuts[1:])], float)
            fit = np.polyfit(mids, pts, 1); resid = np.abs(pts - np.polyval(fit, mids))
            keep = resid <= max(2.0, np.median(resid) * 3)
            if keep.sum() >= 5:
                fit = np.polyfit(mids[keep], pts[keep], 1)
            # vertikale zijde: x = a + b*y ; horizontale zijde: y = a + b*x. Zelfde draairichting: b_h = -b_v
            slopes.append(fit[0] if horizontal else -fit[0])
        return float(np.median(slopes)), slopes
    return (edge(False, L, T, B, +1), edge(True, T, L, R, +1), edge(False, R, T, B, -1), edge(True, B, L, R, -1))


def missing_part(result, covered, px_mm):
    """Feit: een uitkomst bestaat alleen uit gescande pixels. Valt een stuk van de
    vorm buiten alle scans, dan is dat stuk er niet: TWIJFEL, met de plek."""
    gap = ~covered
    area = gap.sum() / px_mm ** 2
    if area < 1.0:                                         # minder dan 1 mm2: niets
        return
    h, w = gap.shape; ys, xs = np.nonzero(gap)
    where = ('top' if ys.mean() < h / 3 else 'bottom' if ys.mean() > 2 * h / 3 else 'middle') + '-' + \
            ('left' if xs.mean() < w / 3 else 'right' if xs.mean() > 2 * w / 3 else 'centre')
    result['verdict'] = 'TWIJFEL'
    result.setdefault('why', []).append(f'not scanned: {area:.0f} mm2 ({gap.mean():.1%}) at {where} (before turning upright)')
    result['message'] = (f'Sleeve can do no more than this: {area:.0f} mm2 at {where} is not on any scan. '
                         'Scan that part again (a black sheet under the lid makes the edges clear), '
                         'or fill it in yourself, for example in Photoshop. Sleeve does not invent image.')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('image'); p.add_argument('part', choices=sorted(PART_SHAPE))
    p.add_argument('--overlay', help='write a preview with the found shape')
    p.add_argument('--out', help='write the crop at full resolution')
    a = p.parse_args()
    meta = json.load(open(a.image + '.scans.json'))
    dpi = meta['dpi']
    if not dpi:
        sys.exit('unknown dpi: the size facts cannot be used')
    full_bgr, full_alpha = load(a.image)
    F = dpi / ANALYSIS_DPI if dpi > ANALYSIS_DPI * 1.05 else 1.0     # volle resolutie : rekenresolutie
    if F > 1.0:
        bgr = cv2.resize(full_bgr, None, fx=1 / F, fy=1 / F, interpolation=cv2.INTER_AREA)
        alpha = cv2.resize(full_alpha.astype(np.uint8), (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
        dpi = dpi / F
    else:
        bgr, alpha = full_bgr, full_alpha
    px_mm = dpi / 25.4
    s = WORK_PX_MM / px_mm
    small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    sa = cv2.resize(alpha.astype(np.uint8), (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    border = scan_border_mask(meta, sa.shape, s / F, max(2, 2 * SCAN_EDGE_MM * WORK_PX_MM))   # strook langs elke scanrand
    shape = PART_SHAPE[a.part]; lo_mm, hi_mm = FACTS_MM[shape]
    lo, hi = lo_mm * WORK_PX_MM, hi_mm * WORK_PX_MM
    result = {'part': a.part, 'shape': shape}
    if shape == 'disc':
        (score, cx, cy, r, scanned), sectors = find_disc(small, sa, border, lo, hi)
        seen = [x for x in sectors if x is not None]
        unseen = [k * 10 for k, x in enumerate(sectors) if x is not None and x < SEEN]
        result.update({'centre_mm': [cx / WORK_PX_MM, cy / WORK_PX_MM], 'diameter_mm': 2 * r / WORK_PX_MM,
                       'ring_cover': score, 'sectors_seen': sum(x >= SEEN for x in seen), 'sectors_scanned': len(seen),
                       'weak_degrees': unseen})
        result['verdict'] = 'GOED' if seen and not unseen else 'TWIJFEL'
    else:
        eh, ev, valid, _, _ = edge_maps(small, sa, border)
        coarse = find_rect(eh, ev, valid, lo, hi, np.arange(-3, 3.01, 0.25))
        _, ang, x0, y0, S = coarse
        c = (eh.shape[1] / 2, eh.shape[0] / 2)
        R = cv2.getRotationMatrix2D(c, ang, 1.0)
        rot = lambda m: cv2.warpAffine(m.astype(np.uint8), R, (m.shape[1], m.shape[0]), flags=cv2.INTER_NEAREST) > 0
        reh, rev, rva = rot(eh), rot(ev), rot(valid)
        x0, y0, Sx, Sy = refine_sides(reh, rev, rva, x0, y0, S, lo, hi, int(3 * WORK_PX_MM))
        sides = side_cover(reh, rev, rva, x0, y0, Sx, Sy)
        weak = [k for k, v in sides.items() if v['cover'] < SEEN]
        result.update({'angle': ang, 'box_mm': [x0 / WORK_PX_MM, y0 / WORK_PX_MM, Sx / WORK_PX_MM, Sy / WORK_PX_MM],
                       'sides': sides, 'weak_sides': weak})
        result['verdict'] = 'GOED' if not weak else 'TWIJFEL'
    print(json.dumps(result, indent=1))
    if a.out:
        k = 1 / s                                          # rekenschaal -> volle resolutie
        if shape == 'disc':
            X, Y, rr, dev = precise_circle(bgr, alpha, cx * k, cy * k, r * k, 3 * px_mm, ROUND_MM * px_mm)
            off = [d for d in dev if d is not None and abs(d) > ROUND_MM * px_mm]
            result['precise_diameter_mm'] = round(2 * rr / px_mm, 2)
            # keuze André (8 nov): de afgeronde rand niet tonen. Feit: waar het vlakke vinyl
            # ophoudt is per richting te meten (eerste sprong van binnenuit); daar snijden.
            # feit: de afgeronde rand is rondom even breed, dus hetzelfde midden als de buitenrand
            _, _, ri, _ = precise_circle(bgr, alpha, X, Y, rr - 0.8 * px_mm, 1.2 * px_mm, ROUND_MM * px_mm, inner=True, fixed_centre=True)
            if rr - 2 * DISC_EDGE_MM * px_mm < ri < rr:
                rr = ri - RIM_CUT_MM * px_mm
            else:
                rr -= DISC_EDGE_MM * px_mm
            result['cut_diameter_mm'] = round(2 * rr / px_mm, 2)
            result['precise_dev_mm'] = round(max([abs(d) for d in dev if d is not None] or [0]) / px_mm, 2)
            result['directions_measured'] = sum(d is not None for d in dev)
            measured = [d for d in dev if d is not None]
            result['directions_on_circle'] = len(measured) - len(off)
            if off:
                result['loose_points'] = ', '.join(f'{k * 5}deg {d / px_mm:+.1f}mm' for k, d in enumerate(dev) if d is not None and abs(d) > ROUND_MM * px_mm)
            if not measured:
                result['verdict'] = 'TWIJFEL'
                result.setdefault('why', []).append('the edge of the record could not be measured anywhere (does the scan resolution match the real size?)')
            elif len(off) > (1 - ON_CIRCLE) * len(measured):
                result['verdict'] = 'TWIJFEL'
                result.setdefault('why', []).append(f'{len(off)} directions more than {ROUND_MM} mm off the circle: ' + ', '.join(f'{k * 5}deg {d / px_mm:+.1f}mm' for k, d in enumerate(dev) if d is not None and abs(d) > ROUND_MM * px_mm))
            print('precise disc:', result['precise_diameter_mm'], 'mm measured, cut at', result['cut_diameter_mm'], 'mm (flat part);', result['directions_on_circle'], 'of', result['directions_measured'], 'directions on the circle; loose:', result.get('loose_points', '-'), '; verdict', result['verdict'], result.get('why', ''))
            x0f, y0f = int(round(X - rr)), int(round(Y - rr)); n = int(round(2 * rr))
            crop = np.zeros((n, n, 4), np.uint8)
            src = np.dstack([bgr, alpha.astype(np.uint8) * 255])
            sx0, sy0 = max(0, x0f), max(0, y0f); sx1, sy1 = min(src.shape[1], x0f + n), min(src.shape[0], y0f + n)
            crop[sy0 - y0f:sy1 - y0f, sx0 - x0f:sx1 - x0f] = src[sy0:sy1, sx0:sx1]
            ring = np.zeros((n, n), np.uint8); cv2.circle(ring, (n * 8, n * 8), int(round(rr * 16)), 255, -1, cv2.LINE_AA, 4)   # zachte rand van één pixel
            crop[:, :, 3] = np.minimum(crop[:, :, 3], ring)
            inside = ring > 0
            cov = np.ones_like(inside); cov[inside] = crop[:, :, 3][inside] > 0
            missing_part(result, cov, px_mm)
            hx, hy, hcov = find_hole(crop[:, :, :3], HOLE_12_MM / 2 * px_mm, 4 * px_mm)
            hole = np.zeros((n, n), np.uint8)
            outline = hole_outline(crop[:, :, :3], hx, hy, HOLE_12_MM / 2 * px_mm)
            cv2.fillPoly(hole, [np.round(outline).astype(np.int32)], 255)
            hole = cv2.dilate(hole, np.ones((3, 3), np.uint8))      # de randpixel van het gat zelf ook
            result['hole_diameter_mm'] = round(2 * math.sqrt(hole.sum() / 255 / math.pi) / px_mm, 2)
            crop[:, :, 3][hole > 0] = 0
            result['hole_offset_mm'] = [round((hx - n / 2) / px_mm, 2), round((hy - n / 2) / px_mm, 2)]
            result['hole_edge_seen'] = round(hcov, 2)
            print('centre hole: offset', result['hole_offset_mm'], 'mm from the disc centre; measured', result['hole_diameter_mm'], 'mm; edge seen', result['hole_edge_seen'])
            if hcov < SEEN:
                result['verdict'] = 'TWIJFEL'
                result.setdefault('why', []).append('centre hole not clearly visible')
            print('final verdict:', result['verdict'], result.get('why', ''))
            if F > 1.0:
                # zelfde plaat en gat op de volle resolutie uitsnijden
                Xf, Yf, rf = X * F, Y * F, rr * F
                x0g, y0g = int(round(Xf - rf)), int(round(Yf - rf)); n2 = int(round(2 * rf))
                big = np.zeros((n2, n2, 4), np.uint8)
                src = np.dstack([full_bgr, full_alpha.astype(np.uint8) * 255])
                sx0, sy0 = max(0, x0g), max(0, y0g); sx1, sy1 = min(src.shape[1], x0g + n2), min(src.shape[0], y0g + n2)
                big[sy0 - y0g:sy1 - y0g, sx0 - x0g:sx1 - x0g] = src[sy0:sy1, sx0:sx1]
                ring2 = np.zeros((n2, n2), np.uint8); cv2.circle(ring2, (n2 * 8, n2 * 8), int(round(rf * 16)), 255, -1, cv2.LINE_AA, 4)
                big[:, :, 3] = np.minimum(big[:, :, 3], ring2)
                hole2 = np.zeros((n2, n2), np.uint8)
                pts = (outline + np.float32([x0f, y0f])) * F - np.float32([x0g, y0g])
                cv2.fillPoly(hole2, [np.round(pts * 16).astype(np.int32)], 255, cv2.LINE_AA, 4)
                hole2 = cv2.dilate(hole2, np.ones((int(2 * F) | 1, int(2 * F) | 1), np.uint8))
                big[:, :, 3] = np.minimum(big[:, :, 3], 255 - hole2)
                crop = big
        else:
            H, W = bgr.shape[:2]
            # feit: de rand van een scan is geen hoesrand, ook niet bij het nauwkeurig meten
            near_scan_edge = scan_border_mask(meta, (H, W), 1 / F, max(2, 2 * SCAN_EDGE_MM * px_mm))
            usable = (alpha & ~near_scan_edge).astype(np.uint8)
            def rotated(angle):
                Rm = cv2.getRotationMatrix2D((W / 2, H / 2), angle, 1.0)
                return (cv2.warpAffine(bgr, Rm, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE),
                        cv2.warpAffine(usable, Rm, (W, H), flags=cv2.INTER_NEAREST) > 0)
            # Feit: de randen van een hoes zijn recht en haaks. De hoek fijn bijstellen
            # tot de gemeten randen recht in het beeld liggen (grof zoeken: stappen van 0,25 graad).
            box0 = (x0 * k, y0 * k, (x0 + Sx) * k, (y0 + Sy) * k)
            tries = {}
            def tilt_at(angle):
                if angle not in tries:
                    f2, a2 = rotated(angle)
                    tries[angle] = abs(precise_edges(f2, a2, *box0, 3 * px_mm, segments=True)[0])
                return tries[angle]
            step = 0.2
            while step >= 0.0125:                     # steeds fijner rond de beste hoek
                ang = min((ang - step, ang, ang + step), key=tilt_at)
                if ang not in (min(tries, key=tries.get),):
                    ang = min(tries, key=tries.get)
                step /= 2
            ang = min(tries, key=tries.get)
            full, fa = rotated(ang)
            best_try = (tries[ang],)
            result['angle'] = round(ang, 3)
            print(f'angle refined on the edges: {ang:+.3f} degrees (remaining tilt {math.degrees(math.atan(best_try[0])):.3f})')
            L, T, Rr, B = precise_edges(full, fa, x0 * k, y0 * k, (x0 + Sx) * k, (y0 + Sy) * k, 3 * px_mm)
            result['precise_mm'] = [round(v / px_mm, 1) for v in (L, T, Rr - L, B - T)]
            print('precise box (mm):', result['precise_mm'])
            wmm, hmm = result['precise_mm'][2:]
            if abs(wmm - hmm) > SQUARE_MM:
                result['verdict'] = 'TWIJFEL'
                result.setdefault('why', []).append(f'not square: {wmm} x {hmm} mm; one side is probably a print edge, not the paper edge')
            print('verdict:', result['verdict'], result.get('why', ''))
            crop = full[int(round(T)):int(round(B)), int(round(L)):int(round(Rr))]
            Rm0 = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0)
            fa_real = cv2.warpAffine(alpha.astype(np.uint8), Rm0, (W, H), flags=cv2.INTER_NEAREST) > 0
            covered = fa_real[int(round(T)):int(round(B)), int(round(L)):int(round(Rr))]
            missing_part(result, covered, px_mm)
            print('final verdict:', result['verdict'], result.get('why', ''))
            if F > 1.0:
                # zelfde hoek en kader op de volle resolutie
                Hf, Wf = full_bgr.shape[:2]
                Rm = cv2.getRotationMatrix2D((Wf / 2, Hf / 2), ang, 1.0)
                big = cv2.warpAffine(full_bgr, Rm, (Wf, Hf), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                crop = big[int(round(T * F)):int(round(B * F)), int(round(L * F)):int(round(Rr * F))]
                big = None
            if a.overlay:
                m = int(5 * px_mm); ym = int((T + B) / 2); xm = int((L + Rr) / 2); z = int(15 * px_mm)
                def mark(tile, at):
                    tile = np.ascontiguousarray(tile).copy(); cv2.line(tile, (at, 0), (at, tile.shape[0]), (0, 0, 255), 1); return tile
                try:
                    left = mark(full[ym - z:ym + z, int(L) - m:int(L) + m], m); right = mark(full[ym - z:ym + z, int(Rr) - m:int(Rr) + m], m)
                    top = mark(cv2.rotate(full[int(T) - m:int(T) + m, xm - z:xm + z], cv2.ROTATE_90_CLOCKWISE), m)
                    bot = mark(cv2.rotate(full[int(B) - m:int(B) + m, xm - z:xm + z], cv2.ROTATE_90_CLOCKWISE), m)
                    cv2.imwrite(a.overlay.replace('.jpg', '_edges.jpg'), cv2.resize(np.hstack([left, right, top, bot]), None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))
                except cv2.error:
                    pass                                   # alleen een hulpbeeld; rand te dicht bij de beeldrand
        cv2.imwrite(a.out, crop)
        result['dpi'] = round(dpi * F, 2)
        json.dump(result, open(a.out + '.feiten.json', 'w'), indent=1)
    if a.overlay:
        view = small.copy()
        if shape == 'disc':
            cv2.circle(view, (int(cx), int(cy)), int(round(r)), (0, 0, 255), 2)
            for k, x in enumerate(sectors):
                if x is None:
                    continue
                ang_ = np.radians(k * 10 + 5)
                col = (0, 200, 0) if x >= SEEN else (0, 140, 255)
                cv2.circle(view, (int(cx + (r + 8) * np.cos(ang_)), int(cy + (r + 8) * np.sin(ang_))), 4, col, -1)
        else:
            Ri = cv2.invertAffineTransform(R)
            cor = np.float32([[x0, y0], [x0 + Sx, y0], [x0 + Sx, y0 + Sy], [x0, y0 + Sy]]) @ Ri[:, :2].T + Ri[:, 2]
            names = ['top', 'right', 'bottom', 'left']
            for i in range(4):
                col = (0, 200, 0) if sides[names[i]]['cover'] >= SEEN else (0, 140, 255)
                cv2.line(view, tuple(np.round(cor[i]).astype(int)), tuple(np.round(cor[(i + 1) % 4]).astype(int)), col, 2)
        view[~sa] = (view[~sa] * .4).astype(np.uint8)
        view[border] = (0, 0, 160)
        cv2.imwrite(a.overlay, view)


if __name__ == '__main__':
    main()
