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


def main():
    a, b = sys.argv[1], sys.argv[2]
    A = cv2.imread(a, cv2.IMREAD_UNCHANGED); B = cv2.imread(b, cv2.IMREAD_UNCHANGED)
    ca, cb = ring_colour(A), ring_colour(B); target = (ca + cb) / 2
    for path, img, c in ((a, A, ca), (b, B, cb)):
        gain = target / np.maximum(c, 1e-4)
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
