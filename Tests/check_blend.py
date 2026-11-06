"""Full-resolution detail, overlap, holes and alpha survive the faster low-pass."""
from pathlib import Path
from unittest.mock import patch
import sys,json,time,contextlib,io
import numpy as np,cv2
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Resources/Tools'))
import scan_stitch as S
from scan_blend import detail_blur
from scan_fields import GainPlane
from scan_memory import MappedArrayStore
cv2.setNumThreads(2)
root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(17);reports=[]
for kind in ['paper','orange','clear','black']:
 h,w=1200,1400;y,x=np.mgrid[:h,:w]
 noise=rng.uniform(-6,6,(h,w,3))
 base={'paper':[235,237,239],'orange':[22,105,224],'clear':[165,170,173],'black':[19,20,22]}[kind]
 scene=np.clip(np.array(base)+noise,0,255).astype(np.uint8)
 scene[430:740,500:820]=35
 cv2.putText(scene,'DETAIL 123',(100,200),cv2.FONT_HERSHEY_SIMPLEX,2,(4,4,4),3)
 for radius in range(260,510,9):cv2.circle(scene,(700,600),radius,(35,72,100),1)
 paths=[]
 for k,start in enumerate([0,200]):
  part=scene[:,start:start+1200].astype(np.float32)
  if k:part*=np.linspace(.97,1.03,1200,dtype=np.float32)[None,:,None]
  p=root/f'{kind}-{k}.png';cv2.imwrite(str(p),np.clip(part,0,255).astype(np.uint8));paths.append(str(p))
 masks={0:np.zeros((300,350),bool),1:np.zeros((300,350),bool)}
 masks[0][:,:300]=True;masks[1][:,50:]=True
 if kind=='clear':
  # A real coverage hole must remain transparent, never be invented by filtering.
  masks[0][120:150,150:170]=False;masks[1][120:150,150:170]=False
 weights={k:cv2.distanceTransform(m.astype(np.uint8),cv2.DIST_L2,5)+m.astype(np.float32) for k,m in masks.items()}
 best=np.where(x[::4,::4]<700,0,1).astype(np.uint8)
 H={0:np.eye(3),1:np.array([[1.,0,50],[0,1,0],[0,0,1]])}
 shape=('none',None) if kind=='clear' else ('disc',(175,150,140)) if kind in ('orange','black') else ('square',None)
 plane=GainPlane([[.01,.04,-.02],[0,-.03,.05],[.02,.02,-.04]],(300,350))
 outputs=[];times=[]
 for optimized in [False,True]:
  fn=detail_blur if optimized else lambda a,s:cv2.GaussianBlur(a,(0,0),s)
  gains={1:plane if optimized else plane.rows(0,300)}
  start=time.monotonic()
  with contextlib.ExitStack() as stack,patch.object(S,'detail_blur',fn),contextlib.redirect_stdout(io.StringIO()):
   store=stack.enter_context(MappedArrayStore(1400*1200*4,scratch=root)) if optimized else None
   allocator=(lambda shape:store.empty('output',shape,np.uint8)) if store else None
   source_admission=[]
   out=S.render_full(paths,[0,1],H,np.eye(3),np.eye(3),.25,(350,300),None,{k:v.copy() for k,v in masks.items()},{k:v.copy() for k,v in weights.items()},gains,best,[0,1],None,shape,output_allocator=allocator,before_sources=lambda:source_admission.append(True))
   assert source_admission==[True]
   out=out.copy()
  outputs.append(out);times.append(time.monotonic()-start)
 a,b=outputs
 if kind=='clear':assert np.count_nonzero(a[500:580,620:660,3])==0,'The fixture must actually contain a transparent hole'
 diff=np.abs(a[:,:,:3].astype(np.int16)-b[:,:,:3].astype(np.int16))
 visible=a[:,:,3]>0;maximum=int(diff[visible].max());fraction=float(np.count_nonzero(diff[visible])/diff[visible].size)
 report={'kind':kind,'alpha_identical':bool(np.array_equal(a[:,:,3],b[:,:,3])),'max_visible_rgb_difference':maximum,'changed_channel_fraction':fraction,'reference_seconds':times[0],'optimized_seconds':times[1]}
 reports.append(report);print(report,flush=True)
 assert report['alpha_identical'] and maximum<=1 and fraction<.005,report
(root/'RESULTAAT.json').write_text(json.dumps(reports,indent=2))
