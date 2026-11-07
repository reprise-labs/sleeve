#!/usr/bin/env python3
"""Meerdere flatbed-deelscans van één hoes of plaat samenvoegen tot één beeld.

Gemaakt voor lp-hoezen en platen die niet in één keer op de scanner passen.
Anders dan een gewone panorama-merge:
  - alleen verschuiving + draaiing (een flatbed vervormt niet), dus geen
    "uitgerekte" of kromme stukken
  - het witte scannerdeksel rond de hoes telt niet mee en wordt nooit over de
    hoes heen geplakt
  - kleur/grijs gelijktrekken: elk stuk krijgt per kleurkanaal een zacht
    verlopende correctie (vaste zweem + lichtverloop van de lamp), gemeten in
    de overlap; ook voor de lastige grijstinten
  - naden zacht laten overlopen

Gebruik:
  python3 scan_stitch.py uit.png deel1.jpg deel2.jpg deel3.jpg ...
      [--geen-kleur]   kleuren niet gelijktrekken
      [--vorm hoes|plaat] standaard bepaalt hij dat zelf
      [--referentie N] stuk N (1 = eerste) is de kleurreferentie (standaard:
                       het stuk met de meeste overlap)
  De oriëntatie van het resultaat is die van het eerste deel.

Uitvoer: png met transparantie waar geen scan was. Daarna eventueel
scan_cutout.py (cover/vinyl) en de watermerkstap.
"""
import argparse, os, sys, gc, contextlib
from scan_progress import progress
from scan_blend import detail_blur
from scan_fields import GainPlane, CorrectedImage
from scan_memory import MappedScanStore,MappedArrayStore,render_tile_size,drop_array_pages,flush_array_rows,MemoryLease
import numpy as np
import cv2

MAX_SIDE = 3600        # rekenschaal: langste zijde voor uitlijnen/kleur/vorm (uitvoer is volle resolutie)
TILE = 2048           # blokgrootte voor het opbouwen op volle resolutie (geheugen)
MATCH_SIZE = 3000      # langste zijde voor het zoeken naar overeenkomsten (hoog = nauwkeurig)
DETAIL_SIGMA = 6       # px: fijner dan dit = detail (uit één scan), grover = kleur/licht (overvloeien)
FEATHER = 700          # px: zo ver van de scanrand weegt een pixel pas volledig mee
                       # (randen van de glasplaat zijn donkerder: lamp + schaduw)
EDGE = 150             # px van de rand die niet meetelt bij het kleurmeten
SEAM_CORRIDOR = 40     # px (rekenschaal): zo ver mag een naad van de scherpste-scan-grens afwijken
SEAM_SIDE = 1200       # px: rekenschaal voor het kiezen van de naden
WINNER_SMOOTH = 8     # px (rekenschaal): keuzekaart per deelscan samenhangend maken
TONE_SIGMA = 30        # px (rekenschaal): alleen deze heel grove toon wordt tussen deelscans gemengd;
                       # alles fijner (ook letters) komt uit de gekozen deelscan
MAX_SLOPE = 0.06      # lichtverloop per deelscan: max ~6% over de hele breedte/hoogte
MAX_CAST = 0.04        # vaste kleurzweem per kanaal: max ~4%


def open_srgb(path, factor=1.0):
    """Open with the established resize/profile path, avoiding RGB copies."""
    import io
    from PIL import Image,ImageCms
    Image.MAX_IMAGE_PIXELS=None
    image=Image.open(path)
    profile=image.info.get('icc_profile')
    if image.mode not in ('RGB','RGBA','L'):image=image.convert('RGB')
    if factor != 1:
        image=image.resize((max(1,round(image.width*factor)),max(1,round(image.height*factor))),Image.LANCZOS)
    if image.mode != 'RGB':image=image.convert('RGB')
    if profile:
        source=ImageCms.ImageCmsProfile(io.BytesIO(profile))
        if 'srgb' not in ImageCms.getProfileDescription(source).lower():
            ImageCms.profileToProfile(image,source,ImageCms.createProfile('sRGB'),outputMode='RGB',inPlace=True)
    return image


def load_into(path,target):
    """Decode/profile once; copy RGB to mapped BGR in bounded row bands."""
    with open_srgb(path) as image:
        if target.shape != (image.height,image.width,3):raise ValueError('Decoder target dimensions changed')
        for start in range(0,image.height,256):
            stop=min(image.height,start+256)
            with image.crop((0,start,image.width,stop)) as band:
                target[start:stop]=cv2.cvtColor(np.asarray(band),cv2.COLOR_RGB2BGR)
            flush_array_rows(target,start,stop)


def load(path,f=1.0,consume_cache=False):
    """Read BGR in sRGB, optionally resized; no source file is modified."""
    try:
        from scan_previews import get
        cached=get(path,f,consume=consume_cache)
        if cached is not None:return cached
        with open_srgb(path,f) as image:
            return cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
    except Exception as error:
        sys.exit(f'kan {path} niet lezen: {error}')


def load_previews(path, factors, inspector=None):
    """Decode once, then create independent previews with the existing pixel path."""
    import io
    from PIL import Image, ImageCms
    Image.MAX_IMAGE_PIXELS = None
    outputs=[]
    with Image.open(path) as original:
        icc=original.info.get('icc_profile')
        image=original if original.mode in ('RGB','RGBA','L') else original.convert('RGB')
        profile=ImageCms.ImageCmsProfile(io.BytesIO(icc)) if icc else None
        convert=profile is not None and 'srgb' not in ImageCms.getProfileDescription(profile).lower()
        for factor in factors:
            preview=image
            if factor != 1:
                preview=image.resize((max(1,round(image.width*factor)),max(1,round(image.height*factor))),Image.LANCZOS)
            preview=preview.convert('RGB')
            if convert:
                preview=ImageCms.profileToProfile(preview,profile,ImageCms.createProfile('sRGB'),outputMode='RGB')
            outputs.append(cv2.cvtColor(np.asarray(preview),cv2.COLOR_RGB2BGR))
        if inspector is not None:return outputs,inspector(outputs,original)
    return outputs


def lid_colour(edge):
    """Kleur van het deksel uit de randpixels + hoeveel donkerder het mag zijn.

    De rand is vaak grotendeels hoes, dus niet de mediaan: groepeer de
    randkleuren en neem de meest neutrale groep (deksel is wit/grijs); is een
    grijze hoes even neutraal, dan de lichtste. Ligt er zo'n even neutrale
    grijze hoes naast, dan mag 'deksel' maar half zo donker worden als het
    verschil, anders loopt het de hoes in."""
    px = edge.reshape(-1, 3).astype(np.float32)
    groups = []
    for k in (2, 3):
        _, lab_, cen = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS)
        for c in range(k):
            if (lab_.ravel() == c).mean() >= 0.08:
                L, a, b = cen[c]
                groups.append((int(np.hypot(a - 128, b - 128) / 5), -L, np.median(px[lab_.ravel() == c], axis=0)))
    if not groups:
        return np.median(px, axis=0), 45.0
    groups.sort(key=lambda g: (g[0], g[1]))
    ch, negL, lid = groups[0]
    darker = [-g[1] for g in groups if g[0] <= ch and -g[1] < -negL - 8]
    down = 45.0 if not darker else float(np.clip(0.5 * (-negL - max(darker)), 8, 45))
    return lid, down


def background_mask(im):
    """True = scannerachtergrond: vlakken in de kleur van het deksel, egaal, die
    aan de rand vastzitten. Kleur (Lab) en niet helderheid, want een lichte hoes
    is even licht als het deksel; randen (schaduwlijn langs de hoes) houden het
    tegen zodat het niet de hoes in loopt."""
    small = cv2.resize(im, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    edge = np.concatenate([lab[2], lab[-3], lab[:, 2], lab[:, -3]])
    lid, down = lid_colour(edge)                           # kleur van het deksel
    dC = np.sqrt(((lab[..., 1:] - lid[1:]) ** 2).sum(axis=2))    # kleurzweem
    dL = np.where(lab[..., 0] < lid[0], (lid[0] - lab[..., 0]) * 45.0 / down,   # donkerder: beperkt
                  lab[..., 0] - lid[0])                                     # lichter mag
    gf = g.astype(np.float32)
    var = cv2.blur(gf * gf, (9, 9)) - cv2.blur(gf, (9, 9)) ** 2
    barrier = cv2.dilate(cv2.Canny(cv2.GaussianBlur(g, (5, 5), 0), 15, 40), np.ones((3, 3), np.uint8)) > 0
    cand = ((dC < 6) & (dL < 45) & (var < 80) & ~barrier).astype(np.uint8)
    n, lab_ = cv2.connectedComponents(cand)
    border = set(np.unique(np.concatenate([lab_[0], lab_[-1], lab_[:, 0], lab_[:, -1]]))) - {0}
    bg = np.isin(lab_, list(border))
    bg = cv2.dilate(bg.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    # alleen grote vlakken zijn hoes/plaat (stofjes op het deksel niet)
    n, lv, st, _ = cv2.connectedComponentsWithStats((~bg).astype(np.uint8))
    keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] > 0.03 * bg.size
    bg = ~keep[lv]
    bg = cv2.resize(bg.astype(np.uint8), (im.shape[1], im.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    m = 6                                                # scannerrand zelf ook weg
    bg[:m] = bg[-m:] = True; bg[:, :m] = bg[:, -m:] = True
    return bg


def features(im, valid):
    s = MATCH_SIZE / max(im.shape[:2])
    small = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    vm = cv2.resize(valid.astype(np.uint8) * 255, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
    sift = cv2.SIFT_create(nfeatures=12000)
    kp, des = sift.detectAndCompute(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), vm)
    pts = np.float32([k.pt for k in kp]) / s
    return pts, des


def pair_matches(fa, fb):
    """Overeenkomende punten (src in b, dst in a) of None."""
    pa, da = fa; pb, db = fb
    if da is None or db is None or len(da) < 10 or len(db) < 10:
        return None
    m = cv2.BFMatcher(cv2.NORM_L2).knnMatch(db, da, k=2)
    good = [x[0] for x in m if len(x) == 2 and x[0].distance < 0.72 * x[1].distance]
    if len(good) < 15:
        return None
    return pb[[g.queryIdx for g in good]], pa[[g.trainIdx for g in good]]


def rigid_fit(src, dst):
    """Rigide transformatie (draaiing + verschuiving) die src op dst legt: (M, inliers, rms)."""
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0, maxIters=5000, confidence=0.999)
    if M is None:
        return None, 0, 1e9
    sc = np.hypot(M[0, 0], M[1, 0])
    if not 0.97 < sc < 1.03:          # flatbed: schaal hoort 1 te zijn
        return None, 0, 1e9
    # Uniform scaling supports scans exported at slightly different sizes.
    # No shear or perspective: a circle remains a circle.
    k = inl.ravel() > 0
    M[:,2] = np.mean(dst[k] - src[k] @ M[:,:2].T, axis=0)
    r = np.sqrt((((src[k] @ M[:, :2].T) + M[:, 2] - dst[k]) ** 2).sum(1).mean())
    return np.vstack([M, [0, 0, 1]]), int(k.sum()), r


def scanner_stretch(pairs):
    """Een flatbed rekt de ene richting net iets anders dan de andere (~0,1-0,5%).
    Liggen stukken 90 graden gedraaid, dan past alleen schuiven/draaien niet meer
    precies (letters verspringen). Zoek de verhouding y/x die alle paren het
    best laat passen; dezelfde scanner, dus één waarde voor alle scans."""
    def score(sy):
        D = np.array([1.0, sy], np.float32); tot = []
        for src, dst in pairs.values():
            M, k, r = rigid_fit(src * D, dst * D)
            if M is not None and k >= 15:
                tot.append(r)
        return np.mean(tot) if tot else 1e9
    grid = np.arange(0.994, 1.0061, 0.001)
    best = min(grid, key=score)
    fine = np.arange(best - 0.001, best + 0.00101, 0.00025)
    best = min(fine, key=score)
    return float(best), score(1.0), score(best)


def place(n, feats):
    """Paarsgewijs uitlijnen en via een opspannende boom (meeste inliers) plaatsen."""
    pairs = {}
    for i in range(n):
        for j in range(n):
            if i != j:
                pm = pair_matches(feats[i], feats[j])  # j op i
                if pm is not None:
                    pairs[(i, j)] = pm
    sy, r0, r1 = scanner_stretch(pairs)
    D = np.array([1.0, sy], np.float32)
    T = {}; W = np.zeros((n, n), int)
    for (i, j), (src, dst) in pairs.items():
        M, k, _ = rigid_fit(src * D, dst * D)
        if M is not None:
            T[(i, j)] = M; W[i, j] = k
    ref = int(np.argmax(W.sum(axis=1)))
    H = {ref: np.eye(3)}; frontier = [ref]
    while frontier:
        best = None
        for i in H:
            for j in range(n):
                if j not in H and W[i, j] > 0 and (best is None or W[i, j] > best[2]):
                    best = (i, j, W[i, j])
        if best is None:
            break
        i, j, _ = best
        H[j] = H[i] @ T[(i, j)]; frontier.append(j)
    Ds = np.diag([1.0, sy, 1.0])                       # eerst de scannerrek eruit
    H = {k: v @ Ds for k, v in H.items()}
    if abs(sy - 1) >= 0.0005:
        print(f'scannerrek gecorrigeerd: y/x = {sy:.4f} (passing {r0:.2f} -> {r1:.2f} px)')
    missing = [k for k in range(n) if k not in H]
    return H, ref, W, missing


def seam_regions(img, masks, ks, height, width):
    """Per plek één deelscan, met naden waar de scans het meest op elkaar lijken
    (wit papier, tussen regels) in plaats van dwars door tekst. Graph cut op
    ~SEAM_SIDE px. Geeft per pixel het scannummer (255 = geen keuze) of None."""
    f = min(1.0, SEAM_SIDE / max(height, width))
    w, h = max(1, round(width * f)), max(1, round(height * f))
    try:
        images, small = [], []
        for k in ks:
            images.append(cv2.UMat(cv2.resize(img[k][0:height], (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)))
            small.append(cv2.UMat(cv2.resize(masks[k].astype(np.uint8) * 255, (w, h), interpolation=cv2.INTER_NEAREST)))
        found = cv2.detail_GraphCutSeamFinder('COST_COLOR_GRAD').find(images, [(0, 0)] * len(ks), small)
    except cv2.error as error:
        print(f'naden: graph cut niet gelukt ({error.code}); samenhangende keuze gebruikt', flush=True)
        return None
    choice = np.full((h, w), 255, np.uint8)
    for n, m in enumerate(found):
        m = m.get() if hasattr(m, 'get') else np.asarray(m)
        choice[(m > 0) & (choice == 255)] = n
    choice = cv2.resize(choice, (width, height), interpolation=cv2.INTER_NEAREST)
    for n, k in enumerate(ks):
        choice[(choice == n) & ~masks[k]] = 255              # nooit buiten de eigen scan
    return choice


def feather_weight(mask):
    """Gewicht dat vanaf de rand van het geldige deel zacht oploopt."""
    d = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    return (np.minimum(d, FEATHER) / FEATHER) ** 2 + (mask * 1e-4)


def gain_correct(im, mask, comp, cmask, step=16, allocator=None, release=None, fit_only=False):
    """Pas im aan zodat het in de overlap gelijk is aan comp.

    Per kanaal een vlak a + b*x + c*y in log(comp/im), robuust geschat op
    rustige (geen randen), niet-overbelichte pixels. Een vlak kan nooit vlekken
    of blokken maken; het vangt een vaste kleurzweem plus het lichtverloop.
    """
    h, w = mask.shape
    sm = lambda x: cv2.resize(x, (w // step, h // step), interpolation=cv2.INTER_AREA)
    ov = ((mask & cmask) & (cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5) > EDGE)
          & (cv2.distanceTransform(cmask.astype(np.uint8), cv2.DIST_L2, 5) > EDGE)).astype(np.uint8)
    if im.dtype == np.uint8:
        kernel=cv2.getGaussianKernel(25,3,cv2.CV_32F)
        A=sm(cv2.sepFilter2D(im,cv2.CV_32F,kernel,kernel))
    else:
        A = sm(cv2.GaussianBlur(im, (0, 0), 3))
    if release:release()
    B = sm(cv2.GaussianBlur(comp, (0, 0), 3))
    if release:release()
    ovs = sm(ov.astype(np.float32)) > 0.99
    g = cv2.cvtColor(np.clip(A, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    grad = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    ok = ovs & (A.min(axis=2) > 8) & (A.max(axis=2) < 247) & (B.min(axis=2) > 8) & (B.max(axis=2) < 247)
    if ok.sum() > 200:
        ok &= grad < np.percentile(grad[ok], 60)       # alleen egale stukken (geen naadfouten)
    if ok.sum() < 100:
        return None if fit_only else (im, None)
    yy, xx = np.nonzero(ok)
    X = np.stack([np.ones_like(xx), xx / (w / step), yy / (h / step)], 1).astype(np.float64)
    fx=np.arange(w,dtype=np.float32)[None,:]
    # Eén gedeeld lichtverloop voor alle kanalen, per kanaal alleen een vaste
    # zweem. Het vlak wordt in de (smalle) overlap gemeten maar over de hele
    # scan doorgetrokken: losse hellingen per kanaal gaven daar rode/grijze
    # gloed op wit papier. De helling is begrensd, gemeten rond de overlap.
    r = np.log(B[ok] / A[ok])
    lum = r.mean(axis=1)
    sel = np.ones(len(lum), bool)
    for _ in range(3):                                  # uitschieters eruit
        coef, *_ = np.linalg.lstsq(X[sel], lum[sel], rcond=None)
        res = lum - X @ coef
        sel = np.abs(res) < max(2.5 * np.std(res[sel]), 0.01)
    coef[1:] = np.clip(coef[1:], -MAX_SLOPE, MAX_SLOPE)
    coef[0] = np.median(lum[sel] - X[sel, 1:] @ coef[1:])
    coefficients=[]
    for c in range(3):
        cast = np.clip(np.median(r[sel, c] - lum[sel]), -MAX_CAST, MAX_CAST)
        coefficients.append(np.array([coef[0] + cast, coef[1], coef[2]]))
    if fit_only:return GainPlane(coefficients,(h,w))
    out=allocator("corrected",im.shape) if allocator else np.empty_like(im)
    gm=allocator("gain",im.shape) if allocator else np.empty_like(im)
    # Write all three channels before flushing this band, instead of rereading
    # and flushing the same mapped pages once per channel. Arithmetic is unchanged.
    for y0 in range(0,h,256):
        y1=min(h,y0+256);fy=np.arange(y0,y1,dtype=np.float32)[:,None]
        for c,coef in enumerate(coefficients):
            gmap=np.exp(coef[0]+coef[1]*fx/w+coef[2]*fy/h)
            gm[y0:y1,:,c]=np.clip(gmap,0.85,1.15)
            out[y0:y1,:,c]=im[y0:y1,:,c]*gm[y0:y1,:,c]
        if release:release()
    return out, gm


def edge_maps(warped, frames, order, size, sc=0.2):
    """Randen per scan (binnen het eigen scanvak, dus geen scanranden), het
    sterkste per plek; plus een gemiddeld grijsbeeld. Op verkleinde schaal."""
    w, h = int(size[0] * sc), int(size[1] * sc)
    Gx = np.zeros((h, w), np.float32); Gy = np.zeros((h, w), np.float32)
    acc = np.zeros((h, w), np.float32); cnt = np.zeros((h, w), np.float32)
    for k in order:
        g = cv2.resize(cv2.cvtColor(warped[k], cv2.COLOR_BGR2GRAY), (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 1.0)
        f = cv2.erode(cv2.resize(frames[k].astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST), np.ones((7, 7), np.uint8)) > 0
        Gx = np.maximum(Gx, np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0)) * f)
        Gy = np.maximum(Gy, np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1)) * f)
        acc += g * f; cnt += f
    lim = max(np.percentile(Gx, 99.5), np.percentile(Gy, 99.5))
    Gx = np.minimum(Gx, lim); Gy = np.minimum(Gy, lim)   # tekst niet laten domineren
    return Gx, Gy, acc / np.maximum(cnt, 1), cnt > 0


def ring_support(G, pts):
    """Gemiddelde randsterkte langs een omtrek (punten op verkleinde schaal)."""
    h, w = G.shape
    x = np.clip(np.round(pts[:, 0]).astype(int), 0, w - 1); y = np.clip(np.round(pts[:, 1]).astype(int), 0, h - 1)
    # beste waarde in een kleine omgeving (de rand ligt niet op de pixel precies)
    Gm = cv2.dilate(G, np.ones((5, 5), np.uint8))
    return float(Gm[y, x].mean())


def find_circle(gray, cover, G, sc=0.2):
    """De plaat: de grootste duidelijke cirkel. Geeft (cx, cy, r) op verkleinde schaal of None."""
    h, w = gray.shape
    g8 = np.clip(gray, 0, 255).astype(np.uint8)
    cs = cv2.HoughCircles(g8, cv2.HOUGH_GRADIENT, dp=2, minDist=min(w, h), param1=60, param2=40,
                          minRadius=int(0.30 * min(w, h)), maxRadius=int(0.55 * max(w, h)))
    if cs is None:
        return None
    best = None
    for cx, cy, r in cs[0][:5]:
        t = np.linspace(0, 2 * np.pi, 720, endpoint=False)
        pts = np.stack([cx + r * np.cos(t), cy + r * np.sin(t)], 1)
        sup = ring_support(G, pts)
        if best is None or sup > best[0]:
            best = (sup, (float(cx), float(cy), float(r)))
    return best


def find_square(Gx, Gy, size, sc=0.2):
    """Het vierkant (hoes) dat het best op de randen past. Voor elke kleine
    draaiing: profiel van horizontale en verticale randen, en het paar randen
    op afstand S (x en y bijna gelijk) met de meeste steun.
    Geeft (masker op canvas, hoek, kader na draaien, steun) of None."""
    h, w = Gx.shape
    c = (w / 2, h / 2)
    Smin, Smax = int(0.55 * min(w, h)), min(w, h) - 2
    best = None
    def pairs(P):
        n = len(P); out = np.full(Smax + 1, -1.0); arg = np.zeros(Smax + 1, int)
        for S in range(Smin, min(Smax, n - 1) + 1):
            v = P[:n - S] + P[S:]; i = int(np.argmax(v)); out[S] = v[i]; arg[S] = i
        return out, arg
    for ang in np.arange(-4, 4.01, 0.1):
        R = cv2.getRotationMatrix2D(c, ang, 1.0)
        Py = cv2.warpAffine(Gy, R, (w, h)).sum(axis=1); Px = cv2.warpAffine(Gx, R, (w, h)).sum(axis=0)
        by_, ay = pairs(Py); bx_, ax = pairs(Px)
        for S in range(Smin, Smax + 1):
            if by_[S] < 0:
                continue
            lo, hi = int(S * 0.96), min(int(S * 1.04) + 1, Smax)
            j = lo + int(np.argmax(bx_[lo:hi + 1]))
            if bx_[j] < 0:
                continue
            sc_ = by_[S] + bx_[j]
            if best is None or sc_ > best[0]:
                best = (sc_, ang, ax[j], ay[S], j, S)
    if best is None:
        return None
    # A closed outer rectangle is stronger evidence than unrelated profile
    # peaks (scanner lid on one side, printed artwork on another).
    closed=[]
    gradient=np.hypot(Gx,Gy)
    for threshold in (8,12,20,30):
        edges=cv2.morphologyEx((gradient>threshold).astype(np.uint8),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area=cv2.contourArea(contour)
            if area<.60*w*h:continue
            polygon=cv2.approxPolyDP(contour,.015*cv2.arcLength(contour,True),True)
            if len(polygon)!=4 or not cv2.isContourConvex(polygon):continue
            rect=cv2.minAreaRect(contour);rw,rh=rect[1]
            if min(rw,rh)<=0 or max(rw,rh)/min(rw,rh)>1.03 or area/(rw*rh)<.96:continue
            angle=rect[2]
            if angle>45:angle-=90
            if abs(angle)>4:continue
            corners=cv2.boxPoints(rect)
            if np.any(corners[:,0]<3) or np.any(corners[:,0]>w-4) or np.any(corners[:,1]<3) or np.any(corners[:,1]>h-4):continue
            rotation=cv2.getRotationMatrix2D(c,angle,1)
            aligned=corners@rotation[:,:2].T+rotation[:,2]
            left,top=aligned.min(axis=0);right,bottom=aligned.max(axis=0)
            closed.append((area,angle,int(round(left)),int(round(top)),int(round(right-left)),int(round(bottom-top))))
    closed_choice=False
    if closed:
        candidate=max(closed,key=lambda item:item[0])
        # Preserve established good crops: replace the profile result only when
        # the closed boundary disagrees materially in position or dimensions.
        discrepancy=max(abs(candidate[i]-best[i]) for i in range(2,6))/max(candidate[4:6])
        if discrepancy>.025:best=candidate;closed_choice=True
    _, ang, x0, y0, Sx, Sy = best
    # vierkant terug naar het canvas (volle resolutie)
    R = cv2.getRotationMatrix2D(c, ang, 1.0); Ri = cv2.invertAffineTransform(R)
    cor = np.float32([[x0, y0], [x0 + Sx, y0], [x0 + Sx, y0 + Sy], [x0, y0 + Sy]])
    cor = (cor @ Ri[:, :2].T + Ri[:, 2]) / sc
    m = np.zeros((size[1], size[0]), np.uint8)
    cv2.fillPoly(m, [np.round(cor).astype(np.int32)], 1)
    m = cv2.erode(m, np.ones((9, 9), np.uint8))           # schaduwrandje van de hoes eraf
    inset = max(5, int((.010 if closed_choice else .006) * max(Sx,Sy) / sc))
    box = (int(x0 / sc) + inset, int(y0 / sc) + inset, int(Sx / sc) - 2*inset, int(Sy / sc) - 2*inset)
    G = np.hypot(Gx, Gy); per = []
    for (xa, ya), (xb, yb) in zip(cor * sc, np.roll(cor * sc, -1, axis=0)):
        t = np.linspace(0, 1, 200)[:, None]; per.append(np.hstack([xa + t * (xb - xa), ya + t * (yb - ya)]))
    return m > 0, float(ang), box, ring_support(G, np.vstack(per)), closed_choice


def flatten_paper(out, inside, sc=0.125):
    """Schaduw in wit papier wegwerken (hoes lag niet helemaal plat, in elke
    scan net anders). Meet de helderheid van het witte papier, maak er een glad
    lichtveld van en licht de donkere plekken op tot het papier overal even wit
    is. Alleen ophelderen, alleen bij hoezen met flink wat wit papier."""
    h, w = out.shape[:2]
    small = cv2.resize(out[:, :, :3], (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
    ins = cv2.erode(cv2.resize(inside.astype(np.uint8), (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST), np.ones((5, 5), np.uint8)) > 0
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV); L = hsv[:, :, 2].astype(np.float32)
    if ins.sum() < 1000:
        return
    top = np.percentile(L[ins], 97)
    paper = ins & (L > top - 30) & (hsv[:, :, 1] < 30)
    paper = cv2.erode(paper.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0   # niet tegen tekst aan
    if paper.sum() < 0.15 * ins.sum():
        return
    sig = 0.012 * max(small.shape)
    pf = paper.astype(np.float32)
    field = cv2.GaussianBlur(L * pf, (0, 0), sig) / np.maximum(cv2.GaussianBlur(pf, (0, 0), sig), 1e-3)
    far = cv2.GaussianBlur(pf, (0, 0), sig) < 0.02                   # ver van papier: niets doen
    gain = np.clip(top / np.maximum(field, 1), 1.0, 1.25)
    gain[far] = 1.0
    gain = cv2.GaussianBlur(gain, (0, 0), sig / 2)
    g = cv2.resize(gain, (w, h), interpolation=cv2.INTER_CUBIC)
    out[:, :, :3] = np.clip(out[:, :, :3].astype(np.float32) * g[..., None], 0, 255).astype(np.uint8)
    print(f'wit papier gelijkgetrokken (max {gain.max():.2f}x opgehelderd)')
    return g


def render_full(paths, order, H, Tsh, O, f, out_small_wh, canvas_small, masks, wts, gainm, best, ks, flat, shape, source_scales=None, release_work=None, sources_ready=None, output_allocator=None,before_sources=None):
    """Het resultaat opnieuw opbouwen op volle scanresolutie, in blokken.
    Alles wat berekend is (uitlijning, kleurcorrectie, gewichten, welke scan
    per plek de details levert, vorm) komt van de kleine schaal; de pixels
    komen rechtstreeks uit de originele scans."""
    s = 1.0 / f
    S = np.diag([s, s, 1.0]); Si = np.diag([f, f, 1.0])
    Wf, Hf = int(round(out_small_wh[0] * s)), int(round(out_small_wh[1] * s))
    print(f'volle resolutie opbouwen: {Wf}x{Hf} px …', flush=True)
    wo, ho = out_small_wh
    O2 = O[:2]
    def to_out(m, interp):                              # kaart canvas -> uitvoer (klein)
        result=cv2.warpAffine(m,O2,(wo,ho),flags=interp,borderMode=cv2.BORDER_CONSTANT)
        drop_array_pages(m)
        return result
    W_o = {k: to_out(wts.pop(k).astype(np.float32,copy=False), cv2.INTER_LINEAR) for k in ks}
    V_o = {k: to_out(masks.pop(k).astype(np.uint8), cv2.INTER_NEAREST) for k in ks}
    G_o = {}
    for k in ks:
        gain=gainm.pop(k,None)
        G_o[k]=gain if isinstance(gain,GainPlane) else to_out(gain,cv2.INTER_LINEAR) if gain is not None else None
    gain=None
    gc.collect()
    B_o = to_out(best.astype(np.uint8), cv2.INTER_NEAREST)
    F_o = to_out(flat.astype(np.float32), cv2.INTER_LINEAR) if flat is not None else None
    if release_work is not None:release_work()
    gc.collect()
    progress('Originele scans openen',0,len(ks))
    with MappedScanStore(paths,ks,load,decode_into=load_into,on_reserved=before_sources,output_bytes=Wf*Hf*4,on_loaded=lambda current,total:progress('Originele scans openen',current,total)) as srcs:
        if sources_ready is not None:sources_ready()
        M, polys = {}, {}
        for k in ks:
            hk, wk = srcs[k].shape[:2]
            source_Si = np.diag([source_scales[k],source_scales[k],1.0]) if source_scales is not None else Si
            M[k] = S @ O @ Tsh @ H[k] @ source_Si                    # bron (vol) -> uitvoer (vol)
            e = 6 / source_scales[k] if source_scales is not None else 6*s
            c = np.float64([[e, e, 1], [wk - e, e, 1], [wk - e, hk - e, 1], [e, hk - e, 1]])
            polys[k] = (c @ M[k].T)[:, :2]
        if shape[0] == 'disc':
            cx, cy, r = shape[1]
            cxo, cyo = (O @ [cx, cy, 1])[:2] * s; ro = r * s
        inverse_O=np.linalg.inv(O)
        sig = TONE_SIGMA * s; pad = int(3 * sig) + 8
        tile=render_tile_size()
        print(f'geheugenbegrensd: bronbeelden via tijdelijke schijfblokken, uitvoerblokken {tile} px',flush=True)
        progress('Beeld opbouwen',0,1)
        out = output_allocator((Hf,Wf,4)) if output_allocator is not None else np.zeros((Hf,Wf,4),np.uint8)
        def sample(m, x0, y0, w, h, interp):               # kleine kaart -> blok op volle schaal
            A = np.array([[f, 0, (x0 + 0.5) * f - 0.5], [0, f, (y0 + 0.5) * f - 0.5]])
            return cv2.warpAffine(m, A, (w, h), flags=interp | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        nty = (Hf + tile - 1) // tile; ntx = (Wf + tile - 1) // tile
        for ty in range(nty):
            for tx in range(ntx):
                x0, y0 = tx * tile - pad, ty * tile - pad
                w = min(tile, Wf - tx * tile) + 2 * pad; h = min(tile, Hf - ty * tile) + 2 * pad
                T = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], float)
                low = np.zeros((h, w, 3), np.float32); high = np.zeros((h, w, 3), np.float32)
                acc = np.zeros((h, w), np.float32); anym = np.zeros((h, w), bool)
                bt = sample(B_o, x0, y0, w, h, cv2.INTER_NEAREST)
                for n, k in enumerate(ks):
                    pk = polys[k] - [x0, y0]
                    if pk[:, 0].max() < 0 or pk[:, 1].max() < 0 or pk[:, 0].min() > w or pk[:, 1].min() > h:
                        continue
                    fr = np.zeros((h, w), np.uint8)
                    cv2.fillPoly(fr, [np.round(pk * 16).astype(np.int32)], 1, shift=4)
                    if shape[0] == 'square':
                        mk = fr > 0
                    elif shape[0] == 'disc':
                        yy, xx = np.ogrid[0:h, 0:w]
                        mk = (fr > 0) & ((xx + x0 - cxo) ** 2 + (yy + y0 - cyo) ** 2 <= ro * ro)
                    else:
                        mk = (fr > 0) & (sample(V_o[k], x0, y0, w, h, cv2.INTER_NEAREST) > 0)
                    if not mk.any():
                        continue
                    im = cv2.warpAffine(srcs[k], (T @ M[k])[:2], (w, h), flags=cv2.INTER_LANCZOS4,
                                        borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
                    if G_o[k] is not None:
                        im *= G_o[k].output_block(inverse_O,f,x0,y0,w,h,out_small_wh) if isinstance(G_o[k],GainPlane) else sample(G_o[k], x0, y0, w, h, cv2.INTER_LINEAR)
                    mf = mk.astype(np.float32)
                    wk = (np.maximum(sample(W_o[k], x0, y0, w, h, cv2.INTER_LINEAR), 0) + 1e-4) * mf
                    mb = detail_blur(mf, sig)
                    lk = detail_blur(im * mf[..., None], sig) / np.maximum(mb, 1e-6)[..., None]
                    low += lk * wk[..., None]; acc += wk
                    winner = (bt == n) & mk
                    if winner.any():
                        win = cv2.GaussianBlur(winner.astype(np.float32), (0, 0), 2 * s)
                        high += (im - lk) * win[..., None]
                    anym |= mk
                res = low / np.maximum(acc, 1e-6)[..., None] + high
                if F_o is not None:
                    res *= sample(F_o, x0, y0, w, h, cv2.INTER_LINEAR)[..., None]
                blk = np.zeros((h, w, 4), np.uint8)
                blk[..., :3] = np.clip(res + 0.5, 0, 255).astype(np.uint8); blk[..., 3] = np.where(anym, 255, 0)
                out[ty * tile:ty * tile + h - 2 * pad, tx * tile:tx * tile + w - 2 * pad] = blk[pad:h - pad, pad:w - pad]
                srcs.drop_pages()
            flush_array_rows(out,ty*tile,min(Hf,(ty+1)*tile))
            srcs.space.committed((min(Hf,(ty+1)*tile)-ty*tile)*Wf*4)
            print(f'  {int(100 * (ty + 1) / nty)}%', flush=True)
        return out


def repair_paper_gaps(out,before_fill=None):
    """Continue local paper tones into small blank gaps; never fill with one global colour.
    Large gaps and gaps beside artwork stay transparent and are reported."""
    h,w = out.shape[:2]
    scale = min(1.0, 1600/max(h,w))
    small = cv2.resize(out, (round(w*scale),round(h*scale)), interpolation=cv2.INTER_AREA)
    hole = (small[...,3] < 128).astype(np.uint8)
    if not hole.any():
        return out
    n, labels, stats, _ = cv2.connectedComponentsWithStats(hole)
    accepted = np.zeros_like(hole)
    for k in range(1,n):
        m = (labels == k).astype(np.uint8)
        ring = (cv2.dilate(m,np.ones((11,11),np.uint8)) > 0) & (hole == 0)
        pixels = small[ring,:3]
        if len(pixels) < 30:
            continue
        # Paper only: little chroma and no printed detail adjacent to the gap.
        hsv = cv2.cvtColor(pixels.reshape(-1,1,3),cv2.COLOR_BGR2HSV).reshape(-1,3)
        plain = np.percentile(hsv[:,1],95) < 65 and np.percentile(hsv[:,2],10) > 140
        if stats[k,cv2.CC_STAT_AREA] < .08*hole.size and plain:
            accepted[m > 0] = 1
    if accepted.any():
        if before_fill is not None:before_fill()
        # Exclude the shadow and interpolation fringe at the edges of missing paper.
        accepted = cv2.dilate(accepted,np.ones((31,31),np.uint8))
        # Harmonic interpolation continues the surrounding tones smoothly.
        # Telea inpainting produces streaks in large areas of blank paper.
        fixed = None
        valid = (1-accepted).astype(np.float32)
        kernel = np.array([[0,.25,0],[.25,0,.25],[0,.25,0]],np.float32)
        longest = max(small.shape[:2])
        for side in (50,100,200,400,800,1600):
            side = min(side,longest)
            wh = (max(1,round(small.shape[1]*side/longest)),max(1,round(small.shape[0]*side/longest)))
            weights = cv2.resize(valid,wh,interpolation=cv2.INTER_AREA)
            known = cv2.resize(small[:,:,:3].astype(np.float32)*valid[...,None],wh,interpolation=cv2.INTER_AREA)/np.maximum(weights[...,None],1e-6)
            missing = cv2.resize(accepted,wh,interpolation=cv2.INTER_NEAREST)>0
            field = np.full_like(known,np.median(small[valid>0,:3],axis=0)) if fixed is None else cv2.resize(fixed,wh,interpolation=cv2.INTER_LINEAR)
            field[~missing] = known[~missing]
            for _ in range(300):
                mean = cv2.filter2D(field,-1,kernel,borderType=cv2.BORDER_REFLECT)
                field[missing] = mean[missing]
            fixed = field
            if side == longest:
                break
        fixed = np.clip(cv2.resize(fixed,(small.shape[1],small.shape[0])),0,255).astype(np.uint8)
        fill = cv2.resize(fixed,(w,h),interpolation=cv2.INTER_CUBIC)
        mask = cv2.resize(accepted,(w,h),interpolation=cv2.INTER_NEAREST)>0
        out[mask,:3] = fill[mask]; out[mask,3] = 255
        print(f'kleine lege papierdelen lokaal aangevuld: {100*mask.mean():.2f}%')
    remaining = (out[:,:,3]<128).mean()
    if remaining > .001:
        print(f'LET OP: {100*remaining:.2f}% van de hoes mist scaninformatie; transparant gelaten.')
    return out


def upright_preview(out):
    """Same RGB thumbnail as re-opening a PNG; share full-size bytes instead."""
    from PIL import Image
    h,w=out.shape[:2]
    # RGBX prevents alpha premultiplication, matching the established RGB conversion.
    image=Image.frombuffer('RGBX',(w,h),np.ascontiguousarray(out),'raw','RGBX',0,1)
    image.thumbnail((1600,1600))
    bgr=np.asarray(image.convert('RGB'))
    return Image.fromarray(bgr[:,:,::-1].copy())


def upright_output(out,work):
    import scan_cutout as CU
    progress('Leesrichting van de hoes controleren')
    q=CU.reading_quadrant(upright_preview(out))
    print('leesrichting: '+('onbekend' if q is None else str(q)),flush=True)
    if not q:return out
    view=np.rot90(out,-int(q//90))
    rotated=work.empty(('upright-output',0),view.shape,np.uint8)
    for y0 in range(0,view.shape[0],256):
        y1=min(view.shape[0],y0+256)
        rotated[y0:y1]=view[y0:y1]
        flush_array_rows(rotated,y0,y1)
        drop_array_pages(out)
    return rotated


def main():
    with contextlib.ExitStack() as resources:
        main_with_resources(resources)

def main_with_resources(resources,lease=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('uitvoer'); p.add_argument('delen', nargs='+')
    p.add_argument('--geen-kleur', action='store_true')
    p.add_argument('--rechtop',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--snelle-tussenbestanden',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--referentie', type=int)
    p.add_argument('--klein', action='store_true', help='uitvoer op ~300 dpi (snel) in plaats van de volle scanresolutie')
    p.add_argument('--vorm', choices=['auto', 'hoes', 'plaat', 'geen'], default='auto', help='hoes = vierkant, plaat = rond, geen = alleen op kleur (standaard: zelf bepalen)')
    a = p.parse_args()
    cv2.setNumThreads(2)
    if len(a.delen) < 2:
        sys.exit('minstens twee deelscans nodig')

    # grote scans (1200 dpi) eerst verkleinen: een Mac met 8 GB loopt anders vast.
    # Eén factor voor alle delen, anders passen ze niet meer op elkaar.
    from PIL import Image as _I
    _I.MAX_IMAGE_PIXELS = None
    metadata = [_I.open(path) for path in a.delen]
    max_source_pixels=max(im.width*im.height for im in metadata)
    # Reserve the larger of preparation and full-source decoding before allocating.
    # Admission only shrinks later, so concurrent workers cannot deadlock upgrading.
    reserve=max(29+max(0,len(a.delen)-4)*3, int(np.ceil((max_source_pixels*8+512*1024**2)/(64*1024**2))))
    lease=resources.enter_context(MemoryLease(min(70,reserve),phase='Deelscans openen'))
    dpis = [float(im.info.get('dpi',(0,0))[0]) for im in metadata]
    ref_dpi = max(dpis) if all(50<d<5000 for d in dpis) else None
    ratios = [ref_dpi/d for d in dpis] if ref_dpi else [1.]*len(dpis)
    longest = max(max(im.size)*ratio for im,ratio in zip(metadata,ratios))
    for im in metadata: im.close()
    if max(ratios)-min(ratios)>.01:
        print('Verschillende scanresoluties genormaliseerd: '+', '.join(str(round(d))+' dpi' for d in dpis),flush=True)
    f = min(1.0, MAX_SIDE / longest)
    if f < 1:
        print(f'rekenen op factor {f:.3f} ({int(longest * f)} px); uitvoer op ' + ('die schaal' if a.klein else f'volle resolutie ({longest} px)'))
    if f < 1 and not a.klein:
        # Check scratch requirements before expensive alignment/blending can trigger swap.
        MappedScanStore(a.delen,range(len(a.delen)),load)
    source_scales = [f*ratio for ratio in ratios]
    imgs=[];progress('Deelscans openen',0,len(a.delen))
    for index,(fn,scale) in enumerate(zip(a.delen,source_scales)):
        imgs.append(load(fn,scale,consume_cache=True));progress('Deelscans openen',index+1,len(a.delen))
    progress('Randen en achtergrond herkennen')
    valid = [~background_mask(im) for im in imgs]
    # kenmerken alleen op de hoes; maar is bijna alles als 'deksel' gezien (witte/crème
    # hoes op een wit deksel), zoek dan op de hele scan, anders mist hij de tekst
    def fmask(im, v):
        if v.mean() >= 0.25:
            return v
        m = np.ones(im.shape[:2], bool); m[:6] = m[-6:] = False; m[:, :6] = m[:, -6:] = False
        return m
    feats = [features(im, fmask(im, v)) for im, v in zip(imgs, valid)]
    progress('Deelscans precies uitlijnen')
    H, ref, W, missing = place(len(imgs), feats)
    if missing:
        unresolved = []
        for k in missing:
            gray = cv2.cvtColor(imgs[k],cv2.COLOR_BGR2GRAY).astype(np.float32)
            h,w = gray.shape; gray = gray[int(.15*h):int(.85*h),int(.15*w):int(.85*w)]
            detail = gray-cv2.GaussianBlur(gray,(0,0),3)
            if (np.abs(detail)>8).mean() < .001:
                print('LET OP: lege scan zonder betrouwbare uitlijning overgeslagen: '+a.delen[k])
            else:
                unresolved.append(k)
        if unresolved or len(H)<2:
            raise ValueError('Niet alle scans passen betrouwbaar op elkaar: ' + ', '.join(a.delen[k] for k in missing) + '. Selecteer alleen delen van dezelfde kant.')
    order = [k for k in range(len(imgs)) if k in H]
    if a.referentie:
        r = a.referentie - 1
        Hr = np.linalg.inv(H[r]); H = {k: Hr @ v for k, v in H.items()}; ref = r

    # oriëntatie altijd van het eerste deel (kleurreferentie kan een ander deel zijn)
    if order and order[0] == 0 and 0 in H:
        H0 = np.linalg.inv(H[0]); H = {k: H0 @ v for k, v in H.items()}

    # canvas
    corners = []
    for k in order:
        h, w = imgs[k].shape[:2]
        c = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        corners.append(cv2.perspectiveTransform(c, H[k]))
    allc = np.concatenate(corners)
    x0, y0 = np.floor(allc.min(axis=(0, 1))).astype(int); x1, y1 = np.ceil(allc.max(axis=(0, 1))).astype(int)
    Tsh = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], float); size = (x1 - x0, y1 - y0)

    warped, masks, frames = {}, {}, {}
    for k in order:
        M = (Tsh @ H[k])[:2]
        warped[k] = cv2.warpAffine(imgs[k], M, size, flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT)
        masks[k] = cv2.warpAffine(valid[k].astype(np.uint8), M, size, flags=cv2.INTER_NEAREST) > 0
        fr = np.zeros(imgs[k].shape[:2], np.uint8); fr[6:-6, 6:-6] = 1
        frames[k] = cv2.warpAffine(fr, M, size, flags=cv2.INTER_NEAREST) > 0

    imgs=valid=feats=None
    gc.collect()
    # 0. hoes of plaat? Een plaat (rond) gaat prima op kleur: het deksel eromheen
    #    wordt weggesneden. Een hoes is altijd vierkant: zoek het vierkant op de
    #    hoesranden; alles erbuiten is deksel, alles erbinnen hoes, welke kleur
    #    de hoes ook heeft (wit en grijs zijn op kleur niet van het deksel te
    #    onderscheiden, en het deksel is grijzer naarmate de hoes dikker is).
    square = None; disc_c = None
    if a.vorm != 'geen':
        Gx, Gy, gmean, cover = edge_maps(warped, frames, order, size)
        G = np.hypot(Gx, Gy)
        sq = find_square(Gx, Gy, size) if a.vorm in ('auto', 'hoes') else None
        ci = find_circle(gmean, cover, G) if a.vorm in ('auto', 'plaat') else None
        if os.environ.get('STITCH_DEBUG'): print('DEBUG steun vierkant', None if sq is None else round(sq[3], 1), 'cirkel', None if ci is None else round(ci[0], 1))
        is_disc = ci is not None and (sq is None or a.vorm == 'plaat' or (not sq[4] and ci[0] > 1.15 * sq[3]))
        if is_disc:
            cx, cy, r = (v / 0.2 for v in ci[1])
            disc = np.zeros((size[1], size[0]), np.uint8)
            cv2.circle(disc, (int(round(cx)), int(round(cy))), int(r * 1.01), 1, -1)
            disc_c = (cx, cy, r * 1.01)
            for k in order:
                masks[k] = frames[k] & (disc > 0)
            print(f'plaat: cirkel gevonden (diameter {2 * r:.0f} px)')
        elif sq is not None:
            square = sq[:3]
            sq_mask, sq_angle, sq_box = square
            for k in order:
                masks[k] = frames[k] & sq_mask
            print(f'hoes: vierkant gevonden ({sq_box[2]}x{sq_box[3]} px), scheefstand {sq_angle:+.2f} graden')

    Gx=Gy=gmean=G=cover=frames=None
    gc.collect()
    # 1. kleur/licht gelijktrekken: elk deel krijgt per kanaal een zacht
    #    verlopende correctie (vlak in log-ruimte: factor + lichtverloop van de
    #    scannerlamp), gemeten in de overlap met wat al samengevoegd is
    ks = list(order)
    height,width=size[1],size[0]
    print(f'rekencanvas: {width}x{height} px; werkbuffers op tijdelijke schijfblokken',flush=True)
    estimate=height*width*(4*len(ks)+32)
    progress('Werkbestanden voor samenvoegen voorbereiden')
    work=resources.enter_context(MappedArrayStore(estimate))
    img={k:CorrectedImage(warped[k]) for k in ks}
    wts={k:work.put(('weight',k),feather_weight(masks[k])) for k in ks}
    gainm={}
    progress('Belichting tussen deelscans afstemmen',0,len(ks))
    if not a.geen_kleur:
        done=[ref];todo=[k for k in ks if k!=ref]
        while todo:
            acc=sum(wts[d] for d in done);cm=acc>0;work.drop_pages()
            comp=None
            comp=work.empty(('composite',0),(height,width,3))
            for y0 in range(0,height,256):
                y1=min(height,y0+256)
                comp[y0:y1]=sum(img[d][y0:y1]*wts[d][y0:y1,...,None] for d in done)/np.maximum(acc[y0:y1],1e-6)[...,None]
                work.drop_pages()
            k=max(todo,key=lambda t:int((masks[t]&cm).sum()))
            if (masks[k]&cm).sum()<5000:break
            gain=gain_correct(img[k].raw,masks[k],comp,cm,release=work.drop_pages,fit_only=True)
            img[k].gain=gain
            gainm[k]=gain;gain=None
            done.append(k);todo.remove(k);work.drop_pages()
            progress('Belichting tussen deelscans afstemmen',len(done),len(ks))
        comp=acc=cm=None;work.discard(('composite',0))
    # Same sharpness winner as argmax, computed by bands without stacking all scores.
    progress('Details tussen deelscans vergelijken',0,height)
    best=np.zeros((height,width),np.uint8)
    # Keep the same 102-row convolution halo; wider bands avoid recomputing it.
    for y0 in range(0,height,768):
        y1=min(height,y0+768);top=max(0,y0-102);bottom=min(height,y1+102)
        value=np.full((y1-y0,width),-np.inf,np.float32);winner=np.zeros(value.shape,np.uint8)
        for n,k in enumerate(ks):
            g=cv2.cvtColor(np.clip(img[k][top:bottom],0,255).astype(np.uint8),cv2.COLOR_BGR2GRAY).astype(np.float32)
            sh=cv2.GaussianBlur(cv2.Laplacian(g,cv2.CV_32F)**2,(0,0),25)
            score=wts[k][y0:y1]*np.sqrt(sh[y0-top:y1-top]+1.0)
            better=score>value;value[better]=score[better];winner[better]=n
            work.drop_pages()
        best[y0:y1]=winner
        progress('Details tussen deelscans vergelijken',y1,height)
    value=winner=g=sh=score=better=None
    # Eén deelscan per plek: maak de keuzekaart samenhangend en neem ook de
    # grove laag vooral uit die scan. Overal mengen gaf dubbele, vage letters
    # waar een hoes niet vlak lag en de deelscans een paar pixels verschilden.
    progress('Naden tussen deelscans kiezen')
    value=np.full((height,width),-1.0,np.float32);coherent=np.zeros((height,width),np.uint8)
    for n,k in enumerate(ks):
        share=cv2.GaussianBlur(((best==n)&masks[k]).astype(np.float32),(0,0),WINNER_SMOOTH)
        share[~masks[k]]=-1.0
        better=share>value;value[better]=share[better];coherent[better]=n
    best[:]=coherent
    if len(ks)>1:
        # Welke deelscan per plek: de scherpste (zoals 0.4.11). De naadzoeker
        # mag alleen de grens verleggen, binnen een smalle strook, zodat die
        # tussen woorden en regels loopt. Zo kiest hij nooit een wazige rand of
        # een deelscan die op die plek niet goed op de andere ligt.
        corridor=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*SEAM_CORRIDOR+1,2*SEAM_CORRIDOR+1))
        allowed={k:(cv2.dilate((best==n).astype(np.uint8),corridor)>0)&masks[k] for n,k in enumerate(ks)}
        seams=seam_regions(img,allowed,ks,height,width)
        allowed=None
        if seams is not None:best[:]=np.where(seams<255,seams,best)
    value=coherent=share=better=None
    def lowpass(x,m):
        mb=cv2.GaussianBlur(m,(0,0),TONE_SIGMA)
        return cv2.GaussianBlur(x*m[...,None],(0,0),TONE_SIGMA)/np.maximum(mb,1e-6)[...,None]
    # Accumulate one band across all sources, then write the byte output directly.
    # Per-pixel source order and float32 arithmetic match the mapped-buffer path.
    pad=int(4*TONE_SIGMA)+2
    out=np.zeros((height,width,4),np.uint8);anymask=np.zeros((height,width),bool)
    progress('Overgangen tussen deelscans afwerken',0,len(ks)*height)
    for y0 in range(0,height,256):
        y1=min(height,y0+256);top=max(0,y0-pad);bottom=min(height,y1+pad)
        low=np.zeros((y1-y0,width,3),np.float32);high=np.zeros_like(low)
        for n,k in enumerate(ks):
            mk=masks[k][top:bottom].astype(np.float32)
            lk=lowpass(img[k][top:bottom],mk)[y0-top:y1-top]
            low+=lk*wts[k][y0:y1,...,None]
            win=cv2.GaussianBlur(((best[top:bottom]==n)&masks[k][top:bottom]).astype(np.float32),(0,0),2)[y0-top:y1-top]
            high+=(img[k][y0:y1]-lk)*win[...,None]
            work.drop_pages()
        acc=sum(wts[k][y0:y1] for k in ks)
        res=low/np.maximum(acc,1e-6)[...,None]+high
        out[y0:y1,:,:3]=np.clip(res+.5,0,255).astype(np.uint8)
        for k in ks:anymask[y0:y1]|=masks[k][y0:y1]
        out[y0:y1,:,3]=np.where(anymask[y0:y1],255,0)
        work.drop_pages()
        progress('Overgangen tussen deelscans afwerken',len(ks)*y1,len(ks)*height)
    imgs=valid=feats=warped=frames=img=low=high=score=res=acc=g=sh=mk=lk=win=None
    work.keep_only({('weight',k) for k in ks}|{('gain',k) for k in ks})
    gc.collect()
    flat = None
    if square is not None and not a.geen_kleur:
        progress('Verlichting van de hoes gelijkmaken')
        flat = flatten_paper(out, square[0])
    progress('Vorm rechtzetten en randen controleren')
    O = np.eye(3)                                         # canvas -> uitvoer (kleine schaal)
    if square is not None:
        # recht op de hoesranden en precies op het vierkant bijsnijden
        sq_mask, sq_angle, (bx, by, bw, bh) = square
        R = cv2.getRotationMatrix2D((size[0] / 2, size[1] / 2), sq_angle, 1.0)
        out = cv2.warpAffine(out, R, size, flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
        out = out[by:by + bh, bx:bx + bw]
        anymask = out[:, :, 3] > 128
        O = np.array([[1, 0, -bx], [0, 1, -by], [0, 0, 1]], float) @ np.vstack([R, [0, 0, 1]])
    nz = anymask
    ys, xs = np.where(nz)
    out = out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    O = np.array([[1, 0, -xs.min()], [0, 1, -ys.min()], [0, 0, 1]], float) @ O
    if f < 1 and not a.klein:
        shape = ('square', None) if square is not None else (('disc', disc_c) if disc_c is not None else (None, None))
        out_wh=(out.shape[1],out.shape[0])
        imgs=valid=feats=warped=frames=img=score=low=high=res=acc=msU=nz=anymask=None
        Gx=Gy=gmean=G=cover=g=sh=mk=win=out=comp=cm=ys=xs=None
        best=best.astype(np.uint8)
        gc.collect()
        field_bytes=out_wh[0]*out_wh[1]*(5*len(ks)+1+(4 if flat is not None else 0))
        field_units=max(1,int(np.ceil((field_bytes+192*1024**2)/(64*1024**2))))
        decoder_units=max(field_units,int(np.ceil((max_source_pixels*8+field_bytes+192*1024**2)/(64*1024**2))))
        if lease is not None and decoder_units>lease.weight:
            # Reject a group whose decoder would exceed its admitted maximum;
            # never wait for an upgrade beyond the preparation reservation.
            raise ValueError('Dit onderdeel vraagt meer werkgeheugen dan vooraf beschikbaar was. Verwerk minder delen tegelijk.')
        def release_preparation():
            work.keep_only(set())
            if lease is not None:lease.resize(field_units)
        out = render_full(a.delen, order, H, Tsh, O, f, out_wh, size,
                          masks, wts, gainm, best, ks, flat, shape, source_scales, release_work=release_preparation,sources_ready=lambda:lease.resize(min(lease.weight,12+max(0,len(ks)-4))) if lease is not None else None,output_allocator=lambda shape:work.empty(('full-output',0),shape,np.uint8),before_sources=lambda:lease.grow(decoder_units,phase='Originele scans openen') if lease is not None else None)
        masks=wts=gainm=best=flat=None
        gc.collect()
    # Full source maps and tile buffers have gone. Flushed output bytes can wait
    # on disk while the independent save/repair stage acquires its own budget.
    drop_array_pages(out)
    gc.collect()
    encode_units=min(70,4+int(np.ceil(out.nbytes/(64*1024**2))))
    if lease is not None:lease.release()
    final_lease=resources.enter_context(MemoryLease(encode_units,phase='Samengesteld beeld opslaan'))
    repair_expanded=False
    def before_paper_fill():
        nonlocal final_lease,repair_expanded
        # Most covers need only the small inspection. Reserve the expensive
        # full-size local fill only when the inspected image actually needs it.
        drop_array_pages(out)
        gc.collect()
        final_lease.release()
        final_lease=resources.enter_context(MemoryLease(48,phase='Kleine open randen aanvullen'))
        repair_expanded=True
    if square is not None:
        progress('Kleine open randen controleren')
        out=repair_paper_gaps(out,before_fill=before_paper_fill)
        drop_array_pages(out)
        if repair_expanded:
            gc.collect()
            final_lease.release()
            final_lease=resources.enter_context(MemoryLease(encode_units,phase='Samengesteld beeld opslaan'))
    if a.rechtop and square is not None:
        out=upright_output(out,work)
    progress('Samengesteld beeld opslaan')
    if a.snelle_tussenbestanden and disc_c is not None:
        import json
        a.uitvoer += '.tif'
        if not cv2.imwrite(a.uitvoer,out,[cv2.IMWRITE_TIFF_COMPRESSION,1]):
            raise OSError('Could not write lossless intermediate')
        print('SLEEVE_INTERMEDIATE '+json.dumps({'path':a.uitvoer}),flush=True)
    elif not cv2.imwrite(a.uitvoer, out, [cv2.IMWRITE_PNG_COMPRESSION, 1]):
        raise OSError('Could not save merged image')
    print(f'klaar: {a.uitvoer}  ({out.shape[1]}x{out.shape[0]}, {len(order)} delen, referentie: {a.delen[ref]})')


if __name__ == '__main__':
    main()
