"""Resolutie van een scan, op feiten.

Feiten:
  - Een jpeg kan twee resoluties bevatten: in het JFIF-deel en in het EXIF-deel. Scanners
    schrijven de echte resolutie in EXIF; een JFIF-waarde zonder eenheid is alleen een
    verhouding, geen resolutie.
  - EXIF zonder eenheid betekent volgens de EXIF-norm: per inch.
  - Een flatbedscanner is hooguit A3 (±300 x 430 mm). Een scan die bij zijn opgeslagen
    resolutie groter zou zijn, heeft een verkeerde resolutie in het bestand.
"""
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SCANNER_MAX_MM = 450.0


def read(path):
    """Resolutie in dpi uit het bestand, of 0.0 als die er niet (betrouwbaar) in staat."""
    try:
        with Image.open(path) as im:
            w, h = im.size
            exif = im.getexif()
            x, unit = exif.get(282), exif.get(296)
            candidates = []
            if x:
                try:
                    v = float(x)
                    if unit in (None, 2):
                        candidates.append(v)
                    elif unit == 3:
                        candidates.append(v * 2.54)
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
            jd, ju = im.info.get('jfif_density'), im.info.get('jfif_unit')
            if jd and ju in (1, 2):
                candidates.append(float(jd[0]) * (2.54 if ju == 2 else 1.0))
            d = im.info.get('dpi')
            if d and not candidates:
                candidates.append(float(d[0]))
    except Exception:
        return 0.0
    for v in candidates:
        if 50 < v < 5000 and max(w, h) / v * 25.4 <= SCANNER_MAX_MM:
            return v
    return 0.0


def size_px(path):
    with Image.open(path) as im:
        return im.size
