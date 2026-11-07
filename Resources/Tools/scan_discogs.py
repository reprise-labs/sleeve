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
MAX_PHOTO_SKEW = 6.0   # graden: kleinere afwijking van een Discogs-foto is scheef gefotografeerd


def get(url):
    """Ophalen; lukt dat niet met Python (bv. geen certificaten op deze Mac), dan met curl."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read()
    except Exception as error:
        if getattr(getattr(error,'reason',error),'errno',None) in (13,51,64,65):
            raise RuntimeError('No connection to Discogs. Check the internet connection and Sleeve’s network access; you can also use your own reference photo.') from error
        import subprocess
        r = subprocess.run(['curl', '-fsSL', '-A', UA, '--connect-timeout', '8', '--max-time', '20', url], capture_output=True)
        if r.returncode:
            raise RuntimeError(f'fetch failed: {url}')
        return r.stdout


def release_images(url, with_metadata=False):
    m = re.search(r'/release/(\d+)', url)
    if not m:
        mm = re.search(r'/master/(\d+)', url)
        if not mm:
            sys.exit('no Discogs release found in the link')
        master = json.loads(get(f'https://api.discogs.com/masters/{mm.group(1)}'))
        rid = master['main_release']
    else:
        rid = m.group(1)
    rel = json.loads(get(f'https://api.discogs.com/releases/{rid}'))
    out = []; roles=[]
    for im in rel.get('images', []):
        try:
            data = get(im['uri'])
            arr = np.asarray(Image.open(io.BytesIO(data)).convert('RGB'))
            out.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR));roles.append(im.get("type","secondary"))
        except Exception:
            pass
    if with_metadata:return rel.get('title',''),out,roles
    return rel.get('title', ''), out


def on_white(rgba):
    bgr = rgba[..., :3].astype(np.float32); a = rgba[..., 3:4].astype(np.float32) / 255
    return (bgr * a + 255 * (1 - a)).astype(np.uint8)


def matches(ours, imgs, with_coverage=False):
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
            selected=inl.ravel()>0
            coverage=min(cv2.contourArea(cv2.convexHull(points[selected]))/(image.shape[0]*image.shape[1]) for points,image in [(src,ours),(dst,im)])
            found.append((k,n,M,coverage) if with_coverage else (k,n,M))
    return sorted(found, key=lambda x: -x[0])


def hsv_f(bgr):
    h = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    return h[..., 0] * 360 / 256, h[..., 1] / 255, h[..., 2] / 255


def main():
    return main_with_memory()


def main_with_memory():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('scan'); p.add_argument('discogs', help='Discogs link or your own reference photo')
    p.add_argument('extra', nargs='*', help='more reference photos of your own')
    p.add_argument('--uit'); p.add_argument('--alleen-stand', action='store_true'); p.add_argument('--alleen-kleur', action='store_true')
    a = p.parse_args()
    with Image.open(a.scan) as original:
        source_mode=original.mode
        metadata = {key:original.info[key] for key in ('dpi','icc_profile') if key in original.info}
    from scan_memory import MemoryLease
    with MemoryLease(39 if metadata else 27,phase='Comparing rotation with Discogs'):
        return apply_reference(a,source_mode,metadata)


def apply_reference(a,source_mode,metadata):
    raw = cv2.imread(a.scan, cv2.IMREAD_UNCHANGED)
    if raw is None:
        sys.exit(f'can’t read {a.scan}')
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
        sys.exit('no photos found for this Discogs release')
    s = 1000 / max(raw.shape[:2])
    small = cv2.resize(raw, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ours = on_white(small)
    detailed = matches(ours, imgs,with_coverage=True)
    found=[item[:3] for item in detailed]
    if not found:
        sys.exit(f'no Discogs photo found that matches the scan ({title})')
    k, n, M = found[0]
    ang = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))     # hoek ons -> discogs (beeldcoördinaten)
    round_ = small[..., 3].mean() / 255 < 0.9                 # transparante hoeken = plaat
    print(f'Discogs: {title} — photo {n + 1} fits best ({k} matches)')
    if detailed[0][3]>=.20:print(f'SLEEVE_REFERENCE_IDENTITY {n+1}')

    out = raw
    del raw
    changed=False
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
            changed=True
            # hoofdkleur van de scan (cirkelgemiddelde van de tint)
            hc = np.degrees(np.arctan2(np.sin(np.radians(h1[m])).mean(), np.cos(np.radians(h1[m])).mean())) % 360
            near = m & (np.abs(((h1 - hc + 180) % 360) - 180) < 25)
            dh = float(np.median(((h2[near] - h1[near] + 180) % 360) - 180))
            sr = float(np.median(s2[near] / np.maximum(s1[near], 1e-3)))
            vr = float(np.median(v2[near] / np.maximum(v1[near], 1e-3)))
            dh = float(np.clip(dh, -30, 30)); sr = float(np.clip(sr, 0.75, 1.35)); vr = float(np.clip(vr, 0.8, 1.25))
            for y0 in range(0, out.shape[0], 256):         # in stroken: weinig geheugen bij 1200 dpi
                blk = out[y0:y0 + 256, :, :3]
                H, S, V = hsv_f(blk)
                w = np.clip(1 - np.abs(((H - hc + 180) % 360) - 180) / 35, 0, 1) * np.clip((S - 0.2) / 0.2, 0, 1)
                H = (H + dh * w) % 360; S = np.clip(S * (1 + (sr - 1) * w), 0, 1); V = np.clip(V * (1 + (vr - 1) * w), 0, 1)
                hsv = np.dstack([H * 256 / 360, S * 255, V * 255]).clip(0, 255).astype(np.uint8)
                out[y0:y0 + 256, :, :3] = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR_FULL)
            print(f'color (photo {nc + 1}): main hue {hc:.0f} degrees -> {dh:+.1f}, saturation x{sr:.2f}, brightness x{vr:.2f}')
        else:
            print('color: too little colored area to compare, not adjusted')
    # stand
    if not a.alleen_kleur:
        # Plaat: het label is al op zijn eigen tekst rechtgezet. Een Discogs-foto
        # staat zelf vaak een paar graden scheef (Urban Solitude: -1,9 tot +3,5),
        # dan alleen de kwartslag overnemen. Wijkt de foto veel af, dan was de
        # labeltekst bewust schuin ontworpen (FIRE: +35 graden): volg dan de foto.
        rot = 90 * round(ang / 90)
        if round_ and abs(ang - rot) > MAX_PHOTO_SKEW:
            rot = ang
        if abs(rot) >= 0.2:
            changed=True
            if rot % 90 == 0 and (not round_ or out.shape[0] == out.shape[1]):
                # Exact quarter turns need no interpolation, padding or lost edge pixels.
                out = np.ascontiguousarray(np.rot90(out, -int(round(rot / 90))))
            else:
                h, w = out.shape[:2]
                turn = -rot
                if round_:
                    # De Discogs-foto staat zelf vaak iets scheef (Hotel New York kant A:
                    # 1,5 graden). Na het volgen van de foto de rechte tekstregels op het
                    # label nameten en dat restje alsnog rechtzetten (één keer draaien).
                    from scan_cutout import text_line_angle, TEXT_LINE_MIN
                    trial = cv2.warpAffine(out, cv2.getRotationMatrix2D((w / 2, h / 2), turn, 1.0), (w, h), flags=cv2.INTER_LINEAR)
                    s = min(h, w); lb = int(s * .18)
                    label = Image.fromarray(np.ascontiguousarray(trial[h // 2 - lb:h // 2 + lb, w // 2 - lb:w // 2 + lb, :3][..., ::-1]))
                    rest = text_line_angle(label)
                    if rest is not None and abs(rest) >= TEXT_LINE_MIN:
                        turn += rest
                        print(f'text lines re-measured after the Discogs photo: another {rest:+.1f} degrees adjusted')
                R = cv2.getRotationMatrix2D((w / 2, h / 2), turn, 1.0)
                out = cv2.warpAffine(out, R, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            how='exactly as the Discogs photo' if rot % 90 else 'per quarter turn'
            print(f'orientation: rotated {rot:+.1f} degrees ({"record" if round_ else "cover"}, {how}; Discogs photo was {ang:+.1f})')
    destination=a.uit or a.scan
    if not changed and source_mode=='RGBA' and os.path.splitext(destination)[1].lower()==os.path.splitext(a.scan)[1].lower():
        if os.path.abspath(destination)!=os.path.abspath(a.scan):
            import shutil
            shutil.copy2(a.scan,destination)
        print('image unchanged; saving again skipped')
        print('done:',destination)
        return
    if metadata:
        Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGRA2RGBA)).save(a.uit or a.scan, compress_level=1, **metadata)
    else:
        cv2.imwrite(a.uit or a.scan, out, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    print('done:', a.uit or a.scan)


if __name__ == '__main__':
    main()
