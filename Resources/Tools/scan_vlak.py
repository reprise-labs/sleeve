#!/usr/bin/env python3
"""Optie: de helderheid van effen vinyl gelijktrekken (André 14 nov, 'optie 1').

Wit vinyl toont na het scannen soms lichte grijze vlekken (licht van de scanner, de rand van het glas): Queen 2021
kant A, helderheid 95 tegen 99. Gemeten, niet verzonnen: per plek de helderheid van het vinyl over een paar mm
(gemiddelde over de omgeving), vergeleken met hoe licht het vinyl op dezelfde afstand van het midden rondom is
(90e percentiel); zo blijft wat rondom gelijk is (de afgeronde rand, de uitloop) zoals het is.
Waar het donkerder is, gaat alleen de helderheid omhoog (alle drie de kleuren met dezelfde factor); groeven, stof en
krasjes blijven zoals ze gescand zijn. Alleen voor effen vinyl (een kleur), alleen ophelderen, hooguit 8 L.
Label en gaatje blijven onaangeroerd. Standaard uit; als het gebeurt, staat het bij het resultaat.

Gebruik als programma: scan_vlak.py <in.png> <uit.png>  (drukt een json-regel af)
"""
import json, sys

import cv2
import numpy as np

MAX_L = 8.0          # hooguit zoveel L-eenheden lichter
PLAIN = 0.90         # zoveel van het vinyl moet binnen ΔE 12 van de mediaankleur liggen (effen)
INNER = 0.30         # binnen 30% van de straal niet (gaatje); het label valt af op kleur (lp-label 100 mm: 33%)


def level(img, dpi):
    """img: BGR of BGRA, de uitgesneden plaat (rond, midden = midden van het beeld). Geeft (img, info)."""
    h, w = img.shape[:2]
    alpha = img[..., 3] if img.ndim == 3 and img.shape[2] == 4 else np.full((h, w), 255, np.uint8)
    bgr = img[..., :3]
    k = max(1, int(round(dpi / 150)))                      # rekenen op ±150 dpi (0,17 mm): ook een smalle strook langs de rand
    sw, sh = max(8, w // k), max(8, h // k)
    lab = cv2.cvtColor(cv2.resize(bgr, (sw, sh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB).astype(np.float32)
    am = cv2.resize(alpha, (sw, sh), interpolation=cv2.INTER_AREA) > 250
    yy, xx = np.mgrid[0:sh, 0:sw]
    r = np.hypot(xx - sw / 2, yy - sh / 2) / (min(sw, sh) / 2)
    ring = am & (r > INNER + .05) & (r < .97)
    if ring.sum() < 100:
        return img, {'levelled': False, 'why': 'too little vinyl to measure'}
    med = np.median(lab[ring], 0)
    dE = np.linalg.norm(lab - med, axis=2)
    plain = float((dE[ring] < 12).mean())
    if plain < PLAIN:
        return img, {'levelled': False, 'plain': round(plain, 3),
                     'why': f'the vinyl is not one plain colour ({100 * plain:.0f}% near its main colour); tone not levelled'}
    if med[0] * 100 / 255 < 60:
        # donker vinyl: daar zijn de vlekken glans (lichter), geen schaduw; ophelderen zou de glans overal leggen
        return img, {'levelled': False, 'plain': round(plain, 3), 'why': 'only light vinyl is levelled (dark vinyl shows gloss, not shade)'}
    vin = am & (r > INNER) & (dE < 12)
    # Rondom meten: per afstand tot het midden is de plaat van zichzelf gelijk (ook de afgeronde rand en de uitloop
    # zijn rondom even licht). Een plek die donkerder is dan de rest op dezelfde afstand is licht van de scan, geen
    # plaat. In poolcoördinaten: 0,5 mm in de straal en 1 graad rond, zodat ook een strook van een paar mm langs de
    # rand meetelt (Queen 2021 kant A rechtsboven: 96,5 -> 98,5 bij 99,2 rondom; breder meten liet de buren doorschieten).
    L = lab[..., 0] * 100 / 255
    c = (sw / 2, sh / 2); Rp = min(sw, sh) / 2; NA = 1440
    pol = lambda a_: cv2.warpPolar(a_, (int(Rp), NA), c, Rp, cv2.WARP_POLAR_LINEAR)
    PL, PM = pol(L.astype(np.float32)), pol(vin.astype(np.float32))
    mm_px = 25.4 / dpi * k
    sr = max(.5 / mm_px, 1.0); st = 1 / 360 * NA
    blur = lambda a_: cv2.GaussianBlur(cv2.copyMakeBorder(a_, int(4 * st), int(4 * st), 0, 0, cv2.BORDER_WRAP), (0, 0), sigmaX=sr, sigmaY=st)[int(4 * st):-int(4 * st)]
    lp = blur(PL * PM) / np.maximum(blur(PM), 1e-3)
    ok = blur(PM) > .3
    target = np.full(lp.shape[1], np.nan, np.float32)
    for col in range(lp.shape[1]):
        v_ = lp[ok[:, col], col]
        if len(v_) > NA * .5:
            target[col] = np.percentile(v_, 90)
    if np.isnan(target).all():
        return img, {'levelled': False, 'why': 'too little vinyl to measure'}
    d = np.clip(target[None, :] - lp, 0, MAX_L)
    d[:, np.isnan(target)] = 0; d[~ok] = 0
    d = cv2.GaussianBlur(d.astype(np.float32), (0, 0), 1.0)
    D = cv2.warpPolar(d, (sw, sh), c, Rp, cv2.WARP_POLAR_LINEAR | cv2.WARP_INVERSE_MAP) * (am & (r > INNER))
    lpc = cv2.warpPolar(np.nan_to_num(lp, nan=99).astype(np.float32), (sw, sh), c, Rp, cv2.WARP_POLAR_LINEAR | cv2.WARP_INVERSE_MAP)
    if float(D[vin].max()) < .5:
        return img, {'levelled': False, 'plain': round(plain, 3), 'why': 'the vinyl tone is already even'}
    gain = 1 + D / np.maximum(lpc, 20)                     # zelfde factor voor B, G en R: alleen lichter, zelfde kleur
    G = cv2.resize(gain, (w, h), interpolation=cv2.INTER_CUBIC)[..., None]
    out = np.clip(bgr.astype(np.float32) * G, 0, 255)
    out = np.where(G > 1.0005, out.round(), bgr).astype(np.uint8)   # waar niets verandert: exact het origineel
    res = np.dstack([out, alpha]) if img.ndim == 3 and img.shape[2] == 4 else out
    return res, {'levelled': True, 'plain': round(plain, 3), 'max_L': round(float(D[vin].max()), 1),
                 'mean_L': round(float(D[vin].mean()), 2)}


def main():
    src, dst = sys.argv[1], sys.argv[2]
    img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
    dpi = 0.0
    try:
        from PIL import Image
        with Image.open(src) as im:
            dpi = float((im.info.get('dpi') or (0, 0))[0])
    except Exception:
        pass
    if not dpi:
        dpi = img.shape[1] / (300 / 25.4)                  # lp-maat als terugval
    out, info = level(img, dpi)
    cv2.imwrite(dst, out)
    print(json.dumps(info))


if __name__ == '__main__':
    main()
