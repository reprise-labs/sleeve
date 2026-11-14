#!/usr/bin/env python3
"""Toets voor het automatisch indelen (scan_vakken.py): komt elke scan van de releases in reference.json
in het goede vak? Er wordt niets verwerkt, dus dit duurt minuten.

  indeling.py [naam ...]

Per release: GOED (elke stapel is precies één vak, met de goede naam), of wat er mis is:
  FOUT       scans van verschillende onderdelen in één stapel, of een stapel met een verkeerde naam
  GESPLITST  een onderdeel in meer stapels (geen fout vak, wel extra slepen)
  NAAMLOOS   een stapel klopt, maar heeft geen naam (jij kiest het onderdeel)
"""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
REF = json.load(open(Path(__file__).with_name('reference.json')))
SCANS = Path(os.environ.get('SLEEVE_TESTSCANS') or Path.home() / 'Desktop')
PY = Path.home() / 'Library/Application Support/com.repriselabs.Sleeve/Runtime/bin/python3'
only = set(sys.argv[1:])
total = {'GOED': 0}; bad = 0
for c in REF['cases']:
    if only and c['name'] not in only:
        continue
    folder = SCANS / c['folder']
    truth = {str(folder / f): (i, s['part']) for i, s in enumerate(c['slots']) for f in s['files']}
    if not all(Path(p).exists() for p in truth):
        print(f"{c['name']:26s} overgeslagen (scans niet op deze Mac)"); continue
    r = subprocess.run([str(PY if PY.exists() else sys.executable), str(ROOT / 'Resources/Tools/scan_vakken.py'),
                        c.get('discogs', ''), c.get('format', ''), '', *truth], capture_output=True, text=True)
    try:
        groups = json.loads(r.stdout.strip().splitlines()[-1])['groups']
    except (ValueError, IndexError, KeyError):
        print(f"{c['name']:26s} FOUT: geen uitkomst ({(r.stderr or '').strip().splitlines()[-1:]})"); bad += 1; continue
    notes = []; verdict = 'GOED'
    placed = {f for g in groups for f in g['files']}
    if placed != set(truth):
        notes.append(f'{len(set(truth) - placed)} scans in geen stapel'); verdict = 'FOUT'
    per_slot = {}
    for g in groups:
        slots = {truth[f][0] for f in g['files'] if f in truth}
        want = {truth[f][1] for f in g['files'] if f in truth}
        if len(slots) > 1:
            verdict = 'FOUT'; notes.append('samen: ' + '+'.join(sorted(want)))
        elif g['part'] == 'unknown':
            if verdict == 'GOED': verdict = 'NAAMLOOS'
            notes.append(f'naamloos: {want.pop()}')
        elif g['part'] not in want:
            verdict = 'FOUT'; notes.append(f"{g['part']} moet {want.pop()} zijn")
        for sl in slots:
            per_slot[sl] = per_slot.get(sl, 0) + 1
    split = [c['slots'][sl]['part'] for sl, n in per_slot.items() if n > 1]
    if split:
        notes.append('gesplitst: ' + ', '.join(split))
        if verdict in ('GOED', 'NAAMLOOS'): verdict = 'GESPLITST'
    total[verdict] = total.get(verdict, 0) + 1; bad += verdict == 'FOUT'
    print(f"{c['name']:26s} {verdict:9s} {'; '.join(notes)}", flush=True)
print('Samen:', ', '.join(f'{k} {v}' for k, v in total.items()))
sys.exit(1 if bad else 0)
