#!/usr/bin/env python3
"""Vaste toets voor de feitenroute: goedgekeurde releases opnieuw maken en vergelijken.

Elke release in reference.json heeft zijn scans, zijn vakken, zijn Discogs-link en per onderdeel
de vastgelegde uitkomst: oordeel, maat in mm, stand en een kleine beeldafdruk. 'run' maakt de
release opnieuw via de bridge (dezelfde weg als de app) en meldt elk verschil. Zo breekt een
verbetering voor de ene hoes niet ongemerkt een andere.

  reference.py list                     welke releases er zijn, en of de scans op deze Mac staan
  reference.py run [naam ...]           maken en vergelijken (zonder naam: alle snelle)
               [--groot]                ook de grote releases (1200 dpi, duurt lang, ±5 GB vrij nodig)
               [--keep MAP]             de gemaakte beelden bewaren in MAP (om te bekijken)
  reference.py record naam ... [--approved]
                                        de uitkomst van nu vastleggen (na akkoord van André: --approved)

De scans staan buiten de repo: map SLEEVE_TESTSCANS (standaard ~/Desktop). Een release waarvan
de scans er niet zijn, wordt overgeslagen en gemeld. Eindigt met code 1 als er iets verschilt.
"""
import argparse, datetime, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(os.environ.get('SLEEVE_REFERENCE_ROOT') or Path(__file__).resolve().parents[2])   # andere versie toetsen: map met Resources/ en build.sh
REF = Path(__file__).with_name('reference.json')
SCANS = Path(os.environ.get('SLEEVE_TESTSCANS') or Path.home() / 'Desktop')
SIZE_MM = 0.3            # zoveel mag een maat verschillen (meetruis van de randen)
ANGLE = 1.0              # graden: zoveel mag de stand van een plaat of cd verschillen
THUMB = 24               # beeldafdruk: 24 x 24 grijswaarden
THUMB_DIFF = 6.0         # gemiddeld verschil (0-255) waarboven het beeld echt anders is
REMEMBERED = ('.anouk-referenties.json', '.sleeve-beslissingen.json', '.sleeve-release.json')


def version():
    """Versie van wat getoetst wordt: build.sh in de repo, of Info.plist in een gebouwde app (Contents)."""
    for f in (ROOT / 'build.sh', ROOT / 'Info.plist'):
        if f.exists():
            m = re.search(r'CFBundleShortVersionString</key>\s*<string>([^<]+)', f.read_text(errors='ignore'))
            if m:
                return m[1]
    return '?'


def key(part, files):
    return part + '|' + '|'.join(sorted(os.path.basename(f) for f in files))


def thumb(path):
    """Kleine beeldafdruk: vangt een andere stand of een verschoven snede, ook als de maat gelijk is."""
    import cv2, numpy as np
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    if im.shape[2] == 4:
        a = im[:, :, 3:4].astype(np.float32) / 255
        im = (im[:, :, :3] * a + 128 * (1 - a)).astype(np.uint8)
    g = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (THUMB, THUMB), interpolation=cv2.INTER_AREA).astype(int).ravel().tolist()


def make(case, keep=None):
    """De release maken via de bridge; geeft {sleutel: uitkomst} of een foutmelding (str)."""
    folder = SCANS / case['folder']
    rows = []
    for i, slot in enumerate(case['slots']):
        for f in slot['files']:
            if not (folder / f).is_file():
                return f'scans not on this Mac: {folder / f}'
            rows.append({'path': str(folder / f), 'part': slot['part'], 'group': f'g{i}', 'reference': False, 'partial': False, 'source': ''})
    saved = {n: (folder / n).read_bytes() for n in REMEMBERED if (folder / n).exists()}
    for n in ('.sleeve-beslissingen.json',):               # de toets meet de feiten, niet eerdere beslissingen
        if (folder / n).exists():
            (folder / n).unlink()
    work = Path(tempfile.mkdtemp(prefix='sleeve-reference-'))
    try:
        out = work / 'out'; out.mkdir()
        req = {'action': 'scan', 'inputs': rows, 'discogs': case.get('discogs', ''), 'variant': '', 'useNames': True, 'useStand': True,
               'format': case.get('format', 'auto'), 'packaging': case.get('packaging', 'auto'), 'year': '', 'output': str(out)}
        (work / 'request.json').write_text(json.dumps(req))
        py = Path.home() / 'Library/Application Support/com.repriselabs.Sleeve/Runtime/bin/python3'
        p = subprocess.run([str(py) if py.exists() else sys.executable, str(ROOT / 'Resources/studio_bridge.py'), str(work / 'request.json')],
                           capture_output=True, text=True, timeout=3 * 3600)
        found = list(out.glob('*/Studio-verwerking.json'))
        if not found:
            last = [json.loads(s).get('message', '') for s in p.stdout.splitlines() if s.startswith('{"event": "error"')]
            return 'nothing made: ' + (last[-1] if last else (p.stderr or p.stdout)[-300:])
        got = {}
        for r in json.loads(found[0].read_text()).get('results', []):
            paths = [q['path'] for q in r.get('panels') or []] or ([r['path']] if r.get('path') else [])
            got[key(r['part'], r.get('scans', []))] = {
                'part': r['part'], 'files': sorted(os.path.basename(f) for f in r.get('scans', [])),
                'verdict': r.get('verdict'), 'size_mm': r.get('size_mm'), 'panels': len(r.get('panels') or []),
                'rotate': (r.get('upright') or {}).get('rotate_clockwise'), 'why': r.get('why', []),
                'applied': r.get('applied', ''), 'thumb': thumb(paths[0]) if paths else None}
        if keep:
            dest = Path(keep) / case['name']; dest.mkdir(parents=True, exist_ok=True)
            for f in found[0].parent.iterdir():
                shutil.copy2(f, dest / f.name)
        return got
    finally:
        shutil.rmtree(work, ignore_errors=True)
        for n in REMEMBERED:                               # de map met scans blijft zoals hij was
            if n in saved:
                (folder / n).write_bytes(saved[n])
            elif (folder / n).exists():
                (folder / n).unlink()


def angle_diff(a, b):
    return abs(((float(a) - float(b) + 180) % 360) - 180)


def compare(want, got):
    """Verschillen tussen de vastgelegde en de nieuwe uitkomst van één onderdeel (lijst met tekst)."""
    out = []
    if want['verdict'] != got['verdict']:
        out.append(f"verdict {want['verdict']} -> {got['verdict']}" + (f" ({'; '.join(got['why'])[:160]})" if got['why'] else ''))
    if (want.get('size_mm') is None) != (got.get('size_mm') is None):
        out.append(f"size {want.get('size_mm')} -> {got.get('size_mm')}")
    elif want.get('size_mm') and max(abs(a - b) for a, b in zip(want['size_mm'], got['size_mm'])) > SIZE_MM:
        out.append(f"size {want['size_mm']} -> {got['size_mm']} mm")
    if want.get('panels', 0) != got.get('panels', 0):
        out.append(f"panels {want.get('panels', 0)} -> {got.get('panels', 0)}")
    wr, gr = want.get('rotate'), got.get('rotate')
    if (wr is None) != (gr is None) or (wr is not None and angle_diff(wr, gr) > ANGLE):
        out.append(f'upright {wr} -> {gr} degrees')
    if want.get('thumb') and got.get('thumb') and len(want['thumb']) == len(got['thumb']):
        d = sum(abs(a - b) for a, b in zip(want['thumb'], got['thumb'])) / len(want['thumb'])
        if d > THUMB_DIFF and not out:
            out.append(f'image differs (mean {d:.1f} of 255) with the same size and verdict: look at it')
    elif bool(want.get('thumb')) != bool(got.get('thumb')):
        out.append('image ' + ('no longer made' if want.get('thumb') else 'now made'))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command', choices=['list', 'run', 'record']); p.add_argument('names', nargs='*')
    p.add_argument('--groot', action='store_true'); p.add_argument('--keep'); p.add_argument('--approved', action='store_true')
    a = p.parse_args()
    data = json.loads(REF.read_text())
    cases = {c['name']: c for c in data['cases']}
    unknown = [n for n in a.names if n not in cases]
    if unknown:
        sys.exit('unknown release: ' + ', '.join(unknown) + '. Known: ' + ', '.join(cases))
    if a.command == 'list':
        for c in data['cases']:
            here = all((SCANS / c['folder'] / f).is_file() for s in c['slots'] for f in s['files'])
            rec = c.get('recorded') or {}
            print(f"{c['name']:<22} {c.get('tier', 'snel'):<6} {len(c['slots'])} parts  scans {'here' if here else 'MISSING'}  "
                  f"recorded {rec.get('version', '-')} {rec.get('date', '')}  {'approved' if c.get('approved') else 'not yet approved'}")
        return
    if a.command == 'record' and not a.names:
        sys.exit('record: name the releases (so nothing is recorded by accident)')
    chosen = [cases[n] for n in a.names] if a.names else [c for c in data['cases'] if a.groot or c.get('tier', 'snel') != 'groot']
    bad = skipped = 0
    for c in chosen:
        t0 = time.time(); print(f"== {c['name']}", flush=True)
        got = make(c, a.keep)
        if isinstance(got, str):
            print('   SKIPPED:' if got.startswith('scans not') else '   FAILED:', got, flush=True)
            skipped += got.startswith('scans not'); bad += not got.startswith('scans not'); continue
        if a.command == 'record':
            c['expect'] = list(got.values()); c['approved'] = bool(a.approved)
            c['recorded'] = {'version': version(), 'date': datetime.date.today().isoformat()}
            REF.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
            for g in got.values():
                print(f"   recorded {g['part']:<8} {g['verdict']:<8} {g['size_mm']} upright {g['rotate']}" + (f"  | {'; '.join(g['why'])[:110]}" if g['why'] else ''))
        else:
            want = {key(e['part'], e['files']): e for e in c.get('expect', [])}
            if not want:
                print('   nothing recorded yet for this release (use: record)'); bad += 1; continue
            for k in sorted(set(want) | set(got)):
                if k not in got:
                    print(f"   DIFFERENT {want[k]['part']}: not made any more"); bad += 1
                elif k not in want:
                    print(f"   DIFFERENT {got[k]['part']}: made, but not in the reference"); bad += 1
                else:
                    diff = compare(want[k], got[k])
                    print(f"   {'DIFFERENT' if diff else 'same     '} {got[k]['part']:<8} {got[k]['verdict']:<8} {got[k]['size_mm']}" + ('  | ' + '; '.join(diff) if diff else ''))
                    bad += bool(diff)
        print(f'   ({time.time() - t0:.0f} s)', flush=True)
    if a.command == 'run':
        print(f"Reference: {'ALL THE SAME' if not bad else str(bad) + ' DIFFERENT'}" + (f', {skipped} skipped (scans not here)' if skipped else ''))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
