#!/usr/bin/env python3
"""Feit: kant A en kant B (en C en D) zijn dezelfde plaat, dus hetzelfde vinyl.
Verschillen in kleur komen van de scanner (elke kant apart gescand en belicht).
Meet de kleur van het vinyl (ring tussen label en rand) op beide kanten en trek
het verschil gelijk naar het midden ertussen. Alleen kleur/licht, geen vorm.

Gebruik: scan_kleur_kanten.py kantA.png kantB.png   (bestanden worden bijgewerkt)
"""
import sys, cv2, numpy as np


def ring_colour(img):
    h, w = img.shape[:2]; yy, xx = np.ogrid[:h, :w]
    r = np.hypot(xx - w / 2, yy - h / 2) / (w / 2)
    m = (r > .45) & (r < .9) & (img[:, :, 3] > 250)
    lin = (img[:, :, :3][m].astype(np.float32) / 255) ** 2.2        # in lineair licht vergelijken
    return np.median(lin, 0)


DARK = (12 / 255) ** 2.2        # een kleurkanaal dat in het vinyl (bijna) zwart is, meet niets
SCANNER = (0.85, 1.18)          # zoveel kan dezelfde plaat tussen twee scans in licht verschillen


def gains(ca, cb):
    """Feit: het verschil tussen twee scans van dezelfde plaat is een klein verschil in belichting
    per kleurkanaal. Geeft per kant de correctie naar het midden, of None als het verschil groter is
    dan een scanner kan verklaren (dan zijn de kanten echt anders, bv. gemarmerd vinyl).
    Een kanaal waarin het vinyl bijna zwart is (rood bij blauw vinyl) zegt niets over de belichting:
    dat kanaal blijft zoals het is. (Zonder dit werd een wit label blauwgroen: 0,5.27, Urban Solitude blauw.)"""
    target = (ca + cb) / 2; out = []
    for c in (ca, cb):
        g = target / np.maximum(c, 1e-6)
        g[np.minimum(ca, cb) < DARK] = 1.0
        out.append(g)
    if any((g < SCANNER[0]).any() or (g > SCANNER[1]).any() for g in out):
        return None
    return out


def main():
    a, b = sys.argv[1], sys.argv[2]
    A = cv2.imread(a, cv2.IMREAD_UNCHANGED); B = cv2.imread(b, cv2.IMREAD_UNCHANGED)
    ca, cb = ring_colour(A), ring_colour(B)
    found = gains(ca, cb)
    if found is None:
        print('sides differ more in colour than a scanner explains; both kept as scanned'); return
    for path, img, gain in ((a, A, found[0]), (b, B, found[1])):
        if np.allclose(gain, 1.0, atol=.004):
            print(path.split('/')[-1], 'already the same colour; kept as scanned'); continue
        lin = (img[:, :, :3].astype(np.float32) / 255) ** 2.2 * gain
        img[:, :, :3] = np.clip(lin ** (1 / 2.2) * 255 + .5, 0, 255).astype(np.uint8)
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as im:
            dpi = im.info.get('dpi')
        out = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))
        out.save(path, dpi=dpi) if dpi else out.save(path)
        print(path.split('/')[-1], 'gain per channel (B,G,R):', np.round(gain, 3).tolist())


if __name__ == '__main__':
    main()
