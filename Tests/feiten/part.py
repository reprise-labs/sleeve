"""Eén onderdeel door de feitenroute: samenvoegen, uitsnijden, rechtop. Gebruik: part.py <release> <onderdeel> <discogs-id> <scan>..."""
import subprocess, sys, json, re, os
P = sys.executable
T = '/Users/andrevanos/Documents/Codex/2026-11-04/referenced-chatgpt-conversation-this-is-an/outputs/Sleeve/Resources/Tools'
rel, name, rid, files = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
O = f'/tmp/feiten/{rel}'; os.makedirs(O, exist_ok=True)
D = os.path.expanduser(f'~/Desktop/sleeve_feiten/{rel}'); os.makedirs(D, exist_ok=True)
words = f'{O}/words.json'
if not os.path.exists(words):
    sys.path.insert(0, T); import scan_naam as N
    d = N.get(f'https://api.discogs.com/releases/{rid}')
    json.dump([a['name'] for a in d.get('artists', [])] + [d['title']] + [t['title'] for t in d.get('tracklist', [])] + [l['name'] for l in d.get('labels', [])], open(words, 'w'))
part = 'insert' if name.startswith('insert') else name
raw, crop, up = f'{O}/{name}_raw.png', f'{O}/{name}_crop.png', f'{D}/{name}.png'
st = subprocess.run([P, f'{T}/scan_stitch.py', raw] + files + ['--vorm', 'ruw', '--klein'], capture_output=True, text=True)
if not os.path.exists(raw):
    print('STITCH FAILED', (st.stdout + st.stderr)[-500:]); sys.exit(1)
fe = subprocess.run([P, f'{T}/scan_feiten.py', raw, part, '--out', crop], capture_output=True, text=True).stdout
dpi = json.load(open(raw + '.scans.json'))['dpi']
args = [P, f'{T}/scan_rechtop.py', crop, '--words', words, '--out', up] + (['--disc', '--dpi', str(dpi)] if part.startswith('side') else [])
ro = json.loads(subprocess.run(args, capture_output=True, text=True).stdout)
for l in fe.splitlines():
    if l.startswith(('precise', 'final', 'centre hole')): print(l)
m = re.search(r'"message": "([^"]*)"', fe)
if m: print('MESSAGE:', m[1])
print('UPRIGHT:', ro['rotate_clockwise'], ro['verdict'], ro.get('read_upright'))
subprocess.run(['open', up])
