"""Manual circle corrections preserve pixels/metadata and never overwrite their source."""
from pathlib import Path
import json,subprocess,sys,hashlib
import numpy as np
from PIL import Image,ImageCms,ImageOps
root=Path(__file__).resolve().parents[1];work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=True)
bridge=root/'Resources/studio_bridge.py';checks={}
def signature(p):
 s=p.stat();return f'{s.st_size}:{s.st_mtime_ns//10**9}:{s.st_mtime_ns%10**9}'
def job(req,name,ok=True):
 out=work/name;out.mkdir();req['output']=str(out);f=out/'request.json';f.write_text(json.dumps(req))
 p=subprocess.run([sys.executable,str(bridge),str(f)],capture_output=True,text=True,timeout=120)
 (out/'events.jsonl').write_text(p.stdout+p.stderr)
 assert (p.returncode==0)==ok,(p.stdout,p.stderr)
 events=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
 return events
w,h=900,800;y,x=np.ogrid[:h,:w];arr=np.empty((h,w,4),dtype=np.uint8);arr[:,:,0]=x%256;arr[:,:,1]=y%256;arr[:,:,2]=(x+y)%256;arr[:,:,3]=255;arr[365:375,445:455,3]=0
source=work/'bron.png';icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes();Image.fromarray(arr).save(source,icc_profile=icc,dpi=(600,600))
original=source.read_bytes();req={'action':'manualCrop','inputs':[{'path':str(source),'part':'cd'}],'sourceSignature':signature(source),'cropX':.5,'cropY':.5,'cropDiameter':.8,'cropPart':'cd'}
events=job(req,'crop');file=next(e['files'][0] for e in events if e['event']=='outputs');result=Path(file['path']);out=np.array(Image.open(result))
assert out.shape==(640,640,4)
assert np.array_equal(out[:,:,:3],arr[80:720,130:770,:3]);assert out[285:295,315:325,3].max()==0
assert np.all(out[:,:,3]<=arr[80:720,130:770,3]);assert out[0,0,3]==0
with Image.open(result) as im:assert im.info['icc_profile']==icc and abs(im.info['dpi'][0]-600)<.01
assert source.read_bytes()==original
assert next(e['audits'][0] for e in events if e['event']=='audit')['round']
checks['pixels_alpha_metadata_and_source_preserved']=True
job(dict(req,cropX=0),'outside',False);job(dict(req,sourceSignature='verouderd'),'stale',False)
checks['outside_and_changed_source_rejected']=True
# EXIF rotation must match the orientation used by the native preview.
jpg=work/'gedraaid.jpg';im=Image.fromarray(arr[:,:,:3]);exif=Image.Exif();exif[274]=6;im.save(jpg,exif=exif)
rotated=np.array(ImageOps.exif_transpose(Image.open(jpg)).convert('RGBA'))
r=dict(req,inputs=[{'path':str(jpg),'part':'cd'}],sourceSignature=signature(jpg),cropDiameter=.5)
events=job(r,'exif');p=Path(next(e['files'][0]['path'] for e in events if e['event']=='outputs'));actual=np.array(Image.open(p));H,W=rotated.shape[:2];d=round(.5*min(W,H));left=round(.5*W-d/2);top=round(.5*H-d/2)
assert np.array_equal(actual[:,:,:3],rotated[top:top+d,left:left+d,:3]);checks['exif_orientation_matches_preview']=True
# Exercise the real scan engine with an explicitly selected single part.
sample=root/'Resources/Samples/Voorbeeld_sidea.png'
events=job({'action':'scan','inputs':[{'path':str(sample),'part':'sideb'}],'rerunPart':'sideb','useNames':False,'useStand':False,'useColour':False},'retry')
outputs=[f for e in events if e['event']=='outputs' for f in e['files']];paths={f['path'] for f in outputs}
assert len(paths)==1 and all(f.get('part')=='sideb' for f in outputs)
checks['real_single_part_retry_keeps_explicit_side']=True
(work/'RESULTAAT.json').write_text(json.dumps(checks,indent=2));print(checks)
