"""Parallel progress, shared memory admission, failure and descendant cancellation."""
from pathlib import Path
import sys,subprocess,json,time,os,signal
root=Path(__file__).resolve().parents[1];tools=root/'Resources/Tools'
sys.path.insert(0,str(tools));from scan_workers import ComponentPool
work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=True)
worker=work/'worker.py';counter=work/'counter.json';counter.write_text(json.dumps({'active':0,'peak':0,'admission':[]}))
worker.write_text('''import sys,time,json,fcntl,subprocess,os
from pathlib import Path
sys.path.insert(0,'''+repr(str(tools))+''')
from scan_memory import MemoryLease
counter=Path(sys.argv[1]);index=int(sys.argv[2])
def change(delta):
 with counter.open('r+') as file:
  fcntl.flock(file,fcntl.LOCK_EX);data=json.load(file);data['active']+=delta;data['peak']=max(data['peak'],data['active']);assert 0<=data['active']<=72,data
  if delta==30:data['admission'].append(index)
  file.seek(0);file.truncate();json.dump(data,file);file.flush()
with MemoryLease(30) as lease:
 change(30);time.sleep(.12)
 change(-22);lease.resize(8)
 time.sleep(.05);lease.grow(28,phase='test decoder');change(20);time.sleep(.05)
 change(-16);lease.resize(12)
 print('SLEEVE_PROGRESS '+json.dumps({'phase':'test render','fraction':.5,'unitsDone':1,'unitsTotal':2}),flush=True)
 time.sleep(.12);change(-12)
''')
completed=[];ordered=[3,1,6,2,5,4]
with ComponentPool(6,work/'pool') as pool:
 for index in pool.run([(i,[sys.executable,str(worker),str(counter),str(i)]) for i in ordered]):
  completed.append(index);pool.finished(index)
data=json.loads(counter.read_text());assert sorted(completed)==list(range(1,7)) and data['active']==0 and data['peak']<=72 and data['admission']==ordered,data
# An error must stop other work promptly.
failure=work/'failure.py';failure.write_text("import sys,time\nif sys.argv[1]=='fail':time.sleep(.1);sys.exit(2)\ntime.sleep(60)\n")
start=time.monotonic()
try:
 with ComponentPool(2,work/'failure-pool') as pool:list(pool.run([(1,[sys.executable,str(failure),'fail']),(2,[sys.executable,str(failure),'wait'])]))
 raise AssertionError('Expected component failure')
except RuntimeError:pass
assert time.monotonic()-start<5
# Cancelling the parent also stops isolated worker process groups and grandchildren.
long=work/'long.py';long.write_text('''import sys,subprocess,time,os,json
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid]))
print('started',flush=True);time.sleep(60)
''')
launcher=work/'launcher.py';launcher.write_text('import sys\nsys.path.insert(0,'+repr(str(tools))+')\nfrom scan_workers import ComponentPool\nwith ComponentPool(2,'+repr(str(work/'cancel-pool'))+') as pool:\n list(pool.run('+repr([(i,[sys.executable,str(long),str(work/f'pids-{i}.json')]) for i in range(1,3)])+'))\n')
process=subprocess.Popen([sys.executable,str(launcher)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
limit=time.monotonic()+8
while not all((work/f'pids-{i}.json').exists() for i in (1,2)):
 if time.monotonic()>limit:process.kill();raise AssertionError('Worker did not start')
 time.sleep(.05)
pids=sum([json.loads((work/f'pids-{i}.json').read_text()) for i in (1,2)],[])
process.terminate();process.communicate(timeout=8)
def alive(pid):
 stat=subprocess.run(['/bin/ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
 return bool(stat and not stat.startswith('Z'))
limit=time.monotonic()+5
while any(alive(pid) for pid in pids) and time.monotonic()<limit:time.sleep(.1)
assert not any(alive(pid) for pid in pids),pids
report={'components_complete':True,'initial_memory_admission_keeps_priority':True,'memory_slots_never_exceeded':True,'failure_stops_peers':True,'cancellation_stops_workers_and_grandchildren':True}
(work/'RESULTAAT.json').write_text(json.dumps(report,indent=2));print(report)
