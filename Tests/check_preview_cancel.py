"""Stopping during initial decoding cleans job caches before in-flight threads end."""
from pathlib import Path
from PIL import Image
import sys,subprocess,os,time,json
root=Path(__file__).resolve().parents[1];work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=True)
scratch=work/'scratch';scratch.mkdir();inputs=[]
for index in range(3):
 path=work/f'{index}.png';Image.new('RGB',(40,40),(index*10,140,210)).save(path);inputs.append(str(path))
started=work/'started';launcher=work/'launcher.py'
launcher.write_text('''import sys,time,numpy as np
from pathlib import Path
sys.path.insert(0,'''+repr(str(root/'Resources/Tools'))+''')
import scan_alles as A
import shutil
from types import SimpleNamespace
shutil.disk_usage=lambda _:SimpleNamespace(free=20*1024**3)
A.CU.ocr_tool=lambda:None
def decode(path,factors,inspector=None):
 assert len(factors)==3
 Path('''+repr(str(started))+''').touch();time.sleep(1.2)
 return [np.zeros((40,40,3),np.uint8) for _ in factors],None
A.ST.load_previews=decode
sys.argv=['scan_alles',*'''+repr(inputs)+''','--geen-vragen','--uit','''+repr(str(work/'outputs'))+''']
A.main()
''')
with (work/'cancel.log').open('w') as log:
 process=subprocess.Popen([sys.executable,str(launcher)],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,TMPDIR=str(scratch),PYTHONDONTWRITEBYTECODE='1'),start_new_session=True)
 limit=time.monotonic()+5
 while not started.exists():
  assert process.poll() is None
  if time.monotonic()>limit:process.kill();raise AssertionError('Initial decoder did not start')
  time.sleep(.02)
 assert list(scratch.glob('sleeve_alles_*'))
 process.terminate();code=process.wait(timeout=3)
 assert code==143,code
 assert not list(scratch.glob('sleeve_alles_*')),'A decoder recreated a removed job cache'
print({'stop_during_preview_cleans_cache':True,'in_flight_decoder_does_not_recreate_cache':True})
