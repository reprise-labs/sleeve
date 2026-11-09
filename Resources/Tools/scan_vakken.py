#!/usr/bin/env python3
"""Vakken vooraf invullen, alleen op feiten. Wat niet vaststaat, blijft leeg voor de gebruiker.

Feiten:
  back   de scan bevat de barcode van deze release (Discogs-barcode, cijfer voor cijfer)
  front  de scan komt aantoonbaar overeen met de hoesfoto van Discogs (type 'primary'),
         of, zonder primary, de eerste foto die Discogs als hoes toont; en met geen
         andere Discogs-foto beter (genoeg overeenkomende punten)
  cd     (cd-uitgave, één schijf) er ligt een cirkel van 120 mm in de scan, gemeten
         met de resolutie uit het bestand

Gebruik: scan_vakken.py <discogs-url> <cd|vinyl> <vakken,komma> <scan> ...
Uitvoer: één JSON-regel {"groups": [{"part": ..., "files": [...]}], "why": {scan: reden}}
"""
import json, os, re, subprocess, sys, tempfile, math
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import scan_dpi
import scan_discogs as D

OCR = os.path.join(HERE, 'sleeve_ocr')
THUMB = 1600
MIN_FRONT = 30          # overeenkomende punten met de hoesfoto


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
        r = subprocess.run([OCR, path, '--identify'], capture_output=True, text=True, timeout=60)
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


def main():
    url, fmt, slots = sys.argv[1], sys.argv[2], [s for s in sys.argv[3].split(',') if s]
    scans = sys.argv[4:]
    rid = re.search(r'/release/(\d+)', url)
    rel = json.loads(D.get(f'https://api.discogs.com/releases/{rid.group(1)}')) if rid else {}
    codes = [re.sub(r'\D', '', i.get('value', '')) for i in rel.get('identifiers', []) if i.get('type') == 'Barcode']
    imgs, roles = [], []
    for im in rel.get('images', []):
        try:
            arr = cv2.imdecode(np.frombuffer(D.get(im['uri']), np.uint8), cv2.IMREAD_COLOR)
            if arr is not None:
                imgs.append(arr); roles.append(im.get('type', 'secondary'))
        except Exception:
            pass
    # Discogs' eigen hoesfoto: type 'primary'; zonder primary toont Discogs de eerste foto als hoes
    primary = roles.index('primary') if 'primary' in roles else (0 if imgs else None)
    claims, why = {}, {}
    with tempfile.TemporaryDirectory() as work:
        for s in scans:
            found = []
            if 'back' in slots and codes and any(same_barcode(b, c) for b in barcodes(s) for c in codes):
                found.append(('back', 'the release barcode is on this scan'))
            im, scale = thumb(s, work)
            if im is None:
                continue
            if 'front' in slots and primary is not None:
                m = D.matches(im, imgs)
                if m and m[0][1] == primary and m[0][0] >= MIN_FRONT:
                    found.append(('front', f'matches the Discogs cover photo ({m[0][0]} points)'))
            cd_slot = 'cd' if 'cd' in slots else None
            if fmt == 'cd' and cd_slot:
                dpi = scan_dpi.read(s)
                if dpi and has_cd(im, dpi * scale / 25.4):
                    found.append((cd_slot, 'a 120 mm disc lies on this scan'))
            if len(found) == 1:            # twee feiten die elkaar tegenspreken: niet kiezen
                claims.setdefault(found[0][0], []).append(s); why[s] = found[0][1]
            elif found:
                why[s] = 'conflicting facts: ' + ', '.join(p for p, _ in found)
    # een cd-vak hoort bij één schijf: meer kandidaten dan dat is geen feit meer
    if len(claims.get('cd', [])) > 1:
        for s in claims.pop('cd'):
            why[s] = 'more than one scan has a disc'
    print(json.dumps({'groups': [{'part': p, 'files': f} for p, f in claims.items()], 'why': why}, ensure_ascii=False))


if __name__ == '__main__':
    main()
