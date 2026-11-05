#!/usr/bin/env python3
"""Alle scans van één uitgave in één keer verwerken.

  python3 scan_alles.py scan1 scan2 scan3 ...   [--uit map]  [--geen-vragen]

1. groeperen: scans die overlappen zijn delen van één hoes/plaatkant
2. groepen met meerdere delen samenvoegen (scan_stitch.py, volle resolutie)
3. per resultaat: schijf (rond, gat in het midden) of hoes?
     cd/plaat -> uitknippen + tekst rechtop (scan_cutout.py cd|vinyl --auto)
     hoes     -> bijsnijden + rechtzetten (scan_cutout.py cover) + leesrichting
4. naam: één keer een Discogs-link (optioneel), dan per resultaat de kant
   kiezen (voorbeeld opent). Naam volgens het schema via scan_naam.py:
     jaar_titel_formaat_label_land[_kleur][_promo]_kant
   Zonder link: <eerste scan>_<kant>.
Uitvoer in de map 'verwerkt' naast de scans.
"""
import argparse, os, subprocess, sys, tempfile
from functools import lru_cache
import numpy as np
import cv2
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
sys.path.insert(0, HERE)
from scan_progress import progress
import scan_stitch as ST          # noqa: E402
import scan_cutout as CU          # noqa: E402

KANTEN = ['front', 'back', 'inside', 'insert', 'inlay', 'sidea', 'sideb', 'sidec', 'sided', 'cd', 'cd1', 'cd2', 'sticker']
LAST = os.path.expanduser('~/.sleeve_laatste_discogs')


def osa(script):
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def small(path, side=1400):
    with Image.open(path) as im:
        w, h = im.size
    f = min(1.0, side / max(w, h))
    return ST.load(path, f), f


@lru_cache(maxsize=256)
def disc_side(path):
    """Read an explicit side marker on the centre label, never infer from artwork."""
    import re
    im, _ = small(path, 700)
    gray = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    m = min(gray.shape)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=m*.1,
                              param1=60, param2=35, minRadius=int(m*.09), maxRadius=int(m*.27))
    if circles is None:
        return None
    exe = CU.ocr_tool()
    if not exe:
        return None
    x, y, r = circles[0][0]
    edge = cv2.dilate(cv2.Canny(gray,30,90),np.ones((5,5),np.uint8))
    angles = np.linspace(0,2*np.pi,360,endpoint=False)
    xx = np.round(x+r*np.cos(angles)).astype(int); yy = np.round(y+r*np.sin(angles)).astype(int)
    valid = (xx>=0)&(yy>=0)&(xx<gray.shape[1])&(yy<gray.shape[0])
    if valid.mean()<.9 or (edge[yy[valid],xx[valid]]>0).mean()<.65:
        return None
    with Image.open(path) as original:
        original.thumbnail((2800,2800))
        ratio = original.width / im.shape[1]
        label = original.convert('RGB').crop(tuple(int(v*ratio) for v in (x-r*1.03,y-r*1.03,x+r*1.03,y+r*1.03))).resize((1200,1200))
    angle = CU.disc_text_angle(label) or 0
    label = label.rotate(angle, resample=Image.BICUBIC, fillcolor='white')
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        label.save(f.name)
        try:
            text = subprocess.run([exe, f.name], capture_output=True, text=True, timeout=25).stdout
        except subprocess.TimeoutExpired:
            return None
    markers = {'ONE':'A', 'TWO':'B', 'THREE':'C', 'FOUR':'D', '1':'A', '2':'B', '3':'C', '4':'D'}
    found = set()
    for line in text.splitlines():
        parts = line.split('\t', 2)
        if len(parts) != 3:
            continue
        dash_mark = re.fullmatch(r'\s*[-–—]\s*([ABCD])\s*[-–—]\s*',parts[2].upper())
        if dash_mark: found.add(dash_mark.group(1))
        for mark in re.findall(r'\b(?:SIDE|KANT)\s*[:.-]?\s*(ONE|TWO|THREE|FOUR|[ABCD1234])\b', parts[2].upper()):
            found.add(markers.get(mark, mark))
    return next(iter(found)) if len(found) == 1 else None


def groups(paths):
    """Welke scans zijn delen van hetzelfde onderdeel? Twee scans horen bij
    elkaar als ze rigide op elkaar passen ÉN het gebied waar ze overeenkomen
    ook in detail gelijk is. Dat laatste scheidt bv. kant A en B van een plaat:
    hetzelfde labelontwerp (logo's passen), maar een andere tracklist.
    Samenvoegen per gemiddelde gelijkenis tussen groepen (geen ketens)."""
    sift = cv2.SIFT_create(4000)
    feats = []
    sides=[]
    progress('Etiketten en plaatkanten lezen',0,len(paths),scope='preparation')
    for index,path in enumerate(paths):
        sides.append(disc_side(path));progress('Etiketten en plaatkanten lezen',index+1,len(paths),scope='preparation')
    print("labelkanten:", [(os.path.basename(p), side) for p, side in zip(paths, sides) if side], flush=True)
    # A shorter cropped scan at the same DPI must retain the same physical scale.
    # Resizing every file to the same longest side made these scans fail rigid matching.
    headers=[]
    for path in paths:
        with Image.open(path) as image:headers.append((max(image.size),dpi_of(path)))
    calibrated=all(dpi for _,dpi in headers)
    span=max((pixels/dpi if calibrated else pixels) for pixels,dpi in headers)
    target=min(1400/span,min(dpi for _,dpi in headers)) if calibrated else 1400/span
    progress("Herkenningspunten zoeken",0,len(paths),scope="preparation")
    for index,(p,(_,dpi)) in enumerate(zip(paths,headers)):
        f=min(1.0,target/dpi if calibrated else target)
        im=ST.load(p,f)
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        # deksel/glasplaat niet meetellen: stofjes daarop staan in elke scan op dezelfde plek
        valid = (~ST.background_mask(im)).astype(np.uint8) * 255
        valid = cv2.erode(valid, np.ones((15, 15), np.uint8))
        if (valid > 0).mean() < 0.25:
            valid[15:-15, 15:-15] = 255
        kp, des = sift.detectAndCompute(g, valid)
        gf = g.astype(np.float32)
        feats.append((np.float32([k.pt for k in kp]), des, gf - cv2.GaussianBlur(gf, (0, 0), 3), valid > 0))
        progress("Herkenningspunten zoeken",index+1,len(paths),scope="preparation")
    n = len(paths); S = np.full((n, n), np.nan)
    comparisons=0;comparison_total=n*(n-1)//2
    for i in range(n):
        for j in range(i + 1, n):
            progress("Scans met elkaar vergelijken",comparisons,comparison_total,scope="preparation");comparisons+=1
            if sides[i] and sides[j] and sides[i] != sides[j]:
                S[i,j] = S[j,i] = -1.0
                continue
            pm = ST.pair_matches(feats[i][:2], feats[j][:2])
            if pm is None:
                continue
            src, dst = pm
            M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0)
            if M is None or inl.sum() < 40 or not 0.97 < np.hypot(M[0,0], M[1,0]) < 1.03:
                continue
            hi = feats[i][2]; sh = (hi.shape[1], hi.shape[0])
            hj = cv2.warpAffine(feats[j][2], M, sh)
            vj = cv2.warpAffine(feats[j][3].astype(np.uint8), M, sh) > 0
            ov = feats[i][3] & vj
            # echte overlap is groot; een gelijk logo op een klein stukje (voor- en achterkant) telt niet
            if ov.sum() < 0.15 * max(feats[i][3].sum(), feats[j][3].sum()):
                continue
            mm = ov & (cv2.blur(hi * hi, (9, 9)) > 4)
            if mm.sum() < 500:
                continue
            full = np.corrcoef(hi[mm], hj[mm])[0, 1]          # hele overlap: gelijk logo op een andere schijf/hoes valt af
            if full < 0.45:
                continue
            k = inl.ravel() > 0
            m = np.zeros(hi.shape, np.uint8)
            cv2.fillConvexPoly(m, cv2.convexHull(dst[k].astype(np.int32)), 1)
            mh = (m > 0) & vj
            if mh.sum() > 500:                               # waar ze overeenkomen (label/drukwerk): in detail gelijk?
                patches = []
                for yy in range(0, hi.shape[0]-23, 24):
                    for xx in range(0, hi.shape[1]-23, 24):
                        sl = np.s_[yy:yy+24,xx:xx+24]; v = mh[sl]
                        if v.sum() > 450 and hi[sl][v].std() > 8 and hj[sl][v].std() > 8:
                            patches.append(np.corrcoef(hi[sl][v],hj[sl][v])[0,1])
                conflict = len(patches) >= 5 and (np.asarray(patches)<.10).mean() > .20
                S[i, j] = S[j, i] = -1.0 if conflict else np.corrcoef(hi[mh], hj[mh])[0, 1]
    progress("Scans met elkaar vergelijken",comparisons,comparison_total,scope="preparation")
    cl = [[i] for i in range(n)]
    while True:
        best = None
        for x in range(len(cl)):
            for y in range(x + 1, len(cl)):
                vals = [S[i, j] for i in cl[x] for j in cl[y] if np.isfinite(S[i, j])]
                if not vals:
                    continue
                score = float(np.mean(vals)) if len(vals) * 2 >= len(cl[x]) * len(cl[y]) and min(vals) >= 0.0 else 0.0
                if score >= 0.65 and (best is None or score > best[0]):
                    best = (score, x, y)
        if best is None:
            break
        _, x, y = best
        cl[x] += cl[y]; del cl[y]
    return [[paths[i] for i in sorted(c)] for c in sorted(cl, key=min)]


def same_cover(first, second):
    """Recognise repeated complete cover scans without blending different scan sets."""
    features = []
    for path in (first,second):
        im,_ = small(path,1000)
        kp,des = cv2.SIFT_create(3000).detectAndCompute(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),None)
        features.append((np.float32([k.pt for k in kp]),des))
    pm = ST.pair_matches(*features)
    if pm is None:
        return False
    src,dst = pm
    M,inliers = cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=3)
    return M is not None and inliers.sum() >= 60 and inliers.mean() > .6 and inliers.sum() > .15*min(len(features[0][0]),len(features[1][0]))


def dpi_of(path):
    try:
        with Image.open(path) as im:
            d = im.info.get('dpi')
        return float(d[0]) if d and d[0] > 50 else None
    except Exception:
        return None


def is_disc(path):
    """Schijf? Grote cirkel met een kleine concentrische cirkel (gat/asring) in het midden.
    Geeft diameter in px (volle schaal) of None."""
    im, f = small(path, 1200)
    with Image.open(path) as raw:
        if raw.mode == 'RGBA':                         # samengevoegd: transparant = wit
            a = np.asarray(raw.convert('RGBA').resize((im.shape[1], im.shape[0])))
            bg = np.full_like(im, 255); m = a[..., 3:4] / 255.0
            im = (im * m + bg * (1 - m)).astype(np.uint8)
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    H, W = g.shape
    big = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1, minDist=10, param1=60, param2=40,
                           minRadius=int(0.3 * min(H, W)), maxRadius=int(0.55 * max(H, W)))
    if big is None:
        return None
    for cx, cy, r in big[0][:3]:
        sm = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1, minDist=5, param1=60, param2=20,
                              minRadius=int(0.02 * r), maxRadius=int(0.2 * r))
        if sm is None:
            continue
        for x, y, rr in sm[0][:10]:
            if np.hypot(x - cx, y - cy) < 0.04 * r:
                return 2 * r / f
    return None


def text_amount(path):
    """Hoeveel echte woorden staan erop (achterkant heeft meestal veel tekst)."""
    import re as _re
    with Image.open(path) as im:
        t = im.convert('RGB'); t.thumbnail((1600, 1600)); t = t.copy()
    exe = CU.ocr_tool()
    if exe is None:
        return 0
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        t.save(f.name)
        try:
            out = subprocess.run([exe, f.name], capture_output=True, text=True, timeout=90).stdout
        except subprocess.TimeoutExpired:
            return 0
    W = CU._words()
    return sum(1 for ln in out.split('\n') if ln.startswith('0\t')
               for w in _re.findall(r"[A-Za-z]{3,}", ln.split('\t', 2)[-1]) if w.lower() in W)


def upright_cover(path):
    """Hoes in hele kwartslagen rechtop zetten op de leesrichting van de tekst."""
    with Image.open(path) as im:
        t = im.convert('RGB'); t.thumbnail((1600, 1600)); t = t.copy()
    q = CU.reading_quadrant(t)
    if q:
        with Image.open(path) as im:
            im.load()
            op = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}[q]   # q = stand waarin hij leest -> terugdraaien
            im.transpose(op).save(path, compress_level=3)
        print(f'  hoes rechtop: {q} graden')
    return q


LOGFILE = None


def log(msg):
    print(msg, flush=True)
    if LOGFILE:
        with open(LOGFILE, 'a') as f:
            f.write(msg + '\n')



def run_stitch_live(cmd):
    """Forward actual stitch progress while keeping its shape report for detection."""
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    lines = []
    for line in process.stdout:
        lines.append(line)
        log(line.rstrip())
    return subprocess.CompletedProcess(cmd, process.wait(), ''.join(lines), '')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--geen-discogs-namen',action='store_true')
    p.add_argument('--een-onderdeel', action='store_true', help='alle geselecteerde scans zijn delen van één kant')
    p.add_argument('--discogs-stand', action='store_true')
    p.add_argument('--discogs-kleur', action='store_true')
    p.add_argument('scans', nargs='+'); p.add_argument('--uit'); p.add_argument('--geen-vragen', action='store_true'); p.add_argument('--discogs', default=''); p.add_argument('--variant', default='')
    a = p.parse_args()
    scans = sorted([s for s in a.scans if os.path.isfile(s)], key=lambda s: [int(t) if t.isdigit() else t.lower()
                   for t in __import__('re').split(r'(\d+)', os.path.basename(s))])
    reference_names = {}
    confirmed_groups = []
    confirmed_parts = {}
    for directory in {os.path.dirname(os.path.abspath(path)) for path in scans}:
        config = os.path.join(directory,'.anouk-referenties.json')
        if os.path.exists(config):
            import json
            data = json.load(open(config))
            reference_names[directory] = set(data.get('reference_files',[]))
            selected = {os.path.abspath(path) for path in scans}
            for group in data.get('scan_groups',[]):
                files = [os.path.join(directory,name) for name in group.get('files',[]) if os.path.basename(name)==name]
                files = [path for path in files if path in selected]
                if files:
                    confirmed_groups.append(files)
                    for path in files: confirmed_parts[path] = group.get('part','')
    reference_inputs = [path for path in scans if os.path.basename(path) in reference_names.get(os.path.dirname(os.path.abspath(path)),set())]
    scans = [path for path in scans if path not in reference_inputs]
    if reference_inputs:
        print('Alleen referentie, niet verwerkt: '+', '.join(os.path.basename(path) for path in reference_inputs),flush=True)
    if not scans:
        sys.exit('geen scans')
    out = a.uit or os.path.join(os.path.dirname(os.path.abspath(scans[0])), 'verwerkt')
    os.makedirs(out, exist_ok=True)
    global LOGFILE
    LOGFILE = os.path.join(out, 'logboek.txt')
    tmp = tempfile.mkdtemp(prefix='sleeve_alles_')
    import time; start = time.time()

    import scan_naam as scan_naam_mod
    url = a.discogs if 'discogs.com' in a.discogs else ''
    if not a.geen_vragen and not url:
        last = open(LAST).read().strip() if os.path.exists(LAST) else ''
        url = osa(f'''set r to display dialog "Discogs-link vooraf? (optioneel)" & return & return & "Plak de Discogs-link van deze uitgave; Leeg / Overslaan = verwerken zonder Discogs." default answer "{last}" buttons {{"Overslaan", "OK"}} default button "OK" with title "Sleeve · Scans verwerken"
if button returned of r is "OK" then return text returned of r''')
        if 'discogs.com' in url:
            open(LAST, 'w').write(url)
        else:
            url = ''
    use_names = bool(url) and not a.geen_discogs_namen
    if url and not a.geen_vragen:
        choices = osa('''set k to choose from list {"Bestandsnamen", "Stand / draairichting", "Kleur"} with prompt "Wat wil je van Discogs gebruiken? Kleur blijft standaard zoals gescand." default items {"Bestandsnamen"} with multiple selections allowed and empty selection allowed
if k is false then return ""
set AppleScript\'s text item delimiters to "|"
return k as text''')
        use_names = 'Bestandsnamen' in choices
        a.discogs_stand = 'Stand / draairichting' in choices
        a.discogs_kleur = 'Kleur' in choices
    variant = a.variant
    if use_names and not a.geen_vragen:
        # bestaat deze naam al in 'verwerkt' (bv. tweede promo van dezelfde single)? dan v2 voorstellen
        try:
            probe = scan_naam_mod.naam(url, 'X')[:-2]
        except BaseException:
            probe = None
        bestaat = probe and any(f.startswith(probe + '_') and not f.startswith(probe + '_v') for f in os.listdir(out)
                                if f.endswith('.png') and os.path.getmtime(os.path.join(out, f)) < start)
        voorstel = 'v2' if bestaat else ''
        variant = osa(f'''set r to display dialog "Variant (optioneel)" & return & return & "Alleen nodig als er meer uitgaven zijn die anders dezelfde naam krijgen, bv. twee promo's van dezelfde single: remixes, radio, v2 …" & return & return & "{'Let op: deze naam bestaat al in de map verwerkt.' if bestaat else 'Leeg laten = geen variant.'}" default answer "{voorstel}" buttons {{"OK"}} default button "OK" with title "Sleeve · Scans verwerken"
return text returned of r''')
    references = [];primary_positions=set()
    if url and (a.discogs_stand or a.discogs_kleur):
        progress("Discogs-referentiefoto’s ophalen",scope="preparation")
        try:
            import scan_discogs
            _, imgs, roles = scan_discogs.release_images(url, with_metadata=True)
            primary_positions={i+1 for i,role in enumerate(roles) if role=="primary"}
            for i, img in enumerate(imgs):
                path = os.path.join(tmp, f'discogs_{i}.png')
                cv2.imwrite(path,img); references.append(path)
        except (Exception, SystemExit) as e:
            log(f'Discogs-foto’s niet beschikbaar ({e}); scans verwerken zonder referentie.')

    print(f'{len(scans)} scans groeperen …', flush=True)
    if a.een_onderdeel:
        gs = [scans]
    elif confirmed_groups:
        used = {path for group in confirmed_groups for path in group}
        remainder = [path for path in scans if os.path.abspath(path) not in used]
        gs = confirmed_groups + (groups(remainder) if remainder else [])
        log('Gecontroleerde scanindeling van deze uitgave gebruikt.')
    else:
        gs = groups(scans)
    print(f'{len(gs)} onderdelen gevonden', flush=True)

    results = []                                       # (pad, soort, bron)
    detected_cover_parts={};component_records=[]
    def save_components():
        import json
        path=os.path.join(out,'Studio-onderdelen.json');temporary=path+'.tmp'
        with open(temporary,'w') as file:json.dump({'files':component_records},file,ensure_ascii=False,indent=2)
        os.replace(temporary,path)
    twijfel = set()
    for n, g in enumerate(gs, 1):
        if len(g) == 1:
            probe,_ = small(g[0],700)
            gray = cv2.cvtColor(probe,cv2.COLOR_BGR2GRAY).astype(np.float32)
            h,w = gray.shape
            gray = gray[int(.15*h):int(.85*h),int(.15*w):int(.85*w)]
            detail = gray-cv2.GaussianBlur(gray,(0,0),3)
            if (np.abs(detail)>8).mean() < .001:
                log('Overgeslagen: vrijwel lege scan zonder betrouwbare overlap: '+os.path.basename(g[0]))
                continue
        print(f'[{n}/{len(gs)}] ' + ', '.join(os.path.basename(x) for x in g), flush=True)
        progress('Deelscans voorbereiden',detail=f'{len(g)} deelscans voor dit onderdeel',completed=len(results))
        src = g[0];matched_primary=False
        dst = os.path.join(tmp, f'deel{n}.png')
        if len(g) > 1:
            src = os.path.join(tmp, f'deel{n}_samengevoegd.png')
            cmd = [PY, os.path.join(HERE,'scan_stitch.py'),src]+g
            known_part = confirmed_parts.get(os.path.abspath(g[0]),'')
            if known_part: cmd += ['--vorm','plaat' if known_part.startswith('side') else 'hoes']
            r = run_stitch_live(cmd)
            if r.returncode:
                raise RuntimeError(r.stdout + r.stderr)
            # samenvoegen herkent de vorm al; samengevoegd = altijd een lp-formaat
            soort = 'vinyl' if 'plaat:' in r.stdout else 'hoes'
        else:
            dia = is_disc(src)
            if dia is None:
                soort = 'hoes'
            else:
                d = dpi_of(src)
                mm = dia / d * 25.4 if d else None
                soort = 'vinyl' if (mm is not None and mm > 140) else 'cd'
        if a.een_onderdeel:
            fixed=confirmed_parts.get(os.path.abspath(g[0]),'')
            if fixed.startswith('side'):soort='vinyl'
            elif fixed.startswith('cd'):soort='cd'
            elif fixed:soort='hoes'
        if soort in ('cd', 'vinyl'):
            progress('Plaat of cd uitsnijden en recht draaien')
            subprocess.run([PY, os.path.join(HERE, 'scan_cutout.py'), soort, src, dst, '--auto'], check=True)
        elif len(g) > 1:
            # samengevoegde hoes is al recht en precies bijgesneden: niet nog eens snijden
            progress('Samengevoegde hoes opslaan')
            with Image.open(src) as im:
                im.save(dst, compress_level=3)
            progress('Leesrichting van de hoes controleren')
            if upright_cover(dst) is None:
                twijfel.add(dst)
        else:
            subprocess.run([PY, os.path.join(HERE, 'scan_cutout.py'), 'cover', src, dst], check=True)
            progress('Leesrichting van de hoes controleren')
            if upright_cover(dst) is None:
                twijfel.add(dst)                       # leesrichting onbekend: straks vragen
        if references and (soort == 'hoes' or (soort == 'vinyl' and a.discogs_stand)):
            cmd = [PY, os.path.join(HERE,'scan_discogs.py'), dst] + references
            if soort == 'vinyl':
                cmd.append('--alleen-stand')
            else:
                if not a.discogs_kleur: cmd.append('--alleen-stand')
                if not a.discogs_stand: cmd.append('--alleen-kleur')
            progress('Draairichting vergelijken met Discogs')
            r = subprocess.run(cmd, capture_output=True,text=True)
            log(r.stdout.strip() if r.returncode == 0 else 'Discogs-referentie past niet betrouwbaar; scan behouden.')
            import re
            match=re.search(r'foto (\d+) past best',r.stdout) if r.returncode==0 else None
            matched_primary=soort=='hoes' and match is not None and int(match[1]) in primary_positions
        # meteen veiligstellen in 'verwerkt' (voorlopige naam); hernoemen gebeurt straks
        veilig = os.path.join(out, f'{os.path.splitext(os.path.basename(g[0]))[0]}_{soort}.png'); m = 2
        while os.path.exists(veilig):
            veilig = os.path.join(out, f'{os.path.splitext(os.path.basename(g[0]))[0]}_{soort}_{m}.png'); m += 1
        __import__("shutil").move(dst, veilig)
        if dst in twijfel:
            twijfel.discard(dst); twijfel.add(veilig)
        results.append((veilig, soort, g[0]))
        if matched_primary:detected_cover_parts[veilig]='front'
        component_records.append({'name':os.path.basename(veilig),'part':confirmed_parts.get(os.path.abspath(g[0]),detected_cover_parts.get(veilig,'unknown')),'type':soort,'source':os.path.realpath(g[0]),'scans':[os.path.realpath(p) for p in g]})
        save_components()
        progress('Onderdeel verwerkt',completed=len(results))

    progress('Onderdelen herkennen voor de bestandsnamen',scope='finishing',completed=len(results))
    # namen
    import scan_naam
    # hoezen: minste tekst eerst (= voorkant), dan de rest
    hz = [r for r in results if r[1] == 'hoes']
    if len(hz) > 1 and not confirmed_groups:
        # The matching primary Discogs image identifies the front. A unique barcode
        # on another cover identifies the back; don't sort a lyric sheet into front.
        if detected_cover_parts:
            from scan_release_advice import recognize
            backs=[]
            for path,_,_ in hz:
                if path not in detected_cover_parts and recognize([{'path':path,'part':'back'}]).get('barcode'):backs.append(path)
            if len(backs)==1:detected_cover_parts[backs[0]]='back'
            hz.sort(key=lambda row:{'front':0,'back':1}.get(detected_cover_parts.get(row[0]),2))
        else:
            hz.sort(key=lambda r: text_amount(r[0]))
        results = hz + [r for r in results if r[1] != 'hoes']
    cover_reps = []
    used_cover_parts=set(detected_cover_parts.values())|{part for part in confirmed_parts.values() if part in ('front','back','inside','insert','inlay','sticker')}
    teller = {'hoes': 0, 'vinyl': 0, 'cd': 0}
    gebruikt = set()
    for result_index,(dst, soort, bron) in enumerate(results):
        progress('Definitieve bestandsnamen maken',result_index,len(results),scope='finishing',completed=len(results))
        i = teller[soort]; teller[soort] += 1
        fixed_part = confirmed_parts.get(os.path.abspath(bron),detected_cover_parts.get(dst,''))
        if fixed_part:
            kant = fixed_part
        elif soort == 'hoes':
            duplicate = next((k for path,k in cover_reps if same_cover(path,dst)),None)
            if duplicate:
                kant = duplicate
                log('Herhaalde hoes apart bewaard (scanreeksen niet gemengd): '+os.path.basename(bron))
            else:
                kant = next((part for part in ['front','back','inside','insert'] if part not in used_cover_parts),'insert')
                used_cover_parts.add(kant)
                cover_reps.append((dst,kant))
        elif soort == 'vinyl':
            label_side = disc_side(bron)
            kant = 'side'+label_side.lower() if label_side else ['sidea', 'sideb', 'sidec', 'sided'][min(i, 3)]
        else:
            kant = 'cd' if teller['cd'] == 1 else f'cd{i + 1}'
        kant = confirmed_parts.get(os.path.abspath(bron),kant)
        if not a.geen_vragen:
            ql = subprocess.Popen(['qlmanage', '-p', dst], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            lst = '{' + ', '.join(f'"{k}"' for k in KANTEN) + '}'
            k = osa(f'''set k to choose from list {lst} with prompt "Welke kant is dit? ({soort})" default items {{"{kant}"}} with title "Sleeve · Scans verwerken"
if k is false then return ""
return item 1 of k''')
            if dst in twijfel:
                d = osa('''set d to choose from list {"staat goed", "90 graden rechtsom", "90 graden linksom", "180 graden"} with prompt "Staat deze hoes rechtop?" default items {"staat goed"} with title "Sleeve · Scans verwerken"
if d is false then return ""
return item 1 of d''')
                op = {'90 graden rechtsom': Image.ROTATE_270, '90 graden linksom': Image.ROTATE_90, '180 graden': Image.ROTATE_180}.get(d)
                if op is not None:
                    with Image.open(dst) as im:
                        im.load(); im.transpose(op).save(dst, compress_level=3)
            ql.terminate()
            kant = k or kant
        if use_names:
            try:
                base = scan_naam.naam(url, kant, variant)
            except BaseException as e:                  # netwerk/Discogs-fout: naam naar de scan
                log(f'naam via Discogs mislukt ({e}); naam naar de scan')
                base = os.path.splitext(os.path.basename(bron))[0] + '_' + kant
        else:
            base = os.path.splitext(os.path.basename(bron))[0] + '_' + kant
        final = os.path.join(out, base + '.png'); m = 2
        while final in gebruikt or (os.path.exists(final) and os.path.abspath(final) != os.path.abspath(dst)):
            final = os.path.join(out, f'{base}_{m}.png'); m += 1
        gebruikt.add(final)
        __import__("shutil").move(dst, final)
        for record in component_records:
            if record['name']==os.path.basename(dst):record['name']=os.path.basename(final);record['part']=kant
        save_components()
        cover_reps = [(final if path == dst else path,k) for path,k in cover_reps]
        print(f'  -> {os.path.basename(final)}')
        progress('Definitieve bestandsnamen maken',result_index+1,len(results),scope='finishing',completed=len(results))
    __import__('shutil').rmtree(tmp, ignore_errors=True)
    print(f'klaar: {len(results)} bestanden in {out}')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        log('FOUT:\n' + traceback.format_exc())
        sys.exit(1)
