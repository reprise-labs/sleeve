"""Checks for the 0.5.27 fixes; no album scans or internet needed.

- Discogs fetch: one request per address, remembered, retried after 'too many requests'.
- A part that hangs is stopped at its time limit and reported; the bridge goes on.
- A decision is remade with the same format, packaging and resolution as the first run.
- The side letter on a label is read in its common spellings, and not from a title.
"""
import http.server, io, json, os, subprocess, sys, threading, time
from pathlib import Path
root = Path(__file__).resolve().parents[1]; work = Path(sys.argv[1]).resolve(); work.mkdir(exist_ok=True, parents=True)
sys.path.insert(0, str(root / 'Resources/Tools')); sys.path.insert(0, str(root / 'Resources'))

# --- 1. Discogs: remembered and retried ------------------------------------------------------
os.environ['SLEEVE_NET_CACHE'] = str(work / 'net')
import scan_net
calls = {'busy': 0, 'gone': 0, 'down': 0}
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        name = self.path.strip('/'); calls[name] += 1
        if name == 'busy' and calls[name] == 1:            # first time: too many requests
            self.send_response(429); self.send_header('Retry-After', '0'); self.end_headers(); return
        if name == 'gone':
            self.send_response(404); self.end_headers(); return
        if name == 'down':
            self.send_response(503); self.end_headers(); return
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"title": "Demo"}')
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_address[1]}/'
waited = []
assert scan_net.fetch(base + 'busy', sleep=waited.append) == b'{"title": "Demo"}' and calls['busy'] == 2 and len(waited) == 1
assert scan_net.fetch(base + 'busy', sleep=waited.append) == b'{"title": "Demo"}' and calls['busy'] == 2      # from memory
import scan_naam, scan_discogs
assert scan_naam.get(base + 'busy') == {'title': 'Demo'} and scan_discogs.get(base + 'busy') == b'{"title": "Demo"}' and calls['busy'] == 2
for name, tries in (('gone', 1), ('down', 4)):             # a real 'not found' is not retried; a fault is, then reported
    try:
        scan_net.fetch(base + name, sleep=waited.append); raise AssertionError(name + ' should fail')
    except RuntimeError:
        assert calls[name] == tries, (name, calls)
server.shutdown()

# --- 2. side letter --------------------------------------------------------------------------
import scan_feitenroute as FR
for text, want in (('SIDE A', 'a'), ('Side Two', 'b'), ('side 3', 'c'), ('STEREO\nKant B 33 RPM', 'b'), ('A-Side', 'a'), ('Seite 2', 'b'),
                   ('Side by side', None), ('Face a storm', None), ('On a side street', None), ('Queen For A Day', None), ('', None)):
    assert FR.side_letter(text) == want, (text, FR.side_letter(text), want)

# --- 3. a hanging part is stopped and reported ------------------------------------------------
import studio_bridge as B
B.EVENT_STREAM = io.StringIO()
fake = work / 'Tools'; fake.mkdir(exist_ok=True)
pidfile = work / 'child.pid'
(fake / 'scan_feitenroute.py').write_text(
    'import subprocess, sys, time\n'
    f'c = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"]); open({str(pidfile)!r}, "w").write(str(c.pid))\n'
    'print("SLEEVE_STEP hanging on purpose", file=sys.stderr, flush=True); time.sleep(120)\n')
real_tools = B.TOOLS; B.TOOLS = fake; os.environ['SLEEVE_PART_TIMEOUT'] = '2'
t0 = time.time(); result = B.feiten_part({}, 'front', [str(root / 'Resources/Samples/Voorbeeld_sidea.png')], work, work / 'hang')
took = time.time() - t0
assert result['verdict'] == 'FOUT' and 'stopped after' in result['why'][0] and took < 20, (result, took)
time.sleep(0.5)
child_pid = int(pidfile.read_text())
alive = subprocess.run(['/bin/ps', '-o', 'stat=', '-p', str(child_pid)], capture_output=True, text=True).stdout.strip()
assert not alive or alive.startswith('Z'), 'the hanging part left a process behind: ' + alive
B.TOOLS = real_tools; del os.environ['SLEEVE_PART_TIMEOUT']
assert 900 <= B.part_time_limit([str(root / 'Resources/Samples/Voorbeeld_sidea.png')]) < 960

# --- 4. a decision uses the facts of the first run ----------------------------------------------
assert B.release_format({'format': 'cd', 'packaging': 'slimjewel'}, ['front']) == 'cd-slimjewel'
assert B.release_format({'format': 'auto', 'packaging': 'auto'}, ['front', 'cd']) == 'cd'
assert B.release_format({'format': 'vinyl', 'packaging': 'digipak'}, ['front']) == 'vinyl'
assert B.release_format({'format': 'auto'}, ['sidea']) == ''
run = work / 'run'; run.mkdir(exist_ok=True)
assert B.run_facts(run) is None
(run / 'Studio-verwerking.json').write_text(json.dumps({'action': 'scan', 'route': 'feiten', 'format': 'cd-cardsleeve', 'release_dpi': 1200.0}))
assert B.run_facts(run) == ('cd-cardsleeve', 1200.0)
(run / 'Studio-verwerking.json').write_text(json.dumps({'action': 'colour'}))
assert B.run_facts(run) is None

checks = {'discogs_remembered_and_retried': True, 'side_letter_spellings': True, 'hanging_part_stopped_and_reported': True, 'decision_uses_first_run_facts': True}
(work / 'RESULTAAT.json').write_text(json.dumps(checks, indent=2)); print(checks)
