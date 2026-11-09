"""Controle per release: oordeel, maten tegen de feiten, randbanden, gat, labelhoek; plus controlebeelden."""
import sys, os, json, glob, math, re
import numpy as np, cv2
sys.path.insert(0, '/Users/andrevanos/Documents/Codex/2026-11-04/referenced-chatgpt-conversation-this-is-an/outputs/Sleeve/Resources/Tools')
import scan_rechtop as R

rel = sys.argv[1]
ev = open(f'/tmp/nacht/{rel}/events.log').read()
m = re.findall(r'"event": "destination", "path": "([^"]+)"', ev)
if not m:
    print(json.dumps({'release': rel, 'error': 'no output folder', 'tail': ev[-600:]})); sys.exit()
D = m[-1]
CTRL = os.path.expanduser('~/Desktop/sleeve_feiten/nacht/_controle'); os.makedirs(CTRL, exist_ok=True)
try:
    res = json.load(open(D + '/Studio-verwerking.json'))['results']
except Exception as e:
    print(json.dumps({'release': rel, 'error': 'no results: ' + str(e), 'tail': ev[-800:]})); sys.exit()
import scan_feitenroute as FR
words = FR.release_words(json.load(open(f'/tmp/nacht/{rel}/req.json'))['discogs'])
report = {'release': rel, 'folder': D, 'parts': []}
sheet, edges = [], []


def band(v, ref_from, ref_to):
    ref = np.median(v[ref_from:ref_to]); k = 0
    while k < 80 and abs(v[k] - ref) > 8:
        k += 1
    return k


def baseline_tilt(view):
    out = []
    for l in R.ocr_lines(view):
        if not any(R.found(R.norm(w), R.norm(l['text'])) for w in words):
            continue
        x0, y0, x1, y1 = [int(v) for v in l['box']]; h = y1 - y0
        x0 = max(0, x0); y0 = max(0, y0)
        if x1 - x0 < 30 or h < 5:
            continue
        p = cv2.cvtColor(view[max(0, y0 - h // 3):y1 + h // 3, x0:x1], cv2.COLOR_BGR2GRAY)
        _, mk = cv2.threshold(p, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if (mk > 0).mean() > .5:
            mk = 255 - mk
        xs, bots = [], []
        for x in range(mk.shape[1]):
            ys = np.nonzero(mk[:, x])[0]
            if len(ys):
                xs.append(x); bots.append(ys.max())
        if len(xs) < 20:
            continue
        xs = np.array(xs, float); bots = np.array(bots, float); best = None
        for sl in np.arange(-0.08, 0.0801, 0.002):
            r_ = bots - sl * xs; med = np.median(r_); n = (np.abs(r_ - med) < 1.5).sum()
            if best is None or n > best[0]:
                best = (n, sl)
        out.append(math.degrees(math.atan(best[1])))
    return round(float(np.median(out)), 2) if out else None


for r in res:
    p = r.get('path')
    item = {k: r.get(k) for k in ('part', 'verdict', 'why', 'size_mm', 'applied', 'message')}
    item['upright'] = (r.get('upright') or {}).get('rotate_clockwise')
    item['name'] = os.path.basename(p) if p else None
    if not p or not os.path.exists(p):
        report['parts'].append(item); continue
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED); h, w = im.shape[:2]
    dpi = r.get('dpi') or 300; pxmm = dpi / 25.4
    item['px'] = [w, h]
    if im.shape[2] == 4:
        a = im[:, :, 3]
        item['hole_transparent'] = bool(a[h // 2, w // 2] == 0)
        col = a[h // 2, w // 2:]; idx = np.nonzero(col > 0)[0]
        item['hole_mm'] = round(2 * idx[0] / pxmm, 1) if len(idx) else None
        item['corner_transparent'] = bool(a[2, 2] == 0)
        # randring: helderheid net binnen de rand in 72 richtingen tegen 3 mm verder naar binnen
        g = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY).astype(float); rr = w / 2; diffs = []
        for k in range(72):
            t = 2 * math.pi * k / 72
            o = g[int(h / 2 + (rr - 3) * math.sin(t)), int(w / 2 + (rr - 3) * math.cos(t))]
            i_ = g[int(h / 2 + (rr - 3 * pxmm) * math.sin(t)), int(w / 2 + (rr - 3 * pxmm) * math.cos(t))]
            diffs.append(abs(o - i_))
        item['rim_diff_max'] = int(max(diffs)); item['rim_diff_median'] = int(np.median(diffs))
        # label recht?
        lr = int(52 * pxmm); lab = im[h // 2 - lr:h // 2 + lr, w // 2 - lr:w // 2 + lr, :3]
        lab = cv2.resize(lab, (1240, 1240), interpolation=cv2.INTER_AREA)
        item['label_tilt_deg'] = baseline_tilt(lab)
        al = im[:, :, 3:4] / 255.
        chk = np.indices((h, w)).sum(0) // max(1, w // 60) % 2
        bg = np.where(chk[..., None] == 1, np.array([255, 0, 255]), np.array([0, 200, 0])).astype(np.uint8)
        vis = (im[:, :, :3] * al + bg * (1 - al)).astype(np.uint8)
        # randdetail 4 richtingen
        z = int(4 * pxmm); pad = z
        big = np.zeros((h + 2 * pad, w + 2 * pad, 3), np.uint8); big[:, :] = (0, 200, 0); big[pad:pad + h, pad:pad + w] = vis
        tiles = []
        for d in (0, 90, 180, 270):
            t = math.radians(d); x = int(w / 2 + pad + (rr - z / 2) * math.cos(t)); y = int(h / 2 + pad + (rr - z / 2) * math.sin(t))
            tiles.append(cv2.resize(big[y - z:y + z, x - z:x + z], (160, 160), interpolation=cv2.INTER_AREA))
        zc = int(14 * pxmm); tiles.append(cv2.resize(vis[h // 2 - zc:h // 2 + zc, w // 2 - zc:w // 2 + zc], (160, 160), interpolation=cv2.INTER_AREA))
        edges.append(np.hstack(tiles))
    else:
        vis = im[:, :, :3]
        L = cv2.cvtColor(vis, cv2.COLOR_BGR2LAB)[:, :, 0].astype(float)
        a_, b_ = int(1.0 * pxmm), int(1.5 * pxmm)
        item['edge_band_px'] = [band(L.mean(1), a_, b_), band(L.mean(1)[::-1], a_, b_), band(L.mean(0), a_, b_), band(L.mean(0)[::-1], a_, b_)]
        z = int(3 * pxmm); m_ = min(h, w) // 2
        tiles = [cv2.resize(vis[:z, w // 2 - z:w // 2 + z], (320, 160), interpolation=cv2.INTER_AREA),
                 cv2.resize(vis[h - z:, w // 2 - z:w // 2 + z], (320, 160), interpolation=cv2.INTER_AREA),
                 cv2.resize(cv2.rotate(vis[h // 2 - z:h // 2 + z, :z], cv2.ROTATE_90_CLOCKWISE), (320, 160), interpolation=cv2.INTER_AREA),
                 cv2.resize(cv2.rotate(vis[h // 2 - z:h // 2 + z, w - z:], cv2.ROTATE_90_CLOCKWISE), (320, 160), interpolation=cv2.INTER_AREA)]
        edges.append(np.hstack(tiles)[:, :800] if False else cv2.resize(np.hstack(tiles), (800, 100)))
    s = 360 / max(h, w); t = cv2.resize(vis, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    c = np.full((400, 380, 3), 255, np.uint8); c[:t.shape[0], :t.shape[1]] = t
    cv2.putText(c, f"{item['part']} {item['verdict']}", (4, 392), 0, .5, (0, 0, 0), 1)
    sheet.append(c); sheet.append(np.full((400, 6, 3), 255, np.uint8))
    report['parts'].append(item)
if sheet:
    cv2.imwrite(f'{CTRL}/{rel}_overzicht.jpg', np.hstack(sheet))
if edges:
    W = max(e.shape[1] for e in edges)
    cv2.imwrite(f'{CTRL}/{rel}_randen.jpg', np.vstack([np.hstack([e, np.full((e.shape[0], W - e.shape[1], 3), 255, np.uint8)]) for e in edges]))
json.dump(report, open(f'{CTRL}/{rel}.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(report, ensure_ascii=False))
