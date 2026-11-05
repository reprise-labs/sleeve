#!/usr/bin/env python3
"""Stand en kleur van een (samengevoegde) scan afstemmen op Discogs.

Haalt de foto's van een Discogs-uitgave op, zoekt de foto die het best bij de
scan past (zelfde label/hoes) en neemt daarvan over:
  - de stand: rechtop zoals op Discogs (plaat: exacte hoek, label recht;
    hoes: in stappen van 90 graden, rechtzetten doet scan_stitch al)
  - de kleur: de hoofdkleur (bv. oranje vinyl) wordt naar de Discogs-kleur
    geschoven; wit, zwart en grijs blijven zoals ze zijn

Gebruik:
  python3 scan_discogs.py scan.png https://www.discogs.com/release/33664818-...
  python3 scan_discogs.py scan.png eigen_foto.jpg     (eigen referentiefoto)
      [--uit ander.png]      standaard: scan.png overschrijven
      [--alleen-stand] [--alleen-kleur]
Werkt zonder Discogs-account (openbare API).
"""
import argparse, io, json, os, re, sys, urllib.request
import numpy as np
import cv2
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

UA = 'Sleeve/0.3.1'


def get(url):
    """Ophalen; lukt dat niet met Python (bv. geen certificaten op deze Mac), dan met curl."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read()
    except Exception as error:
        if getattr(getattr(error,'reason',error),'errno',None) in (13,51,64,65):
            raise RuntimeError('Geen verbinding met Discogs. Controleer de internetverbinding en de netwerktoegang van Sleeve; je kunt ook een eigen referentiefoto gebruiken.') from error
        import subprocess
        r = subprocess.run(['curl', '-fsSL', '-A', UA, '--connect-timeout', '8', '--max-time', '20', url], capture_output=True)
        if r.returncode:
            raise RuntimeError(f'ophalen mislukt: {url}')
        return r.stdout


def release_images(url):
    m = re.search(r'/release/(\d+)', url)
    if not m:
        mm = re.search(r'/master/(\d+)', url)
        if not mm:
            sys.exit('geen Discogs-release in de link gevonden')
        master = json.loads(get(f'https://api.discogs.com/masters/{mm.group(1)}'))
        rid = master['main_release']
    else:
        rid = m.group(1)
    rel = json.loads(get(f'https://api.discogs.com/releases/{rid}'))
    out = []
    for im in rel.get('images', []):
        try:
            data = get(im['uri'])
            arr = np.asarray(Image.open(io.BytesIO(data)).convert('RGB'))
            out.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
        except Exception:
            pass
    return rel.get('title', ''), out


def on_white(rgba):
    bgr = rgba[..., :3].astype(np.float32); a = rgba[..., 3:4].astype(np.float32) / 255
    return (bgr * a + 255 * (1 - a)).astype(np.uint8)


def matches(ours, imgs):
    """Alle Discogs-foto's die passen: [(overeenkomsten, index, transformatie ons -> discogs)], beste eerst."""
    sift = cv2.SIFT_create(4000)
    g = cv2.cvtColor(ours, cv2.COLOR_BGR2GRAY)
    k1, d1 = sift.detectAndCompute(g, None)
    found = []
    if d1 is None or len(d1) < 10:
        return found
    for n, im in enumerate(imgs):
        k2, d2 = sift.detectAndCompute(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), None)
        if d2 is None or len(d2) < 10:
            continue
        m = cv2.BFMatcher().knnMatch(d1, d2, k=2)
        good = [a for a, b in (x for x in m if len(x) == 2) if a.distance < 0.75 * b.distance]
        if len(good) < 12:
            continue
        src = np.float32([k1[x.queryIdx].pt for x in good]); dst = np.float32([k2[x.trainIdx].pt for x in good])
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4)
        if M is None:
            continue
        k = int(inl.sum())
        if k >= 20:
            found.append((k, n, M))
    return sorted(found, key=lambda x: -x[0])


def hsv_f(bgr):
    h = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    return h[..., 0] * 360 / 256, h[..., 1] / 255, h[..., 2] / 255


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('scan'); p.add_argument('discogs', help='Discogs-link of een eigen referentiefoto')
    p.add_argument('extra', nargs='*', help='meer eigen referentiefoto\'s')
    p.add_argument('--uit'); p.add_argument('--alleen-stand', action='store_true'); p.add_argument('--alleen-kleur', action='store_true')
    a = p.parse_args()
    with Image.open(a.scan) as original:
        metadata = {key:original.info[key] for key in ('dpi','icc_profile') if key in original.info}
    raw = cv2.imread(a.scan, cv2.IMREAD_UNCHANGED)
    if raw is None:
        sys.exit(f'kan {a.scan} niet lezen')
    if raw.ndim == 2:
        raw = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGRA)
    if raw.shape[2] == 3:
        raw = np.dstack([raw, np.full(raw.shape[:2], 255, np.uint8)])
    if os.path.exists(a.discogs):                       # eigen referentiefoto(s) in plaats van Discogs
        title = os.path.basename(a.discogs); imgs = []
        for pth in [a.discogs] + (a.extra or []):
            arr = np.asarray(Image.open(pth).convert('RGB'))
            s0 = 1600 / max(arr.shape[:2])
            if s0 < 1:
                arr = cv2.resize(arr, None, fx=s0, fy=s0, interpolation=cv2.INTER_AREA)
            imgs.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    else:
        title, imgs = release_images(a.discogs)
    if not imgs:
        sys.exit('geen foto\'s gevonden bij deze Discogs-uitgave')
    s = 1000 / max(raw.shape[:2])
    small = cv2.resize(raw, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ours = on_white(small)
    found = matches(ours, imgs)
    if not found:
        sys.exit(f'geen Discogs-foto gevonden die bij de scan past ({title})')
    k, n, M = found[0]
    ang = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))     # hoek ons -> discogs (beeldcoördinaten)
    round_ = small[..., 3].mean() / 255 < 0.9                 # transparante hoeken = plaat
    print(f'Discogs: {title} — foto {n + 1} past best ({k} overeenkomsten)')

    out = raw.copy()
    # kleur: vergelijk alleen gekleurde delen van de scan met dezelfde plek op Discogs
    if not a.alleen_stand:
        best = None                                           # foto met het meeste gekleurde vlak
        for _, nn, MM in found:
            Mi = cv2.invertAffineTransform(MM)
            ref = cv2.warpAffine(imgs[nn], Mi, (ours.shape[1], ours.shape[0]), flags=cv2.INTER_AREA, borderValue=(0, 0, 0))
            cover = cv2.warpAffine(np.ones(imgs[nn].shape[:2], np.uint8), Mi, (ours.shape[1], ours.shape[0])) > 0
            b1 = cv2.GaussianBlur(ours, (0, 0), 3); b2 = cv2.GaussianBlur(ref, (0, 0), 3)
            h1, s1, v1 = hsv_f(b1); h2, s2, v2 = hsv_f(b2)
            mm = cover & (small[..., 3] > 128) & (s1 > 0.35) & (v1 > 0.25) & (s2 > 0.25)
            mm = cv2.erode(mm.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
            if best is None or mm.sum() > best[0]:
                best = (mm.sum(), nn, mm, h1, s1, v1, h2, s2, v2)
        _, nc, m, h1, s1, v1, h2, s2, v2 = best
        if m.sum() > 0.02 * m.size:
            # hoofdkleur van de scan (cirkelgemiddelde van de tint)
            hc = np.degrees(np.arctan2(np.sin(np.radians(h1[m])).mean(), np.cos(np.radians(h1[m])).mean())) % 360
            near = m & (np.abs(((h1 - hc + 180) % 360) - 180) < 25)
            dh = float(np.median(((h2[near] - h1[near] + 180) % 360) - 180))
            sr = float(np.median(s2[near] / np.maximum(s1[near], 1e-3)))
            vr = float(np.median(v2[near] / np.maximum(v1[near], 1e-3)))
            dh = float(np.clip(dh, -30, 30)); sr = float(np.clip(sr, 0.75, 1.35)); vr = float(np.clip(vr, 0.8, 1.25))
            for y0 in range(0, out.shape[0], 1024):         # in stroken: weinig geheugen bij 1200 dpi
                blk = out[y0:y0 + 1024, :, :3]
                H, S, V = hsv_f(blk)
                w = np.clip(1 - np.abs(((H - hc + 180) % 360) - 180) / 35, 0, 1) * np.clip((S - 0.2) / 0.2, 0, 1)
                H = (H + dh * w) % 360; S = np.clip(S * (1 + (sr - 1) * w), 0, 1); V = np.clip(V * (1 + (vr - 1) * w), 0, 1)
                hsv = np.dstack([H * 256 / 360, S * 255, V * 255]).clip(0, 255).astype(np.uint8)
                out[y0:y0 + 1024, :, :3] = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR_FULL)
            print(f'kleur (foto {nc + 1}): hoofdtint {hc:.0f} graden -> {dh:+.1f}, verzadiging x{sr:.2f}, helderheid x{vr:.2f}')
        else:
            print('kleur: te weinig gekleurd vlak om te vergelijken, niet aangepast')
    # stand
    if not a.alleen_kleur:
        rot = ang if round_ else 90 * round(ang / 90)
        if abs(rot) >= 0.2:
            if not round_:
                # Exact quarter turns need no interpolation, padding or lost edge pixels.
                out = np.ascontiguousarray(np.rot90(out, -int(round(rot / 90))))
            else:
                h, w = out.shape[:2]
                R = cv2.getRotationMatrix2D((w / 2, h / 2), -rot, 1.0)
                out = cv2.warpAffine(out, R, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            print(f'stand: {rot:+.1f} graden gedraaid ({"plaat, exact" if round_ else "hoes, per 90"})')
    if metadata:
        Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGRA2RGBA)).save(a.uit or a.scan, compress_level=3, **metadata)
    else:
        cv2.imwrite(a.uit or a.scan, out, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    print('klaar:', a.uit or a.scan)


if __name__ == '__main__':
    main()
