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
import argparse, os, subprocess, sys, tempfile, contextlib
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
from scan_memory import MemoryLease,physical_memory,GiB

MERGE_SCORE = 0.65        # gemiddelde gelijkenis waarboven twee groepen scans samengaan
MERGE_WEAKEST = 0.50      # ...of: alle paren passen, geen onder deze waarde
MERGE_STRONGEST = 0.70    #    en minstens één paar boven deze waarde
MIN_INLIERS = 40          # passende punten voor een paar deelscans
MIN_INLIERS_QUARTER = 25  # ... als ze precies een kwartslag (of recht) t.o.v. elkaar liggen
KANTEN = ['front', 'back', 'inside', 'insert', 'insert_left', 'insert_right', 'inlay', 'sidea', 'sideb', 'sidec', 'sided', 'cd', 'cd1', 'cd2', 'sticker']
LAST = os.path.expanduser('~/.sleeve_laatste_discogs')


def osa(script):
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def small(path, side=1400):
    with Image.open(path) as im:
        w, h = im.size
    f = min(1.0, side / max(w, h))
    return ST.load(path, f), f


_disc_side_results = {}

def disc_side(path, preview=None, original=None):
    """Read a side marker; a supplied preview avoids decoding the source twice."""
    stat=os.stat(path);key=(os.path.abspath(path),stat.st_size,stat.st_mtime_ns)
    if key in _disc_side_results:return _disc_side_results[key]
    if preview is None:preview,_=small(path,700)
    result=disc_side_from_preview(path,preview,original)
    if len(_disc_side_results)>=256:_disc_side_results.pop(next(iter(_disc_side_results)))
    _disc_side_results[key]=result
    return result

def label_circle(im):
    """Het middenlabel van een plaat op een voorbeeld: (x, y, r) of None."""
    gray = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    m = min(gray.shape)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=m*.1,
                              param1=60, param2=35, minRadius=int(m*.09), maxRadius=int(m*.27))
    if circles is None:
        return None
    x, y, r = circles[0][0]
    # Red vinyl and a dark label can have the same luminance. Keep chromatic
    # boundaries when checking that the candidate is a real circular label.
    channel_edges=[cv2.Canny(cv2.GaussianBlur(channel,(3,3),0),30,90) for channel in cv2.split(im)]
    edge = cv2.dilate(np.maximum.reduce(channel_edges+[cv2.Canny(gray,30,90)]),np.ones((5,5),np.uint8))
    angles = np.linspace(0,2*np.pi,360,endpoint=False)
    xx = np.round(x+r*np.cos(angles)).astype(int); yy = np.round(y+r*np.sin(angles)).astype(int)
    valid = (xx>=0)&(yy>=0)&(xx<gray.shape[1])&(yy<gray.shape[0])
    if valid.mean()<.9 or (edge[yy[valid],xx[valid]]>0).mean()<.65:
        return None
    return float(x), float(y), float(r)


def disc_side_from_preview(path, im, original=None):
    """Read an explicit side marker on the centre label, never infer from artwork."""
    import re
    circle = label_circle(im)
    if circle is None:
        return None
    exe = CU.ocr_tool()
    if not exe:
        return None
    x, y, r = circle
    with (Image.open(path) if original is None else contextlib.nullcontext(original)) as original:
        original.thumbnail((2800,2800))
        ratio = original.width / im.shape[1]
        label = original.convert('RGB').crop(tuple(int(v*ratio) for v in (x-r*1.03,y-r*1.03,x+r*1.03,y+r*1.03))).resize((1200,1200))
    angle = CU.disc_text_angle(label) or 0
    label = label.rotate(angle, resample=Image.BICUBIC, fillcolor='white')
    def recognize(candidate):
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            candidate.save(f.name)
            try:
                text = subprocess.run([exe, f.name], capture_output=True, text=True, timeout=25).stdout
            except subprocess.TimeoutExpired:
                return set()
        return side_markers(text)
    found=recognize(label)
    if not found:
        # A high-contrast retry helps white side letters on dark, low-contrast
        # labels. Keep fast OCR and require the same explicit side syntax.
        from PIL import ImageOps
        contrast=ImageOps.autocontrast(label.convert('L'),cutoff=2)
        found=recognize(contrast.point(lambda value:255 if value>140 else 0))
    for extra in (15,-15,30,-30):
        # Tekstherkenning leest alleen in kwartslagen; een label dat daar schuin
        # tussen ligt (TGHT: grote schuine titel misleidt de hoekmeting) mist "SIDE A".
        if found:
            break
        found=recognize(label.rotate(extra, resample=Image.BICUBIC, fillcolor='white'))
    if not found:
        found=lone_side_letter(label,exe)
    return next(iter(found)) if len(found) == 1 else None


def lone_side_letter(label, exe):
    """Een label met alleen een losse letter als kant (A, B, C, D), zoals Deena &
    Jim. Tekstherkenning zoekt woorden en slaat zo'n letter over. Zoek daarom
    geïsoleerde tekens van letterformaat, zet ze rechtop volgens de leesrichting
    van de rest van het label, vergroot ze en lees alleen die stand."""
    q = CU.reading_quadrant(label)                     # None: leesrichting onbekend, alle standen
    upright = label.transpose({90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}[q]) if q else label
    rgb = np.asarray(upright.convert('RGB'))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    n = gray.shape[0]
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 51, 15)
    yy, xx = np.ogrid[:n, :n]
    d = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
    ink[(d > .85) | (d < .15)] = 0                    # randtekst en asgat niet
    count, _, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    letters = set()
    for c in range(1, count):
        x, y, w, h, area = stats[c]
        if not (.04 * n < h < .14 * n and .02 * n < w < .14 * n and area > .15 * w * h):
            continue
        x0, y0, x1, y1 = max(0, x - h), max(0, y - h), min(n, x + w + h), min(n, y + 2 * h)
        if (ink[y0:y1, x0:x1] > 0).sum() - area > .25 * area:
            continue                                   # niet los: hoort bij een woord
        pad = int(.6 * h)
        glyph = Image.fromarray(rgb[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad])
        glyph = glyph.resize((max(1, round(glyph.width * 240 / glyph.height)), 240), Image.LANCZOS)
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            glyph.save(f.name)
            try:
                text = subprocess.run([exe, f.name], capture_output=True, text=True, timeout=25).stdout
            except subprocess.TimeoutExpired:
                continue
        for line in text.splitlines():
            parts = line.split('\t', 2)
            if len(parts) != 3 or (q is not None and parts[0] != '0'):
                continue
            mark = parts[2].strip()
            # alleen hoofdletters (een omgekeerde 'a' is geen A); C ook als 'c'
            if mark in ('A', 'B', 'C', 'D', 'c'):
                letters.add(mark.upper())
    return letters


def side_markers(text):
    import re
    markers = {'ONE':'A', 'TWO':'B', 'THREE':'C', 'FOUR':'D', '1':'A', '2':'B', '3':'C', '4':'D'}
    found = set()
    for line in text.splitlines():
        parts = line.split('\t', 2)
        if len(parts) != 3:
            continue
        dash_mark = re.fullmatch(r'\s*[-–—]\s*([ABCD])\s*[-–—]\s*',parts[2].upper())
        if dash_mark: found.add(dash_mark.group(1))
        # ook gangbare leesfouten van SIDE: "SDEA", "S1DE A", "SlDE B"
        for mark in re.findall(r'\b(?:S[I1L|]?DE|KANT)\s*[:.-]?\s*(ONE|TWO|THREE|FOUR|[ABCD1234])\b', parts[2].upper()):
            found.add(markers.get(mark, mark))
    return found


MAX_STRETCH = 0.015       # groeperen: hoogstens 1,5% verschil in rek tussen x en y


QUARTER_TOL = 2.0         # graden: zo dicht bij een kwartslag telt als 'gedraaid tussen deelscans'


def quarter_turn(M):
    angle = np.degrees(np.arctan2(M[1, 0], M[0, 0]))
    return abs(((angle + 45) % 90) - 45) < QUARTER_TOL


def stretch_fit(src, dst, inliers, M):
    """Scannerrek meenemen bij het vergelijken. Een flatbed rekt de ene as iets
    meer dan de andere (y/x ~0,9975); na een kwartslag draait die rek mee, en
    lopen twee deelscans over de breedte een paar pixels uit elkaar. Bij fijne
    tekst (tekstvellen) zakte de gelijkenis daardoor onder de grens. Alleen op
    de punten die al rigide pasten; geen afschuiving, nauwelijks rek."""
    k = inliers.ravel() > 0
    F, _ = cv2.estimateAffine2D(src[k], dst[k], method=cv2.LMEDS)
    if F is None:
        return M
    sx, sy = np.hypot(F[0, 0], F[1, 0]), np.hypot(F[0, 1], F[1, 1])
    shear = abs(F[0, 0] * F[0, 1] + F[1, 0] * F[1, 1]) / (sx * sy)
    if abs(sx / sy - 1) < MAX_STRETCH and shear < MAX_STRETCH and 0.97 < sx < 1.03:
        return F
    return M


def groups(paths):
    with tempfile.TemporaryFile(prefix='sleeve-group-previews-') as scratch:
        return group_with_previews(paths,scratch)


def group_with_previews(paths,scratch):
    """Welke scans zijn delen van hetzelfde onderdeel? Twee scans horen bij
    elkaar als ze rigide op elkaar passen ÉN het gebied waar ze overeenkomen
    ook in detail gelijk is. Dat laatste scheidt bv. kant A en B van een plaat:
    hetzelfde labelontwerp (logo's passen), maar een andere tracklist.
    Samenvoegen per gemiddelde gelijkenis tussen groepen (geen ketens)."""
    sift = cv2.SIFT_create(4000)
    feats = []
    sides=[];preview_offsets=[]
    # A shorter cropped scan at the same DPI must retain the same physical scale.
    # Resizing every file to the same longest side made these scans fail rigid matching.
    headers=[];decode_sizes=[]
    for path in paths:
        with Image.open(path) as image:
            headers.append((max(image.size),dpi_of(path)))
            decode_sizes.append(image.width*image.height*9)

    calibrated=all(dpi for _,dpi in headers)
    span=max((pixels/dpi if calibrated else pixels) for pixels,dpi in headers)
    target=min(1400/span,min(dpi for _,dpi in headers)) if calibrated else 1400/span
    progress('Scans openen en plaatkanten lezen',0,len(paths),scope='preparation')
    cache_dpi=max(dpi for _,dpi in headers) if calibrated else None
    cache_f=min(1.0,ST.MAX_SIDE/(span*cache_dpi if calibrated else span))
    import threading
    stopped=threading.Event();preview_write_lock=threading.Lock()
    def inspect_source(item):
        if stopped.is_set():return None,None
        path,(longest,dpi)=item
        f=min(1.0,target/dpi if calibrated else target)
        scale=cache_f*(cache_dpi/dpi) if calibrated else cache_f
        factors=[min(1.0,700/longest),f]
        if os.environ.get('SLEEVE_WORK_PREVIEWS'):factors.append(scale)
        previews,side=ST.load_previews(path,factors,inspector=lambda images,original:disc_side(path,images[0],original))
        if len(previews)>2:
            from scan_previews import put
            with preview_write_lock:
                if stopped.is_set():return None,None
                put(path,scale,previews[2])
        return previews[1],side
    # At most two source decoders, bounded using source dimensions rather than
    # file sizes. Preserve input order and do all scratch-file writes in one thread.
    workers=2 if physical_memory()>=8*GiB and sum(sorted(decode_sizes,reverse=True)[:2])+.5*GiB<4*GiB else 1
    workers=min(workers,max(1,int(os.environ.get('SLEEVE_PREVIEW_WORKERS','2'))))
    from concurrent.futures import ThreadPoolExecutor
    if workers>1:CU.ocr_tool()  # Compile once before any inspector thread can need it.
    executor=ThreadPoolExecutor(max_workers=workers)
    try:
        for index,(preview,side) in enumerate(executor.map(inspect_source,zip(paths,headers))):
            preview_offsets.append(scratch.tell())
            np.save(scratch,preview,allow_pickle=False)
            sides.append(side)
            progress('Scans openen en plaatkanten lezen',index+1,len(paths),scope='preparation')
    except BaseException:
        # Cancel queued decoders immediately. In-flight decoders may finish, but
        # cannot recreate a cache directory after the job's ExitStack removes it.
        with preview_write_lock:stopped.set()
        executor.shutdown(wait=False,cancel_futures=True)
        raise
    else:executor.shutdown(wait=True)
    label=preview=None
    print("labelkanten:", [(os.path.basename(p), side) for p, side in zip(paths, sides) if side], flush=True)
    progress("Herkenningspunten zoeken",0,len(paths),scope="preparation")
    for index,(p,(_,dpi)) in enumerate(zip(paths,headers)):
        f=min(1.0,target/dpi if calibrated else target)
        scratch.seek(preview_offsets[index])
        im=np.load(scratch,allow_pickle=False)
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
    n = len(paths); S = np.full((n, n), np.nan); Q = np.zeros((n, n), bool)
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
            # Minder punten mag bij een exacte kwartslag (zo worden delen gescand): een
            # toevallige valse match valt vrijwel nooit precies zo (DEENA binnenkant 41-42: 36).
            needed = MIN_INLIERS_QUARTER if M is not None and quarter_turn(M) else MIN_INLIERS
            if M is None or inl.sum() < needed or not 0.97 < np.hypot(M[0,0], M[1,0]) < 1.03:
                continue
            if quarter_turn(M):
                # Alleen bij een kwartslag (zo worden grote vellen in delen gescand).
                # Kant A en B van een plaat liggen in een willekeurige hoek: die
                # blijven zoals voorheen (hetzelfde labelontwerp scoort hoog).
                M = stretch_fit(src, dst, inl, M)
                Q[i, j] = Q[j, i] = True
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
    return cluster_paths(paths,S,sides,Q)


def cluster_paths(paths,S,sides=None,quarter=None):
    n=len(paths)
    cl = [[i] for i in range(n)]
    # Scans met dezelfde gelezen kantletter beginnen samen (als ze op elkaar
    # passen), zodat een scan zonder leesbare letter daarna bij de juiste kant
    # komt in plaats van bij de eerste de beste gelijkende scan.
    for letter in sorted({side for side in (sides or []) if side}):
        members=[i for i in range(n) if sides[i]==letter]
        if len(members)<2 or any(S[i,j]<0 for i in members for j in members if i<j and np.isfinite(S[i,j])):
            continue
        # alleen scans die via overlap met elkaar verbonden zijn (zelfde letter
        # kan ook in drukwerk staan, bv. een tracklijst op de achterkant)
        parts=[[members[0]]];rest=members[1:]
        while rest:
            linked=[j for j in rest if any(np.isfinite(S[i,j]) and S[i,j]>=MERGE_SCORE for i in parts[-1])]
            if linked:
                parts[-1]+=linked;rest=[j for j in rest if j not in linked]
            else:
                parts.append([rest.pop(0)])
        for part in parts:
            seed=[c for c in cl if c[0] in part]
            for c in seed[1:]:
                seed[0]+=c;cl.remove(c)
    while True:
        best = None
        for x in range(len(cl)):
            for y in range(x + 1, len(cl)):
                vals = [S[i, j] for i in cl[x] for j in cl[y] if np.isfinite(S[i, j])]
                if not vals:
                    continue
                score = float(np.mean(vals)) if len(vals) * 2 >= len(cl[x]) * len(cl[y]) and min(vals) >= 0.0 else 0.0
                # Vier kwartslag-delen van één vel: buren overlappen ruim, de
                # diagonale paren alleen in een smalle middenstrook (lager). Passen
                # álle paren en is er minstens één sterke, dan toch samen.
                # Alleen als alle paren een kwartslag verschillen: kant A en B van
                # een plaat scoren ook zo (Graduated Fool: 0,58-0,77), maar liggen
                # in een willekeurige hoek.
                linked = [(i, j) for i in cl[x] for j in cl[y] if np.isfinite(S[i, j])]
                if quarter is not None and all(quarter[i, j] for i, j in linked) and min(vals) >= MERGE_WEAKEST:
                    strong = sum(v >= MERGE_STRONGEST for v in vals)
                    # Alle paren passen (vier delen van één vel), of: een breed vel
                    # (uitgeklapte binnenkant) waarvan de uiteinden elkaar niet raken,
                    # maar dat op minstens twee plekken sterk overlapt.
                    if (len(vals) == len(cl[x]) * len(cl[y]) and strong >= 1) or strong >= 2:
                        score = max(score, MERGE_SCORE)
                if score >= MERGE_SCORE and (best is None or score > best[0]):
                    best = (score, x, y)
        if best is None:
            break
        _, x, y = best
        cl[x] += cl[y]; del cl[y]
    # A cropped corner can overlap just one member of a large, already
    # verified group. Attach only an unambiguous strong match, preserving every
    # explicit conflict veto and never linking two multi-scan groups.
    for singleton in [group for group in cl if len(group)==1]:
        i=singleton[0];candidates=[]
        for target in cl:
            if target is singleton or len(target)<2:continue
            values=[S[i,j] for j in target if np.isfinite(S[i,j])]
            if values and min(values)>=.65 and max(values)>=.80:candidates.append(target)
        if len(candidates)==1:
            candidates[0].append(i);cl.remove(singleton)
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


SPREAD_RANGE = (1.85, 2.15)   # lange/korte zijde van een uitgeklapte binnenkant


def split_spreads(results,detected_cover_parts,twijfel,component_records):
    """Uitgeklapte binnenkant (twee panelen, 2:1) als twee vierkanten opslaan,
    precies op de vouw gesplitst, zonder tussenstuk: insert_left en
    insert_right (André). Staat de stand niet vast, dan beide ter controle."""
    out=[]
    for path,soort,bron in results:
        if soort!='hoes':
            out.append((path,soort,bron));continue
        with Image.open(path) as im:
            w,h=im.size
            if not SPREAD_RANGE[0]<=max(w,h)/min(w,h)<=SPREAD_RANGE[1]:
                out.append((path,soort,bron));continue
            im.load()
            half=max(w,h)//2
            boxes=[(0,0,half,h),(w-half,0,w,h)] if w>h else [(0,0,w,half),(0,h-half,w,h)]
            panels=[im.crop(box) for box in boxes]
        stem,ext=os.path.splitext(path)
        names=[stem+'_links'+ext,stem+'_rechts'+ext]
        for panel,name in zip(panels,names):
            panel.save(name,compress_level=1)
        record=next((r for r in component_records if r['name']==os.path.basename(path)),None)
        part=detected_cover_parts.pop(path,None)
        doubt=path in twijfel;twijfel.discard(path)
        os.remove(path)
        for name,side in zip(names,('insert_left','insert_right')):
            detected_cover_parts[name]=side
            if doubt or w<h:twijfel.add(name)          # staand: links/rechts nog niet zeker
            out.append((name,soort,bron))
            if record is not None:
                copy=dict(record,name=os.path.basename(name),part=detected_cover_parts[name],needs_review=name in twijfel)
                component_records.append(copy)
        if record is not None:component_records.remove(record)
        log(f'Uitgeklapte binnenkant ({w}x{h}) in twee vierkanten gesplitst: '+', '.join(os.path.basename(n) for n in names))
    return out


def mark_repeated_fronts(results,detected_cover_parts,twijfel,component_records):
    """Meer dan één hoes past op de Discogs-voorkant. De grootste is de hoes;
    een duidelijk kleiner exemplaar (bv. de buitenkant van een binnenhoes) wordt
    'insert'. Beide gevallen altijd ter controle voorleggen, nooit stil '_2'."""
    fronts=[(path,bron) for path,soort,bron in results if soort=='hoes' and detected_cover_parts.get(path)=='front']
    if len(fronts)<2:
        return
    sizes={}
    for path,bron in fronts:
        with Image.open(path) as im:
            longest=max(im.size)
        sizes[path]=longest/(dpi_of(bron) or 300.0)*25.4      # mm; zelfde scanner = zelfde dpi
    keep=max(sizes,key=sizes.get)
    for path,_ in fronts:
        if path==keep:
            continue
        if sizes[path]<0.985*sizes[keep]:
            detected_cover_parts[path]='insert'
            log(f'Kleinere voorkant ({sizes[path]:.0f} mm tegen {sizes[keep]:.0f} mm), als insert benoemd; controleer: {os.path.basename(path)}')
        else:
            log('Voorkant twee keer gescand; beide bewaard, controleer: '+os.path.basename(path))
        twijfel.add(path)
        for record in component_records:
            if record['name']==os.path.basename(path):
                record['needs_review']=True


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


def save_merged_cover(source,destination):
    """The stitch worker already finalized these pixels; both paths are in its private temp folder."""
    os.replace(source,destination)


def upright_cover(path):
    with MemoryLease(26,phase='Leesrichting van de hoes controleren'):return upright_cover_with_memory(path)


def upright_cover_with_memory(path):
    """Hoes in hele kwartslagen rechtop zetten op de leesrichting van de tekst."""
    with Image.open(path) as im:
        t = im.convert('RGB'); t.thumbnail((1600, 1600)); t = t.copy()
    q = CU.reading_quadrant(t)
    if q:
        with Image.open(path) as im:
            im.load()
            op = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}[q]   # q = stand waarin hij leest -> terugdraaien
            im.transpose(op).save(path, compress_level=1)
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
    import signal
    previous={sig:signal.getsignal(sig) for sig in (signal.SIGTERM,signal.SIGINT)}
    def stop(signum,frame):raise SystemExit(128+signum)
    try:
        for sig in previous:signal.signal(sig,stop)
        with contextlib.ExitStack() as resources:return main_with_resources(resources)
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)


def main_with_resources(resources):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--geen-discogs-namen',action='store_true')
    p.add_argument('--een-onderdeel', action='store_true', help='alle geselecteerde scans zijn delen van één kant')
    p.add_argument('--discogs-stand', action='store_true')
    p.add_argument('--discogs-kleur', action='store_true')
    p.add_argument('scans', nargs='+'); p.add_argument('--uit'); p.add_argument('--geen-vragen', action='store_true'); p.add_argument('--discogs', default=''); p.add_argument('--variant', default='')
    p.add_argument('--workers',type=int,choices=[1,2,3],default=3,help=argparse.SUPPRESS)
    p.add_argument('--component-worker',help=argparse.SUPPRESS)
    a = p.parse_args()
    worker_context=None
    if a.component_worker:
        import json
        if not a.geen_vragen or not a.een_onderdeel:raise ValueError('Invalid component worker request')
        worker_context=json.load(open(a.component_worker))
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
    tmp=resources.enter_context(tempfile.TemporaryDirectory(prefix='sleeve_alles_',dir=os.path.dirname(a.component_worker) if a.component_worker else None))
    if worker_context is None:
        import shutil
        if shutil.disk_usage(tmp).free>3*GiB:
            os.environ['SLEEVE_WORK_PREVIEWS']=os.path.join(tmp,'work-previews')
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
    if worker_context is not None:
        references=worker_context['references'];primary_positions=set(worker_context['primary_positions'])
    elif url and (a.discogs_stand or a.discogs_kleur):
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
    parallel=bool(a.geen_vragen and not worker_context and a.workers>1 and len(gs)>1 and len({os.path.basename(path) for path in scans})==len(scans))
    if parallel:
        import json,shutil
        from pathlib import Path
        from scan_workers import ComponentPool
        commands=[];job_folders={}
        for n,g in enumerate(gs,1):
            folder=Path(tmp)/('worker-'+str(n));folder.mkdir();stage=folder/'scans';stage.mkdir();destination=folder/'outputs'
            for source in g:os.symlink(os.path.realpath(source),stage/os.path.basename(source))
            known=confirmed_parts.get(os.path.abspath(g[0]),'')
            profile={'scan_groups':[{'part':known,'files':[os.path.basename(p) for p in g]}]} if known else {}
            (stage/'.anouk-referenties.json').write_text(json.dumps(profile))
            context=folder/'context.json';context.write_text(json.dumps({'references':references,'primary_positions':list(primary_positions)}))
            command=[PY,__file__,*[str(stage/os.path.basename(p)) for p in g],'--geen-vragen','--een-onderdeel','--geen-discogs-namen','--workers','1','--component-worker',str(context),'--uit',str(destination)]
            if url:command+=['--discogs',url]
            if a.discogs_stand:command+=['--discogs-stand']
            if a.discogs_kleur:command+=['--discogs-kleur']
            commands.append((n,command));job_folders[n]=destination
        commands.sort(key=lambda item:len(gs[item[0]-1]),reverse=True)
        completed={}
        with ComponentPool(len(gs),Path(tmp)/'pool',a.workers) as pool:
            for n in pool.run(commands):
                destination=job_folders[n]
                record=json.loads((destination/'Worker-resultaat.json').read_text())
                if record['files']:
                    if len(record['files'])!=1:raise ValueError('Een onderdeel leverde niet precies één resultaat op')
                    item=record['files'][0];source=(destination/item['name']).resolve()
                    if source.parent!=destination.resolve() or source.suffix.lower()!='.png':raise ValueError('Invalid component output')
                    soort=item['type'];bron=gs[n-1][0]
                    veilig=os.path.join(out,f'{os.path.splitext(os.path.basename(bron))[0]}_{soort}.png');suffix=2
                    while os.path.exists(veilig):veilig=os.path.join(out,f'{os.path.splitext(os.path.basename(bron))[0]}_{soort}_{suffix}.png');suffix+=1
                    shutil.move(source,veilig)
                    completed[n]=(veilig,soort,bron)
                    item['name']=os.path.basename(veilig);item['scans']=[os.path.realpath(p) for p in gs[n-1]]
                    component_records.append(item);save_components()
                    if item.get('matched_primary'):detected_cover_parts[veilig]='front'
                    if item.get('needs_review'):twijfel.add(veilig)
                pool.finished(n)
        results=[completed[n] for n in sorted(completed)]
    for n, g in enumerate([] if parallel else gs, 1):
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
        src = g[0];matched_primary=False;quality=[];label_check=''
        dst = os.path.join(tmp, f'deel{n}.png')
        if len(g) > 1:
            src = os.path.join(tmp, f'deel{n}_samengevoegd.png')
            cmd = [PY, os.path.join(HERE,'scan_stitch.py'),src]+g+['--rechtop','--snelle-tussenbestanden']
            known_part = confirmed_parts.get(os.path.abspath(g[0]),'')
            if known_part: cmd += ['--vorm','plaat' if known_part.startswith('side') else 'hoes']
            r = run_stitch_live(cmd)
            if r.returncode:
                raise RuntimeError(r.stdout + r.stderr)
            for line in r.stdout.splitlines():
                if line.startswith('SLEEVE_INTERMEDIATE '):
                    import json
                    candidate=json.loads(line[len('SLEEVE_INTERMEDIATE '):])['path']
                    if os.path.abspath(candidate)!=os.path.abspath(src+'.tif'):
                        raise ValueError('Invalid intermediate output')
                    src=candidate
                if line.startswith('SLEEVE_QUALITY '):
                    import json
                    quality=ST.quality_messages(json.loads(line[len('SLEEVE_QUALITY '):]))
            if 'plaat:' in r.stdout:
                # Op platen verstoren groeven en de draaiing tussen deelscans de
                # naadmeting (vals alarm); het label komt meestal uit één scan.
                quality=[]
            # samenvoegen herkent de vorm al; samengevoegd = altijd een lp-formaat
            soort = 'vinyl' if 'plaat:' in r.stdout else 'hoes'
        else:
            fixed=confirmed_parts.get(os.path.abspath(g[0]),'') if a.een_onderdeel else ''
            if fixed:
                soort='vinyl' if fixed.startswith('side') else 'cd' if fixed.startswith('cd') else 'hoes'
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
            save_merged_cover(src,dst)
            progress('Leesrichting van de hoes controleren')
            if 'leesrichting: onbekend' in r.stdout:
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
            match=re.search(r'SLEEVE_REFERENCE_IDENTITY (\d+)',r.stdout) if r.returncode==0 else None
            matched_primary=soort=='hoes' and match is not None and int(match[1]) in primary_positions
            if soort=='hoes' and match is not None and '--alleen-kleur' not in cmd:
                # Zeker passende Discogs-foto heeft de stand gezet: de leesrichting
                # is dan bekend, ook als er geen leesbare tekst op de hoes staat.
                twijfel.discard(dst)
            if soort=='vinyl' and r.returncode==0 and 'past best' in r.stdout:label_check='discogs'
        if soort=='vinyl' and label_check!='discogs':
            # Zonder passende Discogs-foto van het vinyl is de stand alleen op de
            # labeltekst bepaald; bij schuin ontworpen labels kan die ernaast zitten.
            quality.append('Labelstand alleen op de labeltekst bepaald (geen passende Discogs-foto van het vinyl). Controleer of het label recht staat.')
        # meteen veiligstellen in 'verwerkt' (voorlopige naam); hernoemen gebeurt straks
        veilig = os.path.join(out, f'{os.path.splitext(os.path.basename(g[0]))[0]}_{soort}.png'); m = 2
        while os.path.exists(veilig):
            veilig = os.path.join(out, f'{os.path.splitext(os.path.basename(g[0]))[0]}_{soort}_{m}.png'); m += 1
        __import__("shutil").move(dst, veilig)
        if dst in twijfel:
            twijfel.discard(dst); twijfel.add(veilig)
        results.append((veilig, soort, g[0]))
        if matched_primary:detected_cover_parts[veilig]='front'
        component_records.append({'name':os.path.basename(veilig),'part':confirmed_parts.get(os.path.abspath(g[0]),detected_cover_parts.get(veilig,'unknown')),'type':soort,'matched_primary':matched_primary,'needs_review':veilig in twijfel,'source':os.path.realpath(g[0]),'scans':[os.path.realpath(p) for p in g],'quality':quality})
        save_components()
        progress('Onderdeel verwerkt',completed=len(results))

    if worker_context is not None:
        import json,shutil
        with open(os.path.join(out,'Worker-resultaat.json'),'w') as file:json.dump({'files':component_records},file)
        shutil.rmtree(tmp,ignore_errors=True)
        return

    progress('Onderdelen herkennen voor de bestandsnamen',scope='finishing',completed=len(results))
    results=split_spreads(results,detected_cover_parts,twijfel,component_records)
    mark_repeated_fronts(results,detected_cover_parts,twijfel,component_records)
    save_components()
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
    used_cover_parts=set(detected_cover_parts.values())|{part for part in confirmed_parts.values() if part in ('front','back','inside','insert','insert_left','insert_right','inlay','sticker')}
    if used_cover_parts&{'insert_left','insert_right'}:
        used_cover_parts.add('inside')    # de uitgeklapte binnenkant ís de binnenzijde; losse vellen blijven insert
    teller = {'hoes': 0, 'vinyl': 0, 'cd': 0}
    gebruikt = set()
    for result_index,(dst, soort, bron) in enumerate(results):
        progress('Definitieve bestandsnamen maken',result_index,len(results),scope='finishing',completed=len(results))
        i = teller[soort]; teller[soort] += 1
        fixed_part = confirmed_parts.get(os.path.abspath(bron),detected_cover_parts.get(dst,''))
        if fixed_part:
            kant = fixed_part
            if soort=='hoes':cover_reps.append((dst,kant))
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
                        im.load(); im.transpose(op).save(dst, compress_level=1)
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
