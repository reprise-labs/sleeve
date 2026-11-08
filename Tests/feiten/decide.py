"""Jouw beslissingen toepassen op een onderdeel dat TWIJFEL gaf (uit beslissingen.json).
Gebruik: decide.py square <raw.png> <crop.png> <words.json> <out.png>   (vierkant: zwakste zijde schuift in)
         decide.py rotate <crop.png> <graden met de klok mee> <out.png>"""
import sys, json, subprocess, cv2, numpy as np
P = sys.executable; T = '/Users/andrevanos/Documents/Codex/2026-11-04/referenced-chatgpt-conversation-this-is-an/outputs/Sleeve/Resources/Tools'
if sys.argv[1] == 'square':
    raw, crop, words, out = sys.argv[2:6]
    d = json.loads(subprocess.run([P, f'{T}/scan_feiten.py', raw, 'insert'], capture_output=True, text=True).stdout)
    weak = min(d['sides'], key=lambda k: d['sides'][k]['cover'])
    c = cv2.imread(crop); h, w = c.shape[:2]; k = abs(h - w)
    sl = {'top': (slice(k, None), slice(None)), 'bottom': (slice(0, h - k), slice(None)),
          'left': (slice(None), slice(k, None)), 'right': (slice(None), slice(0, w - k))}[weak]
    if (weak in ('top', 'bottom')) != (h > w):
        print('weakest side', weak, 'is not on the long axis; not applied'); sys.exit(1)
    sq = c[sl]; cv2.imwrite(crop.replace('.png', '_sq.png'), sq)
    print('decision square: weakest side', weak, f'(edge seen {d["sides"][weak]["cover"]:.0%}) moved in', round(k / (d.get("dpi", 300) / 25.4), 1), 'px->mm approx;', sq.shape[1], 'x', sq.shape[0], 'px')
    print(subprocess.run([P, f'{T}/scan_rechtop.py', crop.replace('.png', '_sq.png'), '--words', words, '--out', out], capture_output=True, text=True).stdout.strip()[:120])
else:
    crop, deg, out = sys.argv[2], int(sys.argv[3]), sys.argv[4]
    im = cv2.imread(crop, cv2.IMREAD_UNCHANGED)
    rot = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[deg]
    cv2.imwrite(out, cv2.rotate(im, rot)); print('decision rotate', deg)
subprocess.run(['open', out])
