"""Actual component pipelines keep inputs, roles and pixels with parallel execution."""
from pathlib import Path
import sys,json,subprocess,os,hashlib,time
import numpy as np,cv2
from PIL import Image
root=Path(__file__).resolve().parents[1];work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=True)
source=work/'sources';source.mkdir(exist_ok=True);rng=np.random.default_rng(278);groups=[];paths=[]
for index,part in enumerate(['front','back','sidea']):
 scene=np.full((1200,1400,3),248,np.uint8)
 texture=rng.integers(25,225,(1000,1000,3),dtype=np.uint8);texture=cv2.GaussianBlur(texture,(0,0),1)
 scene[100:1100,200:1200]=texture
 if part=='sidea':
  y,x=np.mgrid[:1200,:1400];disc=(x-700)**2+(y-600)**2<530**2
  scene[~disc]=248;cv2.circle(scene,(700,600),180,(25,25,25),-1);cv2.putText(scene,'SIDE A',(590,610),cv2.FONT_HERSHEY_SIMPLEX,1.3,(240,240,240),3)
 else:cv2.putText(scene,'DEMO '+part.upper(),(300,600),cv2.FONT_HERSHEY_SIMPLEX,1.7,(0,0,0),4)
 names=[]
 for label,start in [('a',0),('b',400)]:
  path=source/f'{index}-{label}.png';Image.fromarray(scene[:,start:start+1000,::-1]).save(path,dpi=(300,300));names.append(path.name);paths.append(str(path))
 groups.append({'part':part,'files':names})
(source/'.anouk-referenties.json').write_text(json.dumps({'scan_groups':groups}))
before={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths};outputs=[]
for jobs in [1,3]:
 destination=work/('jobs-'+str(jobs));log=work/('jobs-'+str(jobs)+'.log')
 command=[sys.executable,str(root/'Resources/Tools/scan_alles.py'),*paths,'--geen-vragen','--workers',str(jobs),'--uit',str(destination)]
 with log.open('w') as file:result=subprocess.run(command,stdout=file,stderr=subprocess.STDOUT,timeout=120,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',VECLIB_MAXIMUM_THREADS='1'))
 assert result.returncode==0,log.read_text()[-5000:]
 manifest=json.loads((destination/'Studio-onderdelen.json').read_text())['files'];assert len(manifest)==3
 mapping={item['part']:destination/item['name'] for item in manifest};assert set(mapping)=={'front','back','sidea'}
 outputs.append(mapping)
for part in outputs[0]:
 a=np.array(Image.open(outputs[0][part]));b=np.array(Image.open(outputs[1][part]));assert a.shape==b.shape and np.array_equal(a,b),(part,a.shape,b.shape)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==value for p,value in before.items())
# A single existing cover still uses its own reading-direction path.
single=work/'single-cover';single_log=work/'single-cover.log'
single_input=work/'single-input';single_input.mkdir()
cover_source=single_input/'front.png';cover_source.write_bytes(outputs[0]['front'].read_bytes())
(single_input/'.anouk-referenties.json').write_text(json.dumps({'scan_groups':[{'part':'front','files':['front.png']}]}))
command=[sys.executable,str(root/'Resources/Tools/scan_alles.py'),str(cover_source),'--geen-vragen','--geen-discogs-namen','--een-onderdeel','--workers','1','--uit',str(single)]
with single_log.open('w') as file:result=subprocess.run(command,stdout=file,stderr=subprocess.STDOUT,timeout=40,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',VECLIB_MAXIMUM_THREADS='1'))
assert result.returncode==0,single_log.read_text()[-3000:]
assert len(json.loads((single/'Studio-onderdelen.json').read_text())['files'])==1
report={'actual_parallel_and_sequential_RGBA_identical':True,'component_roles_and_sources_preserved':True,'all_input_bytes_unchanged':True}
(work/'RESULTAAT.json').write_text(json.dumps(report,indent=2));print(report)
