#!/usr/bin/env python3
"""Een deelscan zonder drukwerk op zijn plek leggen met de papierranden.

Deelscans worden op elkaar gelegd met wat er in beide gedrukt staat. Een hoek van een hoes
waar niets gedrukt staat (een effen wit vlak) heeft niets om op te passen. Maar er staat wel
iets in: de randen van de hoes.

Feiten:
  - de rand van een hoes of vel is een rechte lijn;
  - buiten die rand ligt alleen de achtergrond (klep of vel): effen, tot aan de rand van de scan;
  - dezelfde rand loopt recht door over de deelscans heen.
Dus: de twee randen in de lege deelscan moeten in het verlengde liggen van dezelfde randen in de
deelscans die al liggen. Dat geeft de draaiing en de plek, zonder iets te raden. Zijn de randen
niet te zien (wit op wit), dan is er geen feit en blijft de deelscan weg, met een melding.
"""
import math
import numpy as np, cv2

BANDS = 16            # zoveel stroken dwars op de rand; in elk een meting
STEP_DE = 8.0         # kleurverschil (Lab) dat een rand tussen papier en achtergrond minstens heeft
EVEN_DE = 12.0        # binnen dit kleurverschil is de achtergrond 'effen'
EVEN_SHARE = 0.85     # zoveel van het vlak buiten de rand moet die effen kleur hebben
LINE_TOL_MM = 0.3     # zo recht is een rand: meetpunten binnen deze afstand van de lijn
BORDER_MM = 1.0       # zo dicht bij de scanrand is een rand geen bewijs (schaduw van de scanner)
ANGLE_TOL = 4.0       # graden: zoveel mogen twee randen van de haakse hoek afwijken


def _lab(im):
    lab = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[:, :, 0] *= 100 / 255; lab[:, :, 1] -= 128; lab[:, :, 2] -= 128
    return lab


def _lines_along_x(lab, px_mm):
    """Rechte randen die ongeveer langs de x-as lopen: [(a, b, stroken)] met y = a + b*x."""
    h, w = lab.shape[:2]
    bw = w // BANDS; k = max(2, int(round(.5 * px_mm))); margin = int(math.ceil(BORDER_MM * px_mm)) + k
    points = []                                            # (strook, x-midden, y)
    for b in range(BANDS):
        prof = lab[:, b * bw:(b + 1) * bw].mean(1)
        c = np.vstack([np.zeros((1, 3), np.float32), np.cumsum(prof, 0)])
        step = np.linalg.norm((c[2 * k:] - c[k:-k]) - (c[k:-k] - c[:-2 * k]), axis=1) / k     # index i hoort bij y = i + k
        for i in range(1, len(step) - 1):
            y = i + k
            if step[i] >= STEP_DE and step[i] >= step[i - 1] and step[i] > step[i + 1] and margin <= y < h - margin:
                if step[max(0, i - k):i + k + 1].max() <= step[i]:
                    points.append((b, (b + .5) * bw, float(y)))
    tol = max(1.5, LINE_TOL_MM * px_mm); found = []; pts = np.array(points, np.float32).reshape(-1, 3)
    used = np.zeros(len(pts), bool)
    for _ in range(6):                                     # hooguit een paar randen per richting
        best = None
        free = np.nonzero(~used)[0]
        for i in free:
            for j in free:
                if pts[j, 0] - pts[i, 0] < 3:
                    continue
                slope = (pts[j, 2] - pts[i, 2]) / (pts[j, 1] - pts[i, 1])
                if abs(slope) > math.tan(math.radians(8)):
                    continue
                resid = np.abs(pts[free, 2] - (pts[i, 2] + slope * (pts[free, 1] - pts[i, 1])))
                bands = len(set(pts[free][resid <= tol][:, 0].astype(int)))
                if best is None or bands > best[0]:
                    best = (bands, i, slope)
        if best is None or best[0] < .45 * BANDS:
            break
        _, i, slope = best
        resid = np.abs(pts[:, 2] - (pts[i, 2] + slope * (pts[:, 1] - pts[i, 1])))
        on = (resid <= tol) & ~used
        b_, a_ = np.polyfit(pts[on, 1], pts[on, 2], 1)
        found.append((float(a_), float(b_), sorted(set(pts[on, 0].astype(int)))))
        used |= resid <= 3 * tol
    return found


def paper_edges(im, px_mm):
    """De papierranden in één deelscan: [{'p': punt op de rand, 'd': richting, 'n': normaal naar het
    papier toe, 'len': lengte in px}], hooguit één per kant. Lege lijst als er geen rand te zien is."""
    lab = _lab(im); h, w = lab.shape[:2]; out = []
    small = cv2.resize(lab, None, fx=.25, fy=.25, interpolation=cv2.INTER_AREA)
    for along_x in (True, False):
        L = lab if along_x else lab.transpose(1, 0, 2)
        S = small if along_x else small.transpose(1, 0, 2)
        hh, ww = L.shape[:2]
        for a_, b_, bands in _lines_along_x(L, px_mm):
            x0, x1 = bands[0] * (ww // BANDS), (bands[-1] + 1) * (ww // BANDS)
            xs = np.arange(S.shape[1]) * 4.0; ys = a_ + b_ * xs
            yy = np.arange(S.shape[0])[:, None] * 4.0
            inside_span = (xs >= x0) & (xs < x1)
            edge = (BORDER_MM + .5) * px_mm                # de strook langs de scanrand telt niet mee (schaduw van de scanner)
            inner = (yy >= edge) & (yy < hh - edge) & (xs[None, :] >= edge) & (xs[None, :] < ww - edge)
            sides = {}
            for sign in (-1, +1):                          # -1: het vlak boven de lijn, +1: eronder
                region = ((yy - ys[None, :]) * sign > 1.0 * px_mm) & inside_span[None, :] & inner
                near = region & ((yy - ys[None, :]) * sign < 3.5 * px_mm)
                if region.sum() < 50 or near.sum() < 20:
                    sides[sign] = None; continue
                med = np.median(S[region], 0)
                even = (np.linalg.norm(S[region] - med, axis=1) < EVEN_DE).mean()
                sides[sign] = {'med': med, 'even': even, 'area': int(region.sum()), 'near': np.median(S[near], 0)}
            if not sides[-1] or not sides[1]:
                continue
            if np.linalg.norm(sides[-1]['near'] - sides[1]['near']) < STEP_DE:
                continue                                   # geen stap van papier naar achtergrond
            # Feit: een onderdeel dat in delen gescand wordt, is groter dan het glas; het papier ligt
            # dus over het midden van de scan, de achtergrond aan de andere kant van de rand.
            lid = -1 if hh / 2 > a_ + b_ * ww / 2 else 1
            if sides[lid]['even'] < EVEN_SHARE:
                continue                                   # buiten de rand ligt alleen effen achtergrond
            if np.linalg.norm(sides[lid]['med'] - sides[-lid]['med']) < STEP_DE:
                continue                                   # zelfde kleur aan beide kanten: een regel tekst, geen rand
            xm = (x0 + x1) / 2; p = np.array([xm, a_ + b_ * xm]); d = np.array([1.0, b_]) / math.hypot(1, b_)
            n = np.array([-b_, 1.0]) / math.hypot(1, b_) * (-lid)          # van de achtergrond af: naar het papier
            if not along_x:
                p, d, n = p[::-1].copy(), d[::-1].copy(), n[::-1].copy()
            out.append({'p': p, 'd': d, 'n': n, 'len': float(x1 - x0), 'offset_out': float(-(n @ p)), 'lid': sides[lid]['med']})
    if out:
        # Feit: de achtergrond heeft overal dezelfde kleur. Een 'rand' met een andere kleur erbuiten hoort er niet bij.
        ref = max(out, key=lambda e: sum(o['len'] for o in out if np.linalg.norm(o['lid'] - e['lid']) < EVEN_DE))['lid']
        out = [e for e in out if np.linalg.norm(e['lid'] - ref) < EVEN_DE]
    # per kant (richting van de normaal) de buitenste rand
    best = {}
    for e in out:
        key = int(round(math.degrees(math.atan2(e['n'][1], e['n'][0])) / 90)) % 4
        if key not in best or e['offset_out'] > best[key]['offset_out']:
            best[key] = e
    return list(best.values())


def _to_canvas(e, H):
    R = H[:2, :2]; s = math.sqrt(abs(np.linalg.det(R)))
    n = R @ e['n']; n /= np.linalg.norm(n); d = R @ e['d']; d /= np.linalg.norm(d)
    return {'p': R @ e['p'] + H[:2, 2], 'd': d, 'n': n, 'len': e['len'] * s}


def _angle(v):
    return math.degrees(math.atan2(v[1], v[0]))


def _diff(a, b):
    return ((a - b + 180) % 360) - 180


def place_on_edges(imgs, H, missing, px_mm, log=print):
    """Legt deelscans die nergens op passen (geen gezamenlijk drukwerk) op hun papierranden.
    imgs: alle deelscans op rekenschaal; H: {index: 3x3} van de deelscans die al liggen.
    Geeft {index: 3x3} voor de deelscans die zo gelegd konden worden."""
    if not px_mm or not missing or len(H) < 2:
        return {}
    outline = []                                           # randen van de hoes, in het vlak van de gelegde deelscans
    for k, Hk in H.items():
        outline += [_to_canvas(e, Hk) for e in paper_edges(imgs[k], px_mm)]
    if len(outline) < 2:
        return {}
    base = _angle(max(outline, key=lambda e: e['len'])['n'])
    sides = {}                                             # kwartslag -> de buitenste rand aan die kant
    for e in outline:
        q = int(round(_diff(_angle(e['n']), base) / 90)) % 4
        if abs(_diff(_angle(e['n']), base + 90 * q)) > ANGLE_TOL:
            continue
        sides.setdefault(q, []).append(e)
    lines = {}
    for q, es in sides.items():
        n = np.mean([e['n'] for e in es], 0); n /= np.linalg.norm(n)
        far = min(float(n @ e['p']) for e in es)           # de buitenste (n wijst naar binnen)
        keep = [e for e in es if float(n @ e['p']) - far <= 1.0 * px_mm]
        wsum = sum(e['len'] for e in keep)
        n = sum(e['n'] * e['len'] for e in keep) / wsum; n /= np.linalg.norm(n)
        lines[q] = {'n': n, 'c': sum(float(n @ e['p']) * e['len'] for e in keep) / wsum}
    # dekking van wat al ligt, op klein formaat (voor: welke hoek is nog leeg?)
    def footprint(k, Hk):
        h, w = imgs[k].shape[:2]
        return (np.float32([[0, 0], [w, 0], [w, h], [0, h]]) @ Hk[:2, :2].T + Hk[:2, 2]).astype(np.float32)
    placed = {}
    for k in missing:
        own = paper_edges(imgs[k], px_mm)
        pairs = [(a, b) for a in own for b in own if a is not b and abs(abs(_diff(_angle(a['n']), _angle(b['n']))) - 90) <= ANGLE_TOL]
        if not pairs:
            continue
        ea, eb = pairs[0]
        cands = []
        for qa, la in lines.items():
            theta = math.radians(_diff(_angle(la['n']), _angle(ea['n'])))
            Rm = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
            nb = Rm @ eb['n']
            qb = next((q for q, lb in lines.items() if q != qa and abs(_diff(_angle(lb['n']), _angle(nb))) <= ANGLE_TOL), None)
            if qb is None:
                continue
            lb = lines[qb]
            # de draaiing die beide randen het best laat samenvallen
            extra = math.radians(_diff(_angle(lb['n']), _angle(nb)) / 2)
            theta += extra
            Rm = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
            A = np.array([la['n'], lb['n']]); rhs = np.array([la['c'] - la['n'] @ (Rm @ ea['p']), lb['c'] - lb['n'] @ (Rm @ eb['p'])])
            if abs(np.linalg.det(A)) < .5:
                continue
            t = np.linalg.solve(A, rhs)
            Hk = np.array([[Rm[0, 0], Rm[0, 1], t[0]], [Rm[1, 0], Rm[1, 1], t[1]], [0, 0, 1.0]])
            cands.append(Hk)
        if not cands:
            continue
        # Welke hoek: die waar nog niets ligt. Dekking tellen op een raster van 1/8.
        polys = [footprint(j, Hj) for j, Hj in list(H.items()) + list(placed.items())]
        allp = np.vstack(polys + [footprint(k, c) for c in cands]); lo = allp.min(0); sc = 1 / 8.0
        size = tuple(int(v) + 2 for v in ((allp.max(0) - lo) * sc)[::1])
        cover = np.zeros((size[1], size[0]), np.uint8)
        for poly in polys:
            cv2.fillPoly(cover, [np.round((poly - lo) * sc).astype(np.int32)], 1)
        new = []
        for c in cands:
            m = np.zeros_like(cover); cv2.fillPoly(m, [np.round((footprint(k, c) - lo) * sc).astype(np.int32)], 1)
            new.append(float(((m > 0) & (cover == 0)).sum()) / max(1, int(m.sum())))
        order = np.argsort(new)[::-1]
        if new[order[0]] < .03 or (len(order) > 1 and new[order[1]] > .5 * new[order[0]]):
            continue                                       # geen lege hoek, of niet duidelijk welke
        Hk = cands[int(order[0])]
        if not _agrees(imgs, H, k, Hk):
            continue
        placed[k] = Hk
        log(f'placed on its paper edges (no print in common with the other scans): scan {k + 1}, {new[order[0]]:.0%} new area')
    return placed


def _agrees(imgs, H, k, Hk, sc=0.125):
    """Feit: waar de nieuwe deelscan over de andere heen ligt, staat hetzelfde (papier op papier,
    achtergrond op achtergrond). Klopt dat niet, dan ligt hij niet goed."""
    pts = []
    for j, Hj in list(H.items()) + [(k, Hk)]:
        h, w = imgs[j].shape[:2]
        pts.append(np.float32([[0, 0], [w, 0], [w, h], [0, h]]) @ Hj[:2, :2].T + Hj[:2, 2])
    lo = np.vstack(pts).min(0); hi = np.vstack(pts).max(0)
    size = (int((hi[0] - lo[0]) * sc) + 2, int((hi[1] - lo[1]) * sc) + 2)
    def warp(j, Hj):
        M = np.array([[sc, 0, -lo[0] * sc], [0, sc, -lo[1] * sc]]) @ np.vstack([Hj[:2], [0, 0, 1]])
        g = cv2.cvtColor(imgs[j][:, :, :3], cv2.COLOR_BGR2GRAY)
        img = cv2.warpAffine(g, M[:2], size, flags=cv2.INTER_AREA).astype(np.float32)
        msk = cv2.warpAffine(np.full(g.shape, 255, np.uint8), M[:2], size, flags=cv2.INTER_NEAREST) > 0
        return img, cv2.erode(msk.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    gk, mk = warp(k, Hk); good = total = 0
    for j, Hj in H.items():
        gj, mj = warp(j, Hj); both = mk & mj
        if both.sum() < 200:
            continue
        d = np.abs((gk[both] - np.median(gk[both])) - (gj[both] - np.median(gj[both])))
        good += int((d <= 20).sum()); total += int(both.sum())
    return total >= 200 and good / total >= .9
