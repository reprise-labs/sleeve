import json,os,signal,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=Path(sys.argv[1]).resolve();folder.mkdir(exist_ok=True,parents=True)
script=folder/'temporary_worker.py';pidfile=folder/'worker.json'
script.write_text('import os,subprocess,time,json\np=subprocess.Popen(["/bin/sleep","120"])\nopen('+repr(str(pidfile))+',"w").write(json.dumps([os.getpid(),p.pid]))\np.wait()\n')
code='import sys;sys.path.insert(0,'+repr(str(root/'Resources'))+');import studio_bridge as b;b.run(['+repr(str(script))+'])'
p=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
for _ in range(80):
 if pidfile.exists():break
 time.sleep(.1)
assert pidfile.exists()
ids=json.loads(pidfile.read_text());p.terminate();stdout,stderr=p.communicate(timeout=5)
assert p.returncode==130,(p.returncode,stdout,stderr)
for _ in range(30):
 statuses=[subprocess.run(['/bin/ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip() for pid in ids]
 if all(not st or st.startswith('Z') for st in statuses):break
 time.sleep(.1)
assert all(not st or st.startswith('Z') for st in statuses),statuses
(folder/'RESULTAAT.json').write_text(json.dumps({'cancel_stops_worker_and_descendants':True},indent=2));print('Stoppen beëindigt ook onderliggende processen.')
