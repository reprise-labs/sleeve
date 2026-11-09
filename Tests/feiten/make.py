import json, os
V = os.path.expanduser('~/Desktop/vinyl'); OUT = os.path.expanduser('~/Desktop/sleeve_feiten/nacht')
g = json.load(open('/tmp/feiten/reference.json'))
URL = {'ta': 8388109, 'us': 27551973, 'gf': 8576092, 'hny': 27552009, 'deena': 28788697, 'fire': 33664818, 'fake': 19493197, 'queen': 19274500}
def S(a, b, ext='jpeg'): return [f'Scan {i}.{ext}' for i in range(a, b + 1)]
jobs = {}
for rel in ('ta', 'us', 'gf', 'hny', 'deena', 'fire'):
    groups = []
    for x in g[rel]:
        parts = [o['part'] for o in x['outputs']]
        groups.append(('inside' if len(parts) > 1 else parts[0], x['scans']))
    jobs[rel] = (f'{V}/{rel}', groups)
jobs['fake'] = (f'{V}/fake', [('front', S(1, 4)), ('back', S(5, 8)), ('insert', S(12, 15)), ('insert', S(16, 19))])
jobs['queen'] = (f'{V}/queen', [('sidea', S(1, 4)), ('sideb', S(6, 9)), ('insert', S(31, 34)), ('insert', S(35, 38))])
jobs['queen_hoes'] = (f'{V}/queen/hoes', [('front', ['Scan.jpeg'] + S(1, 3)), ('back', S(4, 7))])
for rel, (base, groups) in jobs.items():
    rows = [{'path': f'{base}/{s}', 'part': p, 'group': f'g{i}', 'reference': False, 'partial': False, 'source': ''}
            for i, (p, ss) in enumerate(groups) for s in ss]
    missing = [r['path'] for r in rows if not os.path.exists(r['path'])]
    assert not missing, missing
    os.makedirs(f'/tmp/nacht/{rel}', exist_ok=True)
    json.dump({'action': 'scan', 'inputs': rows, 'discogs': f'https://www.discogs.com/release/{URL[rel.split("_")[0]]}',
               'variant': '', 'useNames': True, 'useStand': True, 'format': 'vinyl', 'output': OUT}, open(f'/tmp/nacht/{rel}/req.json', 'w'), indent=1)
    print(rel, [(p, len(ss)) for p, ss in groups])
