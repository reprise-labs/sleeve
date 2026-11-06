"""Parallel disk admission waits, accounts committed bytes, and clears dead claims."""
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import tempfile,os,sys,json,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Resources/Tools'))
from scan_memory import ScratchLease,GiB
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);free=[4*GiB];acquired=threading.Event();finish=threading.Event();errors=[]
 with patch.dict(os.environ,{'SLEEVE_MEMORY_POOL':str(root)}),patch('scan_memory.shutil.disk_usage',side_effect=lambda _:SimpleNamespace(free=free[0])):
  first=ScratchLease(3*GiB,folder);first.__enter__()
  def worker():
   try:
    with ScratchLease(3*GiB,folder):acquired.set();assert finish.wait(3)
   except BaseException as error:errors.append(error)
  thread=threading.Thread(target=worker);thread.start()
  assert not acquired.wait(.15)
  free[0]-=GiB;first.committed(GiB)
  assert json.loads(first.marker.read_text())['remaining']==GiB
  assert not acquired.wait(.15),'Writing reserved bytes must not manufacture free space'
  free[0]+=GiB;first.__exit__(None,None,None)
  assert acquired.wait(2),'Next renderer should proceed after source maps close'
  finish.set();thread.join(3);assert not thread.is_alive() and not errors,errors
  assert not list(root.glob('scratch-*.json'))
  stale=root/'scratch-dead.json';stale.write_text(json.dumps({'pid':999999999,'remaining':100*GiB}))
  with ScratchLease(3*GiB,folder):pass
  assert not stale.exists()
  free[0]=0
  try:
   with ScratchLease(3*GiB,folder):raise AssertionError('Expected a clear insufficient-space error')
  except ValueError as error:assert 'schijfruimte' in str(error)
print({'waits_for_live_renderer':True,'committed_bytes_not_double_counted':True,'dead_claims_removed':True,'genuine_low_space_rejected':True})
