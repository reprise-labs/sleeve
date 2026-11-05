"""Real worker output must drive progress; save/check phases have no percentage."""
from pathlib import Path
import subprocess,json,sys
resources=Path(__file__).resolve().parents[1]/'Resources';work=Path(sys.argv[1]).resolve();work.mkdir(exist_ok=True,parents=True)
worker=work/'progress_worker.py';worker.write_text("import time\nfor line in ['[2/6] testscan','volle resolutie opbouwen: 4000x4000 px','  12%','  37%','  100%','klaar: testscan']:\n print(line,flush=True)\n time.sleep(.05)\n")
code='import sys;sys.path.insert(0,'+repr(str(resources))+');import studio_bridge as b;b.run(['+repr(str(worker))+'])'
p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10);assert p.returncode==0,p.stderr
events=[json.loads(s) for s in p.stdout.splitlines()];progress=[e for e in events if e['event']=='progress']
assert [e['fraction'] for e in progress]==[None,0,.12,.37,None,None],progress
assert all(e['index']==2 and e['total']==6 for e in progress)
assert progress[-2]['phase']=='Beeld opslaan' and progress[-1]['phase']=='Controle en uitsnijden'
(work/'RESULTAAT.json').write_text(json.dumps({'measured_worker_progress_forwarded':True,'no_invented_percentage_for_save_and_check':True},indent=2));print('Voortgang klopt met echte werkermeldingen; geen percentage tijdens opslaan/controleren.')

worker.write_text("import sys\nprint('ValueError: Onvolledige schijf: 0.9% ontbreekt. Selecteer alle deelscans samen.')\nsys.exit(1)\n")
p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10)
assert p.returncode!=0 and 'RuntimeError: Onvolledige schijf: 0.9%' in p.stderr
print('De concrete onvolledigheidsmelding blijft zichtbaar in de app.')

# Structured phases clear the previous percentage; counts are actual work, not ETA.
payloads=[{'phase':'Scans vergelijken','fraction':.25,'scope':'preparation','unitsDone':2,'unitsTotal':8},
 {'phase':'Overgangen afwerken','fraction':.5,'scope':'component','unitsDone':4,'unitsTotal':8,'completedParts':1},
 {'phase':'Schijf opslaan','fraction':None,'scope':'component'},
 {'phase':'Namen maken','fraction':None,'scope':'finishing','completedParts':6}]
worker.write_text('import json\nprint("[2/6] bron.png")\n'+''.join('print('+repr('SLEEVE_PROGRESS '+json.dumps(payload))+')\n' for payload in payloads))
p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10)
assert p.returncode==0,p.stderr
progress=[json.loads(line) for line in p.stdout.splitlines() if json.loads(line).get('event')=='progress']
assert [event['fraction'] for event in progress]==[None,.25,.5,None,None]
assert progress[1]['scope']=='preparation' and progress[1]['index'] is None
assert progress[2]['unitsDone']==4 and progress[2]['completedParts']==1
assert progress[-1]['index'] is None and progress[-1]['completedParts']==6
print('Echte staptellingen, onbekende opslagduur en afronden worden afzonderlijk doorgegeven.')
