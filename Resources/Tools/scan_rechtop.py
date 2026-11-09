#!/usr/bin/env python3
"""Rechtop zetten op feiten, zonder regels.

Feiten: drukwerk (hoes, label) is gemaakt om gelezen te worden, en welke tekst
erop staat is bekend (artiest, titel, tracks, label van de release op Discogs).
Lees het onderdeel in alle vier de standen met de tekstherkenning van macOS; in de
stand waarin die bekende tekst terug te lezen is, staat het rechtop. Is er geen
duidelijke winnaar: TWIJFEL, de gebruiker beslist.
"""
import argparse, difflib, json, math, os, re, subprocess, sys, tempfile, time
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
OCR = os.path.join(HERE, 'sleeve_ocr')
CLEAR = 2.0          # de beste stand moet minstens zoveel keer meer tekst opleveren dan de op één na beste
MATCH = 0.85         # zo gelijk moet een gelezen stuk tekst aan een bekend woord zijn


def norm(t):
    return re.sub(r'[^a-z0-9]', '', t.lower())


def found(known, line):
    """Komt het bekende stuk tekst (genormaliseerd) in de gelezen regel voor?"""
    if len(known) < 3 or len(line) < len(known) - 1:
        return False
    best = max(difflib.SequenceMatcher(None, known, line[i:i + len(known)]).ratio() for i in range(0, max(1, len(line) - len(known) + 1)))
    return best >= MATCH


def read_rotations(path):
    """Per stand (graden dat het beeld met de klok mee moet): de gelezen regels."""
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im.shape[2] == 4:                                   # plaat: buiten de cirkel donker maken
        a = im[:, :, 3:4] / 255.0
        im = (im[:, :, :3] * a + 40 * (1 - a)).astype(np.uint8)
    s = 2200 / max(im.shape[:2])
    small = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else im
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'x.png'); cv2.imwrite(p, small)
        out = ''
        for attempt in range(4):                           # zie ocr_lines: Vision geeft soms niets terug
            out = subprocess.run([OCR, p], capture_output=True, text=True, timeout=120).stdout
            if out.strip():
                break
            time.sleep(0.3 * (attempt + 1))
    lines = {0: [], 90: [], 180: [], 270: []}
    for line in out.splitlines():
        try:
            deg, _, text = line.split('\t', 2)
        except ValueError:
            continue
        lines[int(deg)].append(text)
    return lines


def known_text_score(lines, words):
    """Per stand: welke bekende woorden terug te lezen zijn, en hun totale lengte."""
    score, hits = {}, {}
    for deg, texts in lines.items():
        got = [w for w in words if any(found(norm(w), norm(t)) for t in texts)]
        hits[deg] = got; score[deg] = sum(len(norm(w)) for w in got)
    return score, hits


# sleeve_ocr leest met CGImagePropertyOrientation .up/.right/.down/.left (0/90/180/270);
# '.right' betekent: het beeld moet 90 graden met de klok mee om rechtop te staan.
LABEL_MM = 105.0     # feit: een 12"-label is ±100 mm; iets ruimer zodat de rand meedoet
ROTATE = {0: None, 90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def read_image(im):
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'x.png'); cv2.imwrite(p, im)
        out = ''
        for attempt in range(4):                           # zie ocr_lines: Vision geeft soms niets terug
            out = subprocess.run([OCR, p], capture_output=True, text=True, timeout=120).stdout
            if out.strip():
                break
            time.sleep(0.3 * (attempt + 1))
    lines = {0: [], 90: [], 180: [], 270: []}
    for line in out.splitlines():
        try:
            deg, _, text = line.split('\t', 2)
        except ValueError:
            continue
        lines[int(deg)].append(text)
    return lines


def text_level(label, angle, r_px, hole_px):
    """Feit: de tekstregels op een label zijn recht en evenwijdig. Rond de grove hoek
    in stappen van 0,1 graad draaien; waar de regels het scherpst horizontaal
    liggen (rij-voor-rij het grootste verschil in drukwerk) staat het label recht."""
    g = cv2.cvtColor(label, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mag = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    ink = (mag > np.percentile(mag, 90)).astype(np.float32)
    n = label.shape[0]; c = n / 2
    keep = np.zeros_like(ink); cv2.circle(keep, (int(c), int(c)), int(r_px * .85), 1, -1)
    cv2.circle(keep, (int(c), int(c)), int(hole_px * 2), 0, -1)
    ink *= keep
    best = None
    for a in np.arange(angle - 4, angle + 4.01, 0.1):
        R = cv2.getRotationMatrix2D((c, c), -a, 1.0)
        prof = cv2.warpAffine(ink, R, (n, n)).sum(1)
        score = float(np.var(prof))
        if best is None or score > best[0]:
            best = (score, float(a))
    return best[1]


def ocr_lines(view):
    """Gelezen regels met hun kader in pixels (x0, y0, x1, y1), via sleeve_ocr --boxes."""
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'x.png'); cv2.imwrite(p, view)
        out = ''
        for attempt in range(4):                           # Vision geeft soms (vaak de eerste keer) niets terug: opnieuw
            out = subprocess.run([OCR, p, '--boxes'], capture_output=True, text=True, timeout=120).stdout
            if out.strip():
                break
            time.sleep(0.3 * (attempt + 1))
    h, w = view.shape[:2]; lines = []
    for row in out.splitlines():
        try:
            conf, text, quad = row.split('\t')
            pts = np.array([[float(v) for v in q.split(',')] for q in quad.split(';')])
        except ValueError:
            continue
        xs, ys = pts[:, 0] * w, (1 - pts[:, 1]) * h
        P = np.c_[xs, ys]                                  # tl, tr, br, bl
        direction = math.degrees(math.atan2(P[0][1] - P[1][1], P[1][0] - P[0][0]))   # leesrichting, tegen de klok in vanaf rechts
        height = (np.linalg.norm(P[0] - P[3]) + np.linalg.norm(P[1] - P[2])) / 2   # letterhoogte, ook als de regel scheef staat
        lines.append({'text': text, 'box': (xs.min(), ys.min(), xs.max(), ys.max()), 'height': height,
                      'width': (np.linalg.norm(P[0] - P[1]) + np.linalg.norm(P[3] - P[2])) / 2, 'direction': direction})
    return lines


def line_angle(view, box, around):
    """Hoek van één tekstregel: een ruim stuk rond de regel draaien in stappen van
    0,1 graad en daarna precies de regel eruit nemen (zo vallen er geen lege hoeken
    in de meting); recht is waar de boven- en onderkanten van de letters per rij het
    scherpst samenvallen."""
    x0, y0, x1, y1 = box; hgt = y1 - y0; wid = x1 - x0
    pad = int(.08 * wid + hgt)                                 # ruim genoeg voor 4 graden over de halve regel
    X0, X1 = int(max(0, x0 - pad)), int(min(view.shape[1], x1 + pad))
    Y0, Y1 = int(max(0, y0 - pad)), int(min(view.shape[0], y1 + pad))
    g = cv2.cvtColor(view[Y0:Y1, X0:X1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1))
    c = ((x0 + x1) / 2 - X0, (y0 + y1) / 2 - Y0)
    bx0, bx1 = int(x0 - X0), int(x1 - X0); by0, by1 = int(y0 - X0 * 0 - Y0 - .4 * hgt), int(y1 - Y0 + .4 * hgt)
    best = None
    for a in np.arange(around - 4, around + 4.01, 0.1):
        R = cv2.getRotationMatrix2D(c, a, 1.0)
        band = cv2.warpAffine(gy, R, (g.shape[1], g.shape[0]))[max(0, by0):by1, max(0, bx0):bx1]
        sc = float(np.var(band.sum(1)))
        if best is None or sc > best[0]:
            best = (sc, float(a))
    return best[1]


def label_lines(view, words):
    """Regels op het label; vindt Vision geen tracklist, dan nog eens op dubbele grootte
    lezen (kleine of omcirkelde cijfers) en de kaders terugschalen."""
    lines = ocr_lines(view)
    if sum(any(found(norm(w), norm(l['text'])) for w in words[2:]) for l in lines) >= 1:
        return lines
    big = cv2.resize(view, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    more = ocr_lines(big)
    for l in more:
        l['box'] = tuple(v / 2 for v in l['box']); l['height'] /= 2; l['width'] /= 2
    return more if len(more) > len(lines) else lines


def level_label(label, coarse, words):
    """Feit: de tracklist op een label staat recht. Draai het label naar de grove
    stand en zet de regels van de tracklist (bekend van Discogs) precies horizontaal.
    Is er geen tracklist te lezen, dan de grootste tekst (artiest of titel).
    Meten, bijdraaien en opnieuw meten tot de regels recht liggen (de grove stand
    kan tot ±7,5 graad naast zitten)."""
    n = label.shape[0]; c = (n / 2, n / 2); angle = coarse; how = 'none'
    for _ in range(4):
        R = cv2.getRotationMatrix2D(c, -angle, 1.0)
        view = cv2.warpAffine(label, R, (n, n), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
        lines = [l for l in label_lines(view, words) if len(re.findall(r'\w', l['text'])) >= 3]
        titles = [l for l in lines if any(found(norm(w), norm(l['text'])) for w in words[:2])]
        tracks = [l for l in lines if any(found(norm(w), norm(l['text'])) for w in words[2:])]
        # Feit (André, 8 nov): de tracklist staat op een label (bijna) altijd recht.
        # Die is leidend; alleen als er geen tracklist te lezen is, de grootste tekst
        # (artiest of titel).
        # een tracktitel die ook de albumtitel is (bv. 'Set This Thing On Fire') telt niet als tracklistregel
        tracks = [l for l in tracks if l not in titles or len(tracks) == 1 and not titles]
        if tracks:
            off = float(np.median([line_angle(view, l['box'], 0.0) for l in tracks]))
            how = 'tracklist (%d lines)' % len(tracks)
        elif titles:
            big = max(titles, key=lambda l: l['height'])
            off, how = line_angle(view, big['box'], 0.0), 'largest text: ' + big['text']
        else:
            break
        angle = (angle - off) % 360
        if abs(off) < 0.15:
            break
    return angle, how


def disc_angle(path, words, px_mm):
    """Plaat: alleen het label lezen (midden, volle resolutie), in stappen rondgedraaid.
    De hoek waarin de bekende tekst het best terug te lezen is, is rechtop.
    Geeft (hoek met de klok mee, score per geteste hoek, gelezen woorden)."""
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)[:, :, :3]
    h, w = im.shape[:2]; r = int(LABEL_MM / 2 * px_mm)
    label = im[h // 2 - r:h // 2 + r, w // 2 - r:w // 2 + r].copy()
    mask = np.zeros(label.shape[:2], np.uint8); cv2.circle(mask, (r, r), r, 255, -1)
    label[mask == 0] = 255
    small = cv2.resize(label, (1240, 1240), interpolation=cv2.INTER_AREA) if label.shape[0] > 1300 else label
    # Vision leest tekst in elke stand en geeft de leesrichting per regel: de tracklist
    # (of anders artiest/titel) zegt dan meteen hoe het label gedraaid ligt.
    lines = label_lines(small, words)
    tracks = [l for l in lines if any(found(norm(w), norm(l['text'])) for w in words[2:])]
    heads = [l for l in lines if any(found(norm(w), norm(l['text'])) for w in words[:2])]
    use = tracks if len(tracks) >= 2 else []          # alleen de tracklist geeft hier meteen de stand; anders rondgedraaid zoeken
    if use:
        dirs = np.array([l['direction'] for l in use])
        ref = dirs[0]; spread = np.abs(((dirs - ref + 180) % 360) - 180)
        if np.median(spread) < 10:
            est = (float(np.median(((dirs - ref + 180) % 360) - 180)) + ref) % 360   # zoveel met de klok mee draaien
            fine, how = level_label(small, est, words)
            got = [w for w in words if any(found(norm(w), norm(l['text'])) for l in lines)]
            # Alleen artiest/titel gelezen, geen tracklist: een titel kan schuin ontworpen zijn
            # (Set This Thing On Fire, kant B). Dan niet vertrouwen maar twijfelen.
            note = [] if use is tracks and how.startswith('tracklist') else ['title only']
            return fine, {round(est, 1): len(use)}, got + ['direction from %d lines' % len(use), 'level: ' + how] + note
    tried = {}
    def score_at(base):
        R = cv2.getRotationMatrix2D((r, r), -base, 1.0)              # met de klok mee draaien
        view = cv2.warpAffine(label, R, (2 * r, 2 * r), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
        sc, hits = known_text_score(read_image(view), words)
        for q, v in sc.items():
            tried[(base + q) % 360] = (v, hits[q])
    for base in range(0, 90, 15):
        score_at(base)
    coarse = max(tried, key=lambda k: tried[k][0])
    for base in np.arange(coarse - 6, coarse + 6.1, 3):
        score_at(float(base) % 90)
    best = max(tried, key=lambda k: (tried[k][0], -abs(((k - coarse + 180) % 360) - 180)))
    fine, how = level_label(small, best, words)          # fijne hoek op ±300 dpi: Vision leest de regels daar het best
    print('label level:', how, f'({fine:.1f} degrees)', file=sys.stderr)
    return fine, {round(k, 1): v[0] for k, v in sorted(tried.items())}, tried[best][1] + ['level: ' + how]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('image'); p.add_argument('--out')
    p.add_argument('--words', required=True, help='JSON list with the known text of the release (Discogs)')
    p.add_argument('--disc', action='store_true', help='record side: read the label, any angle')
    p.add_argument('--dpi', type=float, default=300.0)
    a = p.parse_args()
    words = json.load(open(a.words))
    if a.disc:
        best, per_angle, got = disc_angle(a.image, words, a.dpi / 25.4)
        top = sorted(per_angle.values(), reverse=True)
        # tweede kandidaat: de beste score minstens 30 graden verderop
        far = [v for k, v in per_angle.items() if abs(((k - best + 180) % 360) - 180) >= 30]
        verdict = 'GOED' if top[0] > 0 and top[0] >= CLEAR * max(max(far, default=0), 1) else 'TWIJFEL'
        if 'title only' in got:
            verdict = 'TWIJFEL'                        # label alleen op de titel rechtgezet: jij kijkt
        result = {'rotate_clockwise': round(best, 1), 'known_text_best': top[0], 'next_best_elsewhere': max(far, default=0), 'read_upright': got, 'verdict': verdict}
        print(json.dumps(result, ensure_ascii=False))
        if a.out:
            im = cv2.imread(a.image, cv2.IMREAD_UNCHANGED); hh, ww = im.shape[:2]
            R = cv2.getRotationMatrix2D((ww / 2, hh / 2), -best, 1.0)
            cv2.imwrite(a.out, cv2.warpAffine(im, R, (ww, hh), flags=cv2.INTER_CUBIC, borderValue=(0, 0, 0, 0)))
        return
    # Hoes: Vision leest tekst in elke stand en geeft de leesrichting per regel. Bekende
    # tekst van de release (feit) in een duidelijke richting = zo moet de hoes draaien
    # (een hoes staat altijd op een kwartslag).
    im0 = cv2.imread(a.image, cv2.IMREAD_UNCHANGED)[:, :, :3]
    k0 = 1600 / max(im0.shape[:2])
    view0 = cv2.resize(im0, None, fx=k0, fy=k0, interpolation=cv2.INTER_AREA) if k0 < 1 else im0
    known = [l for l in ocr_lines(view0) if any(found(norm(w), norm(l['text'])) for w in words)]
    votes = {}
    for l in known:
        q = int(round(l['direction'] / 90.0)) % 4 * 90               # leesrichting op een kwartslag
        votes[q] = votes.get(q, 0) + len(norm(l['text']))
    if votes:
        ranked = sorted(votes, key=votes.get, reverse=True)
        best = ranked[0]; second = votes[ranked[1]] if len(ranked) > 1 else 0
        verdict = 'GOED' if votes[best] >= CLEAR * max(second, 1) else 'TWIJFEL'
        result = {'rotate_clockwise': best, 'known_text_per_rotation': votes, 'read_upright': [l['text'] for l in known][:12] + ['direction from Vision'], 'verdict': verdict}
    else:
        score, hits = known_text_score(read_rotations(a.image), words)
        ranked = sorted(score, key=score.get, reverse=True)
        best, second = ranked[0], ranked[1]
        verdict = 'GOED' if score[best] > 0 and score[best] >= CLEAR * max(score[second], 1) else 'TWIJFEL'
        result = {'rotate_clockwise': best, 'known_text_per_rotation': score, 'read_upright': hits[best], 'verdict': verdict}
    print(json.dumps(result, ensure_ascii=False))
    if a.out:
        im = cv2.imread(a.image, cv2.IMREAD_UNCHANGED)
        if ROTATE[best] is not None:
            im = cv2.rotate(im, ROTATE[best])
        cv2.imwrite(a.out, im)


if __name__ == '__main__':
    main()
