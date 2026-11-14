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
import argparse, json, math, os, sys
import numpy as np, cv2

# Feiten per formaat en onderdeel: rechthoek (breedte, hoogte in mm, elk (min, max); de
# stand mag ook gedraaid liggen) of schijf (doorsnede (min, max), middengat in mm).
SHAPES = {
    'vinyl': {
        # hoes ±31 cm (het laatste woord heeft de vergelijking voor- met achterkant, in de bridge)
        'front': ('rect', (305, 318), (305, 318), True), 'back': ('rect', (305, 318), (305, 318), True),
        'inlay': ('rect', (305, 318), (305, 318), True),
        # uitklap (gatefold): twee panelen naast elkaar, 2 : 1
        'inside': ('rect', (605, 640), (305, 318), False),
        # insert/tekstvel/boekje: rechthoek, niet per se vierkant (Music On Vinyl: 303 x 308 en 300 x 300; boekje Urban Solitude: 291 x 291).
        # Ondergrens 288: het boekje meet 290,2-290,9. Niet ruimer: bij 280 won een gekleurde band in het
        # drukwerk (283 mm) van de papierrand (MOV-vel, 12 nov).
        'insert': ('rect', (288, 312), (288, 312), False),
        'sidea': ('disc', (296, 304), 7.24), 'sideb': ('disc', (296, 304), 7.24),
        'sidec': ('disc', (296, 304), 7.24), 'sided': ('disc', (296, 304), 7.24),
    },
    'cd': {                      # jewelcase: boekje 120 x 120, tray-inlay ±151 x 118 (met ruggetjes), schijf 120, gat 15
        'front': ('rect', (117, 123), (117, 123), True), 'inside': ('rect', (117, 123), (117, 123), True),
        'insert': ('rect', (117, 123), (117, 123), True),
        'back': ('rect', (136, 154), (114, 120), False), 'inlay': ('rect', (136, 154), (114, 120), False),
        'cd': ('disc', (117, 122), 15.0), 'cd1': ('disc', (117, 122), 15.0), 'cd2': ('disc', (117, 122), 15.0),
    },
}
# Andere cd-verpakkingen (standaardmaten van fabrikanten; per fabriek een paar mm verschil,
# daarom een bereik - Sleeve meet de echte rand daarbinnen):
#  - slim jewel case: boekje 120 x 120, geen achterkaart in de lade
#  - Super Jewel Box: zelfde buitenmaat als een jewel case (142 x 125); boekje 120 x 120,
#    achterkaart afwijkend en niet eenduidig gepubliceerd: ruim bereik
#  - digipak/digifile: dicht ±139-142 x 125, opengeklapt twee panelen
#  - kartonnen hoesje (cd-wallet): ±5 inch = 127 x 127
_DISC = ('disc', (117, 122), 15.0)
_BOOKLET = ('rect', (117, 123), (117, 123), True)
SHAPES['cd-slimjewel'] = {'front': _BOOKLET, 'back': _BOOKLET, 'insert': _BOOKLET, 'inside': _BOOKLET,
                          'cd': _DISC, 'cd1': _DISC, 'cd2': _DISC}
SHAPES['cd-superjewel'] = {'front': _BOOKLET, 'insert': _BOOKLET, 'inside': _BOOKLET,
                           'back': ('rect', (118, 152), (114, 127), False), 'inlay': ('rect', (118, 152), (114, 127), False),
                           'cd': _DISC, 'cd1': _DISC, 'cd2': _DISC}
SHAPES['cd-digipak'] = {'front': ('rect', (136, 144), (122, 128), False), 'back': ('rect', (136, 144), (122, 128), False),
                        'inside': ('rect', (268, 290), (122, 128), False), 'insert': _BOOKLET,
                        'cd': _DISC, 'cd1': _DISC, 'cd2': _DISC}
SHAPES['cd-cardsleeve'] = {'front': ('rect', (123, 131), (123, 131), True), 'back': ('rect', (123, 131), (123, 131), True),
                           'insert': _BOOKLET, 'inside': ('rect', (123, 131), (123, 131), True),
                           'cd': _DISC, 'cd1': _DISC, 'cd2': _DISC}
PART_SHAPE = {k: ('disc' if v[0] == 'disc' else 'sleeve') for f in SHAPES.values() for k, v in f.items()}
WORK_PX_MM = 2.0                 # rekenschaal voor het zoeken
ON_CIRCLE = 0.9                  # zoveel van de gemeten richtingen moet op de cirkel liggen
DISC_EDGE_MM = 1.0               # feit: de rand van een plaat is afgerond, ±1 mm breed; de scanner
                                 # toont die als glans of schaduw. Gesneden wordt op de vlakke plaat.
HOLE_12_MM = 7.24                # feit (norm): het middengat van een 12"-plaat is 7,24 mm
ANALYSIS_DPI = 300.0              # rekenen op deze resolutie; het eindbeeld komt op de volle resolutie
SCAN_EDGE_MM = 0.6               # feit: de schaduw van de scannerrand is minstens ±0,5 mm breed; daarbinnen is een rand geen bewijs
SCAN_EDGE_MAX_MM = 2.5           # ... en op een gekleurd vel gemeten tot ±2 mm (helderheid 138 -> 191); per scanrand gemeten, zie shading_widths
RIM_CUT_MM = 0.25                # net binnen de binnenkant van de afgeronde rand snijden
FLAT_START = os.environ.get('SLEEVE_FLAT_START', '1') != '0'   # snijden waar de kleur van het vlakke vinyl begint (0.5.32)
FLAT_DE = 3.0                    # ... binnen zoveel ΔE van het vlakke vinyl telt als vlak
EDGE_FLOOR = 3.0                 # kleinste sprong (Sobel) die een rand kan zijn; wit op wit is zwak, dus laag
ROUND_MM = 0.75                  # een plaat is rond: geen richting wijkt meer af dan dit
SQUARE_MM = 1.5                  # een hoes is vierkant: breedte en hoogte verschillen hooguit zoveel
SEEN = 0.5                       # zoveel van een zijde op een zichtbare rand = die zijde is gezien


def load(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        sys.exit('cannot read ' + path)
    alpha = im[:, :, 3] > 0 if im.shape[2] == 4 else np.ones(im.shape[:2], bool)
    return im[:, :, :3], alpha


def scan_border_mask(meta, shape, scale, width_px, widths=None, px_mm=None):
    """Pixels vlak bij de rand van een scan (op rekenschaal): daar is een rand geen bewijs.
    widths: per scan per zijde de gemeten breedte van de randschaduw in mm (shading_widths)."""
    m = np.zeros(shape, np.uint8)
    for k, s in enumerate(meta['scans']):
        cor = np.array(s['corners'], np.float32) * scale
        if widths is None:
            cv2.polylines(m, [np.round(cor).astype(np.int32)], True, 1, int(width_px))
            continue
        for i in range(4):
            a, b = np.round(cor[i]).astype(int), np.round(cor[(i + 1) % 4]).astype(int)
            cv2.line(m, tuple(int(v) for v in a), tuple(int(v) for v in b), 1, int(max(2, round(2 * widths[k][i] * px_mm))))
    return m > 0


def shading_widths(bgr, alpha, meta, scale, px_mm):
    """Feit: langs de rand van een scan loopt de helderheid af (schaduw van de scannerrand), en die
    schaduw houdt op waar de kleur vlak wordt. Per scan en per zijde gemeten, waar die zijde aan de
    buitenkant van het samengevoegde beeld ligt: de afstand vanaf de rand tot het eerste vlakke stuk
    (0,6 mm lang, kleurverschil < 3). Op een witte klep is dat ±0,5 mm, op een gekleurd vel tot ±2 mm.
    Niet te meten (zijde ligt binnenin, of er is geen vlak stuk): de vaste ondergrens."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[:, :, 0] *= 100 / 255
    H, W = alpha.shape; ds = np.arange(0, 4.0, 0.125); win = int(round(0.6 / 0.125)); out = []
    for s in meta['scans']:
        cor = np.array(s['corners'], np.float32) * scale; centre = cor.mean(0); row = []
        for i in range(4):
            a, b = cor[i], cor[(i + 1) % 4]
            d = (b - a) / max(np.linalg.norm(b - a), 1e-6); n = np.array([-d[1], d[0]], np.float32)
            if n @ (centre - a) < 0:
                n = -n
            profs = []
            for t in np.linspace(.1, .9, 48):
                base = a + t * (b - a); o = base - 0.8 * px_mm * n
                ox, oy = int(round(o[0])), int(round(o[1]))
                if 0 <= ox < W and 0 <= oy < H and alpha[oy, ox]:
                    continue                               # hier ligt een andere scan tegenaan: geen buitenrand
                pts = base[None, :] + (ds[:, None] * px_mm) * n[None, :]
                xi = np.round(pts[:, 0]).astype(int); yi = np.round(pts[:, 1]).astype(int)
                ok = (xi >= 0) & (yi >= 0) & (xi < W) & (yi < H)
                ok[ok] = alpha[yi[ok], xi[ok]]             # het samengevoegde beeld begint soms een halve mm binnen de scanrand
                if not ok[ds >= 1.0].all():
                    continue
                prof = np.full((len(ds), 3), np.nan, np.float32); prof[ok] = lab[yi[ok], xi[ok]]
                profs.append(prof)
            width = SCAN_EDGE_MM
            if len(profs) >= 10:
                P = np.nanmedian(np.array(profs), 0)
                first = int(np.argmax(~np.isnan(P[:, 0])))
                for j in range(first, len(ds) - win):
                    if np.linalg.norm(P[j:j + win + 1] - P[j], axis=1).max() < 3.0:
                        width = float(min(SCAN_EDGE_MAX_MM, max(SCAN_EDGE_MM, ds[j]))); break
                    # Feit: de schaduw loopt geleidelijk af; een papierrand is een sprong (kleurverschil >= 10
                    # binnen 0,25 mm). Ligt het onderdeel vlak bij de scanrand, dan houdt de strook vóór die sprong op.
                    if np.linalg.norm(P[j + 2] - P[j]) >= 10.0:
                        width = float(min(SCAN_EDGE_MAX_MM, max(SCAN_EDGE_MM, ds[j] - 0.125))); break
                else:
                    width = SCAN_EDGE_MAX_MM
            row.append(width)
        out.append(row)
    return out


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
    t = max(3.0 * noise, EDGE_FLOOR)                  # vlak gescand papier: ruis ±0, dan telt pas een echte sprong
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
        out[name] = {'cover': float(e.sum() / max(v.sum(), 1)) if v.sum() >= .5 * max(v.size, 1) else 0.0, 'scanned': float(v.mean()) if v.size else 0.0}
    return out


OUTER_MIN_PX = 6                 # 3 mm (rekenschaal 2 px/mm): zoveel groter moet het buitenste kader zijn om drukwerk langs de rand te verklaren
OUTER_TIE = 0.03                 # zo weinig mogen twee kaders in randbewijs schelen (som over vier zijden) om 'even goed' te heten


def background_outside(lab, valid, x0, y0, Sx, Sy):
    """Feit: buiten elke zijde van het vel ligt de achtergrond: gescand, en anders van kleur dan wat er
    net binnen de zijde ligt. Een 'zijde' op de rand van een scan heeft niets gescands erbuiten en telt
    dus niet. lab/valid op rekenschaal (2 px per mm); stroken van 0,5 tot 1,5 mm aan weerszijden."""
    h, w = valid.shape
    def strips(horizontal, pos, a0, a1, outward):
        out = []
        for sign in (outward, -outward):
            lo, hi = sorted((pos + sign * 1, pos + sign * 3))
            if lo < 0 or hi >= (h if horizontal else w):
                return None
            sl = (slice(lo, hi + 1), slice(a0, a1)) if horizontal else (slice(a0, a1), slice(lo, hi + 1))
            v = valid[sl]
            if v.mean() < .8:
                return None
            out.append(np.median(lab[sl][v], 0))
        return out
    for horizontal, pos, a0, a1, outward in ((True, y0, x0, x0 + Sx, -1), (True, y0 + Sy, x0, x0 + Sx, +1),
                                             (False, x0, y0, y0 + Sy, -1), (False, x0 + Sx, y0, y0 + Sy, +1)):
        got = strips(horizontal, pos, a0, a1, outward)
        if got is None or np.linalg.norm(got[0] - got[1]) < 8.0:
            return False
    return True


def find_rect(eh0, ev0, valid0, sizes, angles, outer_wins=False, lab0=None):
    """Rechthoek (Sx, Sy uit 'sizes', in px) die het best op randen ligt (grof).
    outer_wins: liggen twee kaders even goed op randen, dan is het buitenste het vel. Feit: drukwerk
    ligt binnen het papier. Een zwarte balk langs de rand van een vel geeft twee even sterke randen
    (wit-zwart en zwart-achtergrond); de binnenste is drukwerk. (MOV-vel, 12 nov: 13 mm te smal.)"""
    h, w = eh0.shape; c = (w / 2, h / 2); best = None; found = []
    for ang in angles:
        R = cv2.getRotationMatrix2D(c, ang, 1.0)
        rot = lambda a: cv2.warpAffine(a.astype(np.uint8), R, (w, h), flags=cv2.INTER_NEAREST) > 0
        eh, ev, valid = rot(eh0), rot(ev0), rot(valid0)
        cache_h, cache_v = {}, {}
        for Sx, Sy in sizes:
            if Sx >= w or Sy >= h:
                continue
            # feit: een zijde telt alleen als het grootste deel ervan gescand (bruikbaar) is
            if Sx not in cache_h:
                vs = seg_sums(valid, Sx, 1)
                cache_h[Sx] = np.where(vs >= .5 * Sx, seg_sums(eh & valid, Sx, 1) / np.maximum(vs, 1), 0)   # [y, x0]
            if Sy not in cache_v:
                vs = seg_sums(valid, Sy, 0)
                cache_v[Sy] = np.where(vs >= .5 * Sy, seg_sums(ev & valid, Sy, 0) / np.maximum(vs, 1), 0)   # [y0, x]
            th, tv = cache_h[Sx], cache_v[Sy]
            ny, nx = h - Sy, w - Sx
            score = th[:ny, :nx] + th[Sy:Sy + ny, :nx] + tv[:ny, :nx] + tv[:ny, Sx:Sx + nx]
            i = int(np.argmax(score)); y0, x0 = divmod(i, nx)
            if best is None or score[y0, x0] > best[0]:
                best = (float(score[y0, x0]), ang, x0, y0, Sx, Sy)
            if outer_wins:
                found.append((float(score[y0, x0]), ang, x0, y0, Sx, Sy))
    if outer_wins and best is not None and lab0 is not None:
        even = sorted((f for f in found if f[0] >= best[0] - OUTER_TIE), key=lambda f: (f[4] * f[5], f[0]), reverse=True)
        turned = {}
        for f in even[:400]:
            if f[4] * f[5] <= best[4] * best[5]:
                break                                      # geen groter kader dat even goed ligt
            if f[4] < best[4] + OUTER_MIN_PX and f[5] < best[5] + OUTER_MIN_PX:
                continue                                   # nauwelijks groter: dat is meetruis, geen balk drukwerk
            if f[1] not in turned:
                R = cv2.getRotationMatrix2D(c, f[1], 1.0)
                turned[f[1]] = (cv2.warpAffine(lab0, R, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE),
                                cv2.warpAffine(valid0.astype(np.uint8), R, (w, h), flags=cv2.INTER_NEAREST) > 0)
            if background_outside(*turned[f[1]], *f[2:]):
                best = f; break
    return best


def refine_sides(eh, ev, valid, x0, y0, Sx, Sy, xr, yr, reach):
    """Elke zijde apart iets verschuiven (hoes hoeft niet precies vierkant), binnen de feiten."""
    def best_line(edge, fixed_range, positions, horizontal):
        scores = []
        for p in positions:
            if horizontal:
                v = valid[p, fixed_range]; e = edge[p, fixed_range] & v
            else:
                v = valid[fixed_range, p]; e = edge[fixed_range, p] & v
            scores.append(e.sum() / max(v.sum(), 1) if v.sum() >= .5 * max(v.size, 1) else 0.0)
        return positions[int(np.argmax(scores))]
    h, w = eh.shape
    xs = slice(x0, x0 + Sx); ys = slice(y0, y0 + Sy)
    top = best_line(eh, xs, list(range(max(0, y0 - reach), min(h, y0 + reach + 1))), True)
    bottom = best_line(eh, xs, list(range(max(0, y0 + Sy - reach), min(h, y0 + Sy + reach + 1))), True)
    left = best_line(ev, ys, list(range(max(0, x0 - reach), min(w, x0 + reach + 1))), False)
    right = best_line(ev, ys, list(range(max(0, x0 + Sx - reach), min(w, x0 + Sx + reach + 1))), False)
    if not (yr[0] <= bottom - top <= yr[1]):
        top, bottom = y0, y0 + Sy
    if not (xr[0] <= right - left <= xr[1]):
        left, right = x0, x0 + Sx
    return left, top, right - left, bottom - top


def find_disc(bgr, alpha, border, lo, hi):
    """Cirkel met diameter tussen lo en hi px waarvan de omtrek het best op een rand
    ligt (ook de dunne scheidingsrand van wit vinyl op het witte deksel)."""
    g = cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 0.8)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)
    mag = np.hypot(gx, gy)
    valid = (cv2.erode(alpha.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0) & ~border
    t = max(3.0 * (float(np.median(mag[valid])) + 1e-3), EDGE_FLOOR)
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


def precise_circle(img, alpha, cx, cy, r, reach, round_px, n=72, inner=False, fixed_centre=False, outermost=False, median=False):
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
            if outermost:                                  # van buiten naar binnen: de eerste sprong
                i = int(strong.max()) if len(strong) else int(np.argmax(d))
            else:
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
        if outermost or median:                            # cd: de rand is rondom gelijk, de mediaan telt
            return cx, cy, float(np.median(d_all)), [None] * n
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


def rim_end(bgr, alpha, X, Y, r_outer, px_mm, n=144, reach_mm=5.0, flat_de=2.0):
    """Feit: door de dunne, afgeronde rand van een plaat schijnt de achtergrond heen (wit vinyl op een
    paars vel krijgt een lila randje). Dat is de kleur van de achtergrond, niet van de plaat. De plaat
    zelf begint waar de kleur niet meer naar de achtergrond toe verschoven is, vergeleken met de vlakke
    plaat verderop (3 tot 5 mm binnen de rand). Een rand die juist donkerder of glanzender is dan de
    plaat (dik doorschijnend vinyl, zwart vinyl) hoort bij de plaat en telt hier niet.
    Geeft die afstand in mm vanaf de buitenrand; None als het niet rondom te meten is of als de
    achtergrond dezelfde kleur heeft als de plaat (wit op wit)."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32); lab[:, :, 0] *= 100 / 255
    H, W = alpha.shape; ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    def ring(d_mm):
        r = r_outer - d_mm * px_mm
        xs = np.round(X + r * np.cos(ang)).astype(int); ys = np.round(Y + r * np.sin(ang)).astype(int)
        ok = (xs >= 0) & (ys >= 0) & (xs < W) & (ys < H); ok[ok] = alpha[ys[ok], xs[ok]]
        return np.median(lab[ys[ok], xs[ok]], 0) if ok.sum() >= n * .5 else None
    ds = np.arange(0.0, reach_mm + 1e-6, 0.125); P = [ring(d) for d in ds]
    back = [ring(-d) for d in (1.0, 1.5, 2.0)]
    if any(p is None for p in P) or any(b is None for b in back):
        return None
    P = np.array(P); plateau = np.median(P[ds >= 3.0], 0); lid = np.median(np.array(back), 0)
    to_lid = lid - plateau; gap = float(to_lid @ to_lid)
    if gap < 8.0 ** 2:
        return None
    # Alleen bij een gekleurde achtergrond: daar is doorschijnen aan de kleur te herkennen. Op de witte
    # klep is een lichtere rand niet te onderscheiden van glans op donker vinyl (Together Alone werd
    # er 1,3 mm per kant kleiner door): daar blijft de eerste sprong de snede.
    if float(np.hypot(lid[1] - 128, lid[2] - 128)) < 8.0:
        return None
    dev = P - plateau
    t = dev @ to_lid / gap                                  # 0 = kleur van de plaat, 1 = kleur van de achtergrond
    side = np.linalg.norm(dev - t[:, None] * to_lid[None, :], axis=1)
    tinted = (t > .05) & (side < 6.0) & (ds < 3.0)          # meer dan 5% van de weg naar de achtergrondkleur
    return 0.0 if not tinted.any() else float(ds[np.nonzero(tinted)[0].max()] + 0.125)


def swap_pixels(path, shape_full, crop, shape, result, disc, rect):
    """Optie naad-gelijktrekken: de randen zijn op het gewone beeld gevonden; dezelfde uitsnede (zelfde venster,
    hoek en bijsnijding) uit het gelijkgetrokken beeld van precies hetzelfde canvas. Alleen de kleur/toon
    verandert, de vorm en de maat niet."""
    other, _ = load(path)
    if other.shape != tuple(shape_full[:2]) + (3,):
        result.setdefault('notes', []).append('seam levelling skipped: the levelled image is not the same canvas')
        return crop
    if shape == 'disc':
        x0, y0, n = disc
        if x0 is None or n is None:
            return crop
        win = np.zeros((n, n, 3), np.uint8)
        sx0, sy0 = max(0, x0), max(0, y0); sx1, sy1 = min(other.shape[1], x0 + n), min(other.shape[0], y0 + n)
        win[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = other[sy0:sy1, sx0:sx1]
        out = crop.copy(); out[:, :, :3] = win[:crop.shape[0], :crop.shape[1]]
    else:
        ang, T, B, L, R, tr = rect
        Hf, Wf = other.shape[:2]
        big = cv2.warpAffine(other, cv2.getRotationMatrix2D((Wf / 2, Hf / 2), ang, 1.0), (Wf, Hf), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        out = big[int(round(T)) + tr[0]:int(round(B)) - tr[2], int(round(L)) + tr[3]:int(round(R)) - tr[1]]
        if out.shape[:2] != crop.shape[:2]:
            result.setdefault('notes', []).append('seam levelling skipped: the cut did not line up')
            return crop
        if crop.ndim == 3 and crop.shape[2] == 4:
            out = np.dstack([out, crop[:, :, 3]])
    result['seam_levelled'] = True
    return out


def soft_disc(n, r):
    """Een echte cirkel (straal r px, midden n/2) met een zachte rand van één pixel. cv2.circle tekent een
    grote cirkel als 72-hoek: tot 0,14 mm buiten de cirkel bij een lp (zichtbaar als knikjes, 14 nov)."""
    out = np.empty((n, n), np.uint8); xx = (np.arange(n, dtype=np.float32) - n / 2) ** 2
    for y0 in range(0, n, 1024):
        yy = (np.arange(y0, min(n, y0 + 1024), dtype=np.float32) - n / 2) ** 2
        d = np.sqrt(yy[:, None] + xx[None, :])
        out[y0:y0 + len(yy)] = (np.clip(r - d + 0.5, 0, 1) * 255 + .5).astype(np.uint8)
    return out


def flat_start(bgr, alpha, X, Y, r_outer, px_mm, n=144, reach_mm=5.0, max_mm=2.5, sectors=24):
    """Feit: het vlakke vinyl heeft dezelfde kleur als de plaat 3 tot 5 mm binnen de rand. De afgeronde
    rand wijkt daarvan af (schaduw, glans, doorschijnende achtergrond) en loopt geleidelijk over in het
    vlakke deel. Per stuk van de omtrek (sectors) het begin van het vlakke deel: de eerste ring vanaf
    binnen die meer dan FLAT_DE afwijkt. Het licht van de scanner valt van één kant, zodat de rand op
    de schaduwkant breder lijkt; daarom telt de mediaan over de stukken, niet de breedste kant (TA en
    blauw vinyl werden anders 2 tot 3 mm te klein; HNY kant B: verloop tot ±1,9 mm, rondom gelijk).
    Geeft de afstand in mm vanaf de buitenrand, of None als het niet rondom te meten is."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32); lab[:, :, 0] *= 100 / 255
    H, W = alpha.shape; ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    ds = np.arange(-2.0, reach_mm + 1e-6, 0.125)          # negatief: buiten de plaat (de klep of het vel)
    V = np.full((len(ds), n, 3), np.nan, np.float32)
    for i, d in enumerate(ds):
        r = r_outer - d * px_mm
        xs = np.round(X + r * np.cos(ang)).astype(int); ys = np.round(Y + r * np.sin(ang)).astype(int)
        ok = (xs >= 0) & (ys >= 0) & (xs < W) & (ys < H); ok[ok] = alpha[ys[ok], xs[ok]]
        V[i, ok] = lab[ys[ok], xs[ok]]
    flat = ds >= 3.0; rim = (ds >= 0) & (ds < 3.0); outside = (ds <= -1.0); found = []
    for sec in np.array_split(np.arange(n), sectors):
        S = V[:, sec]
        if np.isnan(S[ds >= 0]).any(axis=2).mean() > .2 or np.isnan(S[outside]).all():
            continue                                        # dit stuk is niet (helemaal) gescand
        P = np.nanmedian(S, 1); plateau = np.median(P[flat], 0)
        D = P - plateau; dev = np.linalg.norm(D, axis=1)
        # Alleen schaduw telt als rand: duidelijk donkerder dan het vlakke vinyl. Lichter is doorschijnen (de
        # klep door dik gekleurd vinyl) of glans; dat is echte plaat (blauw vinyl werd anders 1,5 mm in egaal
        # vinyl gesneden) en daar blijft de eerste sprong de snede.
        away = D[:, 0] < -.5 * dev
        tol = max(FLAT_DE, 3 * float(np.percentile(dev[flat], 90)))
        out = np.nonzero(rim & (dev > tol) & away)[0]
        found.append(float(ds[out.max()] + 0.125) if len(out) else 0.0)
    if len(found) < sectors // 2:
        return None
    d = float(np.median(found))
    return d if d <= max_mm else None


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


def hole_outline(img, hx, hy, r, n=72, outermost=False, top=1.7):
    """Het echte gat zoals het gescand is (kan uitgesleten of niet helemaal rond
    zijn): in n richtingen vanuit het midden van het gat de sterkste sprong tussen
    0,7 en 1,6 keer de normstraal. Geeft de omtrek als punten."""
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
    radii = np.arange(.7 * r, top * r, .5); pts = []
    for k in range(n):
        a = 2 * np.pi * (k + .5) / n
        xs = (hx + radii * np.cos(a)).astype(np.float32); ys = (hy + radii * np.sin(a)).astype(np.float32)
        prof = cv2.remap(g, xs.reshape(1, -1), ys.reshape(1, -1), cv2.INTER_LINEAR).ravel()
        d = np.abs(np.diff(np.convolve(prof, np.ones(3) / 3, 'same'))); d[:1] = 0; d[-1:] = 0
        if outermost:                                      # de buitenste duidelijke sprong: waar het bedrukte label begint
            strong = np.nonzero(d >= .5 * d.max())[0]
            rr = radii[int(strong.max()) + 1] if len(strong) else radii[int(np.argmax(d)) + 1]
        else:
            rr = radii[int(np.argmax(d)) + 1]
        pts.append((rr, a))
    rs = np.array([p[0] for p in pts])
    rs = np.maximum(rs, np.median(rs) - .15 * r)            # een losse kras binnenin trekt de rand niet naar binnen
    return np.array([[hx + q * np.cos(a), hy + q * np.sin(a)] for q, (_, a) in zip(rs, pts)], np.float32)


def edge_coverage(g, ok, horizontal, pos, a0, a1, px_mm, segs=10):
    """Feit: een echte rand loopt recht over de hele zijde. In hoeveel van de stukken langs de
    zijde staat op deze plek (±0,4 mm) een trap van minstens 3 grijswaarden (gemiddeld over
    0,25 mm aan elke kant)? Een vlek of kras haalt dat maar in één of twee stukken."""
    kk = max(2, int(.25 * px_mm)); tol = max(2, int(.4 * px_mm)); hits = n = 0
    cuts = np.linspace(a0 + .05 * (a1 - a0), a1 - .05 * (a1 - a0), segs + 1)
    for c0, c1 in zip(cuts[:-1], cuts[1:]):
        lo, hi = int(pos) - tol - kk - 1, int(pos) + tol + kk + 2
        if lo < 0 or hi > (g.shape[0] if horizontal else g.shape[1]):
            continue
        if horizontal:
            band = g[lo:hi, int(c0):int(c1)]; m = ok[lo:hi, int(c0):int(c1)]; ax = 1
        else:
            band = g[int(c0):int(c1), lo:hi]; m = ok[int(c0):int(c1), lo:hi]; ax = 0
        if m.mean() < .5:
            continue
        prof = (band * m).sum(ax) / np.maximum(m.sum(ax), 1); n += 1
        best = 0.0
        for j in range(kk, len(prof) - kk):
            best = max(best, abs(prof[j:j + kk].mean() - prof[j - kk:j].mean()))
        hits += best >= 3
    return hits / n if n else 0.0


def precise_edges(img, alpha, L, T, R, B, reach, segments=False, candidates=False, faint=False):
    """Elke zijde precies op de papierrand, op volle resolutie. Per zijde het
    gemiddelde helderheidsverloop dwars op de rand (middelste 80% van de zijde,
    alleen gescande pixels). De papierrand is de binnenste duidelijke sprong: een
    schaduw valt altijd buiten het papier, nooit erbinnen."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    near_px = reach * 0.4                                 # ±1,2 mm bij een zoekbereik van 3 mm
    def profile(horizontal, pos, a0, a1, whole=False):
        lo, hi = int(round(pos - reach)), int(round(pos + reach))
        lim = g.shape[0] if horizontal else g.shape[1]
        lo, hi = max(0, lo), min(lim, hi)                  # niet buiten het beeld zoeken
        if hi - lo < 4:
            return lo, np.full(max(hi - lo, 1), np.nan)
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
        # niet-gescand telt niet mee, ook niet in het gladstrijken (alleen over de gescande buren middelen)
        okv = (~weak).astype(np.float64); val = np.where(weak, 0.0, prof)
        num = np.convolve(val, np.ones(3), 'same'); den = np.convolve(okv, np.ones(3), 'same')
        prof = np.where(weak, np.nan, num / np.maximum(den, 1e-9))
        return lo, prof
    def edge(horizontal, pos, a0, a1, inward, whole=False):
        lo, prof = profile(horizontal, pos, a0, a1, whole)
        d = np.abs(np.diff(prof)); d = np.nan_to_num(d, nan=0.0); d[:2] = 0; d[-2:] = 0
        if faint and len(prof) > 8:
            # zwakke rand (wit kaartje op witte deksel): de trap tussen ±0,25 mm links en rechts,
            # over de hele zijde gemiddeld; ruis is dan klein, een echte rand blijft staan
            kk = max(2, int(reach / 16)); pv = np.nan_to_num(prof, nan=float(np.nanmedian(prof)))
            cs = np.concatenate([[0], np.cumsum(pv)])
            step_ = np.zeros(len(pv) - 1)
            for i in range(kk, len(pv) - kk):
                step_[i - 1] = abs((cs[i + kk] - cs[i]) - (cs[i] - cs[i - kk])) / kk
            d = np.maximum(d, step_); d[:2] = 0; d[-2:] = 0
        if d.max() <= 0 or np.isnan(prof).mean() > .5:
            return [pos] if candidates else pos            # niets te meten: het grove kader blijft staan
        # duidelijke sprongen: minstens half zo sterk als de sterkste. Met faint (cd-kaartje): ook een
        # zwakke maar rechte rand langs de hele zijde (wit kaartje op witte deksel), ruim boven de ruis.
        noise = float(np.median(np.abs(np.diff(np.nan_to_num(prof, nan=0.0))))) if len(prof) > 2 else 0.0
        floor = max(3.0, 6 * noise) if faint else .5 * d.max()
        peaks = [i for i in range(1, len(d) - 1) if d[i] >= d[i - 1] and d[i] >= d[i + 1] and d[i] >= floor]
        # het grove kader (hele zijde op een rand, ±0,5 mm) is het bewijs; binnen ±1,2 mm daarvan
        # de binnenste sprong (een schaduw valt buiten het papier); anders de binnenste overall
        if candidates:                                     # alle duidelijke randen (de feiten kiezen er later uit)
            return sorted(lo + j + 1 for j in peaks)
        near = [i for i in peaks if abs(lo + i + 1 - pos) <= near_px]
        pool = near or peaks
        i = max(pool) if inward > 0 else min(pool)            # binnenste sprong
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


FAR_FROM_LID = 60.0   # Lab-afstand papier-klep waarboven per stuk van een zijde bijgesneden mag worden (witte klep)


def trim_edge_lines(img, px_mm, lid_lab, max_mm=1.0, shadow_mm=2.5):
    """Feit: wat langs de rand de kleur van de klep heeft (gemeten vlak buiten het onderdeel
    in dezelfde scan), of de schaduw ervan (donkerder en kleurlozer dan het drukwerk), is
    klep en geen drukwerk. Per zijde de buitenste rijen weghalen zolang ze dichter bij de
    klep liggen dan bij het drukwerk ernaast; hooguit max_mm."""
    lab = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2LAB).astype(np.float32)
    # het papier ernaast meten op 2-3 mm van de rand: een brede schaduw reikt tot ±1,5 mm
    a, b = int(3.0 * px_mm), max(int(4.0 * px_mm), int(3.0 * px_mm) + 2); m = max(1, int(max_mm * px_mm))
    m_shadow = int(shadow_mm * px_mm)                    # feit: de kartonrand van een hoes is ±2-3 mm en geen voorkant
    def cut(rows, shadow_ok=True, far=0.0):                # rows: Lab per rij/kolom vanaf de rand naar binnen
        paper = np.median(rows[a:b], 0)
        if far and (lid_lab is None or np.linalg.norm(paper - lid_lab) < far):
            return 0                                       # papier lijkt op de klep: per stuk niets te zeggen
        k = 0
        while k < m_shadow:
            r = rows[k]
            to_paper = np.linalg.norm(r - paper)
            to_lid = np.linalg.norm(r - lid_lab) if lid_lab is not None else 1e9   # klep onbekend: alleen de schaduw telt
            shadow = shadow_ok and r[0] < paper[0] - 10 and np.hypot(r[1] - 128, r[2] - 128) < np.hypot(paper[1] - 128, paper[2] - 128)
            # een mengsel van klep en papier (de rand loopt over in de klep): ligt op de lijn papier-klep
            d = (lid_lab - paper) if lid_lab is not None else np.zeros(3, np.float32); nd = float(d @ d)
            tt = float((r - paper) @ d) / nd if nd > 1 else 0.0
            blend = nd > 100 and tt > .12 and np.linalg.norm(r - (paper + tt * d)) < 10
            # alleen wat duidelijk anders is dan het papier ernaast (een grijze hoes op een grijze klep blijft heel)
            if to_paper > 8 and ((k < m and (to_lid < to_paper or blend)) or shadow):
                k += 1
            else:
                break
        return k
    coloured = lid_lab is not None and float(np.hypot(lid_lab[1] - 128, lid_lab[2] - 128)) >= 8.0
    def side(view):                                        # view: rijen vanaf de rand naar binnen x langs de zijde x Lab
        k = cut(view.mean(1))
        if coloured:
            # Feit, alleen op een gekleurd vel: papier en achtergrond zijn daar duidelijk verschillend. Ligt de rand
            # op één stuk van de zijde lager (de hoes lag in twee deelscans net anders: Urban Solitude backs, een
            # grijze strook achtergrond binnen de snede), dan telt het ergste van 8 stukken. Op de witte klep niet:
            # daar lijkt drukwerk langs de rand op klep of schaduw en kostte dit TA en Fake 0,5-2 mm (13 nov).
            for part in np.array_split(np.arange(view.shape[1]), 8):
                if len(part) > 20:
                    k = max(k, cut(view[:, part].mean(1), shadow_ok=False))   # alleen echte achtergrondkleur, hooguit max_mm
        else:
            # Op de witte klep alleen waar het papier van dat stuk sterk van de klep verschilt (donker drukwerk:
            # Fire-insert, een wit lijntje klep langs een deel van de zijde). Licht drukwerk langs de rand blijft heel.
            for part in np.array_split(np.arange(view.shape[1]), 8):
                if len(part) > 20:
                    k = max(k, cut(view[:, part].mean(1), shadow_ok=False, far=FAR_FROM_LID))
        return k
    t = side(lab); bt = side(lab[::-1])
    l = side(lab.transpose(1, 0, 2)); r = side(lab.transpose(1, 0, 2)[::-1])
    h, w = img.shape[:2]
    return img[t:h - bt, l:w - r], (t, r, bt, l)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('image'); p.add_argument('part', choices=sorted(PART_SHAPE))
    p.add_argument('--format', choices=sorted(SHAPES), default=None, help='vinyl or cd (default: cd for cd parts, else vinyl)')
    p.add_argument('--overlay', help='write a preview with the found shape')
    p.add_argument('--out', help='write the crop at full resolution')
    p.add_argument('--pixels', help='same canvas, other tones (seam levelling): edges are found on IMAGE, the pixels come from here')
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
    shade = shading_widths(bgr, alpha, meta, 1 / F, px_mm)        # per scanrand: hoe breed de randschaduw is (mm)
    print('scan edge shading (mm):', [[round(v, 2) for v in row] for row in shade])
    border = scan_border_mask(meta, sa.shape, s / F, None, shade, WORK_PX_MM)   # strook langs elke scanrand
    fmt = a.format or ('cd' if a.part.startswith('cd') else 'vinyl')
    spec = SHAPES[fmt].get(a.part) or SHAPES['cd' if fmt.startswith('cd') else 'vinyl'].get(a.part) or SHAPES['vinyl'][a.part]
    shape = 'disc' if spec[0] == 'disc' else 'sleeve'
    if shape == 'disc':
        lo, hi = spec[1][0] * WORK_PX_MM, spec[1][1] * WORK_PX_MM; hole_mm = spec[2]
    else:
        (wlo, whi), (hlo, hhi), square = spec[1], spec[2], spec[3]
        xs_ = range(int(wlo * WORK_PX_MM), int(whi * WORK_PX_MM) + 1); ys_ = range(int(hlo * WORK_PX_MM), int(hhi * WORK_PX_MM) + 1)
        if square:
            sizes = [(S, S) for S in xs_]
        else:                                              # rechthoek: beide standen
            sizes = [(x, y) for x in xs_[::2] for y in ys_[::2]] + [(y, x) for x in xs_[::2] for y in ys_[::2]]
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
        small_lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32); small_lab[:, :, 0] *= 100 / 255
        coarse = find_rect(eh, ev, valid, sizes, np.arange(-3, 3.01, 0.25), outer_wins=(fmt == 'vinyl' and not square), lab0=small_lab)
        if coarse is None:
            msg = f'no {a.part} of the expected size ({wlo}-{whi} x {hlo}-{hhi} mm, {fmt}) fits in this scan'
            print('final verdict: FOUT', msg)
            if a.out:
                json.dump({'verdict': 'FOUT', 'why': [msg]}, open(a.out + '.feiten.json', 'w'))
            return
        _, ang, x0, y0, S0x, S0y = coarse
        landscape = S0x >= S0y
        xr = ((wlo, whi) if landscape or square else (hlo, hhi)); yr = ((hlo, hhi) if landscape or square else (wlo, whi))
        xr = (xr[0] * WORK_PX_MM, xr[1] * WORK_PX_MM); yr = (yr[0] * WORK_PX_MM, yr[1] * WORK_PX_MM)
        c = (eh.shape[1] / 2, eh.shape[0] / 2)
        R = cv2.getRotationMatrix2D(c, ang, 1.0)
        rot = lambda m: cv2.warpAffine(m.astype(np.uint8), R, (m.shape[1], m.shape[0]), flags=cv2.INTER_NEAREST) > 0
        reh, rev, rva = rot(eh), rot(ev), rot(valid)
        x0, y0, Sx, Sy = refine_sides(reh, rev, rva, x0, y0, S0x, S0y, xr, yr, int(3 * WORK_PX_MM))
        sides = side_cover(reh, rev, rva, x0, y0, Sx, Sy)
        weak = [k for k, v in sides.items() if v['cover'] < SEEN]
        result.update({'angle': ang, 'box_mm': [x0 / WORK_PX_MM, y0 / WORK_PX_MM, Sx / WORK_PX_MM, Sy / WORK_PX_MM],
                       'sides': sides, 'weak_sides': weak})
        result['verdict'] = 'GOED' if not weak else 'TWIJFEL'
    print(json.dumps(result, indent=1))
    if a.out:
        k = 1 / s                                          # rekenschaal -> volle resolutie
        if shape == 'disc':
            X, Y, rr, dev = precise_circle(bgr, alpha, cx * k, cy * k, r * k, 3 * px_mm, ROUND_MM * px_mm, inner=(fmt.startswith('cd')), outermost=(fmt.startswith('cd')))   # cd: de buitenste sprong is de rand tegen de klep
            off = [d for d in dev if d is not None and abs(d) > ROUND_MM * px_mm]
            result['precise_diameter_mm'] = round(2 * rr / px_mm, 2)
            r_outer = rr
            # keuze André (8 nov): de afgeronde rand niet tonen. Feit: waar het vlakke vinyl
            # ophoudt is per richting te meten (eerste sprong van binnenuit); daar snijden.
            # feit: de afgeronde rand is rondom even breed, dus hetzelfde midden als de buitenrand
            # feit: een plaat heeft een afgeronde rand, een cd een doorzichtige onbedrukte rand;
            # in beide gevallen snijden waar het vlakke, bedrukte deel ophoudt
            if fmt.startswith('cd'):
                # cd: de doorzichtige rand van buiten naar binnen; drukwerk (ringtekst) ligt daarbinnen
                # de doorzichtige rand is een donkere band van ±1-1,5 mm; vanaf het drukwerk naar buiten de eerste sprong
                _, _, ri, _ = precise_circle(bgr, alpha, X, Y, rr - 1.0 * px_mm, 0.9 * px_mm, ROUND_MM * px_mm, inner=True, fixed_centre=True, outermost=False, median=True)
            else:
                _, _, ri, _ = precise_circle(bgr, alpha, X, Y, rr - 0.8 * px_mm, 1.2 * px_mm, ROUND_MM * px_mm, inner=True, fixed_centre=True)
            if rr - (2.2 if fmt.startswith('cd') else 2) * DISC_EDGE_MM * px_mm < ri < rr:
                rr = ri - RIM_CUT_MM * px_mm
            else:
                rr -= DISC_EDGE_MM * px_mm
            if not fmt.startswith('cd'):
                # de rand loopt soms verder door dan de eerste sprong: kleur van de achtergrond in de rand,
                # of een geleidelijk verloop van schaduw of glans naar het vlakke vinyl
                flat = rim_end(bgr, alpha, X, Y, r_outer, px_mm)
                if FLAT_START:
                    f2 = flat_start(bgr, alpha, X, Y, r_outer, px_mm)
                    if f2 is not None and (flat is None or f2 > flat):
                        flat = f2
                if flat is not None and flat <= 2.5 and r_outer - (flat + 0.1) * px_mm < rr:
                    rr = r_outer - (flat + 0.1) * px_mm
                    result['rim_mm'] = round(flat, 2)
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
            ring = soft_disc(n, rr)   # zachte rand van één pixel
            crop[:, :, 3] = np.minimum(crop[:, :, 3], ring)
            inside = ring > 0
            cov = np.ones_like(inside); cov[inside] = crop[:, :, 3][inside] > 0
            missing_part(result, cov, px_mm)
            hx, hy, hcov = find_hole(crop[:, :, :3], hole_mm / 2 * px_mm, 1.2 * px_mm)   # feit: het gat zit (vrijwel) in het midden
            # Feit: het gat is rond. In 72 richtingen vanuit het midden van het gat de buitenste
            # duidelijke sprong (waar de schijf begint, ook voorbij een lichte binnenwand), een
            # cirkel erdoor (losse punten tellen niet) en die cirkel uitsnijden.
            def fit_hole(outer):
                Pq = hole_outline(crop[:, :, :3], hx, hy, hole_mm / 2 * px_mm, outermost=outer, top=(1.7 if fmt.startswith('cd') else 2.2)).astype(np.float64)
                use = np.ones(len(Pq), bool); cx_, cy_, r_ = hx, hy, 0.0
                for _ in range(6):
                    A_ = np.c_[Pq[use], np.ones(use.sum())]; D_, E_, F_ = np.linalg.lstsq(A_, -(Pq[use] ** 2).sum(1), rcond=None)[0]
                    cx_, cy_ = -D_ / 2, -E_ / 2; r_ = math.sqrt(max(D_ * D_ / 4 + E_ * E_ / 4 - F_, 0))
                    res = np.abs(np.hypot(Pq[:, 0] - cx_, Pq[:, 1] - cy_) - r_)
                    new_use = res <= max(.4 * px_mm, np.median(res) * 2.5)
                    if new_use.sum() < 12 or (new_use == use).all():
                        break
                    use = new_use
                dist = np.hypot(Pq[use, 0] - cx_, Pq[use, 1] - cy_)
                # het hele gat weg: tot de buitenkant van de gemeten rand (90e percentiel), niet het gemiddelde
                return cx_, cy_, float(np.percentile(dist, 90)) if len(dist) else r_, int(use.sum())
            # feit: door het gat (en een doorzichtige naaf of een groter labelgat) zie je de klep
            top = (1.62 if fmt.startswith('cd') else 2.1) * hole_mm / 2 * px_mm; low = 0.8 * hole_mm / 2 * px_mm
            hcx = hcy = hr = None
            for outer in ((True, False) if fmt.startswith('cd') else (False, True)):
                c_ = fit_hole(outer)
                if low < c_[2] < top and c_[3] >= 24:
                    hcx, hcy, hr = c_[0], c_[1], c_[2]; break
            if hr is None:
                hcx, hcy, hr = hx, hy, hole_mm / 2 * px_mm
                result.setdefault('why', []).append('centre hole: edge not clearly measured; cut at the standard size')
            hr = max(hr, hole_mm / 2 * px_mm)               # feit: het gat is nooit kleiner dan de norm (7,24 mm / cd 15 mm)
            outline = np.float32([[hcx + hr * math.cos(t), hcy + hr * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 180, endpoint=False)])
            hole = np.zeros((n, n), np.uint8)
            cv2.circle(hole, (int(round(hcx * 16)), int(round(hcy * 16))), int(round((hr + .1 * px_mm) * 16)), 255, -1, cv2.LINE_AA, 4)
            hole_small = hole.copy()
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
                ring2 = soft_disc(n2, rf)
                big[:, :, 3] = np.minimum(big[:, :, 3], ring2)
                # zelfde gat, opgeschaald naar de volle resolutie (zachte rand)
                Mh = np.float32([[F, 0, x0f * F - x0g], [0, F, y0f * F - y0g]])
                hole2 = cv2.warpAffine(hole_small, Mh, (n2, n2), flags=cv2.INTER_LINEAR)
                big[:, :, 3] = np.minimum(big[:, :, 3], 255 - hole2)
                crop = big
        else:
            H, W = bgr.shape[:2]
            # feit: de rand van een scan is geen hoesrand, ook niet bij het nauwkeurig meten
            near_scan_edge = scan_border_mask(meta, (H, W), 1 / F, None, shade, px_mm)
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
            if square:
                # feit: een hoes is vierkant. Uit de duidelijke randen per zijde de combinatie kiezen
                # waarvan breedte en hoogte het best gelijk zijn (bij gelijke stand: de binnenste)
                # Feit (cd): een cd-kaartje heeft geen kartonrand of schaduw zoals een platenhoes; alles
                # binnen de buitenste rechte rand is drukwerk. Dus daar de buitenste rand (ook een zwakke:
                # wit kaartje op witte deksel); bij vinyl de binnenste (schaduw valt buiten het papier).
                outer = fmt.startswith('cd')
                cl, ct, cr, cb = precise_edges(full, fa, x0 * k, y0 * k, (x0 + Sx) * k, (y0 + Sy) * k, (4 if outer else 3) * px_mm, candidates=True, faint=outer)
                best_c = None
                if outer:
                    # Feit: de scanrand is geen kaartrand: kandidaten binnen 1 mm van de beeldrand tellen niet.
                    # Dan per zijde de buitenste echte rand (geen vierkant-voorkeur: een kaartje mag 1-2 mm
                    # afwijken; de vierkant-voorkeur trok een zijde naar de scanrand).
                    Hf, Wf = full.shape[:2]; e1 = 1.0 * px_mm
                    gq = cv2.cvtColor(full, cv2.COLOR_BGR2GRAY).astype(np.float32); okq = fa.astype(np.float32)
                    X0, Y0, X1, Y1 = x0 * k, y0 * k, (x0 + Sx) * k, (y0 + Sy) * k
                    whole = lambda v, hor: edge_coverage(gq, okq, hor, v, *((X0, X1) if hor else (Y0, Y1)), px_mm) >= .7
                    cl2 = [v for v in cl if v > e1 and whole(v, False)]; ct2 = [v for v in ct if v > e1 and whole(v, True)]
                    cr2 = [v for v in cr if v < Wf - e1 and whole(v, False)]; cb2 = [v for v in cb if v < Hf - e1 and whole(v, True)]
                    if cl2 and ct2 and cr2 and cb2:
                        l_, t_, r_, b_ = min(cl2), min(ct2), max(cr2), max(cb2)
                        w_, h_ = r_ - l_, b_ - t_
                        if wlo * px_mm <= w_ <= max(whi, 131) * px_mm and hlo * px_mm <= h_ <= max(hhi, 131) * px_mm:
                            best_c = ((0, 0), (l_, t_, r_, b_))
                for l_ in ([] if best_c else cl):
                    for r_ in cr:
                        for t_ in ct:
                            for b_ in cb:
                                w_, h_ = r_ - l_, b_ - t_
                                # cd: elk cd-kaartje (boekje 117-123, kaartje/hoesje tot 131) mag; welke het is, volgt uit de maat
                                wmax, hmax = (max(whi, 131), max(hhi, 131)) if outer else (whi, hhi)
                                if not (wlo * px_mm <= w_ <= wmax * px_mm and hlo * px_mm <= h_ <= hmax * px_mm):
                                    continue
                                key = (0 if abs(w_ - h_) <= 1.0 * px_mm else abs(w_ - h_), -(w_ + h_) if outer else w_ + h_)   # vierkant binnen 1 mm; dan buitenste (cd) / binnenste (vinyl)
                                if best_c is None or key < best_c[0]:
                                    best_c = (key, (l_, t_, r_, b_))
                if best_c:
                    L, T, Rr, B = best_c[1]
            result['precise_mm'] = [round(v / px_mm, 1) for v in (L, T, Rr - L, B - T)]
            print('precise box (mm):', result['precise_mm'])
            wmm, hmm = result['precise_mm'][2:]
            # (vierkant wordt niet meer geëist: voor- en achterkant worden in de bridge met elkaar vergeleken)
            print('verdict:', result['verdict'], result.get('why', ''))
            crop = full[int(round(T)):int(round(B)), int(round(L)):int(round(Rr))]
            # kleur van de klep: een strook van 1-3 mm buiten het onderdeel, alleen gescande pixels
            o1, o2 = 2, int(5 * px_mm)
            ring = np.zeros(full.shape[:2], bool)
            ring[max(0, int(T) - o2):int(B) + o2, max(0, int(L) - o2):int(Rr) + o2] = True
            ring[max(0, int(T) - o1):int(B) + o1, max(0, int(L) - o1):int(Rr) + o1] = False
            Rk = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0)
            ring &= cv2.warpAffine(alpha.astype(np.uint8), Rk, (W, H), flags=cv2.INTER_NEAREST) > 0   # gescand (ook vlak bij de scanrand)
            ring[:2] = ring[-2:] = False; ring[:, :2] = ring[:, -2:] = False
            lid_lab = np.median(cv2.cvtColor(full, cv2.COLOR_BGR2LAB)[ring].astype(np.float32), 0) if ring.sum() > 100 else None
            print('lid colour (Lab):', None if lid_lab is None else [round(float(x)) for x in lid_lab], 'from', int(ring.sum()), 'px')
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
        if shape != 'disc':
            # feit: niet-gescande pixels (transparant in de bron) horen niet bij het onderdeel
            if F > 1.0:
                Hf, Wf = full_alpha.shape[:2]
                Rmf = cv2.getRotationMatrix2D((Wf / 2, Hf / 2), ang, 1.0)
                acrop = cv2.warpAffine(full_alpha.astype(np.uint8), Rmf, (Wf, Hf), flags=cv2.INTER_NEAREST)[int(round(T * F)):int(round(B * F)), int(round(L * F)):int(round(Rr * F))] > 0
            else:
                acrop = covered
            def gone(v): return v < .995
            m_ = int(1.0 * px_mm * F); h_, w_ = acrop.shape[:2]
            t0 = next((k for k in range(m_) if not gone(acrop[k].mean())), m_)
            b0 = next((k for k in range(m_) if not gone(acrop[h_ - 1 - k].mean())), m_)
            l0 = next((k for k in range(m_) if not gone(acrop[:, k].mean())), m_)
            r0 = next((k for k in range(m_) if not gone(acrop[:, w_ - 1 - k].mean())), m_)
            crop = crop[t0:crop.shape[0] - b0, l0:crop.shape[1] - r0]
            # cd: geen kartonrand; alleen een haarlijn (±0,3 mm) mag eraf, een wit kader blijft
            crop, trimmed = trim_edge_lines(crop, px_mm * F, lid_lab, *((0.3, 0.3) if fmt.startswith('cd') else ()))
            trimmed = tuple(x + y for x, y in zip(trimmed, (t0, r0, b0, l0)))
            if any(trimmed):
                result['edge_lines_trimmed_px'] = trimmed
                print('edge lines trimmed (top, right, bottom, left px):', trimmed)
        if a.pixels:
            crop = swap_pixels(a.pixels, full_bgr.shape, crop, shape, result,
                               disc=(locals().get('x0g'), locals().get('y0g'), locals().get('n2')) if F > 1.0 else (locals().get('x0f'), locals().get('y0f'), locals().get('n')),
                               rect=None if shape == 'disc' else (ang, T * F, B * F, L * F, Rr * F, locals().get('trimmed', (0, 0, 0, 0)) if shape != 'disc' else None))
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
