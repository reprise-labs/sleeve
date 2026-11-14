#!/usr/bin/env python3
"""Een sticker uitsnijden uit één scan (de sticker op zijn plastic hoes). Alleen op feiten:

  rechthoek met kader  een gesloten rechthoek met afgeronde hoeken (het gedrukte kader van een Music On
                       Vinyl-sticker); de rand van de sticker ligt rondom op dezelfde afstand erbuiten.
                       Die afstand wordt op alle vier zijden tegelijk gezocht (de zwakste zijde telt).
  rechthoek zonder     een gesloten rechthoek met afgeronde hoeken die zelf de rand is (strook "new album").
  cirkel               een rand die rondom doorloopt, loodrecht op de straal (ronde sticker), precies gemeten
                       in 180 richtingen en een cirkel erdoor.

Uitsnijden met transparante hoeken (rechthoek: afgeronde hoeken; cirkel: echte cirkel). Twijfel als de rand
niet rondom te zien is. Rechtzetten gebeurt daarna in de route, op de tekst (scan_rechtop).

Gebruik: scan_sticker.py scan.png --out sticker.png [--dpi 600]
Uitvoer: één JSON-regel {verdict, why, shape, size_mm, dpi, angle, ...}
"""
import argparse, json, math, os, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
WORK = 1600            # rekenen op een beeld van ±1600 px (lange zijde)
FILL = 0.95            # een rechthoek met afgeronde hoeken vult zijn omschreven rechthoek voor minstens zoveel
RIM_CIRCLE = 0.6       # zoveel van een cirkel moet als doorlopende rand te zien zijn


def load(path):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    if im is None:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as p:
            im = cv2.cvtColor(np.asarray(p.convert('RGB')), cv2.COLOR_RGB2BGR)
    return im


def closed_rects(g, w, h):
    """Gesloten, bijna rechthoekige vormen (kader of rand): het binnenste van de randen."""
    e = cv2.dilate(cv2.Canny(g, 30, 90), np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(255 - e, connectivity=4)
    out = []
    for i in range(1, n):
        x, y, ww, hh, a = st[i]
        if x == 0 or y == 0 or x + ww >= w or y + hh >= h or a < 0.005 * w * h:
            continue
        c = max(cv2.findContours((lab[y:y + hh, x:x + ww] == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
        c = c + np.array([x, y])
        r = cv2.minAreaRect(c); ra = r[1][0] * r[1][1]; ca = cv2.contourArea(cv2.convexHull(c))
        if ra > 0 and ca / ra > FILL:
            out.append((ra, r, ca, c))
    return sorted(out, key=lambda t: -t[0])


def outer_offset(im, rect, ang):
    """Rand van de sticker buiten het kader: per zijde de sprong in kleur naar buiten; de afstand die op alle
    vier zijden een duidelijke sprong heeft. Geeft (afstand px, zwakste sterkte, scheefstand-gedraaid beeld, kader)."""
    h, w = im.shape[:2]; c0 = rect[0]
    R = cv2.getRotationMatrix2D(c0, ang, 1.0)
    rot = cv2.warpAffine(im, R, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    bp = np.c_[cv2.boxPoints(rect), np.ones(4)] @ R.T
    L, T = bp.min(0); Rr, B = bp.max(0); W0, H0 = Rr - L, B - T
    lab = cv2.cvtColor(rot, cv2.COLOR_BGR2LAB).astype(np.float32)
    reach = int(0.12 * min(W0, H0)); k = 4
    def prof(name):
        if name in ('top', 'bottom'):
            xs = np.arange(int(L + .15 * W0), int(Rr - .15 * W0)); base, sg = (T, -1) if name == 'top' else (B, 1)
            rows = [int(base + sg * d) for d in range(reach) if 0 <= int(base + sg * d) < h]
            p = np.array([np.median(lab[r, xs], 0) for r in rows])
        else:
            ys = np.arange(int(T + .15 * H0), int(B - .15 * H0)); base, sg = (L, -1) if name == 'left' else (Rr, 1)
            cols = [int(base + sg * d) for d in range(reach) if 0 <= int(base + sg * d) < w]
            p = np.array([np.median(lab[ys, c], 0) for c in cols])
        j = np.zeros(len(p))
        if len(p) > 2 * k:
            j[k:-k] = np.linalg.norm(p[2 * k:] - p[:-2 * k], axis=1)
        j[:max(k + 2, int(.01 * min(W0, H0)))] = 0
        return j
    J = {s: prof(s) for s in ('top', 'bottom', 'left', 'right')}
    n = min(len(j) for j in J.values())
    # de dichtstbijzijnde afstand waar alle vier zijden een duidelijke sprong hebben (een drukke achtergrond heeft
    # verder naar buiten overal sprongen; de rand van de sticker is de eerste)
    best = (None, 0.0); first = None
    for o in range(k + 2, n - 2):
        s = min(float(j[max(0, o - 2):o + 3].max()) / max(float(j.max()), 1e-6) for j in J.values())
        if s > best[1] + 1e-6:
            best = (o, s)
        if first is None and s >= .5:
            first = (o, s)
    if first is not None:
        # zelfde sprong een paar pixels verder kan sterker zijn: neem binnen 3 px de sterkste
        # de top van die eerste sprong (gemiddeld over de vier zijden), een pixel naar binnen (de randpixel is gemengd)
        o0 = first[0]
        prof_ = np.mean([j / max(float(j.max()), 1e-6) for j in (J[s_][:n] for s_ in J)], 0)
        o = o0 + int(np.argmax(prof_[o0:min(n, o0 + 3)]))
        best = (max(k + 1, o - 1), first[1])
    return best[0], best[1], rot, (L, T, Rr, B)


def round_rect_mask(cw, ch, r):
    m = np.zeros((ch * 4, cw * 4), np.uint8); rr = max(1, int(r * 4))
    cv2.rectangle(m, (rr, 0), (cw * 4 - rr, ch * 4), 255, -1); cv2.rectangle(m, (0, rr), (cw * 4, ch * 4 - rr), 255, -1)
    for x_, y_ in ((rr, rr), (cw * 4 - rr, rr), (rr, ch * 4 - rr), (cw * 4 - rr, ch * 4 - rr)):
        cv2.circle(m, (x_, y_), rr, 255, -1, cv2.LINE_AA)
    return cv2.resize(m, (cw, ch), interpolation=cv2.INTER_AREA)


def find_circle(im):
    """Ronde sticker: rand rondom doorlopend en loodrecht op de straal; daarna precies (180 richtingen)."""
    h, w = im.shape[:2]
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 2).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1); mag = np.hypot(gx, gy)
    c = cv2.HoughCircles(g.astype(np.uint8), cv2.HOUGH_GRADIENT, dp=1, minDist=20, param1=80, param2=30,
                         minRadius=int(.08 * min(h, w)), maxRadius=int(.5 * min(h, w)))
    best = None
    for x, y, r in (c[0][:30] if c is not None else []):
        hits = n = 0
        for a in np.linspace(0, 2 * np.pi, 360, endpoint=False):
            xs, ys = int(x + r * math.cos(a)), int(y + r * math.sin(a))
            if 2 <= xs < w - 2 and 2 <= ys < h - 2:
                n += 1; win = mag[ys - 2:ys + 3, xs - 2:xs + 3]; j = np.unravel_index(np.argmax(win), win.shape); yy, xx = ys - 2 + j[0], xs - 2 + j[1]
                hits += mag[yy, xx] > 25 and abs(gx[yy, xx] * math.cos(a) + gy[yy, xx] * math.sin(a)) / max(mag[yy, xx], 1e-6) > .8
        if n > 300 and (best is None or hits / n > best[0]):
            best = (hits / n, x, y, r)
    if best is None:
        return None
    s, x, y, r = best
    pts = []
    for a in np.linspace(0, 2 * np.pi, 180, endpoint=False):
        rs = np.arange(r - 8, r + 8, .5); xs = x + rs * math.cos(a); ys = y + rs * math.sin(a)
        v = cv2.remap(g, xs.astype(np.float32).reshape(1, -1), ys.astype(np.float32).reshape(1, -1), cv2.INTER_LINEAR)[0]
        i = int(np.argmax(np.abs(np.diff(v)))); pts.append((x + rs[i] * math.cos(a), y + rs[i] * math.sin(a)))
    P = np.array(pts); D, E, F = np.linalg.lstsq(np.c_[P, np.ones(len(P))], -(P ** 2).sum(1), rcond=None)[0]
    return s, -D / 2, -E / 2, math.sqrt(max(D * D / 4 + E * E / 4 - F, 1))


def main():
    p = argparse.ArgumentParser(); p.add_argument('scan'); p.add_argument('--out', required=True); p.add_argument('--dpi', type=float, default=0.0)
    a = p.parse_args()
    full = load(a.scan); H, W = full.shape[:2]
    dpi = a.dpi
    if not dpi:
        try:
            import scan_dpi; dpi = scan_dpi.read(a.scan) or 0.0
        except Exception:
            dpi = 0.0
    s = min(1.0, WORK / max(H, W)); im = cv2.resize(full, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else full.copy()
    h, w = im.shape[:2]; g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 2)
    res = {'verdict': 'GOED', 'why': []}
    rects = closed_rects(g, w, h)
    circ = find_circle(im)
    choice = None
    if rects:
        ra, rect, ca, cont = rects[0]
        ang = rect[2] - 90 if rect[2] > 45 else rect[2]      # alleen het scheefstaan; een kwartslag doet het lezen van de tekst
        off, strength, rot, (L, T, Rr, B) = outer_offset(im, rect, ang)
        r_in = math.sqrt(max(0, (ra - ca) / (4 - math.pi)))
        choice = ('rect', rect, ang, off, strength, r_in, ra, cont)
    if circ and circ[0] >= RIM_CIRCLE and (choice is None or math.pi * circ[3] ** 2 > choice[6] * 1.1):
        choice = ('circle',) + circ
    if choice is None:
        res.update(verdict='FOUT', why=['no sticker found: no closed rounded rectangle and no round edge in this scan'])
        print(json.dumps(res)); return
    if choice[0] == 'circle':
        _, rim, cx, cy, r = choice
        cx, cy, r = cx / s, cy / s, r / s
        n = int(2 * r) + 2; x0, y0 = int(round(cx - r)), int(round(cy - r))
        crop = np.zeros((n, n, 4), np.uint8)
        sx0, sy0 = max(0, x0), max(0, y0); sub = full[sy0:y0 + n, sx0:x0 + n]
        crop[sy0 - y0:sy0 - y0 + sub.shape[0], sx0 - x0:sx0 - x0 + sub.shape[1], :3] = sub
        yy, xx = np.mgrid[0:n, 0:n]; d = np.hypot(xx - (cx - x0), yy - (cy - y0))
        crop[:, :, 3] = (np.clip(r - .7 - d + .5, 0, 1) * 255).astype(np.uint8)   # net binnen de rand, zachte rand van één pixel
        res.update(shape='circle', rim_seen=round(rim, 2), area_frac=round(math.pi * r * r / (W * H), 4))
        if rim < .75:
            res['verdict'] = 'TWIJFEL'; res['why'].append(f'the round edge is visible on only {100 * rim:.0f}% of the circle')
    else:
        _, rect, ang, off, strength, r_in, ra, cont = choice
        R = cv2.getRotationMatrix2D((rect[0][0] / s, rect[0][1] / s), ang, 1.0)
        rotf = cv2.warpAffine(full, R, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        bp = np.c_[cv2.boxPoints(((rect[0][0] / s, rect[0][1] / s), (rect[1][0] / s, rect[1][1] / s), rect[2])), np.ones(4)] @ R.T
        L, T = bp.min(0); Rr, B = bp.max(0)
        # Kader of rand? Net buiten een gedrukt kader is het nog sticker (zelfde kleur als binnen); net buiten de
        # rand van de sticker is het achtergrond. (Strook "new album": geen kader, de gesloten vorm is de rand.)
        labr = cv2.cvtColor(rotf, cv2.COLOR_BGR2LAB).astype(np.float32)
        gap = max(3, int(.004 * max(Rr - L, B - T)))
        xs_ = slice(int(L + .3 * (Rr - L)), int(L + .7 * (Rr - L))); ys_ = slice(int(T + .3 * (B - T)), int(T + .7 * (B - T)))
        def band(y0, y1, x0, x1):
            y0, y1, x0, x1 = max(0, int(y0)), min(H, int(y1)), max(0, int(x0)), min(W, int(x1))
            return labr[y0:y1, x0:x1].reshape(-1, 3)
        ins = np.concatenate([band(T + 2 * gap, T + 4 * gap, xs_.start, xs_.stop), band(B - 4 * gap, B - 2 * gap, xs_.start, xs_.stop),
                              band(ys_.start, ys_.stop, L + 2 * gap, L + 4 * gap), band(ys_.start, ys_.stop, Rr - 4 * gap, Rr - 2 * gap)])
        o = (off / s) if (off is not None and strength >= .35) else 0.0
        # Feit: net binnen de snede is het sticker, geen achtergrond. Vanaf de gevonden rand naar binnen schuiven tot
        # de strook net binnen de snede de kleur van de sticker heeft (gemeten verderop binnen); zo valt er geen
        # randje achtergrond mee, of de gevonden vorm nu het kader was of al de rand (strook "new album").
        st_c = np.median(ins, 0) if len(ins) else None
        while st_c is not None and o > -2 * gap:
            b_ = np.concatenate([band(T - o, T - o + 2, xs_.start, xs_.stop), band(B + o - 2, B + o, xs_.start, xs_.stop),
                                 band(ys_.start, ys_.stop, L - o, L - o + 2), band(ys_.start, ys_.stop, Rr + o - 2, Rr + o)])
            if len(b_) and float(np.linalg.norm(np.median(b_, 0) - st_c)) < 30:
                break
            o -= 1
        o -= 1                                                     # de randpixel is gemengd
        res.update(shape='rectangle with frame' if o > 2 * gap else 'rectangle', edge_from_shape_px=round(o, 1))
        L, T, Rr, B = L - o, T - o, Rr + o, B + o
        crop = rotf[max(0, int(round(T))):int(round(B)), max(0, int(round(L))):int(round(Rr))]
        ch, cw = crop.shape[:2]
        # de vorm van het kader zelf (met zijn echte hoeken), rondom o groter: de vorm van de sticker
        cf = (np.c_[cont.reshape(-1, 2) / s, np.ones(len(cont))] @ R.T) - [max(0, int(round(T))), max(0, int(round(L)))][::-1]
        m4 = np.zeros((ch * 4, cw * 4), np.uint8)
        cv2.fillPoly(m4, [np.round(cv2.convexHull(cf.astype(np.float32)).reshape(-1, 2) * 4).astype(np.int32)], 255)
        if o > 0:
            rr = int(round(o * 4)); m4 = cv2.dilate(m4, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rr + 1, 2 * rr + 1)))
        mask = cv2.resize(m4, (cw, ch), interpolation=cv2.INTER_AREA)
        # Hoeken op kleur: de hoek van de sticker kan ronder zijn dan zijn kader. In elk hoekvak wordt wat de kleur
        # van de achtergrond heeft (gemeten net buiten de rechte zijden) en aan de buitenhoek vastzit, transparant.
        labf = cv2.cvtColor(rotf, cv2.COLOR_BGR2LAB).astype(np.float32)
        t0, l0 = max(0, int(round(T))), max(0, int(round(L)))
        band = max(3, int(o * .6)) if o > 0 else 4
        mid = lambda a_, b_: slice(int(a_ + .3 * (b_ - a_)), int(a_ + .7 * (b_ - a_)))
        outside = np.concatenate([labf[max(0, t0 - band):t0, mid(l0, l0 + cw)].reshape(-1, 3), labf[t0 + ch:t0 + ch + band, mid(l0, l0 + cw)].reshape(-1, 3),
                                  labf[mid(t0, t0 + ch), max(0, l0 - band):l0].reshape(-1, 3), labf[mid(t0, t0 + ch), l0 + cw:l0 + cw + band].reshape(-1, 3)])
        lc = labf[t0:t0 + ch, l0:l0 + cw]
        inside = np.concatenate([lc[band:2 * band, mid(0, cw)].reshape(-1, 3), lc[ch - 2 * band:ch - band, mid(0, cw)].reshape(-1, 3),
                                 lc[mid(0, ch), band:2 * band].reshape(-1, 3), lc[mid(0, ch), cw - 2 * band:cw - band].reshape(-1, 3)])
        if len(outside) > 20 and len(inside) > 20:
            bg_c, st_c = np.median(outside, 0), np.median(inside, 0)
            if np.linalg.norm(bg_c - st_c) > 12:
                q = int(min(cw, ch) * .12)
                for (y0, x0) in ((0, 0), (0, cw - q), (ch - q, 0), (ch - q, cw - q)):
                    sub = lc[y0:y0 + q, x0:x0 + q]
                    is_bg = (np.linalg.norm(sub - bg_c, axis=2) < .5 * np.linalg.norm(sub - st_c, axis=2)).astype(np.uint8)   # duidelijk achtergrond
                    cy_, cx_ = (0 if y0 == 0 else q - 1), (0 if x0 == 0 else q - 1)
                    if is_bg[cy_, cx_]:
                        ff = is_bg.copy(); m_ = np.zeros((q + 2, q + 2), np.uint8)
                        cv2.floodFill(ff, m_, (cx_, cy_), 2)
                        cut_ = cv2.dilate((ff == 2).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0   # en de gemengde randpixel
                        mask[y0:y0 + q, x0:x0 + q][cut_] = 0
                mask = cv2.GaussianBlur(mask, (3, 3), 0)
        crop = np.dstack([crop, mask])
        res['angle'] = round(ang, 2)
        res['area_frac'] = round(crop.shape[0] * crop.shape[1] / (W * H), 4)
        res['corner_px'] = round(r_in / s, 1)          # straal van de hoeken van de gevonden vorm (0 = scherpe hoeken)
        if off is not None and strength < .35:
            res['verdict'] = 'TWIJFEL'; res['why'].append('the edge of the sticker is not equally visible on all four sides')
    cv2.imwrite(a.out, crop)
    try:
        from PIL import Image
        if dpi:
            with Image.open(a.out) as im_:
                im_.load(); im_.save(a.out, dpi=(dpi, dpi))
    except Exception:
        pass
    res['dpi'] = dpi
    res['size_mm'] = [round(crop.shape[1] / dpi * 25.4, 1), round(crop.shape[0] / dpi * 25.4, 1)] if dpi else None
    if not dpi:
        res['why'].append('the scan has no resolution (dpi) stored: no size in mm')
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
