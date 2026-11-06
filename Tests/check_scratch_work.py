"""A saved source store must not hide output/work maps that can still free disk."""
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import os,sys,subprocess,time,threading,tempfile,json
import numpy as np
root=Path(__file__).resolve().parents[1];tools=root/'Resources/Tools';sys.path.insert(0,str(tools))
from scan_memory import ScratchLease,MappedArrayStore,GiB
work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=True)
pool=work/'pool';pool.mkdir();ready=work/'ready';release=work/'release'
producer=work/'producer.py';producer.write_text('''from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import sys,time,numpy as np
sys.path.insert(0,'''+repr(str(tools))+''')
from scan_memory import ScratchLease,MappedArrayStore,GiB
with patch('scan_memory.shutil.disk_usage',return_value=SimpleNamespace(free=20*GiB)):
 with MappedArrayStore(16384,scratch='''+repr(str(work))+''') as buffers:
  output=buffers.empty('output',(64,64,4),np.uint8);output[:]=179
  with ScratchLease(GiB,'''+repr(str(work))+'''):pass
  Path('''+repr(str(ready))+''').touch()
  limit=time.monotonic()+8
  while not Path('''+repr(str(release))+''').exists():
   if time.monotonic()>limit:raise TimeoutError('consumer did not release producer')
   time.sleep(.02)
  output=None
''')
process=subprocess.Popen([sys.executable,str(producer)],env=dict(os.environ,SLEEVE_MEMORY_POOL=str(pool),PYTHONDONTWRITEBYTECODE='1'))
errors=[];acquired=threading.Event()
try:
 limit=time.monotonic()+5
 while not ready.exists():
  assert process.poll() is None
  if time.monotonic()>limit:raise TimeoutError('producer did not start')
  time.sleep(.02)
 assert list(pool.glob('scratch-work-*.json'))
 assert not [p for p in pool.glob('scratch-*.json') if not p.name.startswith('scratch-work-')]
 def free_space(_):
  return SimpleNamespace(free=(3 if list(pool.glob('scratch-work-*.json')) else 4)*GiB)
 with patch.dict(os.environ,{'SLEEVE_MEMORY_POOL':str(pool)}),patch('scan_memory.shutil.disk_usage',side_effect=free_space):
  def consume():
   try:
    with ScratchLease(int(3.4*GiB),str(work)):acquired.set()
   except BaseException as error:errors.append(error)
  thread=threading.Thread(target=consume);thread.start()
  assert not acquired.wait(.2) and not errors,errors
  release.touch();assert acquired.wait(3),errors
  thread.join(3);assert not thread.is_alive() and not errors,errors
 assert process.wait(timeout=3)==0
 assert not list(pool.glob('scratch-*.json'))
 # Own work maps cannot make progress while the same process waits for space.
 with patch.dict(os.environ,{'SLEEVE_MEMORY_POOL':str(pool)}),patch('scan_memory.shutil.disk_usage',return_value=SimpleNamespace(free=20*GiB)):
  with MappedArrayStore(1024,scratch=work) as buffers:
   output=buffers.empty('output',(8,8),np.uint8);output[:]=93
   with patch('scan_memory.shutil.disk_usage',return_value=SimpleNamespace(free=0)):
    try:
     with ScratchLease(3*GiB,str(work)):raise AssertionError('Expected real low-space error')
    except ValueError:pass
   assert np.all(output==93);output=None
 assert not list(pool.glob('scratch-*.json'))
finally:
 release.touch()
 if process.poll() is None:process.kill();process.wait()
report={'source_close_does_not_hide_live_output_maps':True,'waits_for_other_encoder_to_close_output':True,'own_work_does_not_cause_self_wait':True,'no_reservations_left_after_close':True}
(work/'RESULTAAT.json').write_text(json.dumps(report,indent=2));print(report)
