#!/usr/bin/env python3
"""Voortoets voor een wijziging in het samenvoegen: welke onderdelen van de vaste toets veranderen echt?

Per onderdeel met meer dan één scan wordt alleen de keuze 'welke deelscan waar' berekend, op rekenschaal
(scan_stitch.py --klein met STITCH_CHOICE_ONLY), zonder eindbeeld, twee tegelijk. Dat gebeurt met de code van nu en met
de code van een eerdere versie (standaard de laatste commit), en de twee kaarten worden vergeleken.
Kaarten worden bewaard per versie van de samenvoeg-code, dus de oude kant wordt maar één keer berekend.

  snel.py [naam ...] [--tegen REF] [--jobs N]

Eindigt met de releases die door de volledige toets moeten (reference.py run ...). Dat is alleen de
keuzekaart: een wijziging buiten het samenvoegen (uitsnijden, rechtop) ziet deze voortoets niet; daarvoor
de gewone toets, die het samengevoegde beeld uit de cache haalt zolang het samenvoegen niet veranderd is.
"""
import argparse, concurrent.futures as CF, hashlib, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF = json.loads(Path(__file__).with_name('reference.json').read_text())
SCANS = Path(os.environ.get('SLEEVE_TESTSCANS') or Path.home() / 'Desktop')
PY = Path.home() / 'Library/Application Support/com.repriselabs.Sleeve/Runtime/bin/python3'
CACHE = Path.home() / 'Library/Caches/com.repriselabs.Sleeve/reference/choice'
STITCH_FILES = ('scan_stitch.py', 'scan_blend.py', 'scan_fields.py', 'scan_memory.py', 'scan_progress.py', 'scan_dpi.py', 'scan_edges.py', 'scan_cutout.py')
HOOK = """        if os.environ.get('STITCH_CHOICE_ONLY'):
            lab_=np.full(best.shape,255,np.uint8)
            for n_,k_ in enumerate(ks):lab_[(best==n_)&masks[k_]]=k_
            cv2.imwrite(os.environ['STITCH_CHOICE_ONLY'],lab_);sys.exit(0)
"""
BEST_LINE = "        if os.environ.get('STITCH_BEST'):"
DISC = ('sidea', 'sideb', 'sidec', 'sided', 'cd', 'cd1', 'cd2')


def code_hash(tools):
    h = hashlib.sha1()
    for f in STITCH_FILES:
        p = Path(tools) / f
        if p.exists():
            h.update(f.encode()); h.update(p.read_bytes())
    return h.hexdigest()[:12]


def old_tools(ref, dest):
    """De samenvoeg-code van een eerdere versie, met de voortoets-haak erin als die er nog niet in zat."""
    for f in STITCH_FILES:
        r = subprocess.run(['git', '-C', str(ROOT), 'show', f'{ref}:Resources/Tools/{f}'], capture_output=True)
        if r.returncode == 0:
            (dest / f).write_bytes(r.stdout)
    for f in (ROOT / 'Resources/Tools').glob('*.py'):          # overige modules zoals ze nu zijn
        if not (dest / f.name).exists():
            shutil.copy2(f, dest / f.name)
    st = (dest / 'scan_stitch.py').read_text()
    if 'STITCH_CHOICE_ONLY' not in st:
        i = st.index(BEST_LINE); j = st.index('\n', i) + 1
        (dest / 'scan_stitch.py').write_text(st[:j] + HOOK + st[j:])


def parts():
    for c in REF['cases']:
        folder = SCANS / c['folder']
        for i, s in enumerate(c['slots']):
            if len(s['files']) > 1 and all((folder / f).is_file() for f in s['files']):
                yield c['name'], f"{i}_{s['part']}", s['part'], [str(folder / f) for f in s['files']]


def choice_map(tools, chash, name, tag, part, files):
    out = CACHE / chash / f'{name}__{tag}.png'
    if out.exists():
        return out, True
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='sleeve-snel-'))
    try:
        cmd = [str(PY if PY.exists() else sys.executable), str(Path(tools) / 'scan_stitch.py'), str(work / 'x.png'), *files, '--vorm', 'ruw', '--klein']
        if part in DISC:
            cmd.append('--plaat-onderdeel')
        r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, STITCH_CHOICE_ONLY=str(out)), timeout=3600)
        if not out.exists():
            return f'no map ({(r.stderr or r.stdout).strip().splitlines()[-1:] })', False
        return out, False
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    import cv2, numpy as np
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('names', nargs='*'); p.add_argument('--tegen', default='HEAD'); p.add_argument('--jobs', type=int, default=2)   # 8 GB geheugen: twee tegelijk
    a = p.parse_args()
    t0 = time.time()
    new_tools = ROOT / 'Resources/Tools'; new_hash = code_hash(new_tools)
    tmp = Path(tempfile.mkdtemp(prefix='sleeve-oud-')); old_tools(a.tegen, tmp); old_hash = code_hash(tmp)
    todo = [x for x in parts() if not a.names or x[0] in a.names]
    print(f'{len(todo)} parts; code now {new_hash}, {a.tegen} {old_hash}' + ('  (same stitch code: nothing can change)' if new_hash == old_hash else ''), flush=True)
    if new_hash == old_hash:
        shutil.rmtree(tmp, ignore_errors=True); return
    jobs = []
    with CF.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for x in todo:
            jobs.append((x, pool.submit(choice_map, tmp, old_hash, *x), pool.submit(choice_map, new_tools, new_hash, *x)))
        changed = {}
        for (name, tag, part, files), fo, fn in jobs:
            (po, co), (pn, cn) = fo.result(), fn.result()
            if isinstance(po, str) or isinstance(pn, str):
                print(f'  {name:24s} {tag:10s} ?  {po if isinstance(po, str) else pn}', flush=True); changed.setdefault(name, []).append(tag); continue
            mo, mn = cv2.imread(str(po), 0), cv2.imread(str(pn), 0)
            if mo is None or mn is None or mo.shape != mn.shape:
                print(f'  {name:24s} {tag:10s} CANVAS DIFFERS (alignment changed)', flush=True); changed.setdefault(name, []).append(tag); continue
            both = (mo != 255) & (mn != 255)
            frac = float((mo[both] != mn[both]).mean()) if both.any() else 0.0
            mark = 'CHANGED' if frac > 0.002 else 'same'
            print(f'  {name:24s} {tag:10s} {mark:8s} {100 * frac:5.2f}% of the canvas from another scan', flush=True)
            if frac > 0.002:
                changed.setdefault(name, []).append(tag)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'({time.time() - t0:.0f} s)')
    if changed:
        print('Full test needed for: ' + ' '.join(changed))
        print('  python3 Tests/feiten/reference.py run ' + ' '.join(changed))
    else:
        print('No part chooses its scans differently: the stitch change does not change these releases.')


if __name__ == '__main__':
    main()
