"""Reference set for the own test scans: approved results to compare against.

Records what is right (grouping, cover or record, part, size in mm, straight
labels) and compares a new version with it before a version is built. The scans
live outside the source (~/Desktop/vinyl), so this runs locally and not in
scripts/check.sh.

  python3 reference.py record <run-folder> [reference.json]  approved run as the reference
  python3 reference.py run <run-folder> [reference.json]     compare a finished run
  python3 reference.py quick [reference.json] [release ...]  without processing: grouping
                                                             and cover/record per merged part
Result: OK per release or the differences; exit code 1 on any difference.
"""
import contextlib, glob, io, json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', 'Resources', 'Tools')
sys.path.insert(0, os.path.abspath(TOOLS))
GOLDEN = os.path.join(HERE, 'reference.json')
SCANS = os.path.expanduser('~/Desktop/vinyl')
MM_TOLERANCE = 0.025      # afmetingen mogen 2,5% afwijken (bijsnijden, rek)
LABEL_LIMIT = 1.2         # graden: rechte tekstregels op het label (zoals TEXT_LINE_MIN)

from PIL import Image
Image.MAX_IMAGE_PIXELS = None


def scan_id(path):
    return os.path.basename(path)


def dpi_of(path):
    try:
        with Image.open(path) as im:
            d = im.info.get('dpi')
            return float(d[0]) if d else None
    except OSError:
        return None


def release_of(run):
    request = json.load(open(os.path.join(run, 'Studio-verwerking.json')))
    return request['inputs'][0]['path'].split('/')[-2]


def label_angle(path):
    import scan_cutout as C
    with Image.open(path) as im:
        im = im.convert('RGB'); s = im.width; lb = int(s * .18); c = s // 2
        return C.text_line_angle(im.crop((c - lb, c - lb, c + lb, c + lb)))


def describe_run(run):
    """Per groep scans: soort, onderdelen, mm en labelhoek van de uitvoer."""
    records = json.load(open(os.path.join(run, 'Studio-onderdelen.json')))['files']
    groups = {}
    for record in records:
        key = tuple(sorted(scan_id(s) for s in record['scans']))
        group = groups.setdefault(key, {'scans': list(key), 'type': record['type'], 'outputs': []})
        path = os.path.join(run, record['name'])
        with Image.open(path) as im:
            w, h = im.size
        dpi = dpi_of(record['scans'][0]) or 300.0
        out = {'part': re.sub(r'_\d+$', '', record['part']), 'mm': [round(w / dpi * 25.4, 1), round(h / dpi * 25.4, 1)]}
        if record['type'] == 'vinyl':
            angle = label_angle(path)
            out['label'] = None if angle is None else round(angle, 2)
        group['outputs'].append(out)
    for group in groups.values():
        group['outputs'].sort(key=lambda o: (o['part'], o['mm']))
    return sorted(groups.values(), key=lambda g: g['scans'])


def record(run_root, target):
    golden = {}
    for run in sorted(glob.glob(os.path.join(run_root, 'Scans *'))):
        release = release_of(run)
        request = json.load(open(os.path.join(run, 'Studio-verwerking.json')))
        golden[release] = describe_run(run)
        golden.setdefault('_inputs', {})[release] = [scan_id(i['path']) for i in request['inputs'] if not i.get('reference')]
        print(f'{release}: {len(golden[release])} groups recorded', flush=True)
    json.dump(golden, open(target, 'w'), indent=1, ensure_ascii=False)


def close(a, b):
    return all(abs(x - y) <= MM_TOLERANCE * max(x, y) for x, y in zip(sorted(a), sorted(b)))


def compare_groups(expected, found, check_outputs=True):
    problems = []
    want = {tuple(g['scans']): g for g in expected}
    got = {tuple(g['scans']): g for g in found}
    for key in sorted(set(want) - set(got)):
        problems.append(f'missing group: {", ".join(key)}')
    for key in sorted(set(got) - set(want)):
        problems.append(f'unexpected group: {", ".join(key)}')
    for key in sorted(set(want) & set(got)):
        a, b = want[key], got[key]
        label = key[0] + (f' (+{len(key) - 1})' if len(key) > 1 else '')
        if a['type'] != b['type']:
            problems.append(f'{label}: {b["type"]} instead of {a["type"]}')
        if not check_outputs:
            continue
        if Counter(o['part'] for o in a['outputs']) != Counter(o['part'] for o in b['outputs']):
            problems.append(f'{label}: parts {[o["part"] for o in b["outputs"]]} instead of {[o["part"] for o in a["outputs"]]}')
        for x, y in zip(a['outputs'], b['outputs']):
            if not close(x['mm'], y['mm']):
                problems.append(f'{label} {y["part"]}: {y["mm"]} mm instead of {x["mm"]} mm')
            if b['type'] == 'vinyl' and y.get('label') is not None and abs(y['label']) >= LABEL_LIMIT:
                problems.append(f'{label} {y["part"]}: label {y["label"]:+.1f} degrees skewed')
    return problems


def report(release, problems):
    if problems:
        print(f'FAIL  {release}:', flush=True)
        for p in problems:
            print('      - ' + p, flush=True)
    else:
        print(f'OK    {release}', flush=True)


def compare_run(run_root, golden):
    bad = 0
    for run in sorted(glob.glob(os.path.join(run_root, 'Scans *'))):
        if not os.path.exists(os.path.join(run, 'Studio-onderdelen.json')) or not os.path.exists(os.path.join(run, 'Studio-verwerking.json')):
            print(f'FAIL  {os.path.basename(run)}: processing not finished (no result)'); bad += 1; continue
        release = release_of(run)
        if release not in golden or release.startswith('_'):
            print(f'?     {release}: not in the reference'); continue
        problems = compare_groups(golden[release], describe_run(run))
        report(release, problems); bad += bool(problems)
    return bad


def quick(golden, releases):
    """Zonder te verwerken: groeperen op de originele scans, en per samengevoegd
    onderdeel hoes of plaat en het kader (mm) zoals het samenvoegen ze kiest."""
    import scan_alles as A, scan_stitch as ST
    A.progress = lambda *a, **k: None
    class Stop(Exception):
        pass
    state = {}
    find_square, find_circle = ST.find_square, ST.find_circle
    def square(*args, **kw):
        state['sq'] = find_square(*args, **kw); state['size'] = args[2]
        if max(args[2]) / min(args[2]) >= ST.SPREAD_ASPECT:     # uitgeklapte binnenkant: altijd hoes
            state['disc'] = False; raise Stop
        return state['sq']
    def circle(gray, cover, G, *args, **kw):
        ci = find_circle(gray, cover, G, *args, **kw); sq = state.get('sq')
        holed = ci is not None and sq is not None and not sq[4] and ci[0] > .85 * sq[3] and ST.centre_hole(gray, cover, ci[1])
        state['disc'] = ci is not None and (sq is None or (not sq[4] and (ci[0] > 1.15 * sq[3] or holed)))
        raise Stop
    ST.find_square, ST.find_circle = square, circle
    bad = 0
    for release in releases:
        folder = os.path.join(SCANS, release)
        # precies de scans van de vastgelegde run (een map kan ook andere scans bevatten)
        paths = [os.path.join(folder, name) for name in golden['_inputs'][release]]
        with contextlib.redirect_stdout(io.StringIO()):
            grouped = A.groups(paths)
        expected = [g for g in golden[release] if len(g['scans']) > 1]
        found = []
        for group in grouped:
            if len(group) < 2:
                continue
            state.clear(); sys.argv = ['scan_stitch.py', '/tmp/reference-x.png'] + group + ['--rechtop', '--snelle-tussenbestanden']
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    ST.main()
            except Stop:
                pass
            except Exception as error:          # bv. te weinig schijfruimte
                print(f'      ({release}: {scan_id(group[0])} could not be measured: {error})'); continue
            disc = state.get('disc', False)
            found.append({'scans': sorted(scan_id(p) for p in group), 'type': 'vinyl' if disc else 'hoes', 'outputs': []})
        # enkele scans: alleen de indeling telt
        singles = [g for g in golden[release] if len(g['scans']) == 1]
        grouped_singles = [{'scans': [scan_id(g[0])], 'type': None, 'outputs': []} for g in grouped if len(g) == 1]
        problems = compare_groups(expected, found, check_outputs=False)
        want_single = {tuple(g['scans']) for g in singles}; got_single = {tuple(g['scans']) for g in grouped_singles}
        problems += [f'single scan missing/merged: {k[0]}' for k in sorted(want_single - got_single)]
        # een losse scan die in de gouden set nergens voorkomt (lege scan, overgeslagen) telt niet
        in_golden = {s for g in golden[release] for s in g['scans']}
        problems += [f'scan stands alone but belongs to a group: {k[0]}' for k in sorted(got_single - want_single) if k[0] in in_golden]
        report(release, problems); bad += bool(problems)
    return bad


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'record':
        record(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else GOLDEN)
    elif mode == 'run':
        sys.exit(1 if compare_run(sys.argv[2], json.load(open(sys.argv[3] if len(sys.argv) > 3 else GOLDEN))) else 0)
    elif mode == 'quick':
        target = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].endswith('.json') else GOLDEN
        golden = json.load(open(target))
        chosen = [a for a in sys.argv[2:] if not a.endswith('.json')] or sorted(r for r in golden if not r.startswith('_'))
        sys.exit(1 if quick(golden, chosen) else 0)
    else:
        print(__doc__)
